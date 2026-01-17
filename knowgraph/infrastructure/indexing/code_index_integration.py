"""Integration module for code analysis in KnowGraph indexing pipeline.

This module provides hooks for automatic code detection and CPG generation
during the indexing process.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CodeIndexIntegration:
    """Handles code analysis integration during indexing."""

    def __init__(self):
        """Initialize code index integration."""
        self.cpg_generated = False
        self.cpg_path: Optional[Path] = None
        self.entities_extracted = 0

    def process_code_directory(
        self,
        input_path: Path,
        graph_path: Path,
        skip_cpg: bool = False
    ) -> dict:
        """Process code directory for indexing.

        Args:
            input_path: Directory to analyze
            graph_path: Graph storage path
            skip_cpg: Skip CPG generation (for testing)

        Returns:
            Dictionary with processing results
        """
        from knowgraph.core.joern import JoernProvider
        from knowgraph.domain.intelligence.code_entity_extractor import CodeEntityExtractor
        from knowgraph.infrastructure.indexing.code_file_detector import CodeFileDetector

        results = {
            "code_files_detected": 0,
            "cpg_generated": False,
            "cpg_path": None,
            "entities_extracted": 0,
            "error": None
        }

        try:
            # Step 1: Detect code files
            logger.info("Detecting code files...")
            detector = CodeFileDetector()
            code_files = detector.detect_code_files(input_path)

            results["code_files_detected"] = len(code_files)

            if not code_files:
                logger.info("No code files detected")
                return results

            # Get statistics
            stats = detector.get_statistics(code_files)
            logger.info(f"Found {stats['total_files']} code files ({stats['total_loc']} LOC)")

            # Step 2: Check if CPG generation is worthwhile
            if not detector.should_generate_cpg(code_files):
                logger.info("Skipping CPG generation (below threshold)")
                return results

            if skip_cpg:
                logger.info("CPG generation skipped (skip_cpg=True)")
                return results

            # Step 2.5: Check for incremental updates (NEW - Phase 4)
            from knowgraph.infrastructure.indexing.incremental_cpg import IncrementalCPGUpdater

            updater = IncrementalCPGUpdater(graph_path)
            changes = updater.detect_changes(code_files)
            change_summary = updater.get_change_summary(changes)

            logger.info(f"File changes: {change_summary}")

            # Skip CPG regeneration if no changes
            if not updater.should_regenerate_cpg(changes):
                logger.info("No file changes detected - skipping CPG regeneration")

                # Try to use cached CPG
                from knowgraph.infrastructure.caching import CPGCache
                cache = CPGCache()
                cached_cpg = cache.get_cached_cpg(input_path)

                if cached_cpg:
                    logger.info(f"Using cached CPG: {cached_cpg}")
                    results["cpg_generated"] = True
                    results["cpg_path"] = str(cached_cpg)
                    results["cpg_from_cache"] = True

                    # Continue with entity extraction using cached CPG
                    cpg_path = cached_cpg
                    self.cpg_path = cpg_path
                    self.cpg_generated = True
                else:
                    logger.warning("No cached CPG available despite no changes")
                    # Fall through to generate new CPG

            # Step 3: Generate CPG (if needed)
            if not results.get("cpg_from_cache"):
                logger.info("Generating CPG...")

                # Check if parallel generation is worthwhile (NEW - Phase 4)
                from knowgraph.infrastructure.indexing.parallel_cpg import ParallelCPGGenerator

                parallel_gen = ParallelCPGGenerator(max_workers=4)
                use_parallel = parallel_gen.should_use_parallel(code_files)

                if use_parallel:
                    logger.info("Using parallel CPG generation for large repository")
                    try:
                        import tempfile
                        # Use persistent temp directory (don't auto-delete)
                        tmpdir = Path(tempfile.mkdtemp(prefix="knowgraph_cpg_"))
                        logger.info(f"Parallel CPG temp dir: {tmpdir}")

                        cpg_paths = parallel_gen.generate_parallel(
                            code_files,
                            tmpdir,
                            timeout=300
                        )

                        if cpg_paths:
                            # Use first generated CPG (simplified)
                            cpg_path = cpg_paths[0]
                            results["cpg_generated"] = True
                            results["cpg_path"] = str(cpg_path)
                            results["parallel_generation"] = True
                            self.cpg_path = cpg_path
                            self.cpg_generated = True
                            logger.info(f"Parallel CPG generation complete: {len(cpg_paths)} CPGs")
                        else:
                            logger.warning("Parallel generation failed, falling back to single CPG")
                            use_parallel = False
                    except Exception as e:
                        logger.warning(f"Parallel generation failed: {e}, falling back to single CPG")
                        use_parallel = False

                # Fall back to single CPG generation
                if not use_parallel or not results.get("cpg_generated"):
                    try:
                        provider = JoernProvider()
                        cpg_path = provider.generate_cpg(
                            repo_path=input_path,
                            timeout=300  # 5 minutes
                        )

                        results["cpg_generated"] = True
                        results["cpg_path"] = str(cpg_path)
                        results["parallel_generation"] = False
                        self.cpg_path = cpg_path
                        self.cpg_generated = True

                        logger.info(f"CPG generated at: {cpg_path}")

                    except Exception as e:
                        logger.error(f"CPG generation failed: {e}")
                        results["error"] = f"CPG generation failed: {e}"
                        return results

            # Step 4: Extract entities (methods + classes)
            logger.info("Extracting code entities...")
            try:
                extractor = CodeEntityExtractor()
                entities = extractor.extract_entities(cpg_path)

                results["entities_extracted"] = len(entities)
                self.entities_extracted = len(entities)

                logger.info(f"Extracted {len(entities)} code entities")

                # Step 5: Extract call graph edges (NEW - Phase 3)
                logger.info("Extracting call graph relationships...")
                try:
                    from knowgraph.domain.intelligence.call_graph_extractor import (
                        CallGraphExtractor,
                    )

                    call_extractor = CallGraphExtractor()
                    call_edges = call_extractor.extract_call_edges(cpg_path)

                    results["call_edges_extracted"] = len(call_edges)
                    logger.info(f"Extracted {len(call_edges)} call graph edges")

                except Exception as e:
                    logger.warning(f"Call graph extraction failed (non-fatal): {e}")
                    results["call_edges_extracted"] = 0
                    call_edges = []

                # Step 6: Extract data flows (NEW - Phase 3)
                logger.info("Analyzing data flows...")
                try:
                    from knowgraph.domain.intelligence.data_flow_analyzer import DataFlowAnalyzer

                    flow_analyzer = DataFlowAnalyzer()
                    data_flows = flow_analyzer.find_tainted_flows(cpg_path)

                    results["data_flows_found"] = len(data_flows)
                    logger.info(f"Found {len(data_flows)} potential data flows")

                except Exception as e:
                    logger.warning(f"Data flow analysis failed (non-fatal): {e}")
                    results["data_flows_found"] = 0
                    data_flows = []

                # Step 7: Link code to documentation (NEW - Phase 3)
                logger.info("Linking code to documentation...")
                try:
                    from knowgraph.domain.intelligence.code_docs_linker import CodeDocsLinker

                    linker = CodeDocsLinker()
                    doc_links = linker.find_documentation_links(graph_path, entities)

                    results["doc_links_found"] = len(doc_links)
                    logger.info(f"Found {len(doc_links)} code-to-docs links")

                except Exception as e:
                    logger.warning(f"Code-docs linking failed (non-fatal): {e}")
                    results["doc_links_found"] = 0


                # Step 7.5: Write call graph and data flow edges to graphstore (CRITICAL)
                # DISABLED: This code creates dangling edges because it uses random UUIDs
                # instead of mapping caller/callee names to actual node UUIDs.
                # TODO: Implement proper node ID mapping before enabling this feature.
                try:
                    logger.info("Skipping code edge generation (requires node ID mapping)")
                    results["code_edges_written"] = 0
                    
                    # The following code is commented out until proper node ID mapping is implemented:
                    # 
                    # import time
                    # from uuid import uuid4
                    # from knowgraph.domain.models.edge import Edge
                    # from knowgraph.infrastructure.storage.filesystem import append_edge_jsonl
                    #
                    # logger.info("Writing code edges to graphstore...")
                    # edges_written = 0
                    #
                    # # Write call graph edges
                    # if call_edges:
                    #     for call_edge in call_edges:
                    #         try:
                    #             # PROBLEM: uuid4() creates random UUIDs that don't correspond to any nodes!
                    #             # We need to map caller/callee names to actual node UUIDs first.
                    #             edge = Edge(
                    #                 source=uuid4(),  # ❌ WRONG: Random UUID
                    #                 target=uuid4(),  # ❌ WRONG: Random UUID
                    #                 type="call",
                    #                 score=1.0,
                    #                 created_at=int(time.time()),
                    #                 metadata={
                    #                     "caller": call_edge.get("caller", "unknown"),
                    #                     "callee": call_edge.get("callee", "unknown"),
                    #                     "source": "joern_call_graph"
                    #                 }
                    #             )
                    #             append_edge_jsonl(edge, graph_path)
                    #             edges_written += 1
                    #         except Exception as e:
                    #             logger.warning(f"Failed to write call edge: {e}")
                    #
                    # # Write data flow edges
                    # if data_flows:
                    #     for flow in data_flows:
                    #         try:
                    #             edge = Edge(
                    #                 source=uuid4(),  # ❌ WRONG: Random UUID
                    #                 target=uuid4(),  # ❌ WRONG: Random UUID
                    #                 type="data_flow",
                    #                 score=0.8,
                    #                 created_at=int(time.time()),
                    #                 metadata={
                    #                     "source_node": flow.get("source", "unknown"),
                    #                     "sink_node": flow.get("sink", "unknown"),
                    #                     "variable": flow.get("variable", "unknown"),
                    #                     "source": "joern_data_flow"
                    #                 }
                    #             )
                    #             append_edge_jsonl(edge, graph_path)
                    #             edges_written += 1
                    #         except Exception as e:
                    #             logger.warning(f"Failed to write data flow edge: {e}")
                    #
                    # logger.info(f"✅ Written {edges_written} code edges to graphstore")
                    # results["code_edges_written"] = edges_written

                except Exception as e:
                    logger.error(f"Failed to write code edges: {e}")
                    results["code_edges_written"] = 0

                # Step 8: Convert to graph nodes AND write to graphstore (CRITICAL FIX)
                if entities:
                    nodes = extractor.entities_to_graph_nodes(entities)
                    results["graph_nodes"] = nodes
                    logger.info(f"Converted to {len(nodes)} graph nodes")

                    # CRITICAL: Write code entities to graphstore for GraphRAG integration
                    try:
                        import time
                        from uuid import uuid4

                        from knowgraph.domain.models.node import Node
                        from knowgraph.infrastructure.storage.filesystem import write_node_json
                        from knowgraph.infrastructure.storage.manifest import (
                            read_manifest,
                            write_manifest,
                        )

                        logger.info("Writing code entities to graphstore...")

                        # Read manifest to update
                        manifest = read_manifest(graph_path)
                        if manifest is None:
                             logger.warning("Manifest not found, skipping update")
                             # Initialize empty manifest or handle error

                        written_count = 0
                        created_nodes = []  # Track nodes for indexing
                        for node_dict in nodes:
                            try:
                                # Convert dict to Node object
                                import hashlib

                                # Handle None file_path
                                file_path = node_dict["metadata"].get("file_path") or "unknown"

                                # Generate proper SHA-1 hash (40 characters)
                                content_for_hash = f"{node_dict['name']}_{file_path}"
                                content_hash = hashlib.sha1(content_for_hash.encode()).hexdigest()

                                node_metadata = node_dict["metadata"].copy()
                                
                                # CRITICAL FIX: create_semantic_edges requires "entities" in metadata
                                # For code nodes, the node itself IS the entity.
                                # So we add itself as the single entity in the list.
                                if "entities" not in node_metadata:
                                    node_metadata["entities"] = [
                                        {
                                            "name": node_dict["name"],
                                            "type": node_dict.get("type", "code"),
                                            "description": f"Code entity: {node_dict['name']}"
                                        }
                                    ]

                                node = Node(
                                    id=uuid4(),
                                    hash=content_hash,
                                    title=node_dict["name"],
                                    content=node_dict["content"],
                                    path=file_path,
                                    type=node_dict["type"],
                                    token_count=len(node_dict["content"].split()),
                                    created_at=int(time.time()),
                                    metadata=node_metadata
                                )

                                # Write to graphstore
                                write_node_json(node, graph_path)
                                written_count += 1
                                created_nodes.append(node)

                            except Exception as e:
                                logger.warning(f"Failed to write node {node_dict.get('name')}: {e}")

                        # Update manifest
                        if written_count > 0 and manifest:
                            manifest.node_count += written_count
                            manifest.updated_at = int(time.time())
                            write_manifest(manifest, graph_path)

                        logger.info(f"✅ Written {written_count} code entities to graphstore")
                        results["entities_written_to_graph"] = written_count

                        # Step 8.5: Generate embeddings and update sparse index (CRITICAL)
                        if created_nodes:
                            logger.info("Generating sparse embeddings for code entities...")
                            try:

                                from knowgraph.infrastructure.embedding.sparse_embedder import (
                                    SparseEmbedder,
                                )
                                from knowgraph.infrastructure.search.sparse_index import SparseIndex

                                embedder = SparseEmbedder()
                                index = SparseIndex()

                                # Load existing index if available to append to it
                                try:
                                    index.load(graph_path / "index")
                                    logger.info(f"Loaded existing index with {index.n_docs} documents")
                                except Exception:
                                    logger.info("Creating new sparse index")

                                indexed_count = 0
                                for node in created_nodes:
                                    try:
                                        # Embed content (signatures + body) using code-aware embedding
                                        embedding = embedder.embed_code(node.content)
                                        index.add(node.id, embedding)
                                        indexed_count += 1
                                    except Exception as e:
                                        import traceback
                                        logger.warning(f"Failed to embed node {node.title}: {e}\n{traceback.format_exc()}")

                                index.build()
                                index.save(graph_path / "index")
                                logger.info(f"✅ Added {indexed_count} code entities to sparse index")
                                results["entities_indexed"] = indexed_count

                            except Exception as e:
                                logger.error(f"Failed to update sparse index: {e}")
                                results["entities_indexed"] = 0

                        # Step 8.6: Generate Semantic and Reference Edges (NEW - MISSING FEATURE)
                        if created_nodes:
                            logger.info("Generating semantic and reference edges for code entities...")
                            try:
                                from knowgraph.application.indexing.graph_builder import (
                                    create_semantic_edges,
                                    create_reference_edges,
                                )
                                from knowgraph.infrastructure.storage.filesystem import append_edge_jsonl

                                # Create semantic edges
                                semantic_edges = create_semantic_edges(created_nodes, threshold=0.1)
                                logger.info(f"Created {len(semantic_edges)} semantic edges")
                                
                                for edge in semantic_edges:
                                    append_edge_jsonl(edge, graph_path)
                                
                                # Create reference edges
                                # Note: Reference edges benefit from global context, but here we only have
                                # the current batch of code nodes. This is still useful for internal
                                # references within the codebase.
                                reference_edges = create_reference_edges(created_nodes)
                                logger.info(f"Created {len(reference_edges)} reference edges")

                                for edge in reference_edges:
                                    append_edge_jsonl(edge, graph_path)
                                
                                total_edges = len(semantic_edges) + len(reference_edges)
                                logger.info(f"✅ Written {total_edges} new edges to graphstore")
                                
                                # Update manifest
                                if manifest and total_edges > 0:
                                    manifest.edge_count += total_edges
                                    manifest.semantic_edge_count += len(semantic_edges)
                                    manifest.updated_at = int(time.time())
                                    write_manifest(manifest, graph_path)

                            except Exception as e:
                                logger.error(f"Failed to create edges: {e}")


                    except Exception as e:
                        logger.error(f"Failed to write entities to graphstore: {e}")
                        results["entities_written_to_graph"] = 0


                # Step 9: Persist CPG to graphstore and save metadata (NEW - CRITICAL)
                try:
                    import shutil

                    from knowgraph.infrastructure.indexing.cpg_metadata import save_cpg_metadata

                    # Create persistent CPG path in graphstore
                    metadata_dir = graph_path / "metadata"
                    metadata_dir.mkdir(parents=True, exist_ok=True)
                    persistent_cpg_path = metadata_dir / "cpg.bin"

                    # Copy CPG to graphstore (make it persistent)
                    if cpg_path.exists():
                        shutil.copy2(cpg_path, persistent_cpg_path)
                        logger.info(f"Copied CPG to graphstore: {persistent_cpg_path}")

                        # Save metadata with entity count
                        save_cpg_metadata(
                            graph_path=graph_path,
                            cpg_path=persistent_cpg_path,
                            entities_count=len(entities) if entities else 0
                        )
                        logger.info(f"Saved CPG metadata with {len(entities) if entities else 0} entities")

                        # Update results with persistent path
                        results["cpg_path"] = str(persistent_cpg_path)
                        results["cpg_persisted"] = True
                    else:
                        logger.warning(f"CPG not found at {cpg_path}, skipping persistence")
                        results["cpg_persisted"] = False

                except Exception as e:
                    logger.warning(f"CPG persistence failed (non-fatal): {e}")
                    results["cpg_persisted"] = False

                # Step 10: Cache CPG for future use (NEW - Phase 4)
                try:
                    from knowgraph.infrastructure.caching import CPGCache

                    cache = CPGCache()
                    cached_path = cache.cache_cpg(input_path, cpg_path)
                    results["cpg_cached"] = True
                    logger.info("Cached CPG for future queries")

                except Exception as e:
                    logger.warning(f"CPG caching failed (non-fatal): {e}")
                    results["cpg_cached"] = False

            except Exception as e:
                logger.error(f"Entity extraction failed: {e}")
                results["error"] = f"Entity extraction failed: {e}"
                return results

            return results

        except Exception as e:
            logger.error(f"Code processing failed: {e}")
            results["error"] = str(e)
            return results

    def get_summary(self) -> str:
        """Get human-readable summary of code processing.

        Returns:
            Summary string
        """
        if not self.cpg_generated:
            return "No code analysis performed"

        summary = "🔧 Code Analysis:\n"
        summary += f"  - CPG generated: {self.cpg_path}\n"
        summary += f"  - Entities extracted: {self.entities_extracted}\n"

        return summary

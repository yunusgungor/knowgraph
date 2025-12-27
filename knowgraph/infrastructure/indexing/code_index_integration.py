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
        from knowgraph.infrastructure.indexing.code_file_detector import CodeFileDetector
        from knowgraph.domain.intelligence.joern_provider import JoernProvider
        from knowgraph.domain.intelligence.code_entity_extractor import CodeEntityExtractor
        
        results = {
            'code_files_detected': 0,
            'cpg_generated': False,
            'cpg_path': None,
            'entities_extracted': 0,
            'error': None
        }
        
        try:
            # Step 1: Detect code files
            logger.info("Detecting code files...")
            detector = CodeFileDetector()
            code_files = detector.detect_code_files(input_path)
            
            results['code_files_detected'] = len(code_files)
            
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
                    results['cpg_generated'] = True
                    results['cpg_path'] = str(cached_cpg)
                    results['cpg_from_cache'] = True
                    
                    # Continue with entity extraction using cached CPG
                    cpg_path = cached_cpg
                    self.cpg_path = cpg_path
                    self.cpg_generated = True
                else:
                    logger.warning("No cached CPG available despite no changes")
                    # Fall through to generate new CPG
            
            # Step 3: Generate CPG (if needed)
            if not results.get('cpg_from_cache'):
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
                            results['cpg_generated'] = True
                            results['cpg_path'] = str(cpg_path)
                            results['parallel_generation'] = True
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
                if not use_parallel or not results.get('cpg_generated'):
                    try:
                        provider = JoernProvider()
                        cpg_path = provider.generate_cpg(
                            repo_path=input_path,
                            timeout=300  # 5 minutes
                        )
                        
                        results['cpg_generated'] = True
                        results['cpg_path'] = str(cpg_path)
                        results['parallel_generation'] = False
                        self.cpg_path = cpg_path
                        self.cpg_generated = True
                        
                        logger.info(f"CPG generated at: {cpg_path}")
                        
                    except Exception as e:
                        logger.error(f"CPG generation failed: {e}")
                        results['error'] = f"CPG generation failed: {e}"
                        return results
            
            # Step 4: Extract entities (methods + classes)
            logger.info("Extracting code entities...")
            try:
                extractor = CodeEntityExtractor()
                entities = extractor.extract_entities(cpg_path)
                
                results['entities_extracted'] = len(entities)
                self.entities_extracted = len(entities)
                
                logger.info(f"Extracted {len(entities)} code entities")
                
                # Step 5: Extract call graph edges (NEW - Phase 3)
                logger.info("Extracting call graph relationships...")
                try:
                    from knowgraph.domain.intelligence.call_graph_extractor import CallGraphExtractor
                    
                    call_extractor = CallGraphExtractor()
                    call_edges = call_extractor.extract_call_edges(cpg_path)
                    
                    results['call_edges_extracted'] = len(call_edges)
                    logger.info(f"Extracted {len(call_edges)} call graph edges")
                    
                except Exception as e:
                    logger.warning(f"Call graph extraction failed (non-fatal): {e}")
                    results['call_edges_extracted'] = 0
                
                # Step 6: Extract data flows (NEW - Phase 3)
                logger.info("Analyzing data flows...")
                try:
                    from knowgraph.domain.intelligence.data_flow_analyzer import DataFlowAnalyzer
                    
                    flow_analyzer = DataFlowAnalyzer()
                    data_flows = flow_analyzer.find_tainted_flows(cpg_path)
                    
                    results['data_flows_found'] = len(data_flows)
                    logger.info(f"Found {len(data_flows)} potential data flows")
                    
                except Exception as e:
                    logger.warning(f"Data flow analysis failed (non-fatal): {e}")
                    results['data_flows_found'] = 0
                
                # Step 7: Link code to documentation (NEW - Phase 3)
                logger.info("Linking code to documentation...")
                try:
                    from knowgraph.domain.intelligence.code_docs_linker import CodeDocsLinker
                    
                    linker = CodeDocsLinker()
                    doc_links = linker.find_documentation_links(graph_path, entities)
                    
                    results['doc_links_found'] = len(doc_links)
                    logger.info(f"Found {len(doc_links)} code-to-docs links")
                    
                except Exception as e:
                    logger.warning(f"Code-docs linking failed (non-fatal): {e}")
                    results['doc_links_found'] = 0
                
                # Step 8: Convert to graph nodes
                if entities:
                    nodes = extractor.entities_to_graph_nodes(entities)
                    results['graph_nodes'] = nodes
                    logger.info(f"Converted to {len(nodes)} graph nodes")
                
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
                        results['cpg_path'] = str(persistent_cpg_path)
                        results['cpg_persisted'] = True
                    else:
                        logger.warning(f"CPG not found at {cpg_path}, skipping persistence")
                        results['cpg_persisted'] = False
                        
                except Exception as e:
                    logger.warning(f"CPG persistence failed (non-fatal): {e}")
                    results['cpg_persisted'] = False
                
                # Step 10: Cache CPG for future use (NEW - Phase 4)
                try:
                    from knowgraph.infrastructure.caching import CPGCache
                    
                    cache = CPGCache()
                    cached_path = cache.cache_cpg(input_path, cpg_path)
                    results['cpg_cached'] = True
                    logger.info(f"Cached CPG for future queries")
                    
                except Exception as e:
                    logger.warning(f"CPG caching failed (non-fatal): {e}")
                    results['cpg_cached'] = False
                
            except Exception as e:
                logger.error(f"Entity extraction failed: {e}")
                results['error'] = f"Entity extraction failed: {e}"
                return results
            
            return results
            
        except Exception as e:
            logger.error(f"Code processing failed: {e}")
            results['error'] = str(e)
            return results
    
    def get_summary(self) -> str:
        """Get human-readable summary of code processing.
        
        Returns:
            Summary string
        """
        if not self.cpg_generated:
            return "No code analysis performed"
        
        summary = f"🔧 Code Analysis:\n"
        summary += f"  - CPG generated: {self.cpg_path}\n"
        summary += f"  - Entities extracted: {self.entities_extracted}\n"
        
        return summary

"""Smart Graph Builder using Intelligence Provider."""

import asyncio
import logging
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import UUID

from knowgraph.application.indexing.graph_builder import (
    create_nodes_from_chunks,
    create_semantic_edges,
    create_reference_edges,
)
from knowgraph.config import BATCH_SIZE, MAX_CONCURRENT_REQUESTS
from knowgraph.domain.intelligence.code_analyzer import ASTAnalyzer
from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.cache.cache_manager import CacheManager
from knowgraph.infrastructure.parsing.chunker import Chunk
from knowgraph.shared.error_metrics import IndexingMetrics
from knowgraph.shared.performance import PerformanceTracker

logger = logging.getLogger(__name__)


class SmartGraphBuilder:
    """Graph builder that uses Intelligence Provider for semantic analysis."""

    def __init__(self, provider: IntelligenceProvider | None = None):
        """Initialize builder with optional provider."""
        self.provider = provider
        # CacheManager will be initialized in build() when path is known
        self.cache_manager: CacheManager | None = None
        self.ast_analyzer = ASTAnalyzer()
        self.metrics = IndexingMetrics()
        self.perf_tracker = PerformanceTracker()

    async def build(
        self, chunks: list[Chunk], file_path: str, file_hash: str, graph_path: str
    ) -> tuple[list[Node], list[Edge]]:
        """Build graph nodes and edges from chunks using AI analysis."""
        with self.perf_tracker.track("total_build"):
            # 1. Create Nodes (Initial)
            with self.perf_tracker.track("node_creation"):
                initial_nodes = create_nodes_from_chunks(chunks, file_path)

            # Initialize Cache Manager in the output directory
            cache_dir = Path(graph_path) / ".cache"
            self.cache_manager = CacheManager(cache_dir=str(cache_dir))

            # 2. Extract Entities (Hybrid Strategy: Cache -> AST -> LLM)
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

            # Prepare lists
            final_nodes_map: dict[UUID, Node] = {}
            nodes_needing_llm: list[Node] = []

            # Phase 1: Cache & AST Check
            with self.perf_tracker.track("cache_ast_phase"):
                for node in initial_nodes:
                    self.metrics.total_chunks += 1

                    # Check Cache
                    cached_entities = self.cache_manager.get_entities(node.hash)
                    if cached_entities is not None:
                        self.metrics.record_cache_hit()
                        final_nodes_map[node.id] = replace(
                            node, metadata={"entities": [e._asdict() for e in cached_entities]}
                        )
                        continue

                    self.metrics.record_cache_miss()

                    # Check AST (if code)
                    # Simple heuristic: ASTAnalyzer handles syntax errors gracefully
                    try:
                        ast_entities = self.ast_analyzer.extract_entities(node.content)
                        if ast_entities:
                            self.metrics.record_ast_success()
                            self.cache_manager.save_entities(node.hash, ast_entities)
                            final_nodes_map[node.id] = replace(
                                node, metadata={"entities": [e._asdict() for e in ast_entities]}
                            )
                            continue
                    except Exception as e:
                        self.metrics.record_ast_failure(str(e), f"node_{node.id}")
                        logger.debug(f"AST parsing failed for node {node.id}: {e}")

                    # If Cache Miss & AST Miss -> Queue for LLM
                    nodes_needing_llm.append(node)

            # Phase 2: LLM Batch Processing
            if nodes_needing_llm and self.provider:
                # ... (Existing LLM logic) ...
                # (Skipping ahead for brevity in replacement, but I'll replace the whole if/else block)
                with self.perf_tracker.track("llm_processing"):

                    async def process_batch(
                        batch_nodes: list[Node],
                    ) -> list[tuple[Node, list[Any]]]:
                        texts = [node.content for node in batch_nodes]
                        async with semaphore:
                            from knowgraph.config import LLM_RETRY_COUNT, LLM_RETRY_BASE_DELAY

                            for attempt in range(LLM_RETRY_COUNT):
                                try:
                                    batch_entities = await self.provider.extract_entities_batch(
                                        texts
                                    )
                                    for _ in batch_nodes:
                                        self.metrics.record_llm_success()
                                    return list(zip(batch_nodes, batch_entities))
                                except Exception as e:
                                    if attempt == LLM_RETRY_COUNT - 1:
                                        for node in batch_nodes:
                                            self.metrics.record_llm_failure(
                                                str(e), f"node_{node.id}"
                                            )
                                        logger.error(
                                            f"LLM batch failed after {LLM_RETRY_COUNT} retries: {e}"
                                        )
                                        return [(n, []) for n in batch_nodes]
                                    await asyncio.sleep(LLM_RETRY_BASE_DELAY * (2**attempt))
                            return [(n, []) for n in batch_nodes]

                    tasks = []
                    for i in range(0, len(nodes_needing_llm), BATCH_SIZE):
                        batch = nodes_needing_llm[i : i + BATCH_SIZE]
                        tasks.append(process_batch(batch))

                    batch_results = await asyncio.gather(*tasks)
                    for batch_res in batch_results:
                        for node, entities in batch_res:
                            self.cache_manager.save_entities(node.hash, entities)
                            final_nodes_map[node.id] = replace(
                                node, metadata={"entities": [e._asdict() for e in entities]}
                            )
            elif nodes_needing_llm:
                # If LLM skipped, still add nodes to map (without entities)
                for node in nodes_needing_llm:
                    final_nodes_map[node.id] = node

            # Reassemble final nodes in original order
            final_nodes = [final_nodes_map[node.id] for node in initial_nodes]

            # Finalize metrics
            self.metrics.finalize()
            logger.info(f"\n{self.metrics.get_summary()}")

            # 4. Create Edges (Semantic + Reference)
            with self.perf_tracker.track("edge_creation"):
                # Load existing node metadata for global reference context (OPTIMIZED)
                from knowgraph.infrastructure.storage.filesystem import (
                    list_all_nodes,
                    read_node_metadata_only,
                )
                from dataclasses import replace

                existing_metadata = []
                graph_path_obj = Path(graph_path)
                if graph_path_obj.exists():
                    try:
                        node_ids = list_all_nodes(graph_path_obj)
                        for n_id in node_ids:
                            # Skip nodes we just built (they are already in final_nodes)
                            if any(fn.id == n_id for fn in final_nodes):
                                continue

                            # Load ONLY metadata (95% memory reduction)
                            metadata_dict = read_node_metadata_only(n_id, graph_path_obj)
                            if metadata_dict and metadata_dict.get("entities"):
                                # Create minimal pseudo-node for reference linking
                                # (we only need id and metadata, not content)
                                pseudo_node = Node(
                                    id=metadata_dict["id"],
                                    hash="",  # Not needed for linking
                                    title="",
                                    content="",  # Skip heavy content field
                                    path=metadata_dict["path"],
                                    type="code",
                                    token_count=0,
                                    created_at=0,
                                    metadata={"entities": metadata_dict["entities"]},
                                )
                                existing_metadata.append(pseudo_node)
                    except Exception as e:
                        logger.warning(
                            f"Could not load existing node metadata for reference context: {e}"
                        )

                all_context_nodes = final_nodes + existing_metadata

                semantic_edges = create_semantic_edges(final_nodes)
                # create_reference_edges uses global context to resolve symbols
                reference_edges = create_reference_edges(all_context_nodes)

                # Filter reference_edges: We only want edges where at least one side is a NEW node
                new_node_ids = {n.id for n in final_nodes}
                relevant_reference_edges = [
                    e
                    for e in reference_edges
                    if e.source in new_node_ids or e.target in new_node_ids
                ]

                all_edges = semantic_edges + relevant_reference_edges

            # Auto-validate graph before returning
            with self.perf_tracker.track("validation"):
                validation_warnings = self._validate_build_results(final_nodes, all_edges)
                if validation_warnings:
                    logger.warning(
                        f"Graph validation warnings: {len(validation_warnings)} issues detected"
                    )
                    for warning in validation_warnings[:5]:  # Show first 5
                        logger.warning(f"  - {warning}")

        # Log performance summary
        perf_summary = self.perf_tracker.get_summary()
        if perf_summary:
            logger.info(f"\nBuild Performance Summary: {perf_summary}")

        return final_nodes, all_edges

    def _validate_build_results(self, nodes: list[Node], edges: list[Edge]) -> list[str]:
        """Validate build results for common issues.

        Args:
            nodes: Built nodes
            edges: Built edges

        Returns:
            List of warning messages (empty if no issues)
        """
        warnings = []

        # Check for orphaned nodes (nodes with no edges)
        node_ids = {node.id for node in nodes}
        nodes_with_edges = set()
        for edge in edges:
            nodes_with_edges.add(edge.source)
            nodes_with_edges.add(edge.target)

        orphaned = node_ids - nodes_with_edges
        if orphaned:
            warnings.append(f"{len(orphaned)} orphaned nodes (no edges)")

        # Check for dangling edges (edges pointing to non-existent nodes)
        for edge in edges:
            if edge.source not in node_ids:
                warnings.append(f"Dangling edge: source {edge.source} not in nodes")
            if edge.target not in node_ids:
                warnings.append(f"Dangling edge: target {edge.target} not in nodes")

        # Check for self-loops
        self_loops = [e for e in edges if e.source == e.target]
        if self_loops:
            warnings.append(f"{len(self_loops)} self-loop edges detected")

        # Check for empty entities (nodes with no extracted entities)
        empty_entities = [n for n in nodes if not (n.metadata or {}).get("entities")]
        if len(empty_entities) > len(nodes) * 0.5:  # More than 50%
            warnings.append(
                f"{len(empty_entities)}/{len(nodes)} nodes have no entities (potential extraction failure)"
            )

        return warnings

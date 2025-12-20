"""Graph construction from chunked markdown.

Builds nodes and edges from parsed chunks, implementing hierarchy, semantic,
reference, and cross-file relationships.

Includes both utility functions and SmartGraphBuilder class for AI-powered indexing.
"""

import asyncio
import logging
import time
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from knowgraph.config import BATCH_SIZE, MAX_CONCURRENT_REQUESTS
from knowgraph.domain.intelligence.code_analyzer import ASTAnalyzer
from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.cache.cache_manager import CacheManager
from knowgraph.infrastructure.parsing.chunker import Chunk
from knowgraph.infrastructure.parsing.hasher import hash_content
from knowgraph.shared.error_metrics import IndexingMetrics
from knowgraph.shared.memory_profiler import memory_guard
from knowgraph.shared.performance import PerformanceTracker
from knowgraph.shared.tracing import trace_operation

logger = logging.getLogger(__name__)


def create_node_from_chunk(chunk: Chunk, source_path: str, node_type: str | None = None) -> Node:
    """Convert chunk to node with metadata.

    Args:
    ----
        chunk: Chunk with content and metadata
        source_path: Source file path (relative)
        node_type: Override node type classification

    Returns:
    -------
        Node object

    """
    content_hash = hash_content(chunk.content)
    node_id = uuid4()
    created_at = int(time.time())

    # Classify node type if not provided
    if node_type is None:
        if chunk.has_code:
            node_type = "code"
        elif "readme" in source_path.lower():
            node_type = "readme"
        elif any(
            ext in source_path.lower()
            for ext in [".yaml", ".yml", ".json", ".toml", ".ini", "config"]
        ):
            node_type = "config"
        else:
            node_type = "text"

    # Use chunk source path if available, otherwise fallback to provided path
    # (chunk.source_path will be the specific file path from indexing,
    # source_path argument might be just the project root)
    actual_path = chunk.source_path if chunk.source_path else source_path

    # Ensure path is relative (remove leading slash if present)
    relative_path = actual_path.lstrip("/")

    return Node(
        id=node_id,
        hash=content_hash,
        title=chunk.header,
        content=chunk.content,
        path=relative_path,
        type=node_type,  # type: ignore
        token_count=chunk.token_count,
        created_at=created_at,
        header_depth=chunk.header_depth,
        header_path=chunk.header_path,
        chunk_id=chunk.chunk_id,
        line_start=chunk.line_start,
        line_end=chunk.line_end,
    )


def create_nodes_from_chunks(chunks: list[Chunk], source_path: str) -> list[Node]:
    """Convert multiple chunks to nodes.

    Args:
    ----
        chunks: List of chunks
        source_path: Source file path

    Returns:
    -------
        List of nodes

    """
    return [create_node_from_chunk(chunk, source_path) for chunk in chunks]


def normalize_markdown_content(content: str) -> str:
    r"""Normalize markdown content for consistent processing.

    Implements FR-005 normalization rules:
    - Standardize line endings to \\n
    - Remove trailing whitespace
    - Collapse multiple blank lines to max 2
    - Normalize header spacing

    Args:
    ----
        content: Raw markdown content

    Returns:
    -------
        Normalized content

    """
    # Standardize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Remove trailing whitespace from lines
    lines = [line.rstrip() for line in content.split("\n")]

    # Collapse multiple blank lines
    normalized_lines = []
    blank_count = 0

    for line in lines:
        if not line.strip():
            blank_count += 1
            if blank_count <= 2:
                normalized_lines.append(line)
        else:
            blank_count = 0
            normalized_lines.append(line)

    # Ensure single blank line after headers
    result_lines = []
    for i, line in enumerate(normalized_lines):
        result_lines.append(line)
        if (
            line.startswith("#")
            and i + 1 < len(normalized_lines)
            and normalized_lines[i + 1].strip()
        ):
            result_lines.append("")  # Add blank line

    return "\n".join(result_lines)


def validate_edges(
    edges: list[Edge],
    nodes: list[Node],
) -> tuple[list[Edge], list[str]]:
    """Validate edges and remove dangling/circular references.

    Args:
    ----
        edges: List of edges to validate
        nodes: List of valid nodes

    Returns:
    -------
        Tuple of (valid_edges, warning_messages)

    """
    node_ids = {node.id for node in nodes}
    valid_edges = []
    warnings = []

    # Check for dangling edges (references to non-existent nodes)
    for edge in edges:
        if edge.source not in node_ids:
            warnings.append(f"Dangling edge: source {edge.source} not found in nodes")
            continue
        if edge.target not in node_ids:
            warnings.append(f"Dangling edge: target {edge.target} not found in nodes")
            continue

        # Prevent self-loops (node pointing to itself)
        if edge.source == edge.target:
            warnings.append(f"Self-loop detected: {edge.source} -> {edge.source}")
            continue

        valid_edges.append(edge)

    return valid_edges, warnings


def create_semantic_edges(nodes: list[Node], threshold: float = 0.2, max_edges_per_node: int = 5) -> list[Edge]:
    """Create edges based on shared entities (Smart Mode) - Optimized.

    Args:
    ----
        nodes: List of nodes with metadata['entities']
        threshold: Jaccard similarity threshold (0.2 = 20% overlap required)
        max_edges_per_node: Maximum edges per node (default 5, prevents edge explosion)

    Returns:
    -------
        List of edges

    """
    edges = []
    created_at = int(time.time())

    # Pre-compute entity sets
    node_entities: dict[UUID, set[str]] = {}
    for node in nodes:
        if node.metadata and "entities" in node.metadata:
            raw_entities = node.metadata["entities"]
            if isinstance(raw_entities, list):
                names = {e.get("name", "").lower() for e in raw_entities if isinstance(e, dict)}
                if names:
                    node_entities[node.id] = names

    # Early exit if not enough nodes have entities
    if len(node_entities) < 2:
        return edges

    # Pairwise comparison with top-K selection
    active_nodes = [n for n in nodes if n.id in node_entities]

    for i, node1 in enumerate(active_nodes):
        entities1 = node_entities[node1.id]

        # Collect similarities for this node
        similarities = []

        for j, node2 in enumerate(active_nodes[i + 1 :], start=i + 1):
            entities2 = node_entities[node2.id]

            shared = entities1.intersection(entities2)
            if shared:
                union_size = len(entities1.union(entities2))
                score = len(shared) / union_size

                if score > threshold:
                    similarities.append((node2.id, score, shared))

        # Keep only top-K most similar for this node
        similarities.sort(key=lambda x: x[1], reverse=True)
        for target_id, score, shared in similarities[:max_edges_per_node]:
            edges.append(
                Edge(
                    source=node1.id,
                    target=target_id,
                    type="semantic",
                    score=score,
                    created_at=created_at,
                    metadata={
                        "similarity_type": "ai_entity_overlap",
                        "shared_entities": list(shared),
                    },
                )
            )

    return edges


def create_reference_edges(nodes: list[Node]) -> list[Edge]:
    """Create directed edges based on definition/reference roles.

    If Node A references symbol 'foo' and Node B defines symbol 'foo',
    an edge A -> B is created with type 'reference'.

    Args:
    ----
        nodes: List of nodes with metadata['entities']

    Returns:
    -------
        List of reference edges
    """
    edges = []
    created_at = int(time.time())

    # 1. Build Global symbol table (Symbol -> Defining Node IDs)
    symbol_definitions: dict[str, list[UUID]] = {}
    node_references: dict[UUID, set[str]] = {}

    for node in nodes:
        if not node.metadata or "entities" not in node.metadata:
            continue

        entities = node.metadata["entities"]
        if not isinstance(entities, list):
            continue

        refs = set()
        for e in entities:
            if not isinstance(e, dict):
                continue

            name = e.get("name", "")
            if not name:
                continue

            e_type = e.get("type", "semantic")

            if e_type == "definition":
                if name not in symbol_definitions:
                    symbol_definitions[name] = []
                symbol_definitions[name].append(node.id)
            elif e_type in ["reference", "call", "import"]:
                refs.add(name)

        if refs:
            node_references[node.id] = refs

    # 2. Create Edges: Referencer -> Definer
    existing_edges = set()  # (src, target, symbol) to prevent duplicates

    for ref_node_id, refs in node_references.items():
        for symbol in refs:
            if symbol in symbol_definitions:
                for def_node_id in symbol_definitions[symbol]:
                    # Avoid self-references
                    if ref_node_id == def_node_id:
                        continue

                    edge_key = (ref_node_id, def_node_id, symbol)
                    if edge_key in existing_edges:
                        continue
                    existing_edges.add(edge_key)

                    edges.append(
                        Edge(
                            source=ref_node_id,
                            target=def_node_id,
                            type="reference",
                            score=1.0,
                            created_at=created_at,
                            metadata={"symbol": symbol, "relation": "dependency"},
                        )
                    )

    return edges


class SmartGraphBuilder:
    """Graph builder that uses Intelligence Provider for semantic analysis.

    This class provides AI-powered graph building with:
    - 3-tier hybrid entity extraction (Cache -> AST -> LLM)
    - Async batch processing
    - Performance tracking
    - Automatic validation
    """

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
        with memory_guard(
            operation_name=f"graph_build[{file_path}]",
            warning_threshold_mb=200,
            critical_threshold_mb=500,
        ):
            with trace_operation(
                "smart_graph_builder.build",
                file_path=file_path,
                num_chunks=len(chunks),
            ):
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
                with self.perf_tracker.track("llm_processing"):

                    async def process_batch(
                        batch_nodes: list[Node],
                    ) -> list[tuple[Node, list[Any]]]:
                        texts = [node.content for node in batch_nodes]
                        async with semaphore:
                            from knowgraph.config import LLM_RETRY_BASE_DELAY, LLM_RETRY_COUNT

                            for attempt in range(LLM_RETRY_COUNT):
                                try:
                                    if self.provider is None:
                                        return [(node, []) for node in batch_nodes]
                                    batch_entities = await self.provider.extract_entities_batch(
                                        texts
                                    )
                                    for _ in batch_nodes:
                                        self.metrics.record_llm_success()
                                    return list(zip(batch_nodes, batch_entities))
                                except Exception as e:
                                    error_msg = str(e).lower()

                                    # Check for rate limit errors
                                    if "429" in error_msg or "rate limit" in error_msg or "too many requests" in error_msg:
                                        # Trigger aggressive backoff for rate limits
                                        backoff_time = LLM_RETRY_BASE_DELAY * (3 ** attempt)  # Exponential: 3, 9, 27 seconds
                                        logger.warning(
                                            f"Rate limit hit on attempt {attempt + 1}/{LLM_RETRY_COUNT}. "
                                            f"Backing off for {backoff_time}s..."
                                        )
                                        await asyncio.sleep(backoff_time)
                                    elif attempt == LLM_RETRY_COUNT - 1:
                                        for node in batch_nodes:
                                            self.metrics.record_llm_failure(
                                                str(e), f"node_{node.id}"
                                            )
                                        logger.error(
                                            f"LLM batch failed after {LLM_RETRY_COUNT} retries: {e}"
                                        )
                                        return [(n, []) for n in batch_nodes]
                                    else:
                                        # Regular exponential backoff for other errors
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

                existing_metadata = []
                graph_path_obj = Path(graph_path)
                if graph_path_obj.exists():
                    try:
                        node_ids = list_all_nodes(graph_path_obj)

                        # Parallel metadata loading
                        async def load_metadata(n_id):
                            # Skip nodes we just built
                            if any(fn.id == n_id for fn in final_nodes):
                                return None

                            # Load ONLY metadata (95% memory reduction)
                            metadata_dict = await asyncio.get_event_loop().run_in_executor(
                                None, read_node_metadata_only, n_id, graph_path_obj
                            )
                            if metadata_dict and metadata_dict.get("entities"):
                                return Node(
                                    id=metadata_dict["id"],
                                    hash="",
                                    title="",
                                    content="",
                                    path=metadata_dict["path"],
                                    type="code",
                                    token_count=0,
                                    created_at=0,
                                    metadata={"entities": metadata_dict["entities"]},
                                )
                            return None

                        # Load all metadata in parallel
                        metadata_results = await asyncio.gather(
                            *[load_metadata(n_id) for n_id in node_ids],
                            return_exceptions=True
                        )
                        existing_metadata = [m for m in metadata_results if m is not None and not isinstance(m, Exception)]
                    except Exception as e:
                        logger.warning(
                            f"Could not load existing node metadata for reference context: {e}"
                        )

                all_context_nodes = final_nodes + existing_metadata

                # OPTIMIZATION: Only create semantic edges between NEW nodes
                # (semantic similarity between new and old nodes is less useful)
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

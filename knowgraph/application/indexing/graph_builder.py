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
from knowgraph.domain.intelligence.code_analyzer import CodeAnalyzer
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


def _merge_entities(existing: list[Any], new: list[Any]) -> list[Any]:
    """Union two entity lists, deduped by (name, type).

    ``existing`` may hold ``Entity`` NamedTuples or their ``_asdict()`` dicts
    (as stored on node metadata); ``new`` holds ``Entity`` objects from the
    LLM. Normalizes everything to ``Entity`` so callers can ``_asdict()`` the
    result. Preserves existing (Joern/AST) entities and adds new (LLM) ones.
    """
    from knowgraph.domain.intelligence.provider import Entity

    def to_entity(e: Any) -> Any:
        if isinstance(e, dict):
            return Entity(
                name=e.get("name", ""),
                type=e.get("type", ""),
                description=e.get("description", ""),
            )
        return e

    seen: set[tuple[str, str]] = set()
    merged: list[Any] = []
    for e in list(existing) + list(new):
        ent = to_entity(e)
        k = (ent.name, ent.type)
        if k not in seen:
            seen.add(k)
            merged.append(ent)
    return merged


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


def create_reference_edges(
    nodes: list[Node],
    existing_symbols: dict[str, list[UUID]] | None = None,
) -> list[Edge]:
    """Create directed edges based on definition/reference roles.

    If Node A references symbol 'foo' and Node B defines symbol 'foo',
    an edge A -> B is created with type 'reference'.

    Args:
    ----
        nodes: List of nodes with metadata['entities']
        existing_symbols: Pre-computed global symbol table
            (symbol -> defining node IDs) from previously indexed nodes, so
            callers can avoid re-reading the whole existing graph. When None,
            the table is built only from ``nodes`` (default behavior).

    Returns:
    -------
        List of reference edges
    """
    edges = []
    created_at = int(time.time())

    # Generic/builtin symbols that produce noisy, low-value reference edges.
    # __init__ alone accounts for 15k+ edges; filtering it out cuts edge noise
    # by ~27% while losing zero useful signal.
    _GENERIC_SYMBOLS = frozenset({
        "__init__", "__new__", "__del__", "__repr__", "__str__",
        "__enter__", "__exit__", "__call__", "__iter__", "__next__",
        "__getitem__", "__setitem__", "__delitem__", "__len__",
        "__contains__", "__eq__", "__ne__", "__lt__", "__le__",
        "__gt__", "__ge__", "__hash__", "__bool__",
        "__add__", "__sub__", "__mul__", "__truediv__", "__floordiv__",
        "__mod__", "__pow__", "__and__", "__or__", "__xor__",
        "__neg__", "__pos__", "__abs__", "__invert__",
        "__radd__", "__rsub__", "__rmul__", "__rtruediv__",
        "__iadd__", "__isub__", "__imul__", "__itruediv__",
        "__class__", "__name__", "__module__", "__qualname__",
        "__dict__", "__slots__", "__weakref__", "__doc__",
        "__init_subclass__", "__set_name__", "__class_getitem__",
        "__match_args__", "__allow_redefinition__",
        "run", "_run", "main", "_main",
        "self", "cls", "args", "kwargs", "value", "item", "key",
        "e", "err", "ex", "exc", "error",
        "i", "j", "k", "n", "x", "y", "z",
        "result", "output", "data", "info", "msg", "text",
    })

    # Test functions and high-frequency utility symbols that create noisy
    # reference edges.  test_* alone accounts for 1500+ low-value edges.
    _NOISY_SYMBOLS = frozenset({
        "get_settings", "get_cache_stats", "init_command", "to_dict",
        "from_dict", "echo", "click", "logger", "logging",
        "validate_path", "resolve_graph_store", "detect_project_root",
        "read_manifest", "write_manifest", "list_all_nodes", "read_all_edges",
        "append_edge_jsonl", "write_node_json", "read_node_json",
        "hash_content", "SparseEmbedder", "SparseIndex", "DenseIndex",
        "QueryEngine", "QueryRetriever", "QueryClassifier",
        "SmartGraphBuilder", "CodeAnalyzer", "ASTAnalyzer",
        "JoernProvider", "JoernQueryExecutor", "CPGProvider",
        "CallGraphExtractor", "DataFlowAnalyzer", "CodeDocsLinker",
        "CodeEntityExtractor", "CodeFileDetector", "CodeIndexIntegration",
        "OpenAIProvider", "MCPSamplingProvider", "IntelligenceProvider",
        "Edge", "Node", "Manifest", "Chunk",
        "CircuitBreaker", "RequestThrottle", "RateLimiter",
        "IndexingMetrics", "PerformanceTracker", "ProgressNotifier",
        "MemoryGuard", "memory_guard", "trace_operation",
        "build_error_response", "extract_query_parameters",
        "validate_required_argument", "build_llm_prompt",
    })

    def _is_noisy_symbol(name: str) -> bool:
        """Return True if a symbol should be filtered from reference edges."""
        if name in _GENERIC_SYMBOLS or name in _NOISY_SYMBOLS:
            return True
        # Test functions: test_*, Test*, *_test
        if name.startswith("test_") or name.startswith("Test") or name.endswith("_test"):
            return True
        # Private single-letter/dunder patterns
        if len(name) <= 1:
            return True
        return False

    # 1. Build Global symbol table (Symbol -> Defining Node IDs)
    symbol_definitions: dict[str, list[UUID]] = dict(existing_symbols or {})
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
                if not _is_noisy_symbol(name) and name not in symbol_definitions:
                    symbol_definitions[name] = []
                if not _is_noisy_symbol(name):
                    symbol_definitions[name].append(node.id)
            elif e_type in ["reference", "call", "import"]:
                if not _is_noisy_symbol(name):
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
    - 3-tier hybrid entity extraction (Cache -> AST/Joern -> LLM)
    - Async batch processing
    - Performance tracking
    - Automatic validation
    """

    def __init__(self, provider: IntelligenceProvider | None = None):
        """Initialize builder with optional provider."""
        from knowgraph.config import CPG_NODES_ENABLED
        from knowgraph.domain.intelligence.cpg_converter import CPGConverter

        self.provider = provider
        # CacheManager will be initialized in build() when path is known
        self.cache_manager: CacheManager | None = None
        self.code_analyzer = CodeAnalyzer()  # Hybrid AST + Joern analyzer
        self.cpg_converter = CPGConverter()   # CPG to KnowGraph converter
        self.enable_cpg_nodes = CPG_NODES_ENABLED  # Feature flag
        self.metrics = IndexingMetrics()
        self.perf_tracker = PerformanceTracker()

    async def build(
        self,
        chunks: list[Chunk],
        file_path: str,
        file_hash: str,
        graph_path: str,
        enable_short_unit: bool = False,
    ) -> tuple[list[Node], list[Edge]]:
        """Build graph nodes and edges from chunks using AI analysis.

        ``enable_short_unit`` (Graph Engineering transfer, opt-in): when True,
        non-code chunks that passed LLM entity extraction also run the R-008
        SC-quote + P3 entailment chain (`extract_short_unit_graph`). The
        published relations are stored on each node's ``metadata["relations"]``
        for the query path to consume. Requires a live provider (set via the
        constructor).
        """
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
                # Track CPG edges during entity extraction
                cpg_edges = []  # Collect CPG edges here

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

            # Phase 1: Cache, Joern (directory CPG) & AST fallback
            # Build a shared directory-level CPG once; per-file entity
            # extraction queries it via native Joern DSL (no per-chunk
            # joern-parse). Falls back to CodeAnalyzer (AST) when Joern is
            # unavailable or generation fails.
            cpg_provider = None
            try:
                if self.code_analyzer.use_joern:
                    from knowgraph.domain.intelligence.cpg_provider import CPGProvider

                    cpg_provider = CPGProvider(graph_path=Path(graph_path))
                    if not cpg_provider.ensure_cpg(Path(file_path)):
                        # No Joern-supported files or generation failed:
                        # fall back to AST for every file.
                        cpg_provider = None
            except Exception as e:
                logger.warning(f"Directory CPG generation failed, falling back to per-file analyzer: {e}")
                cpg_provider = None

            # Per-file entity cache: same file's chunks share one extraction
            file_entity_cache: dict[str, list[Any]] = {}
            # Per-file CPG conversion result: entity nodes are generated once
            # per file, not once per chunk (avoid duplicate UUIDs/edges).
            file_cpg_cache: dict[str, Any] = {}

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

                    try:
                        entities: list[Any] = []
                        file_key = node.path or file_path

                        # Joern (directory CPG) extraction, shared per file
                        if cpg_provider is not None:
                            if file_key not in file_entity_cache:
                                file_entity_cache[file_key] = cpg_provider.extract_entities_for_file(file_key)
                            entities = file_entity_cache[file_key]

                        # AST fallback: when CPG returns nothing (unsupported
                        # language, extraction failure, or empty file), fall
                        # back to the built-in AST/regex extractor so code
                        # nodes still get entities for reference edges.
                        if not entities:
                            entities = self.code_analyzer.ast_analyzer.extract_entities(node.content)

                        if entities:
                            # Record success (Joern or AST depending on path)
                            self.metrics.record_ast_success()
                            self.cache_manager.save_entities(node.hash, entities)
                            final_nodes_map[node.id] = replace(
                                node, metadata={"entities": [e._asdict() for e in entities]}
                            )

                            # NEW: If CPG nodes enabled, create entity nodes + hierarchy edges
                            if self.enable_cpg_nodes:
                                logger.info(f"Converting CPG entities for {node.path or file_key}: {len(entities)} entities")

                                try:
                                    # CPG entity nodes are built from the
                                    # per-file native-query entities (directory
                                    # CPG). The GraphML export/parse path is
                                    # gone, so CPG edges (AST/CFG/DDG) are not
                                    # produced here — entity nodes still link
                                    # to their chunk via hierarchy edges.
                                    # Build once per file; later chunks of the
                                    # same file reuse the same entity nodes.
                                    if file_key not in file_cpg_cache:
                                        file_cpg_cache[file_key] = self.cpg_converter.convert_entities_to_graph(
                                            entities,
                                            chunk_node_id=node.id,
                                            file_path=node.path or file_key,
                                        )
                                    cpg_result = file_cpg_cache[file_key]

                                    # Add CPG entity nodes to graph
                                    for entity_node in cpg_result.entity_nodes:
                                        final_nodes_map[entity_node.id] = entity_node

                                    # Add CPG edges to collection (empty for now)
                                    cpg_edges.extend(cpg_result.cpg_edges)

                                    # Add hierarchy edges: entity nodes -> chunk node
                                    for entity_node in cpg_result.entity_nodes:
                                        hierarchy_edge = Edge(
                                            source=entity_node.id,
                                            target=node.id,
                                            type="hierarchy",
                                            score=1.0,
                                            created_at=int(__import__("time").time()),
                                            metadata={"relation": "child_of_chunk", "source": "cpg"},
                                        )
                                        cpg_edges.append(hierarchy_edge)

                                    logger.info(
                                        f"✅ CPG integration: +{len(cpg_result.entity_nodes)} nodes"
                                    )

                                except Exception as cpg_err:
                                    logger.warning(f"CPG conversion failed for {file_key}: {cpg_err}")
                                    # Continue with metadata-only (graceful degradation)

                            # Code chunks are fully handled by Joern/AST and
                            # never go to the LLM. Text chunks (docstring/prose
                            # blocks in a code file) fall through to the LLM
                            # gate below even when the file has code entities.
                            if node.type == "code":
                                continue
                    except Exception as e:
                        self.metrics.record_ast_failure(str(e), f"node_{node.id}")
                        logger.debug(f"Code analysis failed for node {node.id}: {e}")

                    # If Cache Miss & Joern/AST Miss -> Check heuristics before
                    # Queueing for LLM. Code chunks never go to the LLM: Joern
                    # is the code extractor, and LLM entity extraction on code
                    # is slow and low-value. LLM is reserved for non-code
                    # content (docs, README, prose) above the small-file skip.
                    if node.token_count < 2000 or node.type == "code":
                        logger.debug(
                            f"Skipping LLM for {'code' if node.type == 'code' else 'small'} file "
                            f"{node.path} ({node.token_count} tokens)"
                        )
                        # Add node without entities — setdefault so a text
                        # node that already carries Joern entities (from the
                        # branch above) isn't clobbered.
                        final_nodes_map.setdefault(node.id, node)
                    else:
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
                            # Merge LLM entities with any Joern/AST entities the
                            # text node already carries (a docstring chunk in a
                            # code file) instead of replacing them. Dedupe by
                            # (name, type). An empty LLM result keeps the
                            # existing entities rather than wiping them.
                            existing = final_nodes_map.get(node.id)
                            existing_entities = (
                                existing.metadata.get("entities", [])
                                if existing and existing.metadata
                                else []
                            )
                            merged = _merge_entities(existing_entities, entities)
                            self.cache_manager.save_entities(node.hash, merged)
                            final_nodes_map[node.id] = replace(
                                node, metadata={"entities": [e._asdict() for e in merged]}
                            )
            elif nodes_needing_llm:
                # If LLM skipped, still add nodes to map — setdefault so a text
                # node with Joern entities isn't clobbered.
                for node in nodes_needing_llm:
                    final_nodes_map.setdefault(node.id, node)

            # Reassemble final nodes
            # Include ALL nodes from map (chunks + CPG entity nodes)
            final_nodes = list(final_nodes_map.values())

            # Graph Engineering transfer (opt-in): run the R-008 SC-quote + P3
            # entailment chain on non-code chunks that got LLM entities. The
            # published relations are stored on the node metadata for the query
            # path (grounding/context assembly) to consume.
            if enable_short_unit and self.provider is not None:
                from knowgraph.domain.claims.sc_extractor import (
                    AsyncChatAdapter,
                    extract_short_unit_graph,
                )

                adapter = AsyncChatAdapter(self.provider)
                for node in final_nodes:
                    if node.type == "code" or not node.content.strip():
                        continue
                    try:
                        result = await extract_short_unit_graph(adapter, node.content)
                        relations = result.get("relations", [])
                        if relations:
                            node_meta = dict(node.metadata) if node.metadata else {}
                            node_meta["relations"] = [
                                {
                                    "subject": r["subject"],
                                    "predicate": r["predicate"],
                                    "object": r["object"],
                                    "source": "sc_p3",
                                }
                                for r in relations
                            ]
                            final_nodes_map[node.id] = replace(node, metadata=node_meta)
                    except Exception as e:
                        logger.debug(f"Short-unit extraction failed for node {node.id}: {e}")
                        continue
                # Reassemble in case metadata was updated.
                final_nodes = list(final_nodes_map.values())
                # Graph Engineering: turn SC-quote + P3 verified relations into
                # grounded edges so they become part of the queryable graph.
                sc_edges = self._sc_relations_to_edges(final_nodes)
            else:
                sc_edges = []

            # Finalize metrics
            self.metrics.finalize()
            logger.info(f"\n{self.metrics.get_summary()}")

            # 4. Create Edges (Semantic + Reference)
            with self.perf_tracker.track("edge_creation"):
                from knowgraph.infrastructure.storage.filesystem import (
                    list_all_nodes,
                    read_node_metadata_only,
                )

                # Reference-context resolution: build/load the global symbol
                # table (symbol -> defining node IDs) for previously indexed
                # nodes. Cache it on disk so incremental builds don't re-read
                # every existing node file (which is O(existing nodes) I/O).
                graph_path_obj = Path(graph_path)
                cache_dir = Path(graph_path) / ".cache"
                symbols_cache = cache_dir / "reference_symbols.json"

                existing_metadata = []
                existing_symbols: dict[str, list[UUID]] | None = None
                existing_real_node_ids: set[UUID] = set()

                # Try the on-disk symbol cache first (fast path).
                if symbols_cache.exists():
                    try:
                        import json as _json

                        loaded = _json.loads(symbols_cache.read_text(encoding="utf-8"))
                        existing_symbols = {
                            sym: [UUID(str(n)) for n in ids] for sym, ids in loaded.items()
                        }
                        # Real node IDs for edge filtering: all IDs referenced by
                        # the symbol table are existing (real) nodes.
                        existing_real_node_ids = {
                            UUID(nid) for ids in existing_symbols.values() for nid in ids
                        }
                        logger.info(
                            f"Loaded {len(existing_symbols)} reference symbols from cache"
                        )
                    except Exception as e:
                        logger.warning(f"Reference symbol cache unreadable: {e}")
                        existing_symbols = None

                # Cache miss: fall back to reading every existing node's metadata.
                if existing_symbols is None and graph_path_obj.exists():
                    try:
                        node_ids = list_all_nodes(graph_path_obj)
                        final_node_ids = {fn.id for fn in final_nodes}

                        # Parallel metadata loading
                        async def load_metadata(n_id):
                            # Skip nodes we just built
                            if n_id in final_node_ids:
                                return None

                            # Load ONLY metadata (95% memory reduction)
                            metadata_dict = await asyncio.get_event_loop().run_in_executor(
                                None, read_node_metadata_only, n_id, graph_path_obj
                            )
                            if metadata_dict and metadata_dict.get("entities"):
                                existing_real_node_ids.add(n_id)
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
                        existing_metadata = [
                        m for m in metadata_results
                        if m is not None and not isinstance(m, BaseException)
                    ]
                    except Exception as e:
                        logger.warning(
                            f"Could not load existing node metadata for reference context: {e}"
                        )

                all_context_nodes = final_nodes + existing_metadata

                # OPTIMIZATION: Only create semantic edges between NEW nodes
                semantic_edges = create_semantic_edges(final_nodes)
                logger.info(f"Created {len(semantic_edges)} semantic edges from {len(final_nodes)} nodes")

                # create_reference_edges uses global context to resolve symbols
                reference_edges = create_reference_edges(all_context_nodes, existing_symbols)
                logger.info(f"Created {len(reference_edges)} reference edges (before filtering)")

                # Persist the (now updated) reference symbol cache so the next
                # incremental build skips re-reading all existing node files.
                try:
                    import json as _json

                    merged_symbols = {
                        sym: [str(node_id) for node_id in ids]
                        for sym, ids in (existing_symbols or {}).items()
                    }
                    for node in final_nodes:
                        ents = (node.metadata or {}).get("entities")
                        if not isinstance(ents, list):
                            continue
                        for e in ents:
                            if isinstance(e, dict) and e.get("type") == "definition" and e.get("name"):
                                merged_symbols.setdefault(e["name"], []).append(str(node.id))
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    symbols_cache.write_text(
                        _json.dumps(merged_symbols, ensure_ascii=False),
                        encoding="utf-8",
                    )
                except Exception as e:
                    logger.warning(f"Could not persist reference symbol cache: {e}")

                # Filter reference_edges: We only want edges where BOTH ends are real nodes
                # Real nodes = new nodes we just created (final_nodes)
                # existing_metadata nodes are FAKE nodes (metadata-only) used for symbol resolution
                # We must NOT create edges pointing to these fake nodes!
                new_node_ids = {n.id for n in final_nodes}

                # Get IDs of all real nodes in the graph store (for validation).
                # existing_real_node_ids may already be populated from the
                # symbol cache (fast path); only augment from existing_metadata
                # when we actually read node metadata (cache-miss path).
                if existing_metadata:
                    existing_real_node_ids |= {n.id for n in existing_metadata}

                all_real_node_ids = new_node_ids | existing_real_node_ids

                relevant_reference_edges = [
                    e
                    for e in reference_edges
                    # Keep edge only if BOTH source AND target are real nodes
                    if e.source in all_real_node_ids and e.target in all_real_node_ids
                    # AND at least one end is a NEW node (we don't want old-to-old edges)
                    and (e.source in new_node_ids or e.target in new_node_ids)
                ]

                logger.info(f"Filtered to {len(relevant_reference_edges)} valid reference edges")

                # Filter CPG edges: Only keep edges where BOTH ends exist in final_nodes
                # CPG edges should only reference entity nodes we just created
                valid_cpg_edges = [
                    e
                    for e in cpg_edges
                    if e.source in new_node_ids and e.target in new_node_ids
                ]

                if len(cpg_edges) != len(valid_cpg_edges):
                    logger.warning(
                        f"Filtered {len(cpg_edges) - len(valid_cpg_edges)} invalid CPG edges "
                        f"(referencing non-existent nodes)"
                    )

                # Include CPG edges if any were collected
                all_edges = semantic_edges + relevant_reference_edges + valid_cpg_edges + sc_edges
                logger.info(
                    f"Total edges: {len(all_edges)} "
                    f"(semantic: {len(semantic_edges)}, reference: {len(relevant_reference_edges)}, cpg: {len(valid_cpg_edges)}, sc: {len(sc_edges)})"
                )


                # Auto-validate graph before returning
                with self.perf_tracker.track("validation"):
                    validation_warnings = self._validate_build_results(
                        final_nodes,
                        all_edges,
                        valid_node_ids=all_real_node_ids,
                    )
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

    def _sc_relations_to_edges(self, nodes: list[Node]) -> list[Edge]:
        """Convert SC-extractor relations (stored on node metadata) into graph edges.

        Each relation is a (subject, predicate, object) triple produced by the
        R-008 SC-quote + P3 entailment chain (Graph Engineering transfer). The
        subject/object are surface-form entity names; resolve the subject to its
        best matching node (defaults to the node that produced the relation) and
        the object to its best matching node EXCLUDING the subject node. A
        ``grounded`` edge is added between distinct endpoints. Relations whose
        object cannot be resolved to a node other than the subject's are skipped
        (anti-fabrication: a relation inside one document is not a cross-document
        edge).
        """
        import time as _time

        edges: list[Edge] = []

        def _match(name: str, exclude: UUID | None = None) -> UUID | None:
            if not name:
                return None
            needle = name.strip()
            if not needle:
                return None
            # Graph Engineering entity_resolver transfer: exact-name fast-path via
            # the build-time entity metadata BEFORE substring fallback. This is
            # stricter (avoids content false-positives) and resolves names that
            # may not literally appear in title/content (e.g. a canonical symbol
            # registered under metadata["entities"]).
            for candidate in nodes:
                if candidate.type == "conversation":
                    continue
                if exclude is not None and candidate.id == exclude:
                    continue
                ents = (candidate.metadata or {}).get("entities", []) or []
                if any(
                    isinstance(e, dict) and str(e.get("name", "")).strip() == needle
                    for e in ents
                ):
                    return candidate.id
            needle = needle.lower()
            best: UUID | None = None
            best_rank = -1
            for candidate in nodes:
                if candidate.type == "conversation":
                    continue  # skip conversation nodes as entity endpoints
                if exclude is not None and candidate.id == exclude:
                    continue
                rank = 0
                if candidate.path and needle in candidate.path.lower():
                    rank = 3
                elif candidate.title and needle in candidate.title.lower():
                    rank = 2
                elif candidate.content and needle in candidate.content.lower():
                    rank = 1
                if rank > best_rank:
                    best_rank = rank
                    best = candidate.id
            return best if best_rank > 0 else None

        for node in nodes:
            if not node.metadata:
                continue
            # The node that produced the relation is the subject's home node.
            subj_id: UUID | None = node.id
            for rel in node.metadata.get("relations", []):
                # Prefer an explicit subject node match, else fall back to the
                # producing node itself.
                subj_id = _match(rel.get("subject", "")) or node.id
                # Object must resolve to a node OTHER than the subject's.
                obj_id = _match(rel.get("object", ""), exclude=subj_id)
                if subj_id is None or obj_id is None or subj_id == obj_id:
                    continue
                edges.append(
                    Edge(
                        source=subj_id,
                        target=obj_id,
                        type="grounded",
                        score=0.9,  # SC-quote + P3 verified
                        created_at=int(_time.time()),
                        metadata={
                            "predicate": str(rel.get("predicate", "")),
                            "source": "sc_p3",
                        },
                    )
                )
        return edges

    def _validate_build_results(
        self,
        nodes: list[Node],
        edges: list[Edge],
        valid_node_ids: set[UUID] | None = None,
    ) -> list[str]:
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
        edge_node_ids = valid_node_ids or node_ids
        for edge in edges:
            if edge.source not in edge_node_ids:
                warnings.append(f"Dangling edge: source {edge.source} not in nodes")
            if edge.target not in edge_node_ids:
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

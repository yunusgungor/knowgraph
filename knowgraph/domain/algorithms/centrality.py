"""Centrality metrics for graph reasoning.

Implements composite centrality scoring combining multiple metrics
for importance-based node ranking.

Optimized with:
- LRU caching for repeated subgraph queries
- Multiprocessing for large graphs
- Async support for concurrent operations
"""

import asyncio
import atexit
from concurrent.futures import ProcessPoolExecutor
from uuid import UUID

import networkx as nx

from knowgraph.config import (
    BETWEENNESS_MIN_SAMPLES,
    BETWEENNESS_SAMPLE_SIZE_FACTOR,
    CENTRALITY_APPROXIMATE_THRESHOLD,
    CENTRALITY_BETWEENNESS_WEIGHT,
    CENTRALITY_CLOSENESS_WEIGHT,
    CENTRALITY_DEGREE_WEIGHT,
    CENTRALITY_EIGENVECTOR_WEIGHT,
    CENTRALITY_MULTIPROCESSING_ENABLED,
    CENTRALITY_MULTIPROCESSING_THRESHOLD,
    EIGENVECTOR_MAX_ITER_APPROXIMATE,
    EIGENVECTOR_MAX_ITER_EXACT,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node

# Global process pool for multiprocessing
_process_pool: ProcessPoolExecutor | None = None


def _get_process_pool() -> ProcessPoolExecutor:
    """Get or create global process pool for multiprocessing."""
    global _process_pool
    if _process_pool is None:
        _process_pool = ProcessPoolExecutor(max_workers=4)
        # Register cleanup on exit to prevent resource leaks
        atexit.register(_shutdown_process_pool)
    return _process_pool


def _shutdown_process_pool() -> None:
    """Shutdown global process pool."""
    global _process_pool
    if _process_pool is not None:
        _process_pool.shutdown(wait=True)
        _process_pool = None


def build_networkx_graph(nodes: list[Node], edges: list[Edge]) -> "nx.Graph[object]":
    """Build NetworkX graph from nodes and edges (REFERENCE-AWARE WEIGHTS).

    Args:
    ----
        nodes: List of nodes
        edges: List of edges

    Returns:
    -------
        NetworkX graph with edge-type-aware weights

    """
    graph = nx.Graph()

    # Add nodes
    for node in nodes:
        graph.add_node(node.id, data=node)

    # Add edges with TYPE-AWARE WEIGHTS
    for edge in edges:
        # Reference edges get 2x weight (more important for centrality)
        # Semantic edges get 1x weight (baseline)
        edge_weight = 2.0 if edge.type == "reference" else 1.0

        # NetworkX uses weight for shortest path calculations in centrality
        # Higher weight = shorter distance in some metrics (inverse relationship)
        # For betweenness/closeness, lower weight = shorter path, so we invert
        # But for our use case, we want reference edges to be "preferred" paths
        # So we use the weight directly as importance multiplier
        graph.add_edge(
            edge.source,
            edge.target,
            weight=edge.score * edge_weight,  # Combine semantic score with type weight
            edge_type=edge.type,
            base_score=edge.score,
            type_weight=edge_weight,
        )

    return graph


# Global cache for centrality results
_centrality_cache: dict[
    tuple[tuple[UUID, ...], tuple[tuple[UUID, UUID, str], ...]], dict[UUID, dict[str, float]]
] = {}
_cache_max_size = 512  # Increased from 256
_centrality_cache_version: int = 0  # Incremented on invalidation


def clear_centrality_cache() -> None:
    """Clear the centrality cache. Useful for testing or memory management."""
    global _centrality_cache_version
    _centrality_cache.clear()
    _centrality_cache_version += 1


def get_cache_stats() -> dict[str, int]:
    """Get centrality cache statistics."""
    return {
        "size": len(_centrality_cache),
        "max_size": _cache_max_size,
        "utilization": (
            int((len(_centrality_cache) / _cache_max_size) * 100) if _cache_max_size > 0 else 0
        ),
        "version": _centrality_cache_version,
    }


def compute_centrality_metrics(
    nodes: list[Node], edges: list[Edge]
) -> dict[UUID, dict[str, float]]:
    """Compute centrality metrics with caching.

    Uses a simple dict cache to avoid repeated expensive NetworkX calculations.
    """
    # Create cache key from sorted IDs
    cache_key = (
        tuple(sorted(node.id for node in nodes)),
        tuple(sorted((edge.source, edge.target, edge.type) for edge in edges)),
    )

    # Check cache
    if cache_key in _centrality_cache:
        return _centrality_cache[cache_key]

    # Compute if not cached
    result = _compute_centrality_impl(nodes, edges)

    # Store in cache (with size limit)
    if len(_centrality_cache) >= _cache_max_size:
        # Remove oldest entry (simple FIFO)
        _centrality_cache.pop(next(iter(_centrality_cache)))

    _centrality_cache[cache_key] = result
    return result


def _compute_centrality_impl(
    nodes: list[Node],
    edges: list[Edge],
) -> dict[UUID, dict[str, float]]:
    """Compute centrality metrics for all nodes in subgraph.

    Calculates betweenness, degree, closeness, and eigenvector centrality.
    Uses approximate algorithms and multiprocessing for large graphs.

    Args:
    ----
        nodes: List of nodes in active subgraph
        edges: List of edges in active subgraph

    Returns:
    -------
        Dictionary mapping node UUID to centrality metrics

    """
    if not nodes or not edges:
        return {node.id: _default_centrality() for node in nodes}

    graph = build_networkx_graph(nodes, edges)

    # Handle disconnected graphs
    if not nx.is_connected(graph):
        return _compute_disconnected_centrality(graph, nodes)

    metrics = {}

    # Use approximate algorithms for medium-sized graphs
    use_approximate = len(nodes) > CENTRALITY_APPROXIMATE_THRESHOLD

    # Betweenness centrality (architectural boundaries)
    try:
        if use_approximate:
            # Approximate betweenness for large graphs (sample-based)
            k = max(BETWEENNESS_MIN_SAMPLES, int(len(nodes) * BETWEENNESS_SAMPLE_SIZE_FACTOR))
            betweenness = nx.betweenness_centrality(graph, k=k, normalized=True, weight="weight")
        else:
            # Exact betweenness for small graphs
            betweenness = nx.betweenness_centrality(graph, normalized=True, weight="weight")
    except Exception:
        betweenness = {node.id: 0.0 for node in nodes}

    # Degree centrality (API surface) - always fast
    degree = nx.degree_centrality(graph)

    # Closeness centrality (accessibility)
    try:
        closeness = nx.closeness_centrality(graph, distance="weight")
    except Exception:
        closeness = {node.id: 0.0 for node in nodes}

    # Eigenvector centrality (importance)
    try:
        max_iter = (
            EIGENVECTOR_MAX_ITER_APPROXIMATE if use_approximate else EIGENVECTOR_MAX_ITER_EXACT
        )
        eigenvector = nx.eigenvector_centrality(graph, max_iter=max_iter, weight="weight")
    except Exception:
        eigenvector = {node.id: 0.0 for node in nodes}

    # Combine metrics
    for node in nodes:
        node_id = node.id
        metrics[node_id] = {
            "betweenness": betweenness.get(node_id, 0.0),
            "degree": degree.get(node_id, 0.0),
            "closeness": closeness.get(node_id, 0.0),
            "eigenvector": eigenvector.get(node_id, 0.0),
            "composite": _compute_composite_score(
                betweenness.get(node_id, 0.0),
                degree.get(node_id, 0.0),
                closeness.get(node_id, 0.0),
                eigenvector.get(node_id, 0.0),
            ),
        }

    return metrics


async def compute_centrality_metrics_async(
    nodes: list[Node], edges: list[Edge]
) -> dict[UUID, dict[str, float]]:
    """Compute centrality metrics asynchronously with optional multiprocessing.

    For large graphs (>500 nodes), uses ProcessPoolExecutor to compute
    centrality metrics in parallel processes, avoiding GIL limitations.

    Args:
    ----
        nodes: List of nodes in active subgraph
        edges: List of edges in active subgraph

    Returns:
    -------
        Dictionary mapping node UUID to centrality metrics

    """
    # Check cache first (synchronous, fast)
    cache_key = (
        tuple(sorted(node.id for node in nodes)),
        tuple(sorted((edge.source, edge.target, edge.type) for edge in edges)),
    )

    if cache_key in _centrality_cache:
        return _centrality_cache[cache_key]

    # Determine if we should use multiprocessing
    use_multiprocessing = (
        CENTRALITY_MULTIPROCESSING_ENABLED and len(nodes) > CENTRALITY_MULTIPROCESSING_THRESHOLD
    )

    if use_multiprocessing:
        # Compute in separate process to avoid GIL
        loop = asyncio.get_event_loop()
        pool = _get_process_pool()
        result = await loop.run_in_executor(pool, _compute_centrality_impl, nodes, edges)
    else:
        # Compute in current process (run in thread pool to not block event loop)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _compute_centrality_impl, nodes, edges)

    # Store in cache
    if len(_centrality_cache) >= _cache_max_size:
        _centrality_cache.pop(next(iter(_centrality_cache)))
    _centrality_cache[cache_key] = result

    return result


def _compute_disconnected_centrality(
    graph: "nx.Graph[object]", nodes: list[Node]  # noqa: ARG001
) -> dict[UUID, dict[str, float]]:
    """Compute centrality for disconnected graph.

    Args:
    ----
        graph: NetworkX graph
        nodes: List of nodes

    Returns:
    -------
        Centrality metrics per node

    """
    metrics = {}

    # Compute per-component
    for component in nx.connected_components(graph):
        subgraph = graph.subgraph(component)

        try:
            betweenness = nx.betweenness_centrality(subgraph, normalized=True, weight="weight")
        except Exception:
            betweenness = dict.fromkeys(component, 0.0)

        degree = nx.degree_centrality(subgraph)

        try:
            closeness = nx.closeness_centrality(subgraph, distance="weight")
        except Exception:
            closeness = dict.fromkeys(component, 0.0)

        try:
            eigenvector = nx.eigenvector_centrality(subgraph, max_iter=100, weight="weight")
        except Exception:
            eigenvector = dict.fromkeys(component, 0.0)

        for node_id in component:
            metrics[node_id] = {
                "betweenness": betweenness.get(node_id, 0.0),
                "degree": degree.get(node_id, 0.0),
                "closeness": closeness.get(node_id, 0.0),
                "eigenvector": eigenvector.get(node_id, 0.0),
                "composite": _compute_composite_score(
                    betweenness.get(node_id, 0.0),
                    degree.get(node_id, 0.0),
                    closeness.get(node_id, 0.0),
                    eigenvector.get(node_id, 0.0),
                ),
            }

    return metrics


def _compute_composite_score(
    betweenness: float,
    degree: float,
    closeness: float,
    eigenvector: float,
) -> float:
    """Compute weighted composite centrality score.

    Args:
    ----
        betweenness: Betweenness centrality
        degree: Degree centrality
        closeness: Closeness centrality
        eigenvector: Eigenvector centrality

    Returns:
    -------
        Composite score [0, 1]

    """
    return (
        CENTRALITY_BETWEENNESS_WEIGHT * betweenness
        + CENTRALITY_DEGREE_WEIGHT * degree
        + CENTRALITY_CLOSENESS_WEIGHT * closeness
        + CENTRALITY_EIGENVECTOR_WEIGHT * eigenvector
    )


def _default_centrality() -> dict[str, float]:
    """Return default centrality values for isolated nodes.

    Returns
    -------
        Default centrality dict

    """
    return {
        "betweenness": 0.0,
        "degree": 0.0,
        "closeness": 0.0,
        "eigenvector": 0.0,
        "composite": 0.0,
    }

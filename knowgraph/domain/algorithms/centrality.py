"""Centrality metrics for graph reasoning.

Implements composite centrality scoring combining multiple metrics
for importance-based node ranking.

Optimized with LRU caching for repeated subgraph queries.
"""

from functools import lru_cache
from uuid import UUID

import networkx as nx

from knowgraph.config import (
    CENTRALITY_BETWEENNESS_WEIGHT,
    CENTRALITY_CLOSENESS_WEIGHT,
    CENTRALITY_DEGREE_WEIGHT,
    CENTRALITY_EIGENVECTOR_WEIGHT,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


def build_networkx_graph(nodes: list[Node], edges: list[Edge]) -> "nx.Graph[object]":
    """Build NetworkX graph from nodes and edges.

    Args:
    ----
        nodes: List of nodes
        edges: List of edges

    Returns:
    -------
        NetworkX graph

    """
    graph = nx.Graph()

    # Add nodes
    for node in nodes:
        graph.add_node(node.id, data=node)

    # Add edges
    for edge in edges:
        graph.add_edge(edge.source, edge.target, weight=edge.score, edge_type=edge.type)

    return graph


# Global cache for centrality results
_centrality_cache: dict[
    tuple[tuple[UUID, ...], tuple[tuple[UUID, UUID, str], ...]], dict[UUID, dict[str, float]]
] = {}
_cache_max_size = 256


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
    Uses approximate algorithms for large graphs (>100 nodes) for better performance.

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

    # Use approximate algorithms for large graphs
    use_approximate = len(nodes) > 100

    # Betweenness centrality (architectural boundaries)
    try:
        if use_approximate:
            # Approximate betweenness for large graphs (sample-based)
            # Sample ~sqrt(n) nodes for estimation
            k = max(10, int(len(nodes) ** 0.5))
            betweenness = nx.betweenness_centrality(graph, k=k, normalized=True)
        else:
            # Exact betweenness for small graphs
            betweenness = nx.betweenness_centrality(graph, normalized=True)
    except Exception:
        betweenness = {node.id: 0.0 for node in nodes}

    # Degree centrality (API surface) - always fast
    degree = nx.degree_centrality(graph)

    # Closeness centrality (accessibility)
    try:
        closeness = nx.closeness_centrality(graph)
    except Exception:
        closeness = {node.id: 0.0 for node in nodes}

    # Eigenvector centrality (importance)
    try:
        if use_approximate:
            # Reduce max iterations for large graphs
            eigenvector = nx.eigenvector_centrality(graph, max_iter=50)
        else:
            eigenvector = nx.eigenvector_centrality(graph, max_iter=100)
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
            betweenness = nx.betweenness_centrality(subgraph, normalized=True)
        except Exception:
            betweenness = dict.fromkeys(component, 0.0)

        degree = nx.degree_centrality(subgraph)

        try:
            closeness = nx.closeness_centrality(subgraph)
        except Exception:
            closeness = dict.fromkeys(component, 0.0)

        try:
            eigenvector = nx.eigenvector_centrality(subgraph, max_iter=100)
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


def get_top_k_central_nodes(
    centrality_metrics: dict[UUID, dict[str, float]],
    k: int = 10,
    metric: str = "composite",
) -> list[tuple[UUID, float]]:
    """Get top-k most central nodes by specified metric.

    Args:
    ----
        centrality_metrics: Node centrality metrics
        k: Number of results
        metric: Centrality metric to use

    Returns:
    -------
        List of (node_id, score) tuples

    """
    scores = [(node_id, metrics[metric]) for node_id, metrics in centrality_metrics.items()]
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:k]

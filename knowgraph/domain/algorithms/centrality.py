"""Centrality calculations on active subgraphs.

Computes per-query centrality metrics (betweenness, degree, closeness, eigenvector)
using NetworkX on the active reasoning subgraph.
"""

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


def compute_centrality_metrics(
    nodes: list[Node],
    edges: list[Edge],
) -> dict[UUID, dict[str, float]]:
    """Compute centrality metrics for all nodes in subgraph.

    Calculates betweenness, degree, closeness, and eigenvector centrality.

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

    # Betweenness centrality (architectural boundaries)
    try:
        betweenness = nx.betweenness_centrality(graph, normalized=True)
    except Exception:
        betweenness = {node.id: 0.0 for node in nodes}

    # Degree centrality (API surface)
    degree = nx.degree_centrality(graph)

    # Closeness centrality (accessibility)
    try:
        closeness = nx.closeness_centrality(graph)
    except Exception:
        closeness = {node.id: 0.0 for node in nodes}

    # Eigenvector centrality (importance)
    try:
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

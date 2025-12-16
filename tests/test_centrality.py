from unittest.mock import MagicMock
from uuid import uuid4

from knowgraph.domain.algorithms.centrality import compute_centrality_metrics
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


def create_mock_node():
    n = MagicMock(spec=Node)
    n.id = uuid4()
    return n


def create_mock_edge(src, tgt):
    e = MagicMock(spec=Edge)
    e.source = src
    e.target = tgt
    e.score = 1.0
    e.type = "semantic"
    return e


def test_compute_centrality_metrics_basic():
    n1 = create_mock_node()
    n2 = create_mock_node()
    e1 = create_mock_edge(n1.id, n2.id)

    metrics = compute_centrality_metrics([n1, n2], [e1])

    assert n1.id in metrics
    assert n2.id in metrics
    assert "degree" in metrics[n1.id]
    assert "betweenness" in metrics[n1.id]

    # Star graph/Line graph P2: A-B.
    # Degree: 1/(N-1) = 1/1 = 1.0 for both.
    assert metrics[n1.id]["degree"] == 1.0


def test_compute_centrality_empty():
    metrics = compute_centrality_metrics([], [])
    assert metrics == {}


def test_compute_centrality_disconnected():
    # A-B, C-D
    n1, n2 = create_mock_node(), create_mock_node()
    n3, n4 = create_mock_node(), create_mock_node()

    edges = [create_mock_edge(n1.id, n2.id), create_mock_edge(n3.id, n4.id)]

    metrics = compute_centrality_metrics([n1, n2, n3, n4], edges)
    assert len(metrics) == 4
    # Check degree. Subgraph size 2. Degree = 1.
    # nx.degree_centrality normalizes by N-1 where N is graph size.
    # For disconnected components, does it normalize by component size?
    # Logic in _compute_disconnected_centrality loops over components using subgraph.
    # nx.degree_centrality(subgraph). Subgraph size 2. N-1=1. Degree 1/1=1.0.
    assert metrics[n1.id]["degree"] == 1.0
    assert metrics[n3.id]["degree"] == 1.0

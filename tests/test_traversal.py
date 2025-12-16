from unittest.mock import MagicMock
from uuid import uuid4

from knowgraph.domain.algorithms.traversal import (
    traverse_graph_bfs,
    traverse_reverse_references,
)
from knowgraph.domain.models.edge import Edge


def create_mock_edge(src, tgt, type="semantic"):
    e = MagicMock(spec=Edge)
    e.source = src
    e.target = tgt
    e.type = type
    return e


def test_traverse_graph_bfs():
    # A -> B -> C
    # Use UUIDs as nodes are UUIDs usually, but code handles hashable.
    # Traversal uses UUIDs in type hints.
    a, b, c = uuid4(), uuid4(), uuid4()

    edges = [create_mock_edge(a, b), create_mock_edge(b, c)]

    visited = traverse_graph_bfs([a], edges, max_hops=2)
    assert a in visited
    assert b in visited
    assert c in visited
    assert len(visited) == 3


def test_traverse_graph_limit():
    a, b, c = uuid4(), uuid4(), uuid4()
    edges = [create_mock_edge(a, b), create_mock_edge(b, c)]

    visited = traverse_graph_bfs([a], edges, max_hops=1)
    assert a in visited
    assert b in visited
    assert c not in visited


def test_traverse_reverse():
    # A -> B (A references B)
    # Impact on B? A should be found.
    # traverse_reverse_references(target=[B]) -> {B, A}

    a, b = uuid4(), uuid4()
    edges = [create_mock_edge(a, b, type="semantic")]

    visited = traverse_reverse_references([b], edges, max_hops=1, edge_types=["semantic"])
    assert b in visited
    assert a in visited

from uuid import uuid4

from knowgraph.domain.algorithms.traversal import (
    traverse_graph_bfs,
    traverse_graph_dfs,
    traverse_reverse_references,
)
from knowgraph.domain.models.edge import Edge


def create_edge(src, tgt):
    return Edge(source=src, target=tgt, type="type", score=1.0, created_at=1, metadata={})


def test_manual_bfs():
    n1, n2, n3, n4 = uuid4(), uuid4(), uuid4(), uuid4()
    edges = [create_edge(n1, n2), create_edge(n2, n3), create_edge(n3, n4)]

    # 0 hops
    res = traverse_graph_bfs([n1], edges, max_hops=0)
    assert len(res) == 1
    assert n1 in res

    # 1 hop
    res = traverse_graph_bfs([n1], edges, max_hops=1)
    assert len(res) == 2
    assert n2 in res

    # 2 hops
    res = traverse_graph_bfs([n1], edges, max_hops=2)
    assert len(res) == 3
    assert n3 in res


def test_manual_dfs():
    n1, n2, n3 = uuid4(), uuid4(), uuid4()
    edges = [create_edge(n1, n2), create_edge(n2, n3)]

    # Max hops limits depth
    res = traverse_graph_dfs([n1], edges, max_hops=1)
    assert len(res) <= 3
    # Exact check depends on DFS order but should include n1, n2
    assert n1 in res
    assert n2 in res
    assert n3 not in res


def test_reverse_traversal():
    n1, n2, n3 = uuid4(), uuid4(), uuid4()
    # n1 -> n2 -> n3
    edges = [create_edge(n1, n2), create_edge(n2, n3)]

    # Reverse from n3 should find n2, n1
    res = traverse_reverse_references([n3], edges, max_hops=2)
    assert n3 in res
    assert n2 in res
    assert n1 in res

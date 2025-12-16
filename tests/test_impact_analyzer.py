from unittest.mock import MagicMock
from uuid import uuid4

from knowgraph.application.querying.impact_analyzer import (
    analyze_impact,
    find_node_by_path_pattern,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


def create_mock_node(uid, path="file.py"):
    n = MagicMock(spec=Node)
    n.id = uid
    n.path = path
    n.hash = "0" * 40
    return n


def create_mock_edge(src, tgt):
    e = MagicMock(spec=Edge)
    e.source = src
    e.target = tgt
    e.type = "semantic"
    return e


def test_analyze_impact_found():
    # Dependency chain: A <- B (B depends on A)
    # Target: A. We want to find B.
    # Logic: reverse traversal.
    a_id = uuid4()
    b_id = uuid4()

    n_a = create_mock_node(a_id, "a.py")
    n_b = create_mock_node(b_id, "b.py")

    # Edge A->B means A depends on B? OR A->B means semantic link?
    # In knowgraph, dependency usually: if A uses B, edge A->B (reference).
    # "Nodes that depend on target".
    # If Target=B. We want A.
    # traverse_reverse_references follows Target -> Source.
    # So if edge A->B exists, Source=A, Target=B.
    # reverse adjacency[Target] -> [Source].
    # So if we have edge A->B, and we target B, we find A.

    e1 = create_mock_edge(n_a.id, n_b.id)  # A -> B

    result = analyze_impact(n_b.id, [n_a, n_b], [e1])

    assert result.target_node == n_b
    assert n_a in result.dependent_nodes
    assert len(result.dependency_edges) == 1
    assert result.impact_depth == 1
    assert result.impact_breadth == 2  # "a.py", "b.py"


def test_analyze_impact_not_found():
    result = analyze_impact(uuid4(), [], [])
    assert len(result.dependent_nodes) == 0
    assert result.target_node.title == "Unknown"


def test_find_node_by_path_pattern():
    n1 = create_mock_node(uuid4(), "src/utils.py")
    n2 = create_mock_node(uuid4(), "tests/active.py")

    nodes = [n1, n2]

    assert find_node_by_path_pattern("utils", nodes) == [n1]
    assert find_node_by_path_pattern("active", nodes) == [n2]
    assert find_node_by_path_pattern("missing", nodes) == []

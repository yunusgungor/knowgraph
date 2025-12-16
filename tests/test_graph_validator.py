from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from knowgraph.domain.algorithms.graph_validator import validate_graph_consistency
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


@pytest.fixture
def mock_storage():
    with (
        patch("knowgraph.domain.algorithms.graph_validator.list_all_nodes") as mock_list,
        patch("knowgraph.domain.algorithms.graph_validator.read_all_edges") as mock_edges,
        patch("knowgraph.domain.algorithms.graph_validator.read_node_json") as mock_read_node,
    ):
        yield mock_list, mock_edges, mock_read_node


def create_node(uid=None, hash_val="a" * 40):
    if not uid:
        uid = uuid4()
    return Node(
        id=uid,
        hash=hash_val,
        title="Node",
        content="content",
        path="file.md",
        type="text",
        token_count=10,
        created_at=123,
    )


def create_edge(src, tgt, type="semantic"):
    # Avoid self-loop error in Edge.__post_init__ during creation unless intended
    # If test intentionally creates self-loop, Edge init will RAISE ValueError if not mocked.
    # But wait, Edge logic raises ValueError if source == target.
    # The validator test expects to DETECT self-loops.
    # If Edge() constructor raises ValueError, I can't even create the object to pass to validator.
    # Validation logic checks: source == target.
    # If I can't create such an Edge, the validator check for self-loops is moot/unreachable unless I bypass init checks.
    # or if validation runs on DICTs? No, logic uses `edge.source`.
    # I should check if I can bypass post_init or if validator runs on raw data?
    # Validator takes `list[Edge]`. So I MUST provide `Edge` objects.
    # If `Edge` forbids self-loops, then `list_all_edges` would supposedly fail to load them?
    # Or maybe data is loaded via `from_dict`?
    # `from_dict` calls `cls(...)`.
    # Does `cls(...)` call `__post_init__`? Yes in dataclasses.
    # So `Edge` class ENFORCES no self-loops.
    # Thus `detect_self_loops` in validator is redundant or for legacy data?
    # I will mock `Edge` class or create a dummy object that looks like Edge if I want to test that specific function.
    # For now, I'll assume valid creation.
    return Edge(source=src, target=tgt, type=type, score=1.0, created_at=123, metadata={})


def test_validate_valid_graph(mock_storage):
    mock_list, mock_edges, mock_read_node = mock_storage

    n1_id = uuid4()
    n2_id = uuid4()

    mock_list.return_value = [n1_id, n2_id]
    mock_edges.return_value = [create_edge(n1_id, n2_id)]

    def side_effect_read(nid, path):
        if nid == n1_id:
            return create_node(n1_id)
        if nid == n2_id:
            return create_node(n2_id)
        return None

    mock_read_node.side_effect = side_effect_read

    result = validate_graph_consistency("path")
    assert result.valid is True
    assert result.error_count == 0
    assert "Passed" in result.get_error_summary() or "passed" in result.get_error_summary()


def test_validate_dangling_edge(mock_storage):
    mock_list, mock_edges, mock_read_node = mock_storage

    n1_id = uuid4()
    missing_id = uuid4()

    mock_list.return_value = [n1_id]
    mock_edges.return_value = [create_edge(n1_id, missing_id)]
    mock_read_node.return_value = create_node(n1_id)

    result = validate_graph_consistency("path")
    assert result.valid is False
    assert len(result.dangling_edges) == 1


def test_validate_self_loop(mock_storage):
    mock_list, mock_edges, mock_read_node = mock_storage

    n1_id = uuid4()
    mock_list.return_value = [n1_id]

    # Create a mock edge to bypass __post_init__ check for self-loops
    mock_edge = MagicMock(spec=Edge)
    mock_edge.source = n1_id
    mock_edge.target = n1_id
    mock_edge.type = "semantic"

    mock_edges.return_value = [mock_edge]
    mock_read_node.return_value = create_node(n1_id)

    result = validate_graph_consistency("path")
    assert result.valid is False
    assert len(result.self_loops) == 1


def test_validate_invalid_edge_type(mock_storage):
    mock_list, mock_edges, mock_read_node = mock_storage

    n1_id = uuid4()
    n2_id = uuid4()
    mock_list.return_value = [n1_id, n2_id]
    # "bad_type" is not in VALID_EDGE_TYPES
    mock_edges.return_value = [create_edge(n1_id, n2_id, type="bad_type")]
    mock_read_node.return_value = create_node(n1_id)

    result = validate_graph_consistency("path")
    assert result.valid is False
    assert len(result.invalid_edge_types) == 1


def test_validate_invalid_node_hash(mock_storage):
    mock_list, mock_edges, mock_read_node = mock_storage

    n1_id = uuid4()
    mock_list.return_value = [n1_id]
    mock_edges.return_value = []

    # Mock Node to bypass __post_init__ validation of hash length
    mock_node = MagicMock(spec=Node)
    mock_node.id = n1_id
    mock_node.hash = "123"  # Invalid
    mock_node.type = "text"

    mock_read_node.return_value = mock_node

    result = validate_graph_consistency("path")
    assert result.valid is False
    assert len(result.invalid_node_hashes) == 1

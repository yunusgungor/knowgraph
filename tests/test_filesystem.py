from uuid import uuid4

import pytest

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.storage.filesystem import (
    append_edge_jsonl,
    delete_node_json,
    ensure_directory,
    list_all_nodes,
    read_all_edges,
    read_node_json,
    write_all_edges,
    write_node_json,
)


@pytest.fixture
def store_path(tmp_path):
    p = tmp_path / "store"
    p.mkdir()
    return p


def test_ensure_directory(store_path):
    sub = store_path / "subdir" / "nested"
    ensure_directory(sub)
    assert sub.exists()
    assert sub.is_dir()


def test_node_io(store_path):
    """Test write, read, list, delete for nodes."""
    uid = uuid4()
    # Mock node - assuming Node has some required fields
    # Node(id: UUID, name: str, type: str, type_id: int, hash: str, ...)
    # Checking minimal required fields from code reading or simple mock
    # For simplicity, relying on standard Node creation.
    # If Node requires many args, I might need to make a valid one.
    # Looking at filesystem.py imports: knowgraph.domain.models.node.Node
    # I'll create a simple dummy if possible or use concrete class.

    # Let's create a minimal Node object using proper initialization if possible
    # or mock it. But write_node_json calls node.to_dict().
    # read_node_json calls Node.from_dict().
    # So using real object is better.

    # Create a minimal Node object
    node = Node(
        id=uid,
        hash="a" * 40,
        title="Test Node",
        content="Some content",
        path="file1.md",
        type="text",
        token_count=10,
        created_at=1234567890,
    )

    # Write
    write_node_json(node, store_path)
    assert (store_path / "nodes" / f"{uid}.json").exists()

    # Read
    read_node = read_node_json(uid, store_path)
    assert read_node is not None
    assert read_node.id == uid
    assert read_node.title == "Test Node"

    # List
    nodes = list_all_nodes(store_path)
    assert uid in nodes

    # Delete
    assert delete_node_json(uid, store_path) is True
    assert not (store_path / "nodes" / f"{uid}.json").exists()
    assert delete_node_json(uid, store_path) is False


def test_edge_io(store_path):
    """Test write, append, read for edges."""
    edge1 = Edge(
        source=uuid4(),
        target=uuid4(),
        type="semantic",
        score=1.0,
        created_at=1234567890,
        metadata={"desc": "A to B"},
    )
    edge2 = Edge(
        source=uuid4(),
        target=uuid4(),
        type="reference",
        score=0.5,
        created_at=1234567890,
        metadata={"desc": "C to D"},
    )

    # Append
    append_edge_jsonl(edge1, store_path)
    append_edge_jsonl(edge2, store_path)

    file_path = store_path / "edges" / "edges.jsonl"
    assert file_path.exists()

    # Read
    edges = read_all_edges(store_path)
    assert len(edges) == 2
    assert edges[0].metadata["desc"] == "A to B"
    assert edges[1].metadata["desc"] == "C to D"

    # Write All (Overwrite)
    new_edges = [edge1]
    write_all_edges(new_edges, store_path)
    edges = read_all_edges(store_path)
    assert len(edges) == 1
    assert edges[0].metadata["desc"] == "A to B"


def test_missing_files(store_path):
    assert read_node_json(uuid4(), store_path) is None
    assert delete_node_json(uuid4(), store_path) is False
    assert read_all_edges(store_path) == []

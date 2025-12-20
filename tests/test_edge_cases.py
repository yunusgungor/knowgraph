"""Tests for edge cases: empty data, invalid inputs, boundary conditions."""

import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.storage.filesystem import (
    clear_node_cache,
    read_node_json,
    write_node_json,
)
from knowgraph.infrastructure.storage.manifest import Manifest, read_manifest, write_manifest
from knowgraph.shared.exceptions import StorageError

# ====================
# Node Edge Cases
# ====================


def test_node_with_minimal_content():
    """Test node creation with minimal content."""
    node = Node(
        id=uuid4(),
        hash="a" * 40,
        title="Minimal Content Node",
        content="a",  # Minimal non-empty content
        path="test.md",
        type="semantic",
        token_count=1,
        created_at=1000000,
        metadata={},
    )
    assert len(node.content) == 1
    assert node.token_count == 1


def test_node_with_very_long_content():
    """Test node with very long content."""
    long_content = "a" * 10_000  # 10KB of content
    node = Node(
        id=uuid4(),
        hash="b" * 40,
        title="Long Content",
        content=long_content,
        path="large.md",
        type="semantic",
        token_count=2000,  # Within MAX_NODE_TOKEN_COUNT
        created_at=1000000,
        metadata={},
    )
    assert len(node.content) == 10_000


def test_node_with_special_characters():
    """Test node with unicode and special characters."""
    special_content = "Hello 世界 🌍 \n\t\r Special: <>\"'&"
    node = Node(
        id=uuid4(),
        hash="c" * 40,
        title="Special Chars",
        content=special_content,
        path="special.md",
        type="semantic",
        token_count=20,
        created_at=1000000,
        metadata={"emoji": "🎉", "unicode": "日本語"},
    )
    assert "世界" in node.content
    assert node.metadata["emoji"] == "🎉"


def test_node_with_invalid_hash_length():
    """Test that node creation fails with invalid hash length."""
    with pytest.raises(ValueError, match="Hash must be 40 characters"):
        Node(
            id=uuid4(),
            hash="short",  # Invalid: not 40 chars
            title="Invalid Hash",
            content="Content",
            path="test.md",
            type="semantic",
            token_count=10,
            created_at=1000000,
            metadata={},
        )


def test_node_with_one_token():
    """Test node with minimal token count."""
    node = Node(
        id=uuid4(),
        hash="d" * 40,
        title="One Token",
        content="a",
        path="minimal.md",
        type="semantic",
        token_count=1,  # Minimum valid
        created_at=1000000,
        metadata={},
    )
    assert node.token_count == 1


def test_node_with_negative_timestamp():
    """Test node with negative timestamp (before epoch)."""
    node = Node(
        id=uuid4(),
        hash="e" * 40,
        title="Old Node",
        content="Content",
        path="old.md",
        type="semantic",
        token_count=10,
        created_at=-1000,  # Negative timestamp
        metadata={},
    )
    assert node.created_at == -1000


# ====================
# Edge Edge Cases
# ====================


def test_edge_self_loop():
    """Test that self-loops are properly rejected."""
    node_id = uuid4()
    with pytest.raises(ValueError, match="Self-loops are not allowed"):
        Edge(
            source=node_id,
            target=node_id,  # Self-loop should be rejected
            type="semantic",
            score=1.0,
            created_at=1000000,
            metadata={},
        )


def test_edge_with_empty_metadata():
    """Test edge with empty metadata dict."""
    edge = Edge(
        source=uuid4(), target=uuid4(), type="semantic", score=0.5, created_at=1000000, metadata={}
    )
    assert edge.metadata == {}


# ====================
# File System Edge Cases
# ====================


def test_write_node_to_nonexistent_directory():
    """Test that write_node_json creates parent directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        deep_path = Path(tmpdir) / "a" / "b" / "c" / "graph"
        node = Node(
            id=uuid4(),
            hash="f" * 40,
            title="Deep Node",
            content="Content",
            path="test.md",
            type="semantic",
            token_count=10,
            created_at=1000000,
            metadata={},
        )

        # Should create directories and write successfully
        write_node_json(node, deep_path)

        # Verify file exists
        node_file = deep_path / "nodes" / f"{node.id}.json"
        assert node_file.exists()


def test_read_nonexistent_node():
    """Test reading node that doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir)
        result = read_node_json(uuid4(), graph_path)
        assert result is None


def test_read_node_from_corrupted_json():
    """Test reading node from malformed JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir)
        nodes_dir = graph_path / "nodes"
        nodes_dir.mkdir(parents=True)

        # Write corrupted JSON
        node_id = uuid4()
        corrupted_file = nodes_dir / f"{node_id}.json"
        corrupted_file.write_text("{invalid json content")

        # Should handle gracefully
        with pytest.raises(StorageError):
            read_node_json(node_id, graph_path)


def test_write_node_with_empty_id():
    """Test that node with nil UUID still works."""
    from uuid import UUID

    nil_uuid = UUID("00000000-0000-0000-0000-000000000000")
    node = Node(
        id=nil_uuid,
        hash="g" * 40,
        title="Nil UUID",
        content="Content",
        path="test.md",
        type="semantic",
        token_count=10,
        created_at=1000000,
        metadata={},
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        write_node_json(node, Path(tmpdir))

        # Verify can read back
        read_node = read_node_json(nil_uuid, Path(tmpdir))
        assert read_node is not None
        assert read_node.id == nil_uuid


def test_cache_with_zero_max_size():
    """Test node cache behavior at boundaries."""
    clear_node_cache()

    # Cache should still work even with small sizes
    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir)

        node = Node(
            id=uuid4(),
            hash="h" * 40,
            title="Cached",
            content="Content",
            path="test.md",
            type="semantic",
            token_count=10,
            created_at=1000000,
            metadata={},
        )

        write_node_json(node, graph_path)

        # Read with cache
        result = read_node_json(node.id, graph_path, use_cache=True)
        assert result is not None
        assert result.id == node.id


# ====================
# Manifest Edge Cases
# ====================


def test_manifest_with_empty_file_hashes():
    """Test manifest with no files indexed."""
    manifest = Manifest.create_new(edges_filename="edges.jsonl", sparse_index_filename="index.json")
    assert manifest.file_hashes == {}
    assert manifest.node_count == 0
    assert manifest.edge_count == 0


def test_manifest_with_zero_counts():
    """Test manifest with all zero counts."""
    manifest = Manifest(
        version="1.0.0",
        node_count=0,
        edge_count=0,
        file_hashes={},
        edges_filename="edges.jsonl",
        sparse_index_filename="index.json",
        semantic_edge_count=0,
    )
    assert manifest.node_count == 0
    assert manifest.edge_count == 0
    assert manifest.semantic_edge_count == 0


def test_manifest_read_from_empty_directory():
    """Test reading manifest from directory without manifest.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = read_manifest(Path(tmpdir))
        assert result is None


def test_manifest_with_very_large_counts():
    """Test manifest with extremely large counts."""
    manifest = Manifest(
        version="1.0.0",
        node_count=2**31 - 1,  # Max int32
        edge_count=2**31 - 1,
        file_hashes={"file.md": "a" * 40},
        edges_filename="edges.jsonl",
        sparse_index_filename="index.json",
    )
    assert manifest.node_count == 2**31 - 1


def test_manifest_serialization_deserialization():
    """Test manifest survives round-trip serialization."""
    original = Manifest(
        version="1.0.0",
        created_at=1000000,
        updated_at=1000001,
        node_count=100,
        edge_count=200,
        file_hashes={"test.md": "a" * 40},
        edges_filename="edges.jsonl",
        sparse_index_filename="index.json",
        semantic_edge_count=50,
    )

    # Serialize to dict
    data = original.to_dict()

    # Deserialize back
    restored = Manifest.from_dict(data)

    assert restored.version == original.version
    assert restored.node_count == original.node_count
    assert restored.edge_count == original.edge_count
    assert restored.semantic_edge_count == original.semantic_edge_count


# ====================
# String Edge Cases
# ====================


def test_node_with_null_bytes():
    """Test node content with null bytes."""
    content_with_nulls = "Hello\x00World"
    node = Node(
        id=uuid4(),
        hash="n" * 40,
        title="Null Bytes",
        content=content_with_nulls,
        path="test.md",
        type="semantic",
        token_count=10,
        created_at=1000000,
        metadata={},
    )
    assert "\x00" in node.content


def test_node_with_only_whitespace():
    """Test node with only whitespace content."""
    node = Node(
        id=uuid4(),
        hash="o" * 40,
        title="Whitespace",
        content="   \n\t\r   ",
        path="test.md",
        type="semantic",
        token_count=1,  # Must be positive
        created_at=1000000,
        metadata={},
    )
    assert node.content.strip() == ""


def test_node_with_very_long_path():
    """Test node with extremely long file path."""
    long_path = "a/" * 100 + "file.md"  # Very deep path
    node = Node(
        id=uuid4(),
        hash="p" * 40,
        title="Deep Path",
        content="Content",
        path=long_path,
        type="semantic",
        token_count=10,
        created_at=1000000,
        metadata={},
    )
    assert len(node.path) > 200


# ====================
# Metadata Edge Cases
# ====================


def test_node_with_empty_metadata():
    """Test node with empty metadata dict."""
    node = Node(
        id=uuid4(),
        hash="q" * 40,
        title="No Metadata",
        content="Content",
        path="test.md",
        type="semantic",
        token_count=10,
        created_at=1000000,
        metadata={},
    )
    assert node.metadata == {}


def test_node_with_nested_metadata():
    """Test node with deeply nested metadata."""
    nested_meta = {"level1": {"level2": {"level3": {"value": "deep"}}}}
    node = Node(
        id=uuid4(),
        hash="r" * 40,
        title="Nested Meta",
        content="Content",
        path="test.md",
        type="semantic",
        token_count=10,
        created_at=1000000,
        metadata=nested_meta,
    )
    assert node.metadata["level1"]["level2"]["level3"]["value"] == "deep"


def test_node_with_list_in_metadata():
    """Test node with list values in metadata."""
    node = Node(
        id=uuid4(),
        hash="s" * 40,
        title="List Meta",
        content="Content",
        path="test.md",
        type="semantic",
        token_count=10,
        created_at=1000000,
        metadata={"tags": ["python", "graph", "test"], "counts": [1, 2, 3]},
    )
    assert len(node.metadata["tags"]) == 3
    assert node.metadata["counts"][2] == 3


# ====================
# Boundary Value Tests
# ====================


def test_node_with_large_token_count():
    """Test node with large token count within limits."""
    from knowgraph.config import MAX_NODE_TOKEN_COUNT

    node = Node(
        id=uuid4(),
        hash="t" * 40,
        title="Large Tokens",
        content="Content" * 1000,
        path="test.md",
        type="semantic",
        token_count=MAX_NODE_TOKEN_COUNT - 1,  # Just under max
        created_at=1000000,
        metadata={},
    )
    assert node.token_count == MAX_NODE_TOKEN_COUNT - 1


def test_manifest_write_read_cycle():
    """Test manifest survives write-read cycle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir)

        original = Manifest.create_new(
            edges_filename="edges.jsonl", sparse_index_filename="index.json"
        )
        original.node_count = 42
        original.edge_count = 84

        # Write
        write_manifest(original, graph_path)

        # Read back
        restored = read_manifest(graph_path)

        assert restored is not None
        assert restored.node_count == 42
        assert restored.edge_count == 84


def test_multiple_concurrent_cache_clears():
    """Test that multiple cache clears don't cause issues."""
    clear_node_cache()
    clear_node_cache()
    clear_node_cache()

    # Should not raise any errors


def test_node_path_with_special_characters():
    """Test node with special characters in path."""
    special_path = "test/file (1) [copy].md"
    node = Node(
        id=uuid4(),
        hash="u" * 40,
        title="Special Path",
        content="Content",
        path=special_path,
        type="semantic",
        token_count=10,
        created_at=1000000,
        metadata={},
    )
    assert "(" in node.path
    assert "[" in node.path

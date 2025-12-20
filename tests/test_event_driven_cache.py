"""Tests for event-driven cache refresh on graph updates."""

import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.storage.filesystem import write_node_json
from knowgraph.infrastructure.storage.manifest import Manifest, write_manifest
from knowgraph.shared.cache_versioning import (
    CacheVersionManager,
    get_cached,
    invalidate_all_caches,
    set_cached,
)


def create_test_node(content: str = "Test content", node_id: UUID | None = None) -> Node:
    """Helper to create a valid test node."""
    if node_id is None:
        node_id = uuid4()

    return Node(
        id=node_id,
        hash="a" * 40,
        title="Test Node",
        content=content,
        path="test/file.md",
        type="semantic",
        token_count=10,
        created_at=int(time.time()),
        metadata={"source": "test"}
    )


@pytest.fixture
def temp_graph_store():
    """Create temporary graph store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir)

        # Create minimal manifest
        manifest = Manifest.create_new(
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.json"
        )
        write_manifest(manifest, graph_path)

        yield graph_path


def test_cache_invalidation_on_node_write(temp_graph_store):
    """Test that writing a node invalidates all caches."""
    manager = CacheVersionManager(temp_graph_store)

    # Set some cached values
    set_cached("key1", "value1", ttl=60, graph_store_path=manager.graph_store_path)
    set_cached("key2", "value2", ttl=60, graph_store_path=manager.graph_store_path)

    assert get_cached("key1") == "value1"
    assert get_cached("key2") == "value2"

    # Write a node - this should trigger cache invalidation
    node = create_test_node(content="Test content")

    # Small delay to ensure timestamp changes
    time.sleep(0.1)
    write_node_json(node, temp_graph_store)

    # Force manager to check for updates
    manager._version_last_checked = 0

    # Cache should be invalidated (version mismatch)
    assert get_cached("key1") is None
    assert get_cached("key2") is None


def test_cache_invalidation_on_manifest_write(temp_graph_store):
    """Test that writing manifest invalidates all caches."""
    manager = CacheVersionManager(temp_graph_store)

    # Set cached values
    set_cached("key1", "value1", ttl=60, graph_store_path=manager.graph_store_path)
    set_cached("key2", "value2", ttl=60, graph_store_path=manager.graph_store_path)

    assert get_cached("key1") == "value1"
    assert get_cached("key2") == "value2"

    # Update manifest - this should trigger cache invalidation
    manifest = Manifest.create_new(
        edges_filename="edges.jsonl",
        sparse_index_filename="sparse_index.json"
    )
    manifest.node_count = 100
    manifest.edge_count = 200

    # Small delay to ensure timestamp changes
    time.sleep(0.1)
    write_manifest(manifest, temp_graph_store)

    # Force manager to check for updates
    manager._version_last_checked = 0

    # Cache should be invalidated
    assert get_cached("key1") is None
    assert get_cached("key2") is None


def test_multiple_writes_invalidate_caches(temp_graph_store):
    """Test that multiple writes correctly invalidate caches."""
    manager = CacheVersionManager(temp_graph_store)

    # Set initial cache
    set_cached("data", "v1", ttl=60, graph_store_path=manager.graph_store_path)
    assert get_cached("data") == "v1"

    # First write
    node1 = create_test_node(content="Content 1")
    time.sleep(0.1)
    write_node_json(node1, temp_graph_store)
    manager._version_last_checked = 0

    # Cache invalidated
    assert get_cached("data") is None

    # Set new cache value
    set_cached("data", "v2", ttl=60, graph_store_path=manager.graph_store_path)
    assert get_cached("data") == "v2"

    # Second write
    node2 = create_test_node(content="Content 2")
    time.sleep(0.1)
    write_node_json(node2, temp_graph_store)
    manager._version_last_checked = 0

    # Cache invalidated again
    assert get_cached("data") is None


def test_cache_survives_without_writes(temp_graph_store):
    """Test that cache remains valid without graph updates."""
    manager = CacheVersionManager(temp_graph_store)

    # Set cached value
    set_cached("persistent", "value", ttl=60, graph_store_path=manager.graph_store_path)
    assert get_cached("persistent") == "value"

    # Wait a bit
    time.sleep(0.2)

    # Cache should still be valid (no writes happened)
    assert get_cached("persistent") == "value"

    # Check again
    assert get_cached("persistent") == "value"


def test_manual_invalidation_still_works(temp_graph_store):
    """Test that manual invalidate_all_caches() still works."""
    manager = CacheVersionManager(temp_graph_store)

    # Set cached values
    set_cached("key1", "value1", ttl=60, graph_store_path=manager.graph_store_path)
    set_cached("key2", "value2", ttl=60, graph_store_path=manager.graph_store_path)

    assert get_cached("key1") == "value1"
    assert get_cached("key2") == "value2"

    # Manual invalidation (without writing to disk)
    invalidate_all_caches()
    manager._version_last_checked = 0

    # Cache should be cleared
    assert get_cached("key1") is None
    assert get_cached("key2") is None


def test_cache_invalidation_with_multiple_managers(temp_graph_store):
    """Test that cache invalidation affects all managers."""
    manager1 = CacheVersionManager(temp_graph_store)
    manager2 = CacheVersionManager(temp_graph_store)

    # Set cache via manager1
    set_cached("shared", "data", ttl=60, graph_store_path=manager1.graph_store_path)

    # Both managers should see the value
    assert get_cached("shared") == "data"
    assert get_cached("shared") == "data"

    # Write node
    node = create_test_node(content="Test")
    time.sleep(0.1)
    write_node_json(node, temp_graph_store)

    # Force both managers to check
    manager1._version_last_checked = 0
    manager2._version_last_checked = 0

    # Both managers should see invalidated cache
    assert get_cached("shared") is None
    assert get_cached("shared") is None


def test_rapid_writes_invalidate_correctly(temp_graph_store):
    """Test that rapid successive writes all trigger invalidation."""
    manager = CacheVersionManager(temp_graph_store)

    # Set initial cache
    set_cached("counter", 0, ttl=60, graph_store_path=manager.graph_store_path)
    assert get_cached("counter") == 0

    # Perform rapid writes
    for i in range(5):
        node = create_test_node(content=f"Content {i}")
        time.sleep(0.05)  # Small delay
        write_node_json(node, temp_graph_store)

        # Force version check
        manager._version_last_checked = 0

        # Cache should be invalidated
        assert get_cached("counter") is None

        # Set new value
        set_cached("counter", i + 1, ttl=60, graph_store_path=manager.graph_store_path)

    # Final value should be cached
    assert get_cached("counter") == 5

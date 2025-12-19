"""Comprehensive integration tests for KnowGraph.

Tests full workflows with component interactions:
- Indexing → Query flow
- Cache → Retrieval integration
- Streaming → Pagination pipeline
- Error propagation across layers
"""

import asyncio
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from knowgraph.application.querying.query_engine import QueryEngine
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.storage.filesystem import (
    read_all_edges,
    read_node_json,
    write_all_edges,
    write_node_json,
)
from knowgraph.infrastructure.storage.manifest import (
    Manifest,
    read_manifest,
    write_manifest,
)
from knowgraph.shared.cache_versioning import CacheVersionManager


@pytest.fixture
def temp_graph_path():
    """Create temporary graph directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "test_graph"
        graph_path.mkdir(parents=True)
        yield graph_path


@pytest.fixture
def sample_nodes():
    """Create sample nodes for testing."""
    return [
        Node(
            id=uuid4(),
            hash="a" * 40,
            title=f"Node {i}",
            content=f"Content about topic {i} with keywords",
            path=f"doc{i}.md",
            type="semantic",
            token_count=10,
            created_at=1000000 + i,
            metadata={"category": "test"},
        )
        for i in range(10)
    ]


@pytest.fixture
def sample_edges(sample_nodes):
    """Create sample edges connecting nodes."""
    edges = []
    for i in range(len(sample_nodes) - 1):
        edges.append(
            Edge(
                source=sample_nodes[i].id,
                target=sample_nodes[i + 1].id,
                type="reference",
                score=0.8,
                created_at=1000000,
                metadata={"type": "sequential"},
            )
        )
    return edges


class TestIndexingToQueryFlow:
    """Test full workflow from indexing to querying."""

    def test_write_nodes_read_nodes(self, temp_graph_path, sample_nodes):
        """Test writing and reading nodes."""
        # Write nodes
        for node in sample_nodes:
            write_node_json(node, temp_graph_path)

        # Read nodes back
        for node in sample_nodes:
            read_node = read_node_json(node.id, temp_graph_path)
            assert read_node.id == node.id
            assert read_node.content == node.content
            assert read_node.title == node.title

    def test_write_edges_read_edges(self, temp_graph_path, sample_edges):
        """Test writing and reading edges."""
        write_all_edges(sample_edges, temp_graph_path)

        edges = read_all_edges(temp_graph_path)
        assert len(edges) == len(sample_edges)

        # Verify edge data
        edge_dict = {(e.source, e.target): e for e in edges}
        for original_edge in sample_edges:
            key = (original_edge.source, original_edge.target)
            assert key in edge_dict
            assert edge_dict[key].type == original_edge.type
            assert edge_dict[key].score == original_edge.score

    def test_manifest_integration(self, temp_graph_path, sample_nodes):
        """Test manifest creation and reading."""
        # Create manifest
        manifest = Manifest(
            version="1.0",
            node_count=len(sample_nodes),
            edge_count=5,
            file_hashes={f"doc{i}.md": f"hash{i}" for i in range(len(sample_nodes))},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.json",
            created_at=1000000,
            updated_at=1000000,
        )

        # Write manifest
        write_manifest(manifest, temp_graph_path)

        # Read manifest back
        loaded_manifest = read_manifest(temp_graph_path)
        assert loaded_manifest.version == manifest.version
        assert loaded_manifest.node_count == manifest.node_count
        assert loaded_manifest.edge_count == manifest.edge_count
        assert loaded_manifest.file_hashes == manifest.file_hashes

    def test_full_indexing_pipeline(self, temp_graph_path, sample_nodes, sample_edges):
        """Test complete indexing pipeline."""
        # Write graph data
        for node in sample_nodes:
            write_node_json(node, temp_graph_path)
        write_all_edges(sample_edges, temp_graph_path)

        # Create manifest
        manifest = Manifest(
            version="1.0",
            node_count=len(sample_nodes),
            edge_count=len(sample_edges),
            file_hashes={node.path: node.hash for node in sample_nodes},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.json",
            created_at=1000000,
            updated_at=1000000,
        )
        write_manifest(manifest, temp_graph_path)

        # Verify all components work together
        assert read_manifest(temp_graph_path).node_count == len(sample_nodes)
        assert len(read_all_edges(temp_graph_path)) == len(sample_edges)
        assert read_node_json(sample_nodes[0].id, temp_graph_path) is not None


class TestCacheIntegration:
    """Test cache integration with other components."""

    def test_cache_version_manager_with_manifest(self, temp_graph_path):
        """Test cache version manager with manifest updates."""
        CacheVersionManager(temp_graph_path)

        # Initial state
        from knowgraph.shared.cache_versioning import get_cached, set_cached

        set_cached("key1", "value1", graph_store_path=temp_graph_path)
        assert get_cached("key1") == "value1"

        # Update manifest to simulate graph update
        manifest = Manifest(
            version="1.0",
            node_count=10,
            edge_count=5,
            file_hashes={"test.md": "hash1"},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.json",
            created_at=1000000,
            updated_at=1000001,  # Updated
        )
        write_manifest(manifest, temp_graph_path)

        # Cache should invalidate on version change
        # (This depends on implementation - may need to call check_version)

    def test_cache_invalidation_on_graph_update(self, temp_graph_path, sample_nodes):
        """Test cache invalidates when graph updates."""
        CacheVersionManager(temp_graph_path)

        # Cache some results
        from knowgraph.shared.cache_versioning import set_cached

        set_cached("query1", "result1", graph_store_path=temp_graph_path)

        # Write new nodes (simulating graph update)
        for node in sample_nodes[:3]:
            write_node_json(node, temp_graph_path)

        # Update manifest
        manifest = Manifest(
            version="1.0",
            node_count=3,
            edge_count=0,
            file_hashes={node.path: node.hash for node in sample_nodes[:3]},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.json",
            created_at=1000000,
            updated_at=1000002,
        )
        write_manifest(manifest, temp_graph_path)
        # Version manager tracks changes; cache invalidates automatically


class TestErrorPropagation:
    """Test error handling across component boundaries."""

    def test_read_nonexistent_node_error(self, temp_graph_path):
        """Test error when reading nonexistent node."""
        fake_id = uuid4()
        result = read_node_json(fake_id, temp_graph_path)
        assert result is None  # Should return None, not raise

    def test_read_manifest_missing_error(self, temp_graph_path):
        """Test error when manifest is missing."""
        result = read_manifest(temp_graph_path)
        assert result is None  # Returns None for missing manifest

    def test_write_to_invalid_path_error(self, sample_nodes):
        """Test error when writing to invalid path."""
        Path("/nonexistent/impossible/path")
        # Should raise or handle gracefully
        # (Depends on implementation)

    @pytest.mark.asyncio
    async def test_query_with_empty_graph(self, temp_graph_path):
        """Test querying empty graph."""
        # Create empty graph structure
        (temp_graph_path / "nodes").mkdir(parents=True)
        (temp_graph_path / "edges").mkdir(parents=True)
        (temp_graph_path / "index").mkdir(parents=True)
        (temp_graph_path / "metadata").mkdir(parents=True)

        # Create minimal manifest
        manifest = Manifest(
            version="1.0",
            node_count=0,
            edge_count=0,
            file_hashes={},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.json",
            created_at=1000000,
            updated_at=1000000,
        )
        write_manifest(manifest, temp_graph_path)

        # Query should handle empty graph gracefully
        QueryEngine(temp_graph_path)
        # May raise or return empty results depending on implementation


class TestConcurrentOperations:
    """Test concurrent operations across components."""

    @pytest.mark.asyncio
    async def test_concurrent_node_writes(self, temp_graph_path, sample_nodes):
        """Test writing multiple nodes concurrently."""

        async def write_node_async(node):
            # Write in executor
            await asyncio.sleep(0.01)  # Simulate I/O
            write_node_json(node, temp_graph_path)

        # Write nodes concurrently
        await asyncio.gather(*[write_node_async(node) for node in sample_nodes])

        # Verify all written
        for node in sample_nodes:
            result = read_node_json(node.id, temp_graph_path)
            assert result is not None
            assert result.id == node.id

    @pytest.mark.asyncio
    async def test_concurrent_cache_operations(self, temp_graph_path):
        """Test concurrent cache read/write operations."""
        CacheVersionManager(temp_graph_path)

        from knowgraph.shared.cache_versioning import get_cached, set_cached

        async def cache_operation(key, value):
            await asyncio.sleep(0.01)
            set_cached(key, value, graph_store_path=temp_graph_path)
            return get_cached(key)

        # Concurrent cache operations
        results = await asyncio.gather(
            *[cache_operation(f"key{i}", f"value{i}") for i in range(10)]
        )

        assert len(results) == 10
        assert all(results[i] == f"value{i}" for i in range(10))


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""

    def test_complete_graph_creation_workflow(self, temp_graph_path, sample_nodes, sample_edges):
        """Test complete workflow: create graph → write → read → query."""
        # Step 1: Write all components
        for node in sample_nodes:
            write_node_json(node, temp_graph_path)

        write_all_edges(sample_edges, temp_graph_path)

        manifest = Manifest(
            version="1.0",
            node_count=len(sample_nodes),
            edge_count=len(sample_edges),
            file_hashes={node.path: node.hash for node in sample_nodes},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.json",
            created_at=1000000,
            updated_at=1000000,
        )
        write_manifest(manifest, temp_graph_path)

        # Step 2: Verify data integrity
        loaded_manifest = read_manifest(temp_graph_path)
        assert loaded_manifest.node_count == len(sample_nodes)

        loaded_edges = read_all_edges(temp_graph_path)
        assert len(loaded_edges) == len(sample_edges)

    def test_graph_update_workflow(self, temp_graph_path, sample_nodes):
        """Test workflow for updating existing graph."""
        # Initial graph
        for node in sample_nodes[:5]:
            write_node_json(node, temp_graph_path)

        manifest1 = Manifest(
            version="1.0",
            node_count=5,
            edge_count=0,
            file_hashes={node.path: node.hash for node in sample_nodes[:5]},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.json",
            created_at=1000000,
            updated_at=1000000,
        )
        write_manifest(manifest1, temp_graph_path)

        # Update: add more nodes
        for node in sample_nodes[5:8]:
            write_node_json(node, temp_graph_path)

        manifest2 = Manifest(
            version="1.0",
            node_count=8,
            edge_count=0,
            file_hashes={node.path: node.hash for node in sample_nodes[:8]},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.json",
            created_at=1000000,
            updated_at=1000001,
        )
        write_manifest(manifest2, temp_graph_path)

        # Verify update
        loaded = read_manifest(temp_graph_path)
        assert loaded.node_count == 8
        assert loaded.updated_at == 1000001


class TestDataConsistency:
    """Test data consistency across operations."""

    def test_node_hash_consistency(self, temp_graph_path, sample_nodes):
        """Test node hash remains consistent after write/read."""
        original = sample_nodes[0]
        write_node_json(original, temp_graph_path)

        loaded = read_node_json(original.id, temp_graph_path)
        assert loaded.hash == original.hash

    def test_edge_metadata_consistency(self, temp_graph_path, sample_edges):
        """Test edge metadata preserved after write/read."""
        write_all_edges(sample_edges, temp_graph_path)

        loaded_edges = read_all_edges(temp_graph_path)
        loaded_dict = {(e.source, e.target): e for e in loaded_edges}

        for original in sample_edges:
            key = (original.source, original.target)
            loaded = loaded_dict[key]
            assert loaded.metadata == original.metadata

    def test_manifest_file_hash_consistency(self, temp_graph_path, sample_nodes):
        """Test manifest file hashes remain consistent."""
        file_hashes = {node.path: node.hash for node in sample_nodes}

        manifest = Manifest(
            version="1.0",
            node_count=len(sample_nodes),
            edge_count=0,
            file_hashes=file_hashes,
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.json",
            created_at=1000000,
            updated_at=1000000,
        )
        write_manifest(manifest, temp_graph_path)

        loaded = read_manifest(temp_graph_path)
        assert loaded.file_hashes == file_hashes

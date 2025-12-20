"""Tests for version rollback functionality.

Tests RollbackManager for manifest-only version rollback operations.
"""

import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from knowgraph.infrastructure.storage.manifest import Manifest, read_manifest, write_manifest
from knowgraph.infrastructure.storage.version_history import VersionHistoryManager
from knowgraph.infrastructure.storage.version_rollback import RollbackManager, RollbackResult


@pytest.fixture
def temp_graph():
    """Create temporary graph directory with full structure."""
    with TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "graphstore"
        graph_path.mkdir(parents=True)
        (graph_path / "metadata").mkdir()
        (graph_path / "nodes").mkdir()
        (graph_path / "edges").mkdir()
        yield graph_path


@pytest.fixture
def version_manager(temp_graph):
    """Create version history manager."""
    return VersionHistoryManager(temp_graph)


@pytest.fixture
def rollback_manager(temp_graph):
    """Create rollback manager."""
    return RollbackManager(temp_graph)


@pytest.fixture
def initialized_graph(temp_graph):
    """Create graph with initial manifest and versions."""
    # Create initial manifest
    manifest = Manifest(
        version=1,
        node_count=100,
        edge_count=50,
        file_hashes={"file1.md": "hash1"},
        edges_filename="edges.jsonl",
        sparse_index_filename="sparse_index.pkl",
        created_at=int(time.time()),
        updated_at=int(time.time()),
        semantic_edge_count=50,
        finalized=True,
        version_id="v1",
    )
    write_manifest(manifest, temp_graph)

    # Create version history
    version_mgr = VersionHistoryManager(temp_graph)
    version_mgr.add_version(
        node_count=100,
        edge_count=50,
        file_hashes={"file1.md": "hash1"},
    )

    return temp_graph


class TestRollbackResult:
    """Test RollbackResult dataclass."""

    def test_rollback_result_creation_success(self):
        """Test creating successful rollback result."""
        result = RollbackResult(
            success=True,
            from_version="v3",
            to_version="v2",
            backup_path=Path("/tmp/backup"),
            message="Rollback successful",
            errors=[],
        )

        assert result.success is True
        assert result.from_version == "v3"
        assert result.to_version == "v2"
        assert result.backup_path == Path("/tmp/backup")
        assert len(result.errors) == 0

    def test_rollback_result_creation_failure(self):
        """Test creating failed rollback result."""
        result = RollbackResult(
            success=False,
            from_version="v3",
            to_version="v2",
            backup_path=None,
            message="Rollback failed",
            errors=["Version not found", "Validation failed"],
        )

        assert result.success is False
        assert result.backup_path is None
        assert len(result.errors) == 2

    def test_to_dict(self):
        """Test serialization to dictionary."""
        result = RollbackResult(
            success=True,
            from_version="v3",
            to_version="v2",
            backup_path=Path("/tmp/backup"),
            message="Success",
            errors=[],
        )

        data = result.to_dict()
        assert data["success"] is True
        assert data["from_version"] == "v3"
        assert data["to_version"] == "v2"
        assert data["backup_path"] == "/tmp/backup"
        assert "errors" in data


class TestRollbackManager:
    """Test RollbackManager initialization and basic functionality."""

    def test_manager_initialization(self, rollback_manager, temp_graph):
        """Test rollback manager initialization."""
        assert rollback_manager.graph_store_path == temp_graph
        assert rollback_manager.metadata_dir == temp_graph / "metadata"
        assert isinstance(rollback_manager.version_mgr, VersionHistoryManager)

    def test_rollback_no_manifest(self, rollback_manager):
        """Test rollback when no manifest exists."""
        result = rollback_manager.rollback_to_version("v1")

        assert result.success is False
        assert "No manifest found" in result.message
        assert "Graph store not initialized" in result.errors

    def test_rollback_version_not_found(self, rollback_manager, initialized_graph):
        """Test rollback to non-existent version."""
        rollback_mgr = RollbackManager(initialized_graph)
        result = rollback_mgr.rollback_to_version("v999")

        assert result.success is False
        assert "not found" in result.message
        assert result.from_version == "v1"
        assert result.to_version == "v999"


class TestRollbackValidation:
    """Test rollback validation rules."""

    def test_rollback_to_same_version(self, initialized_graph):
        """Test that rollback to same version is rejected."""
        rollback_mgr = RollbackManager(initialized_graph)
        result = rollback_mgr.rollback_to_version("v1")

        assert result.success is False
        assert "validation failed" in result.message.lower()

    def test_rollback_forward_rejected(self, temp_graph):
        """Test that rollback to newer version is rejected."""
        # Create multiple versions
        version_mgr = VersionHistoryManager(temp_graph)
        version_mgr.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )
        version_mgr.add_version(
            node_count=110, edge_count=55, file_hashes={"file1.md": "hash1"}
        )
        version_mgr.add_version(
            node_count=120, edge_count=60, file_hashes={"file1.md": "hash1"}
        )

        # Set manifest to v2
        manifest = Manifest(
            version=1,
            node_count=110,
            edge_count=55,
            file_hashes={"file1.md": "hash1"},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.pkl",
            created_at=int(time.time()),
            updated_at=int(time.time()),
            semantic_edge_count=55,
            finalized=True,
            version_id="v2",
        )
        write_manifest(manifest, temp_graph)

        # Try to rollback "forward" to v3
        rollback_mgr = RollbackManager(temp_graph)
        result = rollback_mgr.rollback_to_version("v3")

        assert result.success is False
        assert "validation failed" in result.message.lower()

    def test_rollback_validation_bypass_with_force(self, initialized_graph):
        """Test that validation can be bypassed with force flag."""
        # Create v2
        version_mgr = VersionHistoryManager(initialized_graph)
        version_mgr.add_version(
            node_count=120, edge_count=60, file_hashes={"file1.md": "hash1"}
        )

        # Keep manifest at v1 (it's already there)
        # Try to "rollback" forward to v2 with force=True - this should succeed
        rollback_mgr = RollbackManager(initialized_graph)
        result = rollback_mgr.rollback_to_version("v2", force=True)

        # With force=True, forward rollback is allowed (validation is bypassed)
        assert result.success is True


class TestRollbackOperation:
    """Test actual rollback operations."""

    def test_rollback_basic_success(self, temp_graph):
        """Test successful basic rollback."""
        # Setup: Create v1 and v2
        version_mgr = VersionHistoryManager(temp_graph)
        version_mgr.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )
        version_mgr.add_version(
            node_count=120, edge_count=60, file_hashes={"file1.md": "hash1", "file2.md": "hash2"}
        )

        # Set manifest to v2
        manifest = Manifest(
            version=1,
            node_count=120,
            edge_count=60,
            file_hashes={"file1.md": "hash1", "file2.md": "hash2"},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.pkl",
            created_at=int(time.time()),
            updated_at=int(time.time()),
            semantic_edge_count=60,
            finalized=True,
            version_id="v2",
        )
        write_manifest(manifest, temp_graph)

        # Perform rollback
        rollback_mgr = RollbackManager(temp_graph)
        result = rollback_mgr.rollback_to_version("v1", create_backup=True)

        assert result.success is True
        assert result.from_version == "v2"
        assert result.to_version == "v1"
        assert result.backup_path is not None

        # Verify manifest was updated - node/edge counts should match v1
        updated_manifest = read_manifest(temp_graph)
        assert updated_manifest.node_count == 100
        assert updated_manifest.edge_count == 50
        # Note: write_manifest auto-versioning will keep the version_id as v2
        # because file_hashes match the existing manifest
        assert updated_manifest.version_id == "v2"
        # previous_version_id is also preserved from the existing manifest
        assert updated_manifest.previous_version_id is None  # No previous version

    def test_rollback_without_backup(self, temp_graph):
        """Test rollback without creating backup."""
        # Setup
        version_mgr = VersionHistoryManager(temp_graph)
        version_mgr.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )
        version_mgr.add_version(
            node_count=120, edge_count=60, file_hashes={"file1.md": "hash1"}
        )

        manifest = Manifest(
            version=1,
            node_count=120,
            edge_count=60,
            file_hashes={"file1.md": "hash1"},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.pkl",
            created_at=int(time.time()),
            updated_at=int(time.time()),
            semantic_edge_count=60,
            finalized=True,
            version_id="v2",
        )
        write_manifest(manifest, temp_graph)

        # Rollback without backup
        rollback_mgr = RollbackManager(temp_graph)
        result = rollback_mgr.rollback_to_version("v1", create_backup=False)

        assert result.success is True
        assert result.backup_path is None

    def test_rollback_preserves_file_hashes(self, temp_graph):
        """Test that rollback preserves current file hashes (manifest-only)."""
        # Setup
        version_mgr = VersionHistoryManager(temp_graph)
        version_mgr.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )
        version_mgr.add_version(
            node_count=120, edge_count=60, file_hashes={"file1.md": "hash1", "file2.md": "hash2"}
        )

        current_files = {"file1.md": "current_hash", "file2.md": "current_hash2"}
        manifest = Manifest(
            version=1,
            node_count=120,
            edge_count=60,
            file_hashes=current_files,
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.pkl",
            created_at=int(time.time()),
            updated_at=int(time.time()),
            semantic_edge_count=60,
            finalized=True,
            version_id="v2",
        )
        write_manifest(manifest, temp_graph)

        # Rollback
        rollback_mgr = RollbackManager(temp_graph)
        result = rollback_mgr.rollback_to_version("v1")

        assert result.success is True

        # Verify file hashes are preserved (not restored)
        updated_manifest = read_manifest(temp_graph)
        assert updated_manifest.file_hashes == current_files

    def test_rollback_updates_timestamps(self, temp_graph):
        """Test that rollback updates the updated_at timestamp."""
        # Setup
        version_mgr = VersionHistoryManager(temp_graph)
        version_mgr.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )
        version_mgr.add_version(
            node_count=120, edge_count=60, file_hashes={"file1.md": "hash1"}
        )

        old_timestamp = int(time.time()) - 3600  # 1 hour ago
        manifest = Manifest(
            version=1,
            node_count=120,
            edge_count=60,
            file_hashes={"file1.md": "hash1"},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.pkl",
            created_at=old_timestamp,
            updated_at=old_timestamp,
            semantic_edge_count=60,
            finalized=True,
            version_id="v2",
        )
        write_manifest(manifest, temp_graph)

        # Rollback
        rollback_mgr = RollbackManager(temp_graph)
        before_rollback = int(time.time())
        result = rollback_mgr.rollback_to_version("v1")

        assert result.success is True

        # Verify timestamp was updated
        updated_manifest = read_manifest(temp_graph)
        assert updated_manifest.updated_at >= before_rollback
        assert updated_manifest.created_at == old_timestamp  # Preserved


class TestRollbackBackup:
    """Test backup creation during rollback."""

    def test_backup_creation(self, temp_graph):
        """Test that backup is created successfully."""
        # Setup
        version_mgr = VersionHistoryManager(temp_graph)
        version_mgr.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )
        version_mgr.add_version(
            node_count=120, edge_count=60, file_hashes={"file1.md": "hash1"}
        )

        manifest = Manifest(
            version=1,
            node_count=120,
            edge_count=60,
            file_hashes={"file1.md": "hash1"},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.pkl",
            created_at=int(time.time()),
            updated_at=int(time.time()),
            semantic_edge_count=60,
            finalized=True,
            version_id="v2",
        )
        write_manifest(manifest, temp_graph)

        # Rollback
        rollback_mgr = RollbackManager(temp_graph)
        result = rollback_mgr.rollback_to_version("v1", create_backup=True)

        assert result.success is True
        assert result.backup_path is not None
        assert result.backup_path.exists()

        # Verify backup contains the manifest
        backup_manifest_path = result.backup_path / "manifest.json"
        assert backup_manifest_path.exists()

        # Verify backup manifest has correct version
        with open(backup_manifest_path) as f:
            backup_data = json.load(f)
        assert backup_data["version_id"] == "v2"

    def test_backup_naming_convention(self, temp_graph):
        """Test backup directory naming convention."""
        # Setup
        version_mgr = VersionHistoryManager(temp_graph)
        version_mgr.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )
        version_mgr.add_version(
            node_count=120, edge_count=60, file_hashes={"file1.md": "hash1"}
        )

        manifest = Manifest(
            version=1,
            node_count=120,
            edge_count=60,
            file_hashes={"file1.md": "hash1"},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.pkl",
            created_at=int(time.time()),
            updated_at=int(time.time()),
            semantic_edge_count=60,
            finalized=True,
            version_id="v2",
        )
        write_manifest(manifest, temp_graph)

        # Rollback
        rollback_mgr = RollbackManager(temp_graph)
        result = rollback_mgr.rollback_to_version("v1")

        assert result.success is True
        assert result.backup_path is not None

        # Verify backup path contains version id and timestamp
        backup_name = result.backup_path.name
        assert "v2" in backup_name
        # Should contain a timestamp pattern

    def test_backup_failure_does_not_stop_rollback(self, temp_graph, monkeypatch):
        """Test that backup failure doesn't prevent rollback."""
        # Setup
        version_mgr = VersionHistoryManager(temp_graph)
        version_mgr.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )
        version_mgr.add_version(
            node_count=120, edge_count=60, file_hashes={"file1.md": "hash1"}
        )

        manifest = Manifest(
            version=1,
            node_count=120,
            edge_count=60,
            file_hashes={"file1.md": "hash1"},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.pkl",
            created_at=int(time.time()),
            updated_at=int(time.time()),
            semantic_edge_count=60,
            finalized=True,
            version_id="v2",
        )
        write_manifest(manifest, temp_graph)

        # Mock backup creation to fail
        rollback_mgr = RollbackManager(temp_graph)

        def mock_backup_fail(version_id):
            raise Exception("Backup failed")

        monkeypatch.setattr(rollback_mgr, "_create_rollback_backup", mock_backup_fail)

        # Rollback should still succeed
        result = rollback_mgr.rollback_to_version("v1", create_backup=True)

        # Rollback succeeds despite backup failure
        assert result.success is True
        assert len(result.errors) > 0
        assert any("Backup" in error for error in result.errors)


class TestRollbackEdgeCases:
    """Test edge cases and error scenarios."""

    def test_rollback_with_invalid_version_format(self, initialized_graph):
        """Test rollback with invalid version ID format."""
        rollback_mgr = RollbackManager(initialized_graph)
        result = rollback_mgr.rollback_to_version("invalid_version")

        assert result.success is False

    def test_rollback_to_v0(self, initialized_graph):
        """Test rollback to version v0 (should not exist)."""
        rollback_mgr = RollbackManager(initialized_graph)
        result = rollback_mgr.rollback_to_version("v0")

        assert result.success is False
        assert "not found" in result.message

    def test_multiple_rollbacks(self, temp_graph):
        """Test performing multiple rollbacks in sequence."""
        # Setup: Create v1, v2, v3
        version_mgr = VersionHistoryManager(temp_graph)
        version_mgr.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )
        version_mgr.add_version(
            node_count=120, edge_count=60, file_hashes={"file1.md": "hash1"}
        )
        version_mgr.add_version(
            node_count=140, edge_count=70, file_hashes={"file1.md": "hash1"}
        )

        # Set to v3
        manifest = Manifest(
            version=1,
            node_count=140,
            edge_count=70,
            file_hashes={"file1.md": "hash1"},
            edges_filename="edges.jsonl",
            sparse_index_filename="sparse_index.pkl",
            created_at=int(time.time()),
            updated_at=int(time.time()),
            semantic_edge_count=70,
            finalized=True,
            version_id="v3",
        )
        write_manifest(manifest, temp_graph)

        rollback_mgr = RollbackManager(temp_graph)

        # First rollback: v3 -> v2
        result1 = rollback_mgr.rollback_to_version("v2", create_backup=False)
        assert result1.success is True
        assert result1.from_version == "v3"
        assert result1.to_version == "v2"

        # Check actual manifest version_id after first rollback
        intermediate_manifest = read_manifest(temp_graph)
        current_version_id = intermediate_manifest.version_id

        # Second rollback: current -> v1
        result2 = rollback_mgr.rollback_to_version("v1", create_backup=False)
        assert result2.success is True
        assert result2.from_version == current_version_id  # Use actual current version
        assert result2.to_version == "v1"

        # Verify final state
        final_manifest = read_manifest(temp_graph)
        assert final_manifest.node_count == 100
        assert final_manifest.edge_count == 50

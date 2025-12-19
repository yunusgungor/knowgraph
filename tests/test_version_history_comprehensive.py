"""Comprehensive tests for version history management.

Tests version tracking, persistence, and retrieval to achieve 60% coverage.
"""

import json
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from knowgraph.infrastructure.storage.version_history import (
    FileChangeSummary,
    VersionHistoryManager,
    VersionSnapshot,
)


@pytest.fixture
def temp_graph():
    """Create temporary graph directory."""
    with TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "graphstore"
        graph_path.mkdir(parents=True)
        (graph_path / "metadata").mkdir()
        yield graph_path


@pytest.fixture
def version_manager(temp_graph):
    """Create version history manager."""
    return VersionHistoryManager(temp_graph)


class TestFileChangeSummary:
    """Test FileChangeSummary data class."""

    def test_file_changes_creation(self):
        """Test creating file change summary."""
        changes = FileChangeSummary(
            added=["file1.py", "file2.py"],
            modified=["file3.py"],
            deleted=["old.py"],
        )

        assert len(changes.added) == 2
        assert len(changes.modified) == 1
        assert len(changes.deleted) == 1
        assert changes.total_changes == 4

    def test_to_dict(self):
        """Test serialization."""
        changes = FileChangeSummary(added=["a.py"], modified=[], deleted=[])
        data = changes.to_dict()

        assert "added" in data
        assert "modified" in data
        assert "deleted" in data
        assert data["total_changes"] == 1

    def test_from_dict(self):
        """Test deserialization."""
        data = {"added": ["a.py"], "modified": ["b.py"], "deleted": []}
        changes = FileChangeSummary.from_dict(data)

        assert len(changes.added) == 1
        assert len(changes.modified) == 1


class TestVersionHistoryManager:
    """Test VersionHistoryManager functionality."""

    def test_manager_initialization(self, version_manager, temp_graph):
        """Test manager initialization."""
        assert version_manager.graph_store_path == temp_graph
        assert version_manager.versions_file.exists()

    def test_add_version(self, version_manager):
        """Test adding a version."""
        snapshot = version_manager.add_version(
            node_count=100,
            edge_count=50,
            file_hashes={"file1.md": "abc123"},
        )

        assert snapshot.version_id == "v1"
        assert snapshot.node_count == 100
        assert snapshot.edge_count == 50

    def test_add_multiple_versions(self, version_manager):
        """Test adding multiple versions."""
        for i in range(3):
            version_manager.add_version(
                node_count=100 * (i + 1),
                edge_count=50 * (i + 1),
                file_hashes={f"file{i}.md": f"hash{i}"},
            )

        versions = version_manager.list_versions()
        assert len(versions) == 3
        assert versions[0].version_id == "v3"  # Newest first

    def test_get_version(self, version_manager):
        """Test getting specific version."""
        version_manager.add_version(
            node_count=100,
            edge_count=50,
            file_hashes={"file1.md": "abc"},
        )

        snapshot = version_manager.get_version("v1")

        assert snapshot is not None
        assert snapshot.version_id == "v1"
        assert snapshot.node_count == 100

    def test_get_nonexistent_version(self, version_manager):
        """Test getting non-existent version."""
        snapshot = version_manager.get_version("v999")
        assert snapshot is None

    def test_list_versions_limit(self, version_manager):
        """Test listing with limit."""
        for i in range(10):
            version_manager.add_version(
                node_count=i,
                edge_count=i,
                file_hashes={f"f{i}.md": f"h{i}"},
            )

        versions = version_manager.list_versions(limit=5)
        assert len(versions) == 5
        # Should be newest first
        assert versions[0].version_id == "v10"

    def test_file_change_detection(self, version_manager):
        """Test file change detection between versions."""
        # First version
        v1 = version_manager.add_version(
            node_count=10,
            edge_count=5,
            file_hashes={"file1.md": "hash1", "file2.md": "hash2"},
        )

        # Second version with changes
        v2 = version_manager.add_version(
            node_count=20,
            edge_count=10,
            file_hashes={
                "file1.md": "hash1",  # Unchanged
                "file2.md": "newhash2",  # Modified
                "file3.md": "hash3",  # Added
            },
            previous_file_hashes={"file1.md": "hash1", "file2.md": "hash2"},
        )

        assert len(v2.file_changes.added) == 1
        assert len(v2.file_changes.modified) == 1
        assert len(v2.file_changes.deleted) == 0


class TestVersionPersistence:
    """Test version persistence."""

    def test_versions_persisted_to_jsonl(self, version_manager, temp_graph):
        """Test versions are saved to JSONL file."""
        version_manager.add_version(
            node_count=100,
            edge_count=50,
            file_hashes={"f1.md": "h1"},
        )

        versions_file = temp_graph / "metadata" / "versions.jsonl"
        assert versions_file.exists()

        with open(versions_file) as f:
            lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["version_id"] == "v1"

    def test_load_existing_versions(self, temp_graph):
        """Test loading existing versions."""
        # Create first manager and add version
        manager1 = VersionHistoryManager(temp_graph)
        manager1.add_version(100, 50, {"f1.md": "h1"})

        # Create second manager - should load existing
        manager2 = VersionHistoryManager(temp_graph)
        versions = manager2.list_versions()

        assert len(versions) == 1
        assert versions[0].version_id == "v1"

    def test_version_id_increments(self, version_manager):
        """Test version IDs increment correctly."""
        v1 = version_manager.add_version(10, 5, {"f1.md": "h1"})
        v2 = version_manager.add_version(20, 10, {"f2.md": "h2"})
        v3 = version_manager.add_version(30, 15, {"f3.md": "h3"})

        assert v1.version_id == "v1"
        assert v2.version_id == "v2"
        assert v3.version_id == "v3"


class TestVersionSnapshot:
    """Test VersionSnapshot data class."""

    def test_snapshot_creation(self):
        """Test creating a version snapshot."""
        snapshot = VersionSnapshot(
            version_id="v1",
            timestamp=int(time.time()),
            created_at_iso="2024-01-01T00:00:00",
            node_count=100,
            edge_count=50,
            file_count=5,
            file_changes=FileChangeSummary(),
            manifest_hash="abc123",
            metadata={"tag": "important"},
        )

        assert snapshot.version_id == "v1"
        assert snapshot.node_count == 100
        assert snapshot.metadata["tag"] == "important"

    def test_snapshot_serialization(self):
        """Test snapshot to_dict."""
        snapshot = VersionSnapshot(
            version_id="v1",
            timestamp=123456,
            created_at_iso="2024-01-01T00:00:00",
            node_count=100,
            edge_count=50,
            file_count=5,
            file_changes=FileChangeSummary(added=["f1.md"]),
            manifest_hash="abc",
        )

        data = snapshot.to_dict()

        assert data["version_id"] == "v1"
        assert data["node_count"] == 100
        assert "file_changes" in data

    def test_snapshot_deserialization(self):
        """Test snapshot from_dict."""
        data = {
            "version_id": "v1",
            "timestamp": 123456,
            "created_at_iso": "2024-01-01T00:00:00",
            "node_count": 100,
            "edge_count": 50,
            "file_count": 5,
            "file_changes": {"added": ["f1.md"], "modified": [], "deleted": []},
            "manifest_hash": "abc",
            "metadata": {},
        }

        snapshot = VersionSnapshot.from_dict(data)

        assert snapshot.version_id == "v1"
        assert snapshot.node_count == 100


class TestVersionIntegration:
    """Integration tests for version workflows."""

    def test_full_version_workflow(self, temp_graph):
        """Test complete version tracking workflow."""
        manager = VersionHistoryManager(temp_graph)

        # Add versions
        manager.add_version(100, 50, {"f1.md": "h1"}, metadata={"note": "v1"})
        manager.add_version(200, 100, {"f2.md": "h2"}, metadata={"note": "v2"})

        # List versions
        versions = manager.list_versions()
        assert len(versions) == 2

        # Get specific version
        v1 = manager.get_version("v1")
        assert v1.metadata["note"] == "v1"

        # Verify persistence
        manager2 = VersionHistoryManager(temp_graph)
        versions2 = manager2.list_versions()
        assert len(versions2) == 2

    def test_manifest_hash_uniqueness(self, version_manager):
        """Test manifest hash changes with different files."""
        v1 = version_manager.add_version(10, 5, {"file1.md": "hash1"})
        v2 = version_manager.add_version(20, 10, {"file2.md": "hash2"})

        # Different file hashes should produce different manifest hashes
        assert v1.manifest_hash != v2.manifest_hash


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

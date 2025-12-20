"""Tests for version diff engine.

Tests VersionDiffEngine functionality for comparing version snapshots.
"""

import time
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from knowgraph.infrastructure.storage.version_diff import VersionDiff, VersionDiffEngine
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


@pytest.fixture
def diff_engine():
    """Create diff engine instance."""
    return VersionDiffEngine()


class TestVersionDiff:
    """Test VersionDiff dataclass."""

    def test_version_diff_creation(self):
        """Test creating version diff object."""
        file_changes = FileChangeSummary(
            added=["new.py"], modified=["updated.py"], deleted=["old.py"]
        )

        diff = VersionDiff(
            from_version="v1",
            to_version="v2",
            timestamp_diff=3600,
            node_count_diff=10,
            edge_count_diff=5,
            file_changes=file_changes,
            significant_changes=["Added 10 nodes", "Added 5 edges"],
        )

        assert diff.from_version == "v1"
        assert diff.to_version == "v2"
        assert diff.timestamp_diff == 3600
        assert diff.node_count_diff == 10
        assert diff.edge_count_diff == 5
        assert len(diff.significant_changes) == 2

    def test_to_dict(self):
        """Test serialization to dictionary."""
        file_changes = FileChangeSummary(added=["a.py"], modified=[], deleted=[])
        diff = VersionDiff(
            from_version="v1",
            to_version="v2",
            timestamp_diff=3600,
            node_count_diff=5,
            edge_count_diff=3,
            file_changes=file_changes,
        )

        data = diff.to_dict()
        assert data["from_version"] == "v1"
        assert data["to_version"] == "v2"
        assert "file_changes" in data
        assert "significant_changes" in data


class TestVersionDiffEngine:
    """Test VersionDiffEngine core functionality."""

    def test_diff_versions_basic(self, diff_engine, version_manager):
        """Test basic diff generation between two versions."""
        # Create first version
        v1 = version_manager.add_version(
            node_count=100,
            edge_count=50,
            file_hashes={"file1.md": "hash1"},
        )

        time.sleep(0.1)  # Ensure different timestamps

        # Create second version with changes - pass previous hashes for comparison
        v2 = version_manager.add_version(
            node_count=120,
            edge_count=60,
            file_hashes={"file1.md": "hash1_updated", "file2.md": "hash2"},
            previous_file_hashes={"file1.md": "hash1"},
        )

        # Generate diff
        diff = diff_engine.diff_versions(v1, v2)

        assert diff.from_version == "v1"
        assert diff.to_version == "v2"
        assert diff.node_count_diff == 20
        assert diff.edge_count_diff == 10
        assert diff.timestamp_diff >= 0  # May be 0 in fast tests

    def test_diff_versions_negative_changes(self, diff_engine, version_manager):
        """Test diff with decreased node/edge counts."""
        v1 = version_manager.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )

        v2 = version_manager.add_version(
            node_count=80, edge_count=40, file_hashes={"file1.md": "hash1"}
        )

        diff = diff_engine.diff_versions(v1, v2)

        assert diff.node_count_diff == -20
        assert diff.edge_count_diff == -10
        assert "Removed 20 nodes" in diff.significant_changes
        assert "Removed 10 edges" in diff.significant_changes

    def test_diff_same_version(self, diff_engine, version_manager):
        """Test diff when comparing same version to itself."""
        v1 = version_manager.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )

        diff = diff_engine.diff_versions(v1, v1)

        assert diff.from_version == "v1"
        assert diff.to_version == "v1"
        assert diff.node_count_diff == 0
        assert diff.edge_count_diff == 0
        assert diff.timestamp_diff == 0

    def test_diff_with_file_additions(self, diff_engine, version_manager):
        """Test diff with new files added."""
        v1 = version_manager.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )

        v2 = version_manager.add_version(
            node_count=120,
            edge_count=60,
            file_hashes={
                "file1.md": "hash1",
                "file2.md": "hash2",
                "file3.md": "hash3",
            },
            previous_file_hashes={"file1.md": "hash1"},
        )

        diff = diff_engine.diff_versions(v1, v2)

        assert len(diff.file_changes.added) == 2
        assert "Added 2 new files" in diff.significant_changes

    def test_diff_with_file_modifications(self, diff_engine, version_manager):
        """Test diff with modified files."""
        v1 = version_manager.add_version(
            node_count=100,
            edge_count=50,
            file_hashes={"file1.md": "hash1", "file2.md": "hash2"},
        )

        v2 = version_manager.add_version(
            node_count=100,
            edge_count=50,
            file_hashes={"file1.md": "hash1_updated", "file2.md": "hash2_updated"},
            previous_file_hashes={"file1.md": "hash1", "file2.md": "hash2"},
        )

        diff = diff_engine.diff_versions(v1, v2)

        assert len(diff.file_changes.modified) == 2
        assert "Modified 2 files" in diff.significant_changes

    def test_diff_with_file_deletions(self, diff_engine, version_manager):
        """Test diff with deleted files."""
        v1 = version_manager.add_version(
            node_count=100,
            edge_count=50,
            file_hashes={"file1.md": "hash1", "file2.md": "hash2", "file3.md": "hash3"},
        )

        v2 = version_manager.add_version(
            node_count=80,
            edge_count=40,
            file_hashes={"file1.md": "hash1"},
            previous_file_hashes={"file1.md": "hash1", "file2.md": "hash2", "file3.md": "hash3"},
        )

        diff = diff_engine.diff_versions(v1, v2)

        assert len(diff.file_changes.deleted) == 2
        assert "Deleted 2 files" in diff.significant_changes

    def test_diff_empty_file_changes(self, diff_engine, version_manager):
        """Test diff with no file changes."""
        v1 = version_manager.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )

        v2 = version_manager.add_version(
            node_count=100,
            edge_count=50,
            file_hashes={"file1.md": "hash1"},
            previous_file_hashes={"file1.md": "hash1"},
        )

        diff = diff_engine.diff_versions(v1, v2)

        assert len(diff.file_changes.added) == 0
        assert len(diff.file_changes.modified) == 0
        assert len(diff.file_changes.deleted) == 0


class TestDiffReportFormatting:
    """Test diff report formatting."""

    def test_format_diff_report_basic(self, diff_engine, version_manager):
        """Test basic report formatting."""
        v1 = version_manager.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )

        time.sleep(0.1)

        v2 = version_manager.add_version(
            node_count=120,
            edge_count=60,
            file_hashes={"file1.md": "hash1", "file2.md": "hash2"},
            previous_file_hashes={"file1.md": "hash1"},
        )

        diff = diff_engine.diff_versions(v1, v2)
        report = diff_engine.format_diff_report(diff)

        assert "VERSION DIFF: v1 → v2" in report
        assert "Nodes:" in report
        assert "Edges:" in report

    def test_format_diff_report_with_file_changes(self, diff_engine, version_manager):
        """Test report with file changes."""
        v1 = version_manager.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )

        v2 = version_manager.add_version(
            node_count=120,
            edge_count=60,
            file_hashes={"file1.md": "hash1_updated", "file2.md": "hash2"},
            previous_file_hashes={"file1.md": "hash1"},
        )

        diff = diff_engine.diff_versions(v1, v2)
        report = diff_engine.format_diff_report(diff)

        assert "File Changes" in report
        assert "Added:" in report or "Modified:" in report

    def test_format_diff_report_time_minutes(self, diff_engine):
        """Test time formatting in minutes."""
        file_changes = FileChangeSummary(added=[], modified=[], deleted=[])
        
        # Create snapshots with small time difference
        timestamp_base = int(time.time())
        v1 = VersionSnapshot(
            version_id="v1",
            timestamp=timestamp_base,
            created_at_iso=datetime.fromtimestamp(timestamp_base).isoformat(),
            node_count=100,
            edge_count=50,
            file_count=1,
            file_changes=file_changes,
            manifest_hash="hash_v1",
        )

        v2 = VersionSnapshot(
            version_id="v2",
            timestamp=timestamp_base + 1800,  # 30 minutes later
            created_at_iso=datetime.fromtimestamp(timestamp_base + 1800).isoformat(),
            node_count=100,
            edge_count=50,
            file_count=1,
            file_changes=file_changes,
            manifest_hash="hash_v2",
        )

        diff = diff_engine.diff_versions(v1, v2)
        report = diff_engine.format_diff_report(diff)

        assert "30 minutes" in report

    def test_format_diff_report_time_hours(self, diff_engine):
        """Test time formatting in hours."""
        file_changes = FileChangeSummary(added=[], modified=[], deleted=[])
        
        timestamp_base = int(time.time())
        v1 = VersionSnapshot(
            version_id="v1",
            timestamp=timestamp_base,
            created_at_iso=datetime.fromtimestamp(timestamp_base).isoformat(),
            node_count=100,
            edge_count=50,
            file_count=1,
            file_changes=file_changes,
            manifest_hash="hash_v1",
        )

        v2 = VersionSnapshot(
            version_id="v2",
            timestamp=timestamp_base + 7200,  # 2 hours later
            created_at_iso=datetime.fromtimestamp(timestamp_base + 7200).isoformat(),
            node_count=100,
            edge_count=50,
            file_count=1,
            file_changes=file_changes,
            manifest_hash="hash_v2",
        )

        diff = diff_engine.diff_versions(v1, v2)
        report = diff_engine.format_diff_report(diff)

        assert "2 hours" in report

    def test_format_diff_report_time_days(self, diff_engine):
        """Test time formatting in days."""
        file_changes = FileChangeSummary(added=[], modified=[], deleted=[])
        
        timestamp_base = int(time.time())
        v1 = VersionSnapshot(
            version_id="v1",
            timestamp=timestamp_base,
            created_at_iso=datetime.fromtimestamp(timestamp_base).isoformat(),
            node_count=100,
            edge_count=50,
            file_count=1,
            file_changes=file_changes,
            manifest_hash="hash_v1",
        )

        v2 = VersionSnapshot(
            version_id="v2",
            timestamp=timestamp_base + 172800,  # 2 days later
            created_at_iso=datetime.fromtimestamp(timestamp_base + 172800).isoformat(),
            node_count=100,
            edge_count=50,
            file_count=1,
            file_changes=file_changes,
            manifest_hash="hash_v2",
        )

        diff = diff_engine.diff_versions(v1, v2)
        report = diff_engine.format_diff_report(diff)

        assert "2 days" in report


class TestSignificantChanges:
    """Test significant changes extraction."""

    def test_significant_changes_additions(self, diff_engine, version_manager):
        """Test significant changes with additions."""
        v1 = version_manager.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )

        v2 = version_manager.add_version(
            node_count=150,
            edge_count=75,
            file_hashes={"file1.md": "hash1", "file2.md": "hash2"},
            previous_file_hashes={"file1.md": "hash1"},
        )

        diff = diff_engine.diff_versions(v1, v2)

        assert "Added 50 nodes" in diff.significant_changes
        assert "Added 25 edges" in diff.significant_changes
        assert "Added 1 new files" in diff.significant_changes

    def test_significant_changes_removals(self, diff_engine, version_manager):
        """Test significant changes with removals."""
        v1 = version_manager.add_version(
            node_count=100,
            edge_count=50,
            file_hashes={"file1.md": "hash1", "file2.md": "hash2"},
        )

        v2 = version_manager.add_version(
            node_count=80,
            edge_count=40,
            file_hashes={"file1.md": "hash1"},
            previous_file_hashes={"file1.md": "hash1", "file2.md": "hash2"},
        )

        diff = diff_engine.diff_versions(v1, v2)

        assert "Removed 20 nodes" in diff.significant_changes
        assert "Removed 10 edges" in diff.significant_changes
        assert "Deleted 1 files" in diff.significant_changes

    def test_significant_changes_mixed(self, diff_engine, version_manager):
        """Test significant changes with mixed operations."""
        v1 = version_manager.add_version(
            node_count=100,
            edge_count=50,
            file_hashes={"file1.md": "hash1", "old.md": "old_hash"},
        )

        v2 = version_manager.add_version(
            node_count=110,
            edge_count=55,
            file_hashes={"file1.md": "hash1_updated", "new.md": "new_hash"},
        )

        diff = diff_engine.diff_versions(v1, v2)

        changes_str = " ".join(diff.significant_changes)
        assert "Added 10 nodes" in changes_str
        assert "Added 5 edges" in changes_str
        # Should have both additions and modifications/deletions
        assert len(diff.file_changes.modified) > 0 or len(diff.file_changes.added) > 0

    def test_significant_changes_no_changes(self, diff_engine, version_manager):
        """Test significant changes when nothing changed."""
        v1 = version_manager.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )

        v2 = version_manager.add_version(
            node_count=100, edge_count=50, file_hashes={"file1.md": "hash1"}
        )

        diff = diff_engine.diff_versions(v1, v2)

        # Should only have time-based change
        node_edge_changes = [c for c in diff.significant_changes if "nodes" in c or "edges" in c]
        assert len(node_edge_changes) == 0

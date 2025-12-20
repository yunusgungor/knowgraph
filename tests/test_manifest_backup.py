"""Tests for manifest backup and recovery."""

import tempfile
import time
from pathlib import Path

import pytest

from knowgraph.infrastructure.storage.manifest_backup import ManifestBackupManager


@pytest.fixture
def temp_manifest_dir():
    """Create temporary manifest directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def manifest_with_content(temp_manifest_dir):
    """Create manifest with content."""
    manifest_path = temp_manifest_dir / "manifest.json"
    manifest_path.write_text('{"version": "1.0", "files": []}')
    return temp_manifest_dir


def test_backup_manifest_creates_backup(manifest_with_content):
    """Test backup creation."""
    manager = ManifestBackupManager(manifest_with_content)

    backup_path = manager.backup_manifest()

    assert backup_path is not None
    assert backup_path.exists()
    assert backup_path.parent == manager.backup_dir
    assert "manifest" in backup_path.name
    assert ".backup" in backup_path.name


def test_backup_nonexistent_manifest(temp_manifest_dir):
    """Test backup when manifest doesn't exist."""
    manager = ManifestBackupManager(temp_manifest_dir)

    backup_path = manager.backup_manifest()

    assert backup_path is None


def test_backup_prunes_old_backups(manifest_with_content):
    """Test that old backups are pruned."""
    manager = ManifestBackupManager(manifest_with_content)

    # Create 8 backups with delays
    for _ in range(8):
        manager.backup_manifest(max_backups=5)
        time.sleep(0.01)

    # Should only keep 5
    backups = manager._list_backups()
    assert len(backups) <= 5


def test_restore_latest_backup(manifest_with_content):
    """Test restore from latest backup."""
    manager = ManifestBackupManager(manifest_with_content)

    # Create backup
    manager.backup_manifest()

    # Modify manifest
    manager.manifest_path.write_text('{"corrupted": true}')

    # Restore
    success = manager.restore_latest_backup()

    assert success is True
    # Should restore original content
    assert "version" in manager.manifest_path.read_text()
    assert "corrupted" not in manager.manifest_path.read_text()


def test_restore_no_backups(temp_manifest_dir):
    """Test restore when no backups exist."""
    manager = ManifestBackupManager(temp_manifest_dir)

    success = manager.restore_latest_backup()

    assert success is False


def test_restore_from_specific_backup(manifest_with_content):
    """Test restore from specific backup."""
    manager = ManifestBackupManager(manifest_with_content)

    # Create first backup
    first_backup = manager.backup_manifest()
    time.sleep(0.1)  # Ensure different timestamps

    # Modify and create second backup
    manager.manifest_path.write_text('{"version": "2.0"}')
    time.sleep(0.1)
    manager.backup_manifest()

    # Debug: List all backups
    print(f"\nDEBUG: Backups available: {[b.name for b in manager._list_backups()]}")

    # Restore from first - create new manager to ensure fresh state
    fresh_manager = ManifestBackupManager(manifest_with_content)
    success = fresh_manager.restore_from_backup(first_backup)

    assert success is True
    # The first backup was of version 1.0 logic
    content = fresh_manager.manifest_path.read_text()
    print(f"DEBUG: Manager path: {fresh_manager.manifest_path}")
    print(f"DEBUG: Content after restore: {content}")
    assert "1.0" in content
    assert "2.0" not in content


def test_get_backup_stats_empty(temp_manifest_dir):
    """Test backup stats when no backups."""
    manager = ManifestBackupManager(temp_manifest_dir)

    stats = manager.get_backup_stats()

    assert stats["backup_count"] == 0
    assert stats["latest_backup"] is None


def test_get_backup_stats_with_backups(manifest_with_content):
    """Test backup stats with backups."""
    manager = ManifestBackupManager(manifest_with_content)

    # Create backups with delay
    manager.backup_manifest()
    time.sleep(0.1)  # Ensure different timestamps
    manager.backup_manifest()

    stats = manager.get_backup_stats()

    assert stats["backup_count"] >= 1
    assert stats["latest_backup"] is not None
    assert "latest_backup_time" in stats
    assert stats["total_size_mb"] >= 0


def test_backup_preserves_corrupted_manifest(manifest_with_content):
    """Test that restore preserves corrupted manifest."""
    manager = ManifestBackupManager(manifest_with_content)

    # Create backup
    manager.backup_manifest()

    # Corrupt manifest
    manager.manifest_path.write_text("CORRUPTED")

    # Restore
    manager.restore_latest_backup()

    # Corrupted version should be preserved
    corrupted_path = manager.manifest_path.with_suffix(".json.corrupted")
    assert corrupted_path.exists()
    assert corrupted_path.read_text() == "CORRUPTED"

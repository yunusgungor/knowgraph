"""Tests for cache health checks and corruption detection."""

import tempfile

import pytest

from knowgraph.infrastructure.cache.cache_manager import CacheManager


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_cache_integrity_healthy(temp_cache_dir):
    """Test cache integrity check on healthy database."""
    cache = CacheManager(cache_dir=temp_cache_dir)

    # Fresh database should be healthy
    assert cache.check_integrity() is True


def test_cache_integrity_corrupted(temp_cache_dir):
    """Test cache integrity check on corrupted database."""
    cache = CacheManager(cache_dir=temp_cache_dir)

    # Corrupt the database by writing invalid data
    cache._get_conn().close()
    with open(cache.db_path, "wb") as f:
        f.write(b"CORRUPTED DATA")

    # Check should detect corruption
    assert cache.check_integrity() is False


def test_cache_rebuild_if_corrupted(temp_cache_dir):
    """Test automatic cache rebuild on corruption."""
    cache = CacheManager(cache_dir=temp_cache_dir)

    # Add some data
    from knowgraph.domain.intelligence.provider import Entity

    entities = [Entity(name="test", type="code", description="test entity")]
    cache.save_entities("test_hash", entities)

    # Corrupt the database
    cache._get_conn().close()
    with open(cache.db_path, "wb") as f:
        f.write(b"CORRUPTED")

    # Rebuild should work
    cache.rebuild_cache_if_corrupted()

    # Check should now pass
    assert cache.check_integrity() is True

    # Backup file should exist
    backup_path = cache.db_path.with_suffix(".db.corrupted")
    assert backup_path.exists()


def test_cache_stats_empty(temp_cache_dir):
    """Test cache stats on empty cache."""
    cache = CacheManager(cache_dir=temp_cache_dir)

    stats = cache.get_cache_stats()

    assert stats["entry_count"] == 0
    assert stats["size_mb"] >= 0
    assert stats["is_healthy"] is True
    assert "db_path" in stats


def test_cache_stats_with_data(temp_cache_dir):
    """Test cache stats with cached data."""
    cache = CacheManager(cache_dir=temp_cache_dir)

    # Add multiple entries
    from knowgraph.domain.intelligence.provider import Entity

    for i in range(10):
        entities = [Entity(name=f"test_{i}", type="code", description=f"entity {i}")]
        cache.save_entities(f"hash_{i}", entities)

    stats = cache.get_cache_stats()

    assert stats["entry_count"] == 10
    assert stats["size_mb"] > 0
    assert stats["is_healthy"] is True


def test_cache_stats_on_corrupted(temp_cache_dir):
    """Test cache stats gracefully handles corrupted database."""
    cache = CacheManager(cache_dir=temp_cache_dir)

    # Corrupt database
    cache._get_conn().close()
    cache.db_path.unlink()
    cache.db_path.write_bytes(b"INVALID")

    stats = cache.get_cache_stats()

    # Should return error state instead of crashing
    assert stats["is_healthy"] is False
    assert "error" in stats


def test_rebuild_preserves_backup(temp_cache_dir):
    """Test that rebuild preserves corrupted DB for debugging."""
    cache = CacheManager(cache_dir=temp_cache_dir)

    # Write some identifiable corrupt data
    cache._get_conn().close()
    corrupt_data = b"CORRUPTED_FOR_DEBUG"
    cache.db_path.write_bytes(corrupt_data)

    # Rebuild
    cache.rebuild_cache_if_corrupted()

    # Backup should contain original corrupted data
    backup_path = cache.db_path.with_suffix(".db.corrupted")
    assert backup_path.exists()
    assert backup_path.read_bytes() == corrupt_data


def test_cache_operations_after_rebuild(temp_cache_dir):
    """Test cache operations work normally after rebuild."""
    cache = CacheManager(cache_dir=temp_cache_dir)

    # Corrupt and rebuild
    cache._get_conn().close()
    cache.db_path.write_bytes(b"CORRUPTED")
    cache.rebuild_cache_if_corrupted()

    # Normal operations should work
    from knowgraph.domain.intelligence.provider import Entity

    entities = [Entity(name="test", type="code", description="test")]
    cache.save_entities("new_hash", entities)

    retrieved = cache.get_entities("new_hash")
    assert retrieved is not None
    assert len(retrieved) == 1
    assert retrieved[0].name == "test"

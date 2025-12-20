"""Tests for resource detection and auto-tuning."""

import pytest

from knowgraph.shared.resource_detector import PSUTIL_AVAILABLE, ResourceDetector


def test_get_available_ram():
    """Test RAM detection."""
    ram_gb = ResourceDetector.get_available_ram_gb()

    # Should return a positive number
    assert ram_gb > 0
    # Reasonable range (most systems have 1-128GB)
    assert 0.5 < ram_gb < 256


def test_get_cpu_count():
    """Test CPU count detection."""
    cpu_count = ResourceDetector.get_cpu_count()

    # Should return a positive integer
    assert cpu_count > 0
    assert isinstance(cpu_count, int)
    # Reasonable range
    assert 1 <= cpu_count <= 128


def test_recommend_workers_low_ram():
    """Test worker recommendation for low RAM."""
    # Mock low RAM
    original_method = ResourceDetector.get_available_ram_gb
    ResourceDetector.get_available_ram_gb = lambda: 3.0  # 3GB

    workers = ResourceDetector.recommend_workers()
    assert workers == 5  # Conservative for low RAM

    # Restore
    ResourceDetector.get_available_ram_gb = original_method


def test_recommend_workers_medium_ram():
    """Test worker recommendation for medium RAM."""
    original_method = ResourceDetector.get_available_ram_gb
    ResourceDetector.get_available_ram_gb = lambda: 6.0  # 6GB

    workers = ResourceDetector.recommend_workers()
    assert workers == 10

    ResourceDetector.get_available_ram_gb = original_method


def test_recommend_workers_high_ram():
    """Test worker recommendation for high RAM."""
    original_method = ResourceDetector.get_available_ram_gb
    ResourceDetector.get_available_ram_gb = lambda: 20.0  # 20GB

    workers = ResourceDetector.recommend_workers()
    assert workers == 20  # Maximum

    ResourceDetector.get_available_ram_gb = original_method


def test_recommend_workers_max_limit():
    """Test that worker count respects max limit."""
    original_method = ResourceDetector.get_available_ram_gb
    ResourceDetector.get_available_ram_gb = lambda: 50.0  # 50GB

    workers = ResourceDetector.recommend_workers(max_workers=15)
    assert workers == 15  # Should not exceed max

    ResourceDetector.get_available_ram_gb = original_method


def test_recommend_batch_size():
    """Test batch size recommendation."""
    original_method = ResourceDetector.get_available_ram_gb

    # Low RAM
    ResourceDetector.get_available_ram_gb = lambda: 3.0
    assert ResourceDetector.recommend_batch_size() == 5

    # Medium RAM
    ResourceDetector.get_available_ram_gb = lambda: 6.0
    assert ResourceDetector.recommend_batch_size() == 10

    # High RAM
    ResourceDetector.get_available_ram_gb = lambda: 16.0
    assert ResourceDetector.recommend_batch_size() == 15

    ResourceDetector.get_available_ram_gb = original_method


def test_get_system_info():
    """Test comprehensive system info retrieval."""
    info = ResourceDetector.get_system_info()

    assert "available_ram_gb" in info
    assert "cpu_count" in info
    assert "psutil_available" in info

    if PSUTIL_AVAILABLE:
        assert info["psutil_available"] is True
        assert "total_ram_gb" in info
        assert "ram_percent_used" in info
    else:
        assert info["psutil_available"] is False
        assert "note" in info


def test_psutil_not_available_fallback():
    """Test graceful degradation when psutil not available."""
    # Even without psutil, functions should return sensible defaults
    ram = ResourceDetector.get_available_ram_gb()
    cpu = ResourceDetector.get_cpu_count()
    workers = ResourceDetector.recommend_workers()

    assert ram > 0
    assert cpu > 0
    assert workers > 0


@pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not installed")
def test_psutil_integration():
    """Test actual psutil integration when available."""
    import psutil

    # Get actual values
    actual_ram = psutil.virtual_memory().available / (1024**3)
    detected_ram = ResourceDetector.get_available_ram_gb()

    # Should match within 10% (some may be used between calls)
    assert abs(actual_ram - detected_ram) / actual_ram < 0.1

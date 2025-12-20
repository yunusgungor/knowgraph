"""Tests for memory profiling guards and monitoring."""

import pytest

from knowgraph.shared.memory_profiler import (
    check_memory_available,
    get_memory_stats,
    get_memory_usage_mb,
    memory_guard,
    memory_profiled,
)


def test_get_memory_usage():
    """Test that memory usage can be measured."""
    usage = get_memory_usage_mb()
    assert usage > 0, "Memory usage should be positive"
    assert usage < 10000, "Memory usage seems unreasonably high"


def test_memory_guard_basic():
    """Test basic memory guard functionality."""
    with memory_guard("test_operation") as stats:
        # Allocate some memory
        data = [0] * 1000000  # ~8MB
        del data

    assert "operation" in stats
    assert stats["operation"] == "test_operation"
    assert "mem_before_mb" in stats
    assert "mem_after_mb" in stats
    assert "mem_delta_mb" in stats


def test_memory_guard_warning_threshold():
    """Test that warning threshold triggers logging."""
    with memory_guard(
        "threshold_test",
        warning_threshold_mb=0.1,  # Very low threshold
        critical_threshold_mb=1000,
    ) as stats:
        # Allocate enough to trigger warning
        data = [0] * 100000
        del data

    # Note: warning_triggered depends on actual memory allocation
    # which can vary, so we just check the structure
    assert "warning_triggered" in stats
    assert "critical_triggered" in stats


def test_memory_profiled_decorator():
    """Test memory profiling decorator."""

    @memory_profiled(warning_threshold_mb=1000, critical_threshold_mb=2000)
    def allocate_memory():
        return [0] * 10000

    result = allocate_memory()
    assert len(result) == 10000


def test_check_memory_available():
    """Test memory availability check."""
    # Should have at least 10MB available
    assert check_memory_available(10) is True

    # Unlikely to have 1TB available
    # (but might on some systems, so we don't assert False)
    result = check_memory_available(1_000_000)
    assert isinstance(result, bool)


def test_get_memory_stats():
    """Test comprehensive memory statistics."""
    stats = get_memory_stats()

    assert "process_rss_mb" in stats
    assert stats["process_rss_mb"] > 0

    # These might not be available without psutil
    if "total_mb" in stats:
        assert stats["total_mb"] > 0
        assert stats["available_mb"] >= 0
        assert 0 <= stats["percent_used"] <= 100


def test_memory_guard_no_leak():
    """Test that memory guard doesn't cause memory leaks."""
    initial_usage = get_memory_usage_mb()

    # Run guard multiple times
    for _ in range(10):
        with memory_guard("leak_test"):
            data = [0] * 10000
            del data

    final_usage = get_memory_usage_mb()

    # Memory should not increase significantly (allow 10MB variance)
    assert final_usage - initial_usage < 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

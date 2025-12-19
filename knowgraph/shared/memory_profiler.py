"""Memory profiling guards and monitoring utilities.

Provides decorators and context managers to monitor memory usage and
prevent memory-related issues in production.
"""

import functools
import gc
import logging
import os
from collections.abc import Callable
from contextlib import contextmanager
from typing import TypeVar

from knowgraph.config import get_settings

logger = logging.getLogger(__name__)

# Type variable for generic function decoration
F = TypeVar("F", bound=Callable)

# Load thresholds from configuration
_settings = get_settings()
WARNING_THRESHOLD_MB = (
    _settings.memory.warning_threshold_mb
)  # Warn if operation uses >500MB (default)
CRITICAL_THRESHOLD_MB = (
    _settings.memory.critical_threshold_mb
)  # Error if operation uses >1GB (default)


def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB.

    Returns
    -------
        float: Memory usage in megabytes
    """
    try:
        import psutil

        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        # Fallback to tracemalloc if psutil not available
        import tracemalloc

        if not tracemalloc.is_tracing():
            tracemalloc.start()
        current, peak = tracemalloc.get_traced_memory()
        return current / 1024 / 1024


@contextmanager
def memory_guard(
    operation_name: str = "operation",
    warning_threshold_mb: float = WARNING_THRESHOLD_MB,
    critical_threshold_mb: float = CRITICAL_THRESHOLD_MB,
    auto_gc: bool = True,
):
    """Context manager to monitor memory usage during an operation.

    Logs warnings if memory usage exceeds thresholds and optionally
    triggers garbage collection.

    Parameters
    ----------
        operation_name: Name of the operation being monitored
        warning_threshold_mb: Threshold to log warning (MB)
        critical_threshold_mb: Threshold to log error (MB)
        auto_gc: Whether to trigger GC if threshold exceeded

    Yields
    ------
        dict: Memory statistics

    Examples
    --------
        >>> with memory_guard("indexing", warning_threshold_mb=100):
        ...     # Your memory-intensive operation
        ...     nodes = load_large_graph()
    """
    # Collect garbage before measuring
    if auto_gc:
        gc.collect()

    mem_before = get_memory_usage_mb()
    stats = {
        "operation": operation_name,
        "mem_before_mb": mem_before,
        "mem_after_mb": 0,
        "mem_delta_mb": 0,
        "warning_triggered": False,
        "critical_triggered": False,
    }

    try:
        yield stats
    finally:
        # Measure after operation
        mem_after = get_memory_usage_mb()
        mem_delta = mem_after - mem_before

        stats["mem_after_mb"] = mem_after
        stats["mem_delta_mb"] = mem_delta

        # Check thresholds
        if mem_delta > critical_threshold_mb:
            stats["critical_triggered"] = True
            logger.error(
                f"CRITICAL: {operation_name} used {mem_delta:.1f}MB "
                f"(threshold: {critical_threshold_mb}MB). "
                f"Total memory: {mem_after:.1f}MB"
            )
            if auto_gc:
                gc.collect()

        elif mem_delta > warning_threshold_mb:
            stats["warning_triggered"] = True
            logger.warning(
                f"WARNING: {operation_name} used {mem_delta:.1f}MB "
                f"(threshold: {warning_threshold_mb}MB). "
                f"Total memory: {mem_after:.1f}MB"
            )


def memory_profiled(
    warning_threshold_mb: float = WARNING_THRESHOLD_MB,
    critical_threshold_mb: float = CRITICAL_THRESHOLD_MB,
    auto_gc: bool = True,
) -> Callable[[F], F]:
    """Decorator to profile memory usage of a function.

    Parameters
    ----------
        warning_threshold_mb: Threshold to log warning (MB)
        critical_threshold_mb: Threshold to log error (MB)
        auto_gc: Whether to trigger GC if threshold exceeded

    Returns
    -------
        Decorated function that logs memory usage

    Examples
    --------
        >>> @memory_profiled(warning_threshold_mb=100)
        ... def load_graph(path):
        ...     return read_all_edges(path)
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with memory_guard(
                operation_name=func.__name__,
                warning_threshold_mb=warning_threshold_mb,
                critical_threshold_mb=critical_threshold_mb,
                auto_gc=auto_gc,
            ):
                return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def check_memory_available(required_mb: float = 100) -> bool:
    """Check if sufficient memory is available.

    Parameters
    ----------
        required_mb: Required memory in MB

    Returns
    -------
        bool: True if sufficient memory available
    """
    try:
        import psutil

        available_mb = psutil.virtual_memory().available / 1024 / 1024
        return available_mb >= required_mb
    except ImportError:
        # Assume sufficient if we can't check
        return True


def get_memory_stats() -> dict[str, float]:
    """Get comprehensive memory statistics.

    Returns
    -------
        dict: Memory statistics including process RSS, available, and total
    """
    stats = {
        "process_rss_mb": get_memory_usage_mb(),
    }

    try:
        import psutil

        vm = psutil.virtual_memory()
        stats.update(
            {
                "total_mb": vm.total / 1024 / 1024,
                "available_mb": vm.available / 1024 / 1024,
                "percent_used": vm.percent,
            }
        )
    except ImportError:
        pass

    return stats


def log_memory_stats(prefix: str = "Memory"):
    """Log current memory statistics.

    Parameters
    ----------
        prefix: Prefix for log message
    """
    stats = get_memory_stats()
    logger.info(
        f"{prefix}: Process={stats['process_rss_mb']:.1f}MB, "
        f"Available={stats.get('available_mb', 'N/A')}MB"
    )

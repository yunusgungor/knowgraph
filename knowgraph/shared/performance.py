"""Performance monitoring and profiling utilities for KnowGraph.

Provides tools to track and analyze performance bottlenecks.
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single operation."""

    operation: str
    duration: float
    memory_delta: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class PerformanceTracker:
    """Track performance metrics across operations."""

    def __init__(self) -> None:
        """Initialize performance tracker."""
        self.metrics: list[PerformanceMetrics] = []
        self._operation_stack: list[tuple[str, float]] = []

    @contextmanager
    def track(self, operation: str, **metadata: Any):
        """Context manager to track operation performance.

        Usage:
            tracker = PerformanceTracker()
            with tracker.track("query_execution", query_id="123"):
                # Your code here
                pass

        Args:
            operation: Name of the operation
            **metadata: Additional metadata to store

        """
        start_time = time.perf_counter()
        self._operation_stack.append((operation, start_time))

        try:
            yield
        finally:
            end_time = time.perf_counter()
            duration = end_time - start_time

            # Pop from stack
            if self._operation_stack:
                self._operation_stack.pop()

            # Record metric
            metric = PerformanceMetrics(
                operation=operation,
                duration=duration,
                metadata=metadata,
            )
            self.metrics.append(metric)

    def get_summary(self) -> dict[str, Any]:
        """Get performance summary.

        Returns:
            Dictionary with aggregated metrics

        """
        if not self.metrics:
            return {"total_operations": 0}

        operations = {}
        for metric in self.metrics:
            if metric.operation not in operations:
                operations[metric.operation] = {
                    "count": 0,
                    "total_time": 0.0,
                    "min_time": float("inf"),
                    "max_time": 0.0,
                }

            ops = operations[metric.operation]
            ops["count"] += 1
            ops["total_time"] += metric.duration
            ops["min_time"] = min(ops["min_time"], metric.duration)
            ops["max_time"] = max(ops["max_time"], metric.duration)

        # Calculate averages
        for ops in operations.values():
            ops["avg_time"] = ops["total_time"] / ops["count"]

        total_time = sum(m.duration for m in self.metrics)

        return {
            "total_operations": len(self.metrics),
            "total_time": total_time,
            "operations": operations,
        }

    def print_report(self) -> None:
        """Print formatted performance report."""
        summary = self.get_summary()

        print("\n" + "=" * 70)
        print("PERFORMANCE REPORT")
        print("=" * 70)
        print(f"Total Operations: {summary['total_operations']}")
        print(f"Total Time: {summary.get('total_time', 0):.3f}s")
        print("\nOperation Breakdown:")
        print("-" * 70)

        operations = summary.get("operations", {})
        for op_name, stats in sorted(
            operations.items(), key=lambda x: x[1]["total_time"], reverse=True
        ):
            print(f"\n{op_name}:")
            print(f"  Count:      {stats['count']}")
            print(f"  Total:      {stats['total_time']:.3f}s")
            print(f"  Average:    {stats['avg_time']:.3f}s")
            print(f"  Min:        {stats['min_time']:.3f}s")
            print(f"  Max:        {stats['max_time']:.3f}s")

        print("\n" + "=" * 70)

    def clear(self) -> None:
        """Clear all metrics."""
        self.metrics.clear()
        self._operation_stack.clear()


# Global tracker instance
_global_tracker = PerformanceTracker()


def get_global_tracker() -> PerformanceTracker:
    """Get global performance tracker instance."""
    return _global_tracker


@contextmanager
def track_performance(operation: str, **metadata: Any):
    """Convenience function to track performance globally.

    Usage:
        with track_performance("sparse_search", query="test"):
            # Your code here
            pass

    Args:
        operation: Name of the operation
        **metadata: Additional metadata to store

    """
    with _global_tracker.track(operation, **metadata):
        yield

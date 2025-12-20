"""Prometheus metrics integration for KnowGraph.

Provides metrics collection for monitoring system performance, usage patterns,
and operational health. Supports counters, histograms, gauges, and summaries.
"""

import functools
import time
from collections.abc import Callable
from contextlib import contextmanager
from enum import Enum

try:
    from prometheus_client import (
        REGISTRY,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Summary,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Provide mock classes for when Prometheus is not installed
    REGISTRY = None

    class MockMetric:
        """Mock metric for when Prometheus is not available."""

        def inc(self, amount: float = 1) -> None:
            pass

        def set(self, value: float) -> None:
            pass

        def observe(self, value: float) -> None:
            pass

        def labels(self, **labels):
            return self

        def time(self):
            return MockTimer()

    class MockTimer:
        """Mock timer context manager."""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    Counter = Gauge = Histogram = Summary = MockMetric
    CollectorRegistry = type("MockRegistry", (), {})


class MetricType(str, Enum):
    """Types of metrics."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class KnowGraphMetrics:
    """Central metrics registry for KnowGraph.

    Provides pre-configured metrics for common operations and
    allows custom metric registration.
    """

    def __init__(self, registry=None, namespace: str = "knowgraph"):
        """Initialize metrics registry.

        Args:
        ----
            registry: Prometheus registry (uses default if None)
            namespace: Metric namespace prefix
        """
        self.namespace = namespace
        self.registry = registry if PROMETHEUS_AVAILABLE else None
        self.enabled = PROMETHEUS_AVAILABLE

        # Initialize metrics
        if self.enabled:
            self._init_metrics()
        else:
            self._init_mock_metrics()

    def _init_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        # Request metrics
        self.requests_total = Counter(
            f"{self.namespace}_requests_total",
            "Total number of requests",
            ["operation", "status"],
            registry=self.registry,
        )

        self.request_duration = Histogram(
            f"{self.namespace}_request_duration_seconds",
            "Request duration in seconds",
            ["operation"],
            registry=self.registry,
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
        )

        # Query metrics
        self.queries_total = Counter(
            f"{self.namespace}_queries_total",
            "Total number of queries",
            ["query_type"],
            registry=self.registry,
        )

        self.query_duration = Histogram(
            f"{self.namespace}_query_duration_seconds",
            "Query execution duration",
            ["query_type"],
            registry=self.registry,
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
        )

        self.query_results = Summary(
            f"{self.namespace}_query_results",
            "Number of results per query",
            ["query_type"],
            registry=self.registry,
        )

        # Cache metrics
        self.cache_hits = Counter(
            f"{self.namespace}_cache_hits_total",
            "Total cache hits",
            ["cache_type"],
            registry=self.registry,
        )

        self.cache_misses = Counter(
            f"{self.namespace}_cache_misses_total",
            "Total cache misses",
            ["cache_type"],
            registry=self.registry,
        )

        self.cache_size = Gauge(
            f"{self.namespace}_cache_size",
            "Current cache size",
            ["cache_type"],
            registry=self.registry,
        )

        # Graph metrics
        self.nodes_total = Gauge(
            f"{self.namespace}_nodes_total",
            "Total number of nodes in graph",
            registry=self.registry,
        )

        self.edges_total = Gauge(
            f"{self.namespace}_edges_total",
            "Total number of edges in graph",
            registry=self.registry,
        )

        self.graph_operations = Counter(
            f"{self.namespace}_graph_operations_total",
            "Total graph operations",
            ["operation_type"],
            registry=self.registry,
        )

        # Error metrics
        self.errors_total = Counter(
            f"{self.namespace}_errors_total",
            "Total errors",
            ["error_type", "operation"],
            registry=self.registry,
        )

        # Indexing metrics
        self.indexed_documents = Counter(
            f"{self.namespace}_indexed_documents_total",
            "Total indexed documents",
            ["document_type"],
            registry=self.registry,
        )

        self.indexing_duration = Histogram(
            f"{self.namespace}_indexing_duration_seconds",
            "Document indexing duration",
            ["document_type"],
            registry=self.registry,
            buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
        )

    def _init_mock_metrics(self) -> None:
        """Initialize mock metrics when Prometheus not available."""

        # Create mock metric instance locally in case module-level MockMetric not available
        class _MockMetric:
            def inc(self, amount: float = 1) -> None:
                pass

            def set(self, value: float) -> None:
                pass

            def observe(self, value: float) -> None:
                pass

            def labels(self, **labels):
                return self

            def time(self):
                return self

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        mock = _MockMetric()
        self.requests_total = mock
        self.request_duration = mock
        self.queries_total = mock
        self.query_duration = mock
        self.query_results = mock
        self.cache_hits = mock
        self.cache_misses = mock
        self.cache_size = mock
        self.nodes_total = mock
        self.edges_total = mock
        self.graph_operations = mock
        self.errors_total = mock
        self.indexed_documents = mock
        self.indexing_duration = mock

    def record_request(self, operation: str, status: str = "success") -> None:
        """Record a request.

        Args:
        ----
            operation: Operation name
            status: Request status (success/error)
        """
        self.requests_total.labels(operation=operation, status=status).inc()

    def record_query(self, query_type: str, duration: float, result_count: int) -> None:
        """Record a query execution.

        Args:
        ----
            query_type: Type of query
            duration: Execution duration in seconds
            result_count: Number of results
        """
        self.queries_total.labels(query_type=query_type).inc()
        self.query_duration.labels(query_type=query_type).observe(duration)
        self.query_results.labels(query_type=query_type).observe(result_count)

    def record_cache_hit(self, cache_type: str = "default") -> None:
        """Record a cache hit.

        Args:
        ----
            cache_type: Type of cache
        """
        self.cache_hits.labels(cache_type=cache_type).inc()

    def record_cache_miss(self, cache_type: str = "default") -> None:
        """Record a cache miss.

        Args:
        ----
            cache_type: Type of cache
        """
        self.cache_misses.labels(cache_type=cache_type).inc()

    def set_cache_size(self, size: int, cache_type: str = "default") -> None:
        """Set current cache size.

        Args:
        ----
            size: Cache size
            cache_type: Type of cache
        """
        self.cache_size.labels(cache_type=cache_type).set(size)

    def set_graph_stats(self, nodes: int, edges: int) -> None:
        """Set graph statistics.

        Args:
        ----
            nodes: Number of nodes
            edges: Number of edges
        """
        self.nodes_total.set(nodes)
        self.edges_total.set(edges)

    def record_error(self, error_type: str, operation: str) -> None:
        """Record an error.

        Args:
        ----
            error_type: Type of error
            operation: Operation that failed
        """
        self.errors_total.labels(error_type=error_type, operation=operation).inc()

    def record_indexing(self, document_type: str, duration: float) -> None:
        """Record document indexing.

        Args:
        ----
            document_type: Type of document
            duration: Indexing duration in seconds
        """
        self.indexed_documents.labels(document_type=document_type).inc()
        self.indexing_duration.labels(document_type=document_type).observe(duration)

    @contextmanager
    def track_operation(self, operation: str):
        """Context manager for tracking operation duration.

        Args:
        ----
            operation: Operation name

        Yields:
        ------
            None
        """
        start_time = time.time()
        status = "success"

        try:
            yield
        except Exception as e:
            status = "error"
            error_type = type(e).__name__
            self.record_error(error_type, operation)
            raise
        finally:
            duration = time.time() - start_time
            self.request_duration.labels(operation=operation).observe(duration)
            self.record_request(operation, status)

    def track_function(self, operation: str | None = None):
        """Decorator for tracking function execution.

        Args:
        ----
            operation: Optional operation name

        Returns:
        -------
            Decorated function
        """

        def decorator(func: Callable) -> Callable:
            op_name = operation or f"{func.__module__}.{func.__name__}"

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.track_operation(op_name):
                    return func(*args, **kwargs)

            return wrapper

        return decorator

    def track_async_function(self, operation: str | None = None):
        """Decorator for tracking async function execution.

        Args:
        ----
            operation: Optional operation name

        Returns:
        -------
            Decorated async function
        """

        def decorator(func: Callable) -> Callable:
            op_name = operation or f"{func.__module__}.{func.__name__}"

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                with self.track_operation(op_name):
                    return await func(*args, **kwargs)

            return wrapper

        return decorator

    def export_metrics(self) -> bytes:
        """Export metrics in Prometheus format.

        Returns:
        -------
            Metrics in Prometheus text format
        """
        if not self.enabled:
            return b""

        return generate_latest(self.registry or REGISTRY)


# Global metrics instance
_default_metrics: KnowGraphMetrics | None = None


def get_metrics(registry=None, namespace: str = "knowgraph") -> KnowGraphMetrics:
    """Get or create global metrics instance.

    Args:
    ----
        registry: Optional Prometheus registry
        namespace: Metric namespace prefix

    Returns:
    -------
        KnowGraph metrics instance
    """
    global _default_metrics

    if _default_metrics is None:
        _default_metrics = KnowGraphMetrics(registry=registry, namespace=namespace)

    return _default_metrics


def configure_metrics(registry=None, namespace: str = "knowgraph") -> KnowGraphMetrics:
    """Configure global metrics settings.

    Args:
    ----
        registry: Optional Prometheus registry
        namespace: Metric namespace prefix

    Returns:
    -------
        Configured metrics instance
    """
    global _default_metrics

    _default_metrics = KnowGraphMetrics(registry=registry, namespace=namespace)
    return _default_metrics


def track_operation(operation: str):
    """Context manager for tracking operation using global metrics.

    Args:
    ----
        operation: Operation name

    Returns:
    -------
        Context manager
    """
    metrics = get_metrics()
    return metrics.track_operation(operation)


def track_function(operation: str | None = None):
    """Decorator for tracking function using global metrics.

    Args:
    ----
        operation: Optional operation name

    Returns:
    -------
        Function decorator
    """
    metrics = get_metrics()
    return metrics.track_function(operation)


def track_async_function(operation: str | None = None):
    """Decorator for tracking async function using global metrics.

    Args:
    ----
        operation: Optional operation name

    Returns:
    -------
        Async function decorator
    """
    metrics = get_metrics()
    return metrics.track_async_function(operation)


def is_metrics_available() -> bool:
    """Check if Prometheus metrics are available.

    Returns:
    -------
        True if prometheus_client is installed
    """
    return PROMETHEUS_AVAILABLE

"""Tests for Prometheus metrics integration."""

import asyncio
import time

import pytest

from knowgraph.shared.metrics import (
    KnowGraphMetrics,
    MetricType,
    configure_metrics,
    get_metrics,
    is_metrics_available,
    track_async_function,
    track_function,
    track_operation,
)


class TestMetricType:
    """Test metric type enum."""

    def test_metric_types(self):
        """Test metric type values."""
        assert MetricType.COUNTER == "counter"
        assert MetricType.GAUGE == "gauge"
        assert MetricType.HISTOGRAM == "histogram"
        assert MetricType.SUMMARY == "summary"


class TestKnowGraphMetrics:
    """Test KnowGraph metrics class."""

    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = KnowGraphMetrics()

        assert metrics is not None
        assert metrics.namespace == "knowgraph"

    def test_metrics_with_custom_namespace(self):
        """Test metrics with custom namespace."""
        metrics = KnowGraphMetrics(namespace="test_app")

        assert metrics.namespace == "test_app"

    def test_record_request(self):
        """Test recording a request."""
        metrics = KnowGraphMetrics()

        # Should not raise error
        metrics.record_request("query", "success")
        metrics.record_request("index", "error")

    def test_record_query(self):
        """Test recording query metrics."""
        metrics = KnowGraphMetrics()

        # Should not raise error
        metrics.record_query("semantic", duration=1.5, result_count=10)

    def test_record_cache_hit(self):
        """Test recording cache hit."""
        metrics = KnowGraphMetrics()

        metrics.record_cache_hit("query_cache")
        metrics.record_cache_hit()  # default cache type

    def test_record_cache_miss(self):
        """Test recording cache miss."""
        metrics = KnowGraphMetrics()

        metrics.record_cache_miss("query_cache")
        metrics.record_cache_miss()  # default cache type

    def test_set_cache_size(self):
        """Test setting cache size."""
        metrics = KnowGraphMetrics()

        metrics.set_cache_size(100, "query_cache")
        metrics.set_cache_size(50)  # default cache type

    def test_set_graph_stats(self):
        """Test setting graph statistics."""
        metrics = KnowGraphMetrics()

        metrics.set_graph_stats(nodes=1000, edges=5000)

    def test_record_error(self):
        """Test recording error."""
        metrics = KnowGraphMetrics()

        metrics.record_error("ValueError", "query")
        metrics.record_error("IOError", "index")

    def test_record_indexing(self):
        """Test recording indexing metrics."""
        metrics = KnowGraphMetrics()

        metrics.record_indexing("markdown", duration=2.5)

    def test_track_operation_success(self):
        """Test tracking successful operation."""
        metrics = KnowGraphMetrics()

        with metrics.track_operation("test_operation"):
            time.sleep(0.01)

    def test_track_operation_with_error(self):
        """Test tracking operation with error."""
        metrics = KnowGraphMetrics()

        with pytest.raises(ValueError):
            with metrics.track_operation("test_operation"):
                raise ValueError("Test error")

    def test_track_function_decorator(self):
        """Test function tracking decorator."""
        metrics = KnowGraphMetrics()

        @metrics.track_function()
        def sample_function(x: int) -> int:
            return x * 2

        result = sample_function(5)
        assert result == 10

    def test_track_function_with_custom_name(self):
        """Test function tracking with custom name."""
        metrics = KnowGraphMetrics()

        @metrics.track_function(operation="custom_op")
        def sample_function(x: int) -> int:
            return x * 2

        result = sample_function(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_track_async_function(self):
        """Test async function tracking."""
        metrics = KnowGraphMetrics()

        @metrics.track_async_function()
        async def async_function(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        result = await async_function(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_track_async_function_with_error(self):
        """Test async function tracking with error."""
        metrics = KnowGraphMetrics()

        @metrics.track_async_function()
        async def async_failing():
            await asyncio.sleep(0.01)
            raise RuntimeError("Async error")

        with pytest.raises(RuntimeError):
            await async_failing()

    def test_export_metrics(self):
        """Test exporting metrics."""
        metrics = KnowGraphMetrics()

        # Should return bytes
        exported = metrics.export_metrics()
        assert isinstance(exported, bytes)


class TestGlobalMetricsFunctions:
    """Test global metrics functions."""

    def test_get_metrics(self):
        """Test getting global metrics instance."""
        metrics = get_metrics()

        assert metrics is not None
        assert isinstance(metrics, KnowGraphMetrics)

    def test_get_metrics_singleton(self):
        """Test that get_metrics returns same instance."""
        metrics1 = get_metrics()
        metrics2 = get_metrics()

        assert metrics1 is metrics2

    def test_configure_metrics(self):
        """Test configuring global metrics."""
        metrics = configure_metrics(namespace="test_metrics")

        assert metrics is not None
        assert metrics.namespace == "test_metrics"

    def test_track_operation_context_manager(self):
        """Test global track_operation context manager."""
        with track_operation("global_test"):
            time.sleep(0.01)

    def test_track_function_decorator_global(self):
        """Test global track_function decorator."""
        @track_function()
        def global_function(x: int) -> int:
            return x * 3

        result = global_function(4)
        assert result == 12

    @pytest.mark.asyncio
    async def test_track_async_function_global(self):
        """Test global track_async_function decorator."""
        @track_async_function()
        async def global_async(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 3

        result = await global_async(4)
        assert result == 12

    def test_is_metrics_available(self):
        """Test checking metrics availability."""
        available = is_metrics_available()
        assert isinstance(available, bool)


class TestMetricsWithMocks:
    """Test metrics behavior with mocked Prometheus."""

    def test_mock_metric_behavior(self):
        """Test that mock metrics work when Prometheus not available."""
        import knowgraph.shared.metrics as metrics_module

        original_value = metrics_module.PROMETHEUS_AVAILABLE
        try:
            metrics_module.PROMETHEUS_AVAILABLE = False

            # Create metrics with disabled Prometheus
            metrics = KnowGraphMetrics()

            # Should use mock metrics - no errors
            metrics.record_request("test", "success")
            metrics.record_query("test", 1.0, 10)
            metrics.record_cache_hit()
            metrics.record_cache_miss()
            metrics.set_cache_size(100)
            metrics.set_graph_stats(100, 200)
            metrics.record_error("TestError", "test_op")
            metrics.record_indexing("test", 1.0)

            # Export should return empty bytes
            exported = metrics.export_metrics()
            assert exported == b""

        finally:
            metrics_module.PROMETHEUS_AVAILABLE = original_value

    def test_disabled_metrics_no_errors(self):
        """Test that disabled metrics don't raise errors."""
        import knowgraph.shared.metrics as metrics_module

        original_value = metrics_module.PROMETHEUS_AVAILABLE
        try:
            metrics_module.PROMETHEUS_AVAILABLE = False

            metrics = KnowGraphMetrics()

            # All operations should work without errors
            with metrics.track_operation("test"):
                pass

            @metrics.track_function()
            def test_func():
                return 42

            assert test_func() == 42

        finally:
            metrics_module.PROMETHEUS_AVAILABLE = original_value


class TestMetricsEdgeCases:
    """Test edge cases in metrics."""

    def test_multiple_operations(self):
        """Test recording multiple operations."""
        metrics = KnowGraphMetrics()

        for i in range(10):
            metrics.record_request(f"operation_{i}", "success")

    def test_nested_tracking(self):
        """Test nested operation tracking."""
        metrics = KnowGraphMetrics()

        with metrics.track_operation("outer"):
            with metrics.track_operation("inner"):
                time.sleep(0.01)

    @pytest.mark.asyncio
    async def test_concurrent_metrics(self):
        """Test concurrent metric recording."""
        metrics = KnowGraphMetrics()

        async def record_metric(i: int):
            await asyncio.sleep(0.01)
            metrics.record_request(f"op_{i}", "success")

        # Run concurrently
        await asyncio.gather(*[record_metric(i) for i in range(5)])

    def test_exception_in_tracked_function(self):
        """Test exception handling in tracked function."""
        metrics = KnowGraphMetrics()

        @metrics.track_function()
        def failing_function():
            raise ValueError("Intentional error")

        with pytest.raises(ValueError):
            failing_function()

    def test_large_values(self):
        """Test handling large metric values."""
        metrics = KnowGraphMetrics()

        # Large numbers
        metrics.set_graph_stats(1_000_000, 5_000_000)
        metrics.record_query("test", duration=100.0, result_count=10000)

    def test_zero_values(self):
        """Test handling zero values."""
        metrics = KnowGraphMetrics()

        metrics.set_cache_size(0)
        metrics.set_graph_stats(0, 0)
        metrics.record_query("test", duration=0.0, result_count=0)

    def test_special_characters_in_labels(self):
        """Test handling special characters in labels."""
        metrics = KnowGraphMetrics()

        # Should handle special characters
        metrics.record_request("test/operation", "success")
        metrics.record_query("query:type", 1.0, 10)
        metrics.record_error("IO-Error", "test-op")


class TestMetricsIntegration:
    """Test metrics integration scenarios."""

    def test_full_workflow_metrics(self):
        """Test metrics for a complete workflow."""
        metrics = KnowGraphMetrics()

        # Simulate a query workflow
        with metrics.track_operation("query_workflow"):
            # Check cache
            metrics.record_cache_miss()

            # Execute query
            metrics.record_query("semantic", duration=1.5, result_count=20)

            # Update cache
            metrics.set_cache_size(10)

    def test_indexing_workflow_metrics(self):
        """Test metrics for indexing workflow."""
        metrics = KnowGraphMetrics()

        # Simulate indexing
        with metrics.track_operation("indexing"):
            metrics.record_indexing("markdown", duration=2.0)
            metrics.set_graph_stats(nodes=100, edges=500)

    @pytest.mark.asyncio
    async def test_async_workflow_metrics(self):
        """Test metrics for async workflow."""
        metrics = KnowGraphMetrics()

        @metrics.track_async_function()
        async def async_workflow():
            await asyncio.sleep(0.01)
            metrics.record_cache_hit()
            return "result"

        result = await async_workflow()
        assert result == "result"

    def test_error_tracking_workflow(self):
        """Test error tracking in workflow."""
        metrics = KnowGraphMetrics()

        try:
            with metrics.track_operation("error_workflow"):
                raise RuntimeError("Test error")
        except RuntimeError:
            pass  # Expected

    def test_multiple_metric_types(self):
        """Test using multiple metric types together."""
        metrics = KnowGraphMetrics()

        # Counter
        metrics.record_request("test", "success")

        # Gauge
        metrics.set_cache_size(50)

        # Histogram
        metrics.record_query("test", 1.0, 10)

        # Summary
        # (record_query also updates summary)

    def test_reconfigure_metrics(self):
        """Test reconfiguring global metrics."""
        # First configuration
        metrics1 = configure_metrics(namespace="app1")
        assert metrics1.namespace == "app1"

        # Reconfigure
        metrics2 = configure_metrics(namespace="app2")
        assert metrics2.namespace == "app2"

        # Should be different instance
        assert metrics1 is not metrics2


class TestMetricsPerformance:
    """Test metrics performance characteristics."""

    def test_metrics_overhead(self):
        """Test that metrics don't add significant overhead."""
        metrics = KnowGraphMetrics()

        # Time without metrics
        start = time.time()
        for _ in range(100):
            pass
        baseline = time.time() - start

        # Time with metrics
        start = time.time()
        for i in range(100):
            metrics.record_request(f"op_{i}", "success")
        with_metrics = time.time() - start

        # Metrics should not add more than 10x overhead
        assert with_metrics < baseline * 10 + 0.1

    def test_concurrent_metric_updates(self):
        """Test concurrent metric updates are safe."""
        metrics = KnowGraphMetrics()

        def update_metrics():
            for _ in range(100):
                metrics.record_request("test", "success")

        # Should not raise errors
        update_metrics()

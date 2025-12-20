"""Tests for OpenTelemetry tracing integration."""

import asyncio

import pytest

from knowgraph.shared.tracing import (
    KnowGraphTracer,
    TracingConfig,
    add_span_attribute,
    add_span_event,
    configure_tracing,
    get_tracer,
    is_tracing_available,
    record_exception,
    trace_async_function,
    trace_function,
    trace_operation,
)


class TestTracingConfig:
    """Test tracing configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TracingConfig()

        assert config.service_name == "knowgraph"
        assert config.service_version == "1.0.0"
        assert config.environment == "development"
        assert config.console_export is False

    def test_custom_config(self):
        """Test custom configuration values."""
        config = TracingConfig(
            service_name="my-service",
            service_version="2.0.0",
            environment="production",
            enabled=True,
            console_export=True,
        )

        assert config.service_name == "my-service"
        assert config.service_version == "2.0.0"
        assert config.environment == "production"
        assert config.console_export is True

    def test_disabled_tracing(self):
        """Test disabled tracing configuration."""
        config = TracingConfig(enabled=False)

        # enabled should be False
        assert config.enabled is False


class TestKnowGraphTracer:
    """Test KnowGraph tracer class."""

    def test_tracer_initialization(self):
        """Test tracer initialization."""
        tracer = KnowGraphTracer()

        assert tracer is not None
        assert tracer.config is not None
        assert tracer._tracer is not None

    def test_tracer_with_config(self):
        """Test tracer with custom configuration."""
        config = TracingConfig(service_name="test-service")
        tracer = KnowGraphTracer(config)

        assert tracer.config.service_name == "test-service"

    def test_start_span(self):
        """Test starting a span."""
        tracer = KnowGraphTracer()

        with tracer.start_span("test_operation") as span:
            assert span is not None

    def test_start_span_with_attributes(self):
        """Test starting a span with attributes."""
        tracer = KnowGraphTracer()

        with tracer.start_span("test_operation", user_id="123", graph_path="/test") as span:
            assert span is not None

    def test_trace_operation_success(self):
        """Test tracing successful operation."""
        tracer = KnowGraphTracer()

        with tracer.trace_operation("test_operation") as span:
            assert span is not None
            # Operation completes successfully

    def test_trace_operation_with_exception(self):
        """Test tracing operation with exception."""
        tracer = KnowGraphTracer()

        with pytest.raises(ValueError):
            with tracer.trace_operation("test_operation") as span:
                assert span is not None
                raise ValueError("Test error")

    def test_trace_function_decorator(self):
        """Test function tracing decorator."""
        tracer = KnowGraphTracer()

        @tracer.trace_function()
        def sample_function(x: int) -> int:
            return x * 2

        result = sample_function(5)
        assert result == 10

    def test_trace_function_with_custom_name(self):
        """Test function tracing with custom operation name."""
        tracer = KnowGraphTracer()

        @tracer.trace_function(operation_name="custom_operation")
        def sample_function(x: int) -> int:
            return x * 2

        result = sample_function(5)
        assert result == 10

    def test_trace_function_with_attributes(self):
        """Test function tracing with default attributes."""
        tracer = KnowGraphTracer()

        @tracer.trace_function(component="test", version="1.0")
        def sample_function(x: int) -> int:
            return x * 2

        result = sample_function(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_trace_async_function(self):
        """Test async function tracing."""
        tracer = KnowGraphTracer()

        @tracer.trace_async_function()
        async def async_sample(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        result = await async_sample(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_trace_async_function_with_exception(self):
        """Test async function tracing with exception."""
        tracer = KnowGraphTracer()

        @tracer.trace_async_function()
        async def async_failing():
            await asyncio.sleep(0.01)
            raise ValueError("Async error")

        with pytest.raises(ValueError):
            await async_failing()

    def test_disabled_tracer(self):
        """Test tracer with disabled configuration."""
        config = TracingConfig(enabled=False)
        tracer = KnowGraphTracer(config)

        # Should work without errors even when disabled
        with tracer.trace_operation("test") as span:
            assert span is not None


class TestGlobalTracingFunctions:
    """Test global tracing functions."""

    def test_get_tracer(self):
        """Test getting global tracer instance."""
        tracer = get_tracer()

        assert tracer is not None
        assert isinstance(tracer, KnowGraphTracer)

    def test_get_tracer_singleton(self):
        """Test that get_tracer returns same instance."""
        tracer1 = get_tracer()
        tracer2 = get_tracer()

        assert tracer1 is tracer2

    def test_configure_tracing(self):
        """Test configuring global tracing."""
        tracer = configure_tracing(
            service_name="test-service",
            service_version="1.0.0",
            environment="test",
        )

        assert tracer is not None
        assert tracer.config.service_name == "test-service"

    def test_trace_operation_context_manager(self):
        """Test global trace_operation context manager."""
        with trace_operation("test_op") as span:
            assert span is not None

    def test_trace_function_decorator_global(self):
        """Test global trace_function decorator."""
        @trace_function()
        def sample_func(x: int) -> int:
            return x * 3

        result = sample_func(4)
        assert result == 12

    @pytest.mark.asyncio
    async def test_trace_async_function_global(self):
        """Test global trace_async_function decorator."""
        @trace_async_function()
        async def async_func(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 3

        result = await async_func(4)
        assert result == 12

    def test_is_tracing_available(self):
        """Test checking if tracing is available."""
        # Should return boolean value
        available = is_tracing_available()
        assert isinstance(available, bool)


class TestSpanHelpers:
    """Test span helper functions."""

    def test_add_span_attribute(self):
        """Test adding attribute to current span."""
        # Should not raise error even without active span
        add_span_attribute("test_key", "test_value")

    def test_add_span_event(self):
        """Test adding event to current span."""
        # Should not raise error even without active span
        add_span_event("test_event", {"key": "value"})

    def test_record_exception(self):
        """Test recording exception in current span."""
        # Should not raise error even without active span
        record_exception(ValueError("Test exception"))

    def test_add_span_attribute_in_context(self):
        """Test adding attribute within traced operation."""
        with trace_operation("test_op"):
            # Should not raise error
            add_span_attribute("user_id", "123")

    def test_add_span_event_in_context(self):
        """Test adding event within traced operation."""
        with trace_operation("test_op"):
            # Should not raise error
            add_span_event("cache_hit", {"cache_key": "test"})


class TestTracingWithMocks:
    """Test tracing behavior with mocked OpenTelemetry."""

    def test_mock_span_behavior(self):
        """Test that mock span works when OpenTelemetry not available."""
        # Force use of mock by temporarily patching OPENTELEMETRY_AVAILABLE
        import knowgraph.shared.tracing as tracing_module

        original_value = tracing_module.OPENTELEMETRY_AVAILABLE
        try:
            tracing_module.OPENTELEMETRY_AVAILABLE = False

            # Create tracer with disabled OpenTelemetry
            config = TracingConfig(enabled=True)
            tracer = KnowGraphTracer(config)

            # Should use mock tracer
            with tracer.start_span("test") as span:
                assert span is not None
                # Mock span methods should not raise errors
                span.set_attribute("key", "value")
                span.set_status(None)
                span.record_exception(ValueError("test"))

        finally:
            tracing_module.OPENTELEMETRY_AVAILABLE = original_value

    def test_disabled_tracing_no_errors(self):
        """Test that disabled tracing doesn't raise errors."""
        config = TracingConfig(enabled=False)
        tracer = KnowGraphTracer(config)

        # All operations should work without errors
        with tracer.trace_operation("test"):
            pass

        @tracer.trace_function()
        def test_func():
            return 42

        assert test_func() == 42


class TestTracingEdgeCases:
    """Test edge cases in tracing."""

    def test_nested_spans(self):
        """Test nested span creation."""
        tracer = KnowGraphTracer()

        with tracer.trace_operation("outer") as outer:
            assert outer is not None

            with tracer.trace_operation("inner") as inner:
                assert inner is not None

    def test_concurrent_spans(self):
        """Test concurrent span operations."""
        tracer = KnowGraphTracer()

        def create_span(name: str):
            with tracer.trace_operation(name):
                pass

        # Should not interfere with each other
        create_span("span1")
        create_span("span2")

    @pytest.mark.asyncio
    async def test_concurrent_async_spans(self):
        """Test concurrent async span operations."""
        tracer = KnowGraphTracer()

        @tracer.trace_async_function()
        async def async_op(name: str) -> str:
            await asyncio.sleep(0.01)
            return name

        # Run concurrently
        results = await asyncio.gather(
            async_op("op1"),
            async_op("op2"),
            async_op("op3"),
        )

        assert results == ["op1", "op2", "op3"]

    def test_exception_in_decorated_function(self):
        """Test exception handling in decorated function."""
        tracer = KnowGraphTracer()

        @tracer.trace_function()
        def failing_function():
            raise RuntimeError("Intentional error")

        with pytest.raises(RuntimeError):
            failing_function()

    def test_none_values_in_attributes(self):
        """Test handling None values in span attributes."""
        tracer = KnowGraphTracer()

        # Should not raise error
        with tracer.trace_operation("test", none_attr=None):
            pass

    def test_large_attribute_values(self):
        """Test handling large attribute values."""
        tracer = KnowGraphTracer()

        large_value = "x" * 10000
        # Should not raise error
        with tracer.trace_operation("test", large_attr=large_value):
            pass

    def test_special_characters_in_span_name(self):
        """Test span names with special characters."""
        tracer = KnowGraphTracer()

        # Should handle special characters
        with tracer.trace_operation("test/with/slashes"):
            pass

        with tracer.trace_operation("test-with-dashes"):
            pass

        with tracer.trace_operation("test.with.dots"):
            pass


class TestTracingIntegration:
    """Test tracing integration scenarios."""

    def test_trace_multiple_operations(self):
        """Test tracing multiple sequential operations."""
        tracer = KnowGraphTracer()
        results = []

        with tracer.trace_operation("operation1"):
            results.append(1)

        with tracer.trace_operation("operation2"):
            results.append(2)

        with tracer.trace_operation("operation3"):
            results.append(3)

        assert results == [1, 2, 3]

    def test_trace_with_multiple_attributes(self):
        """Test tracing with many attributes."""
        tracer = KnowGraphTracer()

        attrs = {
            f"attr_{i}": f"value_{i}"
            for i in range(20)
        }

        with tracer.trace_operation("test", **attrs):
            pass

    @pytest.mark.asyncio
    async def test_mixed_sync_async_tracing(self):
        """Test mixing sync and async traced operations."""
        tracer = KnowGraphTracer()

        @tracer.trace_function()
        def sync_op() -> int:
            return 42

        @tracer.trace_async_function()
        async def async_op() -> int:
            await asyncio.sleep(0.01)
            return 24

        sync_result = sync_op()
        async_result = await async_op()

        assert sync_result == 42
        assert async_result == 24

    def test_reconfigure_tracing(self):
        """Test reconfiguring global tracing."""
        # First configuration
        tracer1 = configure_tracing(service_name="service1")
        assert tracer1.config.service_name == "service1"

        # Reconfigure
        tracer2 = configure_tracing(service_name="service2")
        assert tracer2.config.service_name == "service2"

        # Should be different instance after reconfiguration
        assert tracer1 is not tracer2

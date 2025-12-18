"""OpenTelemetry tracing integration for KnowGraph.

Provides distributed tracing capabilities for tracking requests and operations
across the system. Supports automatic instrumentation and custom spans.
"""

import functools
import time
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.trace import Status, StatusCode

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False

    # Provide mock classes for when OpenTelemetry is not installed
    class MockSpan:
        """Mock span for when OpenTelemetry is not available."""

        def set_attribute(self, key: str, value: Any) -> None:
            pass

        def set_status(self, status: Any) -> None:
            pass

        def record_exception(self, exception: Exception) -> None:
            pass

        def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    class MockTracer:
        """Mock tracer for when OpenTelemetry is not available."""

        def start_as_current_span(self, name: str, **kwargs):
            return MockSpan()

        def start_span(self, name: str, **kwargs):
            return MockSpan()


class TracingConfig:
    """Configuration for OpenTelemetry tracing.

    Attributes
    ----------
        service_name: Name of the service
        service_version: Version of the service
        environment: Deployment environment (dev, staging, prod)
        enabled: Whether tracing is enabled
        console_export: Whether to export to console
    """

    def __init__(
        self,
        service_name: str = "knowgraph",
        service_version: str = "1.0.0",
        environment: str = "development",
        enabled: bool = True,
        console_export: bool = False,
    ):
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self.enabled = enabled and OPENTELEMETRY_AVAILABLE
        self.console_export = console_export


class KnowGraphTracer:
    """Main tracing interface for KnowGraph.

    Provides methods for creating spans, tracking operations,
    and managing distributed traces.
    """

    def __init__(self, config: TracingConfig | None = None):
        """Initialize KnowGraph tracer.

        Args:
        ----
            config: Tracing configuration
        """
        self.config = config or TracingConfig()
        self._tracer = None

        if self.config.enabled and OPENTELEMETRY_AVAILABLE:
            self._setup_tracer()
        else:
            self._tracer = MockTracer()

    def _setup_tracer(self) -> None:
        """Set up OpenTelemetry tracer with configuration."""
        if not OPENTELEMETRY_AVAILABLE:
            return

        # Create resource with service information
        resource = Resource.create(
            {
                "service.name": self.config.service_name,
                "service.version": self.config.service_version,
                "deployment.environment": self.config.environment,
            }
        )

        # Create tracer provider
        provider = TracerProvider(resource=resource)

        # Add console exporter if enabled
        if self.config.console_export:
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))

        # Set as global tracer provider
        trace.set_tracer_provider(provider)

        # Get tracer instance
        self._tracer = trace.get_tracer(
            instrumenting_module_name=__name__,
            instrumenting_library_version=self.config.service_version,
        )

    def start_span(self, name: str, **attributes):
        """Start a new span.

        Args:
        ----
            name: Span name
            **attributes: Span attributes as key-value pairs

        Returns:
        -------
            Span context manager
        """
        assert self._tracer is not None
        span = self._tracer.start_as_current_span(name)

        # Add attributes if OpenTelemetry is available
        if OPENTELEMETRY_AVAILABLE and hasattr(span, "set_attribute"):
            for key, value in attributes.items():
                span.set_attribute(key, str(value))

        return span

    @contextmanager
    def trace_operation(self, operation_name: str, **attributes):
        """Context manager for tracing an operation.

        Args:
        ----
            operation_name: Name of the operation
            **attributes: Additional span attributes

        Yields:
        ------
            Span object for adding additional attributes
        """
        with self.start_span(operation_name, **attributes) as span:
            start_time = time.time()
            try:
                yield span
            except Exception as e:
                # Record exception in span
                if OPENTELEMETRY_AVAILABLE and hasattr(span, "record_exception"):
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                raise
            finally:
                # Record duration
                duration = time.time() - start_time
                if OPENTELEMETRY_AVAILABLE and hasattr(span, "set_attribute"):
                    span.set_attribute("duration_seconds", duration)

    def trace_function(self, operation_name: str | None = None, **default_attributes):
        """Decorator for tracing function calls.

        Args:
        ----
            operation_name: Optional custom operation name
            **default_attributes: Default attributes to add to span

        Returns:
        -------
            Decorated function
        """

        def decorator(func: Callable) -> Callable:
            op_name = operation_name or f"{func.__module__}.{func.__name__}"

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with self.trace_operation(op_name, **default_attributes) as span:
                    # Add function arguments as attributes
                    if OPENTELEMETRY_AVAILABLE and hasattr(span, "set_attribute"):
                        span.set_attribute("function.name", func.__name__)
                        span.set_attribute("function.module", func.__module__)

                    result = func(*args, **kwargs)
                    return result

            return wrapper

        return decorator

    def trace_async_function(self, operation_name: str | None = None, **default_attributes):
        """Decorator for tracing async function calls.

        Args:
        ----
            operation_name: Optional custom operation name
            **default_attributes: Default attributes to add to span

        Returns:
        -------
            Decorated async function
        """

        def decorator(func: Callable) -> Callable:
            op_name = operation_name or f"{func.__module__}.{func.__name__}"

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                with self.trace_operation(op_name, **default_attributes) as span:
                    # Add function arguments as attributes
                    if OPENTELEMETRY_AVAILABLE and hasattr(span, "set_attribute"):
                        span.set_attribute("function.name", func.__name__)
                        span.set_attribute("function.module", func.__module__)

                    result = await func(*args, **kwargs)
                    return result

            return wrapper

        return decorator


# Global tracer instance
_default_tracer: KnowGraphTracer | None = None


def get_tracer(config: TracingConfig | None = None) -> KnowGraphTracer:
    """Get or create global tracer instance.

    Args:
    ----
        config: Optional tracing configuration

    Returns:
    -------
        KnowGraph tracer instance
    """
    global _default_tracer

    if _default_tracer is None:
        _default_tracer = KnowGraphTracer(config)

    return _default_tracer


def configure_tracing(
    service_name: str = "knowgraph",
    service_version: str = "1.0.0",
    environment: str = "development",
    enabled: bool = True,
    console_export: bool = False,
) -> KnowGraphTracer:
    """Configure global tracing settings.

    Args:
    ----
        service_name: Name of the service
        service_version: Version of the service
        environment: Deployment environment
        enabled: Whether tracing is enabled
        console_export: Whether to export to console

    Returns:
    -------
        Configured tracer instance
    """
    global _default_tracer

    config = TracingConfig(
        service_name=service_name,
        service_version=service_version,
        environment=environment,
        enabled=enabled,
        console_export=console_export,
    )

    _default_tracer = KnowGraphTracer(config)
    return _default_tracer


def trace_operation(operation_name: str, **attributes):
    """Context manager for tracing an operation using global tracer.

    Args:
    ----
        operation_name: Name of the operation
        **attributes: Additional span attributes

    Returns:
    -------
        Context manager for the traced operation
    """
    tracer = get_tracer()
    return tracer.trace_operation(operation_name, **attributes)


def trace_function(operation_name: str | None = None, **default_attributes):
    """Decorator for tracing function calls using global tracer.

    Args:
    ----
        operation_name: Optional custom operation name
        **default_attributes: Default attributes to add to span

    Returns:
    -------
        Function decorator
    """
    tracer = get_tracer()
    return tracer.trace_function(operation_name, **default_attributes)


def trace_async_function(operation_name: str | None = None, **default_attributes):
    """Decorator for tracing async function calls using global tracer.

    Args:
    ----
        operation_name: Optional custom operation name
        **default_attributes: Default attributes to add to span

    Returns:
    -------
        Async function decorator
    """
    tracer = get_tracer()
    return tracer.trace_async_function(operation_name, **default_attributes)


def add_span_attribute(key: str, value: Any) -> None:
    """Add attribute to current span.

    Args:
    ----
        key: Attribute key
        value: Attribute value
    """
    if not OPENTELEMETRY_AVAILABLE:
        return

    current_span = trace.get_current_span()
    if current_span and hasattr(current_span, "set_attribute"):
        current_span.set_attribute(key, str(value))


def add_span_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    """Add event to current span.

    Args:
    ----
        name: Event name
        attributes: Event attributes
    """
    if not OPENTELEMETRY_AVAILABLE:
        return

    current_span = trace.get_current_span()
    if current_span and hasattr(current_span, "add_event"):
        current_span.add_event(name, attributes or {})


def record_exception(exception: Exception) -> None:
    """Record exception in current span.

    Args:
    ----
        exception: Exception to record
    """
    if not OPENTELEMETRY_AVAILABLE:
        return

    current_span = trace.get_current_span()
    if current_span and hasattr(current_span, "record_exception"):
        current_span.record_exception(exception)


def is_tracing_available() -> bool:
    """Check if OpenTelemetry is available.

    Returns:
    -------
        True if OpenTelemetry is installed and available
    """
    return OPENTELEMETRY_AVAILABLE

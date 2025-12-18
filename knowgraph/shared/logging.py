"""Structured logging system for KnowGraph.

Provides consistent, context-aware logging with structured output,
performance tracking, and integration with monitoring systems.
"""

import json
import logging
import sys
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class LogLevel(str, Enum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogContext:
    """Contextual information for log entries.

    Attributes
    ----------
        request_id: Unique identifier for request tracking
        operation: Current operation being performed
        user_id: Optional user identifier
        graph_path: Path to graph store
        metadata: Additional context-specific data
    """

    request_id: str = field(default_factory=lambda: str(uuid4()))
    operation: str | None = None
    user_id: str | None = None
    graph_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "request_id": self.request_id,
            "operation": self.operation,
            "user_id": self.user_id,
            "graph_path": self.graph_path,
            **self.metadata,
        }


# Context variable for storing log context across async boundaries
_log_context: ContextVar[LogContext | None] = ContextVar("log_context", default=None)


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
        ----
            record: Log record to format

        Returns:
        -------
            JSON string representation of log entry
        """
        # Base log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add context if available
        context = _log_context.get()
        if context:
            log_entry["context"] = context.to_dict()

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry)


class PerformanceLogger:
    """Logger for tracking performance metrics."""

    def __init__(self, logger: logging.Logger, operation: str):
        """Initialize performance logger.

        Args:
        ----
            logger: Logger instance to use
            operation: Name of operation being tracked
        """
        self.logger = logger
        self.operation = operation
        self.start_time: float | None = None
        self.end_time: float | None = None

    def __enter__(self) -> "PerformanceLogger":
        """Start timing operation."""
        self.start_time = time.time()
        self.logger.debug(f"Starting operation: {self.operation}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Log operation completion and duration."""
        self.end_time = time.time()
        duration = self.end_time - self.start_time if self.start_time else 0

        if exc_type:
            self.logger.error(
                f"Operation failed: {self.operation}",
                extra={"extra_fields": {"duration_seconds": duration, "error": str(exc_val)}},
            )
        else:
            self.logger.info(
                f"Operation completed: {self.operation}",
                extra={"extra_fields": {"duration_seconds": duration}},
            )


class KnowGraphLogger:
    """Main logging interface for KnowGraph.

    Provides structured logging with context management,
    performance tracking, and consistent formatting.
    """

    def __init__(
        self,
        name: str,
        level: LogLevel = LogLevel.INFO,
        output_file: Path | None = None,
        use_json: bool = True,
    ):
        """Initialize KnowGraph logger.

        Args:
        ----
            name: Logger name (usually module name)
            level: Minimum log level
            output_file: Optional file path for log output
            use_json: Whether to use JSON formatting
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.value))
        self.logger.handlers.clear()  # Remove any existing handlers

        # Console handler
        console_handler = logging.StreamHandler(sys.stderr)
        if use_json:
            console_handler.setFormatter(StructuredFormatter())
        else:
            console_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
            )
        self.logger.addHandler(console_handler)

        # File handler (optional)
        if output_file:
            file_handler = logging.FileHandler(output_file)
            if use_json:
                file_handler.setFormatter(StructuredFormatter())
            else:
                file_handler.setFormatter(
                    logging.Formatter(
                        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                    )
                )
            self.logger.addHandler(file_handler)

    def set_context(self, context: LogContext) -> None:
        """Set logging context for current execution.

        Args:
        ----
            context: Log context to set
        """
        _log_context.set(context)

    def clear_context(self) -> None:
        """Clear logging context."""
        _log_context.set(None)

    def get_context(self) -> LogContext | None:
        """Get current logging context.

        Returns:
        -------
            Current context or None
        """
        return _log_context.get()

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message.

        Args:
        ----
            message: Log message
            **kwargs: Additional fields to include in log entry
        """
        self.logger.debug(message, extra={"extra_fields": kwargs})

    def info(self, message: str, **kwargs) -> None:
        """Log info message.

        Args:
        ----
            message: Log message
            **kwargs: Additional fields to include in log entry
        """
        self.logger.info(message, extra={"extra_fields": kwargs})

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message.

        Args:
        ----
            message: Log message
            **kwargs: Additional fields to include in log entry
        """
        self.logger.warning(message, extra={"extra_fields": kwargs})

    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log error message.

        Args:
        ----
            message: Log message
            exc_info: Whether to include exception info
            **kwargs: Additional fields to include in log entry
        """
        self.logger.error(message, exc_info=exc_info, extra={"extra_fields": kwargs})

    def critical(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log critical message.

        Args:
        ----
            message: Log message
            exc_info: Whether to include exception info
            **kwargs: Additional fields to include in log entry
        """
        self.logger.critical(message, exc_info=exc_info, extra={"extra_fields": kwargs})

    def track_performance(self, operation: str) -> PerformanceLogger:
        """Create performance logger for operation.

        Args:
        ----
            operation: Name of operation to track

        Returns:
        -------
            Performance logger context manager
        """
        return PerformanceLogger(self.logger, operation)


# Global logger instance
_default_logger: KnowGraphLogger | None = None


def get_logger(
    name: str | None = None,
    level: LogLevel = LogLevel.INFO,
    output_file: Path | None = None,
    use_json: bool = True,
) -> KnowGraphLogger:
    """Get or create a KnowGraph logger.

    Args:
    ----
        name: Logger name (defaults to "knowgraph")
        level: Minimum log level
        output_file: Optional file path for log output
        use_json: Whether to use JSON formatting

    Returns:
    -------
        KnowGraph logger instance
    """
    global _default_logger

    if name is None:
        if _default_logger is None:
            _default_logger = KnowGraphLogger("knowgraph", level, output_file, use_json)
        return _default_logger

    return KnowGraphLogger(name, level, output_file, use_json)


def configure_logging(
    level: LogLevel = LogLevel.INFO,
    output_file: Path | None = None,
    use_json: bool = True,
) -> None:
    """Configure global logging settings.

    Args:
    ----
        level: Minimum log level
        output_file: Optional file path for log output
        use_json: Whether to use JSON formatting
    """
    global _default_logger
    _default_logger = KnowGraphLogger("knowgraph", level, output_file, use_json)


def set_log_context(
    operation: str | None = None,
    user_id: str | None = None,
    graph_path: str | None = None,
    **metadata,
) -> LogContext:
    """Set logging context for current execution.

    Args:
    ----
        operation: Current operation name
        user_id: Optional user identifier
        graph_path: Path to graph store
        **metadata: Additional context metadata

    Returns:
    -------
        Created log context
    """
    context = LogContext(
        operation=operation,
        user_id=user_id,
        graph_path=graph_path,
        metadata=metadata,
    )
    _log_context.set(context)
    return context


def clear_log_context() -> None:
    """Clear current logging context."""
    _log_context.set(None)


def log_function_call(func):
    """Decorator to automatically log function calls.

    Args:
    ----
        func: Function to wrap

    Returns:
    -------
        Wrapped function with logging
    """

    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(
            f"Calling function: {func.__name__}",
            args=str(args)[:100],  # Truncate to prevent huge logs
            kwargs=str(kwargs)[:100],
        )
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Function completed: {func.__name__}")
            return result
        except Exception as e:
            logger.error(
                f"Function failed: {func.__name__}",
                exc_info=True,
                error=str(e),
            )
            raise

    return wrapper


def log_async_function_call(func):
    """Decorator to automatically log async function calls.

    Args:
    ----
        func: Async function to wrap

    Returns:
    -------
        Wrapped async function with logging
    """

    async def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(
            f"Calling async function: {func.__name__}",
            args=str(args)[:100],
            kwargs=str(kwargs)[:100],
        )
        try:
            result = await func(*args, **kwargs)
            logger.debug(f"Async function completed: {func.__name__}")
            return result
        except Exception as e:
            logger.error(
                f"Async function failed: {func.__name__}",
                exc_info=True,
                error=str(e),
            )
            raise

    return wrapper

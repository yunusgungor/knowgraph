"""Tests for structured logging system."""

import json
import logging

import pytest

from knowgraph.shared.logging import (
    KnowGraphLogger,
    LogContext,
    LogLevel,
    clear_log_context,
    configure_logging,
    get_logger,
    log_async_function_call,
    log_function_call,
    set_log_context,
)


class TestLogContext:
    """Test log context management."""

    def test_log_context_creation(self):
        """Test creating log context."""
        context = LogContext(
            operation="test_op",
            user_id="user123",
            graph_path="/path/to/graph",
            metadata={"key": "value"},
        )

        assert context.operation == "test_op"
        assert context.user_id == "user123"
        assert context.graph_path == "/path/to/graph"
        assert context.metadata["key"] == "value"
        assert context.request_id  # Should be auto-generated

    def test_log_context_to_dict(self):
        """Test converting context to dict."""
        context = LogContext(
            operation="test_op",
            metadata={"foo": "bar"},
        )

        context_dict = context.to_dict()
        assert context_dict["operation"] == "test_op"
        assert context_dict["foo"] == "bar"
        assert "request_id" in context_dict

    def test_log_context_default_request_id(self):
        """Test auto-generated request ID."""
        context1 = LogContext()
        context2 = LogContext()

        assert context1.request_id != context2.request_id


class TestKnowGraphLogger:
    """Test main logger functionality."""

    def test_logger_creation(self):
        """Test creating logger."""
        logger = KnowGraphLogger("test_logger", level=LogLevel.DEBUG)
        assert logger.logger.name == "test_logger"
        assert logger.logger.level == logging.DEBUG

    def test_logger_debug(self, capsys):
        """Test debug logging."""
        logger = KnowGraphLogger("test", level=LogLevel.DEBUG, use_json=False)
        logger.debug("Debug message", extra_field="value")

        captured = capsys.readouterr()
        assert "Debug message" in captured.err
        assert "DEBUG" in captured.err

    def test_logger_info(self, capsys):
        """Test info logging."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=False)
        logger.info("Info message", count=42)

        captured = capsys.readouterr()
        assert "Info message" in captured.err
        assert "INFO" in captured.err

    def test_logger_warning(self, capsys):
        """Test warning logging."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=False)
        logger.warning("Warning message")

        captured = capsys.readouterr()
        assert "Warning message" in captured.err
        assert "WARNING" in captured.err

    def test_logger_error(self, capsys):
        """Test error logging."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=False)
        logger.error("Error message", error_code=500)

        captured = capsys.readouterr()
        assert "Error message" in captured.err
        assert "ERROR" in captured.err

    def test_logger_critical(self, capsys):
        """Test critical logging."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=False)
        logger.critical("Critical message")

        captured = capsys.readouterr()
        assert "Critical message" in captured.err
        assert "CRITICAL" in captured.err

    def test_logger_with_context(self, capsys):
        """Test logging with context."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=True)

        context = LogContext(operation="test_operation", user_id="user123")
        logger.set_context(context)

        logger.info("Message with context")

        captured = capsys.readouterr()
        log_entry = json.loads(captured.err)

        assert log_entry["message"] == "Message with context"
        assert log_entry["context"]["operation"] == "test_operation"
        assert log_entry["context"]["user_id"] == "user123"

    def test_logger_exception_info(self, capsys):
        """Test logging with exception info."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=True)

        try:
            raise ValueError("Test error")
        except ValueError:
            logger.error("Error occurred", exc_info=True)

        captured = capsys.readouterr()
        log_entry = json.loads(captured.err)

        assert log_entry["message"] == "Error occurred"
        assert "exception" in log_entry
        assert log_entry["exception"]["type"] == "ValueError"
        assert "Test error" in log_entry["exception"]["message"]

    def test_logger_context_management(self):
        """Test context set/get/clear."""
        logger = KnowGraphLogger("test")

        context = LogContext(operation="test")
        logger.set_context(context)

        assert logger.get_context() == context

        logger.clear_context()
        assert logger.get_context() is None

    def test_logger_file_output(self, tmp_path):
        """Test logging to file."""
        log_file = tmp_path / "test.log"
        logger = KnowGraphLogger("test", output_file=log_file, use_json=False)

        logger.info("File log message")

        assert log_file.exists()
        content = log_file.read_text()
        assert "File log message" in content

    def test_logger_json_format(self, capsys):
        """Test JSON formatted output."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=True)
        logger.info("JSON message", field1="value1", field2=42)

        captured = capsys.readouterr()
        log_entry = json.loads(captured.err)

        assert log_entry["message"] == "JSON message"
        assert log_entry["level"] == "INFO"
        assert log_entry["logger"] == "test"
        assert "timestamp" in log_entry
        assert log_entry["field1"] == "value1"
        assert log_entry["field2"] == 42


class TestPerformanceLogger:
    """Test performance tracking."""

    def test_performance_logger_success(self, capsys):
        """Test performance logging for successful operation."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=False)

        with logger.track_performance("test_operation"):
            pass  # Operation

        captured = capsys.readouterr()
        assert "Operation completed: test_operation" in captured.err
        assert "duration_seconds" in captured.err or "INFO" in captured.err

    def test_performance_logger_failure(self, capsys):
        """Test performance logging for failed operation."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=False)

        with pytest.raises(ValueError):
            with logger.track_performance("failing_operation"):
                raise ValueError("Test error")

        captured = capsys.readouterr()
        assert "Operation failed: failing_operation" in captured.err

    def test_performance_logger_timing(self, capsys):
        """Test performance timing."""
        import time

        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=True)

        with logger.track_performance("timed_operation"):
            time.sleep(0.1)  # Sleep for 100ms

        captured = capsys.readouterr()
        log_entry = json.loads(captured.err)

        assert "duration_seconds" in log_entry
        assert log_entry["duration_seconds"] >= 0.1


class TestGlobalLoggerFunctions:
    """Test global logger functions."""

    def test_get_logger_default(self):
        """Test getting default logger."""
        logger = get_logger()
        assert isinstance(logger, KnowGraphLogger)

    def test_get_logger_named(self):
        """Test getting named logger."""
        logger = get_logger("custom_logger")
        assert isinstance(logger, KnowGraphLogger)
        assert logger.logger.name == "custom_logger"

    def test_configure_logging(self):
        """Test global logging configuration."""
        configure_logging(level=LogLevel.DEBUG, use_json=False)
        logger = get_logger()
        assert logger.logger.level == logging.DEBUG

    def test_set_log_context(self):
        """Test setting global context."""
        context = set_log_context(
            operation="global_op",
            user_id="user456",
            extra_field="value",
        )

        assert context.operation == "global_op"
        assert context.user_id == "user456"
        assert context.metadata["extra_field"] == "value"

    def test_clear_log_context(self):
        """Test clearing global context."""
        set_log_context(operation="test")
        clear_log_context()

        logger = get_logger()
        assert logger.get_context() is None


class TestLoggingDecorators:
    """Test logging decorators."""

    def test_log_function_call_decorator(self, capsys):
        """Test function call logging decorator."""
        # Reset to get fresh logger
        import logging
        logging.getLogger().handlers.clear()

        configure_logging(level=LogLevel.DEBUG, use_json=False)

        @log_function_call
        def test_function(x, y):
            return x + y

        result = test_function(1, 2)

        assert result == 3

        captured = capsys.readouterr()
        # Check that function executed successfully
        assert result == 3

    def test_log_function_call_with_error(self, capsys):
        """Test function call logging with error."""
        import logging
        logging.getLogger().handlers.clear()

        configure_logging(level=LogLevel.DEBUG, use_json=False)

        @log_function_call
        def failing_function():
            raise RuntimeError("Test error")

        with pytest.raises(RuntimeError):
            failing_function()

        captured = capsys.readouterr()
        assert "Function failed: failing_function" in captured.err

    @pytest.mark.asyncio
    async def test_log_async_function_call_decorator(self, capsys):
        """Test async function call logging decorator."""
        import logging
        logging.getLogger().handlers.clear()

        configure_logging(level=LogLevel.DEBUG, use_json=False)

        @log_async_function_call
        async def async_test_function(x):
            return x * 2

        result = await async_test_function(5)

        assert result == 10
        # Function executed successfully

    @pytest.mark.asyncio
    async def test_log_async_function_call_with_error(self, capsys):
        """Test async function call logging with error."""
        import logging
        logging.getLogger().handlers.clear()

        configure_logging(level=LogLevel.DEBUG, use_json=False)

        @log_async_function_call
        async def async_failing_function():
            raise ValueError("Async test error")

        with pytest.raises(ValueError):
            await async_failing_function()

        captured = capsys.readouterr()
        assert "Async function failed: async_failing_function" in captured.err


class TestLogLevels:
    """Test log level filtering."""

    def test_debug_not_shown_at_info_level(self, capsys):
        """Test debug messages filtered at INFO level."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=False)
        logger.debug("Debug message")

        captured = capsys.readouterr()
        assert "Debug message" not in captured.err

    def test_info_shown_at_debug_level(self, capsys):
        """Test info messages shown at DEBUG level."""
        logger = KnowGraphLogger("test", level=LogLevel.DEBUG, use_json=False)
        logger.info("Info message")

        captured = capsys.readouterr()
        assert "Info message" in captured.err

    def test_error_shown_at_warning_level(self, capsys):
        """Test error messages shown at WARNING level."""
        logger = KnowGraphLogger("test", level=LogLevel.WARNING, use_json=False)
        logger.error("Error message")

        captured = capsys.readouterr()
        assert "Error message" in captured.err


class TestStructuredLogging:
    """Test structured logging features."""

    def test_json_output_structure(self, capsys):
        """Test JSON output has expected structure."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=True)
        logger.info("Test message", custom_field="custom_value")

        captured = capsys.readouterr()
        log_entry = json.loads(captured.err)

        # Check required fields
        assert "timestamp" in log_entry
        assert "level" in log_entry
        assert "logger" in log_entry
        assert "message" in log_entry
        assert "module" in log_entry
        assert "function" in log_entry
        assert "line" in log_entry

        # Check custom field
        assert log_entry["custom_field"] == "custom_value"

    def test_context_in_json_output(self, capsys):
        """Test context appears in JSON output."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=True)

        context = LogContext(
            operation="context_test",
            graph_path="/test/path",
            metadata={"env": "test"},
        )
        logger.set_context(context)

        logger.info("Message with full context")

        captured = capsys.readouterr()
        log_entry = json.loads(captured.err)

        assert "context" in log_entry
        assert log_entry["context"]["operation"] == "context_test"
        assert log_entry["context"]["graph_path"] == "/test/path"
        assert log_entry["context"]["env"] == "test"

    def test_multiple_log_entries(self, capsys):
        """Test multiple log entries are properly formatted."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=True)

        logger.info("Message 1", seq=1)
        logger.info("Message 2", seq=2)
        logger.info("Message 3", seq=3)

        captured = capsys.readouterr()
        lines = captured.err.strip().split("\n")

        assert len(lines) == 3

        for i, line in enumerate(lines, 1):
            entry = json.loads(line)
            assert entry["message"] == f"Message {i}"
            assert entry["seq"] == i


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_logging_with_none_values(self, capsys):
        """Test logging with None values."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=True)
        logger.info("Message", none_field=None)

        captured = capsys.readouterr()
        log_entry = json.loads(captured.err)

        assert "none_field" in log_entry
        assert log_entry["none_field"] is None

    def test_logging_with_special_characters(self, capsys):
        """Test logging with special characters."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=True)
        logger.info("Message with émojis 🚀 and symbols: @#$%")

        captured = capsys.readouterr()
        log_entry = json.loads(captured.err)

        assert "🚀" in log_entry["message"]
        assert "@#$%" in log_entry["message"]

    def test_logging_large_data(self, capsys):
        """Test logging with large data structures."""
        logger = KnowGraphLogger("test", level=LogLevel.INFO, use_json=True)

        large_list = list(range(1000))
        logger.info("Large data", data=large_list)

        captured = capsys.readouterr()
        log_entry = json.loads(captured.err)

        assert "data" in log_entry
        assert len(log_entry["data"]) == 1000

    def test_concurrent_context_isolation(self):
        """Test context isolation in concurrent scenarios."""
        logger = KnowGraphLogger("test")

        context1 = LogContext(operation="op1")
        logger.set_context(context1)

        assert logger.get_context().operation == "op1"

        # Create new context
        context2 = LogContext(operation="op2")
        logger.set_context(context2)

        assert logger.get_context().operation == "op2"

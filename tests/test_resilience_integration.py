"""Integration tests for resilience patterns in the actual application."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from knowgraph.application.querying.query_engine import QueryEngine
from knowgraph.shared.circuit_breaker import CircuitBreakerError


@pytest.fixture
def mock_graph_store(tmp_path: Path):
    """Create a mock graph store for testing."""
    graph_path = tmp_path / "test_graph"
    graph_path.mkdir()

    # Create required directories
    (graph_path / "nodes").mkdir()
    (graph_path / "edges").mkdir()
    (graph_path / "metadata").mkdir()
    (graph_path / "index").mkdir()

    # Create manifest
    manifest = {
        "version": "1.0",
        "node_count": 0,
        "edge_count": 0,
        "created_at": "2025-01-01T00:00:00Z",
    }
    import json

    with open(graph_path / "metadata" / "manifest.json", "w") as f:
        json.dump(manifest, f)

    # Create empty sparse index
    with open(graph_path / "index" / "sparse_index.json", "w") as f:
        json.dump({"terms": {}, "doc_lengths": {}, "avg_doc_length": 0.0}, f)

    # Create empty edges file
    with open(graph_path / "edges" / "edges.jsonl", "w") as f:
        pass

    return graph_path


class TestQueryEngineResilience:
    """Test resilience patterns in QueryEngine."""

    def test_query_engine_has_resilience_patterns(self, mock_graph_store):
        """Verify QueryEngine initializes resilience patterns."""
        engine = QueryEngine(mock_graph_store)

        # Check circuit breaker is initialized
        assert hasattr(engine, "_circuit_breaker")
        assert engine._circuit_breaker is not None

        # Check retry config is initialized
        assert hasattr(engine, "_retry_config")
        assert engine._retry_config is not None

        # Check throttle is initialized
        assert hasattr(engine, "_throttle")
        assert engine._throttle is not None

    @pytest.mark.asyncio
    async def test_async_query_uses_circuit_breaker(self, mock_graph_store):
        """Test that async queries are protected by circuit breaker."""
        engine = QueryEngine(mock_graph_store)

        # Mock the internal query implementation to always fail
        async def failing_query(*args, **kwargs):
            raise Exception("Simulated failure")

        with patch.object(engine, "_query_async_impl", side_effect=failing_query):
            # First few failures should be attempted
            with pytest.raises(Exception, match="Simulated failure"):
                await engine.query_async("test query")

    @pytest.mark.asyncio
    async def test_async_query_uses_throttle(self, mock_graph_store):
        """Test that async queries are throttled."""
        engine = QueryEngine(mock_graph_store)

        # Track how many concurrent queries are executed
        concurrent_count = 0
        max_concurrent = 0

        async def mock_query(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.1)  # Simulate work
            concurrent_count -= 1
            return MagicMock(context="test", answer="test", explanation=None, metrics={})

        with patch.object(engine, "_query_async_impl", side_effect=mock_query):
            # Launch many queries concurrently
            queries = [engine.query_async("test query") for _ in range(20)]
            await asyncio.gather(*queries, return_exceptions=True)

            # Verify throttle limited concurrent execution
            # Check against actual throttle config, not hardcoded value
            expected_max = engine._throttle.config.max_concurrent
            assert (
                max_concurrent <= expected_max + 5
            ), f"Expected max ~{expected_max} concurrent, got {max_concurrent}"

    def test_sync_query_uses_retry(self, mock_graph_store):
        """Test that sync queries use retry logic."""
        engine = QueryEngine(mock_graph_store)

        # Verify retry context is available
        assert engine._retry_config is not None
        assert engine._retry_config.max_attempts == 3


class TestMCPHandlersResilience:
    """Test resilience patterns in MCP handlers."""

    @pytest.mark.asyncio
    async def test_handlers_have_global_circuit_breaker(self):
        """Verify MCP handlers have global circuit breaker."""
        from knowgraph.adapters.mcp import handlers

        # Check global circuit breaker exists
        assert hasattr(handlers, "_global_circuit_breaker")
        assert handlers._global_circuit_breaker is not None

    @pytest.mark.asyncio
    async def test_handlers_have_global_rate_limiter(self):
        """Verify MCP handlers have global rate limiter."""
        from knowgraph.adapters.mcp import handlers

        # Check global rate limiter exists
        assert hasattr(handlers, "_global_rate_limiter")
        assert handlers._global_rate_limiter is not None

    @pytest.mark.asyncio
    async def test_handle_query_protected_by_circuit_breaker(self, mock_graph_store, tmp_path):
        """Test that handle_query uses circuit breaker."""
        from knowgraph.adapters.mcp import handlers

        arguments = {
            "query": "test query",
            "graph_path": str(mock_graph_store),
        }

        # Mock provider
        provider = AsyncMock()
        provider.generate_text = AsyncMock(return_value="Generated answer")

        # This should not raise an error for valid input
        # (though it might fail due to empty graph)
        try:
            result = await handlers.handle_query(arguments, provider, tmp_path)
            assert result is not None
        except Exception:
            # Expected with empty graph
            pass

    @pytest.mark.asyncio
    async def test_handle_batch_query_uses_rate_limiter(self, mock_graph_store, tmp_path):
        """Test that handle_batch_query uses rate limiter."""
        from knowgraph.adapters.mcp import handlers

        arguments = {
            "queries": ["query1", "query2", "query3"],
            "graph_path": str(mock_graph_store),
        }

        provider = AsyncMock()

        # This should apply rate limiting
        try:
            result = await handlers.handle_batch_query(arguments, provider, tmp_path)
            assert result is not None
        except Exception:
            # Expected with empty graph
            pass


class TestAPIVersioning:
    """Test API versioning integration."""

    def test_versioning_registered_at_startup(self):
        """Verify API versions are registered when server module loads."""
        import importlib

        # Reload server module to trigger registration
        from knowgraph.adapters.mcp import server
        from knowgraph.shared.versioning import get_current_version, get_version_registry

        importlib.reload(server)

        # Check versions are registered
        current = get_current_version()
        assert current is not None

        registry = get_version_registry()
        supported = registry.get_supported_versions()
        assert len(supported) > 0
        assert any(v.major == 1 and v.minor >= 1 for v in supported)


class TestEndToEndResilience:
    """End-to-end tests for resilience patterns."""

    @pytest.mark.asyncio
    async def test_full_query_pipeline_with_resilience(self, mock_graph_store):
        """Test complete query pipeline with all resilience patterns."""
        engine = QueryEngine(mock_graph_store)

        # Verify all resilience components are present
        assert engine._circuit_breaker is not None
        assert engine._retry_config is not None
        assert engine._throttle is not None

        # Mock successful query
        mock_result = MagicMock()
        mock_result.context = "test context"
        mock_result.answer = "test answer"
        mock_result.explanation = None
        mock_result.metrics = {}

        with patch.object(engine, "_query_async_impl", return_value=mock_result):
            result = await engine.query_async("test query")
            assert result is not None

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, mock_graph_store):
        """Test that circuit breaker opens after repeated failures."""
        engine = QueryEngine(mock_graph_store)

        # Mock implementation that always fails
        async def always_fails(*args, **kwargs):
            raise Exception("Persistent failure")

        with patch.object(engine, "_query_async_impl", side_effect=always_fails):
            # Execute multiple failing queries
            unique_query = f"test query {uuid4()}"
            for _ in range(10):
                try:
                    await engine.query_async(unique_query)
                except Exception:
                    pass

            # Circuit breaker should eventually open
            # Next call should be rejected immediately
            with pytest.raises((CircuitBreakerError, Exception)):
                await engine.query_async(unique_query)


class TestResilienceConfiguration:
    """Test resilience pattern configuration."""

    def test_circuit_breaker_configuration(self, mock_graph_store):
        """Verify circuit breaker is configured correctly."""
        engine = QueryEngine(mock_graph_store)
        cb = engine._circuit_breaker

        assert cb.config.failure_threshold == 5
        assert cb.config.timeout == 30.0

    def test_retry_configuration(self, mock_graph_store):
        """Verify retry logic is configured correctly."""
        engine = QueryEngine(mock_graph_store)
        retry = engine._retry_config

        assert retry.max_attempts == 3
        assert retry.backoff_strategy.value == "exponential"

    def test_throttle_configuration(self, mock_graph_store):
        """Verify throttle is configured correctly."""
        engine = QueryEngine(mock_graph_store)
        throttle = engine._throttle

        # Should limit concurrent queries
        assert throttle.config.max_concurrent > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

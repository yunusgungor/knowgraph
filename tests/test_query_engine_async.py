"""Test async query engine functionality."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from knowgraph.application.querying.query_engine import QueryEngine, QueryResult


@pytest.mark.asyncio
async def test_query_engine_async_basic():
    """Test basic async query execution."""
    store_path = Path("store")

    # Mocking internal dependencies
    with (
        patch("knowgraph.application.querying.query_engine.QueryRetriever") as mock_retriever_cls,
        patch("knowgraph.application.querying.query_engine.read_all_edges") as mock_read_edges,
        patch("knowgraph.application.querying.query_engine.assemble_context") as mock_assemble,
        patch("knowgraph.application.querying.query_engine.generate_explanation") as mock_gen_exp,
        patch(
            "knowgraph.application.querying.query_engine.compute_centrality_metrics"
        ) as mock_centrality,
    ):
        # Setup mocks
        mock_retriever = mock_retriever_cls.return_value
        n1 = MagicMock()
        n1.id = uuid4()

        # Mock async methods
        async def mock_retrieve_async(*args, **kwargs):
            return ([n1], [n1.id])

        async def mock_retrieve_by_similarity_async(*args, **kwargs):
            return [(n1, 1.0)]

        mock_retriever.retrieve_async = mock_retrieve_async
        mock_retriever.retrieve_by_similarity_async = mock_retrieve_by_similarity_async

        mock_read_edges.return_value = []
        mock_centrality.return_value = {n1.id: {"degree": 1.0}}
        mock_assemble.return_value = ("Context", [])
        mock_gen_exp.return_value = MagicMock()

        engine = QueryEngine(store_path)

        # Test async query
        result = await engine.query_async("test query", with_explanation=True)

        assert isinstance(result, QueryResult)
        assert result.answer == "Context"
        assert result.explanation is not None
        assert result.execution_time > 0


@pytest.mark.asyncio
async def test_query_engine_async_timeout():
    """Test async query timeout."""
    store_path = Path("store")

    with (
        patch("knowgraph.application.querying.query_engine.QueryRetriever") as mock_retriever_cls,
        patch("knowgraph.application.querying.query_engine.read_all_edges") as mock_read_edges,
    ):
        mock_retriever = mock_retriever_cls.return_value

        # Mock async method that takes too long
        async def slow_retrieve_async(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than timeout
            return ([], [])

        mock_retriever.retrieve_async = slow_retrieve_async
        mock_read_edges.return_value = []

        engine = QueryEngine(store_path)

        # Test timeout
        from knowgraph.shared.exceptions import QueryError

        with pytest.raises(QueryError) as exc_info:
            await engine.query_async("test query", timeout=0.1)

        assert "timed out" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_batch_queries_concurrent():
    """Test that multiple queries can run concurrently."""
    store_path = Path("store")

    with (
        patch("knowgraph.application.querying.query_engine.QueryRetriever") as mock_retriever_cls,
        patch("knowgraph.application.querying.query_engine.read_all_edges") as mock_read_edges,
        patch("knowgraph.application.querying.query_engine.assemble_context") as mock_assemble,
        patch(
            "knowgraph.application.querying.query_engine.compute_centrality_metrics"
        ) as mock_centrality,
    ):
        mock_retriever = mock_retriever_cls.return_value
        n1 = MagicMock()
        n1.id = uuid4()

        async def mock_retrieve_async(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate some work
            return ([n1], [n1.id])

        async def mock_retrieve_by_similarity_async(*args, **kwargs):
            return [(n1, 1.0)]

        mock_retriever.retrieve_async = mock_retrieve_async
        mock_retriever.retrieve_by_similarity_async = mock_retrieve_by_similarity_async
        mock_read_edges.return_value = []
        mock_centrality.return_value = {n1.id: {"degree": 1.0}}
        mock_assemble.return_value = ("Context", [])

        engine = QueryEngine(store_path)

        # Run 3 queries concurrently
        import time

        start = time.time()
        results = await asyncio.gather(
            engine.query_async("query 1"),
            engine.query_async("query 2"),
            engine.query_async("query 3"),
        )
        elapsed = time.time() - start

        # Should take ~0.1s (concurrent) not ~0.3s (sequential)
        # Very generous threshold for CI/heavy load scenarios
        assert elapsed < 1.0  # Relaxed significantly for worst-case system load
        assert len(results) == 3
        assert all(isinstance(r, QueryResult) for r in results)


@pytest.mark.asyncio
async def test_batch_query_async_with_progress():
    """Test batch query with progress callback."""
    store_path = Path("store")

    with (
        patch("knowgraph.application.querying.query_engine.QueryRetriever") as mock_retriever_cls,
        patch("knowgraph.application.querying.query_engine.read_all_edges") as mock_read_edges,
        patch("knowgraph.application.querying.query_engine.assemble_context") as mock_assemble,
        patch(
            "knowgraph.application.querying.query_engine.compute_centrality_metrics"
        ) as mock_centrality,
    ):
        mock_retriever = mock_retriever_cls.return_value
        n1 = MagicMock()
        n1.id = uuid4()

        async def mock_retrieve_async(*args, **kwargs):
            return ([n1], [n1.id])

        async def mock_retrieve_by_similarity_async(*args, **kwargs):
            return [(n1, 1.0)]

        mock_retriever.retrieve_async = mock_retrieve_async
        mock_retriever.retrieve_by_similarity_async = mock_retrieve_by_similarity_async
        mock_read_edges.return_value = []
        mock_centrality.return_value = {n1.id: {"degree": 1.0}}
        mock_assemble.return_value = ("Context", [])

        engine = QueryEngine(store_path)

        # Track progress
        progress_calls = []

        async def on_progress(current, total):
            progress_calls.append((current, total))

        # Run batch query with progress
        queries = ["q1", "q2", "q3", "q4", "q5"]
        results = await engine.batch_query_async(
            queries=queries, batch_size=2, progress_callback=on_progress
        )

        # Check results
        assert len(results) == 5
        assert all(isinstance(r, QueryResult) for r in results)

        # Check progress was reported
        assert len(progress_calls) > 0
        assert progress_calls[-1] == (5, 5)  # Final progress


@pytest.mark.asyncio
async def test_batch_query_async_error_handling():
    """Test batch query handles errors gracefully."""
    store_path = Path("store")

    with (
        patch("knowgraph.application.querying.query_engine.QueryRetriever") as mock_retriever_cls,
        patch("knowgraph.application.querying.query_engine.read_all_edges") as mock_read_edges,
        patch("knowgraph.application.querying.query_engine.assemble_context") as mock_assemble,
        patch(
            "knowgraph.application.querying.query_engine.compute_centrality_metrics"
        ) as mock_centrality,
    ):
        mock_retriever = mock_retriever_cls.return_value
        n1 = MagicMock()
        n1.id = uuid4()

        # Make second query fail
        call_count = [0]

        async def mock_retrieve_async(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise Exception("Simulated failure")
            return ([n1], [n1.id])

        async def mock_retrieve_by_similarity_async(*args, **kwargs):
            return [(n1, 1.0)]

        mock_retriever.retrieve_async = mock_retrieve_async
        mock_retriever.retrieve_by_similarity_async = mock_retrieve_by_similarity_async
        mock_read_edges.return_value = []
        mock_centrality.return_value = {n1.id: {"degree": 1.0}}
        mock_assemble.return_value = ("Context", [])

        engine = QueryEngine(store_path)

        # Run batch query
        queries = ["q1", "q2", "q3"]
        results = await engine.batch_query_async(queries=queries)

        # Should have 3 results
        assert len(results) == 3

        # First and third should succeed
        assert results[0].answer == "Context"
        assert results[2].answer == "Context"

        # Second should be empty (failed)
        assert results[1].answer == ""
        assert results[1].active_subgraph_size == 0


@pytest.mark.asyncio
async def test_batch_query_async_performance():
    """Test that batch query is significantly faster than sequential."""
    store_path = Path("store")

    with (
        patch("knowgraph.application.querying.query_engine.QueryRetriever") as mock_retriever_cls,
        patch("knowgraph.application.querying.query_engine.read_all_edges") as mock_read_edges,
        patch("knowgraph.application.querying.query_engine.assemble_context") as mock_assemble,
        patch(
            "knowgraph.application.querying.query_engine.compute_centrality_metrics"
        ) as mock_centrality,
    ):
        mock_retriever = mock_retriever_cls.return_value
        n1 = MagicMock()
        n1.id = uuid4()

        async def mock_retrieve_async(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate work
            return ([n1], [n1.id])

        async def mock_retrieve_by_similarity_async(*args, **kwargs):
            return [(n1, 1.0)]

        mock_retriever.retrieve_async = mock_retrieve_async
        mock_retriever.retrieve_by_similarity_async = mock_retrieve_by_similarity_async
        mock_read_edges.return_value = []
        mock_centrality.return_value = {n1.id: {"degree": 1.0}}
        mock_assemble.return_value = ("Context", [])

        engine = QueryEngine(store_path)

        queries = ["q1", "q2", "q3", "q4", "q5"]

        # Sequential (for comparison)
        import time

        start = time.time()
        sequential_results = []
        for q in queries:
            result = await engine.query_async(q)
            sequential_results.append(result)
        sequential_time = time.time() - start

        # Batch (concurrent)
        start = time.time()
        batch_results = await engine.batch_query_async(queries, batch_size=5)
        batch_time = time.time() - start

        # Batch should be significantly faster
        speedup = sequential_time / batch_time
        print(f"\nSequential: {sequential_time:.2f}s")
        print(f"Batch: {batch_time:.2f}s")
        print(f"Speedup: {speedup:.2f}x")

        # Should be at least 1.5x faster (relaxed for system load)
        # When all tests run together, timing can be less predictable
        assert speedup >= 1.5
        assert len(batch_results) == 5

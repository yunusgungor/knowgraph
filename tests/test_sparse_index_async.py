"""Tests for async sparse index search optimization."""

import asyncio
import time

import pytest

from knowgraph.infrastructure.search.sparse_index import SparseIndex


@pytest.fixture
def sample_index():
    """Create a sample sparse index for testing."""
    index = SparseIndex()

    # Add sample documents
    docs = {
        "doc1": {"async": 5, "await": 3, "python": 2, "performance": 1},
        "doc2": {"async": 2, "performance": 4, "optimization": 3, "speed": 2},
        "doc3": {"query": 3, "search": 5, "index": 2, "performance": 1},
        "doc4": {"async": 4, "concurrent": 3, "parallel": 2, "threading": 1},
        "doc5": {"database": 3, "query": 4, "sql": 2, "optimization": 1},
    }

    for doc_id, sparse_vec in docs.items():
        index.add(doc_id, sparse_vec)

    index.build()
    return index


def test_sync_search(sample_index):
    """Test synchronous search still works."""
    query = {"async": 2, "performance": 1}
    results = sample_index.search(query, top_k=3)

    assert len(results) <= 3
    assert all(isinstance(doc_id, str) and isinstance(score, float) for doc_id, score in results)
    # Should return doc1, doc2, doc4 as they contain "async"
    doc_ids = [doc_id for doc_id, _ in results]
    assert "doc1" in doc_ids or "doc2" in doc_ids or "doc4" in doc_ids


@pytest.mark.asyncio
async def test_async_search(sample_index):
    """Test asynchronous search returns correct results."""
    query = {"async": 2, "performance": 1}
    results = await sample_index.search_async(query, top_k=3)

    assert len(results) <= 3
    assert all(isinstance(doc_id, str) and isinstance(score, float) for doc_id, score in results)

    # Should return same results as sync search
    sync_results = sample_index.search(query, top_k=3)
    assert len(results) == len(sync_results)

    # Results should be identical (same order and scores)
    for (async_id, async_score), (sync_id, sync_score) in zip(results, sync_results):
        assert async_id == sync_id
        assert abs(async_score - sync_score) < 1e-6  # Allow tiny floating point differences


@pytest.mark.asyncio
async def test_async_search_empty_query(sample_index):
    """Test async search with empty query."""
    results = await sample_index.search_async({}, top_k=5)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_async_search_no_matches(sample_index):
    """Test async search with no matching terms."""
    query = {"nonexistent": 1, "missing": 2, "unknown": 3}
    results = await sample_index.search_async(query, top_k=5)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_async_search_large_query(sample_index):
    """Test async search with many terms (benefits from parallelization)."""
    query = {
        "async": 1,
        "await": 1,
        "performance": 1,
        "optimization": 1,
        "query": 1,
        "search": 1,
        "index": 1,
        "concurrent": 1,
        "parallel": 1,
        "threading": 1,
    }

    results = await sample_index.search_async(query, top_k=5)
    assert len(results) <= 5
    assert len(results) > 0  # Should find some matches


@pytest.mark.asyncio
async def test_async_vs_sync_consistency(sample_index):
    """Test that async and sync searches return identical results for various queries."""
    queries = [
        {"async": 2, "performance": 1},
        {"query": 3, "optimization": 2},
        {"async": 1, "concurrent": 1, "parallel": 1},
        {"database": 2, "sql": 1},
    ]

    for query in queries:
        sync_results = sample_index.search(query, top_k=5)
        async_results = await sample_index.search_async(query, top_k=5)

        assert len(sync_results) == len(async_results), f"Length mismatch for query: {query}"

        for (sync_id, sync_score), (async_id, async_score) in zip(sync_results, async_results):
            assert sync_id == async_id, f"ID mismatch for query: {query}"
            assert abs(sync_score - async_score) < 1e-6, f"Score mismatch for query: {query}"


@pytest.mark.asyncio
async def test_concurrent_async_searches(sample_index):
    """Test multiple concurrent async searches."""
    queries = [
        {"async": 2, "performance": 1},
        {"query": 3, "search": 2},
        {"optimization": 2, "speed": 1},
        {"concurrent": 2, "parallel": 1},
    ]

    # Execute all searches concurrently
    tasks = [sample_index.search_async(q, top_k=3) for q in queries]
    results = await asyncio.gather(*tasks)

    assert len(results) == len(queries)
    for result_set in results:
        assert isinstance(result_set, list)
        assert all(
            isinstance(doc_id, str) and isinstance(score, float) for doc_id, score in result_set
        )


@pytest.mark.skip(reason="Timing-sensitive test - performance varies by platform/load")
@pytest.mark.asyncio
async def test_async_search_performance_benefit(sample_index):
    """Test that async search provides performance benefit for large queries."""
    # Create larger index
    index = SparseIndex()
    terms = [f"term{i}" for i in range(100)]

    # Add 100 documents with overlapping terms
    for doc_idx in range(100):
        sparse_vec = {
            term: (doc_idx + i) % 10 + 1
            for i, term in enumerate(terms[doc_idx % 50 : doc_idx % 50 + 10])
        }
        index.add(f"doc{doc_idx}", sparse_vec)

    index.build()

    # Query with many terms (benefits from parallel processing)
    large_query = {f"term{i}": 1 for i in range(50)}

    # Sync search
    start = time.perf_counter()
    sync_results = index.search(large_query, top_k=20)
    sync_time = time.perf_counter() - start

    # Async search
    start = time.perf_counter()
    async_results = await index.search_async(large_query, top_k=20)
    async_time = time.perf_counter() - start

    # Results should be identical
    assert len(sync_results) == len(async_results)

    # Log timing (async might be faster, but not always guaranteed in small tests)
    print(f"\nSync time: {sync_time:.4f}s, Async time: {async_time:.4f}s")

    # At minimum,    # Async should not be significantly slower (may be slower on some platforms due to overhead)
    # Allow up to 3x slower for platform/overhead differences
    assert (
        async_time < sync_time * 3
    ), f"Async search too slow: {async_time:.4f}s vs sync {sync_time:.4f}s"


@pytest.mark.asyncio
async def test_async_search_top_k_boundary(sample_index):
    """Test async search with various top_k values."""
    query = {"async": 1, "performance": 1}

    # top_k = 0
    results = await sample_index.search_async(query, top_k=0)
    assert len(results) == 0

    # top_k = 1
    results = await sample_index.search_async(query, top_k=1)
    assert len(results) <= 1

    # top_k > total docs
    results = await sample_index.search_async(query, top_k=100)
    assert len(results) <= 5  # We only have 5 docs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

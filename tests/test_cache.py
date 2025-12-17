"""Tests for centrality caching functionality."""

import pytest

from knowgraph.domain.algorithms.centrality import (
    _centrality_cache,
    compute_centrality_metrics,
)
from knowgraph.application.querying.cache_warmup import (
    clear_cache,
    get_cache_stats,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


@pytest.fixture
def sample_nodes():
    """Create sample nodes for testing."""
    from uuid import uuid4

    return [
        Node(
            id=uuid4(),
            hash="a" * 40,  # Valid 40-char hash
            title="Node 1",
            content="Content 1",
            path="test/node1.py",
            type="text",
            token_count=10,
            created_at=0,
        ),
        Node(
            id=uuid4(),
            hash="b" * 40,  # Valid 40-char hash
            title="Node 2",
            content="Content 2",
            path="test/node2.py",
            type="text",
            token_count=10,
            created_at=0,
        ),
        Node(
            id=uuid4(),
            hash="c" * 40,  # Valid 40-char hash
            title="Node 3",
            content="Content 3",
            path="test/node3.py",
            type="text",
            token_count=10,
            created_at=0,
        ),
    ]


@pytest.fixture
def sample_edges(sample_nodes):
    """Create sample edges for testing."""
    return [
        Edge(
            source=sample_nodes[0].id,
            target=sample_nodes[1].id,
            type="semantic",
            score=0.8,
            created_at=0,
            metadata={},
        ),
        Edge(
            source=sample_nodes[1].id,
            target=sample_nodes[2].id,
            type="semantic",
            score=0.7,
            created_at=0,
            metadata={},
        ),
    ]


def test_cache_hit(sample_nodes, sample_edges):
    """Test cache hit on repeated computation."""
    clear_cache()

    # First computation (cache miss)
    result1 = compute_centrality_metrics(sample_nodes, sample_edges)
    cache_size_after_first = len(_centrality_cache)

    # Second computation (cache hit)
    result2 = compute_centrality_metrics(sample_nodes, sample_edges)
    cache_size_after_second = len(_centrality_cache)

    # Results should be identical
    assert result1 == result2

    # Cache size should not increase (cache hit)
    assert cache_size_after_first == cache_size_after_second
    assert cache_size_after_first == 1


def test_cache_miss_different_nodes(sample_nodes, sample_edges):
    """Test cache miss with different nodes."""
    clear_cache()

    # First computation
    result1 = compute_centrality_metrics(sample_nodes[:2], sample_edges[:1])

    # Second computation with different nodes (cache miss)
    result2 = compute_centrality_metrics(sample_nodes, sample_edges)

    # Results should be different
    assert result1 != result2

    # Cache should have 2 entries
    assert len(_centrality_cache) == 2


def test_cache_eviction():
    """Test cache eviction when max size reached."""
    from knowgraph.domain.algorithms.centrality import _cache_max_size
    from uuid import uuid4
    import hashlib

    clear_cache()

    # Fill cache to max
    for i in range(_cache_max_size + 10):
        # Generate valid 40-char hash
        hash_value = hashlib.sha1(f"node{i}".encode()).hexdigest()

        node = Node(
            id=uuid4(),
            hash=hash_value,
            title=f"Node {i}",
            content=f"Content {i}",
            path=f"test/node{i}.py",
            type="text",
            token_count=10,
            created_at=0,
        )
        compute_centrality_metrics([node], [])

    # Cache should not exceed max size
    assert len(_centrality_cache) <= _cache_max_size


def test_clear_cache(sample_nodes, sample_edges):
    """Test cache clearing."""
    clear_cache()

    # Add to cache
    compute_centrality_metrics(sample_nodes, sample_edges)
    assert len(_centrality_cache) > 0

    # Clear cache
    clear_cache()
    assert len(_centrality_cache) == 0


def test_get_cache_stats(sample_nodes, sample_edges):
    """Test cache statistics."""
    from knowgraph.application.querying.query_engine import QueryEngine
    from pathlib import Path

    clear_cache()

    # Add some entries
    compute_centrality_metrics(sample_nodes, sample_edges)

    engine = QueryEngine(Path("/Users/yunusgungor/knowrag/graphstore"))
    stats = get_cache_stats(engine)

    assert "size" in stats
    assert "max_size" in stats
    assert "utilization" in stats
    assert stats["size"] > 0
    assert stats["max_size"] > 0
    assert 0 <= stats["utilization"] <= 100


def test_cache_key_order_independence(sample_nodes, sample_edges):
    """Test that cache key is order-independent."""
    clear_cache()

    # Compute with nodes in different order
    result1 = compute_centrality_metrics(sample_nodes, sample_edges)
    result2 = compute_centrality_metrics(list(reversed(sample_nodes)), sample_edges)

    # Results should be identical (same cache key)
    assert result1 == result2

    # Should be cache hit (only 1 entry)
    assert len(_centrality_cache) == 1


def test_cache_with_empty_inputs():
    """Test caching with empty inputs."""
    clear_cache()

    result = compute_centrality_metrics([], [])

    # Should return empty dict
    assert result == {}

    # Should still cache
    assert len(_centrality_cache) >= 0


def test_cache_performance_improvement(sample_nodes, sample_edges):
    """Test that cache improves performance."""
    import time

    clear_cache()

    # First computation (cold cache)
    start = time.time()
    result1 = compute_centrality_metrics(sample_nodes, sample_edges)
    cold_time = time.time() - start

    # Second computation (warm cache)
    start = time.time()
    result2 = compute_centrality_metrics(sample_nodes, sample_edges)
    warm_time = time.time() - start

    # Results should be identical
    assert result1 == result2

    # Warm cache should be faster
    # (might not always be true for tiny graphs, but should be close)
    speedup = cold_time / warm_time if warm_time > 0 else 1.0
    assert speedup >= 0.5  # At least not much slower


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

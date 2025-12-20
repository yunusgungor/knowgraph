"""Tests for async centrality computation with multiprocessing optimization."""

import asyncio
import time
from uuid import uuid4

import pytest

from knowgraph.domain.algorithms.centrality import (
    clear_centrality_cache,
    compute_centrality_metrics,
    compute_centrality_metrics_async,
    get_cache_stats,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


@pytest.fixture
def sample_graph():
    """Create a sample graph for testing."""
    nodes = [
        Node(
            id=uuid4(),
            content=f"Node {i}",
            title=f"Node {i}",
            path=f"test_{i}.md",
            type="text",
            hash=f"{i:040d}",
            token_count=10,
            created_at=1000000 + i,
            metadata={"index": i},
            header_depth=None,
            header_path=None,
            chunk_id=None,
            line_start=0,
            line_end=1,
        )
        for i in range(10)
    ]

    edges = [
        Edge(
            source=nodes[0].id,
            target=nodes[1].id,
            type="relates_to",
            score=0.8,
            created_at=1000000,
            metadata={},
        ),
        Edge(
            source=nodes[1].id,
            target=nodes[2].id,
            type="relates_to",
            score=0.7,
            created_at=1000000,
            metadata={},
        ),
        Edge(
            source=nodes[2].id,
            target=nodes[3].id,
            type="relates_to",
            score=0.9,
            created_at=1000000,
            metadata={},
        ),
        Edge(
            source=nodes[3].id,
            target=nodes[4].id,
            type="relates_to",
            score=0.6,
            created_at=1000000,
            metadata={},
        ),
        Edge(
            source=nodes[0].id,
            target=nodes[4].id,
            type="relates_to",
            score=0.5,
            created_at=1000000,
            metadata={},
        ),
        Edge(
            source=nodes[1].id,
            target=nodes[3].id,
            type="relates_to",
            score=0.8,
            created_at=1000000,
            metadata={},
        ),
        Edge(
            source=nodes[5].id,
            target=nodes[6].id,
            type="relates_to",
            score=0.7,
            created_at=1000000,
            metadata={},
        ),
        Edge(
            source=nodes[6].id,
            target=nodes[7].id,
            type="relates_to",
            score=0.9,
            created_at=1000000,
            metadata={},
        ),
        Edge(
            source=nodes[7].id,
            target=nodes[8].id,
            type="relates_to",
            score=0.6,
            created_at=1000000,
            metadata={},
        ),
        Edge(
            source=nodes[8].id,
            target=nodes[9].id,
            type="relates_to",
            score=0.8,
            created_at=1000000,
            metadata={},
        ),
    ]

    return nodes, edges


@pytest.fixture
def large_graph():
    """Create a large graph for performance testing."""
    nodes = [
        Node(
            id=uuid4(),
            content=f"Node {i}",
            title=f"Node {i}",
            path=f"test_{i}.md",
            type="text",
            hash=f"{i:040d}",
            token_count=10,
            created_at=1000000 + i,
            metadata={},
            header_depth=None,
            header_path=None,
            chunk_id=None,
            line_start=0,
            line_end=1,
        )
        for i in range(100)
    ]

    edges = []
    # Create a connected graph with many edges
    for i in range(99):
        edges.append(
            Edge(
                source=nodes[i].id,
                target=nodes[i + 1].id,
                type="relates_to",
                score=0.8,
                created_at=1000000,
                metadata={},
            )
        )
        if i % 3 == 0 and i + 3 < 100:
            edges.append(
                Edge(
                    source=nodes[i].id,
                    target=nodes[i + 3].id,
                    type="relates_to",
                    score=0.6,
                    created_at=1000000,
                    metadata={},
                )
            )
        if i % 5 == 0 and i + 5 < 100:
            edges.append(
                Edge(
                    source=nodes[i].id,
                    target=nodes[i + 5].id,
                    type="relates_to",
                    score=0.5,
                    created_at=1000000,
                    metadata={},
                )
            )

    return nodes, edges


def test_sync_centrality(sample_graph):
    """Test synchronous centrality computation."""
    nodes, edges = sample_graph
    clear_centrality_cache()

    metrics = compute_centrality_metrics(nodes, edges)

    assert len(metrics) == len(nodes)
    for node_id, scores in metrics.items():
        assert "betweenness" in scores
        assert "degree" in scores
        assert "closeness" in scores
        assert "eigenvector" in scores
        assert "composite" in scores
        assert 0.0 <= scores["composite"] <= 1.0


@pytest.mark.asyncio
async def test_async_centrality(sample_graph):
    """Test asynchronous centrality computation."""
    nodes, edges = sample_graph
    clear_centrality_cache()

    metrics = await compute_centrality_metrics_async(nodes, edges)

    assert len(metrics) == len(nodes)
    for node_id, scores in metrics.items():
        assert "betweenness" in scores
        assert "degree" in scores
        assert "closeness" in scores
        assert "eigenvector" in scores
        assert "composite" in scores


@pytest.mark.asyncio
async def test_async_vs_sync_consistency(sample_graph):
    """Test that async and sync centrality return identical results."""
    nodes, edges = sample_graph
    clear_centrality_cache()

    sync_metrics = compute_centrality_metrics(nodes, edges)
    clear_centrality_cache()
    async_metrics = await compute_centrality_metrics_async(nodes, edges)

    assert len(sync_metrics) == len(async_metrics)

    for node_id in sync_metrics:
        assert node_id in async_metrics
        for metric_name in ["betweenness", "degree", "closeness", "eigenvector", "composite"]:
            sync_val = sync_metrics[node_id][metric_name]
            async_val = async_metrics[node_id][metric_name]
            # Allow small floating point differences
            assert (
                abs(sync_val - async_val) < 1e-6
            ), f"Mismatch for {metric_name}: {sync_val} vs {async_val}"


@pytest.mark.asyncio
async def test_centrality_caching(sample_graph):
    """Test that centrality results are cached properly."""
    nodes, edges = sample_graph
    clear_centrality_cache()

    # First call
    start = time.perf_counter()
    metrics1 = await compute_centrality_metrics_async(nodes, edges)
    time1 = time.perf_counter() - start

    # Second call (should be cached)
    start = time.perf_counter()
    metrics2 = await compute_centrality_metrics_async(nodes, edges)
    time2 = time.perf_counter() - start

    # Results should be identical
    assert metrics1 == metrics2

    # Cached call should be much faster
    assert time2 < time1 / 2, f"Cache not effective: {time1:.4f}s vs {time2:.4f}s"

    # Check cache stats
    stats = get_cache_stats()
    assert stats["size"] >= 1  # At least one entry cached


@pytest.mark.asyncio
async def test_concurrent_centrality_computation(sample_graph):
    """Test multiple concurrent centrality computations."""
    nodes, edges = sample_graph
    clear_centrality_cache()

    # Create multiple tasks
    tasks = [
        compute_centrality_metrics_async(nodes[:5], edges[:3]),
        compute_centrality_metrics_async(nodes[3:8], edges[2:6]),
        compute_centrality_metrics_async(nodes, edges),
    ]

    # Execute concurrently
    results = await asyncio.gather(*tasks)

    assert len(results) == 3
    for metrics in results:
        assert isinstance(metrics, dict)
        for scores in metrics.values():
            assert "composite" in scores


@pytest.mark.asyncio
async def test_large_graph_performance(large_graph):
    """Test centrality computation on large graph (uses approximate algorithms)."""
    nodes, edges = large_graph
    clear_centrality_cache()

    start = time.perf_counter()
    metrics = await compute_centrality_metrics_async(nodes, edges)
    duration = time.perf_counter() - start

    print(f"\nLarge graph (100 nodes) computation time: {duration:.3f}s")

    assert len(metrics) == 100
    assert duration < 10.0, f"Large graph computation too slow: {duration:.3f}s"


@pytest.mark.asyncio
async def test_cache_size_limit(sample_graph):
    """Test that cache respects size limit."""
    nodes, edges = sample_graph
    clear_centrality_cache()

    # Create many different subgraphs to exceed cache limit
    for i in range(550):  # More than cache size (512)
        subset_nodes = nodes[: (i % 8) + 2]
        subset_edges = edges[: (i % 5) + 1]
        await compute_centrality_metrics_async(subset_nodes, subset_edges)

    stats = get_cache_stats()
    assert stats["size"] <= 512, "Cache exceeded max size"


@pytest.mark.asyncio
async def test_empty_graph():
    """Test centrality on empty graph."""
    metrics = await compute_centrality_metrics_async([], [])
    assert metrics == {}


@pytest.mark.asyncio
async def test_single_node():
    """Test centrality on single isolated node."""
    node = Node(
        id=uuid4(),
        content="Solo",
        title="Solo",
        path="solo.md",
        type="text",
        hash="0" * 40,
        token_count=5,
        created_at=1000000,
        metadata={},
        header_depth=None,
        header_path=None,
        chunk_id=None,
        line_start=0,
        line_end=1,
    )
    metrics = await compute_centrality_metrics_async([node], [])

    assert len(metrics) == 1
    assert metrics[node.id]["composite"] == 0.0


@pytest.mark.asyncio
async def test_disconnected_graph():
    """Test centrality on disconnected graph."""
    nodes = [
        Node(
            id=uuid4(),
            content=f"Node {i}",
            title=f"Node {i}",
            path=f"test_{i}.md",
            type="text",
            hash=f"{i:040d}",
            token_count=10,
            created_at=1000000 + i,
            metadata={},
            header_depth=None,
            header_path=None,
            chunk_id=None,
            line_start=0,
            line_end=1,
        )
        for i in range(6)
    ]

    # Two separate components
    edges = [
        Edge(
            source=nodes[0].id,
            target=nodes[1].id,
            type="relates_to",
            score=0.8,
            created_at=1000000,
            metadata={},
        ),
        Edge(
            source=nodes[1].id,
            target=nodes[2].id,
            type="relates_to",
            score=0.7,
            created_at=1000000,
            metadata={},
        ),
        Edge(
            source=nodes[3].id,
            target=nodes[4].id,
            type="relates_to",
            score=0.9,
            created_at=1000000,
            metadata={},
        ),
        Edge(
            source=nodes[4].id,
            target=nodes[5].id,
            type="relates_to",
            score=0.6,
            created_at=1000000,
            metadata={},
        ),
    ]

    metrics = await compute_centrality_metrics_async(nodes, edges)

    assert len(metrics) == 6
    # All nodes should have centrality scores
    for node_id, scores in metrics.items():
        assert "composite" in scores


@pytest.mark.asyncio
async def test_cache_clear():
    """Test cache clearing functionality."""
    nodes = [
        Node(
            id=uuid4(),
            content=f"Node {i}",
            title=f"Node {i}",
            path=f"test_{i}.md",
            type="text",
            hash=f"{i:040d}",
            token_count=10,
            created_at=1000000 + i,
            metadata={},
            header_depth=None,
            header_path=None,
            chunk_id=None,
            line_start=0,
            line_end=1,
        )
        for i in range(3)
    ]
    edges = [
        Edge(
            source=nodes[0].id,
            target=nodes[1].id,
            type="relates_to",
            score=0.8,
            created_at=1000000,
            metadata={},
        )
    ]

    clear_centrality_cache()
    await compute_centrality_metrics_async(nodes, edges)

    stats_before = get_cache_stats()
    assert stats_before["size"] > 0

    clear_centrality_cache()
    stats_after = get_cache_stats()
    assert stats_after["size"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

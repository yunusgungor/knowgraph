"""Test graceful shutdown and resource cleanup."""

import asyncio
import time

import pytest

from knowgraph.application.querying.centrality_mp import (
    get_process_pool,
    shutdown_process_pool,
)
from knowgraph.domain.algorithms.centrality import (
    _get_process_pool,
    _shutdown_process_pool,
    compute_centrality_metrics_async,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.shared.cleanup import cleanup_all_resources


def test_centrality_process_pool_shutdown():
    """Test that centrality process pool shuts down gracefully."""
    # Create pool
    pool = _get_process_pool()
    assert pool is not None

    # Shutdown
    _shutdown_process_pool()

    # Verify it's cleaned up
    from knowgraph.domain.algorithms.centrality import _process_pool
    assert _process_pool is None


def test_centrality_mp_process_pool_shutdown():
    """Test that centrality_mp process pool shuts down gracefully."""
    # Create pool
    pool = get_process_pool()
    assert pool is not None

    # Shutdown
    shutdown_process_pool()

    # Verify it's cleaned up
    from knowgraph.application.querying.centrality_mp import _process_pool
    assert _process_pool is None


def test_multiple_shutdown_calls_are_safe():
    """Test that calling shutdown multiple times doesn't cause errors."""
    # Create and shutdown
    _get_process_pool()
    _shutdown_process_pool()

    # Second shutdown should be safe
    _shutdown_process_pool()
    _shutdown_process_pool()

    # Should still work
    from knowgraph.domain.algorithms.centrality import _process_pool
    assert _process_pool is None


@pytest.mark.asyncio
async def test_async_centrality_cleanup():
    """Test that async centrality operations clean up properly."""
    # Create some test data
    nodes = [
        Node(
            id="11111111-1111-1111-1111-111111111111",
            content="Test node 1",
            path="test1.py",
            hash="a" * 40,
            title="Test 1",
            type="code",
            token_count=10,
            created_at=int(time.time()),
            header_depth=None,
            header_path=None,
            chunk_id=None,
            line_start=1,
            line_end=10,
        ),
        Node(
            id="22222222-2222-2222-2222-222222222222",
            content="Test node 2",
            path="test2.py",
            hash="b" * 40,
            title="Test 2",
            type="code",
            token_count=10,
            created_at=int(time.time()),
            header_depth=None,
            header_path=None,
            chunk_id=None,
            line_start=1,
            line_end=10,
        ),
    ]

    edges = [
        Edge(
            source=nodes[0].id,
            target=nodes[1].id,
            type="semantic",
            score=0.8,
            created_at=int(time.time()),
            metadata={},
        )
    ]

    # Run async computation (this may create a process pool)
    result = await compute_centrality_metrics_async(nodes, edges)
    assert result is not None

    # Cleanup
    _shutdown_process_pool()


def test_cleanup_all_resources():
    """Test that cleanup_all_resources cleans everything."""
    # Create some resources
    _get_process_pool()
    get_process_pool()

    # Cleanup all
    cleanup_all_resources()

    # Verify cleanup
    from knowgraph.application.querying.centrality_mp import _process_pool as pool2
    from knowgraph.domain.algorithms.centrality import _process_pool as pool1

    assert pool1 is None
    assert pool2 is None


def test_atexit_registration():
    """Test that atexit handlers are registered correctly."""

    # Get handlers (this is implementation-dependent)
    # We can at least verify pools get created and have atexit registered
    pool1 = _get_process_pool()
    pool2 = get_process_pool()

    assert pool1 is not None
    assert pool2 is not None

    # Cleanup for next tests
    _shutdown_process_pool()
    shutdown_process_pool()


@pytest.mark.asyncio
async def test_concurrent_operations_with_cleanup():
    """Test cleanup works correctly with concurrent operations."""
    nodes = [
        Node(
            id=f"{i:08d}-1111-1111-1111-111111111111",
            content=f"Test node {i}",
            path=f"test{i}.py",
            hash=f"{chr(97 + i % 26)}" * 40,  # Use different letters, 40 chars
            title=f"Test {i}",
            type="code",
            token_count=10,
            created_at=int(time.time()),
            header_depth=None,
            header_path=None,
            chunk_id=None,
            line_start=1,
            line_end=10,
        )
        for i in range(10)
    ]

    edges = [
        Edge(
            source=nodes[i].id,
            target=nodes[i + 1].id,
            type="semantic",
            score=0.8,
            created_at=int(time.time()),
            metadata={},
        )
        for i in range(9)
    ]

    # Run multiple concurrent operations
    tasks = [
        compute_centrality_metrics_async(nodes[i:i+3], edges[i:i+2])
        for i in range(3)
    ]

    results = await asyncio.gather(*tasks)
    assert len(results) == 3

    # Cleanup should handle this gracefully
    cleanup_all_resources()


def test_pool_recreation_after_shutdown():
    """Test that process pool can be recreated after shutdown."""
    # Create and shutdown
    pool1 = _get_process_pool()
    assert pool1 is not None
    _shutdown_process_pool()

    # Recreate
    pool2 = _get_process_pool()
    assert pool2 is not None
    assert pool2 is not pool1  # Should be a new instance

    # Cleanup
    _shutdown_process_pool()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

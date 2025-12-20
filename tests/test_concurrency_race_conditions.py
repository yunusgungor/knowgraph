"""Race condition and concurrency stress tests for Phase 3.

Tests concurrent operations to ensure thread safety and data consistency.
"""

import asyncio
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest

from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.storage.filesystem import (
    read_node_json,
    write_node_json,
    write_node_json_async,
)


def create_test_node(i: int) -> Node:
    """Create a test node with unique ID."""
    return Node(
        id=uuid4(),
        hash=f"{i:010d}" + "0" * 30,
        title=f"Concurrent Test Node {i}",
        content=f"Content for concurrent test {i}",
        path=f"test/concurrent_{i}.md",
        type="text",
        token_count=10,
        created_at=int(time.time()),
    )


@pytest.fixture
def temp_graph():
    """Create temporary graph for testing."""
    with TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "graphstore"
        graph_path.mkdir(parents=True)
        (graph_path / "nodes").mkdir()
        (graph_path / "metadata").mkdir()
        yield graph_path


@pytest.mark.asyncio
async def test_concurrent_writes_no_race_condition(temp_graph):
    """Test that concurrent writes don't corrupt data."""
    nodes = [create_test_node(i) for i in range(20)]

    # Write all nodes concurrently
    await asyncio.gather(*[write_node_json_async(node, temp_graph) for node in nodes])

    # Verify all nodes are readable and correct
    for node in nodes:
        loaded_node = read_node_json(node.id, temp_graph)
        assert loaded_node is not None
        assert loaded_node.id == node.id
        assert loaded_node.title == node.title
        assert loaded_node.content == node.content


@pytest.mark.asyncio
async def test_concurrent_read_write_consistency(temp_graph):
    """Test that concurrent reads during writes remain consistent."""
    node = create_test_node(1)
    write_node_json(node, temp_graph)

    # Concurrent reads while writing
    async def read_node():
        return read_node_json(node.id, temp_graph)

    async def update_node():
        # Simulate update
        updated = Node(
            id=node.id,
            hash=node.hash,
            title=node.title + " UPDATED",
            content=node.content,
            path=node.path,
            type=node.type,
            token_count=node.token_count,
            created_at=node.created_at,
        )
        await write_node_json_async(updated, temp_graph)

    # Execute 10 reads and 1 write concurrently
    tasks = [read_node() for _ in range(10)] + [update_node()]
    results = await asyncio.gather(*tasks)

    # All reads should succeed (no corruption)
    read_results = results[:-1]  # Exclude write task
    assert all(r is not None for r in read_results)


@pytest.mark.asyncio
async def test_high_concurrency_stress(temp_graph):
    """Stress test with high concurrency (50 concurrent operations)."""
    nodes = [create_test_node(i) for i in range(50)]

    start = time.time()

    # Write 50 nodes concurrently
    await asyncio.gather(*[write_node_json_async(node, temp_graph) for node in nodes])

    end = time.time()
    duration = end - start

    # Should complete in reasonable time (< 5 seconds for 50 nodes)
    assert duration < 5.0, f"Took {duration:.2f}s - too slow!"

    # Verify all written correctly
    for node in nodes:
        loaded = read_node_json(node.id, temp_graph)
        assert loaded is not None
        assert loaded.id == node.id


def test_thread_pool_concurrent_reads(temp_graph):
    """Test concurrent reads using ThreadPoolExecutor (sync version)."""
    from concurrent.futures import ThreadPoolExecutor

    # Create and write test nodes
    nodes = [create_test_node(i) for i in range(30)]
    for node in nodes:
        write_node_json(node, temp_graph)

    # Read all concurrently with thread pool
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(read_node_json, node.id, temp_graph) for node in nodes]
        results = [f.result() for f in futures]

    # All reads should succeed
    assert len(results) == 30
    assert all(r is not None for r in results)

    # Verify data integrity
    for original, loaded in zip(nodes, results):
        assert loaded.id == original.id
        assert loaded.title == original.title


@pytest.mark.asyncio
async def test_no_data_loss_under_load(temp_graph):
    """Ensure no data loss when writing many nodes rapidly."""
    num_nodes = 100
    nodes = [create_test_node(i) for i in range(num_nodes)]

    # Write all nodes as fast as possible
    await asyncio.gather(*[write_node_json_async(node, temp_graph) for node in nodes])

    # Count how many were actually written
    written_count = 0
    for node in nodes:
        if read_node_json(node.id, temp_graph):
            written_count += 1

    # Should have 100% success rate
    assert written_count == num_nodes, f"Lost {num_nodes - written_count} nodes!"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

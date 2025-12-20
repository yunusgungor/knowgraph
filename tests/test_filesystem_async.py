"""Simple async tests for filesystem module to boost coverage.

Using exact same Node/Edge constructors from test_filesystem.py
"""

import asyncio
from uuid import uuid4

import pytest

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.storage.filesystem import (
    read_all_edges_async,
    read_node_json_async,
    write_all_edges_async,
    write_node_json_async,
)


@pytest.fixture
def store_path(tmp_path):
    """Create temp storage path."""
    p = tmp_path / "store"
    p.mkdir()
    return p


@pytest.mark.asyncio
async def test_async_node_write_read(store_path):
    """Test async write and read of node."""
    uid = uuid4()
    node = Node(
        id=uid,
        hash="a" * 40,
        title="Async Test",
        content="Async content",
        path="async.md",
        type="text",
        token_count=5,
        created_at=1234567890,
    )

    await write_node_json_async(node, store_path)
    loaded = await read_node_json_async(uid, store_path)

    assert loaded is not None
    assert loaded.id == uid
    assert loaded.title == "Async Test"


@pytest.mark.asyncio
async def test_async_read_nonexistent(store_path):
    """Test async read of non-existent node returns None."""
    result = await read_node_json_async(uuid4(), store_path)
    assert result is None


@pytest.mark.asyncio
async def test_async_edges_write_read(store_path):
    """Test async write and read of edges."""
    edges = [
        Edge(
            source=uuid4(),
            target=uuid4(),
            type="test1",
            score=0.9,
            created_at=1234567890,
            metadata={"async": True},
        ),
        Edge(
            source=uuid4(),
            target=uuid4(),
            type="test2",
            score=0.7,
            created_at=1234567890,
            metadata={"async": True},
        ),
    ]

    await write_all_edges_async(edges, store_path)
    loaded = await read_all_edges_async(store_path)

    assert len(loaded) == 2
    assert loaded[0].metadata["async"] is True


@pytest.mark.asyncio
async def test_async_edges_read_empty(store_path):
    """Test async read when no edges file exists."""
    result = await read_all_edges_async(store_path)
    assert result == []


@pytest.mark.asyncio
async def test_concurrent_node_writes(store_path):
    """Test writing multiple nodes concurrently."""
    nodes = []
    for i in range(5):
        nodes.append(
            Node(
                id=uuid4(),
                hash=f"{i}" * 40,
                title=f"Node {i}",
                content=f"Content {i}",
                path=f"file{i}.md",
                type="text",
                token_count=10,
                created_at=1234567890,
            )
        )

    # Write concurrently
    await asyncio.gather(*[write_node_json_async(n, store_path) for n in nodes])

    # Read back
    for node in nodes:
        loaded = await read_node_json_async(node.id, store_path)
        assert loaded is not None
        assert loaded.id == node.id


@pytest.mark.asyncio
async def test_concurrent_node_reads(store_path):
    """Test reading same node concurrently."""
    uid = uuid4()
    node = Node(
        id=uid,
        hash="x" * 40,
        title="Concurrent",
        content="Read test",
        path="test.md",
        type="text",
        token_count=5,
        created_at=1234567890,
    )

    await write_node_json_async(node, store_path)

    # Read 10 times concurrently
    results = await asyncio.gather(*[read_node_json_async(uid, store_path) for _ in range(10)])

    assert all(r is not None for r in results)
    assert all(r.id == uid for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

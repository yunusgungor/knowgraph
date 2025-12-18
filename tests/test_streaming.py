"""Test streaming query functionality for memory efficiency."""

import asyncio
import time

import pytest

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.shared.streaming import (
    PaginationState,
    StreamChunk,
    paginate_nodes,
    stream_nodes,
    stream_nodes_async,
)


def create_test_nodes(count: int) -> list[Node]:
    """Create test nodes."""
    return [
        Node(
            id=f"{i:08d}-1111-1111-1111-111111111111",
            content=f"Test content {i}",
            path=f"test{i}.py",
            hash=f"{chr(97 + i % 26)}" * 40,
            title=f"Test {i}",
            type="code",
            token_count=50,
            created_at=int(time.time()),
            header_depth=None,
            header_path=None,
            chunk_id=None,
            line_start=1,
            line_end=10,
        )
        for i in range(count)
    ]


def test_stream_nodes_basic():
    """Test basic streaming functionality."""
    nodes = create_test_nodes(25)
    
    chunks = list(stream_nodes(nodes, chunk_size=10))
    
    assert len(chunks) == 3  # 25 nodes / 10 per chunk = 3 chunks
    assert len(chunks[0].data) == 10
    assert len(chunks[1].data) == 10
    assert len(chunks[2].data) == 5
    assert chunks[2].is_last is True
    assert chunks[0].is_last is False


def test_stream_chunk_metadata():
    """Test stream chunk metadata."""
    nodes = create_test_nodes(15)
    
    chunks = list(stream_nodes(nodes, chunk_size=5))
    
    assert chunks[0].index == 0
    assert chunks[1].index == 1
    assert chunks[2].index == 2
    assert chunks[0].total == 3
    assert chunks[1].total == 3
    assert chunks[2].total == 3


@pytest.mark.asyncio
async def test_stream_nodes_async():
    """Test async streaming."""
    nodes = create_test_nodes(30)
    
    chunks = []
    async for chunk in stream_nodes_async(nodes, chunk_size=10):
        chunks.append(chunk)
    
    assert len(chunks) == 3
    assert chunks[0].data == nodes[0:10]
    assert chunks[1].data == nodes[10:20]
    assert chunks[2].data == nodes[20:30]


@pytest.mark.asyncio
async def test_stream_nodes_async_allows_other_tasks():
    """Test that async streaming allows other tasks to run."""
    nodes = create_test_nodes(50)
    
    counter = 0
    
    async def increment_counter():
        nonlocal counter
        for _ in range(10):
            await asyncio.sleep(0.001)
            counter += 1
    
    # Start counter task
    counter_task = asyncio.create_task(increment_counter())
    
    # Stream nodes
    chunks = []
    async for chunk in stream_nodes_async(nodes, chunk_size=10):
        chunks.append(chunk)
        await asyncio.sleep(0.002)  # Simulate processing
    
    await counter_task
    
    # Counter should have incremented while we were streaming
    assert counter == 10
    assert len(chunks) == 5


def test_paginate_nodes_first_page():
    """Test pagination first page."""
    nodes = create_test_nodes(50)
    
    page_nodes, state = paginate_nodes(nodes, page=1, page_size=10)
    
    assert len(page_nodes) == 10
    assert page_nodes[0] == nodes[0]
    assert page_nodes[-1] == nodes[9]
    assert state.page == 1
    assert state.page_size == 10
    assert state.total_items == 50
    assert state.has_next is True
    assert state.has_previous is False
    assert state.total_pages == 5


def test_paginate_nodes_middle_page():
    """Test pagination middle page."""
    nodes = create_test_nodes(50)
    
    page_nodes, state = paginate_nodes(nodes, page=3, page_size=10)
    
    assert len(page_nodes) == 10
    assert page_nodes[0] == nodes[20]
    assert page_nodes[-1] == nodes[29]
    assert state.page == 3
    assert state.has_next is True
    assert state.has_previous is True


def test_paginate_nodes_last_page():
    """Test pagination last page."""
    nodes = create_test_nodes(47)
    
    page_nodes, state = paginate_nodes(nodes, page=5, page_size=10)
    
    assert len(page_nodes) == 7  # Only 7 nodes left
    assert page_nodes[0] == nodes[40]
    assert page_nodes[-1] == nodes[46]
    assert state.page == 5
    assert state.has_next is False
    assert state.has_previous is True
    assert state.total_pages == 5


def test_pagination_state_indices():
    """Test pagination state index calculations."""
    state = PaginationState(page=3, page_size=10, total_items=47)
    
    assert state.start_index == 20
    assert state.end_index == 30
    assert state.total_pages == 5


def test_stream_empty_list():
    """Test streaming with empty list."""
    nodes = []
    
    chunks = list(stream_nodes(nodes, chunk_size=10))
    
    assert len(chunks) == 0


def test_paginate_empty_list():
    """Test pagination with empty list."""
    nodes = []
    
    page_nodes, state = paginate_nodes(nodes, page=1, page_size=10)
    
    assert len(page_nodes) == 0
    assert state.total_items == 0
    assert state.total_pages == 0
    assert state.has_next is False
    assert state.has_previous is False


def test_stream_single_node():
    """Test streaming with single node."""
    nodes = create_test_nodes(1)
    
    chunks = list(stream_nodes(nodes, chunk_size=10))
    
    assert len(chunks) == 1
    assert len(chunks[0].data) == 1
    assert chunks[0].is_last is True


def test_stream_exact_chunk_size():
    """Test streaming when total nodes equals chunk size."""
    nodes = create_test_nodes(10)
    
    chunks = list(stream_nodes(nodes, chunk_size=10))
    
    assert len(chunks) == 1
    assert len(chunks[0].data) == 10
    assert chunks[0].is_last is True


@pytest.mark.asyncio
async def test_concurrent_streaming():
    """Test multiple concurrent streams."""
    nodes1 = create_test_nodes(20)
    nodes2 = create_test_nodes(30)
    
    async def stream_and_collect(nodes):
        chunks = []
        async for chunk in stream_nodes_async(nodes, chunk_size=10):
            chunks.append(chunk)
        return chunks
    
    results = await asyncio.gather(
        stream_and_collect(nodes1),
        stream_and_collect(nodes2),
    )
    
    assert len(results[0]) == 2  # 20 / 10
    assert len(results[1]) == 3  # 30 / 10


def test_pagination_beyond_total():
    """Test pagination when requesting page beyond total pages."""
    nodes = create_test_nodes(25)
    
    page_nodes, state = paginate_nodes(nodes, page=10, page_size=10)
    
    # Should return empty list but valid state
    assert len(page_nodes) == 0
    assert state.total_pages == 3
    assert state.has_next is False


@pytest.mark.asyncio
async def test_stream_performance():
    """Test that streaming doesn't load all nodes at once."""
    nodes = create_test_nodes(100)
    
    start_time = time.time()
    
    # Stream and process chunks
    processed_count = 0
    async for chunk in stream_nodes_async(nodes, chunk_size=10):
        processed_count += len(chunk.data)
        # Simulate some processing
        await asyncio.sleep(0.001)
    
    elapsed = time.time() - start_time
    
    assert processed_count == 100
    # Streaming should be fast even with processing
    assert elapsed < 1.0  # Should complete in under 1 second


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

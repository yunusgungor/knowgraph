"""Memory leak detection tests for Phase 7 completion.

Tests various operations to ensure no memory leaks in:
- Async operations
- Caching mechanisms
- Parallel processing
- Long-running operations
"""

import asyncio
import gc
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest

from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder
from knowgraph.infrastructure.storage.filesystem import (
    write_node_json,
    write_node_json_async,
)
from knowgraph.shared.memory_profiler import get_memory_usage_mb


def create_test_node(i: int) -> Node:
    """Create a test node."""
    return Node(
        id=uuid4(),
        hash=f"{i:010d}" + "0" * 30,
        title=f"Leak Test Node {i}",
        content=f"Content for leak test {i}" * 100,  # Larger content
        path=f"test/leak_{i}.md",
        type="text",
        token_count=100,
        created_at=int(time.time()),
    )


@pytest.fixture
def temp_graph():
    """Create temporary graph."""
    with TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "graphstore"
        graph_path.mkdir(parents=True)
        (graph_path / "nodes").mkdir()
        (graph_path / "metadata").mkdir()
        yield graph_path


def test_no_leak_repeated_sync_writes(temp_graph):
    """Test that repeated sync writes don't leak memory."""
    gc.collect()
    initial_mem = get_memory_usage_mb()

    # Write 100 nodes repeatedly
    for _ in range(10):
        nodes = [create_test_node(i) for i in range(100)]
        for node in nodes:
            write_node_json(node, temp_graph)
        del nodes
        gc.collect()

    final_mem = get_memory_usage_mb()
    leak = final_mem - initial_mem

    # Should not leak more than 20MB
    assert leak < 20, f"Leaked {leak:.1f}MB in sync writes"


@pytest.mark.asyncio
async def test_no_leak_repeated_async_writes(temp_graph):
    """Test that repeated async writes don't leak memory."""
    gc.collect()
    initial_mem = get_memory_usage_mb()

    # Write 100 nodes repeatedly (async)
    for _ in range(10):
        nodes = [create_test_node(i) for i in range(100)]
        await asyncio.gather(*[write_node_json_async(node, temp_graph) for node in nodes])
        del nodes
        gc.collect()

    final_mem = get_memory_usage_mb()
    leak = final_mem - initial_mem

    # Should not leak more than 20MB
    assert leak < 20, f"Leaked {leak:.1f}MB in async writes"


def test_no_leak_embeddings_cache():
    """Test that embedding cache doesn't cause memory leaks."""
    embedder = SparseEmbedder()

    gc.collect()
    initial_mem = get_memory_usage_mb()

    # Generate embeddings for same texts repeatedly (should hit cache)
    texts = [f"test text {i}" for i in range(100)]

    for _ in range(50):  # Repeat 50 times
        for text in texts:
            _ = embedder.embed_text(text)

    gc.collect()
    final_mem = get_memory_usage_mb()
    leak = final_mem - initial_mem

    # Cache should stabilize, leak should be minimal (<10MB)
    assert leak < 10, f"Leaked {leak:.1f}MB in embedding cache"


def test_no_leak_large_text_processing():
    """Test no leak when processing large texts."""
    embedder = SparseEmbedder()

    gc.collect()
    initial_mem = get_memory_usage_mb()

    # Process large texts
    for i in range(100):
        large_text = f"This is a large text for testing {i}. " * 1000
        _ = embedder.embed_text(large_text)
        del large_text

    gc.collect()
    final_mem = get_memory_usage_mb()
    leak = final_mem - initial_mem

    # Should not leak significantly
    assert leak < 30, f"Leaked {leak:.1f}MB in large text processing"


@pytest.mark.asyncio
async def test_no_leak_concurrent_operations(temp_graph):
    """Test no leak in high concurrency scenarios."""
    gc.collect()
    initial_mem = get_memory_usage_mb()

    # Run many concurrent operations
    for batch in range(5):
        nodes = [create_test_node(batch * 100 + i) for i in range(100)]

        # 100 concurrent writes
        await asyncio.gather(*[write_node_json_async(node, temp_graph) for node in nodes])

        del nodes
        gc.collect()

    final_mem = get_memory_usage_mb()
    leak = final_mem - initial_mem

    # Should not leak more than 25MB
    assert leak < 25, f"Leaked {leak:.1f}MB in concurrent operations"


def test_no_leak_repeated_node_creation():
    """Test that repeated node creation/destruction doesn't leak."""
    gc.collect()
    initial_mem = get_memory_usage_mb()

    # Create and destroy many nodes
    for _ in range(1000):
        nodes = [create_test_node(i) for i in range(50)]
        # Process nodes (simulate real usage)
        _ = [node.id for node in nodes]
        _ = [node.content for node in nodes]
        del nodes

    gc.collect()
    final_mem = get_memory_usage_mb()
    leak = final_mem - initial_mem

    # Should not leak
    assert leak < 15, f"Leaked {leak:.1f}MB in node creation/destruction"


@pytest.mark.asyncio
async def test_no_leak_asyncio_tasks():
    """Test that asyncio tasks don't leak."""
    gc.collect()
    initial_mem = get_memory_usage_mb()

    async def dummy_task(i: int):
        await asyncio.sleep(0.001)
        return i * 2

    # Create and await many tasks
    for _ in range(100):
        tasks = [dummy_task(i) for i in range(50)]
        results = await asyncio.gather(*tasks)
        del tasks, results

    gc.collect()
    final_mem = get_memory_usage_mb()
    leak = final_mem - initial_mem

    # Async tasks should not leak
    assert leak < 10, f"Leaked {leak:.1f}MB in asyncio tasks"


def test_memory_profiler_no_leak():
    """Test that memory profiler itself doesn't leak."""
    from knowgraph.shared.memory_profiler import memory_guard

    gc.collect()
    initial_mem = get_memory_usage_mb()

    # Use memory guard repeatedly
    for i in range(200):
        with memory_guard(f"test_{i}"):
            data = [0] * 10000
            del data

    gc.collect()
    final_mem = get_memory_usage_mb()
    leak = final_mem - initial_mem

    # Memory profiler should not leak
    assert leak < 5, f"Leaked {leak:.1f}MB in memory profiler"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

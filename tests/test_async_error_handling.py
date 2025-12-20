"""Tests for async error handling, timeouts, and cancellation."""

import asyncio
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from knowgraph.domain.models.node import Node


@pytest.fixture
def temp_graph_store():
    """Create temporary graph store."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_nodes():
    """Create sample nodes for testing."""
    return [
        Node(
            id=uuid4(),
            hash="a" * 40,
            title="Node 1",
            content="Content 1",
            path="test1.md",
            type="semantic",
            token_count=10,
            created_at=1000000,
            metadata={},
        ),
        Node(
            id=uuid4(),
            hash="b" * 40,
            title="Node 2",
            content="Content 2",
            path="test2.md",
            type="semantic",
            token_count=20,
            created_at=1000001,
            metadata={},
        ),
    ]


@pytest.mark.asyncio
async def test_asyncio_timeout_error():
    """Test that asyncio.TimeoutError is properly raised."""

    async def slow_operation():
        await asyncio.sleep(10)  # Long operation
        return "result"

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_operation(), timeout=0.1)


@pytest.mark.asyncio
async def test_async_exception_propagation():
    """Test that exceptions propagate correctly through async calls."""

    async def failing_operation():
        raise ValueError("Test error")

    async def wrapper():
        return await failing_operation()

    with pytest.raises(ValueError, match="Test error"):
        await wrapper()


@pytest.mark.asyncio
async def test_async_task_cancellation():
    """Test proper handling of task cancellation."""

    cancelled_flag = False

    async def cancellable_operation():
        nonlocal cancelled_flag
        try:
            await asyncio.sleep(10)
            return "completed"
        except asyncio.CancelledError:
            cancelled_flag = True
            raise

    task = asyncio.create_task(cancellable_operation())
    await asyncio.sleep(0.01)  # Let task start

    # Cancel and wait for cancellation to propagate
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass  # Expected

    # Verify cancellation was handled
    assert cancelled_flag or task.cancelled()


@pytest.mark.asyncio
async def test_concurrent_error_handling():
    """Test error handling in concurrent async operations."""

    async def operation_success():
        await asyncio.sleep(0.01)
        return "success"

    async def operation_fail():
        await asyncio.sleep(0.01)
        raise RuntimeError("Concurrent error")

    # gather with return_exceptions=False (default) propagates first exception
    with pytest.raises(RuntimeError, match="Concurrent error"):
        await asyncio.gather(operation_success(), operation_fail(), operation_success())


@pytest.mark.asyncio
async def test_concurrent_errors_with_exception_collection():
    """Test collecting all exceptions from concurrent operations."""

    async def operation_fail_1():
        await asyncio.sleep(0.01)
        raise ValueError("Error 1")

    async def operation_fail_2():
        await asyncio.sleep(0.02)
        raise TypeError("Error 2")

    async def operation_success():
        await asyncio.sleep(0.01)
        return "success"

    # return_exceptions=True collects all results including exceptions
    results = await asyncio.gather(
        operation_fail_1(), operation_fail_2(), operation_success(), return_exceptions=True
    )

    assert len(results) == 3
    assert isinstance(results[0], ValueError)
    assert isinstance(results[1], TypeError)
    assert results[2] == "success"


@pytest.mark.asyncio
async def test_retriever_async_with_mock_timeout():
    """Test async timeout pattern with mocked slow operation."""

    async def slow_retrieval():
        """Simulate slow retrieval operation."""
        await asyncio.sleep(10)
        return []

    # Test that timeout works correctly
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_retrieval(), timeout=0.1)


@pytest.mark.asyncio
async def test_exception_in_async_generator():
    """Test exception handling in async generators."""

    async def failing_generator():
        yield 1
        yield 2
        raise RuntimeError("Generator failed")
        yield 3  # Never reached

    results = []
    with pytest.raises(RuntimeError, match="Generator failed"):
        async for value in failing_generator():
            results.append(value)

    assert results == [1, 2]


@pytest.mark.asyncio
async def test_async_context_manager_error():
    """Test error handling with async context managers."""

    class AsyncResource:
        def __init__(self):
            self.opened = False
            self.closed = False

        async def __aenter__(self):
            self.opened = True
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            self.closed = True
            return False  # Don't suppress exception

    resource = AsyncResource()

    with pytest.raises(ValueError, match="Context error"):
        async with resource:
            assert resource.opened
            raise ValueError("Context error")

    # Verify cleanup happened despite error
    assert resource.closed


@pytest.mark.asyncio
async def test_multiple_concurrent_timeouts():
    """Test handling multiple operations with different timeouts."""

    async def operation_fast():
        await asyncio.sleep(0.01)
        return "fast"

    async def operation_medium():
        await asyncio.sleep(0.5)
        return "medium"

    async def operation_slow():
        await asyncio.sleep(2.0)
        return "slow"

    # Run with different timeouts
    results = await asyncio.gather(
        asyncio.wait_for(operation_fast(), timeout=1.0),
        asyncio.wait_for(operation_medium(), timeout=1.0),
        asyncio.wait_for(operation_slow(), timeout=0.1),
        return_exceptions=True,
    )

    assert results[0] == "fast"
    assert results[1] == "medium"
    assert isinstance(results[2], asyncio.TimeoutError)


@pytest.mark.asyncio
async def test_async_retry_pattern():
    """Test retry pattern for transient failures."""

    call_count = 0

    async def flaky_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("Transient error")
        return "success"

    # Retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = await flaky_operation()
            break
        except ConnectionError:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(0.01 * (attempt + 1))  # Exponential backoff

    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_async_semaphore_with_errors():
    """Test semaphore behavior when operations fail."""

    semaphore = asyncio.Semaphore(2)  # Max 2 concurrent
    completed = []
    failed = []

    async def limited_operation(task_id: int, should_fail: bool):
        async with semaphore:
            await asyncio.sleep(0.01)
            if should_fail:
                failed.append(task_id)
                raise RuntimeError(f"Task {task_id} failed")
            completed.append(task_id)
            return task_id

    results = await asyncio.gather(
        limited_operation(1, False),
        limited_operation(2, True),
        limited_operation(3, False),
        limited_operation(4, True),
        limited_operation(5, False),
        return_exceptions=True,
    )

    # Verify semaphore released even on errors
    assert len(completed) == 3
    assert len(failed) == 2
    assert sum(isinstance(r, RuntimeError) for r in results) == 2


@pytest.mark.asyncio
async def test_async_queue_error_handling():
    """Test error handling with asyncio queues."""

    queue = asyncio.Queue(maxsize=5)

    async def producer():
        for i in range(3):
            await queue.put(i)
        await queue.put(Exception("Producer error"))
        await queue.put(None)  # Sentinel

    async def consumer():
        results = []
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            results.append(item)
        return results

    producer_task = asyncio.create_task(producer())

    with pytest.raises(Exception, match="Producer error"):
        await consumer()

    await producer_task


@pytest.mark.asyncio
async def test_async_exception_in_task_group():
    """Test exception handling in task groups."""

    async def task_success():
        await asyncio.sleep(0.01)
        return "success"

    async def task_failure():
        await asyncio.sleep(0.02)
        raise ValueError("Task failed")

    exception_caught = None

    tasks = [
        asyncio.create_task(task_success()),
        asyncio.create_task(task_failure()),
        asyncio.create_task(task_success()),
    ]

    try:
        await asyncio.gather(*tasks)
    except ValueError as e:
        exception_caught = e
        # Cancel remaining tasks
        for task in tasks:
            if not task.done():
                task.cancel()

    assert exception_caught is not None
    assert str(exception_caught) == "Task failed"


@pytest.mark.asyncio
async def test_nested_async_error_propagation():
    """Test that errors propagate through nested async calls."""

    async def level_3():
        raise RuntimeError("Deep error")

    async def level_2():
        return await level_3()

    async def level_1():
        return await level_2()

    with pytest.raises(RuntimeError, match="Deep error"):
        await level_1()


@pytest.mark.asyncio
async def test_async_with_finally_cleanup():
    """Test that finally blocks execute on async errors."""

    cleanup_executed = False

    async def operation_with_cleanup():
        nonlocal cleanup_executed
        try:
            await asyncio.sleep(0.01)
            raise ValueError("Operation failed")
        finally:
            cleanup_executed = True

    with pytest.raises(ValueError, match="Operation failed"):
        await operation_with_cleanup()

    assert cleanup_executed


@pytest.mark.asyncio
async def test_concurrent_node_loading_with_failures(sample_nodes):
    """Test concurrent node loading with some failures."""

    async def load_node(node: Node, should_fail: bool):
        await asyncio.sleep(0.01)
        if should_fail:
            raise OSError(f"Failed to load {node.id}")
        return node

    # Load with some failures
    results = await asyncio.gather(
        load_node(sample_nodes[0], False), load_node(sample_nodes[1], True), return_exceptions=True
    )

    assert isinstance(results[0], Node)
    assert isinstance(results[1], IOError)


@pytest.mark.asyncio
async def test_timeout_with_cleanup():
    """Test that cleanup happens even on timeout."""

    resources_released = []

    async def operation_with_resources():
        resource_id = 1
        try:
            await asyncio.sleep(10)
            return "done"
        except asyncio.CancelledError:
            resources_released.append(resource_id)
            raise
        finally:
            resources_released.append(resource_id)

    try:
        await asyncio.wait_for(operation_with_resources(), timeout=0.1)
    except asyncio.TimeoutError:
        pass

    # Give cleanup time to execute
    await asyncio.sleep(0.01)

    # Verify cleanup executed
    assert len(resources_released) >= 1

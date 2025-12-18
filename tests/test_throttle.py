"""Tests for request throttle."""

import asyncio
import time

import pytest

from knowgraph.shared.throttle import (
    Priority,
    QueueFullError,
    RequestThrottle,
    ThrottleConfig,
    ThrottleStats,
    clear_throttles,
    get_throttle,
    throttle_requests,
)


class TestThrottleConfig:
    """Test throttle configuration."""

    def test_default_config(self):
        """Test default configuration."""
        config = ThrottleConfig()
        assert config.max_concurrent == 10
        assert config.queue_size == 100
        assert config.min_delay == 0.0
        assert config.adaptive is True
        assert config.timeout is None

    def test_custom_config(self):
        """Test custom configuration."""
        config = ThrottleConfig(
            max_concurrent=5,
            queue_size=20,
            min_delay=0.1,
            adaptive=False,
            timeout=30.0,
        )
        assert config.max_concurrent == 5
        assert config.queue_size == 20
        assert config.min_delay == 0.1
        assert config.adaptive is False
        assert config.timeout == 30.0


class TestThrottleStats:
    """Test throttle statistics."""

    def test_stats_initialization(self):
        """Test stats initialization."""
        stats = ThrottleStats()
        assert stats.active_requests == 0
        assert stats.queued_requests == 0
        assert stats.total_requests == 0
        assert stats.completed_requests == 0
        assert stats.failed_requests == 0
        assert stats.total_wait_time == 0.0
        assert stats.max_wait_time == 0.0
        assert stats.avg_wait_time == 0.0

    def test_update_wait_time(self):
        """Test wait time updates."""
        stats = ThrottleStats()
        stats.completed_requests = 1
        stats.update_wait_time(1.0)

        assert stats.total_wait_time == 1.0
        assert stats.max_wait_time == 1.0
        assert stats.avg_wait_time == 1.0

        stats.completed_requests = 2
        stats.update_wait_time(2.0)

        assert stats.total_wait_time == 3.0
        assert stats.max_wait_time == 2.0
        assert stats.avg_wait_time == 1.5


class TestRequestThrottle:
    """Test request throttle."""

    @pytest.mark.asyncio
    async def test_basic_throttle(self):
        """Test basic throttling."""
        throttle = RequestThrottle(max_concurrent=2)
        results = []

        async def task(n: int):
            async with await throttle.acquire():
                results.append(f"start_{n}")
                await asyncio.sleep(0.1)
                results.append(f"end_{n}")

        # Run 4 tasks (2 concurrent)
        await asyncio.gather(*[task(i) for i in range(4)])

        # Check that only 2 ran concurrently
        assert len(results) == 8
        assert results[0] == "start_0"
        assert results[1] == "start_1"

    @pytest.mark.asyncio
    async def test_queue_full(self):
        """Test queue full error."""
        throttle = RequestThrottle(max_concurrent=1, queue_size=2)

        async def long_task():
            async with await throttle.acquire():
                await asyncio.sleep(1.0)

        # Start one task (occupies slot)
        task1 = asyncio.create_task(long_task())
        await asyncio.sleep(0.1)  # Let it start

        # Queue 2 more (fills queue)
        task2 = asyncio.create_task(long_task())
        task3 = asyncio.create_task(long_task())
        await asyncio.sleep(0.1)

        # 4th task should fail with queue full
        with pytest.raises(QueueFullError) as exc_info:
            await throttle.acquire()

        assert exc_info.value.queue_size == 2

        # Cleanup
        task1.cancel()
        task2.cancel()
        task3.cancel()
        try:
            await asyncio.gather(task1, task2, task3)
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_min_delay(self):
        """Test minimum delay between requests."""
        throttle = RequestThrottle(max_concurrent=10, min_delay=0.1)

        start = time.time()
        async with await throttle.acquire():
            pass
        async with await throttle.acquire():
            pass
        duration = time.time() - start

        # Should take at least 0.1s due to min_delay
        assert duration >= 0.1

    @pytest.mark.asyncio
    async def test_priority(self):
        """Test priority-based queuing."""
        throttle = RequestThrottle(max_concurrent=1, queue_size=10)
        results = []

        async def task(priority: Priority, name: str):
            async with await throttle.acquire(priority=priority):
                results.append(name)
                await asyncio.sleep(0.05)

        # Start a long-running task
        blocker = asyncio.create_task(task(Priority.NORMAL, "blocker"))
        await asyncio.sleep(0.02)  # Let it start

        # Queue tasks with different priorities
        tasks = [
            asyncio.create_task(task(Priority.LOW, "low")),
            asyncio.create_task(task(Priority.HIGH, "high")),
            asyncio.create_task(task(Priority.NORMAL, "normal")),
            asyncio.create_task(task(Priority.CRITICAL, "critical")),
        ]

        await asyncio.gather(blocker, *tasks)

        # High priority tasks should run first
        assert results[0] == "blocker"
        assert results[1] == "critical"
        assert results[2] == "high"

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Test statistics tracking."""
        throttle = RequestThrottle(max_concurrent=2)

        async def task(should_fail: bool = False):
            async with await throttle.acquire():
                await asyncio.sleep(0.05)
                if should_fail:
                    raise ValueError("Task failed")

        # Run some tasks
        await asyncio.gather(
            task(),
            task(),
            task(),
        )

        # Run a failing task
        with pytest.raises(ValueError):
            await task(should_fail=True)

        stats = throttle.get_stats()
        assert stats.total_requests == 4
        assert stats.completed_requests == 3
        assert stats.failed_requests == 1

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Test request timeout."""
        throttle = RequestThrottle(max_concurrent=1, timeout=0.1)

        async def blocker():
            async with await throttle.acquire():
                await asyncio.sleep(1.0)

        # Start blocking task
        task1 = asyncio.create_task(blocker())
        await asyncio.sleep(0.05)

        # Second task should timeout
        with pytest.raises(asyncio.TimeoutError):
            await throttle.acquire()

        # Cleanup
        task1.cancel()
        try:
            await task1
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_adaptive_throttling(self):
        """Test adaptive throttling."""
        throttle = RequestThrottle(
            max_concurrent=1,
            queue_size=3,
            adaptive=True,
        )

        async def task():
            async with await throttle.acquire():
                await asyncio.sleep(0.05)

        # Run tasks that will fill queue (trigger adaptive delay)
        start = time.time()
        await asyncio.gather(*[task() for i in range(4)])
        duration = time.time() - start

        # Should complete successfully
        assert duration >= 0.2  # 4 tasks * 0.05s minimum


class TestThrottleContext:
    """Test throttle context manager."""

    @pytest.mark.asyncio
    async def test_context_success(self):
        """Test context manager with successful request."""
        throttle = RequestThrottle(max_concurrent=1)

        async with await throttle.acquire():
            assert throttle._stats.active_requests == 1

        stats = throttle.get_stats()
        assert stats.active_requests == 0
        assert stats.completed_requests == 1
        assert stats.failed_requests == 0

    @pytest.mark.asyncio
    async def test_context_failure(self):
        """Test context manager with failed request."""
        throttle = RequestThrottle(max_concurrent=1)

        with pytest.raises(ValueError):
            async with await throttle.acquire():
                raise ValueError("Test error")

        stats = throttle.get_stats()
        assert stats.active_requests == 0
        assert stats.completed_requests == 0
        assert stats.failed_requests == 1


class TestThrottleRegistry:
    """Test throttle registry."""

    def test_get_throttle(self):
        """Test getting throttle from registry."""
        clear_throttles()

        throttle1 = get_throttle("api", max_concurrent=5)
        throttle2 = get_throttle("api")

        assert throttle1 is throttle2

    def test_multiple_throttles(self):
        """Test multiple throttles."""
        clear_throttles()

        throttle1 = get_throttle("api1", max_concurrent=5)
        throttle2 = get_throttle("api2", max_concurrent=10)

        assert throttle1 is not throttle2
        assert throttle1.config.max_concurrent == 5
        assert throttle2.config.max_concurrent == 10

    def test_clear_registry(self):
        """Test clearing registry."""
        get_throttle("test")
        clear_throttles()

        # Should create new throttle
        throttle1 = get_throttle("test", max_concurrent=3)
        throttle2 = get_throttle("test")

        assert throttle1 is throttle2
        assert throttle1.config.max_concurrent == 3


class TestThrottleDecorator:
    """Test throttle decorator."""

    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator usage."""
        results = []

        @throttle_requests(max_concurrent=2)
        async def task(n: int):
            results.append(f"start_{n}")
            await asyncio.sleep(0.05)
            results.append(f"end_{n}")

        # Run 4 tasks
        await asyncio.gather(*[task(i) for i in range(4)])

        # Should have throttled to 2 concurrent
        assert len(results) == 8

    @pytest.mark.asyncio
    async def test_decorator_priority(self):
        """Test decorator with priority."""
        results = []

        @throttle_requests(max_concurrent=1, queue_size=10)
        async def task(name: str):
            results.append(name)
            await asyncio.sleep(0.05)

        # Start blocker
        blocker = asyncio.create_task(task("blocker"))
        await asyncio.sleep(0.02)

        # Queue with different priorities
        tasks = [
            asyncio.create_task(task("low", _priority=Priority.LOW)),
            asyncio.create_task(task("high", _priority=Priority.HIGH)),
            asyncio.create_task(task("normal", _priority=Priority.NORMAL)),
        ]

        await asyncio.gather(blocker, *tasks)

        # High priority should run first
        assert results[0] == "blocker"
        assert results[1] == "high"

    @pytest.mark.asyncio
    async def test_decorator_with_return_value(self):
        """Test decorator preserves return values."""

        @throttle_requests(max_concurrent=2)
        async def task(n: int) -> int:
            await asyncio.sleep(0.01)
            return n * 2

        results = await asyncio.gather(*[task(i) for i in range(5)])
        assert results == [0, 2, 4, 6, 8]


class TestThrottleRepr:
    """Test throttle representation."""

    def test_repr(self):
        """Test string representation."""
        throttle = RequestThrottle(max_concurrent=10, queue_size=50)
        repr_str = repr(throttle)

        assert "RequestThrottle" in repr_str
        assert "max_concurrent=10" in repr_str
        assert "queue_size=50" in repr_str
        assert "active=0" in repr_str
        assert "queued=0" in repr_str


class TestStatsReset:
    """Test statistics reset."""

    @pytest.mark.asyncio
    async def test_reset_stats(self):
        """Test resetting statistics."""
        throttle = RequestThrottle(max_concurrent=2)

        async def task():
            async with await throttle.acquire():
                await asyncio.sleep(0.01)

        # Generate some stats
        await asyncio.gather(*[task() for _ in range(5)])

        stats_before = throttle.get_stats()
        assert stats_before.total_requests == 5

        # Reset
        throttle.reset_stats()

        stats_after = throttle.get_stats()
        assert stats_after.total_requests == 0
        assert stats_after.completed_requests == 0

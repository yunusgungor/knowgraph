"""Request throttling with adaptive backpressure and queuing.

This module provides request throttling mechanisms that slow down requests
rather than rejecting them, using techniques like:
- Semaphore-based concurrency limiting
- Queue-based request buffering
- Adaptive delays based on system load
- Priority-based processing

Example:
-------
    # Create throttle with max 10 concurrent requests
    throttle = RequestThrottle(max_concurrent=10, queue_size=100)

    # Use as decorator
    @throttle_requests(max_concurrent=5)
    async def api_call(data: str):
        pass

    # Or use directly
    async with throttle.acquire():
        # Make request
        pass

"""

import asyncio
import heapq
import time
from asyncio import Semaphore
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

T = TypeVar("T")


class Priority(int, Enum):
    """Request priority levels."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class ThrottleError(Exception):
    """Raised when throttling fails."""



class QueueFullError(ThrottleError):
    """Raised when request queue is full."""

    def __init__(self, queue_size: int, wait_time: float) -> None:
        """Initialize queue full error.

        Args:
        ----
            queue_size: Maximum queue size
            wait_time: Estimated wait time in seconds
        """
        self.queue_size = queue_size
        self.wait_time = wait_time
        super().__init__(
            f"Request queue is full ({queue_size} items). "
            f"Estimated wait time: {wait_time:.1f}s"
        )


@dataclass
class ThrottleConfig:
    """Configuration for request throttle."""

    max_concurrent: int = 10  # Maximum concurrent requests
    queue_size: int = 100  # Maximum queued requests
    min_delay: float = 0.0  # Minimum delay between requests (seconds)
    adaptive: bool = True  # Enable adaptive throttling based on load
    timeout: float | None = None  # Request timeout (seconds)


@dataclass
class ThrottleStats:
    """Statistics for request throttle."""

    active_requests: int = 0
    queued_requests: int = 0
    total_requests: int = 0
    completed_requests: int = 0
    failed_requests: int = 0
    timed_out_requests: int = 0
    total_wait_time: float = 0.0
    max_wait_time: float = 0.0
    avg_wait_time: float = 0.0

    def update_wait_time(self, wait_time: float) -> None:
        """Update wait time statistics.

        Args:
        ----
            wait_time: Time spent waiting in queue
        """
        self.total_wait_time += wait_time
        self.max_wait_time = max(self.max_wait_time, wait_time)
        if self.completed_requests > 0:
            self.avg_wait_time = self.total_wait_time / self.completed_requests


@dataclass(order=True)
class PrioritizedRequest:
    """Request with priority for queue ordering."""

    priority: int = field(compare=True)
    timestamp: float = field(compare=True)
    request_id: str = field(compare=False)
    future: asyncio.Future = field(compare=False)


class RequestThrottle:
    """Request throttle with adaptive backpressure."""

    def __init__(
        self,
        max_concurrent: int = 10,
        queue_size: int = 100,
        min_delay: float = 0.0,
        adaptive: bool = True,
        timeout: float | None = None,
    ) -> None:
        """Initialize request throttle.

        Args:
        ----
            max_concurrent: Maximum concurrent requests
            queue_size: Maximum queued requests
            min_delay: Minimum delay between requests (seconds)
            adaptive: Enable adaptive throttling
            timeout: Request timeout (seconds)
        """
        self.config = ThrottleConfig(
            max_concurrent=max_concurrent,
            queue_size=queue_size,
            min_delay=min_delay,
            adaptive=adaptive,
            timeout=timeout,
        )
        self._semaphore = Semaphore(max_concurrent)
        self._queue: list[PrioritizedRequest] = []
        self._stats = ThrottleStats()
        self._lock = asyncio.Lock()
        self._last_request_time = 0.0
        self._load_factor = 0.0  # 0.0 to 1.0
        self._max_queue_size = queue_size

    async def acquire(
        self,
        priority: Priority = Priority.NORMAL,
        timeout: float | None = None,
    ) -> "ThrottleContext":
        """Acquire throttle slot.

        Args:
        ----
            priority: Request priority
            timeout: Timeout for acquiring slot (uses config timeout if not specified)

        Returns:
        -------
            Context manager for throttled execution

        Raises:
        ------
            QueueFullError: If queue is full
            asyncio.TimeoutError: If timeout is exceeded
        """
        request_id = f"req_{time.time()}_{id(self)}"
        start_time = time.time()

        async with self._lock:
            self._stats.total_requests += 1

        # Calculate adaptive delay if enabled
        if self.config.adaptive:
            await self._apply_adaptive_delay()

        # Apply minimum delay
        if self.config.min_delay > 0:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.config.min_delay:
                await asyncio.sleep(self.config.min_delay - elapsed)
            self._last_request_time = time.time()

        # Try to acquire semaphore
        acquired = self._semaphore.locked() is False

        if not acquired:
            # Need to queue
            if len(self._queue) >= self._max_queue_size:
                wait_time = self._estimate_wait_time()
                raise QueueFullError(self.config.queue_size, wait_time)

            # Create future for this request
            future: asyncio.Future = asyncio.Future()
            prioritized = PrioritizedRequest(
                priority=-priority.value,  # Negative for max-heap behavior
                timestamp=start_time,
                request_id=request_id,
                future=future,
            )

            async with self._lock:
                self._stats.queued_requests += 1
                heapq.heappush(self._queue, prioritized)

            # Wait for slot
            effective_timeout = timeout or self.config.timeout
            try:
                if effective_timeout:
                    await asyncio.wait_for(future, timeout=effective_timeout)
                else:
                    await future
            except asyncio.TimeoutError:
                async with self._lock:
                    self._stats.timed_out_requests += 1
                raise

        # Acquire semaphore
        await self._semaphore.acquire()

        async with self._lock:
            self._stats.active_requests += 1
            if self._stats.queued_requests > 0:
                self._stats.queued_requests -= 1
            wait_time = time.time() - start_time
            self._stats.update_wait_time(wait_time)

        return ThrottleContext(self, request_id)

    async def _apply_adaptive_delay(self) -> None:
        """Apply adaptive delay based on current load."""
        # Calculate load factor (0.0 to 1.0)
        active = self._stats.active_requests
        queued = self._stats.queued_requests
        total_capacity = self.config.max_concurrent + self.config.queue_size

        self._load_factor = (active + queued) / total_capacity

        # Apply exponential backoff based on load
        if self._load_factor > 0.8:
            delay = 0.1 * (self._load_factor ** 2)
            await asyncio.sleep(delay)

    def _estimate_wait_time(self) -> float:
        """Estimate wait time based on current queue and throughput."""
        if self._stats.completed_requests == 0:
            return float("inf")

        # Average time per request
        avg_time = self._stats.avg_wait_time or 1.0

        # Estimate based on queue size and concurrent capacity
        queued = self._stats.queued_requests
        concurrent = self.config.max_concurrent

        return (queued / concurrent) * avg_time

    async def _release(self, request_id: str, success: bool) -> None:
        """Release throttle slot.

        Args:
        ----
            request_id: ID of the request being released
            success: Whether the request completed successfully
        """
        async with self._lock:
            self._stats.active_requests -= 1
            if success:
                self._stats.completed_requests += 1
            else:
                self._stats.failed_requests += 1

        # Release semaphore
        self._semaphore.release()

        # Process next queued request
        async with self._lock:
            if self._queue:
                next_request = heapq.heappop(self._queue)
                # Only set result if future is not already done
                if not next_request.future.done():
                    next_request.future.set_result(True)

    def get_stats(self) -> ThrottleStats:
        """Get current statistics.

        Returns:
        -------
            Throttle statistics
        """
        return self._stats

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = ThrottleStats()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RequestThrottle("
            f"max_concurrent={self.config.max_concurrent}, "
            f"queue_size={self.config.queue_size}, "
            f"active={self._stats.active_requests}, "
            f"queued={self._stats.queued_requests})"
        )


class ThrottleContext:
    """Context manager for throttled requests."""

    def __init__(self, throttle: RequestThrottle, request_id: str) -> None:
        """Initialize context.

        Args:
        ----
            throttle: The throttle instance
            request_id: ID of this request
        """
        self._throttle = throttle
        self._request_id = request_id
        self._success = False

    async def __aenter__(self) -> "ThrottleContext":
        """Enter context."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context."""
        self._success = exc_type is None
        await self._throttle._release(self._request_id, self._success)


# Global throttle registry
_throttles: dict[str, RequestThrottle] = {}


def get_throttle(
    name: str,
    max_concurrent: int = 10,
    queue_size: int = 100,
) -> RequestThrottle:
    """Get or create a request throttle.

    Args:
    ----
        name: Unique name for the throttle
        max_concurrent: Max concurrent requests (used only for new throttles)
        queue_size: Max queue size (used only for new throttles)

    Returns:
    -------
        RequestThrottle instance
    """
    if name not in _throttles:
        _throttles[name] = RequestThrottle(
            max_concurrent=max_concurrent,
            queue_size=queue_size,
        )
    return _throttles[name]


def clear_throttles() -> None:
    """Clear all throttles from registry."""
    _throttles.clear()


def throttle_requests(
    max_concurrent: int = 10,
    queue_size: int = 100,
    priority: Priority = Priority.NORMAL,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator to add request throttling to async functions.

    Args:
    ----
        max_concurrent: Maximum concurrent executions
        queue_size: Maximum queued requests
        priority: Default priority for requests

    Returns:
    -------
        Decorated function

    Example:
    -------
        @throttle_requests(max_concurrent=5)
        async def api_call(data: str):
            pass
    """
    throttle = RequestThrottle(
        max_concurrent=max_concurrent,
        queue_size=queue_size,
    )

    def decorator(
        func: Callable[..., Awaitable[T]]
    ) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Extract priority from kwargs if provided
            req_priority = kwargs.pop("_priority", priority)

            # Acquire throttle slot
            async with await throttle.acquire(priority=req_priority):
                # Call function
                return await func(*args, **kwargs)

        return wrapper

    return decorator

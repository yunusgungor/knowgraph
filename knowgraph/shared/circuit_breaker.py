"""Circuit breaker pattern implementation.

Prevents cascading failures by detecting when a service is failing
and temporarily blocking requests to give it time to recover.

States:
    - Closed: Normal operation, requests pass through
    - Open: Failures detected, requests fail immediately
    - Half-Open: Testing if service has recovered
"""

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, message: str = "Circuit breaker is open"):
        super().__init__(message)
        self.message = message


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker.

    Attributes
    ----------
        failure_threshold: Number of failures before opening circuit
        success_threshold: Number of successes in half-open to close circuit
        timeout: Seconds to wait before transitioning to half-open
        window_size: Size of sliding window for failure tracking
        expected_exceptions: Exception types that count as failures
    """

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0
    window_size: int = 10
    expected_exceptions: tuple[type[Exception], ...] = (Exception,)


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker.

    Attributes
    ----------
        state: Current circuit state
        failure_count: Recent failure count
        success_count: Recent success count (in half-open)
        last_failure_time: Timestamp of last failure
        total_calls: Total calls attempted
        total_failures: Total failures
        total_successes: Total successes
        total_rejections: Total calls rejected (open state)
    """

    state: CircuitState
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float | None = None
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    total_rejections: int = 0


class CircuitBreaker(Generic[T]):
    """Circuit breaker for protecting external service calls.

    Example:
        >>> breaker = CircuitBreaker(name="api", config=CircuitBreakerConfig())
        >>> result = await breaker.call(make_api_request, arg1, arg2)
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        """Initialize circuit breaker.

        Args:
        ----
            name: Identifier for this circuit breaker
            config: Configuration options
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: float | None = None
        self._recent_results: deque[bool] = deque(maxlen=self.config.window_size)

        # Statistics
        self._total_calls = 0
        self._total_failures = 0
        self._total_successes = 0
        self._total_rejections = 0

        # Thread safety
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state == CircuitState.HALF_OPEN

    def get_stats(self) -> CircuitBreakerStats:
        """Get circuit breaker statistics.

        Returns
        -------
            Current statistics
        """
        return CircuitBreakerStats(
            state=self._state,
            failure_count=self._failure_count,
            success_count=self._success_count,
            last_failure_time=self._last_failure_time,
            total_calls=self._total_calls,
            total_failures=self._total_failures,
            total_successes=self._total_successes,
            total_rejections=self._total_rejections,
        )

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute function with circuit breaker protection.

        Args:
        ----
            func: Async function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
        -------
            Result from func

        Raises:
        ------
            CircuitBreakerError: If circuit is open
            Exception: Any exception from func
        """
        async with self._lock:
            self._total_calls += 1

            # Check if we should transition from open to half-open
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                else:
                    self._total_rejections += 1
                    raise CircuitBreakerError(
                        f"Circuit breaker '{self.name}' is open"
                    )

        # Execute the function
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except self.config.expected_exceptions as e:
            await self._on_failure()
            raise e

    def call_sync(
        self,
        func: Callable[..., T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute synchronous function with circuit breaker protection.

        Args:
        ----
            func: Synchronous function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
        -------
            Result from func

        Raises:
        ------
            CircuitBreakerError: If circuit is open
            Exception: Any exception from func
        """
        self._total_calls += 1

        # Check if we should transition from open to half-open
        if self._state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
            else:
                self._total_rejections += 1
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is open"
                )

        # Execute the function
        try:
            result = func(*args, **kwargs)
            self._on_success_sync()
            return result
        except self.config.expected_exceptions as e:
            self._on_failure_sync()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset.

        Returns
        -------
            True if should transition to half-open
        """
        if self._last_failure_time is None:
            return False

        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.config.timeout

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            self._on_success_sync()

    def _on_success_sync(self) -> None:
        """Handle successful call (synchronous)."""
        self._total_successes += 1
        self._recent_results.append(True)

        if self._state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
                self._success_count = 0

    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self._on_failure_sync()

    def _on_failure_sync(self) -> None:
        """Handle failed call (synchronous)."""
        self._total_failures += 1
        self._recent_results.append(False)
        self._last_failure_time = time.time()
        self._failure_count = sum(1 for r in self._recent_results if not r)

        if self._state == CircuitState.HALF_OPEN:
            # Single failure in half-open reopens circuit
            self._state = CircuitState.OPEN
            self._success_count = 0
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN

    async def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._recent_results.clear()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"CircuitBreaker(name='{self.name}', state={self._state.value}, "
            f"failures={self._failure_count}/{self.config.failure_threshold})"
        )


# Global registry for circuit breakers
_circuit_breakers: dict[str, CircuitBreaker[Any]] = {}


def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreaker[Any]:
    """Get or create a circuit breaker by name.

    Args:
    ----
        name: Circuit breaker identifier
        config: Configuration (only used for new breakers)

    Returns:
    -------
        Circuit breaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]


def clear_circuit_breakers() -> None:
    """Clear all circuit breakers from registry."""
    _circuit_breakers.clear()

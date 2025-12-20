"""Rate limiting for API endpoints and resource access.

This module provides rate limiting capabilities using multiple algorithms:
- Token Bucket: Allows bursts while maintaining average rate
- Fixed Window: Simple counter that resets at fixed intervals
- Sliding Window: More accurate than fixed window, smoother enforcement

Example:
-------
    # Token bucket rate limiter (100 requests/minute)
    limiter = RateLimiter(rate=100, period=60, algorithm="token_bucket")

    # Check if request is allowed
    if await limiter.allow("user_123"):
        # Process request
        pass
    else:
        # Reject request
        raise RateLimitExceeded("Too many requests")

    # Or use as decorator
    @rate_limit(rate=10, period=60)
    async def api_endpoint(user_id: str):
        pass

"""

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

T = TypeVar("T")


class RateLimitAlgorithm(str, Enum):
    """Rate limiting algorithms."""

    TOKEN_BUCKET = "token_bucket"
    FIXED_WINDOW = "fixed_window"
    SLIDING_WINDOW = "sliding_window"


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        identifier: str,
        limit: int,
        period: float,
        retry_after: float,
    ) -> None:
        """Initialize rate limit error.

        Args:
        ----
            identifier: The identifier that exceeded the limit
            limit: The rate limit (requests per period)
            period: The time period in seconds
            retry_after: Seconds until rate limit resets
        """
        self.identifier = identifier
        self.limit = limit
        self.period = period
        self.retry_after = retry_after
        super().__init__(
            f"Rate limit exceeded for '{identifier}': "
            f"{limit} requests per {period}s. "
            f"Retry after {retry_after:.1f}s"
        )


@dataclass
class RateLimitConfig:
    """Configuration for rate limiter."""

    rate: int = 100  # Requests per period
    period: float = 60.0  # Time period in seconds
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    burst_size: int | None = None  # Max burst size (for token bucket)


@dataclass
class TokenBucketState:
    """State for token bucket algorithm."""

    tokens: float  # Current token count
    last_update: float  # Last update timestamp
    capacity: float  # Maximum tokens


@dataclass
class FixedWindowState:
    """State for fixed window algorithm."""

    count: int  # Request count in current window
    window_start: float  # Window start timestamp


@dataclass
class SlidingWindowState:
    """State for sliding window algorithm."""

    timestamps: deque[float] = field(default_factory=deque)  # Request timestamps


@dataclass
class RateLimitStats:
    """Statistics for rate limiter."""

    identifier: str
    total_requests: int = 0
    allowed_requests: int = 0
    rejected_requests: int = 0
    last_request_time: float = 0.0

    @property
    def rejection_rate(self) -> float:
        """Calculate rejection rate."""
        if self.total_requests == 0:
            return 0.0
        return self.rejected_requests / self.total_requests


class RateLimiter:
    """Rate limiter with multiple algorithms."""

    def __init__(
        self,
        rate: int = 100,
        period: float = 60.0,
        algorithm: str = "token_bucket",
        burst_size: int | None = None,
    ) -> None:
        """Initialize rate limiter.

        Args:
        ----
            rate: Maximum requests per period
            period: Time period in seconds
            algorithm: Algorithm to use ("token_bucket", "fixed_window", "sliding_window")
            burst_size: Maximum burst size (for token bucket, defaults to rate)
        """
        self.config = RateLimitConfig(
            rate=rate,
            period=period,
            algorithm=RateLimitAlgorithm(algorithm),
            burst_size=burst_size or rate,
        )
        self._lock = asyncio.Lock()
        self._states: dict[str, Any] = {}
        self._stats: dict[str, RateLimitStats] = defaultdict(lambda: RateLimitStats(identifier=""))

    async def allow(self, identifier: str) -> bool:
        """Check if request is allowed for identifier.

        Args:
        ----
            identifier: Unique identifier (user ID, IP, API key, etc.)

        Returns:
        -------
            True if request is allowed, False otherwise

        Raises:
        ------
            RateLimitExceeded: If rate limit is exceeded
        """
        async with self._lock:
            # Update stats
            if identifier not in self._stats:
                self._stats[identifier] = RateLimitStats(identifier=identifier)
            stats = self._stats[identifier]
            stats.total_requests += 1
            stats.last_request_time = time.time()

            # Check rate limit based on algorithm
            if self.config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
                allowed = self._check_token_bucket(identifier)
            elif self.config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
                allowed = self._check_fixed_window(identifier)
            else:  # SLIDING_WINDOW
                allowed = self._check_sliding_window(identifier)

            # Update stats
            if allowed:
                stats.allowed_requests += 1
            else:
                stats.rejected_requests += 1
                retry_after = self._calculate_retry_after(identifier)
                raise RateLimitExceeded(
                    identifier=identifier,
                    limit=self.config.rate,
                    period=self.config.period,
                    retry_after=retry_after,
                )

            return allowed

    def _check_token_bucket(self, identifier: str) -> bool:
        """Check token bucket algorithm."""
        now = time.time()

        # Initialize state if needed
        if identifier not in self._states:
            self._states[identifier] = TokenBucketState(
                tokens=float(self.config.burst_size or self.config.rate),
                last_update=now,
                capacity=float(self.config.burst_size or self.config.rate),
            )

        state: TokenBucketState = self._states[identifier]

        # Calculate tokens to add based on time elapsed
        elapsed = now - state.last_update
        tokens_to_add = elapsed * (self.config.rate / self.config.period)
        state.tokens = min(state.capacity, state.tokens + tokens_to_add)
        state.last_update = now

        # Check if we have tokens available
        if state.tokens >= 1.0:
            state.tokens -= 1.0
            return True

        return False

    def _check_fixed_window(self, identifier: str) -> bool:
        """Check fixed window algorithm."""
        now = time.time()

        # Initialize state if needed
        if identifier not in self._states:
            self._states[identifier] = FixedWindowState(
                count=0,
                window_start=now,
            )

        state: FixedWindowState = self._states[identifier]

        # Check if we're in a new window
        if now - state.window_start >= self.config.period:
            state.count = 0
            state.window_start = now

        # Check if we're under the limit
        if state.count < self.config.rate:
            state.count += 1
            return True

        return False

    def _check_sliding_window(self, identifier: str) -> bool:
        """Check sliding window algorithm."""
        now = time.time()

        # Initialize state if needed
        if identifier not in self._states:
            self._states[identifier] = SlidingWindowState()

        state: SlidingWindowState = self._states[identifier]

        # Remove old timestamps outside the window
        cutoff = now - self.config.period
        while state.timestamps and state.timestamps[0] < cutoff:
            state.timestamps.popleft()

        # Check if we're under the limit
        if len(state.timestamps) < self.config.rate:
            state.timestamps.append(now)
            return True

        return False

    def _calculate_retry_after(self, identifier: str) -> float:
        """Calculate seconds until rate limit resets."""
        if identifier not in self._states:
            return 0.0

        now = time.time()

        if self.config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            tb_state: TokenBucketState = self._states[identifier]
            # Time to accumulate 1 token
            tokens_needed = 1.0 - tb_state.tokens
            return max(0.0, tokens_needed * (self.config.period / self.config.rate))

        elif self.config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
            fw_state: FixedWindowState = self._states[identifier]
            # Time until window resets
            return max(0.0, self.config.period - (now - fw_state.window_start))

        else:  # SLIDING_WINDOW
            sw_state: SlidingWindowState = self._states[identifier]
            if not sw_state.timestamps:
                return 0.0
            # Time until oldest timestamp expires
            oldest = sw_state.timestamps[0]
            return max(0.0, self.config.period - (now - oldest))

    def get_stats(self, identifier: str) -> RateLimitStats:
        """Get statistics for an identifier.

        Args:
        ----
            identifier: The identifier to get stats for

        Returns:
        -------
            Rate limit statistics
        """
        return self._stats.get(
            identifier,
            RateLimitStats(identifier=identifier),
        )

    def reset(self, identifier: str) -> None:
        """Reset rate limit for an identifier.

        Args:
        ----
            identifier: The identifier to reset
        """
        if identifier in self._states:
            del self._states[identifier]
        if identifier in self._stats:
            del self._stats[identifier]

    def reset_all(self) -> None:
        """Reset all rate limits."""
        self._states.clear()
        self._stats.clear()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"RateLimiter("
            f"rate={self.config.rate}, "
            f"period={self.config.period}, "
            f"algorithm={self.config.algorithm.value})"
        )


# Global rate limiter registry
_rate_limiters: dict[str, RateLimiter] = {}


def get_rate_limiter(
    name: str,
    rate: int = 100,
    period: float = 60.0,
    algorithm: str = "token_bucket",
) -> RateLimiter:
    """Get or create a rate limiter.

    Args:
    ----
        name: Unique name for the rate limiter
        rate: Maximum requests per period (used only for new limiters)
        period: Time period in seconds (used only for new limiters)
        algorithm: Algorithm to use (used only for new limiters)

    Returns:
    -------
        RateLimiter instance
    """
    if name not in _rate_limiters:
        _rate_limiters[name] = RateLimiter(
            rate=rate,
            period=period,
            algorithm=algorithm,
        )
    return _rate_limiters[name]


def clear_rate_limiters() -> None:
    """Clear all rate limiters from registry."""
    _rate_limiters.clear()


def rate_limit(
    rate: int = 100,
    period: float = 60.0,
    algorithm: str = "token_bucket",
    identifier_func: Callable[..., str] | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator to add rate limiting to async functions.

    Args:
    ----
        rate: Maximum requests per period
        period: Time period in seconds
        algorithm: Algorithm to use
        identifier_func: Function to extract identifier from args/kwargs
                        (defaults to using first argument)

    Returns:
    -------
        Decorated function

    Example:
    -------
        @rate_limit(rate=10, period=60)
        async def api_call(user_id: str):
            pass
    """
    limiter = RateLimiter(rate=rate, period=period, algorithm=algorithm)

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Extract identifier
            if identifier_func:
                identifier = identifier_func(*args, **kwargs)
            elif args:
                identifier = str(args[0])
            else:
                identifier = "default"

            # Check rate limit
            await limiter.allow(identifier)

            # Call function
            return await func(*args, **kwargs)

        return wrapper

    return decorator

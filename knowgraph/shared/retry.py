"""Retry logic with exponential backoff and multiple strategies.

This module provides retry mechanisms for handling transient failures:
- Exponential backoff with jitter
- Linear backoff
- Constant delay
- Configurable retry conditions
- Max attempts and timeout limits

Example:
-------
    # Retry with exponential backoff
    @retry(max_attempts=3, backoff="exponential")
    async def api_call():
        response = await client.get("/data")
        return response

    # Retry specific exceptions only
    @retry(max_attempts=5, retry_on=[ConnectionError, TimeoutError])
    async def unstable_operation():
        pass

    # Use retry context directly
    async with RetryContext(max_attempts=3) as retry:
        result = await retry.execute(some_async_function, arg1, arg2)

"""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

T = TypeVar("T")


class BackoffStrategy(str, Enum):
    """Backoff strategies for retry delays."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


class RetryError(Exception):
    """Raised when all retry attempts are exhausted."""

    def __init__(
        self,
        attempts: int,
        last_exception: Exception,
        total_duration: float,
    ) -> None:
        """Initialize retry error.

        Args:
        ----
            attempts: Number of attempts made
            last_exception: The last exception encountered
            total_duration: Total time spent retrying
        """
        self.attempts = attempts
        self.last_exception = last_exception
        self.total_duration = total_duration
        super().__init__(
            f"Retry failed after {attempts} attempts "
            f"({total_duration:.2f}s): {last_exception}"
        )


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    backoff_strategy: BackoffStrategy = BackoffStrategy.EXPONENTIAL
    initial_delay: float = 1.0  # Initial delay in seconds
    max_delay: float = 60.0  # Maximum delay between retries
    multiplier: float = 2.0  # Backoff multiplier (for exponential/linear)
    jitter: bool = True  # Add random jitter to delays
    timeout: float | None = None  # Total timeout for all retries
    retry_on: list[type[Exception]] | None = None  # Exceptions to retry
    retry_on_result: Callable[[Any], bool] | None = None  # Retry based on result


@dataclass
class RetryStats:
    """Statistics for retry attempts."""

    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_retries: int = 0
    total_delay: float = 0.0
    exceptions: list[tuple[type[Exception], str]] = field(default_factory=list)

    def add_exception(self, exc: Exception) -> None:
        """Record an exception.

        Args:
        ----
            exc: The exception that occurred
        """
        self.exceptions.append((type(exc), str(exc)))


class RetryContext:
    """Context manager for retry logic."""

    def __init__(
        self,
        max_attempts: int = 3,
        backoff_strategy: str = "exponential",
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        jitter: bool = True,
        timeout: float | None = None,
        retry_on: list[type[Exception]] | None = None,
        retry_on_result: Callable[[Any], bool] | None = None,
    ) -> None:
        """Initialize retry context.

        Args:
        ----
            max_attempts: Maximum number of attempts
            backoff_strategy: Backoff strategy ("exponential", "linear", "constant")
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay between retries
            multiplier: Backoff multiplier
            jitter: Add random jitter to delays
            timeout: Total timeout for all retries
            retry_on: List of exception types to retry on
            retry_on_result: Function to determine if result should trigger retry
        """
        self.config = RetryConfig(
            max_attempts=max_attempts,
            backoff_strategy=BackoffStrategy(backoff_strategy),
            initial_delay=initial_delay,
            max_delay=max_delay,
            multiplier=multiplier,
            jitter=jitter,
            timeout=timeout,
            retry_on=retry_on,
            retry_on_result=retry_on_result,
        )
        self.stats = RetryStats()
        self._start_time = 0.0

    async def __aenter__(self) -> "RetryContext":
        """Enter context."""
        self._start_time = time.time()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context."""

    def _should_retry(
        self, exc: Exception | None, result: Any, attempt: int
    ) -> tuple[bool, str]:
        """Determine if we should retry.

        Args:
        ----
            exc: Exception that occurred (if any)
            result: Result from function (if no exception)
            attempt: Current attempt number (0-indexed)

        Returns:
        -------
            Tuple of (should_retry: bool, reason: str)
            Reason is one of: "max_attempts", "timeout", "non_retryable", "ok"
        """
        # Check if we have attempts left (attempt is 0-indexed)
        if attempt >= self.config.max_attempts - 1:
            return False, "max_attempts"

        # Check timeout
        if self.config.timeout:
            elapsed = time.time() - self._start_time
            if elapsed >= self.config.timeout:
                return False, "timeout"

        # If there's an exception, check if it's retryable
        if exc is not None:
            if self.config.retry_on:
                if not any(isinstance(exc, exc_type) for exc_type in self.config.retry_on):
                    return False, "non_retryable"
            return True, "ok"  # Retry all exceptions by default

        # Check result-based retry
        if self.config.retry_on_result:
            if self.config.retry_on_result(result):
                return True, "ok"
            return False, "max_attempts"

        return False, "ok"

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt.

        Args:
        ----
            attempt: Current attempt number (0-indexed)

        Returns:
        -------
            Delay in seconds
        """
        if self.config.backoff_strategy == BackoffStrategy.CONSTANT:
            delay = self.config.initial_delay
        elif self.config.backoff_strategy == BackoffStrategy.LINEAR:
            delay = self.config.initial_delay + (attempt * self.config.multiplier)
        else:  # EXPONENTIAL
            delay = self.config.initial_delay * (self.config.multiplier ** attempt)

        # Apply max delay
        delay = min(delay, self.config.max_delay)

        # Add jitter if enabled
        if self.config.jitter:
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay)  # Ensure non-negative

        return delay

    async def execute(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute function with retry logic.

        Args:
        ----
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
        -------
            Result from func

        Raises:
        ------
            RetryError: If all retry attempts are exhausted
        """
        last_exception: Exception | None = None
        result: Any = None

        for attempt in range(self.config.max_attempts):
            self.stats.total_attempts += 1

            try:
                result = await func(*args, **kwargs)

                # Check if result should trigger retry
                if self.config.retry_on_result and self.config.retry_on_result(result):
                    should_retry, reason = self._should_retry(None, result, attempt)
                    if should_retry:
                        delay = self._calculate_delay(attempt)
                        self.stats.total_delay += delay
                        self.stats.total_retries += 1
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Can't retry anymore, wrap in RetryError
                        self.stats.failed_attempts += 1
                        duration = time.time() - self._start_time
                        raise RetryError(
                            attempts=self.stats.total_attempts,
                            last_exception=None,
                            total_duration=duration,
                        )

                # Success
                self.stats.successful_attempts += 1
                return result

            except Exception as exc:
                last_exception = exc
                self.stats.add_exception(exc)

                # Check if we should retry this exception
                should_retry, reason = self._should_retry(exc, None, attempt)
                if not should_retry:
                    # Non-retryable exception - raise immediately without wrapping
                    if reason == "non_retryable":
                        raise
                    # Max attempts or timeout - wrap in RetryError
                    self.stats.failed_attempts += 1
                    duration = time.time() - self._start_time
                    raise RetryError(
                        attempts=self.stats.total_attempts,
                        last_exception=exc,
                        total_duration=duration,
                    ) from exc

                # Retry with delay
                delay = self._calculate_delay(attempt)
                self.stats.total_delay += delay
                self.stats.total_retries += 1
                await asyncio.sleep(delay)

        # All attempts exhausted (should not reach here normally)
        self.stats.failed_attempts += 1
        duration = time.time() - self._start_time

        if last_exception:
            raise RetryError(
                attempts=self.stats.total_attempts,
                last_exception=last_exception,
                total_duration=duration,
            )

        # Result-based retry exhausted (should not reach here normally)
        return result


def retry(
    max_attempts: int = 3,
    backoff: str = "exponential",
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    multiplier: float = 2.0,
    jitter: bool = True,
    timeout: float | None = None,
    retry_on: list[type[Exception]] | None = None,
    retry_on_result: Callable[[Any], bool] | None = None,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator to add retry logic to async functions.

    Args:
    ----
        max_attempts: Maximum number of attempts
        backoff: Backoff strategy ("exponential", "linear", "constant")
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay between retries
        multiplier: Backoff multiplier
        jitter: Add random jitter to delays
        timeout: Total timeout for all retries
        retry_on: List of exception types to retry on
        retry_on_result: Function to determine if result should trigger retry

    Returns:
    -------
        Decorated function

    Example:
    -------
        @retry(max_attempts=5, backoff="exponential")
        async def unstable_api_call():
            return await client.get("/data")
    """

    def decorator(
        func: Callable[..., Awaitable[T]]
    ) -> Callable[..., Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            async with RetryContext(
                max_attempts=max_attempts,
                backoff_strategy=backoff,
                initial_delay=initial_delay,
                max_delay=max_delay,
                multiplier=multiplier,
                jitter=jitter,
                timeout=timeout,
                retry_on=retry_on,
                retry_on_result=retry_on_result,
            ) as retry_ctx:
                return await retry_ctx.execute(func, *args, **kwargs)

        return wrapper

    return decorator

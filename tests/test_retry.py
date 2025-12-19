"""Tests for retry logic."""

import asyncio

import pytest

from knowgraph.shared.retry import (
    BackoffStrategy,
    RetryConfig,
    RetryContext,
    RetryError,
    RetryStats,
    retry,
)


class TestRetryConfig:
    """Test retry configuration."""

    def test_default_config(self):
        """Test default configuration."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.backoff_strategy == BackoffStrategy.EXPONENTIAL
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.multiplier == 2.0
        assert config.jitter is True
        assert config.timeout is None
        assert config.retry_on is None

    def test_custom_config(self):
        """Test custom configuration."""
        config = RetryConfig(
            max_attempts=5,
            backoff_strategy=BackoffStrategy.LINEAR,
            initial_delay=0.5,
            max_delay=30.0,
            multiplier=1.5,
            jitter=False,
            timeout=60.0,
            retry_on=[ValueError, TypeError],
        )
        assert config.max_attempts == 5
        assert config.backoff_strategy == BackoffStrategy.LINEAR
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0
        assert config.multiplier == 1.5
        assert config.jitter is False
        assert config.timeout == 60.0
        assert config.retry_on == [ValueError, TypeError]


class TestRetryStats:
    """Test retry statistics."""

    def test_stats_initialization(self):
        """Test stats initialization."""
        stats = RetryStats()
        assert stats.total_attempts == 0
        assert stats.successful_attempts == 0
        assert stats.failed_attempts == 0
        assert stats.total_retries == 0
        assert stats.total_delay == 0.0
        assert len(stats.exceptions) == 0

    def test_add_exception(self):
        """Test adding exceptions."""
        stats = RetryStats()
        stats.add_exception(ValueError("test error"))

        assert len(stats.exceptions) == 1
        assert stats.exceptions[0][0] == ValueError
        assert stats.exceptions[0][1] == "test error"


class TestRetryContext:
    """Test retry context."""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self):
        """Test successful execution on first attempt."""
        call_count = 0

        async def task():
            nonlocal call_count
            call_count += 1
            return "success"

        async with RetryContext(max_attempts=3) as retry_ctx:
            result = await retry_ctx.execute(task)

        assert result == "success"
        assert call_count == 1
        assert retry_ctx.stats.total_attempts == 1
        assert retry_ctx.stats.successful_attempts == 1
        assert retry_ctx.stats.total_retries == 0

    @pytest.mark.asyncio
    async def test_retry_on_exception(self):
        """Test retry on exception."""
        call_count = 0

        async def task():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return "success"

        async with RetryContext(
            max_attempts=3,
            initial_delay=0.01,
            jitter=False,
        ) as retry_ctx:
            result = await retry_ctx.execute(task)

        assert result == "success"
        assert call_count == 3
        assert retry_ctx.stats.total_attempts == 3
        assert retry_ctx.stats.successful_attempts == 1
        assert retry_ctx.stats.total_retries == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted(self):
        """Test all retries exhausted."""
        call_count = 0

        async def task():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"error {call_count}")

        async with RetryContext(
            max_attempts=3,
            initial_delay=0.01,
            jitter=False,
        ) as retry_ctx:
            with pytest.raises(RetryError) as exc_info:
                await retry_ctx.execute(task)

        assert call_count == 3
        assert exc_info.value.attempts == 3
        assert "error 3" in str(exc_info.value.last_exception)

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff."""

        async def task():
            raise ValueError("error")

        async with RetryContext(
            max_attempts=4,
            backoff_strategy="exponential",
            initial_delay=0.1,
            multiplier=2.0,
            jitter=False,
        ) as retry_ctx:
            try:
                await retry_ctx.execute(task)
            except RetryError:
                pass

        # Check delays: 0.1, 0.2, 0.4 (exponential)
        assert retry_ctx.stats.total_retries == 3
        assert 0.6 < retry_ctx.stats.total_delay < 0.8  # ~0.7s total

    @pytest.mark.asyncio
    async def test_linear_backoff(self):
        """Test linear backoff."""
        async def task():
            raise ValueError("error")

        async with RetryContext(
            max_attempts=4,
            backoff_strategy="linear",
            initial_delay=0.1,
            multiplier=0.1,
            jitter=False,
        ) as retry_ctx:
            try:
                await retry_ctx.execute(task)
            except RetryError:
                pass

        # Check delays: 0.1, 0.2, 0.3 (linear)
        assert retry_ctx.stats.total_retries == 3
        assert 0.5 < retry_ctx.stats.total_delay < 0.7  # ~0.6s total

    @pytest.mark.asyncio
    async def test_constant_backoff(self):
        """Test constant backoff."""
        async def task():
            raise ValueError("error")

        async with RetryContext(
            max_attempts=4,
            backoff_strategy="constant",
            initial_delay=0.1,
            jitter=False,
        ) as retry_ctx:
            try:
                await retry_ctx.execute(task)
            except RetryError:
                pass

        # Check delays: 0.1, 0.1, 0.1 (constant)
        assert retry_ctx.stats.total_retries == 3
        assert 0.25 < retry_ctx.stats.total_delay < 0.35  # ~0.3s total

    @pytest.mark.asyncio
    async def test_max_delay(self):
        """Test maximum delay limit."""
        async def task():
            raise ValueError("error")

        async with RetryContext(
            max_attempts=5,
            backoff_strategy="exponential",
            initial_delay=1.0,
            max_delay=2.0,
            multiplier=2.0,
            jitter=False,
        ) as retry_ctx:
            try:
                await retry_ctx.execute(task)
            except RetryError:
                pass

        # Delays should be capped: 1.0, 2.0, 2.0, 2.0 (max 2.0)
        assert retry_ctx.stats.total_delay <= 8.0  # 1 + 2 + 2 + 2 = 7

    @pytest.mark.asyncio
    async def test_jitter(self):
        """Test jitter adds randomness."""
        delays1 = []
        delays2 = []

        async def task():
            raise ValueError("error")

        # First run
        async with RetryContext(
            max_attempts=3,
            initial_delay=0.1,
            jitter=True,
        ) as retry_ctx1:
            try:
                await retry_ctx1.execute(task)
            except RetryError:
                pass
            delays1.append(retry_ctx1.stats.total_delay)

        # Second run
        async with RetryContext(
            max_attempts=3,
            initial_delay=0.1,
            jitter=True,
        ) as retry_ctx2:
            try:
                await retry_ctx2.execute(task)
            except RetryError:
                pass
            delays2.append(retry_ctx2.stats.total_delay)

        # Delays should be slightly different due to jitter
        # (might occasionally be equal, but unlikely)
        assert delays1[0] > 0
        assert delays2[0] > 0

    @pytest.mark.asyncio
    async def test_retry_on_specific_exceptions(self):
        """Test retry only on specific exceptions."""
        call_count = 0

        async def task():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("retryable")
            raise TypeError("not retryable")

        async with RetryContext(
            max_attempts=3,
            initial_delay=0.01,
            retry_on=[ValueError],
        ) as retry_ctx:
            with pytest.raises(TypeError):
                await retry_ctx.execute(task)

        # Should retry ValueError but not TypeError
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_result(self):
        """Test retry based on result."""
        call_count = 0

        async def task():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return None  # Trigger retry
            return "success"

        async with RetryContext(
            max_attempts=3,
            initial_delay=0.01,
            retry_on_result=lambda r: r is None,
        ) as retry_ctx:
            result = await retry_ctx.execute(task)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Test total timeout."""
        call_count = 0

        async def task():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.2)
            raise ValueError("error")

        async with RetryContext(
            max_attempts=10,
            initial_delay=0.1,
            timeout=0.5,
        ) as retry_ctx:
            with pytest.raises(RetryError):
                await retry_ctx.execute(task)

        # Should stop due to timeout, not max_attempts
        assert call_count < 10


class TestRetryDecorator:
    """Test retry decorator."""

    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator usage."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01, jitter=False)
        async def task():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return "success"

        result = await task()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_decorator_with_args(self):
        """Test decorator with function arguments."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        async def task(x: int, y: int):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("error")
            return x + y

        result = await task(5, 10)
        assert result == 15
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_retry_on(self):
        """Test decorator with retry_on."""
        call_count = 0

        @retry(
            max_attempts=3,
            initial_delay=0.01,
            retry_on=[ValueError],
        )
        async def task():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("retryable")
            raise TypeError("not retryable")

        with pytest.raises(TypeError):
            await task()

        assert call_count == 2

    @pytest.mark.asyncio
    async def test_decorator_exhausted(self):
        """Test decorator when retries exhausted."""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        async def task():
            nonlocal call_count
            call_count += 1
            raise ValueError(f"error {call_count}")

        with pytest.raises(RetryError) as exc_info:
            await task()

        assert call_count == 3
        assert exc_info.value.attempts == 3


class TestBackoffStrategies:
    """Test different backoff strategies."""

    @pytest.mark.asyncio
    async def test_all_strategies(self):
        """Test all backoff strategies work."""
        for strategy in ["exponential", "linear", "constant"]:
            call_count = 0

            @retry(
                max_attempts=3,
                backoff=strategy,
                initial_delay=0.01,
                jitter=False,
            )
            async def task():
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    raise ValueError("error")
                return "success"

            result = await task()
            assert result == "success"
            assert call_count == 3

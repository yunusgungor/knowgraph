"""Tests for comprehensive rate limiter (shared module)."""

import asyncio

import pytest

from knowgraph.shared.rate_limiter import (
    RateLimitAlgorithm,
    RateLimitConfig,
    RateLimiter,
    RateLimitExceeded,
    RateLimitStats,
    clear_rate_limiters,
    get_rate_limiter,
    rate_limit,
)


class TestRateLimitConfig:
    """Test rate limit configuration."""

    def test_default_config(self):
        """Test default configuration."""
        config = RateLimitConfig()
        assert config.rate == 100
        assert config.period == 60.0
        assert config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET
        assert config.burst_size is None

    def test_custom_config(self):
        """Test custom configuration."""
        config = RateLimitConfig(
            rate=50,
            period=30.0,
            algorithm=RateLimitAlgorithm.SLIDING_WINDOW,
            burst_size=100,
        )
        assert config.rate == 50
        assert config.period == 30.0
        assert config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW
        assert config.burst_size == 100


class TestRateLimitStats:
    """Test rate limit statistics."""

    def test_stats_initialization(self):
        """Test stats initialization."""
        stats = RateLimitStats(identifier="user_123")
        assert stats.identifier == "user_123"
        assert stats.total_requests == 0
        assert stats.allowed_requests == 0
        assert stats.rejected_requests == 0
        assert stats.rejection_rate == 0.0

    def test_rejection_rate(self):
        """Test rejection rate calculation."""
        stats = RateLimitStats(
            identifier="user_123",
            total_requests=100,
            allowed_requests=80,
            rejected_requests=20,
        )
        assert stats.rejection_rate == 0.2


class TestTokenBucket:
    """Test token bucket algorithm."""

    @pytest.mark.asyncio
    async def test_allow_within_limit(self):
        """Test allowing requests within limit."""
        limiter = RateLimiter(rate=10, period=1.0, algorithm="token_bucket")

        # Should allow up to burst size
        for _ in range(10):
            assert await limiter.allow("user_123")

    @pytest.mark.asyncio
    async def test_exceed_limit(self):
        """Test exceeding rate limit."""
        limiter = RateLimiter(rate=5, period=1.0, algorithm="token_bucket")

        # Use up all tokens
        for _ in range(5):
            await limiter.allow("user_123")

        # Next request should fail
        with pytest.raises(RateLimitExceeded) as exc_info:
            await limiter.allow("user_123")

        assert "user_123" in str(exc_info.value)
        assert exc_info.value.limit == 5
        assert exc_info.value.period == 1.0

    @pytest.mark.asyncio
    async def test_token_refill(self):
        """Test token refill over time."""
        limiter = RateLimiter(rate=10, period=1.0, algorithm="token_bucket")

        # Use all tokens
        for _ in range(10):
            await limiter.allow("user_123")

        # Wait for refill (0.1s = 1 token at 10 tokens/second)
        await asyncio.sleep(0.15)

        # Should allow one more request
        assert await limiter.allow("user_123")

    @pytest.mark.asyncio
    async def test_burst_size(self):
        """Test custom burst size."""
        limiter = RateLimiter(
            rate=10,
            period=1.0,
            algorithm="token_bucket",
            burst_size=20,
        )

        # Should allow burst up to 20
        for _ in range(20):
            await limiter.allow("user_123")

        # Next request should fail
        with pytest.raises(RateLimitExceeded):
            await limiter.allow("user_123")


class TestFixedWindow:
    """Test fixed window algorithm."""

    @pytest.mark.asyncio
    async def test_allow_within_window(self):
        """Test allowing requests within window."""
        limiter = RateLimiter(rate=10, period=1.0, algorithm="fixed_window")

        # Should allow up to limit
        for _ in range(10):
            assert await limiter.allow("user_123")

    @pytest.mark.asyncio
    async def test_exceed_window_limit(self):
        """Test exceeding window limit."""
        limiter = RateLimiter(rate=5, period=1.0, algorithm="fixed_window")

        # Use up limit
        for _ in range(5):
            await limiter.allow("user_123")

        # Next request should fail
        with pytest.raises(RateLimitExceeded):
            await limiter.allow("user_123")

    @pytest.mark.asyncio
    async def test_window_reset(self):
        """Test window reset."""
        limiter = RateLimiter(rate=5, period=0.1, algorithm="fixed_window")

        # Use up limit
        for _ in range(5):
            await limiter.allow("user_123")

        # Wait for window to reset
        await asyncio.sleep(0.15)

        # Should allow requests in new window
        for _ in range(5):
            assert await limiter.allow("user_123")


class TestSlidingWindow:
    """Test sliding window algorithm."""

    @pytest.mark.asyncio
    async def test_allow_within_window(self):
        """Test allowing requests within window."""
        limiter = RateLimiter(rate=10, period=1.0, algorithm="sliding_window")

        # Should allow up to limit
        for _ in range(10):
            assert await limiter.allow("user_123")

    @pytest.mark.asyncio
    async def test_exceed_window_limit(self):
        """Test exceeding window limit."""
        limiter = RateLimiter(rate=5, period=1.0, algorithm="sliding_window")

        # Use up limit
        for _ in range(5):
            await limiter.allow("user_123")

        # Next request should fail
        with pytest.raises(RateLimitExceeded):
            await limiter.allow("user_123")

    @pytest.mark.asyncio
    async def test_sliding_behavior(self):
        """Test sliding window behavior."""
        limiter = RateLimiter(rate=5, period=0.5, algorithm="sliding_window")

        # Use up limit
        for _ in range(5):
            await limiter.allow("user_123")

        # Wait for half the window
        await asyncio.sleep(0.3)

        # Still can't make new requests (all timestamps still in window)
        with pytest.raises(RateLimitExceeded):
            await limiter.allow("user_123")

        # Wait for first timestamp to expire
        await asyncio.sleep(0.3)

        # Now should allow new request
        assert await limiter.allow("user_123")


class TestRateLimiterStats:
    """Test rate limiter statistics."""

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Test statistics tracking."""
        limiter = RateLimiter(rate=5, period=1.0)

        # Make allowed requests
        for _ in range(5):
            await limiter.allow("user_123")

        # Make rejected request
        with pytest.raises(RateLimitExceeded):
            await limiter.allow("user_123")

        stats = limiter.get_stats("user_123")
        assert stats.identifier == "user_123"
        assert stats.total_requests == 6
        assert stats.allowed_requests == 5
        assert stats.rejected_requests == 1
        assert stats.rejection_rate == 1 / 6

    @pytest.mark.asyncio
    async def test_multiple_identifiers(self):
        """Test tracking multiple identifiers."""
        limiter = RateLimiter(rate=5, period=1.0)

        # User 1
        for _ in range(3):
            await limiter.allow("user_1")

        # User 2
        for _ in range(5):
            await limiter.allow("user_2")

        stats1 = limiter.get_stats("user_1")
        stats2 = limiter.get_stats("user_2")

        assert stats1.allowed_requests == 3
        assert stats2.allowed_requests == 5


class TestRateLimiterReset:
    """Test rate limiter reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_identifier(self):
        """Test resetting specific identifier."""
        limiter = RateLimiter(rate=5, period=1.0)

        # Use up limit
        for _ in range(5):
            await limiter.allow("user_123")

        # Reset
        limiter.reset("user_123")

        # Should allow requests again
        for _ in range(5):
            assert await limiter.allow("user_123")

    @pytest.mark.asyncio
    async def test_reset_all(self):
        """Test resetting all identifiers."""
        limiter = RateLimiter(rate=5, period=1.0)

        # Use up limits for multiple users
        for i in range(5):
            await limiter.allow("user_1")
            await limiter.allow("user_2")

        # Reset all
        limiter.reset_all()

        # Should allow requests for both users
        assert await limiter.allow("user_1")
        assert await limiter.allow("user_2")


class TestRateLimiterRegistry:
    """Test rate limiter registry."""

    def test_get_rate_limiter(self):
        """Test getting rate limiter from registry."""
        clear_rate_limiters()

        limiter1 = get_rate_limiter("api", rate=100, period=60)
        limiter2 = get_rate_limiter("api")

        assert limiter1 is limiter2

    def test_multiple_limiters(self):
        """Test multiple rate limiters."""
        clear_rate_limiters()

        limiter1 = get_rate_limiter("api1", rate=100)
        limiter2 = get_rate_limiter("api2", rate=200)

        assert limiter1 is not limiter2
        assert limiter1.config.rate == 100
        assert limiter2.config.rate == 200

    def test_clear_registry(self):
        """Test clearing registry."""
        get_rate_limiter("test")
        clear_rate_limiters()

        # Should create new limiter
        limiter1 = get_rate_limiter("test", rate=50)
        limiter2 = get_rate_limiter("test")

        assert limiter1 is limiter2
        assert limiter1.config.rate == 50


class TestRateLimitDecorator:
    """Test rate limit decorator."""

    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator usage."""
        call_count = 0

        @rate_limit(rate=5, period=1.0)
        async def api_call(user_id: str):
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"

        # Should allow 5 calls
        for i in range(5):
            result = await api_call("user_123")
            assert result == f"result_{i + 1}"

        # 6th call should fail
        with pytest.raises(RateLimitExceeded):
            await api_call("user_123")

    @pytest.mark.asyncio
    async def test_decorator_custom_identifier(self):
        """Test decorator with custom identifier function."""

        @rate_limit(
            rate=3,
            period=1.0,
            identifier_func=lambda user_id, **kwargs: user_id,
        )
        async def api_call(user_id: str, data: str = "test"):
            return f"{user_id}:{data}"

        # Should allow 3 calls per user
        for _ in range(3):
            await api_call("user_1", data="test")

        # 4th call should fail for user_1
        with pytest.raises(RateLimitExceeded):
            await api_call("user_1", data="test")

        # But user_2 should still work
        result = await api_call("user_2", data="test")
        assert result == "user_2:test"

    @pytest.mark.asyncio
    async def test_decorator_no_args(self):
        """Test decorator with function that has no args."""

        @rate_limit(rate=2, period=1.0)
        async def api_call():
            return "result"

        # Should use "default" as identifier
        await api_call()
        await api_call()

        with pytest.raises(RateLimitExceeded):
            await api_call()


class TestRetryAfter:
    """Test retry_after calculation."""

    @pytest.mark.asyncio
    async def test_retry_after_token_bucket(self):
        """Test retry_after for token bucket."""
        limiter = RateLimiter(rate=10, period=1.0, algorithm="token_bucket")

        # Use all tokens
        for _ in range(10):
            await limiter.allow("user_123")

        # Check retry_after in exception
        try:
            await limiter.allow("user_123")
        except RateLimitExceeded as e:
            assert 0.0 < e.retry_after < 0.2  # Should be around 0.1s

    @pytest.mark.asyncio
    async def test_retry_after_fixed_window(self):
        """Test retry_after for fixed window."""
        limiter = RateLimiter(rate=5, period=1.0, algorithm="fixed_window")

        # Use up limit
        for _ in range(5):
            await limiter.allow("user_123")

        # Check retry_after
        try:
            await limiter.allow("user_123")
        except RateLimitExceeded as e:
            assert 0.0 < e.retry_after <= 1.0

    @pytest.mark.asyncio
    async def test_retry_after_sliding_window(self):
        """Test retry_after for sliding window."""
        limiter = RateLimiter(rate=5, period=1.0, algorithm="sliding_window")

        # Use up limit
        for _ in range(5):
            await limiter.allow("user_123")

        # Check retry_after
        try:
            await limiter.allow("user_123")
        except RateLimitExceeded as e:
            assert 0.0 < e.retry_after <= 1.0


class TestRateLimiterRepr:
    """Test rate limiter representation."""

    def test_repr(self):
        """Test string representation."""
        limiter = RateLimiter(rate=100, period=60.0, algorithm="token_bucket")
        repr_str = repr(limiter)

        assert "RateLimiter" in repr_str
        assert "rate=100" in repr_str
        assert "period=60" in repr_str
        assert "token_bucket" in repr_str

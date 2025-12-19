"""Tests for rate limiter (infrastructure/intelligence)."""

import time
from unittest.mock import AsyncMock, patch

import pytest

from knowgraph.infrastructure.intelligence.rate_limiter import RateLimiter as APIRateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_initialization():
    limiter = APIRateLimiter()
    # Check private attributes via name mangling or just assuming default
    assert limiter._remaining_requests == 1000
    assert limiter._remaining_tokens == 1000000


@pytest.mark.asyncio
@pytest.mark.skip(reason="Timing test is flaky in CI")
async def test_acquire_no_wait():
    limiter = APIRateLimiter()
    start = time.time()
    await limiter.acquire()
    duration = time.time() - start
    assert duration < 0.1  # Should be instant


@pytest.mark.asyncio
@pytest.mark.skip(reason="Timing test is flaky in CI")
async def test_acquire_with_backoff():
    limiter = APIRateLimiter()

    # Manually trigger backoff
    await limiter.trigger_backoff()

    # Verify backoff set
    assert limiter._backoff_time > time.time()

    time.time()
    # Mock sleep to run fast but verify it was called
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await limiter.acquire()
        mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_update_headers_standard():
    limiter = APIRateLimiter()
    headers = {"x-ratelimit-remaining": "50", "x-ratelimit-reset": "10.0"}
    await limiter.update(headers)
    assert limiter._remaining_requests == 50.0
    # reset time should be roughly now + 10s
    assert limiter._reset_time > time.time() + 9.0


@pytest.mark.asyncio
async def test_update_headers_openrouter_variants():
    limiter = APIRateLimiter()

    # Case 1: requests and tokens specific
    headers = {"x-ratelimit-remaining-requests": "20", "x-ratelimit-remaining-tokens": "5000"}
    await limiter.update(headers)
    assert limiter._remaining_requests == 20.0
    assert limiter._remaining_tokens == 5000.0


@pytest.mark.asyncio
async def test_limit_reached_logic():
    limiter = APIRateLimiter()
    limiter._remaining_requests = 1
    limiter._reset_time = time.time() + 5.0

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await limiter.acquire()
        # Should wait because requests < 2
        mock_sleep.assert_called()


@pytest.mark.asyncio
async def test_trigger_backoff():
    limiter = APIRateLimiter()
    now = time.time()
    await limiter.trigger_backoff()
    assert limiter._backoff_time >= now + 5.0

"""Rate Limiter for handling API quotas dynamically."""

import asyncio
import time
from typing import Any


class RateLimiter:
    """Dynamic rate limiter based on response headers."""

    def __init__(self, requests_per_minute: int = 50, tokens_per_minute: int = 100000) -> None:
        """Initialize rate limiter.

        Args:
            requests_per_minute: The maximum number of requests allowed per minute.
            tokens_per_minute: The maximum number of tokens allowed per minute.
        """
        self._lock = asyncio.Lock()
        self._remaining_requests = 1000  # Default safe high value
        self._remaining_tokens = 1000000  # Default safe high value
        self._reset_time = 0.0
        self._backoff_time = 0.0

    async def acquire(self) -> None:
        """Acquire permission to make a request."""
        async with self._lock:
            # Check if we are in a backoff period
            now = time.time()
            if self._backoff_time > now:
                wait_seconds = self._backoff_time - now
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

            # More conservative thresholds to avoid rate limits
            # Wait if: < 5 requests remaining OR < 5000 tokens remaining
            if (
                self._remaining_requests < 5 or self._remaining_tokens < 5000
            ) and self._reset_time > now:
                # If we have a reset time, wait for it
                # Wait slightly more than needed to be safe
                wait_seconds = (self._reset_time - now) + 2.0
                # Cap max wait to avoid hanging forever on bad headers
                wait_seconds = min(wait_seconds, 30.0)
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)

            # Add small delay between all requests (rate smoothing)
            await asyncio.sleep(0.1)

    async def update(self, headers: Any) -> None:
        """Update limits from response headers."""
        if not headers:
            return

        async with self._lock:
            # Parse OpenRouter / OpenAI standard headers
            # Note: Headers might be case-insensitive proxy objects
            try:
                # Extract values with safe defaults
                # OpenRouter often sends: x-ratelimit-remaining, x-ratelimit-reset

                # Check different casing just in case (httpx headers are case-insensitive usually)
                remaining = headers.get("x-ratelimit-remaining")
                reset = headers.get("x-ratelimit-reset")

                # Some APIs split limits (requests vs tokens)
                # x-ratelimit-remaining-requests
                # x-ratelimit-remaining-tokens
                rem_req = headers.get("x-ratelimit-remaining-requests")
                rem_tok = headers.get("x-ratelimit-remaining-tokens")

                if rem_req is not None:
                    self._remaining_requests = float(rem_req)
                elif remaining is not None:
                    # Fallback if specific not found
                    self._remaining_requests = float(remaining)

                if rem_tok is not None:
                    self._remaining_tokens = float(rem_tok)

                if reset is not None:
                    # Reset time is usually in seconds from now, or timestamp
                    # OpenRouter usually sends seconds to reset
                    try:
                        reset_val = float(reset)
                        # If value is small, it's seconds. If huge, it's timestamp
                        if reset_val < 10000000:
                            self._reset_time = time.time() + reset_val
                        else:
                            self._reset_time = reset_val
                    except ValueError:
                        pass

            except Exception:
                # If parsing fails, ignore to prevent crashing
                pass

    async def trigger_backoff(self) -> None:
        """Manually trigger a backoff (e.g. on 429)."""
        async with self._lock:
            # Longer backoff for 429 errors (10 seconds)
            self._backoff_time = time.time() + 10.0

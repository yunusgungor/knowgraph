"""Tests for the bounded LLM-synthesis retry in the MCP query handler.

The "first weak, second strong" inconsistency: a transient first-call LLM
failure (free-provider cold-start timeout) degraded the answer to raw context.
Retrying the whole synthesis a bounded number of times turns that into a
success.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowgraph.adapters.mcp.handlers.query import _generate_llm_answer


@pytest.fixture(autouse=True)
def _clear_answer_cache():
    """_llm_answer_cache is a module singleton; clear it between tests or a
    cached prompt from a prior test would short-circuit the retry logic."""
    import knowgraph.adapters.mcp.handlers.query as qh

    qh._llm_answer_cache.clear()
    yield
    qh._llm_answer_cache.clear()


def _result(context: str = "CTX"):
    r = MagicMock()
    r.context = context
    r.entity_names = ["QuickVatCalculator"]
    r.explanation = None
    return r


@pytest.mark.asyncio
async def test_retries_transient_first_call_failure():
    """generate_text failing once then succeeding returns the strong answer."""
    provider = MagicMock()
    provider.generate_text = AsyncMock(side_effect=[TimeoutError("cold"), "FULL ANSWER"])

    answer = await _generate_llm_answer("q", _result(), None, False, provider)

    assert answer == "FULL ANSWER"
    assert provider.generate_text.await_count == 2  # retried, not degraded


@pytest.mark.asyncio
async def test_no_retry_when_first_succeeds():
    """A successful first attempt is not re-called."""
    provider = MagicMock()
    provider.generate_text = AsyncMock(return_value="GOOD")

    answer = await _generate_llm_answer("q", _result(), None, False, provider)

    assert answer == "GOOD"
    assert provider.generate_text.await_count == 1


@pytest.mark.asyncio
async def test_all_fail_falls_back_to_context_with_error():
    """All attempts failing returns context + [Generation Error] (honest), bounded."""
    provider = MagicMock()
    provider.generate_text = AsyncMock(side_effect=TimeoutError("still cold"))

    answer = await _generate_llm_answer("q", _result("CTX"), None, False, provider)

    assert "CTX" in answer
    assert "Generation Error" in answer
    # bounded: 2 retries max (default LLM_SYNTHESIS_RETRIES), not infinite
    assert provider.generate_text.await_count == 2


@pytest.mark.asyncio
async def test_empty_answer_retried():
    """An empty (falsy) generated answer is retried, not returned as-is."""
    provider = MagicMock()
    provider.generate_text = AsyncMock(side_effect=["", "RETRIED"])

    answer = await _generate_llm_answer("q", _result(), None, False, provider)

    assert answer == "RETRIED"
    assert provider.generate_text.await_count == 2
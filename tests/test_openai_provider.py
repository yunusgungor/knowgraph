from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowgraph.domain.intelligence.provider import Entity
from knowgraph.infrastructure.intelligence.openai_provider import OpenAIProvider


@pytest.mark.asyncio
async def test_generate_text():
    with patch(
        "knowgraph.infrastructure.intelligence.openai_provider.AsyncOpenAI"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.chat.completions.create = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Response"
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(api_key="key")
        result = await provider.generate_text("prompt")
        assert result == "Response"


@pytest.mark.asyncio
async def test_extract_entities():
    with patch(
        "knowgraph.infrastructure.intelligence.openai_provider.AsyncOpenAI"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.chat.completions.create = AsyncMock()
        mock_response = MagicMock()
        # Mock JSON response
        mock_response.choices[0].message.content = (
            '{"entities": [{"name": "E1", "type": "T1", "description": "D1"}]}'
        )
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(api_key="key")
        entities = await provider.extract_entities("text")
        assert len(entities) == 1
        assert entities[0].name == "E1"


@pytest.mark.asyncio
async def test_extract_relationships():
    with patch(
        "knowgraph.infrastructure.intelligence.openai_provider.AsyncOpenAI"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.chat.completions.create = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = (
            '{"relationships": [{"source": "A", "target": "B", "description": "Rel"}]}'
        )
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(api_key="key")
        e1 = Entity(name="A", type="T", description="D")
        rels = await provider.extract_relationships("text", [e1])
        assert len(rels) == 1
        assert rels[0].source == "A"


@pytest.mark.asyncio
async def test_rate_limiter_applies_to_all_methods():
    """Every LLM call goes through acquire + header sync; errors backoff."""
    with patch(
        "knowgraph.infrastructure.intelligence.openai_provider.AsyncOpenAI"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.chat.completions.create = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok"
        mock_response.headers = {"x-ratelimit-remaining-requests": "10", "x-ratelimit-remaining-tokens": "5000"}
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIProvider(api_key="key")
        provider.rate_limiter.acquire = AsyncMock()
        provider.rate_limiter.update = AsyncMock()
        provider.rate_limiter.trigger_backoff = AsyncMock()

        await provider.generate_text("p")
        await provider.extract_entities("t")
        await provider.extract_relationships("t", [Entity(name="A", type="T", description="D")])

        # acquire() + update(headers) for each of the three calls.
        assert provider.rate_limiter.acquire.await_count == 3
        assert provider.rate_limiter.update.await_count == 3

        # Backoff is NOT triggered on success.
        assert provider.rate_limiter.trigger_backoff.await_count == 0


@pytest.mark.asyncio
async def test_rate_limiter_backoff_on_error():
    """A failed LLM call triggers backoff (handles 429 dynamically)."""
    with patch(
        "knowgraph.infrastructure.intelligence.openai_provider.AsyncOpenAI"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("429 rate limit")
        )

        provider = OpenAIProvider(api_key="key")
        provider.rate_limiter.acquire = AsyncMock()
        provider.rate_limiter.trigger_backoff = AsyncMock()

        with pytest.raises(Exception):
            await provider.generate_text("p")

        assert provider.rate_limiter.acquire.await_count == 1
        assert provider.rate_limiter.trigger_backoff.await_count == 1


@pytest.mark.asyncio
async def test_chat_completion_sends_max_tokens():
    """Completion requests carry an output token cap."""
    with patch(
        "knowgraph.infrastructure.intelligence.openai_provider.AsyncOpenAI"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        create = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ok"
        mock_response.headers = None
        create.return_value = mock_response
        mock_client.chat.completions.create = create

        provider = OpenAIProvider(api_key="key")
        await provider.generate_text("p")

        _, kwargs = create.call_args
        assert "max_tokens" in kwargs
        assert kwargs["max_tokens"] > 0


@pytest.mark.asyncio
async def test_batch_respects_input_token_budget():
    """Over-budget batch drops tail segments instead of blowing context."""
    from knowgraph.config import LLM_MAX_INPUT_TOKENS

    with patch(
        "knowgraph.infrastructure.intelligence.openai_provider.AsyncOpenAI"
    ) as mock_client_cls:
        mock_client = mock_client_cls.return_value
        create = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"results": []}'
        mock_response.headers = None
        create.return_value = mock_response
        mock_client.chat.completions.create = create

        provider = OpenAIProvider(api_key="key")
        # Many texts whose combined size far exceeds the input budget.
        n = 200
        await provider.extract_entities_batch(["x" * (LLM_MAX_INPUT_TOKENS * 4 // n) for _ in range(n)])

        # The prompt sent must be under the budget.
        sent = create.call_args.kwargs["messages"][0]["content"]
        # Approx: under input budget * some slack for the prompt template itself.
        assert len(sent) <= LLM_MAX_INPUT_TOKENS * 4 + 2000

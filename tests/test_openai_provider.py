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

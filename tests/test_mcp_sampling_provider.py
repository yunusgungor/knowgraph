from unittest.mock import AsyncMock, MagicMock

import pytest

from knowgraph.infrastructure.intelligence.mcp_sampling_provider import MCPSamplingProvider


@pytest.fixture
def mock_server():
    return MagicMock()


@pytest.fixture
def mock_request_context():
    context = MagicMock()
    context.session.create_message = AsyncMock()
    return context


@pytest.mark.asyncio
async def test_extract_entities_batch(mock_server, mock_request_context):
    provider = MCPSamplingProvider(mock_server, mock_request_context)

    # Mock extract_entities behavior by mocking session.create_message return value
    # _sample expects result.content to be TextContent or list of TextContent

    # helper to create mock text content
    def create_mock_result(json_str):
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = json_str

        mock_result = MagicMock()
        mock_result.content = [mock_content]  # Return as list to match one of the checks
        return mock_result

    mock_request_context.session.create_message.side_effect = [
        create_mock_result('[{"name": "Entity1", "type": "class", "description": "desc1"}]'),
        create_mock_result('[{"name": "Entity2", "type": "function", "description": "desc2"}]'),
    ]

    texts = ["code1", "code2"]
    results = await provider.extract_entities_batch(texts)

    assert len(results) == 2
    assert len(results[0]) == 1
    assert results[0][0].name == "Entity1"
    assert len(results[1]) == 1
    assert results[1][0].name == "Entity2"
    assert mock_request_context.session.create_message.call_count == 2

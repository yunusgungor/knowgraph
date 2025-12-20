from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowgraph.adapters.mcp.server import call_tool


@pytest.mark.asyncio
async def test_call_tool_query():
    # Mock resolve_graph_path to ignore PROJECT_ROOT logic
    with (
        patch("knowgraph.adapters.mcp.handlers.resolve_graph_path") as mock_resolve,
        patch("knowgraph.adapters.mcp.handlers.QueryEngine") as mock_engine_cls,
        patch("knowgraph.adapters.mcp.server.get_llm_provider") as mock_provider_func,
        patch(
            "knowgraph.adapters.mcp.handlers.QueryExpander"
        ),  # Mock expander too to avoid side effects
    ):

        # Mock Path object with exists() method
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = True
        mock_resolve.return_value = mock_path

        mock_engine = mock_engine_cls.return_value
        # Mock query_async (server uses async version)
        mock_result = MagicMock(context="Answer", explanation=None)
        mock_engine.query_async = AsyncMock(return_value=mock_result)

        # Mock provider to match protocol
        mock_provider_instance = MagicMock()
        mock_provider_instance.generate_text = AsyncMock(return_value="Generated Answer")
        mock_provider_func.return_value = mock_provider_instance

        result = await call_tool("knowgraph_query", {"query": "test"})
        # The tool uses provider to generate answer from context.
        # If provider exists, it replaces answer with generated text.
        assert result[0].text == "Generated Answer"


@pytest.mark.asyncio
async def test_call_tool_index():
    with (
        patch("knowgraph.adapters.mcp.server.resolve_graph_path"),
        patch("knowgraph.adapters.mcp.server.get_llm_provider") as mock_provider,
        # Mock the actual CLI functions that create OpenAIProvider
        patch("knowgraph.adapters.mcp.methods.run_index", new_callable=AsyncMock) as mock_run_index,
    ):

        mock_provider.return_value = MagicMock()
        mock_run_index.return_value = None

        result = await call_tool("knowgraph_index", {"input_path": "docs"})
        # Check that we got a success message (not an error)
        assert "error" not in result[0].text.lower() or "successfully" in result[0].text.lower()


@pytest.mark.asyncio
async def test_call_tool_unknown():
    result = await call_tool("unknown", {})
    assert "Unknown tool" in result[0].text

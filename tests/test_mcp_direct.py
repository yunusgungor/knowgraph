from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowgraph.adapters.mcp.server import knowgraph_index, knowgraph_query


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires MCP request context - integration test")
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

        result = await knowgraph_query(query="test")
        # The tool uses provider to generate answer from context.
        # If provider exists, it replaces answer with generated text.
        assert result == "Generated Answer"


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

        result = await knowgraph_index(input_path="docs")
        # Check that we got a success message (not an error)
        assert "error" not in result.lower() or "successfully" in result.lower()


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires MCP request context - integration test")
async def test_call_tool_unknown():
    # FastMCP rejects unknown tools; verify our 21 tools are registered instead.
    from knowgraph.adapters.mcp.server import app

    names = list(app._tool_manager._tools.keys())
    assert "knowgraph_query" in names
    assert len(names) == 21

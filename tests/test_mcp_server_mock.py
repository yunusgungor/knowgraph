from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Standard import without sys.path hack
from knowgraph.adapters.mcp import server
from knowgraph.adapters.mcp.server import call_tool


@pytest.mark.asyncio
async def test_mcp_validate():
    """Test knowgraph_validate tool."""
    with patch("knowgraph.adapters.mcp.server.validate_graph_consistency") as mock_validate:
        mock_validate.return_value = MagicMock(valid=True, get_error_summary=lambda: "")

        # Mock resolve_graph_path to just return the path string as Path
        with patch(
            "knowgraph.adapters.mcp.server.resolve_graph_path", side_effect=lambda p, r: Path(p)
        ):
            result = await call_tool("knowgraph_validate", {"graph_path": "/tmp/test_graph"})

        assert "VALID" in result[0].text
        mock_validate.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_get_stats():
    """Test knowgraph_get_stats tool."""
    with (
        patch("builtins.open", create=True) as mock_open,
        patch("json.load") as mock_json_load,
        patch("pathlib.Path.exists", return_value=True),
        patch("knowgraph.adapters.mcp.server.resolve_graph_path", side_effect=lambda p, r: Path(p)),
    ):
        mock_json_load.return_value = {
            "version": "1.0",
            "created_at": 0,
            "updated_at": 0,
            "node_count": 100,
            "edge_count": 50,
            "semantic_edge_count": 10,
            "file_hashes": {"a": "1"},
            "files": {"edges": "edges.jsonl", "sparse_index": "index"},
        }

        result = await call_tool("knowgraph_get_stats", {"graph_path": "/tmp/test_graph"})
        assert "Nodes: 100" in result[0].text


@pytest.mark.asyncio
async def test_mcp_query_advanced():
    """Test knowgraph_query with advanced parameters."""
    with (
        patch("knowgraph.adapters.mcp.server.QueryEngine") as MockEngine,
        patch("knowgraph.adapters.mcp.server.QueryExpander") as MockExpander,
        patch("knowgraph.adapters.mcp.server.resolve_graph_path", side_effect=lambda p, r: Path(p)),
        patch("knowgraph.adapters.mcp.server.get_llm_provider") as mock_provider_func,
    ):
        mock_instance = MockEngine.return_value
        mock_result = MagicMock(context="Expanded Context", explanation=None)
        mock_instance.query_async = AsyncMock(return_value=mock_result)

        # Mock provider
        mock_provider = MagicMock()
        mock_provider.generate_text = AsyncMock(return_value="Generated Answer")
        mock_provider_func.return_value = mock_provider

        # Mock async expansion
        MockExpander.return_value.expand_query_async = AsyncMock(return_value=["expanded_term"])

        result = await call_tool(
            "knowgraph_query",
            {
                "query": "test query",
                "top_k": 20,
                "max_hops": 4,
                "max_tokens": 5000,
                "with_explanation": True,
                "enable_hierarchical_lifting": False,
                "lift_levels": 3,
            },
        )

        assert len(result) == 1
        assert result[0].text == "Generated Answer"
        mock_instance.query_async.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_analyze_impact_semantic():
    """Test knowgraph_analyze_impact in semantic mode."""
    with (
        patch("knowgraph.adapters.mcp.server.QueryEngine") as MockEngine,
        patch("knowgraph.adapters.mcp.server.resolve_graph_path", side_effect=lambda p, r: Path(p)),
    ):
        mock_instance = MockEngine.return_value
        mock_result = MagicMock(answer="Semantic Impact Report")
        mock_instance.analyze_impact_async = AsyncMock(return_value=mock_result)

        result = await call_tool(
            "knowgraph_analyze_impact", {"element": "func_x", "mode": "semantic"}
        )
        assert "Semantic Impact Report" in result[0].text
        mock_instance.analyze_impact_async.assert_called_once()


@pytest.mark.asyncio
async def test_mcp_analyze_impact_path():
    """Test knowgraph_analyze_impact in path mode."""
    with (
        patch("knowgraph.adapters.mcp.server.analyze_path_impact_report") as mock_path_impact,
        patch("knowgraph.adapters.mcp.server.resolve_graph_path", side_effect=lambda p, r: Path(p)),
    ):
        mock_path_impact.return_value = [
            server.types.TextContent(type="text", text="Path Impact Report")
        ]

        result = await call_tool("knowgraph_analyze_impact", {"element": "auth.py", "mode": "path"})

        mock_path_impact.assert_called_once()
        assert "Path Impact Report" in result[0].text


@pytest.mark.asyncio
async def test_mcp_index_resume_gc():
    """Test knowgraph_index with resume and gc options."""
    with (
        patch("knowgraph.adapters.mcp.server.index_graph", new_callable=AsyncMock) as mock_index,
        patch("knowgraph.adapters.mcp.server.resolve_graph_path", side_effect=lambda p, r: Path(p)),
        patch("knowgraph.adapters.mcp.server.get_llm_provider", return_value=MagicMock()),
    ):
        mock_index.return_value = [server.types.TextContent(type="text", text="Success")]

        await call_tool("knowgraph_index", {"input_path": "docs", "gc": True, "resume": True})

        # Verify arguments passed to helper (positional)
        call_args = mock_index.call_args
        # index_graph(input_path, graph_path, provider, resume_mode, gc)
        assert call_args[0][0] == "docs"  # input_path
        assert call_args[0][4] is True  # gc
        assert call_args[0][3] is True  # resume_mode

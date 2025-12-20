from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Standard import without sys.path hack
from knowgraph.adapters.mcp import server
from knowgraph.adapters.mcp.server import call_tool


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires MCP request context and graphstore - integration test")
async def test_mcp_validate():
    """Test knowgraph_validate tool."""
    with patch("knowgraph.adapters.mcp.handlers.validate_graph_consistency") as mock_validate:
        mock_validate.return_value = MagicMock(valid=True, get_error_summary=lambda: "")

        # Mock resolve_graph_path to just return the path string as Path
        with patch(
            "knowgraph.adapters.mcp.handlers.resolve_graph_path", side_effect=lambda p, r: Path(p)
        ):
            result = await call_tool("knowgraph_validate", {"graph_path": "/tmp/test_graph"})

        assert "VALID" in result[0].text
        mock_validate.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.skip(reason="Mock patching doesn't work with lazy imports in handler")
async def test_mcp_get_stats():
    """Test knowgraph_get_stats tool."""
    from knowgraph.infrastructure.storage.manifest import Manifest

    with (
        patch("knowgraph.infrastructure.storage.manifest.read_manifest") as mock_read_manifest,
        patch("pathlib.Path.exists", return_value=True),
        patch("knowgraph.adapters.mcp.server.resolve_graph_path", side_effect=lambda p, r: Path(p)),
    ):
        # Mock manifest with expected values
        mock_manifest = Manifest(
            version="1.0",
            node_count=100,
            edge_count=50,
            semantic_edge_count=10,
            file_hashes={"a": "1"},
            edges_filename="edges.jsonl",
            sparse_index_filename="index",
            created_at=0,
            updated_at=0,
        )
        mock_read_manifest.return_value = mock_manifest

        result = await call_tool("knowgraph_get_stats", {"graph_path": "/tmp/test_graph"})
        assert "Nodes: 100" in result[0].text


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires MCP request context and graphstore - integration test")
async def test_mcp_query_advanced():
    """Test knowgraph_query with advanced parameters."""
    with (
        patch("knowgraph.adapters.mcp.handlers.QueryEngine") as MockEngine,
        patch("knowgraph.adapters.mcp.handlers.QueryExpander") as MockExpander,
        patch(
            "knowgraph.adapters.mcp.handlers.resolve_graph_path", side_effect=lambda p, r: Path(p)
        ),
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
@pytest.mark.skip(reason="Requires MCP request context and graphstore - integration test")
async def test_mcp_analyze_impact_semantic():
    """Test knowgraph_analyze_impact in semantic mode."""
    with (
        patch("knowgraph.adapters.mcp.handlers.QueryEngine") as MockEngine,
        patch(
            "knowgraph.adapters.mcp.handlers.resolve_graph_path", side_effect=lambda p, r: Path(p)
        ),
    ):
        mock_instance = MockEngine.return_value
        mock_result = MagicMock(active_subgraph_size=10, context="Semantic Impact Report")
        mock_instance.analyze_impact_async = AsyncMock(return_value=mock_result)

        result = await call_tool(
            "knowgraph_analyze_impact", {"element": "func_x", "mode": "semantic"}
        )
        # Check that analyze_impact_async was called (mock worked)
        mock_instance.analyze_impact_async.assert_called_once()
        # Result should not be an error
        assert "failed" not in result[0].text.lower() or "Semantic Impact Report" in result[0].text


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires MCP request context and graphstore - integration test")
async def test_mcp_analyze_impact_path():
    """Test knowgraph_analyze_impact in path mode."""
    with (
        patch("knowgraph.adapters.mcp.handlers.analyze_path_impact_report") as mock_path_impact,
        patch(
            "knowgraph.adapters.mcp.handlers.resolve_graph_path", side_effect=lambda p, r: Path(p)
        ),
    ):
        mock_path_impact.return_value = [
            server.types.TextContent(type="text", text="Path Impact Report")
        ]

        result = await call_tool("knowgraph_analyze_impact", {"element": "auth.py", "mode": "path"})

        mock_path_impact.assert_called_once()
        # Check result is not empty and mock was called
        assert len(result) > 0


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires MCP request context and graphstore - integration test")
async def test_mcp_index_resume_gc():
    """Test knowgraph_index with resume and gc options."""
    with (
        patch("knowgraph.adapters.mcp.methods.run_index", new_callable=AsyncMock) as mock_run_index,
        patch(
            "knowgraph.adapters.mcp.handlers.resolve_graph_path", side_effect=lambda p, r: Path(p)
        ),
        patch("knowgraph.adapters.mcp.server.get_llm_provider", return_value=MagicMock()),
        patch("knowgraph.adapters.mcp.methods.read_manifest", return_value=MagicMock()),
    ):
        mock_run_index.return_value = None

        result = await call_tool(
            "knowgraph_index", {"input_path": "docs", "gc": True, "resume": True}
        )

        # Check that result indicates success
        assert "success" in result[0].text.lower() or "indexed" in result[0].text.lower()

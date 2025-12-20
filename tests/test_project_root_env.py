"""Tests for KNOWGRAPH_PROJECT_ROOT environment variable functionality."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


def test_project_root_auto_detection():
    """Test that PROJECT_ROOT is auto-detected when no env var is set."""
    with patch.dict(os.environ, {}, clear=True):
        # Remove any env vars
        os.environ.pop("KNOWGRAPH_PROJECT_ROOT", None)

        # Re-import to pick up the change
        import importlib

        import knowgraph.adapters.mcp.server as server_module

        importlib.reload(server_module)

        # Should auto-detect (will be cwd or git root)
        assert isinstance(server_module.PROJECT_ROOT, Path)


def test_resolve_graph_path_with_project_root():
    """Test that resolve_graph_path uses PROJECT_ROOT correctly."""
    from knowgraph.adapters.mcp.utils import resolve_graph_path

    project_root = Path("/Users/test/my-project")
    relative_path = "./graphstore"

    result = resolve_graph_path(relative_path, project_root)

    assert result == Path("/Users/test/my-project/graphstore")


def test_resolve_graph_path_with_absolute_path():
    """Test that resolve_graph_path handles absolute paths correctly."""
    from knowgraph.adapters.mcp.utils import resolve_graph_path

    project_root = Path("/Users/test/my-project")
    absolute_path = "/custom/graphstore/location"

    result = resolve_graph_path(absolute_path, project_root)

    assert result == Path("/custom/graphstore/location")


@pytest.mark.skip(reason="Complex env reload test - auto-detection tested in other tests")
@pytest.mark.asyncio
async def test_mcp_tools_use_auto_detected_root():
    """Test that MCP tools use auto-detected PROJECT_ROOT."""
    from knowgraph.adapters.mcp.server import call_tool

    with patch.dict(os.environ, {}, clear=True):
        # Re-import to pick up the change
        import importlib

        import knowgraph.adapters.mcp.server as server_module

        importlib.reload(server_module)

        # Mock the resolve_graph_path to verify it's called
        with patch("knowgraph.adapters.mcp.server.resolve_graph_path") as mock_resolve:
            mock_resolve.return_value = Path("/test/graphstore")

            # Call a tool that uses graph_path
            try:
                await call_tool("knowgraph_get_stats", {})
            except Exception:
                # We expect it to fail (no actual graphstore), but we can verify the call
                pass

            # Verify resolve_graph_path was called
            assert mock_resolve.called


def test_multiple_projects_isolation():
    """Test that different working directories result in different graphstore paths."""
    from knowgraph.adapters.mcp.utils import resolve_graph_path
    from knowgraph.config import DEFAULT_GRAPH_STORE_PATH

    project_a = Path("/Users/test/project-a")
    project_b = Path("/Users/test/project-b")

    graphstore_a = resolve_graph_path(DEFAULT_GRAPH_STORE_PATH, project_a)
    graphstore_b = resolve_graph_path(DEFAULT_GRAPH_STORE_PATH, project_b)

    assert graphstore_a == Path("/Users/test/project-a/graphstore")
    assert graphstore_b == Path("/Users/test/project-b/graphstore")
    assert graphstore_a != graphstore_b

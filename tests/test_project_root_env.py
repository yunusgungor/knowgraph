"""Tests for graph store path resolution in a workspace context."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest


def test_project_root_auto_detection():
    """Test that PROJECT_ROOT is auto-detected when no env var is set."""
    # Preserve HOME/PATH so Path.home() and subprocess work on all platforms
    safe_env = {k: v for k, v in os.environ.items()
                if k in ("HOME", "PATH", "HOMEDRIVE", "HOMEPATH", "USERPROFILE")}
    with patch.dict(os.environ, safe_env, clear=True):
        # Remove any env vars
        os.environ.pop("KNOWGRAPH_PROJECT_ROOT", None)

        # Re-import to pick up the change
        import importlib

        import knowgraph.adapters.mcp.server as server_module

        importlib.reload(server_module)

        # Should auto-detect (will be cwd or git root)
        assert isinstance(server_module.PROJECT_ROOT, Path)


def test_resolve_graph_store_with_project_root(tmp_path):
    """Test that resolve_graph_store uses PROJECT_ROOT correctly."""
    from knowgraph.infrastructure.detection.graph_store_locator import (
        resolve_graph_store,
    )

    project_root = tmp_path / "my-project"
    project_root.mkdir()
    relative_path = "./graphstore"

    result = resolve_graph_store(relative_path, root_dir=project_root)

    assert result == (project_root / "graphstore").resolve()


def test_resolve_graph_store_with_absolute_path(tmp_path):
    """Test that resolve_graph_store handles absolute paths correctly."""
    from knowgraph.infrastructure.detection.graph_store_locator import (
        resolve_graph_store,
    )

    project_root = tmp_path / "my-project"
    project_root.mkdir()
    absolute_path = str(tmp_path / "custom" / "graphstore" / "location")

    result = resolve_graph_store(absolute_path, root_dir=project_root)

    assert result == Path(absolute_path)


@pytest.mark.skip(reason="Complex env reload test - auto-detection tested in other tests")
@pytest.mark.asyncio
async def test_mcp_tools_use_auto_detected_root():
    """Test that MCP tools use auto-detected PROJECT_ROOT."""
    from knowgraph.adapters.mcp.server import call_tool

    safe_env = {k: v for k, v in os.environ.items()
                if k in ("HOME", "PATH", "HOMEDRIVE", "HOMEPATH", "USERPROFILE")}
    with patch.dict(os.environ, safe_env, clear=True):
        # Re-import to pick up the change
        import importlib

        import knowgraph.adapters.mcp.server as server_module

        importlib.reload(server_module)

        # Mock the resolve_graph_store to verify it's called
        with patch("knowgraph.adapters.mcp.server.resolve_graph_store") as mock_resolve:
            mock_resolve.return_value = Path("/test/graphstore")

            # Call a tool that uses graph_path
            try:
                await call_tool("knowgraph_get_stats", {})
            except Exception:
                # We expect it to fail (no actual graphstore), but we can verify the call
                pass

            # Verify resolve_graph_store was called
            assert mock_resolve.called


def test_multiple_projects_isolation(tmp_path):
    """Test that different working directories result in different graphstore paths."""
    from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
    from knowgraph.infrastructure.detection.graph_store_locator import (
        resolve_graph_store,
    )

    project_a = tmp_path / "project-a"
    project_a.mkdir()
    project_b = tmp_path / "project-b"
    project_b.mkdir()

    graphstore_a = resolve_graph_store(DEFAULT_GRAPH_STORE_PATH, root_dir=project_a)
    graphstore_b = resolve_graph_store(DEFAULT_GRAPH_STORE_PATH, root_dir=project_b)

    assert graphstore_a == (project_a / "graphstore").resolve()
    assert graphstore_b == (project_b / "graphstore").resolve()
    assert graphstore_a != graphstore_b

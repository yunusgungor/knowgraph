"""Tests for project root auto-detection."""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from knowgraph.infrastructure.detection.project_detector import (
    detect_git_root,
    detect_project_markers,
    detect_project_root,
)


class TestDetectGitRoot:
    """Tests for Git root detection."""

    def test_detect_git_root_in_git_repo(self, tmp_path):
        """Test detection in a git repository."""
        # Create a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

        # Create subdirectory
        subdir = tmp_path / "src" / "app"
        subdir.mkdir(parents=True)

        # Detect from subdirectory
        result = detect_git_root(subdir)

        assert result == tmp_path

    def test_detect_git_root_not_in_repo(self, tmp_path):
        """Test detection when not in a git repository."""
        result = detect_git_root(tmp_path)
        assert result is None

    def test_detect_git_root_default_path(self):
        """Test detection with default path (cwd)."""
        # This might succeed or fail depending on whether we're in a git repo
        result = detect_git_root()
        # Just ensure it doesn't crash
        assert result is None or isinstance(result, Path)


class TestDetectProjectMarkers:
    """Tests for project marker file detection."""

    def test_detect_pyproject_toml(self, tmp_path):
        """Test detection of pyproject.toml."""
        # Create project structure
        project_root = tmp_path / "my-project"
        project_root.mkdir()
        (project_root / "pyproject.toml").touch()

        subdir = project_root / "src" / "app"
        subdir.mkdir(parents=True)

        # Detect from subdirectory
        result = detect_project_markers(subdir)

        assert result == project_root

    def test_detect_package_json(self, tmp_path):
        """Test detection of package.json."""
        project_root = tmp_path / "my-app"
        project_root.mkdir()
        (project_root / "package.json").touch()

        subdir = project_root / "src"
        subdir.mkdir()

        result = detect_project_markers(subdir)

        assert result == project_root

    def test_detect_cargo_toml(self, tmp_path):
        """Test detection of Cargo.toml."""
        project_root = tmp_path / "rust-project"
        project_root.mkdir()
        (project_root / "Cargo.toml").touch()

        subdir = project_root / "src"
        subdir.mkdir()

        result = detect_project_markers(subdir)

        assert result == project_root

    def test_no_markers_found(self, tmp_path):
        """Test when no marker files are found."""
        subdir = tmp_path / "some" / "deep" / "path"
        subdir.mkdir(parents=True)

        result = detect_project_markers(subdir)

        assert result is None

    def test_multiple_markers(self, tmp_path):
        """Test with multiple marker files."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").touch()
        (project_root / "package.json").touch()
        (project_root / "README.md").touch()

        subdir = project_root / "src" / "lib"
        subdir.mkdir(parents=True)

        result = detect_project_markers(subdir)

        assert result == project_root


class TestDetectProjectRoot:
    """Tests for main project root detection."""

    def test_detect_with_git_root(self, tmp_path):
        """Test detection prioritizes git root."""
        # Create git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

        subdir = tmp_path / "src"
        subdir.mkdir()

        result = detect_project_root(subdir, use_llm=False)

        assert result == tmp_path

    def test_detect_with_markers_no_git(self, tmp_path):
        """Test detection falls back to markers when no git."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").touch()

        subdir = project_root / "src"
        subdir.mkdir()

        result = detect_project_root(subdir, use_llm=False)

        assert result == project_root

    def test_detect_fallback_to_cwd(self, tmp_path):
        """Test fallback to current directory."""
        # No git, no markers
        subdir = tmp_path / "random" / "path"
        subdir.mkdir(parents=True)

        result = detect_project_root(subdir, use_llm=False)

        # Should return the start path
        assert result == subdir

    def test_detect_priority_git_over_markers(self, tmp_path):
        """Test that git root takes priority over markers."""
        # Create git repo at root
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

        # Create marker file in subdirectory
        subdir = tmp_path / "subproject"
        subdir.mkdir()
        (subdir / "pyproject.toml").touch()

        deeper = subdir / "src"
        deeper.mkdir()

        result = detect_project_root(deeper, use_llm=False)

        # Should return git root, not marker location
        assert result == tmp_path


class TestMCPServerIntegration:
    """Tests for MCP server integration."""

    def test_project_root_auto_detection_in_server(self):
        """Test that server auto-detects project root."""
        with patch.dict(os.environ, {}, clear=True):
            # Re-import to pick up changes
            import importlib

            import knowgraph.adapters.mcp.server as server_module

            importlib.reload(server_module)

            # Should auto-detect (will be cwd or git root)
            assert isinstance(server_module.PROJECT_ROOT, Path)

    def test_cache_mechanism(self):
        """Test that cache mechanism works."""

        import knowgraph.adapters.mcp.server as server_module

        # Clear cache first
        server_module._PROJECT_ROOT_CACHE["root"] = None
        server_module._PROJECT_ROOT_CACHE["timestamp"] = None

        test_path = Path("/test/path")

        # Cache a path
        server_module._cache_project_root(test_path)

        # Should return cached path
        cached = server_module._get_cached_project_root()
        assert cached == test_path

    def test_cache_expiration(self):
        """Test that cache expires after TTL."""
        import time

        import knowgraph.adapters.mcp.server as server_module

        test_path = Path("/test/path")

        # Cache with very short TTL
        server_module._PROJECT_ROOT_CACHE["ttl"] = 0.1  # 100ms
        server_module._cache_project_root(test_path)

        # Should be cached immediately
        assert server_module._get_cached_project_root() == test_path

        # Wait for expiration
        time.sleep(0.2)

        # Should be expired
        assert server_module._get_cached_project_root() is None

        # Reset TTL
        server_module._PROJECT_ROOT_CACHE["ttl"] = 3600


@pytest.mark.integration
class TestRealWorldScenarios:
    """Integration tests with real project structures."""

    def test_python_project_structure(self, tmp_path):
        """Test detection in a typical Python project."""
        # Create Python project structure
        project = tmp_path / "my-python-app"
        project.mkdir()

        # Add project files
        (project / "pyproject.toml").write_text("[tool.poetry]\nname = 'my-app'\n")
        (project / "README.md").write_text("# My App\n")

        # Create source structure
        src = project / "src" / "myapp"
        src.mkdir(parents=True)
        (src / "__init__.py").touch()
        (src / "main.py").touch()

        # Detect from deep in source tree
        result = detect_project_root(src, use_llm=False)

        assert result == project

    def test_nodejs_project_structure(self, tmp_path):
        """Test detection in a Node.js project."""
        project = tmp_path / "my-node-app"
        project.mkdir()

        # Add Node.js files
        (project / "package.json").write_text('{"name": "my-app"}')
        (project / "README.md").touch()

        # Create source structure
        src = project / "src" / "components"
        src.mkdir(parents=True)

        result = detect_project_root(src, use_llm=False)

        assert result == project

    def test_monorepo_structure(self, tmp_path):
        """Test detection in a monorepo.

        In a monorepo, git root takes priority over sub-project markers.
        This is the expected behavior.
        """
        # Create monorepo with git at root
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)

        # Create sub-projects with subdirectories
        frontend = tmp_path / "frontend"
        frontend.mkdir()
        (frontend / "package.json").touch()
        frontend_src = frontend / "src"
        frontend_src.mkdir()

        backend = tmp_path / "backend"
        backend.mkdir()
        (backend / "pyproject.toml").touch()
        backend_app = backend / "app"
        backend_app.mkdir()

        # Detect from frontend subdirectory - should find git root (not frontend)
        # Git root takes priority over marker files
        result_frontend = detect_project_root(frontend_src, use_llm=False)
        assert result_frontend == tmp_path

        # Detect from backend subdirectory - should find git root (not backend)
        result_backend = detect_project_root(backend_app, use_llm=False)
        assert result_backend == tmp_path

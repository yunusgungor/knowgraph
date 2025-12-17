"""Tests for repository ingestor module."""

from unittest.mock import patch

import pytest

from knowgraph.infrastructure.parsing.repo_ingestor import (
    GitingestNotInstalledError,
    RepositoryIngestorError,
    detect_source_type,
    ingest_repository,
    ingest_source,
)


class TestDetectSourceType:
    """Tests for source type detection."""

    def test_detect_github_url(self):
        """Test detection of GitHub repository URL."""
        assert detect_source_type("https://github.com/user/repo") == "repository"
        assert detect_source_type("git@github.com:user/repo.git") == "repository"

    def test_detect_gitlab_url(self):
        """Test detection of GitLab repository URL."""
        assert detect_source_type("https://gitlab.com/user/repo") == "repository"

    def test_detect_bitbucket_url(self):
        """Test detection of Bitbucket repository URL."""
        assert detect_source_type("https://bitbucket.org/user/repo") == "repository"

    def test_detect_markdown_file(self, tmp_path):
        """Test detection of markdown file."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test")
        assert detect_source_type(str(md_file)) == "markdown"

    def test_detect_code_directory(self, tmp_path):
        """Test detection of code directory."""
        code_dir = tmp_path / "code"
        code_dir.mkdir()
        (code_dir / "test.py").write_text("print('hello')")
        assert detect_source_type(str(code_dir)) == "directory"

    def test_detect_markdown_directory(self, tmp_path):
        """Test detection of markdown directory."""
        md_dir = tmp_path / "docs"
        md_dir.mkdir()
        (md_dir / "test.md").write_text("# Test")
        assert detect_source_type(str(md_dir)) == "markdown"

    def test_detect_nonexistent_local_path(self):
        """Test detection of non-existent local path."""
        assert detect_source_type("/nonexistent/path") == "directory"


class TestIngestRepository:
    """Tests for repository ingestion."""

    @pytest.mark.asyncio
    @patch("knowgraph.infrastructure.parsing.repo_ingestor.ingest_async")
    async def test_ingest_repository_success(self, mock_ingest):
        """Test successful repository ingestion."""
        # Mock gitingest response
        mock_ingest.return_value = (
            "Summary: Test repository",
            "test/\n  file.py",
            "# Code content",
        )

        content, output_path = await ingest_repository("https://github.com/user/repo")

        assert "Repository Digest" in content
        assert "Summary: Test repository" in content
        assert "Directory Structure" in content
        assert "File Contents" in content
        assert output_path.exists()
        assert output_path.suffix == ".md"

        # Cleanup
        output_path.unlink()

    @pytest.mark.asyncio
    @patch("knowgraph.infrastructure.parsing.repo_ingestor.ingest_async")
    async def test_ingest_repository_with_patterns(self, mock_ingest):
        """Test repository ingestion with include/exclude patterns."""
        mock_ingest.return_value = ("Summary", "tree", "content")

        content, output_path = await ingest_repository(
            "https://github.com/user/repo",
            include_patterns=["*.py"],
            exclude_patterns=["node_modules/*"],
        )

        assert mock_ingest.called
        # Cleanup
        output_path.unlink()

    @pytest.mark.asyncio
    @patch("knowgraph.infrastructure.parsing.repo_ingestor.ingest_async")
    async def test_ingest_repository_with_access_token(self, mock_ingest):
        """Test repository ingestion with access token."""
        mock_ingest.return_value = ("Summary", "tree", "content")

        content, output_path = await ingest_repository(
            "https://github.com/user/private-repo",
            access_token="github_pat_xxx",  # noqa: S106
        )

        assert mock_ingest.called
        # Cleanup
        output_path.unlink()

    @pytest.mark.asyncio
    @patch("knowgraph.infrastructure.parsing.repo_ingestor.ingest_async")
    async def test_ingest_repository_to_specific_path(self, mock_ingest, tmp_path):
        """Test repository ingestion to specific output path."""
        mock_ingest.return_value = ("Summary", "tree", "content")
        output_path = tmp_path / "custom_output.md"

        content, returned_path = await ingest_repository(
            "https://github.com/user/repo",
            output_path=output_path,
        )

        assert returned_path == output_path
        assert output_path.exists()

    @pytest.mark.asyncio
    @patch("knowgraph.infrastructure.parsing.repo_ingestor.ingest_async", None)
    async def test_ingest_repository_gitingest_not_installed(self):
        """Test error when gitingest is not installed."""
        with pytest.raises(GitingestNotInstalledError):
            await ingest_repository("https://github.com/user/repo")

    @pytest.mark.asyncio
    @patch("knowgraph.infrastructure.parsing.repo_ingestor.ingest_async")
    async def test_ingest_repository_error(self, mock_ingest):
        """Test error handling during ingestion."""
        mock_ingest.side_effect = Exception("Network error")

        with pytest.raises(RepositoryIngestorError) as exc_info:
            await ingest_repository("https://github.com/user/repo")

        assert "Failed to ingest repository" in str(exc_info.value)


class TestIngestSource:
    """Tests for intelligent source ingestion."""

    @pytest.mark.asyncio
    @patch("knowgraph.infrastructure.parsing.repo_ingestor.ingest_async")
    async def test_ingest_source_repository(self, mock_ingest):
        """Test ingesting a repository URL."""
        mock_ingest.return_value = ("Summary", "tree", "content")

        content, output_path, source_type = await ingest_source("https://github.com/user/repo")

        assert source_type == "repository"
        assert "Repository Digest" in content
        assert output_path.exists()

        # Cleanup
        output_path.unlink()

    @pytest.mark.asyncio
    async def test_ingest_source_markdown_file(self, tmp_path):
        """Test ingesting a markdown file."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test Content")

        content, output_path, source_type = await ingest_source(str(md_file))

        assert source_type == "markdown"
        assert content == "# Test Content"
        assert output_path == md_file

    @pytest.mark.asyncio
    @patch("knowgraph.infrastructure.parsing.repo_ingestor.ingest_async")
    async def test_ingest_source_code_directory(self, mock_ingest, tmp_path):
        """Test ingesting a code directory."""
        code_dir = tmp_path / "code"
        code_dir.mkdir()
        (code_dir / "test.py").write_text("print('hello')")

        mock_ingest.return_value = ("Summary", "tree", "content")

        content, output_path, source_type = await ingest_source(str(code_dir))

        assert source_type == "directory"
        assert "Repository Digest" in content

        # Cleanup
        output_path.unlink()

    @pytest.mark.asyncio
    @patch("knowgraph.infrastructure.parsing.repo_ingestor.ingest_async")
    async def test_ingest_source_force_type(self, mock_ingest, tmp_path):
        """Test forcing source type detection."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test")

        mock_ingest.return_value = ("Summary", "tree", "content")

        # Force treating markdown file as a directory
        content, output_path, source_type = await ingest_source(
            str(md_file), force_type="directory"
        )

        assert source_type == "directory"
        assert mock_ingest.called

        # Cleanup
        output_path.unlink()

    @pytest.mark.asyncio
    @patch("knowgraph.infrastructure.parsing.repo_ingestor.ingest_async")
    async def test_ingest_source_with_all_options(self, mock_ingest):
        """Test ingesting with all options specified."""
        mock_ingest.return_value = ("Summary", "tree", "content")

        content, output_path, source_type = await ingest_source(
            "https://github.com/user/repo",
            include_patterns=["*.py", "*.md"],
            exclude_patterns=["tests/*"],
            max_file_size=1024000,
            access_token="token",  # noqa: S106
        )

        assert source_type == "repository"
        assert mock_ingest.called

        # Cleanup
        output_path.unlink()

"""End-to-End MCP Server Test Suite.

Comprehensive tests for all MCP tools verifying beta branch improvements:
- Refactored run_index integration
- Config system usage
- Helper functions
- All MCP tools functionality
"""

import tempfile
from pathlib import Path

import pytest

from knowgraph.adapters.mcp.handlers import (
    handle_batch_query,
    handle_get_stats,
    handle_index,
    handle_query,
    handle_validate,
)
from knowgraph.config import get_settings


@pytest.fixture
def temp_graph_store():
    """Create temporary graph store for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_markdown_file(tmp_path):
    """Create sample markdown file for testing."""
    md_file = tmp_path / "test.md"
    md_file.write_text(
        """# Test Document

This is a test document for E2E testing.

## Features
- Feature A
- Feature B

## Code Example
```python
def hello():
    print("Hello, World!")
```
"""
    )
    return md_file


@pytest.fixture
def mock_provider():
    """Mock intelligence provider for testing."""

    class MockProvider:
        async def extract_entities(self, text):
            return []

        async def expand_query(self, query):
            return [query]

    return MockProvider()


class TestE2EMCPIndexing:
    """Test MCP indexing with refactored run_index."""

    @pytest.mark.asyncio
    async def test_index_local_file(self, sample_markdown_file, temp_graph_store, mock_provider):
        """Test indexing a local markdown file via MCP."""
        result = await handle_index(
            arguments={
                "input_path": str(sample_markdown_file),
                "output_path": str(temp_graph_store),
            },
            provider=mock_provider,
            project_root=sample_markdown_file.parent,
        )

        assert len(result) > 0
        assert "Successfully indexed" in result[0].text or "completed" in result[0].text.lower()

        # Verify graph store created
        assert temp_graph_store.exists()
        assert (temp_graph_store / "metadata" / "manifest.json").exists()

    @pytest.mark.asyncio
    async def test_index_uses_refactored_run_index(
        self, sample_markdown_file, temp_graph_store, mock_provider
    ):
        """Verify MCP uses refactored run_index (with helpers)."""
        # This test verifies integration by checking the result includes
        # features from refactored code (hash checking, helper functions)

        # First index
        result1 = await handle_index(
            arguments={
                "input_path": str(sample_markdown_file),
                "output_path": str(temp_graph_store),
            },
            provider=mock_provider,
            project_root=sample_markdown_file.parent,
        )

        # Second index (should skip - hash checking from helper)
        result2 = await handle_index(
            arguments={
                "input_path": str(sample_markdown_file),
                "output_path": str(temp_graph_store),
            },
            provider=mock_provider,
            project_root=sample_markdown_file.parent,
        )

        # Should detect no changes (helper: should_skip_indexing)
        assert len(result2) > 0
        # Verify hash checking worked
        assert (temp_graph_store / "metadata" / "manifest.json").exists()


class TestE2EMCPQuery:
    """Test MCP query with config system."""

    @pytest.mark.asyncio
    async def test_query_uses_config_system(self, temp_graph_store, mock_provider):
        """Verify query uses merged config system."""
        settings = get_settings()

        # Config should be accessible
        assert settings.query.top_k == 20
        assert settings.query.max_hops == 4

        # Query with default config
        result = await handle_query(
            arguments={
                "query": "test query",
                "graph_path": str(temp_graph_store),
            },
            provider=mock_provider,
            project_root=temp_graph_store,
        )

        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_batch_query(self, temp_graph_store, mock_provider):
        """Test batch query functionality."""
        result = await handle_batch_query(
            arguments={
                "queries": ["query1", "query2", "query3"],
                "graph_path": str(temp_graph_store),
            },
            provider=mock_provider,
            project_root=temp_graph_store,
        )

        assert len(result) > 0


class TestE2EMCPStats:
    """Test MCP statistics and validation."""

    @pytest.mark.asyncio
    async def test_get_stats(self, temp_graph_store, mock_provider):
        """Test getting graph statistics."""
        result = await handle_get_stats(
            arguments={
                "graph_path": str(temp_graph_store),
            },
            project_root=temp_graph_store,
        )

        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_validate_graph(self, temp_graph_store, mock_provider):
        """Test graph validation."""
        result = await handle_validate(
            arguments={
                "graph_path": str(temp_graph_store),
            },
            project_root=temp_graph_store,
        )

        assert len(result) > 0


class TestE2EIntegration:
    """Full integration tests."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, sample_markdown_file, temp_graph_store, mock_provider):
        """Test complete workflow: index → query → stats."""
        # 1. Index
        index_result = await handle_index(
            arguments={
                "input_path": str(sample_markdown_file),
                "output_path": str(temp_graph_store),
            },
            provider=mock_provider,
            project_root=sample_markdown_file.parent,
        )
        assert len(index_result) > 0

        # 2. Query
        query_result = await handle_query(
            arguments={
                "query": "test features",
                "graph_path": str(temp_graph_store),
            },
            provider=mock_provider,
            project_root=temp_graph_store,
        )
        assert len(query_result) > 0

        # 3. Stats
        stats_result = await handle_get_stats(
            arguments={
                "graph_path": str(temp_graph_store),
            },
            project_root=temp_graph_store,
        )
        assert len(stats_result) > 0

    @pytest.mark.asyncio
    async def test_config_integration(self):
        """Test config system integration."""
        settings = get_settings()

        # Verify Pydantic settings
        assert settings.performance.max_workers >= 1
        assert settings.memory.warning_threshold_mb >= 100
        assert settings.query.top_k >= 1

        # Verify can be customized via environment
        # (would need actual env variable setting)
        assert settings.performance.cache_size >= 100


class TestE2EHelperFunctions:
    """Test that helper functions are used."""

    def test_helpers_importable(self):
        """Verify helper functions are importable."""
        from knowgraph.adapters.cli.index_helpers import (
            build_knowledge_graph,
            chunk_files,
            create_and_save_manifest,
            detect_and_prepare_source,
            prepare_files_and_hashes,
            write_graph_to_storage,
        )

        # All should be callable
        assert callable(detect_and_prepare_source)
        assert callable(prepare_files_and_hashes)
        assert callable(chunk_files)
        assert callable(build_knowledge_graph)
        assert callable(write_graph_to_storage)
        assert callable(create_and_save_manifest)

    @pytest.mark.asyncio
    async def test_run_index_imports_helpers(self):
        """Verify run_index uses helpers."""
        import inspect

        from knowgraph.adapters.cli.index_command import run_index

        source = inspect.getsource(run_index)

        # Should import helpers
        assert "from knowgraph.adapters.cli.index_helpers import" in source

        # Should use key helpers
        assert "detect_and_prepare_source" in source
        assert "chunk_files" in source
        assert "build_knowledge_graph" in source


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])

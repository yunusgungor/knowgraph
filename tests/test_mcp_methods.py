from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from knowgraph.adapters.mcp.methods import analyze_path_impact_report, index_graph
from knowgraph.domain.intelligence.provider import Entity, IntelligenceProvider


@pytest.mark.asyncio
async def test_index_graph_resume_no_manifest():
    graph_path = Path("graph")
    provider = MagicMock(spec=IntelligenceProvider)

    with (
        patch("knowgraph.adapters.mcp.methods.read_manifest", return_value=None),
        patch("knowgraph.adapters.mcp.methods.validate_path", side_effect=lambda p, **k: Path(p)),
    ):
        result = await index_graph("input.md", graph_path, provider, resume_mode=True, gc=False)
        assert "Error: Cannot resume" in result[0].text


@pytest.mark.asyncio
async def test_index_graph_resume_success(tmp_path):
    # Create a real file so Path().is_file() returns True
    input_file = tmp_path / "input.md"
    input_file.write_text("content")  # Content is actually read by open()

    graph_path = Path("graph")
    provider = MagicMock(spec=IntelligenceProvider)
    provider.extract_entities = AsyncMock(
        return_value=[Entity(name="E", type="T", description="D")]
    )

    mock_manifest = MagicMock()

    mock_delta = MagicMock()

    from uuid import uuid4

    from knowgraph.domain.models.node import Node

    real_node = Node(
        id=uuid4(),
        hash="a" * 40,
        title="t",
        content="c",
        path="p",
        type="text",
        token_count=1,
        created_at=1,
    )
    mock_delta.added_nodes = [real_node]

    # We don't need to mock validate_path if the file exists
    # We don't need to mock open if we wrote the file

    with (
        patch("knowgraph.adapters.mcp.methods.read_manifest", return_value=mock_manifest),
        patch("knowgraph.adapters.mcp.methods.detect_delta", return_value=mock_delta),
        patch("knowgraph.adapters.mcp.methods.apply_incremental_update") as mock_apply,
    ):

        result = await index_graph(str(input_file), graph_path, provider, resume_mode=True, gc=True)

        assert "Successfully resumed" in result[0].text
        provider.extract_entities.assert_called_once()
        mock_apply.assert_called_once()


@pytest.mark.asyncio
async def test_index_graph_standard_update():
    graph_path = Path("graph")
    provider = MagicMock(spec=IntelligenceProvider)

    # Simulate manifest exists -> run_update
    with (
        patch("pathlib.Path.exists", return_value=True),
        patch("knowgraph.adapters.mcp.methods.run_index", new_callable=AsyncMock) as mock_run,
        patch("knowgraph.adapters.mcp.methods.validate_path", side_effect=lambda p, **k: Path(p)),
    ):

        result = await index_graph("input.md", graph_path, provider, resume_mode=False, gc=False)
        assert "Successfully indexed/updated" in result[0].text
        mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_index_graph_standard_init():
    graph_path = Path("graph")
    provider = MagicMock(spec=IntelligenceProvider)

    # Simulate manifest does NOT exist -> run_index
    with (
        patch("pathlib.Path.exists", return_value=False),
        patch("knowgraph.adapters.mcp.methods.run_index", new_callable=AsyncMock) as mock_run,
        patch("knowgraph.adapters.mcp.methods.validate_path", side_effect=lambda p, **k: Path(p)),
    ):

        result = await index_graph("input.md", graph_path, provider, resume_mode=False, gc=False)
        assert "Successfully indexed/updated" in result[0].text
        mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_index_graph_error():
    # Simulate exception during indexing
    with (
        patch(
            "knowgraph.infrastructure.parsing.repo_ingestor.detect_source_type",
            return_value="markdown",
        ),
        patch("knowgraph.adapters.mcp.methods.validate_path", return_value=Path("input.md")),
        patch("knowgraph.adapters.mcp.methods.run_index", side_effect=Exception("Boom")),
    ):
        result = await index_graph("input.md", Path("p"), MagicMock(), resume_mode=False, gc=False)
        assert "Error indexing: Boom" in result[0].text


def test_analyze_path_impact_report_no_results():
    with (
        patch("knowgraph.adapters.mcp.methods.list_all_nodes", return_value=[]),
        patch("knowgraph.adapters.mcp.methods.read_all_edges", return_value=[]),
        patch("knowgraph.adapters.mcp.methods.analyze_impact_by_path", return_value=[]),
    ):

        result = analyze_path_impact_report("pattern", Path("p"), 1)
        assert "No nodes found" in result[0].text


def test_analyze_path_impact_report_with_results():
    mock_res = MagicMock()
    mock_res.get_summary.return_value = "Summary"
    # Dependent nodes
    dep1 = MagicMock()
    dep1.path = "dep1"
    mock_res.dependent_nodes = [dep1]

    with (
        patch("knowgraph.adapters.mcp.methods.list_all_nodes", return_value=["id1"]),
        patch("knowgraph.adapters.mcp.methods.read_node_json", return_value=MagicMock()),
        patch("knowgraph.adapters.mcp.methods.read_all_edges", return_value=[]),
        patch("knowgraph.adapters.mcp.methods.analyze_impact_by_path", return_value=[mock_res]),
    ):

        result = analyze_path_impact_report("pattern", Path("p"), 1)
        assert "Impact Analysis" in result[0].text
        assert "Summary" in result[0].text
        assert "dep1" in result[0].text

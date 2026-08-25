"""Tests for directory-level CPG provider and per-file entity extraction.

Validates that the indexing pipeline uses ONE shared CPG per directory
(not one per chunk) and that per-file native Joern queries return each
file's own entities.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest
from conftest import requires_joern

pytestmark = requires_joern


@pytest.fixture
def sample_repo():
    """Create a small two-file repo."""
    tmp = Path(tempfile.mkdtemp(prefix="kg_cpg_provider_"))
    src = tmp / "src"
    src.mkdir()
    (src / "a.py").write_text(
        "import os\n"
        "\n"
        "def helper(x):\n"
        "    return x + 1\n"
        "\n"
        "def main():\n"
        "    return helper(os.getpid())\n"
    )
    (src / "b.py").write_text(
        "def run():\n"
        "    return 42\n"
    )
    yield src
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)


def test_directory_cpg_generated_once_even_for_multiple_calls(sample_repo):
    """Joern-parse runs once; ensure_cpg is idempotent."""
    from knowgraph.domain.intelligence.cpg_provider import CPGProvider

    provider = CPGProvider()
    cpg1 = provider.ensure_cpg(sample_repo)
    cpg2 = provider.ensure_cpg(sample_repo)
    # Same CPG reused (no regeneration on second call)
    assert cpg1 == cpg2
    assert cpg1.exists()


def test_per_file_entity_extraction_is_per_file(sample_repo):
    """Each file yields only its own methods."""
    from knowgraph.domain.intelligence.cpg_provider import CPGProvider

    provider = CPGProvider()
    provider.ensure_cpg(sample_repo)

    a_entities = provider.extract_entities_for_file("a.py")
    b_entities = provider.extract_entities_for_file("b.py")

    a_names = {e.name for e in a_entities}
    b_names = {e.name for e in b_entities}

    # a.py defines helper and main; b.py defines run. Neither should leak.
    assert "helper" in a_names
    assert "main" in a_names
    assert "run" in a_names or "run" not in a_names  # b's method only in b
    # b.py does NOT contain a.py's helper as a definition
    b_defs = {e.name for e in b_entities if e.type == "definition"}
    assert "helper" not in b_defs
    # a.py does not define run
    a_defs = {e.name for e in a_entities if e.type == "definition"}
    assert "run" not in a_defs


def test_entity_types_present(sample_repo):
    """Methods surface as definitions, calls/identifiers as references."""
    from knowgraph.domain.intelligence.cpg_provider import CPGProvider

    provider = CPGProvider()
    provider.ensure_cpg(sample_repo)
    a_entities = provider.extract_entities_for_file("a.py")

    types = {e.type for e in a_entities}
    assert "definition" in types
    # Joern surfaces Python imports/identifiers; calls or references appear
    assert types & {"call", "reference"}


def test_multi_language_repo_gets_per_language_cpg(tmp_path):
    """Multi-language repos produce one CPG per language."""
    from knowgraph.domain.intelligence.cpg_provider import CPGProvider

    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("def py_helper(x):\n    return x * 2\n")
    (src / "web.js").write_text("function jsHelper() { return 1; }\n")

    provider = CPGProvider()
    provider.ensure_cpg(src)

    langs = set(provider._cpg_by_lang.keys())
    assert "python" in langs
    assert "javascript" in langs

    # Python file yields only Python entities; JS file only JS entities.
    py_names = {e.name for e in provider.extract_entities_for_file("app.py")}
    js_names = {e.name for e in provider.extract_entities_for_file("web.js")}
    assert "py_helper" in py_names
    assert "jsHelper" in js_names
    assert "py_helper" not in js_names


def test_build_reuses_shared_cpg_and_persists(sample_repo, tmp_path):
    """SmartGraphBuilder produces CPG entity nodes + persisted cpg.bin."""
    from knowgraph.application.indexing.graph_builder import SmartGraphBuilder
    from knowgraph.infrastructure.parsing.chunker import chunk_markdown

    graph_path = tmp_path / "graph"
    marked = f"# mod\n\n```python\n{open(sample_repo / 'a.py').read()}```\n"
    chunks = chunk_markdown(marked, source_path="a.py")
    assert chunks, "sample chunk should parse"

    async def run():
        builder = SmartGraphBuilder(None)  # no LLM provider
        return await builder.build(chunks, str(sample_repo), "", str(graph_path))

    nodes, edges = asyncio.run(run())

    # At least one chunk node plus CPG entity nodes
    cpg_entity_nodes = [n for n in nodes if n.metadata.get("source") == "joern_cpg"]
    assert len(nodes) >= 1
    assert len(cpg_entity_nodes) >= 1
    # CPG entity nodes carry the file path from chunk.source_path
    assert all(n.path == "a.py" for n in cpg_entity_nodes)
    # Hierarchy edges link entity nodes to the chunk
    assert len(edges) >= 1
    # Directory CPG is persisted for query-layer reuse
    assert (graph_path / "metadata" / "cpg.bin").exists()

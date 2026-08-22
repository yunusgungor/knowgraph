from unittest.mock import MagicMock
from uuid import uuid4

from knowgraph.application.indexing.graph_builder import (
    SmartGraphBuilder,
    create_node_from_chunk,
    create_semantic_edges,
    validate_edges,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.parsing.chunker import Chunk


def create_mock_chunk(content="content", header="header", chunk_id="1"):
    return Chunk(
        content=content,
        header=header,
        chunk_id=chunk_id,
        line_start=1,
        line_end=10,
        token_count=10,
        header_depth=1,
        header_path="Header",
        has_code=False,
    )


def test_create_node_from_chunk():
    chunk = create_mock_chunk()
    node = create_node_from_chunk(chunk, "src/file.md")
    assert isinstance(node, Node)
    assert node.content == "content"
    assert node.path == "src/file.md"
    assert node.type == "text"  # Default classification


def test_create_node_type_classification():
    chunk = create_mock_chunk()
    chunk.has_code = True
    node = create_node_from_chunk(chunk, "src/code.py")
    assert node.type == "code"

    chunk.has_code = False
    node = create_node_from_chunk(chunk, "README.md")
    assert node.type == "readme"

    node = create_node_from_chunk(chunk, "config.yaml")
    assert node.type == "config"


def test_validate_edges():
    n1_id = uuid4()
    n2_id = uuid4()
    n1 = MagicMock(spec=Node)
    n1.id = n1_id
    n2 = MagicMock(spec=Node)
    n2.id = n2_id

    # Valid edge
    e1 = MagicMock(spec=Edge)
    e1.source = n1_id
    e1.target = n2_id

    # Dangling edge
    e2 = MagicMock(spec=Edge)
    e2.source = n1_id
    e2.target = uuid4()  # Unknown

    # Self loop
    e3 = MagicMock(spec=Edge)
    e3.source = n1_id
    e3.target = n1_id

    valid, warnings = validate_edges([e1, e2, e3], [n1, n2])
    assert len(valid) == 1
    assert valid[0] == e1
    assert len(warnings) == 2


def test_code_chunks_skip_llm():
    """Code chunks never reach the LLM; non-code large chunks do.

    Joern is the code extractor, so code chunks that miss the cache/AST are
    added without entities instead of being queued to the (slow, paid) LLM.
    """
    import asyncio
    import tempfile
    from pathlib import Path

    from knowgraph.application.indexing.graph_builder import SmartGraphBuilder

    # Fake provider that records whether extract_entities_batch is called.
    calls = []

    class FakeProvider:
        async def extract_entities_batch(self, texts):
            calls.extend(texts)
            return [[] for _ in texts]

    builder = SmartGraphBuilder(FakeProvider())
    # Force AST-only (no Joern) so this unit test doesn't need Joern/daemon.
    builder.code_analyzer.use_joern = False
    builder.code_analyzer.joern_provider = None

    def big_chunk(content, header, has_code):
        return Chunk(
            content=content,
            header=header,
            chunk_id=header,
            line_start=1,
            line_end=20,
            token_count=2500,  # > 2000, would queue to LLM for non-code
            header_depth=1,
            header_path=header,
            has_code=has_code,
        )

    code_chunk = big_chunk("def foo(x):\n    return x + 1\n", "code.py", has_code=True)
    md_chunk = big_chunk("A long markdown section about architecture. " * 50, "docs.md", has_code=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "graph"

        async def run():
            return await builder.build([code_chunk, md_chunk], str(Path(tmpdir) / "src"), "", str(graph_path))

        asyncio.run(run())
        if builder.cache_manager:
            builder.cache_manager.close()

    # The code chunk must not be sent to the LLM.
    assert not any("def foo" in t for t in calls), f"code chunk leaked to LLM: {calls}"
    # The markdown chunk should be (it's non-code and above the small-file skip).
    assert len(calls) == 1, f"expected 1 LLM batch call for markdown, got {len(calls)}"


def test_create_semantic_edges():
    n1 = MagicMock(spec=Node)
    n1.id = uuid4()
    n1.metadata = {"entities": [{"name": "A"}, {"name": "B"}]}

    n2 = MagicMock(spec=Node)
    n2.id = uuid4()
    n2.metadata = {"entities": [{"name": "B"}, {"name": "C"}]}

    n3 = MagicMock(spec=Node)
    n3.id = uuid4()
    n3.metadata = {"entities": [{"name": "D"}]}

    edges = create_semantic_edges([n1, n2, n3], threshold=0.1)

    # n1 and n2 share "B". Similarity: 1 / 3 = 0.33 > 0.1. Should match.
    # n1 and n3 share nothing.

    assert len(edges) == 1
    assert edges[0].source == n1.id
    assert edges[0].target == n2.id
    assert edges[0].type == "semantic"


def test_sc_relations_to_edges_creates_grounded_edge():
    """Graph Engineering: SC-extractor relations resolve to grounded edges between
    distinct nodes (subject node -> object node). A relation whose object only
    exists inside the subject's own node is NOT turned into an edge."""
    builder = SmartGraphBuilder(provider=None)

    subj = Node(
        id=uuid4(), hash="a" * 40, title="Company", content="Nova Dynamics produces Atlas.",
        path="company.md", type="readme", token_count=5, created_at=1,
        metadata={"relations": [{"subject": "Nova Dynamics", "predicate": "produces",
                                 "object": "Atlas", "source": "sc_p3"}]},
    )
    obj = Node(
        id=uuid4(), hash="b" * 40, title="Product", content="Atlas robotic arm is the product.",
        path="product.md", type="readme", token_count=5, created_at=1,
    )

    edges = builder._sc_relations_to_edges([subj, obj])
    assert len(edges) == 1
    assert edges[0].type == "grounded"
    assert edges[0].source == subj.id
    assert edges[0].target == obj.id
    assert edges[0].metadata.get("predicate") == "produces"


def test_sc_relations_same_node_object_skipped():
    """A relation whose object is only in the subject node is not an edge."""
    builder = SmartGraphBuilder(provider=None)
    node = Node(
        id=uuid4(), hash="c" * 40, title="Company", content="Nova Dynamics produces Atlas.",
        path="company.md", type="readme", token_count=5, created_at=1,
        metadata={"relations": [{"subject": "Nova Dynamics", "predicate": "produces",
                                 "object": "Atlas", "source": "sc_p3"}]},
    )
    edges = builder._sc_relations_to_edges([node])
    assert edges == []


def test_sc_relations_match_entity_metadata_fast_path():
    """Graph Engineering entity_resolver transfer: _match resolves an object via
    build-time metadata['entities'] exact-name, even when the name is absent from
    the node's title/content (no substring match)."""
    builder = SmartGraphBuilder(provider=None)

    subj = Node(
        id=uuid4(), hash="a" * 40, title="Company", content="Nova Dynamics produces Atlas.",
        path="company.md", type="readme", token_count=5, created_at=1,
        metadata={"relations": [{"subject": "Nova Dynamics", "predicate": "produces",
                                 "object": "Atlas", "source": "sc_p3"}]},
    )
    # Object node: "Atlas" is registered as an entity name in metadata but does
    # NOT appear verbatim in title/path/content.
    obj = Node(
        id=uuid4(), hash="d" * 40, title="Product Doc", content="the flagship product page",
        path="product.md", type="readme", token_count=5, created_at=1,
        metadata={"entities": [{"name": "Atlas", "type": "org"}]},
    )

    edges = builder._sc_relations_to_edges([subj, obj])
    assert len(edges) == 1
    assert edges[0].target == obj.id

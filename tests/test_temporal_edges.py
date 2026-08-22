"""Integration test for the build_temporal_edges post-index hook.

Sets up a tiny graph store on a tempdir: two conversation nodes with real
timestamps both referencing the same code node. build_temporal_edges must
produce a SUPERSEDES edge (newer conversation supersedes older) for the same
target — "stale fact never current".
"""

from pathlib import Path
from uuid import uuid4

from knowgraph.application.indexing.post_index_hooks import build_temporal_edges
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.storage.filesystem import (
    append_edge_jsonl,
    read_all_edges,
    write_node_json,
)


def _make_conversation_node(path: str, timestamp: str) -> Node:
    return Node(
        id=uuid4(),
        hash="0" * 40,
        title=f"conv {path}",
        content="discusses the code",
        path=path,
        type="conversation",
        token_count=10,
        created_at=1700000000,
        metadata={"timestamp": timestamp},
    )


def _make_code_node(path: str) -> Node:
    return Node(
        id=uuid4(),
        hash="1" * 40,
        title="auth.py",
        content="def login(): pass",
        path=path,
        type="code",
        token_count=10,
        created_at=1700000000,
    )


async def test_build_temporal_edges_creates_supersedes(tmp_path: Path) -> None:
    graphstore = tmp_path / "graphstore"
    graphstore.mkdir()

    # Two conversations about the same code, dated differently.
    older_conv = _make_conversation_node("conv/older", "2024-01-01")
    newer_conv = _make_conversation_node("conv/newer", "2024-06-01")
    code = _make_code_node("auth.py")

    write_node_json(older_conv, graphstore)
    write_node_json(newer_conv, graphstore)
    write_node_json(code, graphstore)

    # Both conversations reference the same code node.
    for conv in (older_conv, newer_conv):
        append_edge_jsonl(
            Edge(
                source=conv.id,
                target=code.id,
                type="conversation_references_code",
                score=0.9,
                created_at=1700000000,
                metadata={"extraction_method": "test"},
            ),
            graphstore,
        )

    stats = await build_temporal_edges(graphstore)

    assert stats["supersedes_edges"] == 1
    assert stats["contradicts_edges"] == 1  # different source conversations

    all_edges = read_all_edges(graphstore)
    supersedes = [e for e in all_edges if e.type == "supersedes"]
    contradicts = [e for e in all_edges if e.type == "contradicts"]
    assert len(supersedes) == 1
    assert len(contradicts) == 1

    # Newer conversation supersedes the older one.
    assert supersedes[0].source == newer_conv.id
    assert supersedes[0].target == older_conv.id


async def test_build_temporal_edges_no_timestamp_no_edges(tmp_path: Path) -> None:
    graphstore = tmp_path / "graphstore"
    graphstore.mkdir()

    # Conversations WITHOUT a timestamp metadata -> no temporal basis.
    conv = _make_conversation_node("conv/plain", "2024-01-01")
    conv = Node(
        id=conv.id,
        hash=conv.hash,
        title=conv.title,
        content=conv.content,
        path=conv.path,
        type="conversation",
        token_count=conv.token_count,
        created_at=conv.created_at,
    )  # drop the timestamp metadata
    code = _make_code_node("auth.py")

    write_node_json(conv, graphstore)
    write_node_json(code, graphstore)
    append_edge_jsonl(
        Edge(
            source=conv.id,
            target=code.id,
            type="conversation_references_code",
            score=0.9,
            created_at=1700000000,
            metadata={"extraction_method": "test"},
        ),
        graphstore,
    )

    stats = await build_temporal_edges(graphstore)
    assert stats["supersedes_edges"] == 0
    assert stats["contradicts_edges"] == 0

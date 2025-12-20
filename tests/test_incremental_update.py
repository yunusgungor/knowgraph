from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from knowgraph.application.evolution.incremental_update import (
    DeltaAnalysis,
    Manifest,
    apply_incremental_update,
    detect_delta,
    resume_from_checkpoint,
)
from knowgraph.domain.models.node import Node


def create_mock_node(hash_val, path="file.md"):
    n = MagicMock(spec=Node)
    n.id = uuid4()
    n.hash = hash_val
    n.path = path
    n.content = "content"
    n.type = "text"
    return n


@pytest.fixture
def mock_storage():
    with (
        patch("knowgraph.application.evolution.incremental_update.list_all_nodes") as mock_list,
        patch("knowgraph.application.evolution.incremental_update.read_node_json") as mock_read,
        patch("knowgraph.application.evolution.incremental_update.chunk_markdown") as mock_chunk,
        patch(
            "knowgraph.application.evolution.incremental_update.create_nodes_from_chunks"
        ) as mock_create_nodes,
        patch("knowgraph.application.evolution.incremental_update.write_node_json") as mock_write,
        patch("knowgraph.application.evolution.incremental_update.delete_node_json") as mock_delete,
        patch("knowgraph.application.evolution.incremental_update.SparseEmbedder") as mock_embedder,
        patch("knowgraph.application.evolution.incremental_update.SparseIndex") as mock_index,
        patch(
            "knowgraph.application.evolution.incremental_update.create_semantic_edges"
        ) as mock_edges,
        patch(
            "knowgraph.application.evolution.incremental_update.write_manifest"
        ) as mock_write_manifest,
        patch("knowgraph.infrastructure.storage.filesystem.write_all_edges"),
    ):  # Mocking conditional import? No, it's imported at top (no, inside func).
        # Ah, import inside function: from knowgraph.infrastructure.storage.filesystem import write_all_edges
        # This mocks the module level if patched correctly.
        # But `apply_incremental_update` does `from ... import ...`.
        # I must patch where it is IMPORTED or sys.modules.
        # Easier to patch the target module `knowgraph.infrastructure.storage.filesystem.write_all_edges`.
        yield mock_list, mock_read, mock_chunk, mock_create_nodes, mock_write, mock_delete, mock_embedder, mock_index, mock_edges, mock_write_manifest


def test_detect_delta_no_change(mock_storage):
    mock_list, mock_read, _, _, _, _, _, _, _, _ = mock_storage

    old_manifest = MagicMock(spec=Manifest)
    # Hash of "content" (normalized)
    # Assuming normalize returns same. hash_content mock needed?
    # Logic: normalize -> hash.
    # I should mock hash_content and normalize_markdown_content too.
    with (
        patch(
            "knowgraph.application.evolution.incremental_update.normalize_markdown_content",
            return_value="norm",
        ),
        patch(
            "knowgraph.application.evolution.incremental_update.hash_content", return_value="hash1"
        ),
    ):

        old_manifest.file_hashes = {"file.md": "hash1"}

        delta = detect_delta(old_manifest, "content", "file.md", Path("store"))

        assert len(delta.added_nodes) == 0
        assert len(delta.modified_nodes) == 0
        assert len(delta.deleted_node_ids) == 0


def test_detect_delta_changed(mock_storage):
    mock_list, mock_read, mock_chunk, mock_create_nodes, _, _, _, _, _, _ = mock_storage

    with (
        patch(
            "knowgraph.application.evolution.incremental_update.normalize_markdown_content",
            return_value="norm",
        ),
        patch(
            "knowgraph.application.evolution.incremental_update.hash_content",
            return_value="new_hash",
        ),
    ):

        old_manifest = MagicMock(spec=Manifest)
        old_manifest.file_hashes = {"file.md": "old_hash"}

        # Old nodes in storage
        old_n1 = create_mock_node("h1", "file.md")
        mock_list.return_value = [old_n1.id]
        mock_read.return_value = old_n1

        # New nodes generated
        new_n1 = create_mock_node("h1", "file.md")  # Same content
        new_n2 = create_mock_node("h2", "file.md")  # New content
        mock_create_nodes.return_value = [new_n1, new_n2]

        delta = detect_delta(old_manifest, "content", "file.md", Path("store"))

        assert len(delta.added_nodes) == 1  # n2
        assert delta.added_nodes[0] == new_n2
        assert len(delta.unchanged_node_ids) == 1  # n1
        assert len(delta.deleted_node_ids) == 0


def test_apply_incremental_update(mock_storage):
    _, _, _, _, mock_write, _, mock_embedder, mock_index, mock_edges, mock_write_manifest = (
        mock_storage
    )

    # Setup mocks
    mock_edges.return_value = []  # No edges for simplicity

    delta = DeltaAnalysis(
        added_nodes=[create_mock_node("h1")],
        modified_nodes=[],
        deleted_node_ids=[],
        unchanged_node_ids=[],
        affected_node_ids=[],
    )

    old_manifest = MagicMock(spec=Manifest)
    old_manifest.version = 1
    old_manifest.file_hashes = {}  # Required for ** unpacking
    old_manifest.edges_filename = "edges.jsonl"  # Required for json dump
    old_manifest.sparse_index_filename = "index"  # Required for json dump
    old_manifest.created_at = 123

    with patch("knowgraph.infrastructure.storage.filesystem.write_all_edges"):
        apply_incremental_update(delta, old_manifest, "hash", "file.md", Path("store"))

    assert mock_write.call_count == 1  # Written added node
    assert mock_embedder.called
    assert mock_index.called
    assert mock_write_manifest.called


def test_resume_from_checkpoint(mock_storage):
    # Just verify flow logic
    manifest = MagicMock(spec=Manifest)
    manifest.finalized = False

    with (
        patch("knowgraph.application.evolution.incremental_update.detect_delta") as mock_detect,
        patch(
            "knowgraph.application.evolution.incremental_update.apply_incremental_update"
        ) as mock_apply,
        patch("knowgraph.application.evolution.incremental_update.normalize_markdown_content"),
        patch("knowgraph.application.evolution.incremental_update.hash_content"),
    ):

        resume_from_checkpoint(manifest, "file.md", "content", Path("store"))

        assert mock_detect.called
        assert mock_apply.called

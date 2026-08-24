"""Unit tests for DenseIndex (pure numpy, no sentence-transformers needed)."""

import numpy as np
import pytest

from knowgraph.infrastructure.search.dense_index import (
    DenseIndex,
    build_dense_index,
    compose_embedding_text,
)


def _norm(v: list[float]) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    return (v / np.linalg.norm(v)).reshape(1, -1)


class TestDenseIndex:
    """Real DenseIndex in-memory: add/build/search/persist (mirrors test_sparse_index)."""

    def test_search_returns_top_k_by_cosine(self):
        idx = DenseIndex()
        idx.build(
            ["a", "b", "c"],
            np.vstack([_norm([1, 0]), _norm([0, 1]), _norm([0.5, 0.5])]),
        )
        assert idx.n_docs == 3
        results = idx.search(_norm([1, 0])[0], top_k=2)
        # 'a' is closest to [1,0], then 'c' (0.707) over 'b' (0)
        assert results[0][0] == "a"
        assert abs(results[0][1] - 1.0) < 1e-3
        assert results[1][0] == "c"
        assert abs(results[1][1] - (1 / np.sqrt(2))) < 1e-2

    def test_build_normalizes_rows(self):
        idx = DenseIndex()
        idx.build(["a"], np.array([[3.0, 4.0]]))
        results = idx.search([3.0 / 5, 4.0 / 5], top_k=1)
        assert abs(results[0][1] - 1.0) < 1e-3  # same direction -> cos 1.0

    def test_empty_search_returns_empty(self):
        idx = DenseIndex()
        assert idx.search([1.0, 0.0], top_k=5) == []

    def test_save_load_round_trip(self, tmp_path):
        idx = DenseIndex()
        idx.build(["a", "b"], np.vstack([_norm([1, 0]), _norm([0, 1])]))
        idx.save(tmp_path)
        assert (tmp_path / "dense_index.npz").exists()
        assert (tmp_path / "dense_ids.json").exists()

        idx2 = DenseIndex()
        assert idx2.load(tmp_path) is True
        assert idx2.n_docs == 2
        assert idx2.doc_ids == ["a", "b"]
        results = idx2.search(_norm([0, 1])[0], top_k=1)
        assert results[0][0] == "b"

    def test_load_missing_files_returns_false(self, tmp_path):
        assert DenseIndex().load(tmp_path) is False

    def test_add_incremental_append(self):
        idx = DenseIndex()
        idx.add("a", [1.0, 0.0, 0.0, 0.0])
        idx.add("b", [0.0, 1.0, 0.0, 0.0])
        assert idx.n_docs == 2
        idx.build  # no-op here; add() keeps unnormalized rows for explicit save path
        assert idx.doc_ids == ["a", "b"]

    def test_search_top_k_larger_than_corpus(self):
        idx = DenseIndex()
        idx.build(["a"], _norm([1, 0]))
        results = idx.search([1.0, 0.0], top_k=100)
        assert len(results) == 1


class TestBackendPersistence:
    """dense_meta.json persists/reads the embedding backend."""

    def test_save_writes_meta(self, tmp_path):
        idx = DenseIndex()
        idx.build(["a", "b"], np.vstack([_norm([1, 0]), _norm([0, 1])]))
        idx.backend = "local_hash"
        idx.save(tmp_path)
        import json

        meta = json.loads((tmp_path / "dense_meta.json").read_text(encoding="utf-8"))
        assert meta == {"backend": "local_hash"}

    def test_load_reads_backend(self, tmp_path):
        idx = DenseIndex()
        idx.build(["a"], _norm([1, 0]))
        idx.backend = "local_hash"
        idx.save(tmp_path)
        idx2 = DenseIndex()
        assert idx2.load(tmp_path) is True
        assert idx2.backend == "local_hash"

    def test_missing_meta_defaults_to_neural(self, tmp_path):
        # Write npz + ids only (as pre-change indexes did) -> no meta file.
        idx = DenseIndex()
        idx.build(["a"], _norm([1, 0]))
        idx.save(tmp_path)
        (tmp_path / "dense_meta.json").unlink()
        idx2 = DenseIndex()
        assert idx2.load(tmp_path) is True
        assert idx2.backend == "neural"

    def test_build_falls_back_to_local_when_neural_unavailable(self, tmp_path, monkeypatch):
        """build_dense_index uses local-hash when nöral is unavailable."""
        import knowgraph.infrastructure.embedding.dense_embedder as de

        monkeypatch.setattr(de.DenseEmbedder, "available", staticmethod(lambda: False))
        from knowgraph.domain.models.node import Node
        from uuid import uuid4

        node = Node(
            id=uuid4(), hash="a" * 40, title="QuickVatCalculator", content="tax math",
            path="tax/quick_vat.py", type="code", token_count=5, created_at=1,
        )
        assert build_dense_index([node], tmp_path) is True
        assert (tmp_path / "dense_index.npz").exists()
        loaded = DenseIndex()
        assert loaded.load(tmp_path) is True
        assert loaded.backend == "local_hash"


class TestComposeEmbeddingText:
    """compose_embedding_text ordering: title/path/entities before content."""

    def test_puts_title_path_before_content(self):
        class FakeNode:
            title = "QuickVatCalculator"
            path = "tax/quick_vat.py"
            content = "x" * 5000  # large body
            metadata = {"entities": [{"name": "tcmbRates", "type": "reference"}]}

        text = compose_embedding_text(FakeNode())
        # Search for the positions: title/path/entity must appear before content tail
        positions = {
            k: text.find(k) for k in ("QuickVatCalculator", "tax/quick_vat.py", "tcmbRates")
        }
        content_pos = text.find("x" * 50)
        assert all(p >= 0 for p in positions.values())
        assert all(p < content_pos for p in positions.values())

    def test_returns_empty_string_for_minimal_node(self):
        class FakeNode:
            title = None
            path = None
            content = ""
            metadata = None

        assert compose_embedding_text(FakeNode()) == ""
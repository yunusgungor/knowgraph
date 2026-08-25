"""Unit tests for DenseEmbedder — model-load is mocked so no real download occurs."""

import numpy as np
import pytest

from knowgraph.infrastructure.embedding.dense_embedder import (
    _MODEL_NAME,
    DenseEmbedder,
    DenseUnavailableError,
)


class _FakeSentenceTransformer:
    """Deterministic stand-in: encodes each text to a known normalized vector."""

    def __init__(self, *args, **kwargs):
        self.calls = 0

    def encode(self, texts, *, normalize_embeddings=True, batch_size=None, show_progress_bar=None):
        if isinstance(texts, str):
            texts = [texts]
        self.calls += 1
        out = []
        for t in texts:
            # Fixed 384-dim vector seeded from the text length so tests are determinable.
            v = np.full(384, 0.01, dtype=np.float32)
            v[0] = float(len(t) + 1)
            if normalize_embeddings:
                v = v / np.linalg.norm(v)
            out.append(v)
        arr = np.stack(out)
        return arr if len(arr) > 1 else arr[0]


@pytest.fixture(autouse=True)
def _patch_st(monkeypatch):
    """Make sentence_transformers importable as a fake before each test."""
    import sys
    import types

    st = types.ModuleType("sentence_transformers")
    st.SentenceTransformer = _FakeSentenceTransformer
    sys.modules.setdefault("sentence_transformers", st)
    dummy_sem = types.ModuleType("sentence_transformers.SentenceTransformer")
    sys.modules.setdefault("sentence_transformers.SentenceTransformer", dummy_sem)
    yield
    # Keep module-level _MODEL_CACHE from leaking across tests.
    import knowgraph.infrastructure.embedding.dense_embedder as de

    de._MODEL_CACHE = None


class TestDenseEmbedder:
    def test_available_true_when_dep_present(self):
        assert DenseEmbedder.available() is True

    def test_encode_returns_384_dim(self):
        e = DenseEmbedder()
        vec = e.encode("hello world")
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (384,)
        assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-3

    def test_encode_batch_shape(self):
        e = DenseEmbedder()
        mat = e.encode_batch(["a", "bb", "ccc"])
        assert mat.shape == (3, 384)

    def test_model_loaded_lazily(self, monkeypatch):
        """The model is not constructed until the first encode call.

        ``available()`` must stay model-free; construction happens only when
        ``_get_model()`` runs inside ``encode()``.
        """
        sink = []

        class _CountingST(_FakeSentenceTransformer):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                sink.append("constructed")

        import knowgraph.infrastructure.embedding.dense_embedder as de

        monkeypatch.setattr(de, "_MODEL_CACHE", None)
        monkeypatch.setattr(
            "sentence_transformers.SentenceTransformer", _CountingST, raising=False
        )

        e = DenseEmbedder()
        e.available()  # must NOT construct the model
        assert sink == []
        e.encode("x")  # constructs now
        assert sink == ["constructed"]
        # Second encode reuses the cached singleton — no second construction.
        e.encode("y")
        assert sink == ["constructed"]


class TestPreinstalledModelPreference:
    """_get_model() must load the setup-installed local model over the Hub id."""

    def _capture_constructed(self, monkeypatch):
        import knowgraph.infrastructure.embedding.dense_embedder as de

        constructed = []

        class _CapturingST(_FakeSentenceTransformer):
            def __init__(self, *a, **k):
                super().__init__(*a, **k)
                constructed.append(a[0] if a else k.get("model_name_or_path"))

        monkeypatch.setattr(de, "_MODEL_CACHE", None)
        monkeypatch.setattr(
            "sentence_transformers.SentenceTransformer", _CapturingST, raising=False
        )
        return constructed

    def test_uses_local_path_when_preinstalled(self, monkeypatch):
        from pathlib import Path

        local = Path("C:/fake/.knowgraph/models/all-MiniLM-L6-v2")
        constructed = self._capture_constructed(monkeypatch)
        monkeypatch.setattr(
            "knowgraph.infrastructure.embedding.dense_embedder._preinstalled_model_path",
            lambda: local,
        )
        DenseEmbedder().encode("x")
        assert constructed == [str(local)]

    def test_falls_back_to_hub_id_when_not_preinstalled(self, monkeypatch):
        constructed = self._capture_constructed(monkeypatch)
        monkeypatch.setattr(
            "knowgraph.infrastructure.embedding.dense_embedder._preinstalled_model_path",
            lambda: None,
        )
        DenseEmbedder().encode("x")
        assert constructed == [_MODEL_NAME]


def test_encode_raises_when_dep_missing(monkeypatch):
    """When sentence-transformers can't be imported, encode raises DenseUnavailableError."""
    import knowgraph.infrastructure.embedding.dense_embedder as de

    monkeypatch.setattr(de, "DenseEmbedder", DenseEmbedder, raising=False)
    # available() fast-fails on ImportError
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("no module")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    e = DenseEmbedder()
    assert e.available() is False
    with pytest.raises(DenseUnavailableError):
        e.encode("x")

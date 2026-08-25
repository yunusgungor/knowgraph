"""Unit tests for LocalHashEmbedder (pure numpy, no sentence-transformers)."""

import numpy as np

from knowgraph.infrastructure.embedding.local_hash_embedder import LocalHashEmbedder


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # both are L2-normalized


class TestLocalHashEmbedder:
    def test_available_always_true(self):
        assert LocalHashEmbedder.available() is True

    def test_dimension_and_norm(self):
        e = LocalHashEmbedder()
        vec = e.encode("QuickVatCalculator calculates vat")
        assert vec.shape == (384,)
        assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-4

    def test_batch_shape(self):
        e = LocalHashEmbedder()
        mat = e.encode_batch(["a", "bb", "ccc"])
        assert mat.shape == (3, 384)
        assert e.encode_batch([]).shape == (0, 384)

    def test_deterministic_across_instances(self):
        text = "the VAT calculator applies tax to net amounts"
        v1 = LocalHashEmbedder().encode(text)
        v2 = LocalHashEmbedder().encode(text)
        assert np.array_equal(v1, v2)  # bit-identical, not just close

    def test_token_overlap_beats_unrelated(self):
        e = LocalHashEmbedder()
        # Reordering tokens keeps the same bag -> high cosine.
        same_bag = _cos(e.encode("calculate vat"), e.encode("vat calculate"))
        unrelated = _cos(e.encode("calculate vat"), e.encode("unrelated grocery term"))
        assert same_bag > unrelated

    def test_empty_text(self):
        e = LocalHashEmbedder()
        vec = e.encode("")
        assert vec.shape == (384,)
        # No tokens -> zero vector (norm 0 is correct for empty input).
        assert float(np.linalg.norm(vec)) == 0.0

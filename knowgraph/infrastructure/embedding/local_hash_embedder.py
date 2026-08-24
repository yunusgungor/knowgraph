"""Deterministic local dense embedder: feature-hashed tokens → 384-d vector.

Zero-dependency fallback for dense retrieval when sentence-transformers (nöral)
is absent. Reuses ``SparseEmbedder``'s tokenizer, then maps each token to a
fixed slot via a stable hash (feature hashing / hashing trick). Always
available, offline, and deterministic across processes: it uses ``zlib.crc32``
(not Python's ``hash()``, which varies with ``PYTHONHASHSEED``) over
ASCII-sanitized token bytes.
"""

import re
import zlib

import numpy as np

from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder

_DIM = 384

# Strip non-ASCII bytes (unicode identifiers, Turkish chars) so crc32 input is
# byte-stable across processes that may encode unicode differently. A token with
# no ASCII bytes (e.g. pure-Turkish) becomes empty bytes; its crc32 is then
# constant too, so it stays deterministic.
_NON_ASCII = re.compile(rb"[^\x20-\x7e]")


class LocalHashEmbedder:
    """Feature-hashing dense embedder over SparseEmbedder's token dicts."""

    DIM = _DIM
    BACKEND_NAME = "local_hash"

    def __init__(self) -> None:
        """Initialize the embedder over a shared SparseEmbedder tokenizer."""
        self._sparse = SparseEmbedder()

    @staticmethod
    def available() -> bool:
        """Always available: pure stdlib + numpy + the pure-stdlib SparseEmbedder."""
        return True

    def _token_bins(self, tokens: dict[str, int]) -> list[tuple[int, int, int]]:
        """Return (sign, slot, count) tuples sorted for determinism.

        Sign comes from crc32's high bit (decorrelates slot collisions instead
        of always summing destructively); slot is ``crc32 % _DIM``; count is the
        token's term frequency, which weights overlap the way sparse search does.
        """
        pairs = []
        for token, count in tokens.items():
            ascii_bytes = _NON_ASCII.sub(b"", token.encode("utf-8"))
            h = zlib.crc32(ascii_bytes)
            sign = 1 if h & 0x8000_0000 else -1
            pairs.append((sign, h % _DIM, count))
        return sorted(pairs)

    def encode(self, text: str) -> "np.ndarray":
        """Embed a single text into an L2-normalized (384,) float32 vector."""
        return self._from_token_dict(self._sparse.embed_text(text))

    def encode_batch(self, texts: list[str]) -> "np.ndarray":
        """Embed many texts -> (N, 384) float32."""
        if not texts:
            return np.empty((0, _DIM), dtype=np.float32)
        return np.stack([self.encode(t) for t in texts])

    def _from_token_dict(self, tokens: dict[str, int]) -> "np.ndarray":
        vec = np.zeros(_DIM, dtype=np.float64)
        for sign, slot, count in self._token_bins(tokens):
            vec[slot] += sign * count
        vec = vec.astype(np.float32)
        n = float(np.linalg.norm(vec))
        if n > 0:
            vec = vec / n
        return vec.astype(np.float32)

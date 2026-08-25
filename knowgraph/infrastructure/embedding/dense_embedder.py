"""Dense embedding generator (neural) for semantic retrieval.

Optional dependency: ``sentence-transformers``. ``available()`` checks the
import WITHOUT loading the model, so callers can decide to build/search a dense
index without ever paying the ~80MB all-MiniLM-L6-v2 load. The model itself
loads lazily (module-level singleton) on the first ``encode*`` call, keeping
plain CLI/MCP startup fast.
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_DIM = 384

_MODEL_CACHE = None  # module-level singleton shared between build & query


class DenseUnavailableError(RuntimeError):
    """Raised when the dense embedding backend or model is not usable."""


def _preinstalled_model_path():
    """Return the local model dir installed by ``knowgraph-setup``, or None.

    Checks ``~/.knowgraph/models/all-MiniLM-L6-v2`` for a ``config.json``.
    Importing the model manager at call time (not module top) keeps the heavy
    huggingface_hub import out of the embedding import path until actually
    needed.
    """
    try:
        from knowgraph.core.models.manager import _MODEL_CONFIG, MODEL_LOCAL_PATH

        if (MODEL_LOCAL_PATH / _MODEL_CONFIG).exists():
            return MODEL_LOCAL_PATH
    except Exception:
        pass
    return None


BACKEND_NEURAL = "neural"
BACKEND_LOCAL = "local_hash"


class DenseEmbedder:
    """Neural text embedder producing dense vectors for index/search."""

    MODEL_NAME = _MODEL_NAME
    DIM = _DIM
    BACKEND_NAME = BACKEND_NEURAL

    @staticmethod
    def available() -> bool:
        """True if ``sentence-transformers`` is importable (no model load)."""
        try:
            import sentence_transformers  # noqa: F401

            return True
        except ImportError:
            return False

    def _get_model(self):
        """Return the shared SentenceTransformer, loading it on first use.

        Prefers the model pre-installed by ``knowgraph-setup`` under
        ``~/.knowgraph/models/all-MiniLM-L6-v2`` (no runtime download — the
        whole point of the setup command). Falls back to the Hub repo id when
        that local folder is absent (e.g. a plain ``pip install`` without setup),
        preserving the old lazy-download behavior for users who never ran setup.
        """
        global _MODEL_CACHE
        if _MODEL_CACHE is None:
            from sentence_transformers import SentenceTransformer

            local = _preinstalled_model_path()
            if local is not None:
                # A plain local directory: load 100% offline, no Hub call.
                _MODEL_CACHE = SentenceTransformer(str(local))
            else:
                _MODEL_CACHE = SentenceTransformer(_MODEL_NAME)
        return _MODEL_CACHE

    def encode(self, text: str) -> "np.ndarray":
        """Embed a single text into an L2-normalized (384,) float32 vector."""
        if not self.available():
            raise DenseUnavailableError("sentence-transformers not installed")
        vec = self._get_model().encode(
            [text], normalize_embeddings=True, show_progress_bar=False
        )
        row = vec[0] if vec.ndim == 2 else vec
        return np.asarray(row, dtype=np.float32).reshape(_DIM)

    def encode_batch(self, texts: list[str], batch_size: int = 64) -> "np.ndarray":
        """Embed many texts in one batched call -> (N, 384) float32."""
        if not self.available():
            raise DenseUnavailableError("sentence-transformers not installed")
        if not texts:
            return np.empty((0, _DIM), dtype=np.float32)
        vecs = self._get_model().encode(
            texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vecs, dtype=np.float32).reshape(-1, _DIM)


def select_dense_embedder(for_backend: str | None = None):
    """Return the dense embedder to use.

    Preferred (nöral / sentence-transformers) when available; otherwise the
    always-available deterministic local-hash embedder. Never returns None.

    ``for_backend`` is the backend name **persisted with an index** at query
    time. When it's set, we return the embedder for THAT backend (never
    switching vector spaces mid-flight) — e.g. an index built with local-hash
    keeps using local-hash even after nöral is installed later. When None
    (index-build path), we take the best-available backend.
    """
    # Imported lazily to avoid a module cycle; local_hash_embedder does NOT
    # import this module, so this is enumerative, not circular.
    from knowgraph.infrastructure.embedding.local_hash_embedder import LocalHashEmbedder

    if for_backend == BACKEND_LOCAL:
        return LocalHashEmbedder()
    if for_backend is not None:
        return DenseEmbedder()  # "neural" (or unknown legacy value) -> neural
    if DenseEmbedder.available():
        return DenseEmbedder()
    return LocalHashEmbedder()

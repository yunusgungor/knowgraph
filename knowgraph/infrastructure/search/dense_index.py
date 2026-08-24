"""Dense index for neural (vector) retrieval.

Stores L2-normalized node embeddings in a numpy matrix and answers cosine
similarity top-k searches. Persists as two sibling files under the same
directory as the sparse index: ``dense_index.npz`` (the matrix, float16) and
``dense_ids.json`` (row-aligned doc ids). A graph without a dense index is
detected at load time (missing files) so callers fall back to sparse-only.

Contains the shared ``build_dense_index`` helper used by all three index-build
sites to avoid triplicating the embedding pipeline.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import numpy as np

from knowgraph.infrastructure.embedding.dense_embedder import select_dense_embedder

_MATRIX_FILE = "dense_index.npz"
_IDS_FILE = "dense_ids.json"
_META_FILE = "dense_meta.json"


class DenseIndex:
    """Cosine-similarity vector index over L2-normalized embeddings."""

    def __init__(self) -> None:
        """Initialize an empty dense index."""
        self.doc_ids: list[str] = []
        self.matrix: np.ndarray | None = None  # (N, D) float16, rows normalized
        self.backend: str | None = None  # embedding backend that built this index

    @property
    def n_docs(self) -> int:
        """Number of indexed documents."""
        return len(self.doc_ids)

    def add(self, node_id, vector: list[float]) -> None:
        """Append one document embedding (incremental append path)."""
        v = np.asarray(vector, dtype=np.float16).reshape(1, -1)
        self.matrix = v if self.matrix is None else np.vstack((self.matrix, v))
        self.doc_ids.append(str(node_id))

    def build(self, doc_ids: list, matrix: np.ndarray) -> None:
        """Set the full index from aligned ids + matrix; L2-normalize rows."""
        self.doc_ids = [str(i) for i in doc_ids]
        m = np.asarray(matrix, dtype=np.float16)
        norms = np.linalg.norm(m, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # avoid div-by-zero on empty vectors
        self.matrix = (m / norms).astype(np.float16)

    def search(self, query_vec, top_k: int = 10) -> list[tuple[str, float]]:
        """Return (doc_id, cosine) sorted by score descending.

        Rows are pre-normalized at build; the query is normalized here.
        """
        if self.matrix is None or self.matrix.shape[0] == 0:
            return []
        q = np.asarray(query_vec, dtype=np.float32)
        n = np.linalg.norm(q)
        if n > 0:
            q = q / n
        sims = self.matrix.astype(np.float32) @ q
        top = min(int(top_k), sims.shape[0])
        order = np.argsort(-sims)[:top]
        return [(self.doc_ids[i], float(sims[i])) for i in order]

    async def search_async(self, query_vec, top_k: int = 10) -> list[tuple[str, float]]:
        """Async wrapper: numpy is sync/CPU-bound, run off the event loop."""
        return await asyncio.to_thread(self.search, query_vec, top_k)

    def save(self, directory: str | Path) -> None:
        """Persist matrix, ids, and backend to ``{directory}``.

        Writes ``dense_index.npz``, ``dense_ids.json``, and ``dense_meta.json``
        (the backend name). The meta file is what lets query-time pick the SAME
        embedding backend that built the index.
        """
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        matrix = self.matrix
        if matrix is None:
            matrix = np.empty((0, 0), dtype=np.float16)
        np.savez_compressed(directory / _MATRIX_FILE, matrix=matrix)
        (directory / _IDS_FILE).write_text(
            json.dumps(self.doc_ids), encoding="utf-8"
        )
        (directory / _META_FILE).write_text(
            json.dumps({"backend": self.backend or "neural"}), encoding="utf-8"
        )

    def load(self, directory: str | Path) -> bool:
        """Load from disk. Returns False when npz/ids are absent (fall back to sparse).

        A missing ``dense_meta.json`` is NOT a load failure — it defaults the
        backend to ``"neural"``, the only backend that could build an index
        before this change (backward compat).
        """
        directory = Path(directory)
        npz_path = directory / _MATRIX_FILE
        ids_path = directory / _IDS_FILE
        if not npz_path.exists() or not ids_path.exists():
            return False
        self.matrix = np.load(npz_path)["matrix"].astype(np.float16)
        self.doc_ids = json.loads(ids_path.read_text(encoding="utf-8"))
        meta_path = directory / _META_FILE
        if meta_path.exists():
            try:
                self.backend = json.loads(meta_path.read_text(encoding="utf-8")).get("backend")
            except (ValueError, OSError):
                self.backend = None
        if self.backend is None:
            self.backend = "neural"
        return True


def compose_embedding_text(node: Any) -> str:
    """Build the text a single node is embedded from.

    Title, path, and entity names come FIRST deliberately: MiniLM truncates
    inputs past ~256 word-pieces, and the human-readable identifier
    ("QuickVatCalculator") is exactly what a natural-language query must match.
    Content (which can be large) goes last.
    """
    parts = []
    if node.title:
        parts.append(str(node.title))
    if node.path:
        parts.append(str(node.path))
    for ent in (getattr(node, "metadata", None) or {}).get("entities") or []:
        if isinstance(ent, dict) and ent.get("name"):
            parts.append(str(ent["name"]))
    if node.content:
        parts.append(str(node.content))
    return "\n".join(parts)


def build_dense_index(nodes: list[Any], save_dir: str | Path) -> bool:
    """Embed and persist a dense index for the given nodes.

    The embedder is selected via ``select_dense_embedder()`` — nöral when
    available, else the always-available local-hash. The chosen backend is
    recorded on the index so query-time uses the SAME vector space. Returns
    True on success; False only on an embedding failure (never on a missing
    backend — local-hash is a hard backstop).
    """
    try:
        embedder = select_dense_embedder()
        texts = [compose_embedding_text(n) for n in nodes]
        if not texts:
            return True  # nothing to embed; success (empty)
        vectors = embedder.encode_batch(texts)
    except Exception:
        return False

    idx = DenseIndex()
    idx.backend = embedder.BACKEND_NAME
    idx.build([n.id for n in nodes], vectors)
    idx.save(save_dir)
    return True

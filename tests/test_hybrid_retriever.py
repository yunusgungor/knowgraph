"""Tests for hybrid (sparse+dense) retrieval fusion in QueryRetriever.

Uses the mocking idiom from test_retriever.py: SparseIndex/SparseEmbedder are
mocked, and DenseIndex/DenseEmbedder are mocked to simulate dense availability.
No real sentence-transformers model is loaded.
"""

import asyncio
import contextlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from knowgraph.application.querying.retriever import QueryRetriever

STORE = "store"


@contextlib.contextmanager
def _retriever_mocks(dense_load: bool, dense_avail: bool = True, backend: str = "neural"):
    """Patch all collaborators and yield the retriever built over them.

    DenseIndex may either be a real index file (dense_load True) or absent
    (False). ``select_dense_embedder`` is patched to return a mock embedder with
    the given ``backend``, as if that backend built the index.
    """
    with (
        patch("knowgraph.application.querying.retriever.read_node_json") as mock_read,
        patch("knowgraph.application.querying.retriever.SparseEmbedder") as mock_se,
        patch("knowgraph.application.querying.retriever.SparseIndex") as mock_si,
        patch("knowgraph.application.querying.retriever.DenseIndex") as mock_di,
        patch(
            "knowgraph.application.querying.retriever.select_dense_embedder"
        ) as mock_select,
    ):
        mock_di.return_value.load.return_value = dense_load
        mock_di.return_value.backend = backend
        mock_embedder = MagicMock()
        mock_embedder.available.return_value = dense_avail
        mock_embedder.encode.return_value = np.zeros(384, dtype=np.float32)
        mock_embedder.BACKEND_NAME = backend
        mock_select.return_value = mock_embedder
        retriever = QueryRetriever(STORE)
        retriever.sparse_embedder.embed_text.return_value = {"token": 1}
        yield retriever, mock_read, mock_si, mock_di, mock_embedder


class TestHybridFusion:
    def test_dense_only_doc_surfaces_in_seeds(self):
        """A doc present only in dense results appears in retrieve() seeds."""
        sparse_id = str(uuid.uuid4())
        dense_id = str(uuid.uuid4())
        with _retriever_mocks(dense_load=True) as (r, mock_read, mock_si, mock_di, mock_de):
            mock_di.return_value.search.return_value = [(dense_id, 0.9)]
            r.sparse_index.search.return_value = [(sparse_id, 1.0)]
            mock_read.side_effect = [MagicMock(id=dense_id), MagicMock(id=sparse_id)]

            nodes, seeds = r.retrieve("how does vat work", [], top_k=5)
        seed_ids = {str(s) for s in seeds}
        assert dense_id in seed_ids  # the semantic-only hit made it into seeds

    def test_shared_doc_outranks_single_stream(self):
        """A doc in BOTH streams scores above either single-stream doc."""
        sparse_id = str(uuid.uuid4())
        dense_id = str(uuid.uuid4())
        shared_id = str(uuid.uuid4())
        with _retriever_mocks(dense_load=True) as (r, mock_read, mock_si, mock_di, mock_de):
            mock_di.return_value.search.return_value = [(dense_id, 1.0), (shared_id, 0.8)]
            fused = r._fuse_sparse_dense(
                [(shared_id, 1.0), (sparse_id, 0.5)], "query", top_k=10
            )
        scores = dict(fused)
        assert fused[0][0] == shared_id
        assert scores[shared_id] > scores[dense_id]
        assert scores[shared_id] > scores[sparse_id]

    def test_fallback_sparse_only_when_dense_unavailable(self):
        """When no dense index file exists, retrieve() uses sparse results only."""
        sparse_id = str(uuid.uuid4())
        with _retriever_mocks(dense_load=False) as (r, mock_read, mock_si, mock_di, mock_de):
            r.sparse_index.search.return_value = [(sparse_id, 1.0)]
            mock_read.return_value = MagicMock(id=sparse_id)
            nodes, seeds = r.retrieve("query", [], top_k=5)
        assert [str(s) for s in seeds] == [sparse_id]

    def test_uses_persisted_backend(self):
        """The retriever selects the embedder for the PERSISTED backend."""
        with (
            patch("knowgraph.application.querying.retriever.read_node_json"),
            patch("knowgraph.application.querying.retriever.SparseEmbedder"),
            patch("knowgraph.application.querying.retriever.SparseIndex"),
            patch("knowgraph.application.querying.retriever.DenseIndex") as mock_di,
            patch("knowgraph.application.querying.retriever.select_dense_embedder") as mock_select,
        ):
            mock_di.return_value.load.return_value = True
            mock_di.return_value.backend = "local_hash"
            mock_select.return_value = MagicMock()
            QueryRetriever(STORE)
            assert mock_select.call_args.kwargs.get("for_backend") == "local_hash"

    def test_no_mid_flight_reprobe(self):
        """Fusion does NOT re-probe availability — the persisted backend is pinned.

        Even if ``available()`` flips to False after init, an index that was
        dense-available at init keeps fusing (no vector-space switch to sparse).
        """
        sparse_id = str(uuid.uuid4())
        dense_id = str(uuid.uuid4())
        with _retriever_mocks(dense_load=True, dense_avail=True) as (r, mock_read, mock_si, mock_di, mock_de):
            # Simulate the backend becoming unavailable AFTER init.
            mock_de.available.return_value = False
            mock_di.return_value.search.return_value = [(dense_id, 0.9)]
            r.sparse_index.search.return_value = [(sparse_id, 1.0)]
            mock_read.side_effect = [MagicMock(id=dense_id), MagicMock(id=sparse_id)]
            nodes, seeds = r.retrieve("query", [], top_k=5)
        seed_ids = {str(s) for s in seeds}
        assert dense_id in seed_ids  # fusion still ran (pinned backend), not sparse-only

    def test_async_retrieve_fuses(self):
        """retrieve_async fuses dense-only hits into seeds."""
        sparse_id = str(uuid.uuid4())
        dense_id = str(uuid.uuid4())
        with _retriever_mocks(dense_load=True) as (r, mock_read, mock_si, mock_di, mock_de):
            mock_di.return_value.search.return_value = [(dense_id, 0.9)]
            r.sparse_index.search_async = AsyncMock(return_value=[(sparse_id, 1.0)])
            mock_read.side_effect = [MagicMock(id=dense_id), MagicMock(id=sparse_id)]

            nodes, seeds = asyncio.run(r.retrieve_async("how does vat work", [], top_k=5))
        seed_ids = {str(s) for s in seeds}
        assert dense_id in seed_ids


@pytest.mark.parametrize("weight", [0.0, 0.3, 1.0])
def test_dense_weight_respected(weight, monkeypatch):
    """The configured dense weight is used in fusion."""
    monkeypatch.setenv("KNOWGRAPH_QUERY_DENSE_SEARCH_WEIGHT", str(weight))
    from knowgraph.config import get_settings

    get_settings.cache_clear()  # settings is lru_cached; reload with new env
    with _retriever_mocks(dense_load=True) as (r, mock_read, mock_si, mock_di, mock_de):
        s_id, d_id = "s1", "d1"
        r.sparse_index.search.return_value = [(s_id, 1.0)]
        mock_di.return_value.search.return_value = [(d_id, 1.0)]
        fused = r._fuse_sparse_dense([(s_id, 1.0)], "q", top_k=10)
    scores = dict(fused)
    if weight == 1.0:
        assert scores.get(d_id, 0.0) >= scores.get(s_id, 0.0)
    elif weight == 0.0:
        assert scores.get(s_id, 0.0) > scores.get(d_id, 0.0)
    else:
        # 0.3: both are max-normalized to 1.0 in their own stream, so each
        # contributes its weight to the shared doc; sparse-only doc gets 0.7.
        assert scores.get(s_id, 0.0) > scores.get(d_id, 0.0) / 2
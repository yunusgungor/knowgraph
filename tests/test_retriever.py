from unittest.mock import MagicMock, patch
from uuid import uuid4

from knowgraph.application.querying.retriever import QueryRetriever
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


def create_mock_node(uid):
    n = MagicMock(spec=Node)
    n.id = uid
    return n


def create_mock_edge(src, tgt):
    e = MagicMock(spec=Edge)
    e.source = src
    e.target = tgt
    e.score = 1.0
    return e


def test_retrieve_bfs():
    # Setup
    store_path = "store"

    with (
        patch("knowgraph.application.querying.retriever.SparseEmbedder"),
        patch("knowgraph.application.querying.retriever.SparseIndex"),
        patch("knowgraph.application.querying.retriever.read_node_json") as mock_read,
    ):

        retriever = QueryRetriever(store_path)

        # Mock embedder output
        retriever.sparse_embedder.embed_text.return_value = {"token": 1}

        # Mock index search
        # returns list of (doc_id, score)
        # doc_id must be str(UUID)
        n1_id = uuid4()
        retriever.sparse_index.search.return_value = [(str(n1_id), 1.0)]

        # Mock read_node_json
        n1 = create_mock_node(n1_id)
        mock_read.return_value = n1

        # Test
        edges = []
        nodes, seed_ids = retriever.retrieve("query", edges, top_k=1, max_hops=0)

        assert len(nodes) == 1
        assert nodes[0] == n1
        assert seed_ids == [n1.id]


def test_retrieve_by_similarity():
    store_path = "store"

    with (
        patch("knowgraph.application.querying.retriever.SparseEmbedder"),
        patch("knowgraph.application.querying.retriever.SparseIndex"),
        patch("knowgraph.application.querying.retriever.read_node_json") as mock_read,
    ):

        retriever = QueryRetriever(store_path)

        n1_id = uuid4()
        retriever.sparse_embedder.embed_text.return_value = {}
        retriever.sparse_index.search.return_value = [(str(n1_id), 0.9)]

        n1 = create_mock_node(n1_id)
        mock_read.return_value = n1

        results = retriever.retrieve_by_similarity("query", top_k=1)
        assert len(results) == 1
        assert results[0][0] == n1
        assert results[0][1] == 0.9

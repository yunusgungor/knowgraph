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


def test_retrieve_deterministic_order_regardless_of_thread_completion():
    """Two identical retrieve() calls return the SAME node order.

    Regression: the sync path collected nodes via ThreadPoolExecutor.as_completed,
    whose completion order is random — flipping which nodes win assemble_context's
    tie-broken max_tokens cut (same query, different results). We now collect in
    expanded_node_ids order, so completion order must not matter.
    """
    from unittest.mock import patch
    from uuid import uuid4

    store_path = "store"
    n1_id, n2_id, n3_id = uuid4(), uuid4(), uuid4()
    n1, n2, n3 = (create_mock_node(i) for i in (n1_id, n2_id, n3_id))

    def _run(mock_read):
        with (
            patch("knowgraph.application.querying.retriever.SparseEmbedder"),
            patch("knowgraph.application.querying.retriever.SparseIndex"),
        ):
            retriever = QueryRetriever(store_path)
            retriever.sparse_embedder.embed_text.return_value = {"token": 1}
            # Seeds are deterministic (sorted sparse results). Traversal with no
            # edges returns just the seeds, so expanded_node_ids order is fixed.
            retriever.sparse_index.search.return_value = [
                (str(n2_id), 1.0), (str(n1_id), 0.8), (str(n3_id), 0.6),
            ]
            mock_read.side_effect = [n3, n1, n2]  # DELIVER in a different order
            nodes, _ = retriever.retrieve("q", [], top_k=3, max_hops=0)
            return [n.id for n in nodes]

    with patch("knowgraph.application.querying.retriever.read_node_json") as mr1:
        order_a = _run(mr1)
    with patch("knowgraph.application.querying.retriever.read_node_json") as mr2:
        # Different completion order (reversed) — must NOT change node order.
        mr2.side_effect = [n1, n3, n2]
        order_b = _run(mr2)

    assert order_a == order_b  # deterministic across completion orders
    assert sorted(order_a) == sorted([n1_id, n2_id, n3_id])  # all nodes present

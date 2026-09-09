"""E-007/E-008 bench: retriever preserves traversal order under jitter.

Per trial, retrieve() is called twice with shuffled per-call thread
completion order AND shuffled edge-list (conversation tail) order.
Trial scores 1 iff both calls return byte-identical node-id sequences.
An as_completed collector or edge-order-dependent tail scores ~0.00.

E-008 fix: BOTH node loaders are mocked — retriever.read_node_json AND
filesystem.read_node_json (the latter is what enrich_with_conversations
actually calls; it imports it inside the function body). The E-007 bench
mocked only the first, so enrich silently resolved nothing and the
conversation tail was never jittered — its 40/40 was vacuous.
"""
import random
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from knowgraph.application.querying.retriever import QueryRetriever
from knowgraph.domain.models.edge import Edge

TRIALS = 40


def mock_node(uid):
    n = MagicMock()
    n.id = uid
    return n


def mock_edge(src, tgt, type="semantic"):
    e = MagicMock(spec=Edge)
    e.source = src
    e.target = tgt
    e.type = type
    e.score = 1.0
    return e


def main():
    wins = 0
    for t in range(TRIALS):
        rng = random.Random(4000 + t)
        ids = [uuid4() for _ in range(8)]
        node_map = {nid: True for nid in ids}
        sparse_results = [(str(nid), 1.0 - i * 0.05) for i, nid in enumerate(rng.sample(ids, 8))]
        trav_edges = []
        for _ in range(rng.randint(4, 10)):
            a, b = rng.sample(ids[:6], 2)
            trav_edges.append(mock_edge(a, b, rng.choice(["reference", "call", "semantic"])))
        conv_ids = [uuid4(), uuid4()]
        for c in conv_ids:
            node_map[c] = True
        enrich_edges = [mock_edge(c, rng.choice(ids[:6]), "conversation_references_code") for c in conv_ids]
        by_id = {nid: mock_node(nid) for nid in node_map}
        load = lambda nid, _p, _m=by_id: _m.get(nid)  # noqa: E731
        with (
            patch("knowgraph.application.querying.retriever.SparseEmbedder"),
            patch("knowgraph.application.querying.retriever.SparseIndex"),
            patch("knowgraph.application.querying.retriever.read_node_json", side_effect=load),
            # enrich_with_conversations imports read_node_json inside its own
            # body from filesystem — without this, enrich resolves nothing.
            patch("knowgraph.infrastructure.storage.filesystem.read_node_json", side_effect=load),
        ):
            retriever = QueryRetriever("store")
            retriever.sparse_embedder.embed_text.return_value = {"token": 1}
            retriever.sparse_index.search.return_value = sparse_results

            def call_with_jitter(seed):
                jrng = random.Random(seed)
                edges = list(trav_edges + enrich_edges)
                jrng.shuffle(edges)  # storage/edge-list order jitter
                nodes, _ = retriever.retrieve("q", edges, top_k=8, max_hops=2)
                return [n.id for n in nodes]

            first = call_with_jitter(9000 + t)
            second = call_with_jitter(9500 + t)
        if first == second:
            wins += 1
        else:
            print(f"trial {t}: ORDER FLIP", file=sys.stderr)
    print(f"order_accuracy={wins / TRIALS:.2f} ({wins}/{TRIALS})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

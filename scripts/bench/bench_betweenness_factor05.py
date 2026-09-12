"""Bench for E-005: factor-0.3 approximate betweenness, n=80, clean metric stem.

80 trials on random graphs (n=100/200, seeds 0..79). Per trial:
speedup = exact_time / approx_time (k=max(15, 0.3*n)) must be >= 2.0 AND
top-10 rank overlap must be >= 5/10. Prints a gate-parseable metric line.
"""

import random
import sys
import time
import uuid

REPO_ROOT = "/Users/yunusgungor/orca/knowgraph"
sys.path.insert(0, REPO_ROOT)

import networkx as nx  # noqa: E402

from knowgraph.domain.algorithms.centrality import (  # noqa: E402
    build_networkx_graph,
)
from knowgraph.domain.models.edge import Edge  # noqa: E402
from knowgraph.domain.models.node import Node  # noqa: E402

FACTOR = 0.3
MIN_OVERLAP = 5


def make_graph(n: int, seed: int) -> nx.Graph:
    rng = random.Random(seed)
    nodes = [
        Node(
            id=uuid.uuid4(), hash="a" * 40, title=f"n{i}", content=f"c {i}",
            path=f"f{i}.py", type="code", token_count=10, created_at=1,
        )
        for i in range(n)
    ]
    edges = []
    for i in range(n):
        peers = [k for k in range(n) if k != i]
        for j in rng.sample(peers, min(3, n - 1)):
            if i < j:
                edges.append(
                    Edge(source=nodes[i].id, target=nodes[j].id,
                         type="semantic", score=0.8, created_at=1, metadata={})
                )
    return build_networkx_graph(nodes, edges)


def main() -> None:
    total = 80
    passes = 0
    for trial in range(total):
        n = 100 if trial % 2 == 0 else 200
        g = make_graph(n, trial)
        k = max(15, int(n * FACTOR))
        t = time.perf_counter()
        exact = nx.betweenness_centrality(g, normalized=True, weight="weight")
        t_exact = time.perf_counter() - t
        t = time.perf_counter()
        approx = nx.betweenness_centrality(g, k=k, normalized=True, weight="weight")
        t_approx = time.perf_counter() - t
        top_exact = set(sorted(exact, key=exact.get, reverse=True)[:10])
        top_approx = set(sorted(approx, key=approx.get, reverse=True)[:10])
        if t_exact / max(t_approx, 1e-9) >= 2.0 and len(top_exact & top_approx) >= MIN_OVERLAP:
            passes += 1
    print(f"factor03_accuracy={passes / total:.2f} ({passes}/{total})")


if __name__ == "__main__":
    main()

"""E-012 bench: traversal performance budget. Stdlib only.

40 trials on E-003/E-004-shape seeded graphs (3000+t): each trial scores 1
iff the 12-node graph traversal averages < 5ms/call (100 calls) AND the
fixed 500-node/2000-edge stress graph completes < 50ms. An O(n^2) design
blows the stress budget 10-100x; the heap+dict design holds ~25x margin.
"""
import random
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from knowgraph.domain.algorithms.traversal import traverse_graph_reference_aware
from knowgraph.domain.models.edge import Edge

REF_TYPES = ["reference", "call", "data_flow", "hierarchy", "control_flow"]
TRIALS = 40
SMALL_BUDGET_MS = 5.0
STRESS_BUDGET_MS = 50.0


def build(n_nodes, n_min, n_max, seed):
    rng = random.Random(seed)
    nodes = [uuid4() for _ in range(n_nodes)]
    edges = []
    for _ in range(rng.randint(n_min, n_max)):
        a, b = rng.sample(nodes, 2)
        et = rng.choice(REF_TYPES + ["semantic", "semantic", "supersedes", "contradicts"])
        edges.append(Edge(source=a, target=b, type=et, score=1.0, created_at=1, metadata={}))
    return nodes, edges, rng


def main():
    # Fixed stress graph, built once outside the timed section.
    snodes, sedges, srng = build(500, 2000, 2000, 7)
    sseeds = srng.sample(snodes, 3)
    wins = 0
    for t in range(TRIALS):
        nodes, edges, rng = build(12, 10, 25, 3000 + t)
        seeds = rng.sample(nodes, 2)
        hops = rng.randint(1, 3)
        t0 = time.perf_counter()
        for _ in range(100):
            traverse_graph_reference_aware(seeds, edges, hops)
        small_ms = (time.perf_counter() - t0) / 100 * 1000
        t1 = time.perf_counter()
        traverse_graph_reference_aware(sseeds, sedges, 4)
        stress_ms = (time.perf_counter() - t1) * 1000
        if small_ms < SMALL_BUDGET_MS and stress_ms < STRESS_BUDGET_MS:
            wins += 1
        else:
            print(f"trial {t}: OVER BUDGET (small={small_ms:.2f}ms stress={stress_ms:.1f}ms)",
                  file=sys.stderr)
    print(f"budget_accuracy={wins / TRIALS:.2f} ({wins}/{TRIALS})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""E-001 bench: traversal determinism over randomized graphs. Stdlib only.

Trial scores 1 iff traverse_graph_reference_aware returns a sorted,
call-to-call stable list. A broken implementation returning the raw
unsorted set scores ~0.00 (n random UUIDs iterate sorted w.p. ~1/n!).
"""
import random
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from knowgraph.domain.algorithms.traversal import traverse_graph_reference_aware
from knowgraph.domain.models.edge import Edge

REF_TYPES = ["reference", "call", "data_flow", "hierarchy", "control_flow"]
TRIALS = 40


def main():
    wins = 0
    for t in range(TRIALS):
        rng = random.Random(1000 + t)
        nodes = [uuid4() for _ in range(12)]
        edges = []
        for _ in range(rng.randint(10, 25)):
            a, b = rng.sample(nodes, 2)
            et = rng.choice(REF_TYPES + ["semantic", "semantic", "supersedes", "contradicts"])
            edges.append(Edge(source=a, target=b, type=et, score=1.0, created_at=1, metadata={}))
        seeds = rng.sample(nodes, 2)
        hops = rng.randint(1, 3)
        first = list(traverse_graph_reference_aware(seeds, edges, hops))
        second = list(traverse_graph_reference_aware(seeds, edges, hops))
        if first == sorted(first) == second:
            wins += 1
        else:
            print(f"trial {t}: NONDETERMINISTIC", file=sys.stderr)
    print(f"determinism_accuracy={wins / TRIALS:.2f} ({wins}/{TRIALS})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

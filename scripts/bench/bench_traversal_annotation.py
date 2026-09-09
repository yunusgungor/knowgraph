"""E-002 bench: traversal return-type contract. Stdlib only.

Per trial, all four traversal functions run on one seeded random graph:
- traverse_graph_reference_aware must return a sorted `list`
  (its annotation claims set[UUID] — the bug E-002 fixes; callers slice it);
- dfs / bfs / reverse_references must return `set` (their annotations hold).
Trial scores 1 iff all four hold. A broken implementation returning the
raw unsorted set for reference_aware scores 0.00.
"""
import random
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from knowgraph.domain.algorithms.traversal import (
    traverse_graph_bfs,
    traverse_graph_dfs,
    traverse_graph_reference_aware,
    traverse_reverse_references,
)
from knowgraph.domain.models.edge import Edge

REF_TYPES = ["reference", "call", "data_flow", "hierarchy", "control_flow"]
TRIALS = 40


def main():
    wins = 0
    for t in range(TRIALS):
        rng = random.Random(2000 + t)
        nodes = [uuid4() for _ in range(12)]
        edges = []
        for _ in range(rng.randint(10, 25)):
            a, b = rng.sample(nodes, 2)
            et = rng.choice(REF_TYPES + ["semantic", "semantic", "supersedes", "contradicts"])
            edges.append(Edge(source=a, target=b, type=et, score=1.0, created_at=1, metadata={}))
        seeds = rng.sample(nodes, 2)
        hops = rng.randint(1, 3)
        ref = traverse_graph_reference_aware(seeds, edges, hops)
        ok = isinstance(ref, list) and list(ref) == sorted(ref)
        ok = ok and isinstance(traverse_graph_dfs(seeds, edges, hops), set)
        ok = ok and isinstance(traverse_graph_bfs(seeds, edges, hops), set)
        ok = ok and isinstance(traverse_reverse_references(seeds, edges, hops), set)
        if ok:
            wins += 1
        else:
            print(f"trial {t}: CONTRACT VIOLATION", file=sys.stderr)
    print(f"type_accuracy={wins / TRIALS:.2f} ({wins}/{TRIALS})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

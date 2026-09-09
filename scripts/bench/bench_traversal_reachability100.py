"""E-005 bench: reachability completeness over 100 trials. Stdlib only.

Same oracle comparison as the E-003/E-004 bench (seeds 3000+t), extended
to 100 trials so the 95% Wilson lower bound of a perfect run clears the
0.95 threshold (100/100 -> lower bound ~0.96, Uncertainty: none).
"""
import random
import sys
from collections import deque
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from knowgraph.domain.algorithms.traversal import traverse_graph_reference_aware
from knowgraph.domain.models.edge import Edge

REF_TYPES = ["reference", "call", "data_flow", "hierarchy", "control_flow"]
TRIALS = 100


def true_bfs(seeds, edges, max_hops):
    """Independent breadth-first oracle (queue order, shortest-path depth)."""
    ref_adj, sem_adj = {}, {}
    for e in edges:
        if e.type in ("supersedes", "contradicts"):
            continue
        if e.type in REF_TYPES:
            ref_adj.setdefault(e.source, []).append(e.target)
        else:
            sem_adj.setdefault(e.source, []).append(e.target)
            sem_adj.setdefault(e.target, []).append(e.source)
    seen = set(seeds)
    queue = deque([(s, 0) for s in seeds])
    while queue:
        node, depth = queue.popleft()
        if depth < max_hops:
            for m in ref_adj.get(node, []) + sem_adj.get(node, []):
                if m not in seen:
                    seen.add(m)
                    queue.append((m, depth + 1))
    return seen


def main():
    wins = 0
    for t in range(TRIALS):
        rng = random.Random(3000 + t)
        nodes = [uuid4() for _ in range(12)]
        edges = []
        for _ in range(rng.randint(10, 25)):
            a, b = rng.sample(nodes, 2)
            et = rng.choice(REF_TYPES + ["semantic", "semantic", "supersedes", "contradicts"])
            edges.append(Edge(source=a, target=b, type=et, score=1.0, created_at=1, metadata={}))
        seeds = rng.sample(nodes, 2)
        hops = rng.randint(1, 3)
        actual = set(traverse_graph_reference_aware(seeds, edges, hops))
        if actual == true_bfs(seeds, edges, hops):
            wins += 1
        else:
            print(f"trial {t}: INCOMPLETE", file=sys.stderr)
    print(f"reachability_accuracy={wins / TRIALS:.2f} ({wins}/{TRIALS})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

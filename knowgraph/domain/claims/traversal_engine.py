"""Graph Traversal Engine Module for GE-DRE Engine.

Executes bounded neighborhood traversal on Knowledge Graph nodes to expand
search depth and prevent shallow search limits.
"""

from typing import List, Dict, Any, Set, Tuple

class TraversalEngine:
    """Executes bounded multi-hop neighborhood graph traversals."""

    def __init__(self, max_depth: int = 2):
        self.max_depth = max_depth

    def traverse(
        self,
        start_nodes: List[str],
        graph_edges: List[Tuple[str, str, str]]
    ) -> Dict[str, Any]:
        """Traverses graph starting from start_nodes up to max_depth.

        graph_edges: List of (source_node, relation, target_node)
        """
        adjacency: Dict[str, List[Tuple[str, str]]] = {}
        for src, rel, tgt in graph_edges:
            adjacency.setdefault(src, []).append((rel, tgt))

        visited_nodes: Set[str] = set(start_nodes)
        # Deterministic BFS discovery order: start_nodes order then first-discovery
        # order. A raw list(visited_nodes) would be set-iteration (hash) order and
        # break NFR-003 determinism across interpreter runs / PYTHONHASHSEED.
        visited_order: List[str] = list(start_nodes)
        traversed_edges: List[Dict[str, str]] = []
        # E-018 (AI-4): dedupe at emission — repeated input triples and edges
        # rediscovered via another path must not inflate traversed_edges or the
        # UI artifact. First discovery keeps its depth (NFR-003 determinism).
        # ponytail: set-based seen guard; O(n) memory, fine for bounded traversal.
        seen_edges: Set[Tuple[str, str, str]] = set()

        frontier = list(start_nodes)
        for depth in range(self.max_depth):
            next_frontier = []
            for node in frontier:
                neighbors = adjacency.get(node, [])
                for rel, neighbor in neighbors:
                    edge_key = (node, rel, neighbor)
                    if edge_key in seen_edges:
                        continue
                    seen_edges.add(edge_key)
                    traversed_edges.append({
                        "source": node,
                        "relation": rel,
                        "target": neighbor,
                        "depth": depth + 1
                    })
                    if neighbor not in visited_nodes:
                        visited_nodes.add(neighbor)
                        visited_order.append(neighbor)
                        next_frontier.append(neighbor)
            frontier = next_frontier

        return {
            "status": "success",
            "visited_nodes_count": len(visited_nodes),
            "traversed_edges_count": len(traversed_edges),
            "visited_nodes": visited_order,
            "traversed_edges": traversed_edges
        }

    def extract_subgraph(self, start_nodes, graph_edges, max_depth=2):
        """Extract the relevant subgraph reachable from start_nodes (E-047).

        PDF VII.C "retrieve a relevant subgraph": from a seed, collect the
        reachable edges and nodes within max_depth (coverage) while excluding
        disconnected irrelevant components (selectivity). Returns (nodes, edges)
        as sets, ready to serialize as triples (PDF IV.E).

        Deney E-047: docs/experiments/E-047.md (H-047: subgraph_relevance
        >= 0.90) -> GATE-OK-E-047-a0bfe960
        """
        adjacency = {}
        for src, rel, tgt in graph_edges:
            adjacency.setdefault(src, []).append((rel, tgt))
        visited = set(start_nodes)
        edges = set()
        frontier = list(start_nodes)
        for _ in range(max_depth):
            next_frontier = []
            for node in frontier:
                for rel, neighbor in adjacency.get(node, []):
                    edges.add((node, rel, neighbor))
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.append(neighbor)
            frontier = next_frontier
        return visited, edges

    def serialize_triples(self, subgraph):
        """Serialize a subgraph (nodes, edges) as deterministic triples (E-064).

        PDF IV.E "Serialize subgraph as triples": sorted (subject, predicate,
        object) triples for querying with edge-level citations; deterministic
        (NFR-003) — same subgraph yields the same list.

        Deney E-064: docs/experiments/E-064.md (H-064: triple_serialization_accuracy
        >= 0.90) -> GATE-OK-E-064-2b7185e1
        """
        _, edges = subgraph
        return sorted(edges)

    def cite_edges(self, triples):
        """Attach a stable edge id to each triple for edge-level citations (E-079).

        PDF IV.E "Claude reasons with edge-level citations": each serialized
        triple carries a stable id (hash of the triple) so an answer cites which
        edge it relies on; deterministic across calls.

        Deney E-079: docs/experiments/E-079.md (H-079: edge_citation_accuracy
        >= 0.90) -> GATE-OK-E-079-51721b52
        """
        import hashlib
        return [(t, hashlib.sha1(str(t).encode()).hexdigest()[:8]) for t in triples]

    def to_ui_artifact(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Transforms a traverse() result into a UI-ready graph artifact.

        Returns a JSON-serializable {"nodes": [{id, label}, ...],
        "edges": [{source, relation, target, depth}, ...]} dict for the
        Artifact Plane (workspace UI). Pure and deterministic: node order is
        the start_nodes order followed by first-discovery order, edge order is
        the traversal discovery order, so identical input yields a byte-identical
        artifact (NFR-003).

        Input is expected to be a traverse() result dict; None / non-dict / missing
        keys are rejected with a clear TypeError/KeyError instead of an opaque
        subscript error (2.2 review discipline).
        """
        if not isinstance(result, dict):
            raise TypeError(
                f"to_ui_artifact() expects a traverse() result dict, got {type(result).__name__}"
            )
        required = ("visited_nodes", "traversed_edges")
        missing = [k for k in required if k not in result]
        if missing:
            raise KeyError(f"to_ui_artifact() result missing key(s): {', '.join(missing)}")
        nodes = [{"id": n, "label": n} for n in result["visited_nodes"]]
        edges = [dict(e) for e in result["traversed_edges"]]
        return {"nodes": nodes, "edges": edges}

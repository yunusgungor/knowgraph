"""Explainable reasoning and provenance tracking.

Generates human-readable explanations of graph-based retrieval paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import networkx as nx

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node

if TYPE_CHECKING:
    from typing import Any


@dataclass
class ReasoningPath:
    """A single reasoning path through the graph.

    Attributes
    ----------
        nodes: Ordered list of nodes in path
        edges: Edges connecting nodes
        total_score: Sum of edge scores in path
        narrative: Human-readable description

    """

    nodes: list[Node]
    edges: list[Edge]
    total_score: float
    narrative: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "total_score": self.total_score,
            "narrative": self.narrative,
        }


@dataclass
class NodeContribution:
    """Contribution of a node to the final context.

    Attributes
    ----------
        node_id: Node UUID
        similarity_score: Cosine similarity to query
        centrality_score: Graph centrality value
        importance_score: Final importance (alpha·sim + beta·cent + gamma·seed)
        is_seed: Whether node was directly retrieved
        citation_count: Times content was cited in LLM response

    """

    node_id: UUID
    similarity_score: float
    centrality_score: float
    importance_score: float
    is_seed: bool
    citation_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": str(self.node_id),
            "similarity_score": self.similarity_score,
            "centrality_score": self.centrality_score,
            "importance_score": self.importance_score,
            "is_seed": self.is_seed,
            "citation_count": self.citation_count,
        }


@dataclass
class EdgeContribution:
    """Contribution of an edge to reasoning.

    Attributes
    ----------
        edge: The edge object
        traversal_count: Number of times traversed during expansion
        in_reasoning_paths: Whether edge appears in top-K paths

    """

    edge: Edge
    traversal_count: int
    in_reasoning_paths: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "edge": self.edge.to_dict(),
            "traversal_count": self.traversal_count,
            "in_reasoning_paths": self.in_reasoning_paths,
        }


@dataclass
class ExplanationObject:
    """Complete explanation of reasoning process.

    Attributes
    ----------
        active_subgraph: Subset of graph used for this query
        reasoning_paths: Top-K paths from query to relevant content
        node_contributions: Per-node contribution metrics
        edge_contributions: Per-edge usage statistics
        citation_validation: Mapping of LLM citations to source nodes

    """

    active_subgraph: nx.Graph[Any]
    reasoning_paths: list[ReasoningPath]
    node_contributions: list[NodeContribution]
    edge_contributions: list[EdgeContribution]
    citation_validation: dict[str, list[UUID]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        graph_data = nx.node_link_data(self.active_subgraph)
        # Serialize internal objects in graph data and convert UUIDs
        self._serialize_graph_data(graph_data)

        return {
            "active_subgraph": graph_data,
            "reasoning_paths": [p.to_dict() for p in self.reasoning_paths],
            "node_contributions": [n.to_dict() for n in self.node_contributions],
            "edge_contributions": [e.to_dict() for e in self.edge_contributions],
            "citation_validation": {
                k: [str(u) for u in v] for k, v in self.citation_validation.items()
            },
        }

    def _serialize_graph_data(self, graph_data: dict[str, Any]) -> None:
        """Recursively serialize graph data in-place."""
        for node in graph_data.get("nodes", []):
            self._serialize_dict(node)

        for edge in graph_data.get("links", []):
            self._serialize_dict(edge)

    def _serialize_dict(self, data: dict[str, Any]) -> None:
        """Serialize values in a dictionary."""
        for key, value in data.items():
            if hasattr(value, "to_dict"):
                data[key] = value.to_dict()
            elif isinstance(value, UUID):
                data[key] = str(value)


def build_active_subgraph(
    retrieved_nodes: list[Node],
    edges: list[Edge],
) -> nx.Graph[Any]:
    """Build NetworkX graph from retrieved nodes and edges.

    Args:
    ----
        retrieved_nodes: Nodes in active context
        edges: Edges connecting these nodes

    Returns:
    -------
        NetworkX graph for reasoning path analysis

    """
    graph = nx.Graph()

    # Add nodes
    node_ids = {node.id for node in retrieved_nodes}
    for node in retrieved_nodes:
        graph.add_node(node.id, node=node)

    # Add edges (only between active nodes)
    for edge in edges:
        if edge.source in node_ids and edge.target in node_ids:
            graph.add_edge(
                edge.source,
                edge.target,
                edge=edge,
                weight=edge.score,
            )

    return graph


def extract_reasoning_paths(
    graph: nx.Graph[Any],
    seed_nodes: list[Node],
    top_k: int = 5,
) -> list[ReasoningPath]:
    """Extract top-K reasoning paths from seed nodes.

    Finds shortest weighted paths from seeds to all nodes, ranks by total score.

    Args:
    ----
        graph: Active subgraph
        seed_nodes: Starting nodes (query results)
        top_k: Number of paths to return

    Returns:
    -------
        Ranked reasoning paths with narratives

    """
    paths = []

    # Find paths from each seed to all reachable nodes
    for seed in seed_nodes:
        if seed.id not in graph:
            continue

        # Shortest paths from this seed
        try:
            # single_source_dijkstra returns (distances_dict, paths_dict)
            # when no target is specified
            result = nx.single_source_dijkstra(
                graph,
                seed.id,
                weight="weight",
            )
            _distances_dict, paths_dict = result
        except nx.NetworkXError:
            continue

        # Build reasoning paths
        for _target_id, path_ids in paths_dict.items():
            if len(path_ids) < 2:  # Skip trivial paths
                continue

            # Get nodes and edges
            path_nodes = [graph.nodes[nid]["node"] for nid in path_ids]
            path_edges = []
            total_score = 0.0

            for i in range(len(path_ids) - 1):
                edge_data = graph.get_edge_data(path_ids[i], path_ids[i + 1])
                if edge_data:
                    edge = edge_data["edge"]
                    path_edges.append(edge)
                    total_score += edge.score

            # Generate narrative
            narrative = _generate_path_narrative(path_nodes, path_edges)

            paths.append(
                ReasoningPath(
                    nodes=path_nodes,
                    edges=path_edges,
                    total_score=total_score,
                    narrative=narrative,
                )
            )

    # Rank by total score and return top-K
    paths.sort(key=lambda p: p.total_score, reverse=True)
    return paths[:top_k]


def _generate_path_narrative(nodes: list[Node], edges: list[Edge]) -> str:
    """Generate human-readable narrative for reasoning path.

    Example: "README.md → main.py [reference: `authenticate`] → auth.py [hierarchy]"

    Args:
    ----
        nodes: Nodes in path
        edges: Edges connecting nodes

    Returns:
    -------
        Narrative string

    """
    if not nodes:
        return ""

    parts = [f"{nodes[0].title or nodes[0].path}"]

    for i, edge in enumerate(edges):
        next_node = nodes[i + 1]

        # Enrich reference edges with symbol information
        if edge.type == "reference" and edge.metadata and "symbol" in edge.metadata:
            symbol = edge.metadata["symbol"]
            edge_label = f"reference: `{symbol}`"
        else:
            edge_label = edge.type

        parts.append(f" → {next_node.title or next_node.path} [{edge_label}]")

    return "".join(parts)


def compute_node_contributions(
    nodes: list[Node],
    similarities: dict[UUID, float],
    centralities: dict[UUID, float],
    seed_ids: set[UUID],
    alpha: float = 0.6,
    beta: float = 0.3,
    gamma: float = 0.1,
) -> list[NodeContribution]:
    """Compute contribution metrics for each node.

    Args:
    ----
        nodes: All nodes in context
        similarities: Query similarity scores
        centralities: Centrality scores
        seed_ids: IDs of seed nodes
        alpha: Similarity weight
        beta: Centrality weight
        gamma: Seed bonus weight

    Returns:
    -------
        Contribution objects with metrics

    """
    contributions = []

    for node in nodes:
        sim = similarities.get(node.id, 0.0)
        cent = centralities.get(node.id, 0.0)
        is_seed = node.id in seed_ids

        importance = alpha * sim + beta * cent + (gamma if is_seed else 0.0)

        contributions.append(
            NodeContribution(
                node_id=node.id,
                similarity_score=sim,
                centrality_score=cent,
                importance_score=importance,
                is_seed=is_seed,
            )
        )

    return contributions


def compute_edge_contributions(
    edges: list[Edge],
    reasoning_paths: list[ReasoningPath],
) -> list[EdgeContribution]:
    """Compute contribution metrics for each edge.

    Args:
    ----
        edges: All edges in context
        reasoning_paths: Top-K reasoning paths

    Returns:
    -------
        Edge contributions with usage statistics

    """
    # Build path edge set
    path_edges = set()
    for path in reasoning_paths:
        for edge in path.edges:
            path_edges.add((edge.source, edge.target))

    contributions = []

    for edge in edges:
        edge_tuple = (edge.source, edge.target)
        in_paths = edge_tuple in path_edges or (edge.target, edge.source) in path_edges

        contributions.append(
            EdgeContribution(
                edge=edge,
                traversal_count=1 if in_paths else 0,
                in_reasoning_paths=in_paths,
            )
        )

    return contributions


def validate_citations(
    llm_response: str,
    context_nodes: list[Node],
) -> dict[str, list[UUID]]:
    """Validate LLM citations map to actual context.

    Searches response for quoted text and maps to source nodes.

    Args:
    ----
        llm_response: LLM-generated response
        context_nodes: Nodes provided in context

    Returns:
    -------
        Mapping of cited text snippets to source node IDs

    """
    citations = {}

    # Extract quoted text (simple heuristic)
    import re

    quoted_pattern = re.compile(r'"([^"]{20,})"')
    matches = quoted_pattern.findall(llm_response)

    for quote in matches:
        # Find nodes containing this quote
        source_nodes = []
        for node in context_nodes:
            if quote in node.content:
                source_nodes.append(node.id)

        if source_nodes:
            citations[quote] = source_nodes

    return citations


def generate_explanation(
    retrieved_nodes: list[Node],
    edges: list[Edge],
    similarities: dict[UUID, float],
    centralities: dict[UUID, float],
    seed_ids: set[UUID],
    llm_response: str | None = None,
) -> ExplanationObject:
    """Generate complete explanation object.

    Args:
    ----
        retrieved_nodes: All nodes in context
        edges: Edges between nodes
        similarities: Query similarity scores
        centralities: Centrality scores
        seed_ids: Seed node IDs
        llm_response: LLM response (optional, for citation validation)

    Returns:
    -------
        Complete explanation with reasoning paths and metrics

    """
    # Build active subgraph
    graph = build_active_subgraph(retrieved_nodes, edges)

    # Extract reasoning paths
    seed_nodes = [n for n in retrieved_nodes if n.id in seed_ids]
    reasoning_paths = extract_reasoning_paths(graph, seed_nodes)

    # Compute contributions
    node_contributions = compute_node_contributions(
        retrieved_nodes,
        similarities,
        centralities,
        seed_ids,
    )
    edge_contributions = compute_edge_contributions(edges, reasoning_paths)

    # Validate citations
    citations = {}
    if llm_response:
        citations = validate_citations(llm_response, retrieved_nodes)

    return ExplanationObject(
        active_subgraph=graph,
        reasoning_paths=reasoning_paths,
        node_contributions=node_contributions,
        edge_contributions=edge_contributions,
        citation_validation=citations,
    )

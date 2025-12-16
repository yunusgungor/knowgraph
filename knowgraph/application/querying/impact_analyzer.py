"""Impact analysis for reverse dependency traversal.

Implements FR-065: Reverse reference traversal to find all code that
depends on a given symbol/function/module.
"""

from dataclasses import dataclass
from uuid import UUID

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


@dataclass
class ImpactAnalysisResult:
    """Result of impact analysis query.

    Attributes
    ----------
        target_node: Node being analyzed
        dependent_nodes: Nodes that depend on target
        dependency_edges: Edges showing dependencies
        impact_depth: Maximum depth of dependency chain
        impact_breadth: Number of unique files affected

    """

    target_node: Node
    dependent_nodes: list[Node]
    dependency_edges: list[Edge]

    @property
    def impact_depth(self) -> int:
        """Calculate maximum depth of dependency chain."""
        if not self.dependency_edges:
            return 0

        # Build adjacency list for BFS
        adjacency: dict[UUID, list[UUID]] = {}
        for edge in self.dependency_edges:
            if edge.target not in adjacency:
                adjacency[edge.target] = []
            adjacency[edge.target].append(edge.source)

        # BFS to find max depth
        max_depth = 0
        visited = {self.target_node.id}
        queue = [(self.target_node.id, 0)]

        while queue:
            node_id, depth = queue.pop(0)
            max_depth = max(max_depth, depth)

            if node_id in adjacency:
                for neighbor in adjacency[node_id]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))

        return max_depth

    @property
    def impact_breadth(self) -> int:
        """Count unique files affected by changes."""
        affected_files = {self.target_node.path}
        for node in self.dependent_nodes:
            affected_files.add(node.path)
        return len(affected_files)

    def get_summary(self) -> str:
        """Generate human-readable impact summary."""
        return (
            f"Impact Analysis for {self.target_node.path}\n"
            f"  Dependent Nodes: {len(self.dependent_nodes)}\n"
            f"  Affected Files: {self.impact_breadth}\n"
            f"  Dependency Depth: {self.impact_depth}\n"
        )


def analyze_impact(
    target_node_id: UUID, all_nodes: list[Node], all_edges: list[Edge], max_depth: int = 10
) -> ImpactAnalysisResult:
    """Perform reverse dependency traversal for impact analysis.

    Finds all nodes that depend on the target node by traversing edges
    in reverse direction (following incoming edges).

    Args:
    ----
        target_node_id: ID of node to analyze
        all_nodes: Complete node set
        all_edges: Complete edge set
        max_depth: Maximum traversal depth (default: 10)

    Returns:
    -------
        ImpactAnalysisResult with dependent nodes and edges

    """
    # Find target node
    target_node = None
    nodes_by_id = {node.id: node for node in all_nodes}

    if target_node_id not in nodes_by_id:
        # Target not found, return empty result
        dummy_node = Node(
            id=target_node_id,
            hash="0" * 40,
            title="Unknown",
            content="Unknown",
            path="unknown",
            type="text",
            token_count=1,
            created_at=0,
        )
        return ImpactAnalysisResult(target_node=dummy_node, dependent_nodes=[], dependency_edges=[])

    target_node = nodes_by_id[target_node_id]

    # Build reverse adjacency list (target <- source)
    reverse_edges: dict[UUID, list[Edge]] = {}
    for edge in all_edges:
        if edge.target not in reverse_edges:
            reverse_edges[edge.target] = []
        reverse_edges[edge.target].append(edge)

    # BFS traversal following reverse edges
    visited = {target_node_id}
    queue = [(target_node_id, 0)]
    dependent_nodes = []
    dependency_edges = []

    while queue:
        current_id, depth = queue.pop(0)

        # Stop at max depth
        if depth >= max_depth:
            continue

        # Get incoming edges (nodes that depend on current)
        if current_id in reverse_edges:
            for edge in reverse_edges[current_id]:
                if edge.source not in visited:
                    visited.add(edge.source)
                    queue.append((edge.source, depth + 1))
                    dependency_edges.append(edge)

                    if edge.source in nodes_by_id:
                        dependent_nodes.append(nodes_by_id[edge.source])

    return ImpactAnalysisResult(
        target_node=target_node, dependent_nodes=dependent_nodes, dependency_edges=dependency_edges
    )


def find_node_by_path_pattern(pattern: str, all_nodes: list[Node]) -> list[Node]:
    """Find nodes matching a file path pattern.

    Useful for converting user queries like "auth/login.py" to node IDs.

    Args:
    ----
        pattern: File path pattern to match
        all_nodes: Complete node set

    Returns:
    -------
        List of matching nodes

    """
    matches = []
    pattern_lower = pattern.lower()

    for node in all_nodes:
        if pattern_lower in node.path.lower():
            matches.append(node)

    return matches


def analyze_impact_by_path(
    path_pattern: str, all_nodes: list[Node], all_edges: list[Edge], max_depth: int = 10
) -> list[ImpactAnalysisResult]:
    """Perform impact analysis for nodes matching path pattern.

    Args:
    ----
        path_pattern: File path pattern to search
        all_nodes: Complete node set
        all_edges: Complete edge set
        max_depth: Maximum traversal depth

    Returns:
    -------
        List of impact results for matching nodes

    """
    matching_nodes = find_node_by_path_pattern(path_pattern, all_nodes)

    results = []
    for node in matching_nodes:
        result = analyze_impact(node.id, all_nodes, all_edges, max_depth)
        results.append(result)

    return results

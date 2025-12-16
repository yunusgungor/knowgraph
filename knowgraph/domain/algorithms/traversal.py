"""Graph traversal algorithms for n-hop exploration.

Implements DFS and BFS traversal strategies for expanding from seed nodes.
"""

from uuid import UUID

from knowgraph.config import MAX_HOPS
from knowgraph.domain.models.edge import Edge


def traverse_graph_dfs(
    seed_nodes: list[UUID],
    edges: list[Edge],
    max_hops: int = MAX_HOPS,
) -> set[UUID]:
    """Traverse graph using depth-first search.

    Args:
    ----
        seed_nodes: Starting nodes
        edges: List of all edges
        max_hops: Maximum traversal depth

    Returns:
    -------
        Set of reachable node UUIDs

    """
    # Build adjacency list
    adjacency: dict[UUID, list[UUID]] = {}
    for edge in edges:
        if edge.source not in adjacency:
            adjacency[edge.source] = []
        adjacency[edge.source].append(edge.target)

        # Add reverse edges for undirected traversal
        if edge.target not in adjacency:
            adjacency[edge.target] = []
        adjacency[edge.target].append(edge.source)

    visited: set[UUID] = set()
    stack: list[tuple[UUID, int]] = [(node_id, 0) for node_id in seed_nodes]

    while stack:
        current_node, depth = stack.pop()

        if current_node in visited or depth > max_hops:
            continue

        visited.add(current_node)

        # Add neighbors to stack
        if current_node in adjacency:
            for neighbor in adjacency[current_node]:
                if neighbor not in visited:
                    stack.append((neighbor, depth + 1))

    return visited


def traverse_graph_bfs(
    seed_nodes: list[UUID],
    edges: list[Edge],
    max_hops: int = MAX_HOPS,
) -> set[UUID]:
    """Traverse graph using breadth-first search.

    Args:
    ----
        seed_nodes: Starting nodes
        edges: List of all edges
        max_hops: Maximum traversal depth

    Returns:
    -------
        Set of reachable node UUIDs

    """
    from collections import deque

    # Build adjacency list
    adjacency: dict[UUID, list[UUID]] = {}
    for edge in edges:
        if edge.source not in adjacency:
            adjacency[edge.source] = []
        adjacency[edge.source].append(edge.target)

        if edge.target not in adjacency:
            adjacency[edge.target] = []
        adjacency[edge.target].append(edge.source)

    visited: set[UUID] = set()
    queue: deque[tuple[UUID, int]] = deque([(node_id, 0) for node_id in seed_nodes])

    while queue:
        current_node, depth = queue.popleft()

        if current_node in visited or depth > max_hops:
            continue

        visited.add(current_node)

        # Add neighbors to queue
        if current_node in adjacency and depth < max_hops:
            for neighbor in adjacency[current_node]:
                if neighbor not in visited:
                    queue.append((neighbor, depth + 1))

    return visited


def get_neighbors(node_id: UUID, edges: list[Edge]) -> list[UUID]:
    """Get all neighbors of a node.

    Args:
    ----
        node_id: Node UUID
        edges: List of edges

    Returns:
    -------
        List of neighbor UUIDs

    """
    neighbors = []
    for edge in edges:
        if edge.source == node_id:
            neighbors.append(edge.target)
        elif edge.target == node_id:
            neighbors.append(edge.source)
    return neighbors


def traverse_reverse_references(
    target_nodes: list[UUID],
    edges: list[Edge],
    max_hops: int = MAX_HOPS,
    edge_types: list[str] | None = None,
) -> set[UUID]:
    """Traverse graph in reverse to find nodes that reference target nodes.

    Used for impact analysis: "What will be affected if I change X?"
    Follows edges backward to find all nodes that depend on target nodes.

    Args:
    ----
        target_nodes: Nodes to analyze impact for
        edges: List of all edges
        max_hops: Maximum traversal depth
        edge_types: Filter by edge types (e.g., ["reference", "cross_file"])

    Returns:
    -------
        Set of node UUIDs that reference target nodes

    """
    from collections import deque

    # Filter edges by type if specified
    filtered_edges = edges
    if edge_types:
        filtered_edges = [e for e in edges if e.type in edge_types]

    # Build reverse adjacency list (target -> sources that reference it)
    reverse_adjacency: dict[UUID, list[UUID]] = {}
    for edge in filtered_edges:
        # For impact analysis, we traverse backward along directed edges
        if edge.target not in reverse_adjacency:
            reverse_adjacency[edge.target] = []
        reverse_adjacency[edge.target].append(edge.source)

    visited: set[UUID] = set()
    queue: deque[tuple[UUID, int]] = deque([(node_id, 0) for node_id in target_nodes])

    while queue:
        current_node, depth = queue.popleft()

        if current_node in visited or depth > max_hops:
            continue

        visited.add(current_node)

        # Add nodes that reference this node
        if current_node in reverse_adjacency and depth < max_hops:
            for referencing_node in reverse_adjacency[current_node]:
                if referencing_node not in visited:
                    queue.append((referencing_node, depth + 1))

    return visited

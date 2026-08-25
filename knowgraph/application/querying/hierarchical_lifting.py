"""Hierarchical context lifting for enriched retrieval.

Automatically includes parent directory documentation (README, package docs)
when retrieving code files to provide architectural context.

Example:
    Query: "getUserById function"
    Direct match: src/services/user_service.py
    Lifted context: src/services/README.md (explains service architecture)
                    src/README.md (explains overall structure)
"""

from pathlib import Path

from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.storage.filesystem import list_all_nodes, read_node_json


def lift_hierarchical_context(
    retrieved_nodes: list[Node],
    graph_store_path: Path,
    lift_levels: int = 2,
    max_additional_nodes: int = 5,
) -> list[Node]:
    """Lift hierarchical context by including parent directory documentation.

    For each retrieved code node, walks up the directory tree to find
    README files, package documentation, or other architectural docs.

    Uses an O(N) pre-built path→node_id index instead of O(N²) scanning.

    Args:
    ----
        retrieved_nodes: Initially retrieved nodes from query
        graph_store_path: Root graph storage directory
        lift_levels: Number of directory levels to walk up (default: 2)
        max_additional_nodes: Maximum additional nodes to add (default: 5)

    Returns:
    -------
        Extended list of nodes including hierarchical context

    """
    if not retrieved_nodes:
        return retrieved_nodes

    # Collect paths of retrieved nodes
    retrieved_paths = {Path(node.path) for node in retrieved_nodes if node.path}

    if not retrieved_paths:
        return retrieved_nodes

    # Find parent directories to search
    parent_dirs: set[Path] = set()
    for path in retrieved_paths:
        current = path.parent
        for _ in range(lift_levels):
            if current and current != current.parent:  # Not at root
                parent_dirs.add(current)
                current = current.parent

    # Build O(1) path→node_id index (single pass, no per-node disk reads)
    path_index: dict[Path, str] = {}  # path → node_id
    node_ids = list_all_nodes(graph_store_path)
    for node_id in node_ids:
        node = read_node_json(node_id, graph_store_path)
        if node and node.path:
            path_index[Path(node.path)] = str(node_id)

    # Documentation file patterns (prioritized)
    doc_patterns = [
        "readme.md",
        "readme.txt",
        "__init__.py",
        "package.json",
        "index.md",
        "overview.md",
        "architecture.md",
    ]

    additional_nodes: list[Node] = []
    retrieved_id_set = {n.id for n in retrieved_nodes}

    # O(P * D) where P = parent_dirs, D = doc_patterns (small constants)
    for parent_dir in parent_dirs:
        for pattern in doc_patterns:
            # Try common filenames in this directory
            candidate_path = parent_dir / pattern
            if candidate_path in path_index:
                nid = path_index[candidate_path]
                from uuid import UUID
                node_id = UUID(nid) if isinstance(nid, str) else nid
                if node_id not in retrieved_id_set:
                    node = read_node_json(node_id, graph_store_path)
                    if node:
                        additional_nodes.append(node)
                        retrieved_id_set.add(node_id)
                        if len(additional_nodes) >= max_additional_nodes:
                            break
        if len(additional_nodes) >= max_additional_nodes:
            break

    # Sort additional nodes by priority (README first)
    def doc_priority(node: Node) -> int:
        filename = Path(node.path).name.lower()
        if "readme" in filename:
            return 0
        elif "__init__" in filename:
            return 1
        elif "architecture" in filename or "overview" in filename:
            return 2
        else:
            return 3

    additional_nodes.sort(key=doc_priority)

    return retrieved_nodes + additional_nodes[:max_additional_nodes]

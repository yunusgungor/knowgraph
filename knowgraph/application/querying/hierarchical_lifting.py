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
from uuid import UUID

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

    # Load all nodes to find documentation in parent dirs
    additional_nodes: list[Node] = []
    node_ids = list_all_nodes(graph_store_path)

    # Documentation file patterns (prioritized)
    doc_patterns = [
        "readme.md",
        "readme.txt",
        "__init__.py",  # Python package docs
        "package.json",  # JS/TS package info
        "index.md",
        "overview.md",
        "architecture.md",
    ]

    for node_id in node_ids:
        # Skip if already in retrieved nodes
        if any(n.id == node_id for n in retrieved_nodes):
            continue

        node = read_node_json(node_id, graph_store_path)
        if not node or not node.path:
            continue

        node_path = Path(node.path)
        node_dir = node_path.parent
        node_filename = node_path.name.lower()

        # Check if this node is in a parent directory and is documentation
        if node_dir in parent_dirs and any(pattern in node_filename for pattern in doc_patterns):
            additional_nodes.append(node)

            if len(additional_nodes) >= max_additional_nodes:
                break

    # Sort additional nodes by priority (README first, then __init__.py, etc.)
    def doc_priority(node: Node) -> int:
        """Assign priority to documentation nodes."""
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

    # Combine: original nodes first, then hierarchical context
    return retrieved_nodes + additional_nodes[:max_additional_nodes]


def explain_lifted_context(
    original_count: int,
    final_count: int,
    lifted_nodes: list[Node],
) -> str:
    """Generate human-readable explanation of lifted context.

    Args:
    ----
        original_count: Number of originally retrieved nodes
        final_count: Number of nodes after lifting
        lifted_nodes: List of lifted (additional) nodes

    Returns:
    -------
        Explanation string

    """
    if final_count == original_count:
        return "No additional hierarchical context found."

    added_count = final_count - original_count
    lifted_paths = [Path(n.path).name for n in lifted_nodes[:added_count]]

    return (
        f"Added {added_count} parent directory documentation file(s) "
        f"for architectural context: {', '.join(lifted_paths)}"
    )


def lift_conversation_artifacts(
    conversation_nodes: list[Node],
    graph_store_path: Path,
    max_related: int = 3,
) -> list[Node]:
    """Lift related conversation artifacts for richer context.

    For conversation nodes (e.g., task.md), automatically include
    related artifacts (walkthrough.md, implementation_plan.md) from
    the same conversation directory.

    Args:
    ----
        conversation_nodes: Initial conversation nodes
        graph_store_path: Path to graph storage
        max_related: Maximum related artifacts to include

    Returns:
    -------
        Original nodes + related conversation artifacts

    """
    from knowgraph.infrastructure.storage.graph_store import GraphStore

    store = GraphStore(graph_store_path)
    all_nodes = list(store.list_nodes())

    # Group nodes by conversation directory
    conversation_dirs = {}
    for node in conversation_nodes:
        if node.path and ("brain/" in node.path or "conversation" in node.path.lower()):
            # Extract conversation directory
            # e.g., "brain/conv-id/task.md" → "brain/conv-id"
            parts = Path(node.path).parts
            if len(parts) >= 2:
                conv_dir = "/".join(parts[:-1])
                if conv_dir not in conversation_dirs:
                    conversation_dirs[conv_dir] = []
                conversation_dirs[conv_dir].append(node)

    # Find related artifacts in same conversation directory
    related_nodes = []
    artifact_patterns = ["task.md", "walkthrough.md", "implementation_plan.md"]

    for conv_dir, nodes in conversation_dirs.items():
        # Find all nodes in same conversation directory
        for other_node in all_nodes:
            if other_node in nodes:
                continue  # Skip nodes we already have

            if other_node.path and conv_dir in other_node.path:
                # Check if it's an artifact
                filename = Path(other_node.path).name.lower()
                if any(pattern in filename for pattern in artifact_patterns):
                    related_nodes.append(other_node)

                    if len(related_nodes) >= max_related:
                        break

    # Combine original + related (unique)
    all_node_ids = {node.id for node in conversation_nodes}
    unique_related = [n for n in related_nodes if n.id not in all_node_ids]

    return conversation_nodes + unique_related[:max_related]

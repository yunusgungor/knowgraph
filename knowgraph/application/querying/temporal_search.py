"""Temporal search extensions for QueryEngine.

Adds time-aware querying capabilities:
- Timestamp-based filtering
- Date range queries
- Conversation timeline search
"""

from datetime import datetime
from pathlib import Path

from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.storage.filesystem import list_all_nodes, read_node_json


def filter_nodes_by_time_range(
    nodes: list[Node],
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[Node]:
    """Filter nodes by creation timestamp.

    Args:
    ----
        nodes: Nodes to filter
        start_time: Optional start of time range
        end_time: Optional end of time range

    Returns:
    -------
        Filtered nodes

    """
    if not start_time and not end_time:
        return nodes

    filtered = []
    for node in nodes:
        # Check if node has timestamp
        if not hasattr(node, "created_at") or node.created_at is None:
            # Try metadata timestamp
            if node.metadata and "timestamp" in node.metadata:
                try:
                    node_time = datetime.fromisoformat(node.metadata["timestamp"])
                except (ValueError, TypeError):
                    continue
            else:
                continue
        else:
            # created_at is unix timestamp
            node_time = datetime.fromtimestamp(node.created_at)

        # Apply filters
        if start_time and node_time < start_time:
            continue
        if end_time and node_time > end_time:
            continue

        filtered.append(node)

    return filtered


def filter_conversations_by_time(
    graph_store_path: Path,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    editor: str | None = None,
) -> list[Node]:
    """Find conversations in time range.

    Args:
    ----
        graph_store_path: Path to graph storage
        start_time: Optional start time
        end_time: Optional end time
        editor: Optional editor filter (antigravity, cursor, etc.)

    Returns:
    -------
        List of conversation nodes in time range

    """
    # Load all nodes
    node_ids = list_all_nodes(graph_store_path)
    conversations = []

    for node_id in node_ids:
        node = read_node_json(node_id, graph_store_path)
        if not node:
            continue

        # Filter to conversations only
        node_type = node.metadata.get("type") if node.metadata else None
        if node_type not in ["conversation", "tagged_snippet"]:
            continue

        # Filter by editor if specified
        if editor:
            node_editor = node.metadata.get("editor") if node.metadata else None
            if node_editor != editor:
                continue

        conversations.append(node)

    # Apply time filter
    return filter_nodes_by_time_range(conversations, start_time, end_time)


def query_with_time_range(
    query_text: str,
    graph_store_path: Path,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    include_conversations: bool = True,
    top_k: int = 10,
) -> dict:
    """Execute query with temporal filtering.

    Args:
    ----
        query_text: Query text
        graph_store_path: Path to graph storage
        start_time: Optional start time
        end_time: Optional end time
        include_conversations: Include conversation nodes
        top_k: Max results

    Returns:
    -------
        Dictionary with results and metadata

    """
    from knowgraph.application.querying.query_engine import QueryEngine

    # Execute base query
    engine = QueryEngine(graph_store_path)
    result = engine.query(query_text, top_k=top_k * 2)  # Get more for filtering

    # Extract nodes from context
    # (In real implementation, would parse result.context)
    # For now, get all nodes and filter
    all_nodes = []
    node_ids = list_all_nodes(graph_store_path)
    for node_id in node_ids[:50]:  # Sample for demo
        node = read_node_json(node_id, graph_store_path)
        if node:
            all_nodes.append(node)

    # Apply time filter
    filtered_nodes = filter_nodes_by_time_range(all_nodes, start_time, end_time)

    # Filter to conversations if requested
    if include_conversations:
        filtered_nodes = [
            n
            for n in filtered_nodes
            if n.metadata and n.metadata.get("type") in ["conversation", "tagged_snippet"]
        ]

    return {
        "nodes": filtered_nodes[:top_k],
        "total_found": len(filtered_nodes),
        "time_range": {
            "start": start_time.isoformat() if start_time else None,
            "end": end_time.isoformat() if end_time else None,
        },
        "query": query_text,
    }


# Example usage
if __name__ == "__main__":
    from datetime import timedelta

    # Query last week's conversations about authentication
    end = datetime.now()
    start = end - timedelta(days=7)

    result = query_with_time_range(
        "authentication",
        Path("./graphstore"),
        start_time=start,
        end_time=end,
    )

    print(f"Found {result['total_found']} results in last 7 days")

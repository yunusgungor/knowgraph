"""Extended query methods for QueryEngine.

Adds conversation and temporal search capabilities.
"""

from datetime import datetime
from pathlib import Path

from knowgraph.application.querying.conversation_search import (
    enrich_with_conversations,
    search_bookmarks,
)
from knowgraph.application.querying.temporal_search import filter_nodes_by_time_range
from knowgraph.domain.models.node import Node


def query_with_conversations(
    query_engine,
    query_text: str,
    top_k: int = 10,
    include_conversations: bool = True,
    max_conversations: int = 3,
) -> dict:
    """Execute query and optionally include related conversations.

    Args:
    ----
        query_engine: QueryEngine instance
        query_text: Query text
        top_k: Number of results
        include_conversations: Include conversation nodes
        max_conversations: Max conversations to add

    Returns:
    -------
        Extended query result with conversations

    """
    # Execute base query
    result = query_engine.query(query_text, top_k=top_k)

    if not include_conversations:
        return {
            "context": result.context,
            "explanation": result.explanation,
            "conversations_included": False,
        }

    # Parse nodes from context (simplified - assumes context has node info)
    # In production, would need proper parsing from result.context
    from knowgraph.infrastructure.storage.filesystem import list_all_nodes, read_node_json

    node_ids = list_all_nodes(query_engine.graph_store_path)
    all_nodes = []
    for node_id in node_ids[:top_k]:
        node = read_node_json(node_id, query_engine.graph_store_path)
        if node:
            all_nodes.append(node)

    # Enrich with conversations
    enriched_nodes, metadata = enrich_with_conversations(
        all_nodes, query_engine.graph_store_path, max_conversations=max_conversations
    )

    return {
        "context": result.context,
        "explanation": result.explanation,
        "conversations_included": True,
        "conversations_found": metadata["conversations_found"],
        "enriched_nodes": enriched_nodes,
    }


def query_with_time_filter(
    query_engine,
    query_text: str,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    top_k: int = 10,
) -> dict:
    """Execute query with temporal filtering.

    Args:
    ----
        query_engine: QueryEngine instance
        query_text: Query text
        start_time: Start of time range
        end_time: End of time range
        top_k: Number of results

    Returns:
    -------
        Time-filtered query results

    """
    # Execute base query
    result = query_engine.query(query_text, top_k=top_k * 2)  # Get more for filtering

    # Load nodes and filter by time
    from knowgraph.infrastructure.storage.filesystem import list_all_nodes, read_node_json

    node_ids = list_all_nodes(query_engine.graph_store_path)
    all_nodes = []
    for node_id in node_ids[: top_k * 2]:
        node = read_node_json(node_id, query_engine.graph_store_path)
        if node:
            all_nodes.append(node)

    # Apply time filter
    filtered_nodes = filter_nodes_by_time_range(all_nodes, start_time, end_time)

    return {
        "context": result.context,
        "explanation": result.explanation,
        "time_filtered": True,
        "time_range": {
            "start": start_time.isoformat() if start_time else None,
            "end": end_time.isoformat() if end_time else None,
        },
        "filtered_nodes": filtered_nodes[:top_k],
        "total_before_filter": len(all_nodes),
        "total_after_filter": len(filtered_nodes),
    }


def search_bookmarks_integrated(
    query_engine,
    query_text: str,
    top_k: int = 10,
) -> list[Node]:
    """Search bookmarks using query engine.

    Args:
    ----
        query_engine: QueryEngine instance
        query_text: Search query
        top_k: Number of results

    Returns:
    -------
        List of bookmark nodes

    """
    return search_bookmarks(query_text, query_engine.graph_store_path, top_k)

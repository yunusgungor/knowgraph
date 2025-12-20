"""Query engine extension for conversation and bookmark search.

Adds conversation-aware querying capabilities to enable searching
across both code and conversation history.
"""

from pathlib import Path

from knowgraph.domain.models.node import Node


def search_bookmarks(
    query: str,
    graph_store_path: Path,
    top_k: int = 10,
) -> list[Node]:
    """Search tagged bookmarks/snippets using FTS5.

    Uses SQLite FTS5 with BM25 ranking for fast full-text search.
    Falls back to legacy full-scan if FTS5 index doesn't exist.

    Args:
    ----
        query: Search query
        graph_store_path: Path to graph storage
        top_k: Number of results

    Returns:
    -------
        List of bookmark nodes matching query

    """
    import logging

    from knowgraph.infrastructure.search.bookmark_search import BookmarkSearch
    from knowgraph.infrastructure.storage.filesystem import read_node_json

    logger = logging.getLogger(__name__)

    try:
        # Try FTS5 search first (fast path)
        search = BookmarkSearch(graph_store_path)

        # Check if index needs migration
        if search.count() == 0:
            logger.info("FTS5 index empty, running auto-migration...")
            from knowgraph.infrastructure.search.bookmark_search import migrate_bookmarks
            stats = migrate_bookmarks(graph_store_path)
            logger.info(f"Auto-migration complete: {stats['bookmarks_migrated']} bookmarks indexed")

        # Perform FTS5 search
        results = search.search(query, top_k=top_k)

        # Load full nodes
        nodes = []
        for node_id, score in results:
            node = read_node_json(node_id, graph_store_path)
            if node:
                nodes.append(node)
                logger.debug(f"FTS5 result: {node.metadata.get('tag', 'unknown') if node.metadata else 'no-tag'} (score={score:.3f})")

        logger.info(f"search_bookmarks: FTS5 returned {len(nodes)} results for '{query}'")
        return nodes

    except Exception as e:
        # Fallback to legacy full-scan search
        logger.warning(f"FTS5 search failed ({e}), falling back to full-scan")
        return _search_bookmarks_legacy(query, graph_store_path, top_k)


def _search_bookmarks_legacy(
    query: str,
    graph_store_path: Path,
    top_k: int = 10,
) -> list[Node]:
    """Legacy full-scan bookmark search (fallback).

    This is the original O(N) implementation kept for backward compatibility.
    """
    import logging

    from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder
    from knowgraph.infrastructure.storage.filesystem import list_all_nodes, read_node_json

    logger = logging.getLogger(__name__)

    # Load all nodes from filesystem
    node_ids = list_all_nodes(graph_store_path)
    logger.debug(f"search_bookmarks (legacy): Scanning {len(node_ids)} total nodes")

    bookmarks = []
    nodes_checked = 0

    for node_id in node_ids:
        node = read_node_json(node_id, graph_store_path)
        nodes_checked += 1
        if node and node.type == "tagged_snippet":
            bookmarks.append(node)

    logger.info(f"search_bookmarks (legacy): Found {len(bookmarks)} bookmarks out of {nodes_checked} nodes checked")

    if not bookmarks:
        logger.warning(f"No bookmarks found in {graph_store_path}. Use tag_snippet to create bookmarks first.")
        return []

    # Use code-aware tokenization on query
    embedder = SparseEmbedder()
    query_tokens = embedder.embed_code(query)

    # Score bookmarks by tag match
    scored_bookmarks = []
    for bookmark in bookmarks:
        tag_tokens = bookmark.metadata.get("tag_tokens", []) if bookmark.metadata else []

        # Calculate overlap score
        query_keys_list: list[str] = list(query_tokens.keys())
        query_keys_set: set[str] = set(query_keys_list)
        tag_tokens_set: set[str] = set(tag_tokens)  # type: ignore[call-overload]
        overlap = len(query_keys_set & tag_tokens_set)
        if overlap > 0:
            score = overlap / len(query_tokens)
            scored_bookmarks.append((bookmark, score))

    # Sort by score and return top k
    scored_bookmarks.sort(key=lambda x: x[1], reverse=True)
    return [b for b, _ in scored_bookmarks[:top_k]]


def enrich_with_conversations(
    query_result_nodes: list[Node],
    graph_store_path: Path,
    max_conversations: int = 3,
) -> tuple[list[Node], dict]:
    """Enrich query results with related conversations.

    Finds conversations that discuss the same code files as query results.

    Args:
    ----
        query_result_nodes: Nodes from query
        graph_store_path: Path to graph storage
        max_conversations: Max conversations to add

    Returns:
    -------
        Tuple of (enriched nodes, metadata)

    """
    from knowgraph.infrastructure.storage.filesystem import (
        list_all_edges,
        list_all_nodes,
        read_edge_json,
        read_node_json,
    )

    # Load all edges and nodes
    edge_ids = list_all_edges(graph_store_path)
    list_all_nodes(graph_store_path)

    # Find conversation nodes that reference our result nodes
    result_node_ids = {node.id for node in query_result_nodes}
    conversation_nodes = []

    for edge_id in edge_ids:
        edge = read_edge_json(edge_id, graph_store_path)
        if not edge:
            continue

        # Look for conversation_references_code edges pointing to our results
        if edge.type == "conversation_references_code" and edge.target in result_node_ids:
            # Find the conversation node
            conv_node = read_node_json(edge.source, graph_store_path)
            if conv_node and conv_node not in conversation_nodes:
                conversation_nodes.append(conv_node)

                if len(conversation_nodes) >= max_conversations:
                    break

    metadata = {
        "conversations_found": len(conversation_nodes),
        "original_results": len(query_result_nodes),
    }

    return query_result_nodes + conversation_nodes, metadata


# Example usage
if __name__ == "__main__":
    from pathlib import Path

    # Test bookmark search
    bookmarks = search_bookmarks(
        query="getUserById",
        graph_store_path=Path("./graphstore"),
        top_k=5,
    )
    print(f"Found {len(bookmarks)} bookmarks")

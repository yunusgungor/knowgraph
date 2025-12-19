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
    """Search tagged bookmarks/snippets.

    Uses code-aware tokenization for better recall on bookmark tags.

    Args:
    ----
        query: Search query
        graph_store_path: Path to graph storage
        top_k: Number of results

    Returns:
    -------
        List of bookmark nodes matching query

    """
    from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder
    from knowgraph.infrastructure.storage.filesystem import list_all_nodes, read_node_json

    # Load all nodes from filesystem
    node_ids = list_all_nodes(graph_store_path)
    bookmarks = []

    for node_id in node_ids:
        node = read_node_json(node_id, graph_store_path)
        if node and node.type == "tagged_snippet":
            bookmarks.append(node)

    if not bookmarks:
        return []

    # Use code-aware tokenization on query
    embedder = SparseEmbedder()
    query_tokens = embedder.embed_code(query)

    # Score bookmarks by tag match
    scored_bookmarks = []
    for bookmark in bookmarks:
        tag_tokens = bookmark.metadata.get("tag_tokens", []) if bookmark.metadata else []

        # Calculate overlap score
        overlap = len(set(query_tokens.keys()) & set(tag_tokens))
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

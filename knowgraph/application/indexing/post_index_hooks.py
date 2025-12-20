"""Post-indexing automation hooks.

Provides automatic processing after code indexing:
- Conversation discovery and linking
- Bookmark auto-tagging
- Statistics collection
"""

from pathlib import Path

# Type: ignore for conversation_discovery - it's infrastructure code
# mypy: disable-error-code="import-not-found"



async def auto_link_conversations(
    graphstore_path: Path,
    workspace_path: Path | None = None,
) -> dict:
    """Auto-discover and link conversations to code after indexing.

    Args:
    ----
        graphstore_path: Path to graph storage
        workspace_path: Workspace root (for conversation discovery)

    Returns:
    -------
        Statistics about conversations linked

    """
    from knowgraph.application.linking.conversation_linker import link_conversation_to_code
    from knowgraph.infrastructure.detection.conversation_discovery import discover_conversations

    stats = {
        "conversations_found": 0,
        "conversations_linked": 0,
        "edges_created": 0,
        "errors": 0,
    }

    try:
        # Discover conversations
        workspace = workspace_path or graphstore_path.parent
        conversations = discover_conversations(workspace)
        stats["conversations_found"] = len(conversations)

        # Link each conversation to code
        for conv_file in conversations:
            try:
                edges_created = await link_conversation_to_code(conv_file, graphstore_path)
                if edges_created > 0:
                    stats["conversations_linked"] += 1
                    stats["edges_created"] += edges_created
            except Exception:
                stats["errors"] += 1
                continue

    except Exception:
        stats["errors"] += 1

    return stats


async def auto_tag_bookmarks(
    graphstore_path: Path,
    min_confidence: float = 0.3,
) -> dict:
    """Apply AI auto-tagging to existing bookmarks.

    Args:
    ----
        graphstore_path: Path to graph storage
        min_confidence: Minimum confidence for auto-suggestions

    Returns:
    -------
        Statistics about bookmarks tagged

    """
    from knowgraph.application.tagging.auto_tagger import auto_tag_snippet
    from knowgraph.infrastructure.storage.filesystem import (
        list_all_nodes,
    )

    stats = {
        "bookmarks_found": 0,
        "bookmarks_enhanced": 0,
        "suggestions_added": 0,
        "errors": 0,
    }

    import asyncio

    from knowgraph.infrastructure.storage.filesystem import (
        read_node_json_async,
        write_node_json_async,
    )

    try:
        # Load all nodes
        node_ids = list_all_nodes(graphstore_path)

        # Process nodes in parallel batches for better performance
        async def process_node(node_id):
            node = await read_node_json_async(node_id, graphstore_path)

            if not node or node.type != "tagged_snippet":
                return None

            stats["bookmarks_found"] += 1

            try:
                # Apply auto-tagging
                result = auto_tag_snippet(node.content)

                if result["confidence"] >= min_confidence:
                    # Add auto-suggestions to metadata
                    if not node.metadata:
                        node.metadata = {}

                    node.metadata["auto_suggested_tags"] = result["suggested_tags"]
                    node.metadata["auto_tag_confidence"] = result["confidence"]
                    node.metadata["auto_topic"] = result.get("topic", "general")

                    # Save updated node (async)
                    await write_node_json_async(node, graphstore_path)

                    stats["bookmarks_enhanced"] += 1
                    stats["suggestions_added"] += len(result["suggested_tags"])
                    return True
            except Exception:
                stats["errors"] += 1
                return None

        # Process in batches of 10 for controlled concurrency
        batch_size = 10
        for i in range(0, len(node_ids), batch_size):
            batch = node_ids[i : i + batch_size]
            await asyncio.gather(*[process_node(nid) for nid in batch])

    except Exception:
        stats["errors"] += 1

    return stats


def collect_index_stats(graphstore_path: Path) -> dict:
    """Collect comprehensive indexing statistics.

    Args:
    ----
        graphstore_path: Path to graph storage

    Returns:
    -------
        Complete statistics dictionary

    """
    from knowgraph.infrastructure.storage.filesystem import (
        list_all_edges,
        list_all_nodes,
        read_node_json,
    )

    stats = {
        "total_nodes": 0,
        "total_edges": 0,
        "code_nodes": 0,
        "markdown_nodes": 0,
        "conversation_nodes": 0,
        "bookmark_nodes": 0,
        "other_nodes": 0,
    }

    try:
        # Count nodes by type
        node_ids = list_all_nodes(graphstore_path)
        stats["total_nodes"] = len(node_ids)

        for node_id in node_ids:
            node = read_node_json(node_id, graphstore_path)
            if not node:
                continue

            if node.type == "code":
                stats["code_nodes"] += 1
            elif node.type in ("markdown", "text", "documentation", "config"):
                stats["markdown_nodes"] += 1
            elif node.type == "conversation":
                stats["conversation_nodes"] += 1
            elif node.type == "tagged_snippet":
                stats["bookmark_nodes"] += 1
            else:
                stats["other_nodes"] += 1

        # Count edges
        edge_ids = list_all_edges(graphstore_path)
        stats["total_edges"] = len(edge_ids)

    except Exception:
        pass

    return stats


# Example usage
if __name__ == "__main__":
    import asyncio

    async def test():
        graphstore = Path("./graphstore")

        # Auto-link conversations
        conv_stats = await auto_link_conversations(graphstore)
        print(f"Conversations: {conv_stats}")

        # Auto-tag bookmarks
        tag_stats = await auto_tag_bookmarks(graphstore)
        print(f"Auto-tagging: {tag_stats}")

        # Collect stats
        stats = collect_index_stats(graphstore)
        print(f"Index stats: {stats}")

    asyncio.run(test())

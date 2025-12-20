"""Snippet tagging for semantic bookmarking.

Allows users to tag important conversation snippets for later retrieval.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from knowgraph.domain.models.node import Node


@dataclass
class TaggedSnippet:
    """A tagged conversation snippet."""

    tag: str
    content: str
    conversation_id: str | None = None
    user_question: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)


def create_tagged_snippet(
    tag: str,
    content: str,
    conversation_id: str | None = None,
    user_question: str | None = None,
    additional_metadata: dict | None = None,
) -> Node:
    """Create a tagged snippet node.

    Args:
    ----
        tag: Tag for the snippet (e.g., "fastapi jwt detayı")
        content: The snippet content to tag
        conversation_id: Optional conversation ID
        user_question: Optional user question that prompted the response
        additional_metadata: Optional additional metadata

    Returns:
    -------
        Node with tagged snippet

    """
    node_id = str(uuid4())
    timestamp = datetime.now()

    # ENHANCEMENT: Process tag with code-aware tokenization
    from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder

    embedder = SparseEmbedder()
    tag_tokens = embedder.embed_code(tag)  # camelCase/snake_case splitting
    tokenized_tags = list(tag_tokens.keys())  # Expanded tokens

    # Build metadata
    metadata = {
        "type": "tagged_snippet",
        "tag": tag,
        "tag_tokens": tokenized_tags,  # NEW: For better search
        "timestamp": timestamp.isoformat(),
        "conversation_id": conversation_id,
        "user_question": user_question,
        "role": "tagged_snippet",
    }

    if additional_metadata:
        metadata.update(additional_metadata)

    # Create node with all required fields
    from knowgraph.infrastructure.parsing.hasher import hash_content

    content_hash = hash_content(content)

    node = Node(
        id=node_id,
        content=content,
        path=f"tagged_snippets/{tag.replace(' ', '_')}.md",
        hash=content_hash,
        title=f"Tagged: {tag}",
        type="tagged_snippet",  # type: ignore
        token_count=len(content.split()),  # Rough estimate
        created_at=timestamp,
        metadata=metadata,
    )

    return node


def format_tagged_snippet_markdown(snippet: TaggedSnippet) -> str:
    """Format tagged snippet as markdown.

    Args:
    ----
        snippet: Tagged snippet to format

    Returns:
    -------
        Markdown formatted snippet

    """
    lines = []

    # Header
    lines.append(f"# Tagged Snippet: {snippet.tag}")
    lines.append("")
    lines.append(f"**Tag**: `{snippet.tag}`")
    lines.append(f"**Timestamp**: {snippet.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

    if snippet.conversation_id:
        lines.append(f"**Conversation ID**: {snippet.conversation_id}")

    if snippet.user_question:
        lines.append(f"**User Question**: {snippet.user_question}")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Content
    lines.append("## Content")
    lines.append("")
    lines.append(snippet.content)
    lines.append("")

    return "\n".join(lines)


async def index_tagged_snippet(
    snippet: Node,
    graph_path: Path,
    provider: Any | None = None,
) -> None:
    """Index a tagged snippet into the graph and FTS5 search index.

    Args:
    ----
        snippet: Tagged snippet node
        graph_path: Path to graph storage
        provider: Optional IntelligenceProvider (not used, kept for compatibility)

    """
    # Write snippet node directly to graph store instead of using run_index
    # This preserves the tagged_snippet type and all metadata
    from knowgraph.infrastructure.storage.filesystem import write_node_json

    # Ensure graph store directory exists
    graph_path.mkdir(parents=True, exist_ok=True)

    # Write node to storage
    write_node_json(snippet, graph_path)

    # Verification: Check if snippet was written successfully
    from knowgraph.infrastructure.storage.filesystem import read_node_json

    verification_node = read_node_json(snippet.id, graph_path)
    if not verification_node:
        raise RuntimeError(
            f"Snippet verification failed: Node {snippet.id} not found in graph store after writing"
        )

    if verification_node.type != "tagged_snippet":
        raise RuntimeError(
            f"Snippet verification failed: Node type is '{verification_node.type}', expected 'tagged_snippet'"
        )

    # Validation: Check required metadata
    if not verification_node.metadata or "tag" not in verification_node.metadata:
        raise RuntimeError(
            "Snippet verification failed: Missing tag in metadata"
        )

    # Index into FTS5 for fast search
    try:
        from knowgraph.infrastructure.search.bookmark_search import BookmarkSearch

        search = BookmarkSearch(graph_path)
        search.add(snippet)

    except Exception as e:
        # Log error but don't fail the operation
        # FTS5 indexing is performance optimization, not critical
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to index snippet into FTS5: {e}")


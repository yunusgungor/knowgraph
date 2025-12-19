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
    """Index a tagged snippet into the graph.

    Args:
    ----
        snippet: Tagged snippet node
        graph_path: Path to graph storage
        provider: Optional IntelligenceProvider (defaults to OpenAIProvider)

    """
    # Create temporary markdown file
    import tempfile
    from typing import Any

    from knowgraph.adapters.cli.index_command import run_index
    from knowgraph.infrastructure.intelligence.openai_provider import OpenAIProvider

    snippet_data = TaggedSnippet(
        tag=(snippet.metadata or {}).get("tag", "unknown"),
        content=snippet.content,
        conversation_id=(snippet.metadata or {}).get("conversation_id"),
        user_question=(snippet.metadata or {}).get("user_question"),
        timestamp=datetime.fromisoformat(
            (snippet.metadata or {}).get("timestamp", datetime.now().isoformat())
        ),
    )

    markdown_content = format_tagged_snippet_markdown(snippet_data)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        prefix=f"tagged_{str(snippet_data.tag).replace(' ', '_')}_",
        delete=False,
        encoding="utf-8",
    ) as temp_file:
        temp_file.write(markdown_content)
        temp_path = Path(temp_file.name)

    try:
        # Index the snippet
        if provider is None:
            provider = OpenAIProvider()

        await run_index(
            input_path=str(temp_path),
            output_path=str(graph_path),
            verbose=False,
            provider=provider,
        )
    finally:
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

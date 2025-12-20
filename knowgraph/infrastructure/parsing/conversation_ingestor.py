"""Conversation ingestor for converting conversation files to markdown.

Handles conversation files from various AI code editors and converts them
to markdown format for indexing.
"""

import tempfile
from pathlib import Path

from knowgraph.infrastructure.parsing.conversation_parser import (
    conversation_to_markdown,
    parse_conversation,
)


class ConversationIngestorError(Exception):
    """Base exception for conversation ingestor errors."""


async def ingest_conversation(
    conversation_path: Path,
    output_path: Path | None = None,
) -> tuple[str, Path]:
    """Ingest a conversation file and convert to markdown.

    Args:
    ----
        conversation_path: Path to conversation file (.aichat, .json, .txt)
        output_path: Path to save the markdown (if None, uses temp file)

    Returns:
    -------
        Tuple of (markdown_content, output_file_path)

    Raises:
    ------
        ConversationIngestorError: If parsing or conversion fails

    """
    try:
        # Parse conversation
        conversation = parse_conversation(conversation_path)

        if conversation is None:
            msg = f"Could not parse conversation file: {conversation_path}"
            raise ConversationIngestorError(msg)

        # Convert to markdown
        markdown_content = conversation_to_markdown(conversation)

        # Save to file
        if output_path is None:
            # Create temporary file
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".md",
                prefix="conversation_",
                delete=False,
                encoding="utf-8",
            ) as temp_file:
                output_path = Path(temp_file.name)
                temp_file.write(markdown_content)
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

        return markdown_content, output_path

    except Exception as e:
        msg = f"Failed to ingest conversation: {e}"
        raise ConversationIngestorError(msg) from e

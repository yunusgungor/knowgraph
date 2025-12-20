"""Node value object - immutable representation of a knowledge unit."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from knowgraph.config import DEFAULT_ROLE_WEIGHT, MAX_NODE_TOKEN_COUNT, ROLE_WEIGHTS
from knowgraph.shared.types import NodeType


@dataclass(frozen=True)
class Node:
    """A single node in the knowledge graph.

    Represents a chunk of content from the source repository with metadata
    for retrieval and graph traversal.

    Attributes
    ----------
        id: Unique identifier (UUID4)
        hash: SHA-1 content hash (40 hex characters)
        title: Chunk header or first line
        content: Full chunk text
        path: Source file path (relative to repo root)
        type: Content classification (code, text, readme, config)
        token_count: Approximate token count via tiktoken
        created_at: Unix timestamp of creation
        header_depth: H1-H4 level (1-4) or None
        header_path: Breadcrumb path (e.g., "H1 > H2 > H3")
        chunk_id: Context identifier for markdown
        line_start: Starting line in source file
        line_end: Ending line in source file

    """

    # Identity
    id: UUID
    hash: str

    # Content
    title: str
    content: str
    path: str

    # Metadata
    type: NodeType
    token_count: int
    created_at: int

    # Hierarchy (optional)
    header_depth: int | None = None
    header_path: str | None = None
    chunk_id: str | None = None
    line_start: int | None = None
    line_end: int | None = None

    # Dynamic Metadata
    metadata: dict[str, object] | None = None

    def __post_init__(self: Node) -> None:
        """Validate node invariants."""
        max_tokens = MAX_NODE_TOKEN_COUNT  # Maximum tokens per node

        if len(self.hash) != 40:
            raise ValueError(f"Hash must be 40 characters, got {len(self.hash)}")
        if not self.content:
            raise ValueError("Content cannot be empty")
        if self.token_count <= 0:
            raise ValueError(f"Token count must be positive, got {self.token_count}")
        if self.token_count > max_tokens:
            raise ValueError(f"Token count too large: {self.token_count}")
        if self.header_depth is not None and not (1 <= self.header_depth <= 4):
            raise ValueError(f"Header depth must be 1-4, got {self.header_depth}")
        if self.path.startswith("/"):
            raise ValueError("Path must be relative (no leading slash)")

    def to_dict(self: Node) -> dict[str, object]:
        """Serialize node to dictionary for JSON storage."""
        return {
            "id": str(self.id),
            "hash": self.hash,
            "title": self.title,
            "content": self.content,
            "path": self.path,
            "type": self.type,
            "token_count": self.token_count,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else self.created_at,
            "header_depth": self.header_depth,
            "header_path": self.header_path,
            "chunk_id": self.chunk_id,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Node:
        """Deserialize node from dictionary."""
        from datetime import datetime
        from typing import cast
        from uuid import UUID

        # Parse created_at (can be int timestamp or ISO string)
        created_at_raw = data["created_at"]
        if isinstance(created_at_raw, str):
            # ISO format string -> convert to timestamp
            try:
                dt = datetime.fromisoformat(created_at_raw)
                created_at_value = int(dt.timestamp())
            except (ValueError, AttributeError):
                # Fallback: try to parse as int string
                created_at_value = int(created_at_raw)
        else:
            created_at_value = cast(int, created_at_raw)

        return cls(
            id=UUID(cast(str, data["id"])),
            hash=cast(str, data["hash"]),
            title=cast(str, data["title"]),
            content=cast(str, data["content"]),
            path=cast(str, data["path"]),
            type=cast(NodeType, data["type"]),
            token_count=cast(int, data["token_count"]),
            created_at=created_at_value,
            header_depth=(
                cast(int, data.get("header_depth"))
                if data.get("header_depth") is not None
                else None
            ),
            header_path=(
                cast(str, data.get("header_path")) if data.get("header_path") is not None else None
            ),
            chunk_id=cast(str, data.get("chunk_id")) if data.get("chunk_id") is not None else None,
            line_start=(
                cast(int, data.get("line_start")) if data.get("line_start") is not None else None
            ),
            line_end=cast(int, data.get("line_end")) if data.get("line_end") is not None else None,
            metadata=(
                cast(dict[str, object], data.get("metadata"))
                if data.get("metadata") is not None
                else None
            ),
        )

    @property
    def role_weight(self: Node) -> float:
        """Get importance weight based on node type."""
        return ROLE_WEIGHTS.get(self.type, DEFAULT_ROLE_WEIGHT)

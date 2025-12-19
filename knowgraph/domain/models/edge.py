"""Edge value object - immutable representation of a relationship."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from knowgraph.shared.types import EdgeType


@dataclass(frozen=True)
class Edge:
    """A directed edge between two nodes in the knowledge graph.

    Represents a relationship with type-specific semantics and confidence scoring.

    Attributes
    ----------
        source: Source node UUID
        target: Target node UUID
        type: Relationship type (semantic)
        score: Strength/confidence [0.0, 1.0]
        created_at: Unix timestamp of creation
        metadata: Type-specific attributes as key-value pairs

    """

    source: UUID
    target: UUID
    type: EdgeType
    score: float
    created_at: int
    metadata: dict[str, str]

    def __post_init__(self: Edge) -> None:
        """Validate edge invariants."""
        if self.source == self.target:
            raise ValueError("Self-loops are not allowed")
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Score must be in [0.0, 1.0], got {self.score}")
        if not isinstance(self.metadata, dict):
            raise ValueError("Metadata must be a dictionary")

    def to_dict(self: Edge) -> dict[str, object]:
        """Serialize edge to dictionary for JSONL storage."""
        return {
            "source": str(self.source),
            "target": str(self.target),
            "type": self.type,
            "score": self.score,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Edge:
        """Deserialize edge from dictionary."""
        from typing import cast
        from uuid import UUID

        return cls(
            source=UUID(cast(str, data["source"])),
            target=UUID(cast(str, data["target"])),
            type=cast(EdgeType, data["type"]),
            score=cast(float, data["score"]),
            created_at=cast(int, data["created_at"]),
            metadata=cast(dict[str, str], data.get("metadata", {})),
        )

    # is_semantic removed as it was unused helper method

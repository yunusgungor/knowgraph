"""Custom exception types for KnowGraph system."""


class KnowGraphError(Exception):
    """Base exception for all KnowGraph errors."""

    def __init__(
        self: "KnowGraphError", message: str, details: dict[str, object] | None = None
    ) -> None:
        """Initialize KnowGraphError."""
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(KnowGraphError):
    """Raised when input validation fails."""


class StorageError(KnowGraphError):
    """Raised when storage operations fail."""


class IndexingError(KnowGraphError):
    """Raised when indexing operations fail."""


class QueryError(KnowGraphError):
    """Raised when query operations fail."""


class EmbeddingError(KnowGraphError):
    """Raised when embedding generation fails."""


class ConfigurationError(KnowGraphError):
    """Raised when configuration is invalid."""


class GraphConstructionError(KnowGraphError):
    """Raised when graph construction fails."""


class ExportError(KnowGraphError):
    """Raised when export operations fail."""

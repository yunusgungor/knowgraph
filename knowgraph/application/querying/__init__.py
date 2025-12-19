"""Querying use cases - Graph querying and context assembly."""

from knowgraph.application.querying.conversation_search import (
    enrich_with_conversations,
    search_bookmarks,
)
from knowgraph.application.querying.hierarchical_lifting import (
    lift_hierarchical_context,
)
from knowgraph.application.querying.query_engine import (
    QueryEngine,
    QueryResult,
)

__all__ = [
    # Core query
    "QueryEngine",
    "QueryResult",
    "enrich_with_conversations",
    # Hierarchical lifting
    "lift_hierarchical_context",
    # Conversation search
    "search_bookmarks",
]

"""Querying use cases - Graph querying and context assembly."""

from knowgraph.application.querying.hierarchical_lifting import (
    lift_hierarchical_context,
)
from knowgraph.application.querying.query_engine import (
    QueryEngine,
    QueryResult,
)
from knowgraph.application.querying.conversation_search import (
    search_bookmarks,
    enrich_with_conversations,
)

__all__ = [
    # Core query
    "QueryEngine",
    "QueryResult",
    # Hierarchical lifting
    "lift_hierarchical_context",
    # Conversation search
    "search_bookmarks",
    "enrich_with_conversations",
]

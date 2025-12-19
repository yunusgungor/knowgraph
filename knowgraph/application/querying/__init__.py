"""Querying use cases - Graph querying and context assembly."""

from knowgraph.application.querying.hierarchical_lifting import (
    lift_hierarchical_context,
    explain_lifted_context,
    lift_conversation_artifacts,
)
from knowgraph.application.querying.query_engine import (
    QueryEngine,
    QueryResult,
    clear_query_result_cache,
    get_query_cache_stats,
)
from knowgraph.application.querying.conversation_search import (
    search_bookmarks,
    enrich_with_conversations,
)
from knowgraph.application.querying.query_extensions import (
    query_with_conversations,
    query_with_time_filter,
    search_bookmarks_integrated,
)

__all__ = [
    # Core query
    "QueryEngine",
    "QueryResult",
    "clear_query_result_cache",
    "get_query_cache_stats",
    # Hierarchical lifting
    "lift_hierarchical_context",
    "explain_lifted_context",
    "lift_conversation_artifacts",
    # Conversation search
    "search_bookmarks",
    "enrich_with_conversations",
    # Extended queries
    "query_with_conversations",
    "query_with_time_filter",
    "search_bookmarks_integrated",
]

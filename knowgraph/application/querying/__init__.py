"""Querying use cases - Graph querying and context assembly."""

from knowgraph.application.querying.hierarchical_lifting import (
    lift_hierarchical_context,
    explain_lifted_context,
)
from knowgraph.application.querying.query_engine import (
    QueryEngine,
    QueryResult,
    clear_query_result_cache,
    get_query_cache_stats,
)

__all__ = [
    "QueryEngine",
    "QueryResult",
    "lift_hierarchical_context",
    "explain_lifted_context",
    "clear_query_result_cache",
    "get_query_cache_stats",
]

"""MCP tool handlers - extracted from large call_tool function.

This module contains individual handler functions for each MCP tool,
improving maintainability and testability.
"""

from knowgraph.adapters.mcp.handlers._resilience import (
    _global_circuit_breaker,
    _global_rate_limiter,
)
from knowgraph.adapters.mcp.handlers.conversations import (
    handle_analyze_conversations,
    handle_discover_conversations,
    handle_search_bookmarks,
    handle_tag_snippet,
)
from knowgraph.adapters.mcp.handlers.indexing import handle_index
from knowgraph.adapters.mcp.handlers.joern import (
    handle_analyze_call_graph,
    handle_export_cpg,
    handle_find_dead_code,
    handle_generate_cpg,
    handle_joern_query,
    handle_security_scan,
)
from knowgraph.adapters.mcp.handlers.misc import (
    handle_analyze_impact,
    handle_get_stats,
    handle_validate,
)
from knowgraph.adapters.mcp.handlers.query import (
    _expand_query_if_available,
    _generate_llm_answer,
    handle_batch_query,
    handle_query,
)
from knowgraph.adapters.mcp.utils import resolve_graph_path

__all__ = [
    "_expand_query_if_available",
    "_generate_llm_answer",
    "_global_circuit_breaker",
    "_global_rate_limiter",
    "handle_analyze_call_graph",
    "handle_analyze_conversations",
    "handle_analyze_impact",
    "handle_batch_query",
    "handle_discover_conversations",
    "handle_export_cpg",
    "handle_find_dead_code",
    "handle_generate_cpg",
    "handle_get_stats",
    "handle_index",
    "handle_joern_query",
    "handle_query",
    "handle_search_bookmarks",
    "handle_security_scan",
    "handle_tag_snippet",
    "handle_validate",
]

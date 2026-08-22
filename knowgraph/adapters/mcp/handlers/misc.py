"""Miscellaneous MCP tool handlers."""

import json
from pathlib import Path
from typing import Any

import mcp.types as types

from knowgraph.adapters.mcp.handlers._resilience import _global_circuit_breaker
from knowgraph.adapters.mcp.methods import analyze_path_impact_report
from knowgraph.adapters.mcp.utils import resolve_graph_path
from knowgraph.application.querying.query_engine import QueryEngine
from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.domain.algorithms.graph_validator import validate_graph_consistency
from knowgraph.infrastructure.storage.manifest import Manifest
from knowgraph.shared.refactoring import (
    build_error_response,
    build_graph_stats_response,
    build_validation_response,
    format_impact_result,
    validate_required_argument,
)
from knowgraph.shared.tracing import trace_operation


async def handle_analyze_impact(
    arguments: dict[str, Any],
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_analyze_impact tool with circuit breaker protection and tracing.

    Protected by circuit breaker for resilience.

    Args:
    ----
        arguments: Tool arguments
        project_root: Project root path

    Returns:
    -------
        List of text content responses
    """
    with trace_operation(
        "mcp_analyze_impact", metadata={"element": arguments.get("element", "")[:100]}
    ) as trace:
        # Apply circuit breaker protection
        async def execute_analysis():
            if error := validate_required_argument(arguments, "element"):
                trace.add_event("validation_error", {"error": error})
                return [types.TextContent(type="text", text=error)]

            element = arguments.get("element")
            max_hops = arguments.get("max_hops", 4)
            mode = arguments.get("mode", "semantic")

            graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
            graph_path = resolve_graph_path(graph_path_arg, project_root)

            trace.add_event("analysis_params", {"mode": mode, "max_hops": max_hops})

            try:
                engine = QueryEngine(graph_path)
                if mode == "path":
                    # Path analysis uses specialized report generator
                    return analyze_path_impact_report(element, graph_path, max_hops)
                else:
                    # Semantic analysis uses QueryEngine
                    result = await engine.analyze_impact_async(element, max_hops)

                trace.add_event(
                    "analysis_completed",
                    {
                        "affected_nodes": (
                            result.active_subgraph_size
                            if hasattr(result, "active_subgraph_size")
                            else 0
                        )
                    },
                )
                return [types.TextContent(type="text", text=format_impact_result(result))]
            except Exception as e:
                trace.record_exception(e)
                return [
                    types.TextContent(
                        type="text", text=build_error_response(e, "Impact analysis failed")
                    )
                ]

        return await _global_circuit_breaker.call(execute_analysis)


async def handle_validate(
    arguments: dict[str, Any],
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_validate tool.

    Args:
    ----
        arguments: Tool arguments
        project_root: Project root path

    Returns:
    -------
        List of text content responses
    """
    graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
    graph_path = resolve_graph_path(graph_path_arg, project_root)

    try:
        result = validate_graph_consistency(graph_path)
        message = build_validation_response(result)
        return [types.TextContent(type="text", text=message)]
    except Exception as e:
        return [types.TextContent(type="text", text=build_error_response(e, "Validation failed"))]


async def handle_get_stats(
    arguments: dict[str, Any],
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_get_stats tool.

    Args:
    ----
        arguments: Tool arguments
        project_root: Project root path

    Returns:
    -------
        List of text content responses
    """
    graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
    graph_path = resolve_graph_path(graph_path_arg, project_root)

    manifest_path = graph_path / "metadata" / "manifest.json"

    if not manifest_path.exists():
        return [types.TextContent(type="text", text="No manifest found. Graph might be empty.")]

    try:
        # Use real-time node/edge counting instead of manifest for accuracy
        # Manifest can be outdated when nodes are added via tag_snippet
        from knowgraph.infrastructure.storage.filesystem import (
            list_all_nodes,
            read_all_edges,  # Changed from list_all_edges (which is a stub)
        )

        node_ids = list_all_nodes(graph_path)
        edges = read_all_edges(graph_path)  # Read actual edges from JSONL

        # Still read manifest for version and file count
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        manifest = Manifest.from_dict(data)

        # Override node/edge counts with real-time values
        manifest.node_count = len(node_ids)
        manifest.edge_count = len(edges)

        # Count semantic edges
        semantic_edges = [e for e in edges if e.type == "semantic"]
        manifest.semantic_edge_count = len(semantic_edges)

        stats = build_graph_stats_response(manifest)
        return [types.TextContent(type="text", text=stats)]
    except Exception as e:
        return [types.TextContent(type="text", text=build_error_response(e, "Error reading stats"))]
"""Indexing MCP tool handlers."""

from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server import Server

from knowgraph.adapters.mcp.methods import index_graph
from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.infrastructure.detection.graph_store_locator import resolve_graph_store
from knowgraph.shared.progress import ProgressNotifier
from knowgraph.shared.refactoring import (
    build_error_response,
    validate_required_argument,
)
from knowgraph.shared.tracing import trace_operation


async def handle_index(
    arguments: dict[str, Any],
    provider: Any,
    project_root: Path,
    server: Server | None = None,
) -> list[types.TextContent]:
    """Handle knowgraph_index tool with circuit breaker protection and tracing.

    Protected by circuit breaker for resilience.

    Args:
    ----
        arguments: Tool arguments
        provider: Intelligence provider for LLM
        project_root: Project root path
        server: MCP server instance for progress notifications

    Returns:
    -------
        List of text content responses
    """
    with trace_operation(
        "mcp_index", metadata={"input_path": (arguments.get("input_path") or "")[:100]}
    ) as trace:
        try:
            # Accept `source_path` as a backward-compatible alias so callers can
            # use the same argument name as knowgraph_generate_cpg.
            if not arguments.get("input_path") and arguments.get("source_path"):
                arguments["input_path"] = arguments["source_path"]

            if error := validate_required_argument(arguments, "input_path"):
                trace.add_event("validation_error", {"error": error})
                return [types.TextContent(type="text", text=error)]

            input_path = arguments.get("input_path")
            resume_mode = arguments.get("resume", False)
            output_path = arguments.get("output_path", DEFAULT_GRAPH_STORE_PATH)
            gc = arguments.get("gc", False)

            graph_path = resolve_graph_store(output_path, root_dir=project_root)
            trace.add_event("paths_resolved", {"graph_path": str(graph_path)[:100]})

            # Extract additional parameters for repository/code directory indexing
            include_patterns = arguments.get("include_patterns")
            exclude_patterns = arguments.get("exclude_patterns")
            access_token = arguments.get("access_token")

            trace.add_event(
                "indexing_started",
                {
                    "resume": resume_mode,
                    "gc": gc,
                    "has_patterns": bool(include_patterns or exclude_patterns),
                },
            )

            # Create progress notifier for real-time updates
            progress = ProgressNotifier(server, "Indexing") if server else None

            if progress:
                await progress.start(90, f"Starting indexing for {input_path[:50]}...")

            async def progress_callback(stage: str, current: int, total: int, message: str) -> None:
                """Callback for progress updates from run_index."""
                if progress:
                    # Map 9 steps to 90 units (10 per step) for smoother progress
                    progress_value = current * 10
                    await progress.update(progress_value, f"[{stage}] {message}")

            result = await index_graph(
                input_path,
                graph_path,
                provider,
                resume_mode,
                gc,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                access_token=access_token,
                progress_callback=progress_callback if progress else None,
            )

            trace.add_event("indexing_completed", {"success": True})
            return result

        except Exception as e:
            trace.record_exception(e)
            return [types.TextContent(type="text", text=build_error_response(e, "Indexing failed"))]

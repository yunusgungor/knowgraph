"""MCP tool handlers - extracted from large call_tool function.

This module contains individual handler functions for each MCP tool,
improving maintainability and testability.
"""

import json
from pathlib import Path
from typing import Any

import mcp.types as types

from knowgraph.adapters.mcp.methods import analyze_path_impact_report, index_graph
from knowgraph.adapters.mcp.utils import resolve_graph_path
from knowgraph.application.querying.query_engine import QueryEngine
from knowgraph.application.querying.query_expansion import QueryExpander
from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.domain.algorithms.graph_validator import validate_graph_consistency
from knowgraph.infrastructure.storage.manifest import Manifest
from knowgraph.shared.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from knowgraph.shared.rate_limiter import (
    RateLimiter as SharedRateLimiter,
)
from knowgraph.shared.refactoring import (
    build_conversation_discovery_response,
    build_error_response,
    build_graph_stats_response,
    build_llm_prompt,
    build_validation_response,
    extract_query_parameters,
    format_impact_result,
    validate_required_argument,
)
from knowgraph.shared.tracing import trace_operation
from knowgraph.shared.versioning import (
    get_current_version,
    negotiate_version,
)

# Global resilience patterns - shared across all handlers
_global_circuit_breaker = CircuitBreaker(
    name="mcp_handlers",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        timeout=60.0,  # Use 'timeout' not 'recovery_timeout'
        success_threshold=3,  # Use 'success_threshold' not 'half_open_max_calls'
    ),
)

_global_rate_limiter = SharedRateLimiter(
    rate=10,  # 10 requests
    period=1.0,  # per second
    algorithm="token_bucket",
    burst_size=20,
)


async def handle_query(
    arguments: dict[str, Any],
    provider: Any,
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_query tool with resilience patterns.

    Protected by circuit breaker and rate limiter.

    Args:
    ----
        arguments: Tool arguments
        provider: Intelligence provider for LLM
        project_root: Project root path

    Returns:
    -------
        List of text content responses
    """
    # Tracing context for observability
    with trace_operation(
        "mcp_query", metadata={"query": arguments.get("query", "")[:100]}
    ) as trace:
        try:
            # Rate limiting - use unique identifier for tracking
            identifier = arguments.get("user_id", "default")
            await _global_rate_limiter.allow(identifier)
            trace.add_event("rate_limit_passed", {"identifier": identifier})

            # Version negotiation
            requested_version = arguments.get("api_version")
            if requested_version:
                try:
                    version = negotiate_version(requested_version)
                    trace.add_event("version_negotiated", {"version": str(version)})
                except ValueError as e:
                    trace.add_event("version_error", {"error": str(e)})
                    return [
                        types.TextContent(
                            type="text",
                            text=f"API Version Error: {e}\nCurrent version: {get_current_version()}",
                        )
                    ]

            query = arguments.get("query")
            if error := validate_required_argument(arguments, "query"):
                trace.add_event("validation_error", {"error": error})
                return [types.TextContent(type="text", text=error)]

            graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
            graph_path = resolve_graph_path(graph_path_arg, project_root)

            # Wrap query execution with circuit breaker
            async def execute_query():
                engine = QueryEngine(graph_path)
                params = extract_query_parameters(arguments)

                # Query Expansion (now supports generic provider)
                if params["expand_query"]:
                    query_expanded = await _expand_query_if_available(query, provider)
                    trace.add_event(
                        "query_expanded", {"original": query[:50], "expanded": query_expanded[:50]}
                    )
                else:
                    query_expanded = query

                result = await engine.query_async(
                    query_expanded,
                    top_k=params["top_k"],
                    max_hops=params["max_hops"],
                    max_tokens=params["max_tokens"],
                    with_explanation=params["with_explanation"],
                    enable_hierarchical_lifting=params["enable_hierarchical_lifting"],
                    lift_levels=params["lift_levels"],
                )
                return result, params

            # Execute with circuit breaker protection
            result, params = await _global_circuit_breaker.call(execute_query)
            trace.add_event(
                "query_executed",
                {
                    "nodes_retrieved": result.active_subgraph_size,
                    "execution_time": result.execution_time,
                },
            )

            # Generate Answer using LLM Delegation
            answer = result.context

            if provider:
                answer = await _generate_llm_answer(
                    query, result, params["system_prompt"], params["with_explanation"], provider
                )
                trace.add_event("llm_answer_generated", {"length": len(answer)})

            trace.add_event("query_completed", {"success": True})
            return [types.TextContent(type="text", text=answer)]

        except Exception as e:
            trace.record_exception(e)
            return [
                types.TextContent(
                    type="text", text=build_error_response(e, "Error executing query")
                )
            ]


async def _expand_query_if_available(query: str, provider: Any) -> str:
    """Expand query using available provider."""
    try:
        if provider:
            expander = QueryExpander(intelligence_provider=provider)
            expansion_terms = await expander.expand_query_async(query)
            if expansion_terms:
                return f"{query} {' '.join(expansion_terms)}"
        else:
            # Fall back to OpenAI env vars
            import os

            if os.getenv("KNOWGRAPH_API_KEY"):
                llm_model = os.getenv("KNOWGRAPH_LLM_MODEL", "amazon/nova-2-lite-v1:free")
                expander = QueryExpander(provider="openai", model=llm_model)
                expansion_terms = expander.expand_query(query)
                if expansion_terms:
                    return f"{query} {' '.join(expansion_terms)}"
    except Exception:
        pass

    return query


async def _generate_llm_answer(
    query: str,
    result: Any,
    system_prompt: str | None,
    with_explanation: bool,
    provider: Any,
) -> str:
    """Generate answer using LLM provider."""
    explanation_data = None
    if with_explanation and result.explanation:
        explanation_data = json.dumps(result.explanation.to_dict(), indent=2, default=str)

    prompt = build_llm_prompt(query, result.context, system_prompt, explanation_data)

    try:
        generated_answer = await provider.generate_text(prompt)
        if generated_answer:
            return generated_answer
    except Exception as e:
        return f"{result.context}\n\n[Generation Error: {e!s}]"

    return result.context


async def handle_index(
    arguments: dict[str, Any],
    provider: Any,
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_index tool with circuit breaker protection and tracing.

    Protected by circuit breaker for resilience.

    Args:
    ----
        arguments: Tool arguments
        provider: Intelligence provider for LLM
        project_root: Project root path

    Returns:
    -------
        List of text content responses
    """
    with trace_operation(
        "mcp_index", metadata={"input_path": arguments.get("input_path", "")[:100]}
    ) as trace:
        try:
            if error := validate_required_argument(arguments, "input_path"):
                trace.add_event("validation_error", {"error": error})
                return [types.TextContent(type="text", text=error)]

            input_path = arguments.get("input_path")
            resume_mode = arguments.get("resume", False)
            output_path = arguments.get("output_path", DEFAULT_GRAPH_STORE_PATH)
            gc = arguments.get("gc", False)

            graph_path = resolve_graph_path(output_path, project_root)
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

            result = await index_graph(
                input_path,
                graph_path,
                provider,
                resume_mode,
                gc,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                access_token=access_token,
            )

            trace.add_event("indexing_completed", {"success": True})
            return result

        except Exception as e:
            trace.record_exception(e)
            return [types.TextContent(type="text", text=build_error_response(e, "Indexing failed"))]


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
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)

        manifest = Manifest.from_dict(data)
        stats = build_graph_stats_response(manifest)
        return [types.TextContent(type="text", text=stats)]
    except Exception as e:
        return [types.TextContent(type="text", text=build_error_response(e, "Error reading stats"))]


async def handle_discover_conversations(
    arguments: dict[str, Any],
    provider: Any,
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_discover_conversations tool.

    Args:
    ----
        arguments: Tool arguments
        provider: Intelligence provider for LLM
        project_root: Project root path

    Returns:
    -------
        List of text content responses
    """
    from knowgraph.infrastructure.detection.conversation_discovery import (
        discover_all_conversations,
    )

    graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
    graph_path = resolve_graph_path(graph_path_arg, project_root)
    editor_filter = arguments.get("editor", "all")

    try:
        # Discover all conversations
        discovered = discover_all_conversations()

        if not discovered:
            return [
                types.TextContent(
                    type="text",
                    text="No conversations found from any editor.\n\n"
                    "Make sure you have one of these editors installed:\n"
                    "  - Antigravity (Gemini)\n"
                    "  - Cursor\n"
                    "  - VSCode with GitHub Copilot",
                )
            ]

        # Filter by editor if specified
        if editor_filter != "all":
            discovered = {k: v for k, v in discovered.items() if k == editor_filter}

        # Index all discovered conversations
        indexed_count = 0
        failed_count = 0

        for editor_name, files in discovered.items():
            for file_path in files:
                try:
                    await index_graph(
                        str(file_path),
                        graph_path,
                        provider,
                        resume_mode=False,
                        gc=False,
                    )
                    indexed_count += 1
                except Exception:
                    failed_count += 1

        # Format response
        response = build_conversation_discovery_response(
            discovered, indexed_count, failed_count, graph_path
        )

        return [types.TextContent(type="text", text=response)]

    except Exception as e:
        return [
            types.TextContent(
                type="text", text=build_error_response(e, "Error discovering conversations")
            )
        ]


async def handle_tag_snippet(
    arguments: dict[str, Any],
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_tag_snippet tool.

    Args:
    ----
        arguments: Tool arguments
        project_root: Project root path

    Returns:
    -------
        List of text content responses
    """
    from knowgraph.application.tagging.snippet_tagger import (
        create_tagged_snippet,
        index_tagged_snippet,
    )

    tag = arguments.get("tag")
    snippet = arguments.get("snippet")

    if not tag or not snippet:
        return [
            types.TextContent(type="text", text="Error: Both 'tag' and 'snippet' are required.")
        ]

    graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
    graph_path = resolve_graph_path(graph_path_arg, project_root)
    conversation_id = arguments.get("conversation_id")
    user_question = arguments.get("user_question")

    try:
        # Create tagged snippet node
        tagged_node = create_tagged_snippet(
            tag=tag,
            content=snippet,
            conversation_id=conversation_id,
            user_question=user_question,
        )

        # Index the snippet
        await index_tagged_snippet(tagged_node, graph_path)

        response = (
            f"✅ Snippet tagged successfully!\n\n"
            f"**Tag**: `{tag}`\n"
            f"**Content Preview**: {snippet[:100]}{'...' if len(snippet) > 100 else ''}\n\n"
            f"You can retrieve this later by mentioning the tag in your queries."
        )

        return [types.TextContent(type="text", text=response)]

    except Exception as e:
        return [
            types.TextContent(type="text", text=build_error_response(e, "Error tagging snippet"))
        ]


async def handle_batch_query(
    arguments: dict[str, Any],
    provider: Any,
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_batch_query tool with rate limiting.

    Protected by rate limiter for batch operations.

    Args:
    ----
        arguments: Tool arguments
        provider: Intelligence provider for LLM
        project_root: Project root path

    Returns:
    -------
        List of text content responses
    """
    # Rate limiting for batch operations
    identifier = arguments.get("user_id", "default")
    await _global_rate_limiter.allow(identifier)

    queries = arguments.get("queries", [])

    if not queries or not isinstance(queries, list):
        return [types.TextContent(type="text", text="Error: queries must be a non-empty list.")]

    graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
    graph_path = resolve_graph_path(graph_path_arg, project_root)

    try:
        # Shared parameters for all queries
        top_k = arguments.get("top_k", 20)
        max_hops = arguments.get("max_hops", 4)
        max_tokens = arguments.get("max_tokens", 3000)
        enable_hierarchical_lifting = arguments.get("enable_hierarchical_lifting", True)
        lift_levels = arguments.get("lift_levels", 2)

        engine = QueryEngine(graph_path)

        # Use async batch query for better performance
        results_list = await engine.batch_query_async(
            queries=queries,
            top_k=top_k,
            max_hops=max_hops,
            max_tokens=max_tokens,
            enable_hierarchical_lifting=enable_hierarchical_lifting,
            lift_levels=lift_levels,
        )

        # Format results with LLM generation if provider available
        results = []
        for query, result in zip(queries, results_list):
            # Generate answer with LLM if provider available
            answer = result.context
            if provider and result.answer:  # Only if we have context
                try:
                    prompt = build_llm_prompt(query, result.context)
                    generated_answer = await provider.generate_text(prompt)
                    if generated_answer:
                        answer = generated_answer
                except Exception:
                    pass

            results.append(
                {
                    "query": query,
                    "answer": answer,
                    "nodes_retrieved": len(result.seed_nodes),
                    "execution_time": result.execution_time,
                }
            )

        # Format results as text
        output = f"Batch Query Results ({len(queries)} queries)\n" + "=" * 50 + "\n\n"
        for i, res in enumerate(results, 1):
            output += f"Query {i}: {res.get('query', 'N/A')}\n"
            if "error" in res:
                output += f"Error: {res['error']}\n"
            else:
                output += f"Answer: {res.get('answer', 'N/A')}\n"
                output += f"Nodes: {res.get('nodes_retrieved', 0)}, Time: {res.get('execution_time', 0):.2f}s\n"
            output += "\n"

        return [types.TextContent(type="text", text=output)]

    except Exception as e:
        return [
            types.TextContent(
                type="text", text=build_error_response(e, "Error executing batch query")
            )
        ]

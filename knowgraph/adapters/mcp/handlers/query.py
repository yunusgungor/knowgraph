"""Query MCP tool handlers."""

import asyncio
import json
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server import Server

from knowgraph.adapters.mcp.handlers._resilience import (
    _global_circuit_breaker,
    _global_rate_limiter,
    logger,
)
from knowgraph.infrastructure.detection.graph_store_locator import resolve_graph_store
from knowgraph.application.querying.query_engine import QueryEngine
from knowgraph.application.querying.query_expansion import QueryExpander
from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.shared.progress import ProgressNotifier
from knowgraph.shared.refactoring import (
    build_error_response,
    build_llm_prompt,
    extract_query_parameters,
    validate_required_argument,
)
from knowgraph.shared.tracing import trace_operation
from knowgraph.shared.versioning import (
    get_current_version,
    negotiate_version,
)

# Cache of generated LLM answers keyed by prompt hash. The same query plus the
# same retrieval context yields the same prompt, so a repeated question would
# otherwise re-bill the LLM on every call. Bounded to avoid unbounded memory.
_llm_answer_cache: dict[str, str] = {}
_LLM_ANSWER_CACHE_MAX = 256


def _llm_answer_key(prompt: str) -> str:
    """Return a stable key for a generated-answer prompt."""
    import hashlib

    return hashlib.sha256(prompt.encode("utf-8", errors="replace")).hexdigest()


async def handle_query(
    arguments: dict[str, Any],
    provider: Any,
    project_root: Path,
    server: Server | None = None,
) -> list[types.TextContent]:
    """Handle knowgraph_query tool with resilience patterns.

    Protected by circuit breaker and rate limiter.

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
    # Tracing context for observability
    with trace_operation(
        "mcp_query", metadata={"query": arguments.get("query", "")[:100]}
    ) as trace:
        # Create progress notifier for real-time updates
        progress = ProgressNotifier(server, "Query Search") if server else None

        try:
            if progress:
                await progress.start(5, "Initializing semantic search...")
                await progress.update(1, "🔍 Starting semantic search...")

            # Rate limiting - use unique identifier for tracking
            identifier = arguments.get("user_id", "default")
            await _global_rate_limiter.allow(identifier)
            trace.add_event("rate_limit_passed", {"identifier": identifier})

            # Version negotiation. The negotiated version's advertised features
            # are surfaced (telemetry) so version gating is observable, and an
            # unsupported version is rejected up front.
            requested_version = arguments.get("api_version")
            min_api_version = arguments.get("min_api_version")
            if requested_version:
                try:
                    version = negotiate_version(requested_version, min_api_version)
                    features = []
                    try:
                        from knowgraph.shared.versioning import get_version_info

                        info = get_version_info(version)
                        features = list(info.features) if info else []
                    except Exception:
                        pass
                    trace.add_event(
                        "version_negotiated",
                        {"version": str(version), "features": features},
                    )
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
                if progress:
                    await progress.error(f"Validation error: {error}")
                return [types.TextContent(type="text", text=error)]

            graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
            graph_path = resolve_graph_store(graph_path_arg, root_dir=project_root)

            # Validate graph store exists and has nodes
            if not graph_path.exists():
                error_msg = f"Graph store not found at {graph_path}. Please run indexing first."
                trace.add_event("graph_store_error", {"path": str(graph_path)})
                if progress:
                    await progress.error(error_msg)
                return [types.TextContent(type="text", text=error_msg)]

            # Check if provider is available for LLM features
            if not provider:
                import os
                api_keys = {
                    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
                    "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
                }
                available_keys = [k for k, v in api_keys.items() if v]

                if not available_keys:
                    warning_msg = (
                        "⚠️ No LLM provider configured. Query will return raw context only.\n"
                        "To enable AI-generated answers, set one of: OPENAI_API_KEY, ANTHROPIC_API_KEY\n\n"
                    )
                    trace.add_event("provider_warning", {"message": "No API keys found"})
                else:
                    warning_msg = ""
            else:
                warning_msg = ""

            # NEW: Query Classification for intelligent routing
            from knowgraph.application.query.code_query_handler import CodeQueryHandler
            from knowgraph.application.query.query_classifier import QueryClassifier, QueryType

            classifier = QueryClassifier()
            query_type = classifier.classify(query)

            logger.info(f"Query classified as: {query_type.value} - '{query[:50]}'")

            # Route based on query type
            if query_type == QueryType.CODE:
                # CODE-only query → Use Joern tools
                if progress:
                    await progress.update(1, f'🔧 Code Analysis: "{query[:50]}..."')

                code_handler = CodeQueryHandler(graph_path)
                code_results = await code_handler.handle(query)

                # Format and return code analysis results
                output = code_handler.format_results(code_results)

                return [types.TextContent(type="text", text=output)]

            elif query_type == QueryType.HYBRID:
                # HYBRID query → Run both text and code search
                if progress:
                    await progress.update(1, f'🔄 Hybrid Search: "{query[:50]}..."')

                # Code analysis is run inside QueryEngine.query_async, which
                # awaits CodeQueryHandler.handle() for CODE/HYBRID queries and
                # returns the combined result. No separate coroutine here.

            # TEXT or HYBRID queries continue with normal semantic search

            if progress:
                query_label = "hybrid" if query_type == QueryType.HYBRID else "text"
                await progress.update(2, f"📝 Searching ({query_label})...")

            # Wrap query execution with circuit breaker
            async def execute_query():
                if progress:
                    await progress.update(2, "🔧 Initializing query engine...")

                engine = QueryEngine(graph_path, provider=provider)
                params = extract_query_parameters(arguments)

                # Query Expansion (now supports generic provider)
                if params["expand_query"]:
                    if progress:
                        await progress.update(2, "🧮 Expanding query with AI...")
                    query_expanded = await _expand_query_if_available(query, provider)
                    trace.add_event(
                        "query_expanded", {"original": query[:50], "expanded": query_expanded[:50]}
                    )
                else:
                    query_expanded = query

                if progress:
                    await progress.update(3, f"🔎 Searching graph (top_k={params['top_k']}, max_hops={params['max_hops']})...")

                result = await engine.query_async(
                    query_expanded,
                    top_k=params["top_k"],
                    max_hops=params["max_hops"],
                    max_tokens=params["max_tokens"],
                    with_explanation=params["with_explanation"],
                    enable_hierarchical_lifting=params["enable_hierarchical_lifting"],
                    lift_levels=params["lift_levels"],
                    enable_grounding=params["enable_grounding"],
                )

                if progress:
                    await progress.update(4, f"✅ Found {result.active_subgraph_size} relevant nodes")

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
                if progress:
                    await progress.update(4, "🤖 Generating AI answer from context...")
                answer = await _generate_llm_answer(
                    query, result, params["system_prompt"], params["with_explanation"], provider
                )
                trace.add_event("llm_answer_generated", {"length": len(answer)})

            if progress:
                await progress.complete("✅ Search completed successfully!")

            trace.add_event("query_completed", {"success": True})
            return [types.TextContent(type="text", text=answer)]

        except Exception as e:
            trace.record_exception(e)
            if progress:
                await progress.error(f"Query failed: {e!s}")
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

    # Skip re-billing when the exact prompt was answered before.
    cache_key = _llm_answer_key(prompt)
    cached = _llm_answer_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        generated_answer = await provider.generate_text(prompt)
        if generated_answer:
            if len(_llm_answer_cache) >= _LLM_ANSWER_CACHE_MAX:
                _llm_answer_cache.clear()  # simple bounded reset
            _llm_answer_cache[cache_key] = generated_answer
            return generated_answer
    except Exception as e:
        return f"{result.context}\n\n[Generation Error: {e!s}]"

    return result.context


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
    graph_path = resolve_graph_store(graph_path_arg, root_dir=project_root)

    try:
        # Shared parameters for all queries
        top_k = arguments.get("top_k", 20)
        max_hops = arguments.get("max_hops", 4)
        max_tokens = arguments.get("max_tokens", 3000)
        enable_hierarchical_lifting = arguments.get("enable_hierarchical_lifting", True)
        lift_levels = arguments.get("lift_levels", 2)

        engine = QueryEngine(graph_path, provider=provider)

        # Use async batch query for better performance
        results_list = await engine.batch_query_async(
            queries=queries,
            top_k=top_k,
            max_hops=max_hops,
            max_tokens=max_tokens,
            enable_hierarchical_lifting=enable_hierarchical_lifting,
            lift_levels=lift_levels,
        )

        # Format results with LLM generation if provider available (PARALLELIZED)
        async def generate_answer_for_result(query: str, result: Any) -> dict:
            """Generate LLM answer for a single query result."""
            answer = result.context
            if provider and result.answer:  # Only if we have context
                try:
                    prompt = build_llm_prompt(query, result.context)
                    cache_key = _llm_answer_key(prompt)
                    cached = _llm_answer_cache.get(cache_key)
                    if cached is not None:
                        answer = cached
                    else:
                        generated_answer = await provider.generate_text(prompt)
                        if generated_answer:
                            if len(_llm_answer_cache) >= _LLM_ANSWER_CACHE_MAX:
                                _llm_answer_cache.clear()
                            _llm_answer_cache[cache_key] = generated_answer
                            answer = generated_answer
                except Exception:
                    pass  # Use context as fallback

            return {
                "query": query,
                "answer": answer,
                "nodes_retrieved": len(result.seed_nodes),
                "execution_time": result.execution_time,
            }

        # Parallel LLM generation for all queries
        results = await asyncio.gather(
            *[generate_answer_for_result(q, r) for q, r in zip(queries, results_list)]
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

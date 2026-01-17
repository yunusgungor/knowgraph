"""MCP tool handlers - extracted from large call_tool function.

This module contains individual handler functions for each MCP tool,
improving maintainability and testability.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server import Server

from knowgraph.adapters.mcp.methods import analyze_path_impact_report, index_graph
from knowgraph.adapters.mcp.utils import resolve_graph_path
from knowgraph.application.querying.query_engine import QueryEngine
from knowgraph.application.querying.query_expansion import QueryExpander
from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.domain.algorithms.graph_validator import validate_graph_consistency
from knowgraph.infrastructure.storage.manifest import Manifest
from knowgraph.shared.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from knowgraph.shared.progress import ProgressNotifier
from knowgraph.shared.rate_limiter import (
    RateLimiter as SharedRateLimiter,
)
from knowgraph.shared.refactoring import (
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

# Initialize logger
logger = logging.getLogger(__name__)

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
                if progress:
                    await progress.error(f"Validation error: {error}")
                return [types.TextContent(type="text", text=error)]

            graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
            graph_path = resolve_graph_path(graph_path_arg, project_root)

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
                # HYBRID query → Run both text and code search in parallel
                if progress:
                    await progress.update(1, f'🔄 Hybrid Search: "{query[:50]}..."')

                logger.info("Running parallel text + code search")

                # Run code analysis (non-blocking)
                code_handler = CodeQueryHandler(graph_path)
                code_task = code_handler.handle(query)

                # Continue with text search below
                # Code results will be merged after text search completes

            # TEXT or HYBRID queries continue with normal semantic search

            if progress:
                query_label = "hybrid" if query_type == QueryType.HYBRID else "text"
                await progress.update(2, f"📝 Searching ({query_label})...")

            # Wrap query execution with circuit breaker
            async def execute_query():
                if progress:
                    await progress.update(2, "🔧 Initializing query engine...")

                engine = QueryEngine(graph_path)
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

async def handle_search_bookmarks(
    arguments: dict[str, Any],
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_search_bookmarks tool.

    Search tagged snippets with semantic matching.

    Args:
    ----
        arguments: Tool arguments
        project_root: Project root path

    Returns:
    -------
        List of text content responses

    """
    with trace_operation(
        "mcp_search_bookmarks", metadata={"query": arguments.get("query", "")[:100]}
    ) as trace:
        try:
            # Validate required arguments
            query = arguments.get("query")
            if not query:
                return [
                    types.TextContent(type="text", text="❌ Error: 'query' argument is required")
                ]

            # Optional arguments
            top_k = arguments.get("top_k", 10)
            graph_path_arg = arguments.get("graph_path")

            # Resolve graph path
            graph_path = resolve_graph_path(graph_path_arg, project_root)

            # Search bookmarks using semantic search
            from knowgraph.application.querying.conversation_search import search_bookmarks

            results = search_bookmarks(query, graph_path, top_k=top_k)

            trace.add_event("search_completed", {"results_count": len(results)})

            # Format results
            if not results:
                return [
                    types.TextContent(type="text", text=f"No bookmarks found for query: `{query}`")
                ]

            response_lines = [f"🔍 Found {len(results)} bookmarks for: `{query}`\n"]

            for i, bookmark in enumerate(results, 1):
                tag = bookmark.metadata.get("tag", "unknown") if bookmark.metadata else "unknown"
                (
                    bookmark.content[:100] + "..."
                    if len(bookmark.content) > 100
                    else bookmark.content
                )

                response_lines.append(f"{i}. **{tag}**")
            return [types.TextContent(type="text", text="\n".join(response_lines))]

        except Exception as e:
            import traceback

            traceback.print_exc()
            trace.record_exception(e)
            return [
                types.TextContent(
                    type="text", text=build_error_response(e, "Bookmark search failed")
                )
            ]


async def handle_analyze_conversations(
    arguments: dict[str, Any],
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_analyze_conversations tool.

    Analyze conversation patterns for topics and trends.

    Args:
    ----
        arguments: Tool arguments
        project_root: Project root path

    Returns:
    -------
        List of text content responses

    """
    with trace_operation(
        "mcp_analyze_conversations", metadata={"topic": arguments.get("topic", "")[:100]}
    ) as trace:
        try:
            # Optional arguments
            topic = arguments.get("topic")
            time_window_days = int(arguments.get("time_window_days", 7))
            graph_path_arg = arguments.get("graph_path")

            # Resolve graph path
            graph_path = resolve_graph_path(graph_path_arg, project_root)

            if topic:
                # Get timeline for specific topic
                from knowgraph.application.analytics.knowledge_tracker import get_knowledge_timeline

                result = get_knowledge_timeline(topic, graph_path, time_window_days)

                trace.add_event(
                    "timeline_analyzed", {"topic": topic, "mentions": result["total_mentions"]}
                )

                response_lines = [
                    f"📊 **Knowledge Timeline: {topic}**\n",
                    f"Time window: {time_window_days} days",
                    f"Total mentions: {result['total_mentions']}",
                    f"Days with activity: {result['days_with_activity']}",
                ]

                if result["timeline"]:
                    response_lines.append("\n**Daily Activity:**")
                    for date, items in sorted(result["timeline"].items())[:10]:
                        response_lines.append(f"  {date}: {len(items)} conversation(s)")

            else:
                # Analyze trending topics
                from knowgraph.application.analytics.topic_analyzer import analyze_trending_topics

                result = analyze_trending_topics(graph_path, time_window_days)

                trace.add_event(
                    "trends_analyzed", {"conversations": result["conversations_analyzed"]}
                )

                response_lines = [
                    f"📈 **Trending Topics (Last {time_window_days} days)**\n",
                    f"Conversations analyzed: {result['conversations_analyzed']}",
                ]

                if result["trending_entities"]:
                    response_lines.append("\n**Top Entities:**")
                    for entity, count in list(result["trending_entities"].items())[:10]:
                        response_lines.append(f"  • {entity}: {count} mentions")

                if result["trending_topics"]:
                    response_lines.append("\n**Top Topics:**")
                    for topic, count in list(result["trending_topics"].items())[:10]:
                        response_lines.append(f"  • {topic}: {count} conversations")

            return [types.TextContent(type="text", text="\n".join(response_lines))]

        except Exception as e:
            trace.record_exception(e)
            return [
                types.TextContent(
                    type="text", text=build_error_response(e, "Conversation analysis failed")
                )
            ]


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
    import time
    from uuid import uuid4

    from knowgraph.domain.models.node import Node
    from knowgraph.infrastructure.detection.conversation_discovery import (
        discover_all_conversations,
    )
    from knowgraph.infrastructure.parsing.conversation_parser import (
        conversation_to_markdown,
        parse_conversation,
    )
    from knowgraph.infrastructure.parsing.hasher import hash_content
    from knowgraph.infrastructure.storage.filesystem import (
        ensure_directory,
    )
    from knowgraph.infrastructure.storage.manifest import (
        Manifest,
        read_manifest,
        write_manifest,
    )

    def count_tokens(text: str) -> int:
        """Approximate token count."""
        try:
            import tiktoken

            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except (ImportError, Exception):
            # Fallback: char count / 4
            return len(text) // 4

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

        # Ensure graph directory exists
        ensure_directory(graph_path)
        ensure_directory(graph_path / "metadata")
        ensure_directory(graph_path / "nodes")

        # Load or create manifest
        manifest = read_manifest(graph_path)
        if not manifest:
            manifest = Manifest.create_new(
                edges_filename="edges.jsonl", sparse_index_filename="sparse_index.json"
            )

        # Index all discovered conversations
        indexed_count = 0
        failed_count = 0

        # Import async filesystem
        from knowgraph.infrastructure.storage.filesystem import write_node_json_async

        # Semaphore to limit concurrent file processing
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent files

        async def process_conversation_file(editor_name: str, file_path: Path) -> bool:
            """Process a single conversation file asynchronously."""
            async with semaphore:
                try:
                    # 1. Parse conversation (CPU-bound, run in thread pool)
                    conversation = await asyncio.to_thread(parse_conversation, file_path)
                    if not conversation:
                        return False

                    # 2. Convert to markdown content
                    content = await asyncio.to_thread(conversation_to_markdown, conversation)

                    # 3. Create Node
                    try:
                        rel_path = f".conversations/{editor_name}/{file_path.name}"
                    except Exception:
                        rel_path = f".conversations/{editor_name}/{file_path.name}"

                    # Hash for dedup
                    content_hash = await asyncio.to_thread(hash_content, content)

                    node = Node(
                        id=uuid4(),
                        hash=content_hash,
                        title=f"{editor_name.title()}: {conversation.title}",
                        content=content,
                        path=rel_path,
                        type="conversation",
                        token_count=count_tokens(content),
                        created_at=int(time.time()),
                        metadata={
                            "source": editor_name,
                            "conversation_id": conversation.id,
                            "original_path": str(file_path),
                            "timestamp": conversation.created_at.isoformat(),
                        },
                    )

                    # 4. Write to disk (async for non-blocking I/O)
                    await write_node_json_async(node, graph_path)

                    # Update manifest hash map (thread-safe for dict in asyncio)
                    manifest.file_hashes[rel_path] = content_hash

                    return True

                except Exception as e:
                    print(f"Failed to index {file_path}: {e}")
                    return False

        # Process all files in parallel with controlled concurrency
        tasks = []
        for editor_name, files in discovered.items():
            for file_path in files:
                tasks.append(process_conversation_file(editor_name, file_path))

        # Execute all tasks and gather results
        results = await asyncio.gather(*tasks)
        indexed_count = sum(1 for r in results if r)
        failed_count = sum(1 for r in results if not r)

        # Update and save manifest
        if indexed_count > 0:
            manifest.node_count += indexed_count - failed_count  # Approximate increment
            # A reload of all nodes would be more accurate but slow
            # For now, increment is fine for count tracking
            manifest.updated_at = int(time.time())
            write_manifest(manifest, graph_path)

            # Run auto-linking if successful
            try:
                from knowgraph.application.indexing.post_index_hooks import auto_link_conversations

                await auto_link_conversations(graph_path)
            except Exception:
                pass

        # Build response
        response_text = f"✅ Auto-discovered {len(discovered)} editors with conversations:\n\n"

        for editor, files in discovered.items():
            response_text += f"📂 {editor.upper()}: {len(files)} conversations\n"

        response_text += "\n📥 Indexing complete:\n"
        response_text += f"  Indexed: {indexed_count} conversations\n"

        if failed_count > 0:
            response_text += f"  Failed: {failed_count} files (skipped)\n"

        response_text += f"\n📊 Graph stored in: {graph_path}"

        return [types.TextContent(type="text", text=response_text)]

    except Exception as e:
        return [
            types.TextContent(
                type="text", text=build_error_response(e, "Conversation discovery failed")
            )
        ]


async def handle_tag_snippet(
    arguments: dict[str, Any],
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_tag_snippet tool with AI auto-suggestions.

    Enhanced with:
    - Auto-tag suggestions
    - Duplicate detection
    - Similar snippet linking

    Args:
    ----
        arguments: Tool arguments
        project_root: Project root path

    Returns:
    -------
        List of text content responses

    """
    with trace_operation(
        "mcp_tag_snippet", metadata={"tag": arguments.get("tag", "")[:100]}
    ) as trace:
        try:
            # Rate limiting
            await _global_rate_limiter.allow("tag_snippet")

            # Validate required arguments
            if error := validate_required_argument(arguments, "tag"):
                trace.add_event("validation_error", {"error": error})
                return [types.TextContent(type="text", text=error)]
            tag = arguments["tag"]

            if error := validate_required_argument(arguments, "snippet"):
                trace.add_event("validation_error", {"error": error})
                return [types.TextContent(type="text", text=error)]
            snippet = arguments["snippet"]

            # Optional arguments
            conversation_id = arguments.get("conversation_id")
            user_question = arguments.get("user_question")
            graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
            auto_suggest = arguments.get("auto_suggest", True)

            # Resolve graph path
            graph_path = resolve_graph_path(graph_path_arg, project_root)

            # ENHANCEMENT: Auto-suggest tags if enabled
            suggested_tags = []
            if auto_suggest:
                from knowgraph.application.tagging.auto_tagger import auto_tag_snippet

                auto_result = auto_tag_snippet(snippet)
                suggested_tags = auto_result.get("suggested_tags", [])
                topic = auto_result.get("topic", "general")
                confidence = auto_result.get("confidence", 0.0)

                trace.add_event(
                    "auto_tagging",
                    {
                        "suggested_count": len(suggested_tags),
                        "topic": topic,
                        "confidence": confidence,
                    },
                )

            # Create tagged snippet node
            from knowgraph.application.tagging.snippet_tagger import (
                create_tagged_snippet,
                index_tagged_snippet,
            )

            snippet_node = create_tagged_snippet(
                tag=tag,
                content=snippet,
                conversation_id=conversation_id,
                user_question=user_question,
            )

            # Index snippet
            await index_tagged_snippet(snippet_node, graph_path)

            # Build response
            response_lines = [
                f"✅ Tagged snippet: `{tag}`",
                f"Snippet ID: {snippet_node.id}",
            ]

            if suggested_tags:
                response_lines.append("\n💡 **Auto-suggested tags**:")
                for sugg_tag in suggested_tags[:5]:
                    response_lines.append(f"  - `{sugg_tag}`")
                response_lines.append(f"\nConfidence: {confidence:.0%}")

            trace.add_event("snippet_tagged", {"success": True})

            return [types.TextContent(type="text", text="\n".join(response_lines))]

        except Exception as e:
            import traceback

            traceback.print_exc()
            trace.record_exception(e)
            return [
                types.TextContent(type="text", text=build_error_response(e, "Tag snippet failed"))
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

        # Format results with LLM generation if provider available (PARALLELIZED)
        async def generate_answer_for_result(query: str, result: Any) -> dict:
            """Generate LLM answer for a single query result."""
            answer = result.context
            if provider and result.answer:  # Only if we have context
                try:
                    prompt = build_llm_prompt(query, result.context)
                    generated_answer = await provider.generate_text(prompt)
                    if generated_answer:
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


# ==================== JOERN INTEGRATION HANDLERS ====================


async def handle_joern_query(arguments: dict[str, Any], PROJECT_ROOT: Path) -> list[types.TextContent]:
    """Execute native Joern DSL query.

    Allows AI assistants to run custom Joern queries or use predefined templates.
    """
    try:
        from knowgraph.application.security.joern_query_templates import (
            JoernQueryTemplate,
            get_vulnerability_query,
        )
        from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

        # Required parameters
        cpg_path_str = arguments.get("cpg_path")
        if not cpg_path_str:
            return [types.TextContent(type="text", text="Error: cpg_path is required")]

        cpg_path = Path(cpg_path_str)
        if not cpg_path.exists():
            return [types.TextContent(type="text", text=f"Error: CPG not found at {cpg_path}")]

        # Get query (direct or template)
        query = arguments.get("query")
        query_name = arguments.get("query_name")

        if query_name:
            # Use predefined template - try enum first, then vulnerability queries
            try:
                template = JoernQueryTemplate[query_name.upper()]
                query = template.value
            except KeyError:
                # Try vulnerability query
                query = get_vulnerability_query(query_name)
                if not query:
                    available = ", ".join([t.name.lower() for t in JoernQueryTemplate])
                    return [types.TextContent(
                        type="text",
                        text=f"Error: Unknown query template '{query_name}'. Available: {available}, sql_injection, buffer_overflow, command_injection, dangerous_functions"
                    )]
        elif not query:
            return [types.TextContent(type="text", text="Error: Either 'query' or 'query_name' is required")]

        timeout = arguments.get("timeout", 60)

        # Execute query
        executor = JoernQueryExecutor()
        result = executor.execute_query(cpg_path, query, timeout=timeout)

        # Format output
        output = "🔍 Joern Query Executed\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"**Query**: {query[:100]}{'...' if len(query) > 100 else ''}\n"
        output += f"**Results**: {result.node_count} nodes\n"
        output += f"**Execution Time**: {result.execution_time_ms:.0f}ms\n\n"

        if result.results:
            output += "**Results**:\n"
            for idx, res in enumerate(result.results[:20], 1):  # Limit to 20
                output += f"{idx}. {res}\n"
            if len(result.results) > 20:
                output += f"\n... and {len(result.results) - 20} more results\n"
        else:
            output += "_No results found_\n"

        return [types.TextContent(type="text", text=output)]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=build_error_response(e, "Error executing Joern query")
        )]


async def handle_security_scan(arguments: dict[str, Any], PROJECT_ROOT: Path) -> list[types.TextContent]:
    """Run security policy validation with CWE-mapped rules.

    Scans code for 10 predefined security vulnerabilities.
    """
    try:
        from knowgraph.application.security.policy_engine import PolicyEngine, Severity
        from knowgraph.infrastructure.indexing.cpg_metadata import get_cpg_path

        # Try to get CPG path from arguments or graph metadata
        cpg_path_str = arguments.get("cpg_path")
        graph_path_arg = arguments.get("graph_path")

        if not cpg_path_str and graph_path_arg:
            # Try to auto-detect CPG from graph metadata
            graph_path = resolve_graph_path(graph_path_arg, PROJECT_ROOT)
            cpg_path = get_cpg_path(graph_path)

            if not cpg_path:
                return [types.TextContent(
                    type="text",
                    text="Error: No CPG found. Either provide 'cpg_path' or run 'knowgraph_index' first to generate CPG."
                )]
        elif cpg_path_str:
            cpg_path = Path(cpg_path_str)
            if not cpg_path.exists():
                return [types.TextContent(type="text", text=f"Error: CPG not found at {cpg_path}")]
        else:
            return [types.TextContent(
                type="text",
                text="Error: Either 'cpg_path' or 'graph_path' is required"
            )]

        # Optional parameters
        severity_filter_str = arguments.get("severity_filter", "MEDIUM")
        try:
            severity_filter = Severity[severity_filter_str.upper()]
        except KeyError:
            severity_filter = Severity.MEDIUM

        # Filter policies by name if policy_names is provided
        policy_names = arguments.get("policy_names")
        engine = PolicyEngine()
        policies_to_check = None

        if policy_names:
            policies_to_check = [p for p in engine.policies if p.name in policy_names]
            if not policies_to_check:
                return [types.TextContent(
                    type="text",
                    text=f"Error: None of the specified policies found: {policy_names}"
                )]

        # Run policy validation
        violations = engine.validate_policies(
            cpg_path,
            policies=policies_to_check,
            severity_filter=severity_filter
        )

        # Format output
        output = "🔒 Security Policy Scan\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"**Scanned**: {cpg_path.name}\n"
        output += f"**Severity Filter**: {severity_filter.name}\n"
        output += f"**Violations Found**: {len(violations)}\n\n"

        if violations:
            # Group by severity - PolicyViolation is a dataclass, use attribute access
            by_severity = {}
            for v in violations:
                sev = v.severity  # attribute access
                if sev not in by_severity:
                    by_severity[sev] = []
                by_severity[sev].append(v)

            for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
                if sev in by_severity:
                    icon = "🔴" if sev == Severity.CRITICAL else "🟠" if sev == Severity.HIGH else "🟡" if sev == Severity.MEDIUM else "⚪"
                    output += f"\n{icon} **{sev.name}** ({len(by_severity[sev])} findings):\n"
                    for v in by_severity[sev][:5]:  # Limit to 5 per severity
                        # Access dataclass attributes
                        policy_name = v.policy.name if v.policy else "Unknown"
                        cwe = getattr(v.policy, "cwe", "N/A") if v.policy else "N/A"
                        output += f"  - **{policy_name}** (CWE-{cwe})\n"
                        output += f"    Location: {v.location}\n"
                        if v.policy and hasattr(v.policy, "recommendation"):
                            output += f"    💡 {v.policy.recommendation}\n"
                    if len(by_severity[sev]) > 5:
                        output += f"  _... and {len(by_severity[sev]) - 5} more {sev.name} findings_\n"
        else:
            output += "✅ **No violations found!** Code passes all security policies.\n"

        return [types.TextContent(type="text", text=output)]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=build_error_response(e, "Error running security scan")
        )]


async def handle_find_dead_code(arguments: dict[str, Any], PROJECT_ROOT: Path) -> list[types.TextContent]:
    """Detect unreachable methods using dominance analysis.

    Finds methods that have no callers (potential dead code).
    """
    try:
        from knowgraph.application.analysis.dominance_analyzer import DominanceAnalyzer

        # Required parameters
        from knowgraph.infrastructure.indexing.cpg_metadata import get_cpg_path

        # Try to get CPG path from arguments or graph metadata
        cpg_path_str = arguments.get("cpg_path")
        graph_path_arg = arguments.get("graph_path")

        if not cpg_path_str and graph_path_arg:
            # Try to auto-detect CPG from graph metadata
            graph_path = resolve_graph_path(graph_path_arg, PROJECT_ROOT)
            cpg_path = get_cpg_path(graph_path)

            if not cpg_path:
                return [types.TextContent(
                    type="text",
                    text="Error: No CPG found. Either provide 'cpg_path' or run 'knowgraph_index' first to generate CPG."
                )]
        elif cpg_path_str:
            cpg_path = Path(cpg_path_str)
            if not cpg_path.exists():
                return [types.TextContent(type="text", text=f"Error: CPG not found at {cpg_path}")]
        else:
            return [types.TextContent(
                type="text",
                text="Error: Either 'cpg_path' or 'graph_path' is required"
            )]

        # Optional parameters
        include_internal = arguments.get("include_internal", False)

        # Find dead code
        analyzer = DominanceAnalyzer()
        dead_methods = analyzer.find_dead_code(cpg_path)

        # Filter internal methods if needed
        if not include_internal:
            dead_methods = [m for m in dead_methods if not m.get("name", "").startswith("_")]

        # Format output
        output = "💀 Dead Code Detection\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"**Scanned**: {cpg_path.name}\n"
        output += f"**Dead Methods Found**: {len(dead_methods)}\n\n"

        if dead_methods:
            output += "**Unreachable Methods** (no callers):\n\n"
            for idx, method in enumerate(dead_methods[:15], 1):  # Limit to 15
                name = method.get("name", "Unknown")
                signature = method.get("signature", "")
                file_loc = method.get("filename", method.get("file", "Location not available"))

                output += f"{idx}. `{name}`\n"
                if signature:
                    output += f"   Signature: `{signature}`\n"
                output += f"   Location: {file_loc}\n\n"

            if len(dead_methods) > 15:
                output += f"_... and {len(dead_methods) - 15} more dead methods_\n\n"

            output += "💡 **Recommendations**:\n"
            output += "- Review if these methods are truly unused\n"
            output += "- Check for dynamic calls or reflection\n"
            output += "- Consider removing to reduce code complexity\n"
        else:
            output += "✅ **No dead code detected!** All methods have callers.\n"

        return [types.TextContent(type="text", text=output)]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=build_error_response(e, "Error finding dead code")
        )]


async def handle_analyze_call_graph(arguments: dict[str, Any], PROJECT_ROOT: Path) -> list[types.TextContent]:
    """Analyze call graph structure and relationships.

    Supports validation, recursive call detection, and call chain analysis.
    """
    try:
        from knowgraph.application.analysis.call_graph_analyzer import CallGraphAnalyzer

        # Required parameters
        cpg_path_str = arguments.get("cpg_path")
        analysis_type = arguments.get("analysis_type", "validate")
        graph_path_arg = arguments.get("graph_path")

        if not cpg_path_str and graph_path_arg:
            from knowgraph.infrastructure.indexing.cpg_metadata import get_cpg_path
            # Try to auto-detect CPG from graph metadata
            graph_path = resolve_graph_path(graph_path_arg, PROJECT_ROOT)
            cpg_path = get_cpg_path(graph_path)

            if not cpg_path:
                return [types.TextContent(
                    type="text",
                    text="Error: No CPG found. Either provide 'cpg_path' or run 'knowgraph_index' first to generate CPG."
                )]
        elif cpg_path_str:
            cpg_path = Path(cpg_path_str)
            if not cpg_path.exists():
                return [types.TextContent(type="text", text=f"Error: CPG not found at {cpg_path}")]
        else:
            return [types.TextContent(
                type="text",
                text="Error: Either 'cpg_path' or 'graph_path' is required"
            )]

        analyzer = CallGraphAnalyzer()

        # Route to appropriate analysis
        if analysis_type == "validate":
            result = analyzer.validate_call_graph(cpg_path)

            output = "📊 Call Graph Validation\n"
            output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            output += f"**Status**: {'✅ Valid' if result.is_valid else '❌ Invalid'}\n"
            output += f"**Methods**: {result.total_methods}\n"  # Changed from "Total Methods:"
            output += f"**Call Edges**: {result.call_edges}\n"
            output += f"**Entry Points**: {len(result.entry_points)}\n"
            output += f"**Leaf Methods**: {len(result.leaf_methods)}\n\n"

            if result.entry_points:
                output += "**Entry Points** (no callers):\n"
                for ep in result.entry_points[:10]:
                    output += f"  - `{ep}`\n"
                if len(result.entry_points) > 10:
                    output += f"  _... and {len(result.entry_points) - 10} more_\n"

            return [types.TextContent(type="text", text=output)]

        elif analysis_type == "recursive":
            recursive_methods = analyzer.find_recursive_calls(cpg_path)

            output = "🔄 Recursive Call Detection\n"
            output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            output += f"**Recursive Methods Found**: {len(recursive_methods)}\n\n"

            if recursive_methods:
                for idx, method in enumerate(recursive_methods[:10], 1):
                    name = method.get("name", "Unknown")
                    rec_type = method.get("recursion_type", "direct")
                    output += f"{idx}. `{name}` ({rec_type} recursion)\n"

                if len(recursive_methods) > 10:
                    output += f"\n_... and {len(recursive_methods) - 10} more_\n"
            else:
                output += "✅ No recursive methods detected.\n"

            return [types.TextContent(type="text", text=output)]

        elif analysis_type == "call_chain":
            method_name = arguments.get("method_name")
            target_method = arguments.get("target_method")
            max_depth = arguments.get("max_depth", 5)

            if not method_name or not target_method:
                return [types.TextContent(
                    type="text",
                    text="Error: For call_chain analysis, both 'method_name' and 'target_method' are required"
                )]

            # Use the correct method name: find_call_chains (plural)
            chains = analyzer.find_call_chains(
                cpg_path,
                from_pattern=method_name,
                to_pattern=target_method,
                max_depth=max_depth
            )

            output = "🔗 Call Chain Analysis\n"
            output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            output += f"**From**: `{method_name}`\n"
            output += f"**To**: `{target_method}`\n"
            output += f"**Max Depth**: {max_depth}\n"
            output += f"**Paths Found**: {len(chains)}\n\n"

            if chains:
                for idx, chain in enumerate(chains[:5], 1):
                    output += f"**Path {idx}**: {' → '.join(f'`{m}`' for m in chain)}\n"

                if len(chains) > 5:
                    output += f"\n_... and {len(chains) - 5} more paths_\n"
            else:
                output += "❌ No call path found between these methods.\n"
                output += "\n💡 **Tip**: Try increasing max_depth or check if methods exist in CPG\n"

            return [types.TextContent(type="text", text=output)]


        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown analysis_type '{analysis_type}'. Use 'validate', 'recursive', or 'call_chain'"
            )]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=build_error_response(e, "Error analyzing call graph")
        )]


async def handle_export_cpg(arguments: dict[str, Any], PROJECT_ROOT: Path) -> list[types.TextContent]:
    """Export CPG to various formats for visualization and CI/CD.

    Supports JSON, SARIF, Neo4j, DOT, and GraphML formats.
    """
    try:
        from knowgraph.core.joern import ExportFormat, JoernProvider
        from knowgraph.infrastructure.indexing.cpg_metadata import get_cpg_path

        # Required parameters
        cpg_path_str = arguments.get("cpg_path")
        output_path_str = arguments.get("output_path")
        format_str = arguments.get("format", "json")
        graph_path_arg = arguments.get("graph_path")

        if not cpg_path_str and graph_path_arg:
            # Try to auto-detect CPG from graph metadata
            graph_path = resolve_graph_path(graph_path_arg, PROJECT_ROOT)
            cpg_path = get_cpg_path(graph_path)

            if not cpg_path:
                return [types.TextContent(
                    type="text",
                    text="Error: No CPG found. Either provide 'cpg_path' or run 'knowgraph_index' first to generate CPG."
                )]
        elif cpg_path_str:
            cpg_path = Path(cpg_path_str)
            if not cpg_path.exists():
                return [types.TextContent(type="text", text=f"Error: CPG not found at {cpg_path}")]
        else:
            return [types.TextContent(
                type="text",
                text="Error: Either 'cpg_path' or 'graph_path' is required"
            )]

        if not output_path_str:
            return [types.TextContent(type="text", text="Error: output_path is required")]

        output_path = Path(output_path_str)

        # Parse format
        try:
            export_format = ExportFormat[format_str.upper()]
        except KeyError:
            available = ", ".join([f.name.lower() for f in ExportFormat])
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown format '{format_str}'. Available: {available}"
            )]

        # Export CPG with correct parameter order
        provider = JoernProvider()
        result_path = provider.export_cpg(cpg_path, export_format, output_path)  # Fixed order

        # Format output
        output = "💾 CPG Export Complete\n"  # Changed from "Successful"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"**Format**: {export_format.value.upper()}\n"
        output += f"**Source CPG**: {cpg_path}\n"
        output += f"**Exported To**: {result_path}\n\n"

        # Add format-specific info
        if export_format == ExportFormat.JSON:
            output += "📄 **JSON Format**:\n"
            output += "- Structured CPG data\n"
            output += "- Use for custom processing pipelines\n"
        elif export_format == ExportFormat.SARIF:
            output += "🔍 **SARIF Format**:\n"
            output += "- Static Analysis Results Interchange Format\n"
            output += "- Integrate with CI/CD tools\n"
        elif export_format == ExportFormat.NEO4J:
            output += "🗂️ **Neo4j Format**:\n"
            output += "- Import into Neo4j graph database\n"
            output += "- Run Cypher queries\n"
        elif export_format == ExportFormat.DOT:
            output += "🎨 **DOT Format**:\n"
            output += "- Graphviz visualization\n"
            output += "- Generate diagrams with `dot` command\n"
        elif export_format == ExportFormat.GRAPHML:
            output += "📊 **GraphML Format**:\n"
            output += "- XML-based graph format\n"
            output += "- Full metadata preserved\n"

        return [types.TextContent(type="text", text=output)]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=build_error_response(e, "Error exporting CPG")
        )]


async def handle_generate_cpg(arguments: dict[str, Any], PROJECT_ROOT: Path) -> list[types.TextContent]:
    """Generate Code Property Graph dynamically from source code.

    Allows AI assistants to generate CPGs on-the-fly without manual setup.
    """
    try:
        from knowgraph.core.joern import JoernProvider

        # Required parameters
        source_path_str = arguments.get("source_path")
        if not source_path_str:
            return [types.TextContent(type="text", text="Error: source_path is required")]

        source_path = Path(source_path_str)
        if not source_path.exists():
            return [types.TextContent(type="text", text=f"Error: Source path not found: {source_path}")]

        # Optional parameters
        language = arguments.get("language")  # Auto-detected if None
        timeout = arguments.get("timeout", 600)

        # Initialize Joern provider
        try:
            provider = JoernProvider()
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"Error: Joern not found. Run: knowgraph-setup-joern\n{e}"
            )]

        # Generate CPG
        output = "📦 Generating Code Property Graph\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"**Source**: {source_path}\n"
        if language:
            output += f"**Language**: {language}\n"
        output += f"**Timeout**: {timeout}s\n\n"
        output += "⏳ Generating CPG (this may take a while)...\n\n"

        try:
            cpg_path = provider.generate_cpg(
                repo_path=source_path,
                language=language,
                timeout=timeout
            )

            output += "✅ **CPG Generated Successfully!**\n\n"
            output += f"**CPG Path**: `{cpg_path}`\n\n"
            output += "💡 **Next Steps**:\n"
            output += "- Use `knowgraph_joern_query` to query the CPG\n"
            output += "- Use `knowgraph_security_scan` to find vulnerabilities\n"
            output += "- Use `knowgraph_find_dead_code` to detect unused code\n"
            output += "- Use `knowgraph_analyze_call_graph` to analyze call relationships\n"
            output += "- Use `knowgraph_export_cpg` to export in various formats\n"

            # Get CPG stats
            if cpg_path.exists():
                size_mb = cpg_path.stat().st_size / (1024 * 1024)
                output += f"\n📊 **CPG Size**: {size_mb:.2f} MB\n"

            return [types.TextContent(type="text", text=output)]

        except Exception as e:
            error_output = output
            error_output += "\n❌ **CPG Generation Failed**\n\n"
            error_output += f"Error: {e!s}\n\n"
            error_output += "💡 **Troubleshooting**:\n"
            error_output += "- Ensure Joern is installed: `knowgraph-setup-joern`\n"
            error_output += "- Check if source path contains supported code files\n"
            error_output += "- Try increasing timeout if source is large\n"
            return [types.TextContent(type="text", text=error_output)]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=build_error_response(e, "Error generating CPG")
        )]

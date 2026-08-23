"""Conversation and bookmark MCP tool handlers."""

import asyncio
from pathlib import Path
from typing import Any

import mcp.types as types

from knowgraph.adapters.mcp.handlers._resilience import _global_rate_limiter
from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.infrastructure.detection.graph_store_locator import resolve_graph_store
from knowgraph.shared.refactoring import (
    build_error_response,
    validate_required_argument,
)
from knowgraph.shared.tracing import trace_operation


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
            graph_path = resolve_graph_store(graph_path_arg, root_dir=project_root)

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
            graph_path = resolve_graph_store(graph_path_arg, root_dir=project_root)

            if topic:
                # Get timeline for specific topic
                from knowgraph.application.analytics.knowledge_tracker import get_knowledge_timeline

                result = get_knowledge_timeline(topic, graph_path, time_window_days)

                # Defensive: analytics can return None / drop keys on a partial
                # store; degrade to "no data" instead of throwing a TypeError.
                result = result or {}
                mentions = result.get("total_mentions", 0)
                timeline = result.get("timeline") or {}

                trace.add_event("timeline_analyzed", {"topic": topic, "mentions": mentions})

                response_lines = [
                    f"📊 **Knowledge Timeline: {topic}**\n",
                    f"Time window: {time_window_days} days",
                    f"Total mentions: {mentions}",
                    f"Days with activity: {result.get('days_with_activity', 0)}",
                ]

                if timeline:
                    response_lines.append("\n**Daily Activity:**")
                    for date, items in sorted(timeline.items())[:10]:
                        response_lines.append(f"  {date}: {len(items)} conversation(s)")

            else:
                # Analyze trending topics
                from knowgraph.application.analytics.topic_analyzer import analyze_trending_topics

                result = analyze_trending_topics(graph_path, time_window_days)

                # Defensive: same as above — never crash on None/partial data.
                result = result or {}
                conversations_analyzed = result.get("conversations_analyzed", 0)
                trending_entities = result.get("trending_entities") or {}
                trending_topics = result.get("trending_topics") or {}

                trace.add_event(
                    "trends_analyzed", {"conversations": conversations_analyzed}
                )

                response_lines = [
                    f"📈 **Trending Topics (Last {time_window_days} days)**\n",
                    f"Conversations analyzed: {conversations_analyzed}",
                ]

                if trending_entities:
                    response_lines.append("\n**Top Entities:**")
                    for entity, count in list(trending_entities.items())[:10]:
                        response_lines.append(f"  • {entity}: {count} mentions")

                if trending_topics:
                    response_lines.append("\n**Top Topics:**")
                    for topic, count in list(trending_topics.items())[:10]:
                        response_lines.append(f"  • {topic}: {count} conversations")

            return [types.TextContent(type="text", text="\n".join(response_lines))]

        except Exception as e:
            trace.record_exception(e)
            return [
                types.TextContent(
                    type="text", text=build_error_response(e, "Conversation analysis failed")
                )
            ]


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
    graph_path = resolve_graph_store(graph_path_arg, root_dir=project_root)
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
            graph_path = resolve_graph_store(graph_path_arg, root_dir=project_root)

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

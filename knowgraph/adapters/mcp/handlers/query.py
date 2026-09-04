"""Query MCP tool handlers."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server import Server

from knowgraph.adapters.mcp.handlers._resilience import (
    _global_circuit_breaker,
    _global_rate_limiter,
    logger,
)
from knowgraph.application.querying.query_engine import QueryEngine
from knowgraph.application.querying.query_expansion import QueryExpander
from knowgraph.config import (
    DEFAULT_GRAPH_STORE_PATH,
    LLM_MAX_INPUT_TOKENS,
    LLM_SYNTHESIS_RETRIES,
    LLM_SYNTHESIS_TIMEOUT,
    QUERY_TOTAL_TIMEOUT,
)
from knowgraph.infrastructure.detection.graph_store_locator import resolve_graph_store
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

# QueryEngine cache: keyed by resolved graph_path. The dense index (500MB+)
# stays in memory after the first load, making subsequent queries ~10x faster.
# The provider is NOT part of the key — a stale provider reference is harmless
# (it's only used for LLM synthesis, not retrieval), and baking it in would
# defeat the cache on every provider refresh.
_engine_cache: dict[str, QueryEngine] = {}
_ENGINE_CACHE_MAX = 4  # at most N graph stores cached


def _get_cached_engine(graph_path: Path, provider: Any) -> QueryEngine:
    """Return a cached QueryEngine for *graph_path*, creating one if needed."""
    key = str(graph_path.resolve())
    engine = _engine_cache.get(key)
    if engine is None:
        if len(_engine_cache) >= _ENGINE_CACHE_MAX:
            # Evict the oldest entry (first inserted)
            oldest_key = next(iter(_engine_cache))
            del _engine_cache[oldest_key]
        engine = QueryEngine(graph_path, provider=provider)
        _engine_cache[key] = engine
    # Always refresh the provider reference (LLM synthesis needs a live one)
    engine.retriever.intelligence_provider = provider
    return engine


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
        "mcp_query", metadata={"query": (arguments.get("query") or "")[:100]}
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
                # CODE-only query → Try Joern tools, but degrade to semantic
                # search when code analysis produced nothing usable. A Joern
                # error or empty result must never be the final answer (it reads
                # as "an unrelated Joern error"), so we only return here on real
                # results and let TEXT/HYBRID semantic search take over otherwise.
                if progress:
                    await progress.update(1, f'🔧 Code Analysis: "{query[:50]}..."')

                try:
                    code_handler = CodeQueryHandler(graph_path)
                    code_results = await code_handler.handle(query)
                except Exception:
                    code_results = {"success": False, "results": []}

                if code_results.get("success") and code_results.get("results"):
                    return [types.TextContent(type="text", text=code_handler.format_results(code_results))]

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

                engine = _get_cached_engine(graph_path, provider)
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
            try:
                async with asyncio.timeout(QUERY_TOTAL_TIMEOUT):
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
                            query, result, params["system_prompt"], params["with_explanation"], provider,
                            enable_grounding=params.get("enable_grounding", False),
                        )
                        trace.add_event("llm_answer_generated", {"length": len(answer)})
            except TimeoutError:
                if progress:
                    await progress.error(f"Query timed out after {QUERY_TOTAL_TIMEOUT}s")
                answer = (
                    f"[Generation Error: query exceeded {QUERY_TOTAL_TIMEOUT}s budget] "
                    f"[raise KNOWGRAPH_QUERY_TOTAL_TIMEOUT or use a faster provider]"
                )

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
    """Expand query using available provider.

    Expanded terms are only appended when they are generic (non-identifier)
    keywords. A weak model may still fabricate a symbol name despite the prompt;
    invented identifiers must never reach the retriever (they would pollute the
    search and echo back into the answer). ``_sanitize_expansion_terms`` drops
    terms that look like code identifiers (camelCase, snake_case, dots,
    parentheses, currency codes) and keeps only plain language keywords.
    """
    try:
        if provider:
            expander = QueryExpander(intelligence_provider=provider)
            expansion_terms = await expander.expand_query_async(query)
            if expansion_terms:
                safe = _sanitize_expansion_terms(expansion_terms)
                if safe:
                    return f"{query} {' '.join(safe)}"
        else:
            # Fall back to OpenAI env vars
            import os

            if os.getenv("KNOWGRAPH_API_KEY"):
                llm_model = os.getenv("KNOWGRAPH_LLM_MODEL", "amazon/nova-2-lite-v1:free")
                expander = QueryExpander(provider="openai", model=llm_model)
                expansion_terms = expander.expand_query(query)
                if expansion_terms:
                    safe = _sanitize_expansion_terms(expansion_terms)
                    if safe:
                        return f"{query} {' '.join(safe)}"
    except Exception:
        pass

    return query


def _timeout_hint(error: Exception) -> str:
    """Return a short actionable hint when the LLM call failed on a timeout.

    A slow/free provider hitting the whole-call budget (LLM_REQUEST_TIMEOUT)
    degrades to a raw-context answer; tell the user how to fix it rather than
    leaving them with a bare "[Generation Error: ...]".
    """
    if isinstance(error, (TimeoutError, asyncio.TimeoutError)):
        return (
            "\n[provider timed out — raise KNOWGRAPH_LLM_REQUEST_TIMEOUT "
            "(env) or use a faster endpoint]"
        )
    return ""


def _ensure_code_context_visible(answer: str, query: str, context: str) -> str:
    """Append a bounded code excerpt when the LLM omits code from a code context."""
    if not answer or "```" not in context:
        return answer

    query_lower = query.lower().strip()
    query_is_identifier = bool(re.fullmatch(r"[A-Za-z_$][\w$]*", query.strip()))
    has_relevant_code = "```" in answer and (
        not query_is_identifier or query_lower in answer.lower()
    )
    if has_relevant_code:
        return answer

    excerpt = _extract_relevant_code_excerpt(context, query)
    if not excerpt:
        return answer

    return f"{answer}\n\n## Retrieved Code Context\n\n{excerpt}"


def _extract_relevant_code_excerpt(context: str, query: str, max_chars: int = 6000) -> str:
    """Return the most query-relevant context blocks without flooding MCP clients."""
    blocks = [b.strip() for b in re.split(r"(?=\n## )", context) if b.strip()]
    if not blocks:
        return ""

    query_lower = query.lower().strip()
    query_words = [w for w in re.split(r"\W+", query_lower) if len(w) > 3]

    def block_score(block: str) -> tuple[int, int]:
        lower = block.lower()
        exact = 2 if query_lower and query_lower in lower else 0
        word_hits = sum(1 for word in query_words if word in lower)
        has_code = 1 if "```" in block else 0
        return (exact + word_hits + has_code, len(block))

    selected = []
    total = 0
    for block in sorted(blocks, key=block_score, reverse=True):
        if "```" not in block:
            continue
        if total + len(block) > max_chars:
            remaining = max_chars - total
            if remaining > 1000:
                selected.append(block[:remaining].rstrip() + "\n[truncated]")
            break
        selected.append(block)
        total += len(block)
        if total >= max_chars:
            break

    return "\n\n".join(selected)


def _sanitize_expansion_terms(terms: list[str]) -> list[str]:
    """Drop terms that look like code identifiers; keep plain language keywords.

    An expansion term is a *likely fabricated identifier* (and dropped) when it
    contains:
      - camelCase or snake_case (``calculate_kdv_base``, ``get_kdv_orani``)
      - a dot, slash, parentheses, or leading '@' (``foo.bar``, ``find()``)
      - two or more space-separated words with an identifier-looking first token
    Plain terms (``vat``, ``tax``, ``currency``, ``exchange rate``) pass.
    """
    import re

    safe = []
    for term in terms:
        t = str(term).strip()
        if not t:
            continue
        lower = t.lower()
        # A single identifier token (no spaces) in camelCase/snake_case, or
        # containing punctuation typical of a symbol reference.
        if (
            re.search(r"[a-z0-9][A-Z]", t)  # camelCase
            or "_" in t
            or re.search(r"[./()@]", t)
            or (lower.startswith(("get_", "set_", "is_", "find_", "calc_", "hesapla", "bul")))
        ):
            continue
        safe.append(t)
    return safe


async def _generate_llm_answer(
    query: str,
    result: Any,
    system_prompt: str | None,
    with_explanation: bool,
    provider: Any,
    enable_grounding: bool = False,
) -> str:
    """Generate answer using LLM provider.

    When ``enable_grounding`` (Graph Engineering transfer), the raw LLM answer
    is annotated with entities that appear in the answer but are not backed by
    the retrieved subgraph (zero extra LLM calls). Annotation is applied AFTER
    the cache read so the raw prompt response stays cacheable.

    ``result.entity_names`` (real graph symbols) is passed as the
    ``known_identifiers`` allowlist so the model is told to only reference
    symbols that actually exist in the graph — the anti-hallucination guard.
    """
    explanation_data = None
    if with_explanation and result.explanation:
        explanation_data = json.dumps(result.explanation.to_dict(), indent=2, default=str)

    known_identifiers = getattr(result, "entity_names", None) or None
    prompt = build_llm_prompt(query, result.context, system_prompt, explanation_data,
                              known_identifiers=known_identifiers)

    # Skip re-billing when the exact prompt was answered before.
    cache_key = _llm_answer_key(prompt)
    cached = _llm_answer_cache.get(cache_key)
    raw_answer: str | None = cached
    if cached is None:
        # Retry the WHOLE synthesis a bounded number of times. The provider's
        # internal retry covers HTTP/429 but fail-fast times out (by design); a
        # slow/free provider's cold-start can time out the FIRST attempt and
        # degrade the answer to raw context. Retrying here turns that transient
        # first-call failure into a success — the "first weak, second strong"
        # inconsistency without the user having to re-ask.
# Bound the WHOLE synthesis (retries included) so a cold provider's retry
        # chain can't span past the client's window (~30s). Without this outer
        # cap, 2 x LLM_REQUEST_TIMEOUT would let synthesis burn ~180s server-side
        # and guarantee the client's cut. Now it degrades (or succeeds) promptly.
        last_error: Exception | None = None
        try:
            async with asyncio.timeout(LLM_SYNTHESIS_TIMEOUT):
                for attempt in range(LLM_SYNTHESIS_RETRIES):
                    try:
                        generated_answer = await provider.generate_text(prompt)
                        if generated_answer:
                            raw_answer = generated_answer
                            if len(_llm_answer_cache) >= _LLM_ANSWER_CACHE_MAX:
                                _llm_answer_cache.clear()  # simple bounded reset
                            _llm_answer_cache[cache_key] = generated_answer
                            break
                    except Exception as e:
                        last_error = e
                        # Small backoff so a cold provider gets a moment before retry.
                        if attempt < LLM_SYNTHESIS_RETRIES - 1:
                            await asyncio.sleep(0.5 * (attempt + 1))
        except TimeoutError as e:
            # Whole-synthesis budget exhausted — degrade honestly, promptly.
            last_error = e

        if raw_answer is None:
            if last_error is not None:
                hint = _timeout_hint(last_error)
                return f"{result.context}\n\n[Generation Error: {last_error!s}]{hint}"
            return result.context

    if enable_grounding:
        raw_answer = _annotate_grounding(raw_answer, result)

    raw_answer = _ensure_code_context_visible(raw_answer, query, result.context)

    return raw_answer


def _annotate_grounding(answer: str, result: Any) -> str:
    """Annotate a generated answer with unbacked entities (zero LLM).

    Reuses ``grounding_evaluator.verify_entities_in_answer`` on the grounding
    facts that ``query_engine`` serialized onto the QueryResult. Entities found
    in the answer but not in the retrieved graph get a trailing note. We never
    strip content — this is an honest "double-check these" annotation.
    """
    from knowgraph.domain.claims.grounding_evaluator import verify_entities_in_answer

    entity_names = getattr(result, "entity_names", []) or []
    grounded_edges = getattr(result, "grounded_edges", []) or []
    if not entity_names:
        return answer

    verdict = verify_entities_in_answer(answer, entity_names, grounded_edges)
    miss = verdict["absent"] + verdict["isolated"]
    if miss:
        answer = (
            f"{answer}\n\n"
            f"[grounding] these entities in the answer were not found in the "
            f"retrieved graph; verify: {', '.join(miss)}"
        )
    return answer


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
        max_tokens = arguments.get("max_tokens", LLM_MAX_INPUT_TOKENS)
        enable_hierarchical_lifting = arguments.get("enable_hierarchical_lifting", True)
        lift_levels = arguments.get("lift_levels", 2)
        enable_grounding = arguments.get("enable_grounding", False)
        enable_temporal_filter = arguments.get("enable_temporal_filter", False)

        engine = _get_cached_engine(graph_path, provider)

        # Use async batch query for better performance
        results_list = await engine.batch_query_async(
            queries=queries,
            top_k=top_k,
            max_hops=max_hops,
            max_tokens=max_tokens,
            enable_hierarchical_lifting=enable_hierarchical_lifting,
            lift_levels=lift_levels,
            enable_grounding=enable_grounding,
            enable_temporal_filter=enable_temporal_filter,
        )

        # Format results with LLM generation if provider available (PARALLELIZED)
        async def generate_answer_for_result(query: str, result: Any) -> dict:
            """Generate LLM answer for a single query result."""
            answer = result.context
            if provider and result.answer:  # Only if we have context
                try:
                    known_identifiers = getattr(result, "entity_names", None) or None
                    prompt = build_llm_prompt(query, result.context,
                                              known_identifiers=known_identifiers)
                    cache_key = _llm_answer_key(prompt)
                    cached = _llm_answer_cache.get(cache_key)
                    if cached is not None:
                        answer = cached
                    else:
                        # Bounded retry on a transient first-call failure (the
                        # provider fail-fast times out; make it succeed on retry),
                        # ALSO bounded by a whole-synthesis cap so a cold provider
                        # can't span past the client window.
                        generated_answer = ""
                        try:
                            async with asyncio.timeout(LLM_SYNTHESIS_TIMEOUT):
                                for attempt in range(LLM_SYNTHESIS_RETRIES):
                                    try:
                                        generated_answer = await provider.generate_text(prompt)
                                        if generated_answer:
                                            break
                                    except Exception:
                                        if attempt < LLM_SYNTHESIS_RETRIES - 1:
                                            await asyncio.sleep(0.5 * (attempt + 1))
                        except TimeoutError:
                            generated_answer = ""
                        if generated_answer:
                            if len(_llm_answer_cache) >= _LLM_ANSWER_CACHE_MAX:
                                _llm_answer_cache.clear()
                            _llm_answer_cache[cache_key] = generated_answer
                            answer = generated_answer
                except Exception as e:
                    hint = _timeout_hint(e)
                    answer = f"{answer}{hint}"  # context fallback + (maybe) hint

            answer = _ensure_code_context_visible(answer, query, result.context)

            if enable_grounding:
                answer = _annotate_grounding(answer, result)

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

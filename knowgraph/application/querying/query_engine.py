"""Query engine - orchestrates full query pipeline.

Coordinates retrieval, graph reasoning, and context assembly.

Supports both sync and async modes for backward compatibility.
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass
import asyncio
import time
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from knowgraph.application.querying.context_assembly import assemble_context
from knowgraph.application.querying.explanation import ExplanationObject, generate_explanation
from knowgraph.application.querying.retriever import QueryRetriever
from knowgraph.config import (
    DEFAULT_CENTRALITY_SCORE,
    MAX_CONCURRENT_QUERIES,
    MAX_QUERY_PREVIEW_LENGTH,
    QUERY_TIMEOUT_SECONDS,
    TOP_K,
    get_settings,
)
from knowgraph.domain.algorithms.centrality import (
    compute_centrality_metrics,
    compute_centrality_metrics_async,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.infrastructure.storage.filesystem import (
    read_all_edges,
)
from knowgraph.shared.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from knowgraph.shared.exceptions import QueryError
from knowgraph.shared.memory_profiler import memory_guard
from knowgraph.shared.metrics import get_metrics
from knowgraph.shared.refactoring import (
    filter_active_edges,
    flatten_centrality_scores,
)
from knowgraph.shared.retry import BackoffStrategy, RetryConfig, RetryContext
from knowgraph.shared.throttle import RequestThrottle
from knowgraph.shared.tracing import trace_operation

# Context variable for request tracking
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


# Query Result Cache (LRU with TTL)
@dataclass
class CachedQueryResult:
    """Cached query result with timestamp."""

    result: "QueryResult"
    timestamp: float


_query_result_cache: dict[str, CachedQueryResult] = {}
_query_cache_max_size = 128  # Maximum cached queries
_query_cache_ttl = 300.0  # 5 minutes TTL


def _get_query_cache_key(
    query_text: str,
    top_k: int,
    max_hops: int,
    max_tokens: int,
    enable_hierarchical_lifting: bool,
    lift_levels: int,
    with_explanation: bool,
) -> str:
    """Generate cache key for query parameters."""
    import hashlib

    key_parts = f"{query_text}|{top_k}|{max_hops}|{max_tokens}|{enable_hierarchical_lifting}|{lift_levels}|{with_explanation}"
    return hashlib.md5(key_parts.encode()).hexdigest()  # noqa: S324


@dataclass
class QueryResult:
    """Result from query execution.

    Attributes
    ----------
        query: Original query text
        answer: Retrieved context
        context: Assembled context
        seed_nodes: Seed node IDs from vector search
        active_subgraph_size: Number of nodes in reasoning subgraph
        execution_time: Total execution time (seconds)
        sparse_search_time: Time for sparse search
        graph_expansion_time: Time for graph traversal
        centrality_time: Time for centrality calculation
        explanation: Optional explanation object (if requested)

    """

    query: str
    answer: str  # Now always the retrieved context
    context: str
    seed_nodes: list[UUID]
    active_subgraph_size: int
    execution_time: float
    sparse_search_time: float
    graph_expansion_time: float
    centrality_time: float
    explanation: ExplanationObject | None = None


class QueryEngine:
    """Full query pipeline orchestration.

    Workflow:
        1. Sparse search for seed nodes
        2. Graph traversal expansion
        3. Centrality calculation on active subgraph
        4. Context assembly with importance scoring
        5. Return context
    """

    def __init__(
        self: "QueryEngine",
        graph_store_path: Path,
    ) -> None:
        """Initialize query engine.

        Args:
        ----
            graph_store_path: Root graph storage directory

        """
        self.graph_store_path = graph_store_path
        self.retriever = QueryRetriever(graph_store_path)
        # LAZY LOADING: Don't load all edges upfront
        # Instead, load only when needed with optional filtering
        self._edges_cache: list[Edge] | None = None

        # Async concurrency control
        self._query_semaphore = asyncio.Semaphore(MAX_CONCURRENT_QUERIES)
        self._active_tasks: set[asyncio.Task[QueryResult]] = set()

        # Resilience patterns
        self._circuit_breaker = CircuitBreaker(
            name="query_engine",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                timeout=30.0,  # Use 'timeout' not 'recovery_timeout'
                success_threshold=3,  # Use 'success_threshold' not 'half_open_max_calls'
            ),
        )
        self._retry_config = RetryConfig(
            max_attempts=3,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,  # Correct parameter name
            initial_delay=1.0,  # Use 'initial_delay' not 'base_delay'
            max_delay=10.0,
            timeout=30.0,
        )
        self._throttle = RequestThrottle(
            max_concurrent=MAX_CONCURRENT_QUERIES,
            queue_size=100,
            adaptive=True,
            timeout=30.0,
        )

        # Metrics tracking
        self.metrics = get_metrics()

    def _get_edges(self) -> list[Edge]:
        """Lazy load edges with caching and memory monitoring."""
        if self._edges_cache is None:
            from knowgraph.shared.memory_profiler import memory_guard

            with memory_guard(
                operation_name="lazy_edge_loading",
                warning_threshold_mb=200,  # Warn if edges use >200MB
                critical_threshold_mb=500,  # Error if >500MB
            ):
                self._edges_cache = read_all_edges(self.graph_store_path)
        return self._edges_cache

    def __del__(self) -> None:
        """Cleanup resources on deletion."""
        # Import here to avoid circular dependency issues
        from knowgraph.domain.algorithms.centrality import _shutdown_process_pool

        try:
            _shutdown_process_pool()
        except Exception:
            # Ignore errors during cleanup
            pass

    def query(
        self: "QueryEngine",
        query_text: str,
        top_k: int = 20,
        max_hops: int = 4,
        max_tokens: int = 3000,
        with_explanation: bool = False,
        enable_hierarchical_lifting: bool = True,
        lift_levels: int = 2,
    ) -> QueryResult:
        """Execute full query pipeline with retry logic.

        Args:
        ----
            query_text: Natural language query
            top_k: Number of seed nodes
            max_hops: Graph traversal depth
            max_tokens: Maximum context tokens
            with_explanation: Generate explanation object
            enable_hierarchical_lifting: Apply hierarchical context lifting (FR-029)
            lift_levels: Directory levels to traverse upward (default: 2)

        Returns:
        -------
            QueryResult with answer and metrics

        Raises:
        ------
            QueryError: If query fails

        """
        # Validate parameters explicitly
        if not query_text or not query_text.strip():
            raise QueryError("Query text cannot be empty")

        if top_k <= 0:
            raise QueryError(f"top_k must be positive, got {top_k}")
        if max_hops < 0:
            raise QueryError(f"max_hops cannot be negative, got {max_hops}")
        if max_tokens <= 0:
            raise QueryError(f"max_tokens must be positive, got {max_tokens}")
        if lift_levels < 0:
            raise QueryError(f"lift_levels cannot be negative, got {lift_levels}")

        # Check cache first (for identical queries)
        cache_key = _get_query_cache_key(
            query_text,
            top_k,
            max_hops,
            max_tokens,
            enable_hierarchical_lifting,
            lift_levels,
            with_explanation,
        )

        if cache_key in _query_result_cache:
            cached = _query_result_cache[cache_key]
            # Check if cache is still valid (TTL)
            if time.time() - cached.timestamp < _query_cache_ttl:
                return cached.result
            else:
                # Expired, remove from cache
                del _query_result_cache[cache_key]

        # Note: Retry logic only available in query_async()
        # This sync version calls implementation directly
        start_time = time.time()
        try:
            result = self._execute_query_with_retry(
                None,  # No retry context for sync version
                query_text,
                top_k,
                max_hops,
                max_tokens,
                with_explanation,
                enable_hierarchical_lifting,
                lift_levels,
            )

            # Store in cache
            _query_result_cache[cache_key] = CachedQueryResult(result=result, timestamp=time.time())

            # Prune cache if needed (simple FIFO)
            if len(_query_result_cache) > _query_cache_max_size:
                oldest_key = next(iter(_query_result_cache))
                del _query_result_cache[oldest_key]

            # Record successful query
            self.metrics.record_request("query", "success")
            self.metrics.request_duration.labels(operation="query").observe(
                time.time() - start_time
            )
            return result
        except Exception as error:
            # Record failed query
            self.metrics.record_error(type(error).__name__, "query")
            raise

    def _execute_query_with_retry(
        self: "QueryEngine",
        retry_ctx: "RetryContext",
        query_text: str,
        top_k: int,
        max_hops: int,
        max_tokens: int,
        with_explanation: bool,
        enable_hierarchical_lifting: bool,
        lift_levels: int,
    ) -> QueryResult:
        """Internal query execution with retry support."""
        with memory_guard(
            operation_name=f"query_sync[{query_text[:30]}]",
            warning_threshold_mb=100,
            critical_threshold_mb=250,
        ):
            with trace_operation(
                "query_engine.query_sync",
                query_length=len(query_text),
                top_k=top_k,
                max_hops=max_hops,
            ):
                start_time = time.time()
                timings = {}

                try:
                    # Step 1: Sparse search + graph expansion
                    retrieval_start = time.time()
                    nodes, seed_node_ids = self.retriever.retrieve(
                        query_text, self._get_edges(), top_k, max_hops
                    )
                    timings["sparse_search"] = time.time() - retrieval_start
                    timings["graph_expansion"] = 0.0  # Included in retrieval

                    if not nodes:
                        raise QueryError("No relevant nodes found")

                    # Step 1.5: Hierarchical Context Lifting (if enabled)
                    if enable_hierarchical_lifting:
                        from knowgraph.application.querying.hierarchical_lifting import (
                            lift_hierarchical_context,
                        )

                        original_count = len(nodes)
                        nodes = lift_hierarchical_context(
                            nodes, self.graph_store_path, lift_levels=lift_levels, max_additional_nodes=5
                        )
                        if len(nodes) > original_count:
                            # Update seed_node_ids to not include lifted nodes as seeds
                            # (they're context, not direct matches)
                            pass  # seed_node_ids stays the same

                    # Step 2: Compute centrality on active subgraph
                    centrality_start = time.time()
                    active_node_ids = {node.id for node in nodes}
                    active_edges = filter_active_edges(self._get_edges(), active_node_ids)
                    centrality_scores = compute_centrality_metrics(nodes, active_edges)
                    timings["centrality"] = time.time() - centrality_start

                    # Step 3: Get similarity scores from retriever results
                    retrieval_results = self.retriever.retrieve_by_similarity(query_text, top_k)
                    similarity_scores = {node.id: score for node, score in retrieval_results}

                    # Step 4: Assemble context (REFERENCE-AWARE IMPORTANCE!)
                    context, _context_blocks = assemble_context(
                        nodes,
                        seed_node_ids,
                        similarity_scores,
                        centrality_scores,
                        max_tokens,
                        edges=active_edges,
                    )

                    # Step 5: Return context
                    answer = context

                    # Step 6: Generate explanation (if requested, now context-based only)
                    explanation = None
                    if with_explanation:
                        context_nodes = [n for n in nodes if n.id in {n.id for n in nodes}][:30]
                        flat_centralities = flatten_centrality_scores(
                            centrality_scores, "degree", DEFAULT_CENTRALITY_SCORE
                        )
                        explanation = generate_explanation(
                            context_nodes,
                            active_edges,
                            similarity_scores,
                            flat_centralities,
                            set(seed_node_ids),
                            answer,
                        )

                    # Build result
                    total_time = time.time() - start_time

                    return QueryResult(
                        query=query_text,
                        answer=answer,
                        context=context,
                        seed_nodes=seed_node_ids,
                        active_subgraph_size=len(nodes),
                        execution_time=total_time,
                        sparse_search_time=timings["sparse_search"],
                        graph_expansion_time=timings["graph_expansion"],
                        centrality_time=timings["centrality"],
                        explanation=explanation,
                    )

                except QueryError:
                    raise
                except Exception as error:
                    raise QueryError(
                        "Query execution failed",
                        {"error": str(error), "query": query_text[:MAX_QUERY_PREVIEW_LENGTH]},
                    ) from error

    async def query_async(
        self: "QueryEngine",
        query_text: str,
        top_k: int | None = None,
        max_hops: int | None = None,
        max_tokens: int = 3000,
        timeout: float | None = None,
        with_explanation: bool = False,
        enable_hierarchical_lifting: bool = True,
        lift_levels: int = 2,
    ) -> QueryResult:
        """Execute full query pipeline (async version with timeout and concurrency control).

        Improvements over sync version:
        - Concurrent node loading
        - Async query expansion
        - Timeout support
        - Request tracking
        - Concurrency limiting

        Args:
        ----
            query_text: Natural language query
            top_k: Number of seed nodes
            max_hops: Graph traversal depth
            max_tokens: Maximum context tokens
            timeout: Query timeout in seconds (default: QUERY_TIMEOUT_SECONDS)
            with_explanation: Generate explanation object
            enable_hierarchical_lifting: Apply hierarchical context lifting
            lift_levels: Directory levels to traverse upward

        Returns:
        -------
            QueryResult with answer and metrics

        Raises:
        ------
            QueryError: If query fails
            asyncio.TimeoutError: If query exceeds timeout

        """
        # Validate parameters explicitly
        if not query_text or not query_text.strip():
            raise QueryError("Query text cannot be empty")

        # Use config defaults if not specified
        settings = get_settings()
        if top_k is None:
            top_k = settings.query.top_k
        if max_hops is None:
            max_hops = settings.query.max_hops

        if top_k <= 0:
            raise QueryError(f"top_k must be positive, got {top_k}")
        if max_hops < 0:
            raise QueryError(f"max_hops cannot be negative, got {max_hops}")
        if max_tokens <= 0:
            raise QueryError(f"max_tokens must be positive, got {max_tokens}")
        if lift_levels < 0:
            raise QueryError(f"lift_levels cannot be negative, got {lift_levels}")

        # Check cache first (for identical queries) - ASYNC CACHE SUPPORT
        cache_key = _get_query_cache_key(
            query_text,
            top_k,
            max_hops,
            max_tokens,
            enable_hierarchical_lifting,
            lift_levels,
            with_explanation,
        )

        if cache_key in _query_result_cache:
            cached = _query_result_cache[cache_key]
            # Check if cache is still valid (TTL)
            if time.time() - cached.timestamp < _query_cache_ttl:
                return cached.result
            else:
                # Expired, remove from cache
                del _query_result_cache[cache_key]

        # Set request ID for tracking
        request_id = str(uuid4())
        request_id_var.set(request_id)

        # Use default timeout if not specified
        if timeout is None:
            timeout = QUERY_TIMEOUT_SECONDS

        # Apply concurrency limit with throttle protection
        throttle_context = await self._throttle.acquire()
        async with throttle_context:
            async with self._query_semaphore:
                # Track active task
                task = asyncio.current_task()
                if task:
                    self._active_tasks.add(task)

                try:
                    # Execute with timeout and circuit breaker protection
                    start_time_inner = time.time()

                    async def _execute():
                        return await self._query_async_impl(
                            query_text=query_text,
                            top_k=top_k,
                            max_hops=max_hops,
                            max_tokens=max_tokens,
                            enable_hierarchical_lifting=enable_hierarchical_lifting,
                            lift_levels=lift_levels,
                            with_explanation=with_explanation,
                        )

                    result = await asyncio.wait_for(
                        self._circuit_breaker.call(_execute),
                        timeout=timeout,
                    )

                    # Store in cache (ASYNC CACHE SUPPORT)
                    _query_result_cache[cache_key] = CachedQueryResult(
                        result=result, timestamp=time.time()
                    )

                    # Prune cache if needed (simple FIFO)
                    if len(_query_result_cache) > _query_cache_max_size:
                        oldest_key = next(iter(_query_result_cache))
                        del _query_result_cache[oldest_key]

                    # Record successful async query
                    self.metrics.record_request("query_async", "success")
                    self.metrics.request_duration.labels(operation="query_async").observe(
                        time.time() - start_time_inner
                    )
                    return result

                except asyncio.TimeoutError:
                    self.metrics.record_error("TimeoutError", "query_async")
                    raise QueryError(
                        f"Query timed out after {timeout}s",
                        {"query": query_text[:MAX_QUERY_PREVIEW_LENGTH], "request_id": request_id},
                    ) from None
                except Exception as error:
                    self.metrics.record_error(type(error).__name__, "query_async")
                    raise
                finally:
                    # Remove from active tasks
                    if task:
                        self._active_tasks.discard(task)

    async def _query_async_impl(
        self: "QueryEngine",
        query_text: str,
        top_k: int,
        max_hops: int,
        max_tokens: int,
        enable_hierarchical_lifting: bool,
        lift_levels: int,
        with_explanation: bool,
    ) -> QueryResult:
        """Internal async implementation without timeout wrapper."""
        with memory_guard(
            operation_name=f"query_async[{query_text[:30]}]",
            warning_threshold_mb=100,
            critical_threshold_mb=250,
        ):
            with trace_operation(
                "query_engine.query_async",
                query_length=len(query_text),
                top_k=top_k,
                max_hops=max_hops,
            ):
                start_time = time.time()
                timings = {}

                try:
                    # Step 1: Sparse search + graph expansion (async)
                    retrieval_start = time.time()
                    nodes, seed_node_ids = await self.retriever.retrieve_async(
                        query_text, self._get_edges(), top_k, max_hops
                    )
                    timings["sparse_search"] = time.time() - retrieval_start
                    timings["graph_expansion"] = 0.0  # Included in retrieval

                    if not nodes:
                        raise QueryError("No relevant nodes found")

                    # Allow cancellation
                    await asyncio.sleep(0)

                    # Step 2: Compute centrality on active subgraph (ASYNC with multiprocessing)
                    centrality_start = time.time()
                    active_node_ids = {node.id for node in nodes}
                    active_edges = filter_active_edges(self._get_edges(), active_node_ids)
                    centrality_scores = await compute_centrality_metrics_async(nodes, active_edges)
                    timings["centrality"] = time.time() - centrality_start

                    # Allow cancellation
                    await asyncio.sleep(0)

                    # Step 3: Get similarity scores from retriever results
                    retrieval_results = await self.retriever.retrieve_by_similarity_async(query_text, top_k)
                    similarity_scores = {node.id: score for node, score in retrieval_results}

                    # Step 4: Assemble context with hierarchical lifting
                    context, _context_blocks = assemble_context(
                        nodes,
                        seed_node_ids,
                        similarity_scores,
                        centrality_scores,
                        max_tokens,
                        enable_hierarchical_lifting=enable_hierarchical_lifting,
                        lift_levels=lift_levels,
                    )

                    # Step 5: Return context
                    answer = context

                    # Step 6: Generate explanation (if requested)
                    explanation = None
                    if with_explanation:
                        context_nodes = [n for n in nodes if n.id in {n.id for n in nodes}][:30]
                        flat_centralities = flatten_centrality_scores(
                            centrality_scores, "degree", DEFAULT_CENTRALITY_SCORE
                        )
                        explanation = generate_explanation(
                            context_nodes,
                            active_edges,
                            similarity_scores,
                            flat_centralities,
                            set(seed_node_ids),
                            answer,
                        )

                    # Build result
                    total_time = time.time() - start_time

                    return QueryResult(
                        query=query_text,
                        answer=answer,
                        context=context,
                        seed_nodes=seed_node_ids,
                        active_subgraph_size=len(nodes),
                        execution_time=total_time,
                        sparse_search_time=timings["sparse_search"],
                        graph_expansion_time=timings["graph_expansion"],
                        centrality_time=timings["centrality"],
                        explanation=explanation,
                    )

                except QueryError:
                    raise
                except asyncio.CancelledError:
                    # Log cancellation and re-raise
                    raise
                except Exception as error:
                    raise QueryError(
                        "Query execution failed",
                        {"error": str(error), "query": query_text[:MAX_QUERY_PREVIEW_LENGTH]},
                    ) from error

    async def analyze_impact_async(
        self: "QueryEngine",
        query_text: str,
        max_hops: int = 4,
        edge_types: list[str] | None = None,
    ) -> QueryResult:
        """Analyze impact of changes to a code element (async version).

        Performs reverse dependency traversal to find all code that depends
        on the queried element.

        Args:
        ----
            query_text: Element to analyze (e.g., function name, file path)
            max_hops: Maximum traversal depth (default: 4)
            edge_types: Edge types to follow (default: ["semantic"])

        Returns:
        -------
            QueryResult with affected nodes and reasoning

        """
        from knowgraph.domain.algorithms.traversal import traverse_reverse_references
        from knowgraph.domain.models.node import Node
        from knowgraph.infrastructure.storage.filesystem import read_node_json

        start_time = time.time()

        try:
            # Step 1: Find target nodes via vector search (async)
            vector_start = time.time()
            _nodes, seed_node_ids = await self.retriever.retrieve_async(
                query_text, self._get_edges(), top_k=TOP_K, max_hops=1  # At least 1 hop for context
            )
            vector_time = time.time() - vector_start

            if not seed_node_ids:
                # Return empty result instead of error
                return QueryResult(
                    query=query_text,
                    answer=f"No nodes found matching '{query_text}' for impact analysis.",
                    context="",
                    seed_nodes=[],
                    active_subgraph_size=0,
                    execution_time=time.time() - start_time,
                    sparse_search_time=vector_time,
                    graph_expansion_time=0.0,
                    centrality_time=0.0,
                )

            # Step 2: Traverse reverse references
            traversal_start = time.time()
            affected_node_ids = traverse_reverse_references(
                seed_node_ids, self._get_edges(), max_hops, edge_types or ["semantic"]
            )
            traversal_time = time.time() - traversal_start

            # Step 3: Load affected nodes concurrently
            load_start = time.time()

            async def load_node_async(node_id: UUID, graph_store_path: Path) -> Node | None:
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, read_node_json, node_id, graph_store_path)

            tasks = [
                load_node_async(node_id, self.graph_store_path) for node_id in affected_node_ids
            ]
            loaded_nodes = await asyncio.gather(*tasks)
            affected_nodes = [node for node in loaded_nodes if node is not None]
            load_time = time.time() - load_start

            # Step 4: Build context
            context_lines = [f"Impact Analysis for: {query_text}\n"]
            context_lines.append(f"Target Nodes: {len(seed_node_ids)}")
            context_lines.append(f"Affected Nodes: {len(affected_nodes)}")
            context_lines.append(f"Traversal Depth: {max_hops}\n")

            # Group by file
            files_affected = {}
            for node in affected_nodes:
                if node.path not in files_affected:
                    files_affected[node.path] = []
                files_affected[node.path].append(node)

            context_lines.append(f"Files Affected: {len(files_affected)}\n")
            for file_path, nodes in sorted(files_affected.items())[:20]:  # Top 20 files
                context_lines.append(f"  {file_path} ({len(nodes)} nodes)")

            context = "\n".join(context_lines)

            return QueryResult(
                query=query_text,
                answer=context,
                context=context,
                seed_nodes=list(seed_node_ids),
                active_subgraph_size=len(affected_nodes),
                execution_time=time.time() - start_time,
                sparse_search_time=vector_time,
                graph_expansion_time=traversal_time + load_time,
                centrality_time=0.0,
            )

        except Exception as error:
            # Better error handling
            error_msg = f"Impact analysis failed: {type(error).__name__}: {error}"
            return QueryResult(
                query=query_text,
                answer=error_msg,
                context="",
                seed_nodes=[],
                active_subgraph_size=0,
                execution_time=time.time() - start_time,
                sparse_search_time=0.0,
                graph_expansion_time=0.0,
                centrality_time=0.0,
            )

    async def batch_query_async(
        self: "QueryEngine",
        queries: list[str],
        top_k: int = 20,
        max_hops: int = 4,
        max_tokens: int = 3000,
        enable_hierarchical_lifting: bool = True,
        lift_levels: int = 2,
        batch_size: int = 5,
        timeout: float | None = None,
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> list[QueryResult]:
        """Execute multiple queries concurrently with advanced features.

        Features:
        - Chunked processing to avoid memory issues
        - Progress callbacks for long-running batches
        - Timeout support per query
        - Graceful error handling (continues on failures)
        - **OPTIMIZED**: Bypasses per-query semaphore for true concurrency

        Args:
        ----
            queries: List of query texts
            top_k: Number of seed nodes per query
            max_hops: Graph traversal depth
            max_tokens: Maximum context tokens
            batch_size: Number of queries to process concurrently (default: 5)
            timeout: Timeout per query in seconds (default: QUERY_TIMEOUT_SECONDS)
            progress_callback: Optional async callback(current, total)

        Returns:
        -------
            List of QueryResults in same order as queries

        Example:
        -------
            >>> async def on_progress(current, total):
            ...     print(f"Progress: {current}/{total}")
            >>>
            >>> results = await engine.batch_query_async(
            ...     queries=["query1", "query2", "query3"],
            ...     progress_callback=on_progress
            ... )

        """

        results = []

        # Use default timeout if not specified
        if timeout is None:
            timeout = QUERY_TIMEOUT_SECONDS

        # Process queries in chunks to avoid memory issues
        for i in range(0, len(queries), batch_size):
            batch = queries[i : i + batch_size]

            # Create tasks for this batch
            # OPTIMIZATION: Call _query_async_impl directly to bypass semaphore
            # This allows true concurrent execution within batch
            tasks = []
            for query in batch:
                # Set request ID for tracking
                request_id = str(uuid4())
                request_id_var.set(request_id)

                # Wrap with timeout
                task = asyncio.wait_for(
                    self._query_async_impl(
                        query_text=query,
                        top_k=top_k,
                        max_hops=max_hops,
                        max_tokens=max_tokens,
                        enable_hierarchical_lifting=enable_hierarchical_lifting,
                        lift_levels=lift_levels,
                        with_explanation=False,  # Disable for batch performance
                    ),
                    timeout=timeout,
                )
                tasks.append(task)

            # Execute batch concurrently
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle exceptions gracefully
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    # Log error but continue with other queries
                    # Return empty result for failed queries
                    results.append(
                        QueryResult(
                            query=batch[j],
                            answer="",
                            context="",
                            seed_nodes=[],
                            active_subgraph_size=0,
                            execution_time=0.0,
                            sparse_search_time=0.0,
                            graph_expansion_time=0.0,
                            centrality_time=0.0,
                        )
                    )
                else:
                    results.append(result)

            # Report progress
            if progress_callback:
                await progress_callback(min(i + batch_size, len(queries)), len(queries))

            # Allow garbage collection between batches
            await asyncio.sleep(0)

        return results

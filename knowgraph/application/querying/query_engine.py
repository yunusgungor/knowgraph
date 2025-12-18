"""Query engine - orchestrates full query pipeline.

Coordinates retrieval, graph reasoning, and context assembly.

Supports both sync and async modes for backward compatibility.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
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
    MAX_HOPS,
    MAX_QUERY_PREVIEW_LENGTH,
    MAX_TOKENS,
    QUERY_TIMEOUT_SECONDS,
    TOP_K,
)
from knowgraph.domain.algorithms.centrality import (
    compute_centrality_metrics,
    compute_centrality_metrics_async,
)
from knowgraph.infrastructure.storage.filesystem import (
    read_all_edges,
    read_node_json,
)
from knowgraph.shared.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from knowgraph.shared.exceptions import QueryError
from knowgraph.shared.metrics import get_metrics
from knowgraph.shared.refactoring import (
    filter_active_edges,
    flatten_centrality_scores,
)
from knowgraph.shared.retry import BackoffStrategy, RetryConfig, RetryContext
from knowgraph.shared.throttle import RequestThrottle

# Context variable for request tracking
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


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
        self.edges = read_all_edges(graph_store_path)

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
        start_time = time.time()
        timings = {}

        try:
            # Step 1: Sparse search + graph expansion
            retrieval_start = time.time()
            nodes, seed_node_ids = self.retriever.retrieve(query_text, self.edges, top_k, max_hops)
            timings["sparse_search"] = time.time() - retrieval_start
            timings["graph_expansion"] = 0.0  # Included in retrieval

            if not nodes:
                raise QueryError("No relevant nodes found")

            # Step 2: Compute centrality on active subgraph
            centrality_start = time.time()
            active_node_ids = {node.id for node in nodes}
            active_edges = filter_active_edges(self.edges, active_node_ids)
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

    def analyze_impact(
        self: "QueryEngine",
        query_text: str,
        max_hops: int = MAX_HOPS,
        edge_types: list[str] | None = None,
    ) -> QueryResult:
        """Analyze impact of changes using reverse reference traversal.

        Answers "what will be affected if I change X?" by traversing
        references backward to find dependent nodes.

        Args:
        ----
            query_text: Query identifying nodes to analyze
            max_hops: Maximum reverse traversal depth
            edge_types: Edge types to follow (default: ["semantic"])

        Returns:
        -------
            QueryResult with affected nodes and reasoning

        """
        from knowgraph.domain.algorithms.traversal import traverse_reverse_references

        start_time = time.time()

        try:
            # Step 1: Find target nodes via vector search
            vector_start = time.time()
            _nodes, seed_node_ids = self.retriever.retrieve(
                query_text, self.edges, top_k=TOP_K, max_hops=0
            )
            vector_time = time.time() - vector_start

            if not seed_node_ids:
                raise QueryError("No nodes found for impact analysis")

            # Step 2: Traverse reverse references
            traversal_start = time.time()
            if edge_types is None:
                edge_types = ["semantic"]

            affected_node_ids = traverse_reverse_references(
                seed_node_ids, self.edges, max_hops, edge_types
            )
            traversal_time = time.time() - traversal_start

            # Step 3: Load affected nodes
            affected_nodes = []
            for node_id in affected_node_ids:
                node = read_node_json(node_id, self.graph_store_path)
                if node:
                    affected_nodes.append(node)

            # Step 4: Compute centrality for importance
            centrality_start = time.time()
            centrality_scores = compute_centrality_metrics(affected_nodes, self.edges)
            centrality_time = time.time() - centrality_start

            # Step 5: Get similarity scores (use distance of 0 for affected nodes)
            similarity_scores = {node.id: 0.0 for node in affected_nodes}

            # Step 6: Assemble context with affected nodes
            context, _context_blocks = assemble_context(
                affected_nodes,
                seed_node_ids,
                similarity_scores,
                centrality_scores,
                max_tokens=MAX_TOKENS,
            )

            # Step 6: Return context as answer
            answer = context

            # (No LLM generation for impact analysis anymore)

            total_time = time.time() - start_time

            return QueryResult(
                query=f"Impact Analysis: {query_text}",
                answer=answer,
                context=context,
                seed_nodes=seed_node_ids,
                active_subgraph_size=len(affected_nodes),
                execution_time=total_time,
                sparse_search_time=vector_time,
                graph_expansion_time=traversal_time,
                centrality_time=centrality_time,
                explanation=None,
            )

        except QueryError:
            raise
        except Exception as error:
            raise QueryError(
                "Impact analysis failed",
                {"error": str(error), "query": query_text[:MAX_QUERY_PREVIEW_LENGTH]},
            ) from error

    async def query_async(
        self: "QueryEngine",
        query_text: str,
        top_k: int = 20,
        max_hops: int = 4,
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
                            with_explanation=with_explanation,
                            enable_hierarchical_lifting=enable_hierarchical_lifting,
                            lift_levels=lift_levels,
                        )

                    result = await asyncio.wait_for(
                        self._circuit_breaker.call(_execute),
                        timeout=timeout,
                    )

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
        with_explanation: bool,
        enable_hierarchical_lifting: bool,
        lift_levels: int,
    ) -> QueryResult:
        """Internal async implementation without timeout wrapper."""
        start_time = time.time()
        timings = {}

        try:
            # Step 1: Sparse search + graph expansion (async)
            retrieval_start = time.time()
            nodes, seed_node_ids = await self.retriever.retrieve_async(
                query_text, self.edges, top_k, max_hops
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
            active_edges = filter_active_edges(self.edges, active_node_ids)
            centrality_scores = await compute_centrality_metrics_async(nodes, active_edges)
            timings["centrality"] = time.time() - centrality_start

            # Allow cancellation
            await asyncio.sleep(0)

            # Step 3: Get similarity scores from retriever results
            retrieval_results = await self.retriever.retrieve_by_similarity_async(query_text, top_k)
            similarity_scores = {node.id: score for node, score in retrieval_results}

            # Step 4: Assemble context
            context, _context_blocks = assemble_context(
                nodes, seed_node_ids, similarity_scores, centrality_scores, max_tokens
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
                query_text, self.edges, top_k=TOP_K, max_hops=1  # At least 1 hop for context
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
                seed_node_ids, self.edges, max_hops, edge_types or ["semantic"]
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

    async def cancel_all_queries(self: "QueryEngine") -> None:
        """Cancel all active queries gracefully.

        This method cancels all currently running async queries and waits
        for them to complete or be cancelled.

        """
        for task in self._active_tasks:
            task.cancel()

        # Wait for all tasks to complete/cancel
        await asyncio.gather(*self._active_tasks, return_exceptions=True)
        self._active_tasks.clear()

    async def batch_query_async(
        self: "QueryEngine",
        queries: list[str],
        top_k: int = 20,
        max_hops: int = 4,
        max_tokens: int = 3000,
        batch_size: int = 5,
        timeout: float | None = None,
        enable_hierarchical_lifting: bool = True,
        lift_levels: int = 2,
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
                        with_explanation=False,  # Disable for batch performance
                        enable_hierarchical_lifting=enable_hierarchical_lifting,
                        lift_levels=lift_levels,
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

    async def query_streaming_async(
        self: "QueryEngine",
        query_text: str,
        top_k: int = TOP_K,
        max_hops: int = MAX_HOPS,
        max_tokens: int = MAX_TOKENS,
        chunk_size: int = 50,
        enable_hierarchical_lifting: bool = True,
        lift_levels: int = 2,
    ) -> AsyncIterator[tuple[str, dict]]:
        """Execute query with streaming results for memory efficiency.

        Yields context chunks as nodes are processed, allowing for:
        - Lower memory usage on large result sets
        - Progressive UI updates
        - Early termination if needed

        Args:
        ----
            query_text: Natural language query
            top_k: Number of seed nodes
            max_hops: Graph traversal depth
            max_tokens: Maximum context tokens
            chunk_size: Nodes per chunk (default: 50)
            enable_hierarchical_lifting: Apply hierarchical context lifting
            lift_levels: Directory levels to traverse upward

        Yields:
        ------
            Tuple of (context_chunk, metadata_dict)

        Example:
        -------
            >>> async for context, meta in engine.query_streaming_async(query):
            ...     print(f"Chunk {meta['chunk_index']}: {len(context)} chars")
            ...     display_partial_results(context)
            ...     if meta['is_last']:
            ...         print(f"Total nodes: {meta['total_nodes']}")
        """
        start_time = time.time()

        try:
            all_nodes = []
            seed_node_ids = []

            # Stream retrieve nodes in chunks
            chunk_index = 0
            async for nodes_chunk, is_last in self.retriever.retrieve_streaming_async(
                query_text, self.edges, top_k, max_hops, chunk_size
            ):
                all_nodes.extend(nodes_chunk)

                # Build partial context from accumulated nodes
                if all_nodes:
                    # Get similarity scores (only need to do once)
                    if chunk_index == 0:
                        retrieval_results = await self.retriever.retrieve_by_similarity_async(
                            query_text, top_k
                        )
                        similarity_scores = {node.id: score for node, score in retrieval_results}
                        seed_node_ids = [node.id for node, _ in retrieval_results[:top_k]]

                    # Compute centrality on accumulated nodes
                    active_node_ids = {node.id for node in all_nodes}
                    active_edges = [
                        edge
                        for edge in self.edges
                        if edge.source in active_node_ids and edge.target in active_node_ids
                    ]

                    centrality_scores = await compute_centrality_metrics_async(
                        all_nodes, active_edges
                    )

                    # Assemble context from accumulated nodes
                    context, _ = assemble_context(
                        all_nodes,
                        seed_node_ids,
                        similarity_scores,
                        centrality_scores,
                        max_tokens,
                    )

                    # Yield chunk with metadata
                    metadata = {
                        "chunk_index": chunk_index,
                        "nodes_in_chunk": len(nodes_chunk),
                        "total_nodes_so_far": len(all_nodes),
                        "is_last": is_last,
                        "elapsed_time": time.time() - start_time,
                    }

                    yield (context, metadata)

                chunk_index += 1

        except QueryError:
            raise
        except Exception as error:
            raise QueryError(
                "Streaming query execution failed",
                {"error": str(error), "query": query_text[:MAX_QUERY_PREVIEW_LENGTH]},
            ) from error

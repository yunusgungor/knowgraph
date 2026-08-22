"""Query retriever with vector search and graph expansion.

Implements seed node retrieval via sparse lexical search followed by
graph traversal expansion.

Supports both sync and async modes for backward compatibility.
"""

import asyncio
from pathlib import Path
from typing import Any
from uuid import UUID

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from knowgraph.application.querying.query_expansion import QueryExpander
from knowgraph.config import (
    MAX_HOPS,
    MAX_QUERY_PREVIEW_LENGTH,
    TOP_K,
    get_settings,
)
from knowgraph.domain.algorithms.traversal import traverse_graph_reference_aware
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder
from knowgraph.infrastructure.search.sparse_index import SparseIndex
from knowgraph.infrastructure.storage.filesystem import read_node_json
from knowgraph.shared.exceptions import QueryError
from knowgraph.shared.memory_profiler import memory_guard
from knowgraph.shared.tracing import trace_operation


class QueryRetriever:
    """Retrieves relevant nodes for a query using vector search + graph expansion.

    Workflow:
        1. Generate query embedding (sparse)
        2. Search Sparse index for top-k similar nodes (seeds)
        3. Expand seeds via REFERENCE-AWARE graph traversal (CODE DEPENDENCIES FIRST!)
        4. Return active subgraph nodes

    Attributes
    ----------
        sparse_embedder: Sparse embedding generator
        sparse_index: Sparse index
        graph_store_path: Root storage directory

    """

    def __init__(
        self: "QueryRetriever",
        graph_store_path: Path,
        intelligence_provider: Any | None = None,
    ) -> None:
        """Initialize retriever.

        Args:
        ----
            graph_store_path: Root graph storage directory
            intelligence_provider: Optional LLM provider for query expansion.
                When set, expansion runs against the real provider instead of
                the hardcoded mock that returns terms for only a few keywords.

        Raises:
        ------
            QueryError: If graph store cannot be loaded

        """
        self.graph_store_path = graph_store_path

        self.sparse_embedder = SparseEmbedder()
        self.sparse_index = SparseIndex()
        try:
            self.sparse_index.load(graph_store_path / "index")
        except Exception:
            # Often index might not exist yet if fresh, but log/raise if critical
            pass

        # Query expansion is wired end-to-end: the caller (MCP/CLI) expands the
        # raw query with the LLM provider before calling retrieve(). Only install
        # an expander here when a real provider is supplied, so it never falls
        # back to the toy "mock" provider that returns terms for a few keywords.
        if intelligence_provider and self._query_expansion_enabled():
            self.expander = QueryExpander(intelligence_provider=intelligence_provider)

    @staticmethod
    def _query_expansion_enabled() -> bool:
        """Return whether LLM query expansion is enabled via settings.

        Reads the Pydantic ``QuerySettings.enable_query_expansion`` (tunable
        through ``KNOWGRAPH_QUERY_ENABLE_QUERY_EXPANSION``) so the .env knob
        actually takes effect, instead of the hardcoded legacy constant.
        """
        try:
            return get_settings().query.enable_query_expansion
        except Exception:
            # Fall back to the historical default when settings are unavailable.
            return True

    def retrieve(
        self: "QueryRetriever",
        query_text: str,
        edges: list[Edge],
        top_k: int = TOP_K,
        max_hops: int = MAX_HOPS,
        use_code_search: bool = False,
        enable_temporal_filter: bool = False,
    ) -> tuple[list[Node], list[UUID]]:
        """Retrieve relevant nodes for query (REFERENCE-AWARE!).

        Args:
        ----
            query_text: Natural language query
            edges: All graph edges
            top_k: Number of seed nodes
            max_hops: Graph traversal depth
            use_code_search: Use code embeddings instead of text
            enable_temporal_filter: When True (Graph Engineering transfer,
                opt-in), drop edges sourced from superseded conversations before
                traversal — "stale fact never current".

        Returns:
        -------
            (active_subgraph_nodes, seed_node_ids)

        Raises:
        ------
            QueryError: If retrieval fails

        """
        with memory_guard(
            operation_name=f"retrieve[{query_text[:30]}]",
            warning_threshold_mb=80,
            critical_threshold_mb=200,
        ):
            with trace_operation(
                "query_retriever.retrieve",
                query_length=len(query_text),
                top_k=top_k,
                max_hops=max_hops,
            ):
                try:
                    # Step 1: Generate query embedding & Search
                    # Sparse Retrieval
                    search_text = query_text

                    if hasattr(self, "expander") and self.expander:
                        expansion_terms = self.expander.expand_query(query_text)
                        if expansion_terms:
                            # Append expansion terms to original query for broader token match
                            search_text = f"{query_text} {' '.join(expansion_terms)}"

                    if use_code_search:
                        query_tokens = self.sparse_embedder.embed_code(search_text)
                    else:
                        query_tokens = self.sparse_embedder.embed_text(search_text)

                    results = self.sparse_index.search(query_tokens, top_k)
                    # results is list of (doc_id, score) where doc_id is str
                    seed_node_ids = [UUID(node_id) for node_id, _ in results]

                    # Step 2: Expand via REFERENCE-AWARE graph traversal (CODE DEPENDENCIES FIRST!)
                    # Graph Engineering transfer (opt-in): drop edges sourced from
                    # superseded conversations so stale facts never expand the subgraph.
                    traversal_edges: list[Edge] = edges
                    if enable_temporal_filter:
                        from knowgraph.domain.claims.temporal_filter import filter_edges_by_temporal

                        traversal_edges = filter_edges_by_temporal(edges, "")

                    expanded_node_ids = traverse_graph_reference_aware(seed_node_ids, traversal_edges, max_hops)

                    # Step 3: Load nodes CONCURRENTLY (using thread pool for I/O)
                    from concurrent.futures import ThreadPoolExecutor, as_completed

                    nodes = []
                    with ThreadPoolExecutor(max_workers=10) as executor:
                        # Submit all node loading tasks
                        future_to_id = {
                            executor.submit(read_node_json, node_id, self.graph_store_path): node_id
                            for node_id in expanded_node_ids
                        }

                        # Collect results as they complete
                        for future in as_completed(future_to_id):
                            node = future.result()
                            if node:
                                nodes.append(node)

                    # Enrich results with related conversations so the retrieved
                    # subgraph also surfaces conversations discussing these files.
                    try:
                        from knowgraph.application.querying.conversation_search import (
                            enrich_with_conversations,
                        )

                        nodes, _ = enrich_with_conversations(nodes, self.graph_store_path, edges=edges)
                    except Exception:
                        # Enrichment is best-effort; never fail retrieval over it.
                        pass

                    return nodes, seed_node_ids

                except QueryError:
                    raise
                except Exception as error:
                    raise QueryError(
                        f"Failed to retrieve nodes: {error!s}",
                {"error": str(error), "query": query_text[:MAX_QUERY_PREVIEW_LENGTH]},
            ) from error

    def retrieve_by_similarity(
        self: "QueryRetriever", query_text: str, top_k: int = TOP_K, use_code_search: bool = False
    ) -> list[tuple[Node, float]]:
        """Retrieve nodes by similarity only (no graph expansion).

        Args:
        ----
            query_text: Query text
            top_k: Number of results
            use_code_search: Use code embeddings instead of text

        Returns:
        -------
            List of (node, similarity_score) tuples

        """
        if use_code_search:
            # Just map to text embed if code specific logic isn't different for sparse
            query_tokens = self.sparse_embedder.embed_code(query_text)
        else:
            query_tokens = self.sparse_embedder.embed_text(query_text)

        results = self.sparse_index.search(query_tokens, top_k)
        # results: list[(str_id, score)]

        nodes_with_scores = []
        for node_id, score in results:
            # Ensure ID is UUID
            if isinstance(node_id, str):
                try:
                    uuid_id = UUID(node_id)
                except ValueError:
                    continue
            else:
                uuid_id = node_id

            node = read_node_json(uuid_id, self.graph_store_path)
            if node:
                nodes_with_scores.append((node, score))

        return nodes_with_scores

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True,
    )
    async def retrieve_async(
        self: "QueryRetriever",
        query_text: str,
        edges: list[Edge],
        top_k: int = TOP_K,
        max_hops: int = MAX_HOPS,
        use_code_search: bool = False,
    ) -> tuple[list[Node], list[UUID]]:
        """Retrieve relevant nodes for query (async version with retry logic).

        Improvements over sync version:
        - Concurrent node loading
        - Async query expansion
        - Automatic retry on transient failures

        Args:
        ----
            query_text: Natural language query
            edges: All graph edges
            top_k: Number of seed nodes
            max_hops: Graph traversal depth
            use_code_search: Use code embeddings instead of text

        Returns:
        -------
            (active_subgraph_nodes, seed_node_ids)

        Raises:
        ------
            QueryError: If retrieval fails after retries

        """
        with memory_guard(
            operation_name=f"retrieve_async[{query_text[:30]}]",
            warning_threshold_mb=80,
            critical_threshold_mb=200,
        ):
            with trace_operation(
                "query_retriever.retrieve_async",
                query_length=len(query_text),
                top_k=top_k,
                max_hops=max_hops,
            ):
                try:
                    # Step 1: Generate query embedding & Search
                    search_text = query_text

                    # Async query expansion if available
                    if hasattr(self, "expander") and self.expander:
                        expansion_terms = await self.expander.expand_query_async(query_text)
                        if expansion_terms:
                            search_text = f"{query_text} {' '.join(expansion_terms)}"

                    # Embedding generation (sync - fast enough)
                    if use_code_search:
                        query_tokens = self.sparse_embedder.embed_code(search_text)
                    else:
                        query_tokens = self.sparse_embedder.embed_text(search_text)

                    # Search ASYNC for better performance with parallel term processing
                    results = await self.sparse_index.search_async(query_tokens, top_k)
                    seed_node_ids = [UUID(node_id) for node_id, _ in results]

                    # Step 2: Expand via REFERENCE-AWARE graph traversal (CODE DEPENDENCIES FIRST!)
                    expanded_node_ids = traverse_graph_reference_aware(seed_node_ids, edges, max_hops)

                    # Step 3: Load nodes CONCURRENTLY
                    nodes = await self._load_nodes_async(expanded_node_ids)

                    # Enrich results with related conversations (best-effort).
                    try:
                        from knowgraph.application.querying.conversation_search import (
                            enrich_with_conversations,
                        )

                        nodes, _ = enrich_with_conversations(nodes, self.graph_store_path, edges=edges)
                    except Exception:
                        pass

                    return nodes, seed_node_ids

                except QueryError:
                    raise
                except Exception as error:
                    raise QueryError(
                        f"Failed to retrieve nodes: {error!s}",
                        {"error": str(error), "query": query_text[:MAX_QUERY_PREVIEW_LENGTH]},
                    ) from error

    async def _load_nodes_async(self: "QueryRetriever", node_ids: list[UUID]) -> list[Node]:
        """Load multiple nodes concurrently.

        Uses asyncio.gather for parallel file I/O operations.

        Args:
        ----
            node_ids: List of node UUIDs to load

        Returns:
        -------
            List of loaded nodes (None values filtered out)

        """

        async def load_node(node_id: UUID) -> Node | None:
            """Load a single node using executor for sync I/O."""
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, read_node_json, node_id, self.graph_store_path)

        # Load all nodes concurrently
        tasks = [load_node(node_id) for node_id in node_ids]
        results = await asyncio.gather(*tasks)

        # Filter out None values
        return [node for node in results if node is not None]

    async def retrieve_by_similarity_async(
        self: "QueryRetriever",
        query_text: str,
        top_k: int = TOP_K,
        use_code_search: bool = False,
    ) -> list[tuple[Node, float]]:
        """Retrieve nodes by similarity only (async version, no graph expansion).

        Args:
        ----
            query_text: Query text
            top_k: Number of results
            use_code_search: Use code embeddings instead of text

        Returns:
        -------
            List of (node, similarity_score) tuples

        """
        # Embedding generation (sync - fast enough)
        if use_code_search:
            query_tokens = self.sparse_embedder.embed_code(query_text)
        else:
            query_tokens = self.sparse_embedder.embed_text(query_text)

        # Search ASYNC for better performance with parallel term processing
        results = await self.sparse_index.search_async(query_tokens, top_k)

        # Load nodes concurrently
        async def load_node_with_score(node_id_str: str, score: float) -> tuple[Node, float] | None:
            """Load node and return with score."""
            try:
                uuid_id = UUID(node_id_str) if isinstance(node_id_str, str) else node_id_str
            except ValueError:
                return None

            loop = asyncio.get_event_loop()
            node = await loop.run_in_executor(None, read_node_json, uuid_id, self.graph_store_path)

            if node:
                return (node, score)
            return None

        # Load all nodes concurrently
        tasks = [load_node_with_score(node_id, score) for node_id, score in results]
        results_with_nodes = await asyncio.gather(*tasks)

        # Filter out None values
        return [result for result in results_with_nodes if result is not None]

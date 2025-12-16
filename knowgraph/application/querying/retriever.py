"""Query retriever with vector search and graph expansion.

Implements seed node retrieval via sparse lexical search followed by
graph traversal expansion.
"""

from pathlib import Path
from uuid import UUID

from knowgraph.application.querying.query_expansion import QueryExpander
from knowgraph.config import (
    ENABLE_QUERY_EXPANSION,
    MAX_HOPS,
    MAX_QUERY_PREVIEW_LENGTH,
    TOP_K,
)
from knowgraph.domain.algorithms.traversal import traverse_graph_bfs
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder
from knowgraph.infrastructure.search.sparse_index import SparseIndex
from knowgraph.infrastructure.storage.filesystem import read_node_json
from knowgraph.shared.exceptions import QueryError


class QueryRetriever:
    """Retrieves relevant nodes for a query using vector search + graph expansion.

    Workflow:
        1. Generate query embedding (sparse)
        2. Search Sparse index for top-k similar nodes (seeds)
        3. Expand seeds via graph traversal
        4. Return active subgraph nodes

    Attributes
    ----------
        sparse_embedder: Sparse embedding generator
        sparse_index: Sparse index
        graph_store_path: Root storage directory

    """

    def __init__(self: "QueryRetriever", graph_store_path: Path) -> None:
        """Initialize retriever.

        Args:
        ----
            graph_store_path: Root graph storage directory

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

        if ENABLE_QUERY_EXPANSION:
            # Use "mock" provider for now if no API key, or default from config
            self.expander = QueryExpander(provider="mock")

    def retrieve(
        self: "QueryRetriever",
        query_text: str,
        edges: list[Edge],
        top_k: int = TOP_K,
        max_hops: int = MAX_HOPS,
        use_code_search: bool = False,
    ) -> tuple[list[Node], list[UUID]]:
        """Retrieve relevant nodes for query.

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
            QueryError: If retrieval fails

        """
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

            # Step 2: Expand via graph traversal
            expanded_node_ids = traverse_graph_bfs(seed_node_ids, edges, max_hops)

            # Step 3: Load nodes
            nodes = []
            for node_id in expanded_node_ids:
                node = read_node_json(node_id, self.graph_store_path)
                if node:
                    nodes.append(node)

            return nodes, seed_node_ids

        except QueryError:
            raise
        except Exception as error:
            raise QueryError(
                "Failed to retrieve nodes",
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

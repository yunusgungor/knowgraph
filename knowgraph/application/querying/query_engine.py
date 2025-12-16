"""Query engine - orchestrates full query pipeline.

Coordinates retrieval, graph reasoning, and context assembly.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from knowgraph.application.querying.context_assembly import assemble_context
from knowgraph.application.querying.explanation import ExplanationObject, generate_explanation
from knowgraph.application.querying.retriever import QueryRetriever
from knowgraph.config import (
    DEFAULT_CENTRALITY_SCORE,
    MAX_HOPS,
    MAX_QUERY_PREVIEW_LENGTH,
    MAX_TOKENS,
    TOP_K,
)
from knowgraph.domain.algorithms.centrality import compute_centrality_metrics
from knowgraph.infrastructure.storage.filesystem import (
    read_all_edges,
    read_node_json,
)
from knowgraph.shared.exceptions import QueryError


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
        """Execute full query pipeline.

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
            # Filter edges to active subgraph
            active_node_ids = {node.id for node in nodes}
            active_edges = [
                edge
                for edge in self.edges
                if edge.source in active_node_ids and edge.target in active_node_ids
            ]
            centrality_scores = compute_centrality_metrics(nodes, active_edges)
            timings["centrality"] = time.time() - centrality_start

            # Step 3: Get similarity scores from retriever results
            retrieval_results = self.retriever.retrieve_by_similarity(query_text, top_k)
            similarity_scores = {node.id: score for node, score in retrieval_results}

            # Step 4: Assemble context
            context, _context_blocks = assemble_context(
                nodes, seed_node_ids, similarity_scores, centrality_scores, max_tokens
            )

            # Step 5: Return context
            answer = context

            # Step 6: Generate explanation (if requested, now context-based only)
            explanation = None
            if with_explanation:
                # Get context nodes from context_blocks
                context_nodes = [n for n in nodes if n.id in {n.id for n in nodes}][:30]
                # Flatten centrality scores to single dict
                flat_centralities = {
                    node_id: scores.get("degree", DEFAULT_CENTRALITY_SCORE)
                    for node_id, scores in centrality_scores.items()
                }
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

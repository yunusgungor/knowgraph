"""Refactored utilities - extracted from large functions.

This module contains refactored helper functions extracted from large,
complex functions to improve readability and maintainability.
"""

from typing import Any
from uuid import UUID

from knowgraph.domain.models.edge import Edge


def filter_active_edges(edges: list[Edge], active_node_ids: set[UUID]) -> list[Edge]:
    """Filter edges to only those within active subgraph.

    Args:
    ----
        edges: All edges
        active_node_ids: Set of active node IDs

    Returns:
    -------
        Filtered edges within active subgraph
    """
    return [
        edge for edge in edges if edge.source in active_node_ids and edge.target in active_node_ids
    ]


def flatten_centrality_scores(
    centrality_scores: dict[UUID, dict[str, float]],
    metric: str = "degree",
    default: float = 0.0,
) -> dict[UUID, float]:
    """Flatten nested centrality scores to single metric.

    Args:
    ----
        centrality_scores: Nested centrality scores by node ID
        metric: Metric to extract (default: "degree")
        default: Default value if metric not found

    Returns:
    -------
        Flattened scores by node ID
    """
    return {node_id: scores.get(metric, default) for node_id, scores in centrality_scores.items()}


def validate_required_argument(arguments: dict[str, Any], key: str) -> str | None:
    """Validate and extract required argument from MCP arguments.

    Args:
    ----
        arguments: MCP tool arguments
        key: Required key to extract

    Returns:
    -------
        Error message if missing, None if valid
    """
    value = arguments.get(key)
    if not value:
        return f"Error: {key} is required."
    return None


def build_error_response(error: Exception, prefix: str = "Error") -> str:
    """Build consistent error response message.

    Args:
    ----
        error: Exception that occurred
        prefix: Error message prefix

    Returns:
    -------
        Formatted error message
    """
    return f"{prefix}: {error!s}"


def build_graph_stats_response(manifest: Any) -> str:
    """Build graph statistics response message.

    Args:
    ----
        manifest: Manifest object with graph statistics

    Returns:
    -------
        Formatted statistics message
    """
    return (
        f"Graph Stats (v{manifest.version})\n"
        f"Nodes: {manifest.node_count}\n"
        f"Edges: {manifest.edge_count}\n"
        f"Semantic Edges: {manifest.semantic_edge_count}\n"
        f"Files Indexed: {len(manifest.file_hashes)}"
    )


def build_validation_response(result: Any) -> str:
    """Build validation result response message.

    Args:
    ----
        result: ValidationResult object

    Returns:
    -------
        Formatted validation message
    """
    status = "VALID" if result.valid else "INVALID"
    message = f"Graph Validation Status: {status}\n"
    if not result.valid:
        message += f"\nErrors:\n{result.get_error_summary()}"
    else:
        message += "\nGraph is consistent and ready for queries."
    return message


def extract_query_parameters(arguments: dict[str, Any]) -> dict[str, Any]:
    """Extract and validate query parameters from MCP arguments.

    Args:
    ----
        arguments: MCP tool arguments

    Returns:
    -------
        Dictionary of extracted parameters with defaults
    """
    return {
        "top_k": arguments.get("top_k", 20),
        "max_hops": arguments.get("max_hops", 4),
        "with_explanation": arguments.get("with_explanation", False),
        "expand_query": arguments.get("expand_query", False),
        "max_tokens": arguments.get("max_tokens", 3000),
        "enable_hierarchical_lifting": arguments.get("enable_hierarchical_lifting", True),
        "lift_levels": arguments.get("lift_levels", 2),
        "system_prompt": arguments.get("system_prompt"),
    }


def build_llm_prompt(
    query: str,
    context: str,
    system_prompt: str | None = None,
    explanation_data: str | None = None,
) -> str:
    """Build LLM prompt from query and context.

    Args:
    ----
        query: User query
        context: Retrieved context
        system_prompt: Optional system prompt override
        explanation_data: Optional explanation JSON

    Returns:
    -------
        Complete prompt for LLM
    """
    base_system = (
        system_prompt
        if system_prompt
        else "You are a helpful assistant. Use the following context to answer the user's question."
    )

    prompt = f"{base_system}\n\nContext:\n{context}\n\nQuestion: {query}\n\nAnswer:"

    if explanation_data:
        prompt += f"\n\nExplanation Data:\n{explanation_data}"

    return prompt


def format_impact_result(result: Any) -> str:
    """Format impact analysis result to string.

    Args:
    ----
        result: QueryResult from impact analysis

    Returns:
    -------
        Formatted text report
    """
    output = "Impact Analysis (Semantic)\n"
    output += "--------------------------\n"

    if hasattr(result, "original_question") and result.original_question:
        output += f"Target: {result.original_question}\n"

    if hasattr(result, "active_subgraph_size"):
        output += f"Affected Nodes: {result.active_subgraph_size}\n"

    output += "\nReasoning & Details:\n"
    output += result.context

    if hasattr(result, "explanation") and result.explanation:
        explanation = result.explanation
        if hasattr(explanation, "reasoning_paths") and explanation.reasoning_paths:
            output += "\n\nKey Dependencies:\n"
            for path in explanation.reasoning_paths[:5]:
                output += f"- {path}\n"

    return output

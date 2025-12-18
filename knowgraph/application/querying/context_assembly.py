"""Context assembly with token-aware packing and importance scoring.

Implements greedy packing of nodes into LLM context with role separation
and importance-based ordering.
"""

from dataclasses import dataclass
from uuid import UUID

import tiktoken

from knowgraph.config import (
    ALPHA,
    BETA,
    DEFAULT_CENTRALITY_SCORE,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_SIMILARITY_SCORE,
    GAMMA,
    MAX_TOKEN_COUNT_FOR_PENALTY,
    MAX_TOKENS,
    SEED_NODE_BONUS,
    TOKEN_PENALTY_FACTOR,
)
from knowgraph.domain.models.node import Node


@dataclass
class ContextBlock:
    """A formatted block of context for LLM.

    Attributes
    ----------
        node_id: Source node UUID
        content: Formatted content
        role: Node role (code/readme/config/text)
        importance: Combined importance score
        tokens: Token count

    """

    node_id: UUID
    content: str
    role: str
    importance: float
    tokens: int


def score_node_importance(
    node: Node,
    is_seed: bool,
    similarity_score: float,
    centrality_score: float,
) -> float:
    """Calculate node importance for context inclusion.

    Formula: alpha·similarity + beta·centrality + gamma·is_seed

    Args:
    ----
        node: Node to score
        is_seed: Whether node is a seed from vector search
        similarity_score: Cosine similarity to query [0, 1]
        centrality_score: Composite centrality [0, 1]

    Returns:
    -------
        Importance score [0, 1]

    """
    seed_bonus = SEED_NODE_BONUS if is_seed else 0.0

    importance = ALPHA * similarity_score + BETA * centrality_score + GAMMA * seed_bonus

    # Apply role weight
    importance *= node.role_weight

    # Token penalty (favor shorter content)
    penalty_ratio = min(node.token_count, MAX_TOKEN_COUNT_FOR_PENALTY) / MAX_TOKEN_COUNT_FOR_PENALTY
    token_penalty = 1.0 - penalty_ratio * TOKEN_PENALTY_FACTOR
    importance *= token_penalty

    return min(importance, 1.0)


def assemble_context(
    nodes: list[Node],
    seed_node_ids: list[UUID],
    similarity_scores: dict[UUID, float],
    centrality_scores: dict[UUID, dict[str, float]],
    max_tokens: int = MAX_TOKENS,
) -> tuple[str, list[ContextBlock]]:
    """Assemble context from nodes with greedy token-aware packing.

    Args:
    ----
        nodes: Candidate nodes
        seed_node_ids: Seed node UUIDs
        similarity_scores: Node similarity scores
        centrality_scores: Node centrality metrics
        max_tokens: Maximum context tokens

    Returns:
    -------
        (formatted_context, context_blocks)

    """
    try:
        tokenizer = tiktoken.encoding_for_model(DEFAULT_OPENAI_MODEL)
    except KeyError:
        tokenizer = tiktoken.get_encoding("o200k_base")

    # Score and sort nodes
    blocks = []
    for node in nodes:
        is_seed = node.id in seed_node_ids
        similarity = similarity_scores.get(node.id, DEFAULT_SIMILARITY_SCORE)
        centrality = centrality_scores.get(node.id, {}).get("composite", DEFAULT_CENTRALITY_SCORE)

        importance = score_node_importance(node, is_seed, similarity, centrality)

        # Format content
        formatted = _format_node_content(node)
        tokens = len(tokenizer.encode(formatted))

        blocks.append(
            ContextBlock(
                node_id=node.id,
                content=formatted,
                role=node.type,
                importance=importance,
                tokens=tokens,
            )
        )

    # Sort by importance (descending)
    blocks.sort(key=lambda b: b.importance, reverse=True)

    # Greedy packing
    selected_blocks = []
    total_tokens = 0

    for block in blocks:
        if total_tokens + block.tokens <= max_tokens:
            selected_blocks.append(block)
            total_tokens += block.tokens

    # Sort selected blocks by role (code > readme > config > text)
    role_order = {"code": 0, "readme": 1, "config": 2, "text": 3}
    selected_blocks.sort(key=lambda b: role_order.get(b.role, 4))

    # Format final context
    context = _format_context_blocks(selected_blocks)

    return context, selected_blocks


def _format_node_content(node: Node) -> str:
    """Format node content for context.

    Args:
    ----
        node: Node to format

    Returns:
    -------
        Formatted content with header

    """
    header = f"## {node.title}\n"
    if node.path:
        header += f"**Source**: `{node.path}`"
        if node.line_start and node.line_end:
            header += f" (lines {node.line_start}-{node.line_end})"
        header += "\n\n"

    return header + node.content


def _format_context_blocks(blocks: list[ContextBlock]) -> str:
    """Format context blocks into final context string.

    Groups by role with section headers.

    Args:
    ----
        blocks: Context blocks

    Returns:
    -------
        Formatted context

    """
    sections = []

    # Group by role
    current_role: str | None = None
    current_section: list[str] = []

    for block in blocks:
        if block.role != current_role:
            if current_section:
                sections.append("\n\n".join(current_section))
            current_role = block.role
            current_section = [_role_header(block.role)]

        current_section.append(block.content)

    if current_section:
        sections.append("\n\n".join(current_section))

    return "\n\n---\n\n".join(sections)


def _role_header(role: str) -> str:
    """Get section header for role.

    Args:
    ----
        role: Node role

    Returns:
    -------
        Section header

    """
    headers = {
        "code": "# Code Reference",
        "readme": "# Documentation",
        "config": "# Configuration",
        "text": "# Additional Context",
    }
    return headers.get(role, "# Context")

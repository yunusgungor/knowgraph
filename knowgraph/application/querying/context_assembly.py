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

# File-type multiplier: boost code files, penalize metadata/config
_CODE_EXTS = {".tsx", ".ts", ".js", ".jsx", ".py", ".java", ".go", ".rs", ".rb", ".php", ".cs", ".cpp", ".c", ".h"}
_META_NAMES = {"manifest.json", "package.json", "metadata.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
_CONFIG_EXTS = {".env", ".env.example", ".env.local", ".env.development"}
_CONFIG_NAMES = {"tsconfig.json", "jsconfig.json", "vite.config.ts", "vite.config.js", "next.config.js", ".eslintrc.json", ".prettierrc.json"}


def _file_type_multiplier(node: Node) -> float:
    """Boost code files, penalize metadata/config for retrieval precision."""
    path = (node.path or "").lower()
    name = path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] if path else ""
    ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""

    # Penalize metadata files (manifest.json, package.json, etc.)
    if name in _META_NAMES:
        return 0.3
    # Penalize config files
    if ext in _CONFIG_EXTS or name in _CONFIG_NAMES:
        return 0.4
    # Boost code files
    if ext in _CODE_EXTS:
        return 1.3
    # Default: neutral
    return 1.0


def _query_match_boost(node: Node, query_text: str) -> float:
    """Boost nodes whose path directly matches the query term.

    Only boosts on exact or near-exact path matches to avoid false positives.
    Partial single-word matches (e.g. "vat" matching "VatCalculator") are
    NOT boosted because they create noise for unrelated queries.
    """
    query_lower = query_text.lower().strip()
    path_lower = (node.path or "").lower()

    # Exact full query in path (e.g. "reversevatmodule" in "ReverseVatModule.tsx")
    if query_lower in path_lower:
        return 0.30

    # Multi-word: ALL query words must appear as path words (not just one)
    query_words = [w for w in query_lower.split() if len(w) > 3]
    if len(query_words) >= 2:
        path_words = set(path_lower.replace("/", " ").replace("\\", " ").replace(".", " ").replace("-", " ").split())
        if all(w in path_words for w in query_words):
            return 0.20

    # Single exact word match (e.g. query="QuickVatCalculator", path contains "quickvatcalculator")
    if len(query_words) == 1:
        path_compact = path_lower.replace("/", "").replace("\\", "").replace(".", "").replace("-", "").replace("_", "")
        if query_words[0] in path_compact:
            return 0.25

    return 0.0


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
    path: str = ""


def score_node_importance(
    node: Node,
    is_seed: bool,
    similarity_score: float,
    centrality_score: float,
    reference_path_quality: float = 0.0,
    grounded: bool | None = None,
    query_text: str = "",
) -> float:
    """Calculate node importance for context inclusion (REFERENCE-AWARE).

    Formula: alpha·similarity + beta·centrality + gamma·is_seed + delta·ref_path_quality

    Args:
    ----
        node: Node to score
        is_seed: Whether node is a seed from vector search
        similarity_score: Cosine similarity to query [0, 1]
        centrality_score: Composite centrality [0, 1]
        reference_path_quality: Quality of reference path to this node [0, 1]
                                (Higher if reached via reference edges vs semantic)
        grounded: When not None, the claim's grounding verdict (Graph Engineering
            transfer, E-132). Grounded nodes get a +20% importance bonus;
            ungrounded (graph-isolated) nodes a -50% penalty so they rank clearly
            below evidence-backed content and lose the context budget first —
            "evidence wins the budget".

    Returns:
    -------
        Importance score [0, 1]

    """
    seed_bonus = SEED_NODE_BONUS if is_seed else 0.0

    # ENHANCED: Add reference path quality to importance
    # Delta weight for reference path (stealing a bit from alpha/beta to balance)
    delta = 0.15  # Reference path quality weight
    adjusted_alpha = ALPHA * 0.85  # Reduce alpha slightly
    adjusted_beta = BETA * 0.85  # Reduce beta slightly

    importance = (
        adjusted_alpha * similarity_score
        + adjusted_beta * centrality_score
        + GAMMA * seed_bonus
        + delta * reference_path_quality
    )

    # Apply role weight
    importance *= node.role_weight

    # File-type multiplier: boost code, penalize metadata/config
    importance *= _file_type_multiplier(node)

    # Query-match boost: nodes whose path/content directly match the query term
    # get a significant importance boost so they're not crowded out by related files
    if query_text:
        importance += _query_match_boost(node, query_text)

    # Token penalty (favor shorter content)
    penalty_ratio = min(node.token_count, MAX_TOKEN_COUNT_FOR_PENALTY) / MAX_TOKEN_COUNT_FOR_PENALTY
    token_penalty = 1.0 - penalty_ratio * TOKEN_PENALTY_FACTOR
    importance *= token_penalty

    # Grounding verdict (opt-in): grounded evidence is preferred, unbacked demoted.
    if grounded is True:
        importance *= 1.2
    elif grounded is False:
        importance *= 0.5

    return min(importance, 1.0)


def compute_reference_path_quality(
    node_id: UUID,
    seed_ids: list[UUID],
    edges: list,  # Type hint as list to avoid circular import
) -> float:
    """Compute quality of reference path from seeds to this node.

    Higher quality if:
    - Path contains reference edges (vs only semantic)
    - Path is shorter
    - More reference edges in path

    Args:
    ----
        node_id: Target node
        seed_ids: Seed node IDs
        edges: All edges in active subgraph

    Returns:
    -------
        Path quality score [0, 1]

    """
    from collections import deque

    # BFS from seeds to find shortest path to node_id
    visited = set()
    queue = deque([(sid, [], 0) for sid in seed_ids])  # (current, path_edges, depth)

    best_path_quality = 0.0

    while queue:
        current, path_edges, depth = queue.popleft()

        if current == node_id:
            # Found path - compute quality
            if not path_edges:
                # Node is a seed
                quality = 1.0
            else:
                reference_count = sum(1 for e in path_edges if e.type == "reference")
                total_edges = len(path_edges)

                # Quality formula:
                # - 50% based on reference ratio
                # - 30% based on path shortness (inverse depth)
                # - 20% base for having any path
                ref_ratio = reference_count / total_edges if total_edges > 0 else 0.0
                shortness = max(0, 1.0 - (depth / 10.0))  # Penalize depth > 10

                quality = 0.2 + 0.5 * ref_ratio + 0.3 * shortness

            best_path_quality = max(best_path_quality, quality)
            continue

        if current in visited or depth > 6:  # Don't search too deep
            continue

        visited.add(current)

        # Expand to neighbors. Temporal/metadata edges (Graph Engineering transfer)
        # are not content links — exclude them from path quality.
        for edge in edges:
            if edge.type in ("supersedes", "contradicts"):
                continue
            if edge.source == current and edge.target not in visited:
                queue.append((edge.target, [*path_edges, edge], depth + 1))
            elif edge.target == current and edge.source not in visited:
                # For semantic edges, also traverse backward
                if edge.type != "reference":
                    queue.append((edge.source, [*path_edges, edge], depth + 1))

    return best_path_quality


def assemble_context(
    nodes: list[Node],
    seed_node_ids: list[UUID],
    similarity_scores: dict[UUID, float],
    centrality_scores: dict[UUID, dict[str, float]],
    max_tokens: int = MAX_TOKENS,
    edges: list | None = None,  # NEW: Optional edges for path quality
    enable_hierarchical_lifting: bool = True,  # NEW: Enable hierarchical context lifting
    lift_levels: int = 2,  # NEW: Number of directory levels to lift from
    grounded_verdicts: dict[UUID, bool] | None = None,  # Graph Engineering: grounding verdict per node id
    query_text: str = "",  # NEW: Original query for match boosting
) -> tuple[str, list[ContextBlock]]:
    """Assemble context from nodes with greedy token-aware packing (REFERENCE-AWARE).

    Args:
    ----
        nodes: Candidate nodes
        seed_node_ids: Seed node UUIDs
        similarity_scores: Node similarity scores
        centrality_scores: Node centrality metrics
        max_tokens: Maximum context tokens
        edges: Optional edges for reference path quality analysis

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
    # Cap reference path quality computation to avoid O(N*E) explosion
    # on large subgraphs. Only compute for top-scored nodes.
    _MAX_PATH_QUALITY_NODES = 100
    _seed_set = set(seed_node_ids)
    # Pre-sort by approximate importance to pick top candidates
    _pre_scored = []
    for node in nodes:
        _sim = similarity_scores.get(node.id, DEFAULT_SIMILARITY_SCORE)
        _cen = centrality_scores.get(node.id, {}).get("composite", DEFAULT_CENTRALITY_SCORE)
        _pre_scored.append((_sim + _cen + (SEED_NODE_BONUS if node.id in _seed_set else 0.0), node))
    _pre_scored.sort(key=lambda x: x[0], reverse=True)
    _path_quality_candidates = {n.id for _, n in _pre_scored[:_MAX_PATH_QUALITY_NODES]}

    for node in nodes:
        is_seed = node.id in seed_node_ids
        similarity = similarity_scores.get(node.id, DEFAULT_SIMILARITY_SCORE)
        centrality = centrality_scores.get(node.id, {}).get("composite", DEFAULT_CENTRALITY_SCORE)

        # NEW: Compute reference path quality if edges provided
        # Skip for nodes outside the top-scored candidate set (cap at 100)
        ref_path_quality = 0.0
        if edges and node.id in _path_quality_candidates:
            ref_path_quality = compute_reference_path_quality(node.id, seed_node_ids, edges)

        # Graph Engineering: pass the node's grounding verdict if provided.
        grounded = grounded_verdicts.get(node.id) if grounded_verdicts is not None else None

        importance = score_node_importance(
            node, is_seed, similarity, centrality, ref_path_quality, grounded=grounded,
            query_text=query_text,
        )

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
                path=node.path or "",
            )
        )

    # Sort by importance (descending)
    blocks.sort(key=lambda b: b.importance, reverse=True)

    # Same-file cohesion: a large file split into multiple chunk nodes must not
    # have its formula-bearing chunks dropped in favor of cheaper one-off files.
    # Phase A selects the best block per path; Phase B forces a selected path's
    # sibling chunks in (within budget); Phase C fills the rest with leftovers.
    selected_blocks: list[ContextBlock] = []
    total_tokens = 0
    used_paths: set[str] = set()

    # Phase A+B: take each path's top block, then its whole (multi-chunk) file.
    by_path: dict[str, list[ContextBlock]] = {}
    for block in blocks:
        by_path.setdefault(block.path, []).append(block)

    # A path with no path (single doc) is treated as one unit anyway.
    for block in blocks:
        if block.path in used_paths or total_tokens + block.tokens > max_tokens:
            continue
        # Skip truly tiny blocks (< 25 tokens) when a much larger sibling exists.
        # Threshold is low (25) to preserve meaningful function calls (32+ tokens)
        # while still skipping trivial ref-only nodes (13-20 chars like "Call: setRate").
        siblings = by_path.get(block.path, [])
        max_sibling_tokens = max((s.tokens for s in siblings), default=0)
        if block.tokens < 25 and max_sibling_tokens > block.tokens * 10:
            continue
        # Phase A: pick this path's best (already-aligned top) block.
        selected_blocks.append(block)
        total_tokens += block.tokens
        used_paths.add(block.path)
        # Phase B: force the rest of this path's chunks in while they fit.
        for sibling in by_path.get(block.path, []):
            if sibling is block or sibling in selected_blocks:
                continue
            if total_tokens + sibling.tokens <= max_tokens:
                selected_blocks.append(sibling)
                total_tokens += sibling.tokens

    # Phase C: fill leftover budget with any remaining unselected blocks.
    selected_ids = {b.node_id for b in selected_blocks}
    for block in blocks:
        if block.node_id in selected_ids:
            continue
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

"""Tag relationship graph for semantic tag discovery.

Builds and queries a graph of tag relationships based on:
- Tag similarity (via code tokenization)
- Tag co-occurrence
- Tag→Code references
"""

from pathlib import Path

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder


def compute_tag_similarity(tag1: str, tag2: str) -> float:
    """Compute similarity between two tags using tokenization.

    Args:
    ----
        tag1: First tag
        tag2: Second tag

    Returns:
    -------
        Similarity score (0-1)

    """
    embedder = SparseEmbedder()

    tokens1 = set(embedder.embed_code(tag1).keys())
    tokens2 = set(embedder.embed_code(tag2).keys())

    if not tokens1 or not tokens2:
        return 0.0

    # Jaccard similarity
    intersection = len(tokens1 & tokens2)
    union = len(tokens1 | tokens2)

    return intersection / union if union > 0 else 0.0


def build_tag_similarity_edges(
    all_tags: list[str],
    similarity_threshold: float = 0.3,
) -> list[Edge]:
    """Build similarity edges between tags.

    Args:
    ----
        all_tags: List of all tags in system
        similarity_threshold: Minimum similarity to create edge

    Returns:
    -------
        List of tag_similar_to edges

    """
    edges = []

    for i, tag1 in enumerate(all_tags):
        for tag2 in all_tags[i + 1 :]:  # Avoid duplicates
            similarity = compute_tag_similarity(tag1, tag2)

            if similarity >= similarity_threshold:
                # Create bidirectional edges
                edges.append(
                    Edge(
                        source=tag1,
                        target=tag2,
                        type="tag_similar_to",
                        score=similarity,
                        metadata={"similarity_method": "token_overlap"},
                    )
                )
                edges.append(
                    Edge(
                        source=tag2,
                        target=tag1,
                        type="tag_similar_to",
                        score=similarity,
                        metadata={"similarity_method": "token_overlap"},
                    )
                )

    return edges


def find_related_tags(
    tag: str,
    graph_store_path: Path,
    max_related: int = 5,
) -> list[tuple[str, float]]:
    """Find tags related to given tag.

    Args:
    ----
        tag: Tag to find relations for
        graph_store_path: Path to graph storage
        max_related: Maximum related tags to return

    Returns:
    -------
        List of (tag, similarity_score) tuples

    """
    # Load edges from filesystem
    from knowgraph.infrastructure.storage.filesystem import list_all_edges, read_edge_json

    edge_ids = list_all_edges(graph_store_path)

    # Find tag_similar_to edges from this tag
    related = []
    for edge_id in edge_ids:
        edge = read_edge_json(edge_id, graph_store_path)
        if edge and edge.type == "tag_similar_to" and edge.source == tag:
            related.append((edge.target, edge.score))

    # Sort by similarity and return top
    related.sort(key=lambda x: x[1], reverse=True)
    return related[:max_related]


def discover_tag_cluster(
    seed_tag: str,
    graph_store_path: Path,
    max_depth: int = 2,
) -> set[str]:
    """Discover cluster of related tags via graph traversal.

    Args:
    ----
        seed_tag: Starting tag
        graph_store_path: Path to graph storage
        max_depth: Maximum traversal depth

    Returns:
    -------
        Set of related tags

    """
    # Load edges from filesystem
    from knowgraph.infrastructure.storage.filesystem import list_all_edges, read_edge_json

    edge_ids = list_all_edges(graph_store_path)
    edges = []
    for edge_id in edge_ids:
        edge = read_edge_json(edge_id, graph_store_path)
        if edge:
            edges.append(edge)

    # BFS from seed tag
    visited = {seed_tag}
    queue = [(seed_tag, 0)]  # (tag, depth)

    while queue:
        current_tag, depth = queue.pop(0)

        if depth >= max_depth:
            continue

        # Find similar tags
        for edge in edges:
            if edge.type == "tag_similar_to" and edge.source == current_tag:
                if edge.target not in visited:
                    visited.add(edge.target)
                    queue.append((edge.target, depth + 1))

    return visited


# Example usage
if __name__ == "__main__":
    # Test tag similarity
    similarity = compute_tag_similarity("getUserById_auth", "authenticateUser")
    print(f"Similarity: {similarity:.2f}")

    # Test tag edge creation
    tags = ["getUserById", "authenticateUser", "loginFlow", "database_query"]
    edges = build_tag_similarity_edges(tags, similarity_threshold=0.2)
    print(f"Created {len(edges)} similarity edges")

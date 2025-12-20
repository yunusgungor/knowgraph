"""Topic analysis and trending detection.

Analyzes conversation patterns to identify:
- Most discussed topics
- Emerging technologies
- Knowledge gaps
"""

from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from knowgraph.application.tagging.auto_tagger import categorize_topic, extract_entities
from knowgraph.infrastructure.storage.filesystem import list_all_nodes, read_node_json


def analyze_trending_topics(
    graph_store_path: Path,
    time_window_days: int = 7,
    min_mentions: int = 2,
) -> dict:
    """Identify trending topics in recent conversations.

    Args:
    ----
        graph_store_path: Path to graph storage
        time_window_days: Days to analyze
        min_mentions: Minimum mentions to be considered

    Returns:
    -------
        Trending topics analysis

    """
    # Load recent conversations
    node_ids = list_all_nodes(graph_store_path)
    cutoff = datetime.now() - timedelta(days=time_window_days)

    recent_conversations = []
    for node_id in node_ids:
        node = read_node_json(node_id, graph_store_path)
        if not node or not node.metadata:
            continue

        # Check node type (attribute or metadata)
        node_type = getattr(node, "type", None) or node.metadata.get("type")
        if node_type not in ["conversation", "tagged_snippet"]:
            continue

        # Check timestamp
        if hasattr(node, "created_at") and node.created_at:
            node_time = datetime.fromtimestamp(node.created_at)
        elif "timestamp" in node.metadata:
            try:
                node_time = datetime.fromisoformat(node.metadata["timestamp"])
            except (ValueError, TypeError):
                # Skip nodes with invalid timestamps
                continue
        else:
            continue

        if node_time >= cutoff:
            recent_conversations.append(node)

    # Extract entities and topics from all conversations
    all_entities = []
    all_topics = []

    for conv in recent_conversations:
        entities = extract_entities(conv.content)
        topic = categorize_topic(conv.content, entities)

        all_entities.extend(entities)
        all_topics.append(topic)

    # Count occurrences
    entity_counts = Counter(all_entities)
    topic_counts = Counter(all_topics)

    # Filter by min mentions
    trending_entities = {
        entity: count for entity, count in entity_counts.most_common(20) if count >= min_mentions
    }

    trending_topics = {
        topic: count for topic, count in topic_counts.most_common(10) if count >= min_mentions
    }

    return {
        "time_window_days": time_window_days,
        "conversations_analyzed": len(recent_conversations),
        "trending_entities": trending_entities,
        "trending_topics": trending_topics,
        "top_entity": entity_counts.most_common(1)[0] if entity_counts else None,
        "top_topic": topic_counts.most_common(1)[0] if topic_counts else None,
    }


def identify_emerging_technologies(
    graph_store_path: Path,
    recent_days: int = 7,
    baseline_days: int = 30,
) -> list[tuple[str, float]]:
    """Identify technologies with increasing mentions.

    Compares recent mention rate to baseline.

    Args:
    ----
        graph_store_path: Path to graph storage
        recent_days: Recent period to analyze
        baseline_days: Baseline period for comparison

    Returns:
    -------
        List of (technology, growth_rate) tuples

    """
    # Get mentions in two time windows
    recent_cutoff = datetime.now() - timedelta(days=recent_days)
    baseline_cutoff = datetime.now() - timedelta(days=baseline_days)

    node_ids = list_all_nodes(graph_store_path)
    recent_entities = []
    baseline_entities = []

    for node_id in node_ids:
        node = read_node_json(node_id, graph_store_path)
        if not node or not node.metadata:
            continue

        # Check node type (attribute or metadata)
        node_type = getattr(node, "type", None) or node.metadata.get("type")
        if node_type not in ["conversation", "tagged_snippet"]:
            continue

        # Get timestamp
        if hasattr(node, "created_at") and node.created_at:
            node_time = datetime.fromtimestamp(node.created_at)
        elif "timestamp" in node.metadata:
            try:
                node_time = datetime.fromisoformat(node.metadata["timestamp"])
            except (ValueError, TypeError):
                # Skip nodes with invalid timestamps
                continue
        else:
            continue

        entities = extract_entities(node.content)

        # Categorize into time windows
        if node_time >= recent_cutoff:
            recent_entities.extend(entities)
        if baseline_cutoff <= node_time < recent_cutoff:
            baseline_entities.extend(entities)

    # Calculate rates
    recent_counts = Counter(recent_entities)
    baseline_counts = Counter(baseline_entities)

    # Find emerging (increased mentions)
    emerging = []
    for entity, recent_count in recent_counts.items():
        baseline_count = baseline_counts.get(entity, 0)

        # Calculate growth rate
        if baseline_count == 0:
            growth_rate = float("inf") if recent_count > 1 else 0
        else:
            growth_rate = (recent_count - baseline_count) / baseline_count

        if growth_rate > 0.5:  # 50% increase
            emerging.append((entity, growth_rate))

    # Sort by growth rate
    emerging.sort(key=lambda x: x[1], reverse=True)
    return emerging[:10]


# Example usage
if __name__ == "__main__":
    # Analyze last 7 days
    trending = analyze_trending_topics(Path("./graphstore"), time_window_days=7)
    print(f"Analyzed {trending['conversations_analyzed']} conversations")
    print(f"Top entity: {trending['top_entity']}")
    print(f"Top topic: {trending['top_topic']}")

    # Find emerging technologies
    emerging = identify_emerging_technologies(Path("./graphstore"))
    print(f"\nEmerging technologies: {emerging[:5]}")

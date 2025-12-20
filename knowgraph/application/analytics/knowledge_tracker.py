"""Knowledge evolution tracking.

Tracks how knowledge evolves over time:
- Timeline of conversations about topics
- Knowledge accumulation patterns
- Learning trends
"""

from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from knowgraph.infrastructure.storage.filesystem import list_all_nodes, read_node_json


def get_knowledge_timeline(
    topic: str,
    graph_store_path: Path,
    time_window_days: int = 30,
) -> dict:
    """Get timeline of knowledge about a topic.

    Args:
    ----
        topic: Topic to track
        graph_store_path: Path to graph storage
        time_window_days: Days to look back

    Returns:
    -------
        Timeline dictionary

    """
    # Load conversations
    node_ids = list_all_nodes(graph_store_path)
    conversations = []

    for node_id in node_ids:
        node = read_node_json(node_id, graph_store_path)
        if not node or not node.metadata:
            continue

        if node.metadata.get("type") in ["conversation", "tagged_snippet"]:
            # Check if topic is mentioned
            if topic.lower() in node.content.lower():
                conversations.append(node)

    # Group by date
    timeline = defaultdict(list)
    cutoff = datetime.now() - timedelta(days=time_window_days)

    for conv in conversations:
        # Get timestamp
        if hasattr(conv, "created_at") and conv.created_at:
            conv_time = datetime.fromtimestamp(conv.created_at)
        elif conv.metadata and "timestamp" in conv.metadata:
            try:
                conv_time = datetime.fromisoformat(conv.metadata["timestamp"])
            except (ValueError, TypeError):
                # Skip conversations with invalid timestamps
                continue
        else:
            continue

        if conv_time < cutoff:
            continue

        # Group by day
        date_key = conv_time.strftime("%Y-%m-%d")
        timeline[date_key].append(
            {
                "id": conv.id,
                "timestamp": conv_time.isoformat(),
                "content_preview": conv.content[:100],
            }
        )

    return {
        "topic": topic,
        "time_window_days": time_window_days,
        "timeline": dict(timeline),
        "total_mentions": sum(len(items) for items in timeline.values()),
        "days_with_activity": len(timeline),
    }


def analyze_knowledge_accumulation(
    graph_store_path: Path,
    time_buckets: int = 7,
) -> dict:
    """Analyze knowledge accumulation patterns.

    Args:
    ----
        graph_store_path: Path to graph storage
        time_buckets: Number of time buckets to divide into

    Returns:
    -------
        Accumulation analysis

    """
    # Load all conversations/bookmarks
    node_ids = list_all_nodes(graph_store_path)
    knowledge_nodes = []

    for node_id in node_ids:
        node = read_node_json(node_id, graph_store_path)
        if not node or not node.metadata:
            continue

        if node.metadata.get("type") in ["conversation", "tagged_snippet"]:
            knowledge_nodes.append(node)

    if not knowledge_nodes:
        return {"error": "No knowledge nodes found"}

    # Get time range
    timestamps = []
    for node in knowledge_nodes:
        if hasattr(node, "created_at") and node.created_at:
            timestamps.append(node.created_at)
        elif node.metadata and "timestamp" in node.metadata:
            try:
                ts = datetime.fromisoformat(node.metadata["timestamp"]).timestamp()
                timestamps.append(ts)
            except (ValueError, TypeError):
                # Skip nodes with invalid timestamps
                continue

    if not timestamps:
        return {"error": "No timestamps found"}

    min_time = min(timestamps)
    max_time = max(timestamps)
    bucket_size = (max_time - min_time) / time_buckets

    # Count nodes per bucket
    buckets = defaultdict(int)
    for ts in timestamps:
        bucket_idx = int((ts - min_time) / bucket_size) if bucket_size > 0 else 0
        bucket_idx = min(bucket_idx, time_buckets - 1)
        buckets[bucket_idx] += 1

    # Format results
    bucket_data = []
    for i in range(time_buckets):
        start_time = datetime.fromtimestamp(min_time + i * bucket_size)
        count = buckets.get(i, 0)
        bucket_data.append(
            {
                "bucket": i,
                "start_time": start_time.isoformat(),
                "count": count,
            }
        )

    return {
        "total_knowledge_nodes": len(knowledge_nodes),
        "time_range": {
            "start": datetime.fromtimestamp(min_time).isoformat(),
            "end": datetime.fromtimestamp(max_time).isoformat(),
        },
        "buckets": bucket_data,
        "avg_per_bucket": len(timestamps) / time_buckets,
    }


# Example usage
if __name__ == "__main__":
    # Track FastAPI knowledge over last 30 days
    timeline = get_knowledge_timeline("FastAPI", Path("./graphstore"), time_window_days=30)
    print(
        f"FastAPI mentions: {timeline['total_mentions']} across {timeline['days_with_activity']} days"
    )

    # Analyze accumulation
    accumulation = analyze_knowledge_accumulation(Path("./graphstore"))
    print(f"Total knowledge nodes: {accumulation.get('total_knowledge_nodes', 0)}")

"""Multiprocessing support for centrality calculation.

Uses process pool to bypass GIL for CPU-bound centrality calculations.
Optimized to minimize serialization overhead.
"""

import asyncio
import atexit
from concurrent.futures import ProcessPoolExecutor
from uuid import UUID

import networkx as nx

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node

# Global process pool (persistent, reused across queries)
_process_pool: ProcessPoolExecutor | None = None
_pool_size = 2  # Number of worker processes


def get_process_pool() -> ProcessPoolExecutor:
    """Get or create global process pool."""
    global _process_pool
    if _process_pool is None:
        _process_pool = ProcessPoolExecutor(max_workers=_pool_size)
        # Register cleanup on exit to prevent resource leaks
        atexit.register(shutdown_process_pool)
    return _process_pool


def shutdown_process_pool() -> None:
    """Shutdown process pool gracefully."""
    global _process_pool
    if _process_pool is not None:
        _process_pool.shutdown(wait=True)
        _process_pool = None


def _compute_centrality_worker(
    node_ids: list[UUID],
    edge_data: list[tuple[UUID, UUID, str, float]],
) -> dict[UUID, dict[str, float]]:
    """Worker function for multiprocessing (minimal serialization).

    This runs in a separate process. Only serializes minimal data:
    - Node IDs (UUIDs)
    - Edge tuples (source, target, type, score)

    Avoids serializing full Node/Edge objects.
    """
    # Reconstruct graph from minimal data
    graph = nx.Graph()

    # Add nodes
    for node_id in node_ids:
        graph.add_node(node_id)

    # Add edges
    for source, target, edge_type, score in edge_data:
        graph.add_edge(source, target, weight=score, edge_type=edge_type)

    if not graph.nodes() or not graph.edges():
        return {node_id: _default_centrality() for node_id in node_ids}

    # Check connectivity
    if not nx.is_connected(graph):
        return _compute_disconnected_centrality_minimal(graph, node_ids)

    # Use approximate for large graphs
    use_approximate = len(node_ids) > 100

    # Betweenness centrality
    try:
        if use_approximate:
            k = max(10, int(len(node_ids) ** 0.5))
            betweenness = nx.betweenness_centrality(graph, k=k, normalized=True)
        else:
            betweenness = nx.betweenness_centrality(graph, normalized=True)
    except Exception:
        betweenness = dict.fromkeys(node_ids, 0.0)

    # Degree centrality
    degree = nx.degree_centrality(graph)

    # Closeness centrality
    try:
        closeness = nx.closeness_centrality(graph)
    except Exception:
        closeness = dict.fromkeys(node_ids, 0.0)

    # Eigenvector centrality
    try:
        if use_approximate:
            eigenvector = nx.eigenvector_centrality(graph, max_iter=50)
        else:
            eigenvector = nx.eigenvector_centrality(graph, max_iter=100)
    except Exception:
        eigenvector = dict.fromkeys(node_ids, 0.0)

    # Combine metrics
    from knowgraph.config import (
        CENTRALITY_BETWEENNESS_WEIGHT,
        CENTRALITY_CLOSENESS_WEIGHT,
        CENTRALITY_DEGREE_WEIGHT,
        CENTRALITY_EIGENVECTOR_WEIGHT,
    )

    metrics = {}
    for node_id in node_ids:
        b = betweenness.get(node_id, 0.0)
        d = degree.get(node_id, 0.0)
        c = closeness.get(node_id, 0.0)
        e = eigenvector.get(node_id, 0.0)

        composite = (
            CENTRALITY_BETWEENNESS_WEIGHT * b
            + CENTRALITY_DEGREE_WEIGHT * d
            + CENTRALITY_CLOSENESS_WEIGHT * c
            + CENTRALITY_EIGENVECTOR_WEIGHT * e
        )

        metrics[node_id] = {
            "betweenness": b,
            "degree": d,
            "closeness": c,
            "eigenvector": e,
            "composite": composite,
        }

    return metrics


def _default_centrality() -> dict[str, float]:
    """Default centrality values."""
    return {
        "betweenness": 0.0,
        "degree": 0.0,
        "closeness": 0.0,
        "eigenvector": 0.0,
        "composite": 0.0,
    }


def _compute_disconnected_centrality_minimal(
    graph: nx.Graph,
    node_ids: list[UUID],
) -> dict[UUID, dict[str, float]]:
    """Compute centrality for disconnected graph (minimal version)."""
    from knowgraph.config import (
        CENTRALITY_BETWEENNESS_WEIGHT,
        CENTRALITY_CLOSENESS_WEIGHT,
        CENTRALITY_DEGREE_WEIGHT,
        CENTRALITY_EIGENVECTOR_WEIGHT,
    )

    metrics = {}

    for component in nx.connected_components(graph):
        subgraph = graph.subgraph(component)

        try:
            betweenness = nx.betweenness_centrality(subgraph, normalized=True)
        except Exception:
            betweenness = dict.fromkeys(component, 0.0)

        degree = nx.degree_centrality(subgraph)

        try:
            closeness = nx.closeness_centrality(subgraph)
        except Exception:
            closeness = dict.fromkeys(component, 0.0)

        try:
            eigenvector = nx.eigenvector_centrality(subgraph, max_iter=100)
        except Exception:
            eigenvector = dict.fromkeys(component, 0.0)

        for node_id in component:
            b = betweenness.get(node_id, 0.0)
            d = degree.get(node_id, 0.0)
            c = closeness.get(node_id, 0.0)
            e = eigenvector.get(node_id, 0.0)

            composite = (
                CENTRALITY_BETWEENNESS_WEIGHT * b
                + CENTRALITY_DEGREE_WEIGHT * d
                + CENTRALITY_CLOSENESS_WEIGHT * c
                + CENTRALITY_EIGENVECTOR_WEIGHT * e
            )

            metrics[node_id] = {
                "betweenness": b,
                "degree": d,
                "closeness": c,
                "eigenvector": e,
                "composite": composite,
            }

    return metrics


async def compute_centrality_async(
    nodes: list[Node],
    edges: list[Edge],
    use_multiprocessing: bool = True,
) -> dict[UUID, dict[str, float]]:
    """Compute centrality metrics asynchronously with optional multiprocessing.

    Optimized to minimize serialization overhead:
    - Only serializes node IDs and edge tuples (not full objects)
    - Uses persistent process pool (no spawn overhead)
    - Smart threshold (only for large graphs)

    Args:
        nodes: List of nodes in active subgraph
        edges: List of edges in active subgraph
        use_multiprocessing: Use process pool for CPU-bound work (default: True)

    Returns:
        Dictionary mapping node UUID to centrality metrics

    Example:
        >>> metrics = await compute_centrality_async(nodes, edges)
    """
    # Smart threshold: only use multiprocessing for large graphs
    # where computation time > serialization overhead
    if not use_multiprocessing or len(nodes) < 300:
        # For small/medium graphs, use single-process (faster due to overhead)
        from knowgraph.domain.algorithms.centrality import _compute_centrality_impl

        return _compute_centrality_impl(nodes, edges)

    # Prepare minimal data for serialization
    node_ids = [node.id for node in nodes]
    edge_data = [(edge.source, edge.target, edge.type, edge.score) for edge in edges]

    # Use process pool for large graphs
    loop = asyncio.get_event_loop()
    pool = get_process_pool()

    # Run in executor (process pool) with minimal data
    result = await loop.run_in_executor(
        pool,
        _compute_centrality_worker,
        node_ids,
        edge_data,
    )

    return result


# Example usage
if __name__ == "__main__":
    import time
    from uuid import uuid4

    async def benchmark() -> None:
        """Benchmark multiprocessing vs single-process."""
        print("\n🔥 Multiprocessing Benchmark\n")
        print("=" * 60)

        # Create large graph
        nodes = []
        edges = []

        for i in range(200):
            node = Node(
                id=uuid4(),
                hash="a" * 40,
                title=f"Node {i}",
                content=f"Content {i}",
                path=f"test/node{i}.py",
                type="text",
                token_count=10,
                created_at=0,
            )
            nodes.append(node)

        for i in range(200):
            edges.append(
                Edge(
                    source=nodes[i].id,
                    target=nodes[(i + 1) % 200].id,
                    type="semantic",
                    score=0.8,
                    created_at=0,
                    metadata={},
                )
            )

        print(f"Graph: {len(nodes)} nodes, {len(edges)} edges\n")

        # Single-process
        print("📊 Single-process")
        start = time.time()
        await compute_centrality_async(nodes, edges, use_multiprocessing=False)
        single_time = time.time() - start
        print(f"  Time: {single_time:.3f}s")

        # Multi-process
        print("\n📊 Multi-process")
        start = time.time()
        await compute_centrality_async(nodes, edges, use_multiprocessing=True)
        multi_time = time.time() - start
        print(f"  Time: {multi_time:.3f}s")

        # Compare
        speedup = single_time / multi_time if multi_time > 0 else 1.0
        print(f"\n🚀 Speedup: {speedup:.2f}x")

        if speedup > 1.2:
            print("  ✅ Multiprocessing faster!")
        else:
            print("  ⚠️  Multiprocessing overhead (small graph or overhead)")

        # Cleanup
        shutdown_process_pool()

        print("\n" + "=" * 60)

    asyncio.run(benchmark())

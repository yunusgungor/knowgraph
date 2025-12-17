"""Test approximate centrality performance."""

import asyncio
import time
from pathlib import Path
from uuid import uuid4

from knowgraph.application.querying.query_engine import QueryEngine
from knowgraph.domain.algorithms.centrality import compute_centrality_metrics
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


def create_large_graph(n_nodes=150):
    """Create a large graph for testing."""
    nodes = []
    edges = []

    for i in range(n_nodes):
        node = Node(
            id=uuid4(),
            hash="a" * 40,  # Valid 40-char hash
            title=f"Node {i}",
            content=f"Content {i}",
            path=f"test/node{i}.py",
            type="text",
            token_count=10,
            created_at=0,
        )
        nodes.append(node)

    # Create edges (ring + some random connections)
    for i in range(n_nodes):
        # Ring connection
        edges.append(
            Edge(
                source=nodes[i].id,
                target=nodes[(i + 1) % n_nodes].id,
                type="semantic",
                score=0.8,
                created_at=0,
                metadata={},
            )
        )

        # Random connections
        if i % 5 == 0 and i + 10 < n_nodes:
            edges.append(
                Edge(
                    source=nodes[i].id,
                    target=nodes[i + 10].id,
                    type="semantic",
                    score=0.6,
                    created_at=0,
                    metadata={},
                )
            )

    return nodes, edges


def test_approximate_vs_exact():
    """Test approximate centrality vs exact."""
    print("\n🔬 Approximate Centrality Test\n")
    print("=" * 60)

    # Small graph (exact)
    print("\n📊 Small Graph (50 nodes) - Exact Algorithm")
    small_nodes, small_edges = create_large_graph(50)

    start = time.time()
    small_result = compute_centrality_metrics(small_nodes, small_edges)
    small_time = time.time() - start

    print(f"  Time: {small_time:.3f}s")
    print(f"  Nodes: {len(small_nodes)}")
    print(f"  Algorithm: Exact")

    # Large graph (approximate)
    print("\n📊 Large Graph (150 nodes) - Approximate Algorithm")
    large_nodes, large_edges = create_large_graph(150)

    start = time.time()
    large_result = compute_centrality_metrics(large_nodes, large_edges)
    large_time = time.time() - start

    print(f"  Time: {large_time:.3f}s")
    print(f"  Nodes: {len(large_nodes)}")
    print(f"  Algorithm: Approximate (k=12 samples)")

    # Compare
    print(f"\n🎯 Performance Comparison")
    time_per_node_small = small_time / len(small_nodes)
    time_per_node_large = large_time / len(large_nodes)

    print(f"  Small graph: {time_per_node_small*1000:.2f}ms per node")
    print(f"  Large graph: {time_per_node_large*1000:.2f}ms per node")

    if time_per_node_large < time_per_node_small:
        improvement = (time_per_node_small / time_per_node_large - 1) * 100
        print(f"  ✅ Approximate is {improvement:.1f}% faster per node!")
    else:
        print(f"  ⚠️  Approximate not faster (overhead for small graphs)")

    # Projected time for exact on large graph
    projected_exact_time = time_per_node_small * len(large_nodes)
    speedup = projected_exact_time / large_time

    print(f"\n📈 Projected Speedup for Large Graph")
    print(f"  Projected exact time: {projected_exact_time:.3f}s")
    print(f"  Actual approx time: {large_time:.3f}s")
    print(f"  Speedup: {speedup:.2f}x")

    print("\n" + "=" * 60)


async def test_with_real_queries():
    """Test with real query engine."""
    engine = QueryEngine(Path("/Users/yunusgungor/knowrag/graphstore"))

    print("\n🔍 Real Query Test\n")
    print("=" * 60)

    queries = [
        "large codebase",
        "complex system",
        "architecture",
    ]

    for query in queries:
        print(f"\n📊 Query: {query}")

        start = time.time()
        result = await engine.query_async(query, top_k=20, max_hops=4)
        query_time = time.time() - start

        print(f"  Time: {query_time:.3f}s")
        print(
            f"  Centrality: {result.centrality_time:.3f}s ({result.centrality_time/query_time*100:.1f}%)"
        )
        print(f"  Nodes: {result.active_subgraph_size}")

        if result.active_subgraph_size > 100:
            print(f"  Algorithm: Approximate (large graph)")
        else:
            print(f"  Algorithm: Exact (small graph)")

    print("\n" + "=" * 60)


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Approximate Centrality Performance Test")
    print("=" * 60)

    test_approximate_vs_exact()
    await test_with_real_queries()

    print("\n✅ Test Complete!\n")


if __name__ == "__main__":
    asyncio.run(main())

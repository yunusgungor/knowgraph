"""Test optimized multiprocessing with various graph sizes."""

import asyncio
import time
from uuid import uuid4

from knowgraph.application.querying.centrality_mp import (
    compute_centrality_async,
    shutdown_process_pool,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


def create_graph(n_nodes):
    """Create a graph for testing."""
    nodes = []
    edges = []

    for i in range(n_nodes):
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

    for i in range(n_nodes):
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


async def benchmark_size(n_nodes):
    """Benchmark a specific graph size."""
    print(f"\n📊 Graph Size: {n_nodes} nodes")
    print("-" * 60)

    nodes, edges = create_graph(n_nodes)

    # Single-process
    start = time.time()
    result1 = await compute_centrality_async(nodes, edges, use_multiprocessing=False)
    single_time = time.time() - start

    # Multi-process
    start = time.time()
    result2 = await compute_centrality_async(nodes, edges, use_multiprocessing=True)
    multi_time = time.time() - start

    speedup = single_time / multi_time if multi_time > 0 else 1.0

    print(f"  Single-process: {single_time:.3f}s")
    print(f"  Multi-process:  {multi_time:.3f}s")
    print(f"  Speedup:        {speedup:.2f}x", end="")

    if speedup > 1.2:
        print(" ✅")
    elif speedup > 0.9:
        print(" ⚠️")
    else:
        print(" ❌")

    return n_nodes, single_time, multi_time, speedup


async def main():
    """Run benchmarks for various graph sizes."""
    print("\n" + "=" * 60)
    print("Optimized Multiprocessing Benchmark")
    print("=" * 60)

    sizes = [50, 100, 200, 300, 400, 500]
    results = []

    for size in sizes:
        result = await benchmark_size(size)
        results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"\n{'Size':<10} {'Single':<12} {'Multi':<12} {'Speedup':<10} {'Status'}")
    print("-" * 60)

    for size, single, multi, speedup in results:
        status = "✅" if speedup > 1.2 else "⚠️" if speedup > 0.9 else "❌"
        print(f"{size:<10} {single:<12.3f} {multi:<12.3f} {speedup:<10.2f} {status}")

    # Find optimal threshold
    print("\n🎯 Optimal Threshold Analysis:")
    for size, single, multi, speedup in results:
        if speedup > 1.1:
            print(f"  Multiprocessing beneficial at {size}+ nodes ({speedup:.2f}x)")
            break
    else:
        print(f"  Multiprocessing not beneficial for tested sizes")

    # Cleanup
    shutdown_process_pool()

    print("\n" + "=" * 60)
    print("✅ Benchmark Complete!\n")


if __name__ == "__main__":
    asyncio.run(main())

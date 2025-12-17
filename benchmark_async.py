"""Performance optimization script for KnowGraph async implementation."""

import asyncio
import time
from pathlib import Path

from knowgraph.application.querying.query_engine import QueryEngine


async def benchmark_queries():
    """Benchmark query performance."""
    engine = QueryEngine(Path("/Users/yunusgungor/knowrag/graphstore"))

    queries = [
        "QueryEngine nedir?",
        "async/await avantajları",
        "batch query performansı",
        "concurrency control",
        "timeout mekanizması",
    ]

    print("🔥 Performance Benchmark\n")
    print("=" * 60)

    # Test 1: Sequential queries
    print("\n📊 Test 1: Sequential Queries")
    start = time.time()
    for i, query in enumerate(queries, 1):
        q_start = time.time()
        result = await engine.query_async(query, top_k=10, max_hops=3)
        q_time = time.time() - q_start
        print(f"  Query {i}: {q_time:.2f}s ({len(result.seed_nodes)} nodes)")
    sequential_time = time.time() - start
    print(f"\n  Total Sequential Time: {sequential_time:.2f}s")

    # Test 2: Batch query
    print("\n📊 Test 2: Batch Query (Concurrent)")
    start = time.time()
    results = await engine.batch_query_async(queries=queries, top_k=10, max_hops=3, batch_size=5)
    batch_time = time.time() - start
    print(f"  Total Batch Time: {batch_time:.2f}s")
    print(f"  Queries Processed: {len(results)}")

    # Calculate speedup
    speedup = sequential_time / batch_time if batch_time > 0 else 0
    print(f"\n🚀 Speedup: {speedup:.2f}x")

    if speedup < 2.0:
        print("⚠️  WARNING: Batch query not showing expected speedup!")
        print("   Expected: 3-5x, Got: {:.2f}x".format(speedup))
    else:
        print("✅ Batch query performing well!")

    print("\n" + "=" * 60)


async def test_impact_analysis():
    """Test impact analysis."""
    engine = QueryEngine(Path("/Users/yunusgungor/knowrag/graphstore"))

    print("\n🔍 Impact Analysis Test\n")
    print("=" * 60)

    try:
        result = await engine.analyze_impact_async("QueryEngine", max_hops=3)
        print(f"✅ Impact Analysis Successful!")
        print(f"   Nodes: {len(result.seed_nodes)}")
        print(f"   Answer length: {len(result.answer)} chars")
    except Exception as e:
        print(f"❌ Impact Analysis Failed: {e}")

    print("=" * 60)


async def main():
    """Run all benchmarks."""
    print("\n" + "=" * 60)
    print("KnowGraph Async Performance Benchmark")
    print("=" * 60)

    await benchmark_queries()
    await test_impact_analysis()

    print("\n✅ Benchmark Complete!\n")


if __name__ == "__main__":
    asyncio.run(main())

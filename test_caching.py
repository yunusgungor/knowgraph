"""Test centrality caching performance improvement."""

import asyncio
import time
from pathlib import Path

from knowgraph.application.querying.query_engine import QueryEngine


async def test_caching_improvement():
    """Test caching performance improvement."""
    engine = QueryEngine(Path("/Users/yunusgungor/knowrag/graphstore"))

    print("\n🔥 Centrality Caching Performance Test\n")
    print("=" * 60)

    # Same query repeated
    query = "QueryEngine nedir?"

    # First run (cold cache)
    print("📊 First Run (Cold Cache)")
    start = time.time()
    result1 = await engine.query_async(query, top_k=10, max_hops=3)
    time1 = time.time() - start
    print(f"  Time: {time1:.3f}s")
    print(
        f"  Centrality: {result1.centrality_time:.3f}s ({result1.centrality_time/time1*100:.1f}%)"
    )

    # Second run (warm cache - same subgraph)
    print("\n📊 Second Run (Warm Cache - Same Query)")
    start = time.time()
    result2 = await engine.query_async(query, top_k=10, max_hops=3)
    time2 = time.time() - start
    print(f"  Time: {time2:.3f}s")
    print(
        f"  Centrality: {result2.centrality_time:.3f}s ({result2.centrality_time/time2*100:.1f}%)"
    )

    # Calculate improvement
    speedup = time1 / time2
    centrality_speedup = (
        result1.centrality_time / result2.centrality_time if result2.centrality_time > 0 else 1.0
    )

    print(f"\n🚀 Performance Improvement")
    print(f"  Overall Speedup:     {speedup:.2f}x")
    print(f"  Centrality Speedup:  {centrality_speedup:.2f}x")

    if speedup > 1.5:
        print(f"  ✅ Caching working! {(speedup-1)*100:.0f}% faster")
    else:
        print(f"  ⚠️  Caching not effective ({speedup:.2f}x)")

    # Third run (different query, might share subgraph)
    print("\n📊 Third Run (Different Query)")
    query3 = "async/await avantajları"
    start = time.time()
    result3 = await engine.query_async(query3, top_k=10, max_hops=3)
    time3 = time.time() - start
    print(f"  Time: {time3:.3f}s")
    print(f"  Centrality: {result3.centrality_time:.3f}s")

    # Batch test
    print("\n📊 Batch Test (5 queries)")
    queries = ["QueryEngine", "async/await", "batch query", "concurrency", "timeout"]

    start = time.time()
    results = await engine.batch_query_async(queries, top_k=10, max_hops=3, batch_size=5)
    batch_time = time.time() - start

    print(f"  Total Time: {batch_time:.3f}s")
    print(f"  Avg per Query: {batch_time/len(queries):.3f}s")
    print(f"  Successful: {sum(1 for r in results if r.answer)}/{len(results)}")

    print("\n" + "=" * 60)


async def main():
    """Run caching test."""
    print("\n" + "=" * 60)
    print("Centrality Caching Performance Test")
    print("=" * 60)

    await test_caching_improvement()

    print("\n✅ Test Complete!\n")


if __name__ == "__main__":
    asyncio.run(main())

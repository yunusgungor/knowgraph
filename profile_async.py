"""Detailed profiling for async query performance."""

import asyncio
import cProfile
import pstats
import time
from io import StringIO
from pathlib import Path

from knowgraph.application.querying.query_engine import QueryEngine


async def profile_query(engine: QueryEngine, query: str) -> None:
    """Profile a single query to find bottlenecks."""

    print("\n🔍 Profiling Single Query\n")
    print("=" * 60)

    # Profile the query
    profiler = cProfile.Profile()
    profiler.enable()

    result = await engine.query_async("QueryEngine nedir?", top_k=10, max_hops=3)

    profiler.disable()

    # Print stats
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
    ps.print_stats(30)  # Top 30 functions

    print(s.getvalue())
    print(f"\nQuery completed: {len(result.seed_nodes)} nodes in {result.execution_time:.2f}s")
    print("=" * 60)


async def analyze_bottlenecks() -> None:
    """Analyze where time is spent in queries."""
    engine = QueryEngine(Path("/Users/yunusgungor/knowrag/graphstore"))

    print("\n⏱️  Detailed Timing Analysis\n")
    print("=" * 60)

    query = "async/await avantajları"  # noqa: RUF001

    # Time each component
    start = time.time()
    result = await engine.query_async(query, top_k=10, max_hops=3)
    total_time = time.time() - start

    print(f"Query: {query}")
    print("\nTiming Breakdown:")
    print(
        f"  Sparse Search:    {result.sparse_search_time:.3f}s ({result.sparse_search_time/total_time*100:.1f}%)"
    )
    print(
        f"  Graph Expansion:  {result.graph_expansion_time:.3f}s ({result.graph_expansion_time/total_time*100:.1f}%)"
    )
    print(
        f"  Centrality:       {result.centrality_time:.3f}s ({result.centrality_time/total_time*100:.1f}%)"
    )

    other_time = total_time - (
        result.sparse_search_time + result.graph_expansion_time + result.centrality_time
    )
    print(f"  Other (context):  {other_time:.3f}s ({other_time/total_time*100:.1f}%)")
    print(f"  TOTAL:            {total_time:.3f}s")

    print(f"\nNodes Retrieved: {len(result.seed_nodes)}")
    print(f"Active Subgraph: {result.active_subgraph_size}")

    print("=" * 60)

    # Identify bottleneck
    components = {
        "Sparse Search": result.sparse_search_time,
        "Graph Expansion": result.graph_expansion_time,
        "Centrality": result.centrality_time,
        "Other": other_time,
    }

    bottleneck = max(components.items(), key=lambda x: x[1])
    print(
        f"\n🎯 Primary Bottleneck: {bottleneck[0]} ({bottleneck[1]:.3f}s, {bottleneck[1]/total_time*100:.1f}%)"
    )

    if bottleneck[0] == "Sparse Search":
        print("   → Sparse index search is sequential (not async)")
        print("   → Consider caching or optimizing sparse embedder")
    elif bottleneck[0] == "Centrality":
        print("   → Centrality calculation is CPU-bound (not async)")
        print("   → NetworkX operations are sequential")
    elif bottleneck[0] == "Other":
        print("   → Context assembly or file I/O is slow")
        print("   → Check node loading performance")


async def test_concurrent_io() -> None:
    """Test if concurrent I/O actually works."""
    engine = QueryEngine(Path("/Users/yunusgungor/knowrag/graphstore"))

    print("\n🔄 Concurrent I/O Test\n")
    print("=" * 60)

    queries = ["test1", "test2", "test3"]

    # Sequential
    start = time.time()
    for q in queries:
        try:
            await engine.query_async(q, top_k=5, max_hops=2)
        except Exception:
            pass
    seq_time = time.time() - start

    # Concurrent
    start = time.time()
    tasks = [
        engine._query_async_impl(
            q,
            top_k=5,
            max_hops=2,
            max_tokens=1000,
            with_explanation=False,
            enable_hierarchical_lifting=True,
            lift_levels=2,
        )
        for q in queries
    ]
    await asyncio.gather(*tasks, return_exceptions=True)
    conc_time = time.time() - start

    print(f"Sequential: {seq_time:.2f}s")
    print(f"Concurrent: {conc_time:.2f}s")
    print(f"Speedup:    {seq_time/conc_time:.2f}x")

    if seq_time / conc_time < 1.5:
        print("\n⚠️  Concurrent execution NOT working properly!")
        print("   Likely causes:")
        print("   - Global locks in sparse index")
        print("   - Sequential file I/O")
        print("   - GIL contention in CPU-bound operations")
    else:
        print("\n✅ Concurrent execution working!")

    print("=" * 60)


async def main() -> None:
    """Run all profiling tests."""
    print("\n" + "=" * 60)
    print("KnowGraph Async Performance Profiling")
    print("=" * 60)

    await analyze_bottlenecks()
    await test_concurrent_io()
    # await profile_single_query()  # Uncomment for detailed profiling

    print("\n✅ Profiling Complete!\n")


if __name__ == "__main__":
    asyncio.run(main())

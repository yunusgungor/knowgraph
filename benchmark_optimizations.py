"""Comprehensive performance benchmark suite for KnowGraph optimizations.

Tests and compares performance before/after optimizations.
"""

import asyncio
import time
from pathlib import Path

from knowgraph.application.querying.query_engine import QueryEngine
from knowgraph.infrastructure.storage.filesystem import (
    clear_node_cache,
    get_cache_stats,
)
from knowgraph.shared.performance import get_global_tracker


async def benchmark_node_cache() -> dict[str, float]:
    """Benchmark node cache performance."""
    print("\n📦 Node Cache Benchmark")
    print("=" * 60)

    engine = QueryEngine(Path("./graphstore"))

    # Cold cache
    clear_node_cache()
    start = time.time()
    result1 = await engine.query_async("QueryEngine", top_k=10, max_hops=3)
    cold_time = time.time() - start

    # Warm cache
    start = time.time()
    result2 = await engine.query_async("QueryEngine", top_k=10, max_hops=3)
    warm_time = time.time() - start

    speedup = cold_time / warm_time if warm_time > 0 else 0
    cache_stats = get_cache_stats()

    print(f"  Cold Cache: {cold_time:.3f}s")
    print(f"  Warm Cache: {warm_time:.3f}s")
    print(f"  Speedup: {speedup:.2f}x")
    print(f"  Cache Size: {cache_stats['size']}/{cache_stats['max_size']}")
    print(f"  Utilization: {cache_stats['utilization']}%")

    return {
        "cold_time": cold_time,
        "warm_time": warm_time,
        "speedup": speedup,
    }


async def benchmark_batch_queries() -> dict[str, float]:
    """Benchmark batch query performance with different batch sizes."""
    print("\n🚀 Batch Query Optimization Benchmark")
    print("=" * 60)

    engine = QueryEngine(Path("./graphstore"))

    queries = [
        "async/await",
        "performance",
        "caching",
        "optimization",
        "batch processing",
        "query engine",
        "centrality",
        "graph traversal",
    ]

    # Test different batch sizes
    batch_sizes = [3, 5, 8]
    results = {}

    for batch_size in batch_sizes:
        start = time.time()
        await engine.batch_query_async(
            queries=queries,
            batch_size=batch_size,
            top_k=10,
            max_hops=3,
        )
        duration = time.time() - start
        results[f"batch_size_{batch_size}"] = duration
        print(f"  Batch Size {batch_size}: {duration:.3f}s")

    # Find optimal
    optimal = min(results.items(), key=lambda x: x[1])
    print(f"\n  ✅ Optimal Batch Size: {optimal[0]} ({optimal[1]:.3f}s)")

    return results


async def benchmark_centrality_cache() -> dict[str, float]:
    """Benchmark centrality cache effectiveness."""
    print("\n🎯 Centrality Cache Benchmark")
    print("=" * 60)

    engine = QueryEngine(Path("./graphstore"))

    # Clear centrality cache
    engine._centrality_cache.clear()

    # First query (cold cache)
    start = time.time()
    result1 = await engine.query_async("centrality algorithms", top_k=15, max_hops=4)
    cold_time = time.time() - start

    # Second query (warm cache, similar subgraph)
    start = time.time()
    result2 = await engine.query_async("centrality metrics", top_k=15, max_hops=4)
    warm_time = time.time() - start

    speedup = cold_time / warm_time if warm_time > 0 else 0
    cache_size = len(engine._centrality_cache)

    print(f"  Cold Cache: {cold_time:.3f}s")
    print(f"  Warm Cache: {warm_time:.3f}s")
    print(f"  Speedup: {speedup:.2f}x")
    print(f"  Cache Entries: {cache_size}/512")

    return {
        "cold_time": cold_time,
        "warm_time": warm_time,
        "speedup": speedup,
        "cache_size": cache_size,
    }


async def benchmark_parameter_tuning() -> dict[str, float]:
    """Benchmark different parameter configurations."""
    print("\n⚙️  Parameter Tuning Benchmark")
    print("=" * 60)

    engine = QueryEngine(Path("./graphstore"))
    query = "query engine optimization"

    configs = [
        {"name": "Conservative", "top_k": 10, "max_hops": 2, "max_tokens": 2000},
        {"name": "Balanced", "top_k": 15, "max_hops": 3, "max_tokens": 3000},
        {"name": "Aggressive", "top_k": 20, "max_hops": 4, "max_tokens": 5000},
    ]

    results = {}

    for config in configs:
        name = config.pop("name")
        start = time.time()
        result = await engine.query_async(query, **config)
        duration = time.time() - start

        results[name] = duration
        print(f"  {name:12s}: {duration:.3f}s (nodes: {len(result.seed_nodes)})")

    return results


async def benchmark_concurrent_load() -> dict[str, float]:
    """Benchmark concurrent query load."""
    print("\n⚡ Concurrent Load Benchmark")
    print("=" * 60)

    engine = QueryEngine(Path("./graphstore"))

    queries = ["query" + str(i) for i in range(10)]

    # Sequential
    start = time.time()
    for q in queries:
        await engine.query_async(q, top_k=5, max_hops=2)
    sequential_time = time.time() - start

    # Concurrent (batch)
    start = time.time()
    await engine.batch_query_async(queries, batch_size=8, top_k=5, max_hops=2)
    concurrent_time = time.time() - start

    speedup = sequential_time / concurrent_time if concurrent_time > 0 else 0

    print(f"  Sequential: {sequential_time:.3f}s")
    print(f"  Concurrent: {concurrent_time:.3f}s")
    print(f"  Speedup: {speedup:.2f}x")

    return {
        "sequential": sequential_time,
        "concurrent": concurrent_time,
        "speedup": speedup,
    }


async def run_full_benchmark() -> None:
    """Run all benchmarks."""
    print("\n" + "=" * 60)
    print("🔬 KnowGraph Performance Optimization Benchmark")
    print("=" * 60)

    results = {}

    # Run all benchmarks
    results["node_cache"] = await benchmark_node_cache()
    results["batch_queries"] = await benchmark_batch_queries()
    results["centrality_cache"] = await benchmark_centrality_cache()
    results["parameter_tuning"] = await benchmark_parameter_tuning()
    results["concurrent_load"] = await benchmark_concurrent_load()

    # Print global tracker report
    tracker = get_global_tracker()
    tracker.print_report()

    # Summary
    print("\n" + "=" * 60)
    print("📊 OPTIMIZATION SUMMARY")
    print("=" * 60)
    print(f"  Node Cache Speedup:      {results['node_cache']['speedup']:.2f}x")
    print(f"  Centrality Cache Speedup: {results['centrality_cache']['speedup']:.2f}x")
    print(f"  Concurrent Load Speedup:  {results['concurrent_load']['speedup']:.2f}x")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_full_benchmark())

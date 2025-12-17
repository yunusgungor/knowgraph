"""Cache pre-warming utilities for KnowGraph.

Warms up the centrality cache at startup with common queries
to improve cold start performance.
"""

import asyncio
from pathlib import Path

from knowgraph.application.querying.query_engine import QueryEngine

# Common queries to pre-warm cache
DEFAULT_WARMUP_QUERIES = [
    "authentication",
    "database",
    "API",
    "error handling",
    "logging",
    "configuration",
    "testing",
    "deployment",
]


async def warm_cache(
    engine: QueryEngine,
    queries: list[str] | None = None,
    top_k: int = 10,
    max_hops: int = 3,
    verbose: bool = True,
) -> dict[str, float]:
    """Warm up centrality cache with common queries.

    Args:
        engine: QueryEngine instance
        queries: List of queries to warm (default: DEFAULT_WARMUP_QUERIES)
        top_k: Number of seed nodes per query
        max_hops: Graph traversal depth
        verbose: Print progress

    Returns:
        Dict mapping query to execution time

    Example:
        >>> engine = QueryEngine(Path("./graphstore"))
        >>> times = await warm_cache(engine)
        >>> print(f"Warmed {len(times)} queries")
    """
    if queries is None:
        queries = DEFAULT_WARMUP_QUERIES

    if verbose:
        print(f"🔥 Warming cache with {len(queries)} queries...")

    times = {}

    for i, query in enumerate(queries, 1):
        try:
            result = await engine.query_async(
                query,
                top_k=top_k,
                max_hops=max_hops,
                timeout=30.0,
            )
            times[query] = result.execution_time

            if verbose:
                print(f"  [{i}/{len(queries)}] {query}: {result.execution_time:.2f}s")

        except Exception as e:
            if verbose:
                print(f"  [{i}/{len(queries)}] {query}: FAILED ({e})")
            times[query] = -1.0

    if verbose:
        successful = sum(1 for t in times.values() if t > 0)
        total_time = sum(t for t in times.values() if t > 0)
        print(f"\n✅ Cache warmed: {successful}/{len(queries)} queries in {total_time:.2f}s")

    return times


async def warm_cache_background(
    engine: QueryEngine,
    queries: list[str] | None = None,
    delay: float = 1.0,
) -> asyncio.Task[None]:
    """Warm cache in background (non-blocking).

    Args:
        engine: QueryEngine instance
        queries: List of queries to warm
        delay: Delay before starting (seconds)

    Returns:
        Async task (can be awaited or cancelled)

    Example:
        >>> engine = QueryEngine(Path("./graphstore"))
        >>> task = await warm_cache_background(engine)
        >>> # Do other work...
        >>> await task  # Wait for completion
    """

    async def _warm() -> None:
        await asyncio.sleep(delay)
        await warm_cache(engine, queries, verbose=False)

    return asyncio.create_task(_warm())


def get_cache_stats(engine: QueryEngine) -> dict[str, int]:
    """Get centrality cache statistics.

    Args:
        engine: QueryEngine instance

    Returns:
        Dict with cache stats

    Example:
        >>> stats = get_cache_stats(engine)
        >>> print(f"Cache size: {stats['size']}")
    """
    from knowgraph.domain.algorithms.centrality import _cache_max_size, _centrality_cache

    return {
        "size": len(_centrality_cache),
        "max_size": _cache_max_size,
        "utilization": len(_centrality_cache) / _cache_max_size * 100,
    }


def clear_cache() -> None:
    """Clear centrality cache.

    Useful for:
    - Freeing memory
    - Graph updates
    - Testing

    Example:
        >>> clear_cache()
        >>> print("Cache cleared")
    """
    from knowgraph.domain.algorithms.centrality import _centrality_cache

    _centrality_cache.clear()


# Example usage
if __name__ == "__main__":

    async def main() -> None:
        engine = QueryEngine(Path("/Users/yunusgungor/knowrag/graphstore"))

        # Warm cache
        times = await warm_cache(engine)

        # Check stats
        stats = get_cache_stats(engine)
        print("\nCache Stats:")
        print(f"  Size: {stats['size']}/{stats['max_size']}")
        print(f"  Utilization: {stats['utilization']:.1f}%")

    asyncio.run(main())

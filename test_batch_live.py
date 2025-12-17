"""Test batch query with updated parameters."""

import asyncio
from pathlib import Path

from knowgraph.application.querying.query_engine import QueryEngine


async def test_batch():
    """Test batch query."""
    engine = QueryEngine(Path("/Users/yunusgungor/knowrag/graphstore"))

    queries = ["QueryEngine nedir?", "async/await avantajları", "batch query performansı"]

    print("🚀 Batch query başlatılıyor...")
    results = await engine.batch_query_async(
        queries=queries,
        top_k=10,
        max_hops=3,
    )

    print(f"\n✅ {len(results)} sorgu tamamlandı!\n")

    for i, (query, result) in enumerate(zip(queries, results), 1):
        print(f"{'='*60}")
        print(f"Query {i}: {query}")
        print(f"{'='*60}")
        print(f"Nodes: {len(result.seed_nodes)}")
        print(f"Time: {result.execution_time:.3f}s")
        print(f"Answer: {result.answer[:200]}...")
        print()


if __name__ == "__main__":
    asyncio.run(test_batch())

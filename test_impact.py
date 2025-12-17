"""Test impact analysis with better error reporting."""

import asyncio
from pathlib import Path

from knowgraph.application.querying.query_engine import QueryEngine


async def test_impact_analysis():
    """Test impact analysis with various queries."""
    engine = QueryEngine(Path("/Users/yunusgungor/knowrag/graphstore"))

    print("\n🔍 Impact Analysis Debug Test\n")
    print("=" * 60)

    test_queries = [
        "QueryEngine",
        "async/await",
        "batch_query_async",
        "centrality",
        "query_engine.py",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n📊 Test {i}: {query}")
        print("-" * 60)

        try:
            result = await engine.analyze_impact_async(query, max_hops=3)

            print(f"✅ Success!")
            print(f"   Seed Nodes: {len(result.seed_nodes)}")
            print(f"   Active Subgraph: {result.active_subgraph_size}")
            print(f"   Execution Time: {result.execution_time:.3f}s")
            print(f"\n   Answer Preview:")
            print(f"   {result.answer[:200]}...")

        except Exception as e:
            print(f"❌ Failed: {type(e).__name__}: {e}")

    print("\n" + "=" * 60)


async def main():
    """Run impact analysis tests."""
    print("\n" + "=" * 60)
    print("Impact Analysis Debug Test")
    print("=" * 60)

    await test_impact_analysis()

    print("\n✅ Test Complete!\n")


if __name__ == "__main__":
    asyncio.run(main())

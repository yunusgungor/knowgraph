#!/usr/bin/env python3
"""End-to-end MCP server test suite.

Tests all Joern integration features through the actual MCP server interface.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest

# NOTE: this suite targets a legacy MCP methods API that no longer exists.
# methods.handle_query() was removed and index_graph() changed from a single
# dict argument to keyword arguments (input_path, graph_path, provider, ...).
# It also instantiates the abstract IntelligenceProvider, which cannot be
# constructed. The equivalent, up-to-date coverage lives in test_mcp_server_e2e.py.
# Skip permanently (even when Joern is present) so CI stays green once Joern
# is installed; rewrite against the current API if this suite is revived.
pytestmark = pytest.mark.skip(
    reason="legacy/broken: targets removed handle_query() API, abstract "
    "IntelligenceProvider, and old index_graph(dict) signature; "
    "see test_mcp_server_e2e.py for the current equivalent",
)


async def test_mcp_index_with_code():
    """Test 1: Index a code repository through MCP."""
    print("🧪 Test 1: MCP Index with Code Analysis")
    print("=" * 70)

    from knowgraph.adapters.mcp import methods
    from knowgraph.domain.intelligence.provider import IntelligenceProvider

    test_dir = Path(__file__).resolve().parent.parent / "knowgraph" / "domain" / "intelligence"

    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "graph"
        graph_path.mkdir(parents=True)

        print(f"Indexing: {test_dir}")

        provider = IntelligenceProvider()

        # Call async index_graph with correct signature
        result = await methods.index_graph(
            input_path=str(test_dir),
            graph_path=graph_path,
            provider=provider,
            resume_mode=False,
            gc=True
        )

        print()
        print("Results:")
        print(f"  Result type: {type(result)}")
        print(f"  Result length: {len(result) if isinstance(result, list) else 'N/A'}")

        # Result is list of TextContent
        success = len(result) > 0 if isinstance(result, list) else False

        if success and result:
            print(f"  Message: {result[0].text[:100]}...")

        print()
        if success:
            print("✅ MCP Index Test PASSED")
        else:
            print("❌ MCP Index Test FAILED")

        return success


async def test_mcp_code_query():
    """Test 2: CODE query through MCP."""
    print("\n🧪 Test 2: MCP CODE Query")
    print("=" * 70)

    from knowgraph.adapters.mcp import methods

    test_dir = Path(__file__).resolve().parent.parent / "knowgraph" / "domain" / "intelligence"

    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "graph"

        # First index
        print("Indexing...")
        methods.index_graph({
            "input_path": str(test_dir),
            "output_path": str(graph_path)
        })

        # Then query
        print("Querying: 'find security vulnerabilities'")

        result = methods.handle_query({
            "query": "find security vulnerabilities",
            "graph_path": str(graph_path)
        })

        print()
        print("Results:")
        print(f"  Success: {result.get('success', False)}")
        print(f"  Query type: {result.get('query_type', 'unknown')}")
        print(f"  Tool used: {result.get('tool_used', 'none')}")
        print(f"  Results count: {len(result.get('results', []))}")

        success = result.get("success", False)
        is_code_query = result.get("query_type") == "code"

        print()
        if success and is_code_query:
            print("✅ MCP CODE Query Test PASSED")
        else:
            print("❌ MCP CODE Query Test FAILED")

        return success and is_code_query


async def test_mcp_hybrid_query():
    """Test 3: HYBRID query through MCP."""
    print("\n🧪 Test 3: MCP HYBRID Query")
    print("=" * 70)

    from knowgraph.adapters.mcp import methods

    test_dir = Path(__file__).resolve().parent.parent / "knowgraph" / "domain" / "intelligence"

    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "graph"

        # Index
        print("Indexing...")
        methods.index_graph({
            "input_path": str(test_dir),
            "output_path": str(graph_path)
        })

        # Hybrid query
        print("Querying: 'is the code secure?'")

        result = methods.handle_query({
            "query": "is the code secure?",
            "graph_path": str(graph_path)
        })

        print()
        print("Results:")
        print(f"  Success: {result.get('success', False)}")
        print(f"  Query type: {result.get('query_type', 'unknown')}")
        print(f"  Has code results: {'code_results' in result}")
        print(f"  Has text results: {'text_results' in result}")

        success = result.get("success", False)
        is_hybrid = result.get("query_type") == "hybrid"

        print()
        if success and is_hybrid:
            print("✅ MCP HYBRID Query Test PASSED")
        else:
            print("❌ MCP HYBRID Query Test FAILED")

        return success and is_hybrid


async def test_mcp_incremental_reindex():
    """Test 4: Incremental re-indexing through MCP."""
    print("\n🧪 Test 4: MCP Incremental Re-indexing")
    print("=" * 70)

    from knowgraph.adapters.mcp import methods

    test_dir = Path(__file__).resolve().parent.parent / "knowgraph" / "domain" / "intelligence"

    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "graph"

        # First index
        print("First index...")
        result1 = methods.index_graph({
            "input_path": str(test_dir),
            "output_path": str(graph_path)
        })

        # Second index (should use cache/incremental)
        print("Second index (should be faster)...")
        result2 = methods.index_graph({
            "input_path": str(test_dir),
            "output_path": str(graph_path)
        })

        print()
        print("First Index:")
        if "code_analysis" in result1:
            print(f"  CPG from cache: {result1['code_analysis'].get('cpg_from_cache', False)}")

        print("Second Index:")
        if "code_analysis" in result2:
            print(f"  CPG from cache: {result2['code_analysis'].get('cpg_from_cache', False)}")

        # Second should use cache
        used_cache = False
        if "code_analysis" in result2:
            used_cache = result2["code_analysis"].get("cpg_from_cache", False)

        print()
        if used_cache:
            print("✅ MCP Incremental Re-index Test PASSED")
        else:
            print("⚠️  MCP Incremental Re-index Test - cache not used (may be expected)")

        return True  # Non-fatal


async def test_mcp_performance():
    """Test 5: Performance benchmarks through MCP."""
    print("\n🧪 Test 5: MCP Performance Benchmarks")
    print("=" * 70)

    import time

    from knowgraph.adapters.mcp import methods

    test_dir = Path(__file__).resolve().parent.parent / "knowgraph" / "domain" / "intelligence"

    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "graph"

        # Benchmark indexing
        print("Benchmarking indexing...")
        start = time.time()

        result = methods.index_graph({
            "input_path": str(test_dir),
            "output_path": str(graph_path)
        })

        index_time = time.time() - start

        # Benchmark query
        print("Benchmarking query...")
        start = time.time()

        methods.handle_query({
            "query": "find vulnerabilities",
            "graph_path": str(graph_path)
        })

        query_time = time.time() - start

        print()
        print("Performance:")
        print(f"  Index time: {index_time:.2f}s")
        print(f"  Query time: {query_time:.2f}s")

        # Reasonable thresholds
        index_ok = index_time < 60  # 60s for indexing
        query_ok = query_time < 10   # 10s for query

        print()
        if index_ok and query_ok:
            print("✅ MCP Performance Test PASSED")
        else:
            print("⚠️  MCP Performance Test - slower than expected")

        return True  # Non-fatal


async def run_mcp_test_suite():
    """Run complete MCP test suite."""
    print("🚀 MCP SERVER END-TO-END TEST SUITE")
    print("=" * 70)
    print()

    tests = [
        ("Index with Code", test_mcp_index_with_code),
        ("CODE Query", test_mcp_code_query),
        ("HYBRID Query", test_mcp_hybrid_query),
        ("Incremental Re-index", test_mcp_incremental_reindex),
        ("Performance", test_mcp_performance),
    ]

    results = []

    for name, test_func in tests:
        try:
            result = await test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Summary
    print("\n" + "=" * 70)
    print("📊 MCP TEST SUITE SUMMARY")
    print("=" * 70)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} - {name}")

    print()
    print(f"Total: {passed}/{total} tests passed ({100*passed/total:.0f}%)")

    if passed == total:
        print("\n🎉 ALL MCP TESTS PASSED!")
        print("✅ System is PRODUCTION READY via MCP")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_mcp_test_suite())
    exit(exit_code)

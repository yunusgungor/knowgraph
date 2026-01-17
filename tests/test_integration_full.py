#!/usr/bin/env python3
"""Integration tests for Joern code indexing and hybrid queries.

Tests the complete flow from indexing to querying with real code repositories.
"""

import asyncio
import tempfile
from pathlib import Path


async def test_code_indexing_integration():
    """Test full code indexing pipeline."""
    print("🧪 Test 1: Code Indexing Integration")
    print("=" * 60)

    from knowgraph.infrastructure.indexing.code_index_integration import CodeIndexIntegration

    # Use knowgraph/domain/intelligence as test project
    test_dir = Path("/Users/yunusgungor/knowrag/knowgraph/domain/intelligence")

    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "test_graph"
        graph_path.mkdir()

        print(f"Indexing: {test_dir}")

        integration = CodeIndexIntegration()
        result = integration.process_code_directory(test_dir, graph_path)

        print()
        print("Results:")
        print(f"  Code files detected: {result.get('code_files_detected', 0)}")
        print(f"  CPG generated: {result.get('cpg_generated', False)}")
        print(f"  Entities extracted: {result.get('entities_extracted', 0)}")

        # Validate (check actual keys, not 'success')
        assert result.get("code_files_detected", 0) > 0, "Should detect code files"
        assert result.get("cpg_generated", False), "Should generate CPG"
        assert result.get("entities_extracted", 0) > 0, "Should extract entities"

        print()
        print("✅ Code indexing integration test PASSED")

        return True


async def test_hybrid_query_integration():
    """Test hybrid query routing and execution."""
    print("\n🧪 Test 2: Hybrid Query Integration")
    print("=" * 60)

    from knowgraph.application.query.query_classifier import QueryClassifier, QueryType

    # Test queries
    test_cases = [
        {
            "query": "is the authentication code secure?",
            "expected_type": QueryType.HYBRID,
            "description": "Security question (English)"
        },
        {
            "query": "how does the login function work?",
            "expected_type": QueryType.HYBRID,
            "description": "Implementation question"
        },
        {
            "query": "login fonksiyonu güvenli mi?",
            "expected_type": QueryType.HYBRID,
            "description": "Security question (Turkish)"
        },
        {
            "query": "find SQL injection vulnerabilities",
            "expected_type": QueryType.CODE,
            "description": "Pure code query"
        },
        {
            "query": "explain the architecture",
            "expected_type": QueryType.TEXT,
            "description": "Pure text query"
        }
    ]

    classifier = QueryClassifier()

    all_passed = True
    for case in test_cases:
        query = case["query"]
        expected = case["expected_type"]

        result = classifier.classify(query)
        passed = result == expected

        status = "✅" if passed else "❌"
        print(f"{status} {result.value:8} - {case['description']}")
        print(f'   Query: "{query}"')

        if not passed:
            all_passed = False
            print(f"   Expected: {expected.value}, Got: {result.value}")

    print()
    if all_passed:
        print("✅ Hybrid query integration test PASSED")
    else:
        print("❌ Some tests FAILED")

    return all_passed


async def test_end_to_end_workflow():
    """Test complete workflow: index → query → results."""
    print("\n🧪 Test 3: End-to-End Workflow")
    print("=" * 60)

    from knowgraph.application.query.code_query_handler import CodeQueryHandler
    from knowgraph.application.query.query_classifier import QueryClassifier, QueryType
    from knowgraph.infrastructure.indexing.code_index_integration import CodeIndexIntegration

    test_dir = Path("/Users/yunusgungor/knowrag/knowgraph/domain/intelligence")

    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "test_graph"
        graph_path.mkdir()

        # Step 1: Index
        print("Step 1: Indexing code...")
        integration = CodeIndexIntegration()
        index_result = integration.process_code_directory(test_dir, graph_path)

        # Check result has data (not 'success' key)
        assert index_result.get("entities_extracted", 0) > 0, "Should extract entities"
        print(f"  ✅ Indexed {index_result['entities_extracted']} entities")

        # Step 2: Classify query
        print("\nStep 2: Classifying query...")
        classifier = QueryClassifier()
        query = "find security vulnerabilities in authentication"
        query_type = classifier.classify(query)

        print(f"  ✅ Query classified as: {query_type.value}")

        # Step 3: Execute code query
        print("\nStep 3: Executing code query...")
        handler = CodeQueryHandler(graph_path)
        query_result = await handler.handle(query)

        print(f"  Success: {query_result.get('success', False)}")
        print(f"  Tool: {query_result.get('tool', 'none')}")
        print(f"  CPG available: {query_result.get('cpg_available', False)}")

        # Validate
        assert query_type == QueryType.CODE, "Should classify as CODE"
        assert query_result.get("tool") == "security_scan", "Should route to security_scan"

        print()
        print("✅ End-to-end workflow test PASSED")

        return True


async def test_performance_benchmarks():
    """Test performance meets acceptable thresholds."""
    print("\n🧪 Test 4: Performance Benchmarks")
    print("=" * 60)

    import time

    from knowgraph.infrastructure.indexing.code_index_integration import CodeIndexIntegration

    test_dir = Path("/Users/yunusgungor/knowrag/knowgraph/domain/intelligence")

    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "test_graph"
        graph_path.mkdir()

        # Benchmark indexing
        print("Benchmarking indexing...")
        start = time.time()

        integration = CodeIndexIntegration()
        result = integration.process_code_directory(test_dir, graph_path)

        duration = time.time() - start

        print(f"  Duration: {duration:.2f}s")
        print(f"  Entities: {result['entities_extracted']}")
        print(f"  Rate: {result['entities_extracted']/duration:.1f} entities/sec")

        # Validate performance (allow 35s for safety margin)
        assert duration < 35, f"Indexing too slow: {duration:.2f}s (max 35s)"

        print()
        print("✅ Performance benchmark test PASSED")

        return True


async def run_all_integration_tests():
    """Run all integration tests."""
    print("🚀 Joern Integration Test Suite")
    print("=" * 60)
    print()

    results = []

    # Test 1: Code indexing
    try:
        result = await test_code_indexing_integration()
        results.append(("Code Indexing", result))
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results.append(("Code Indexing", False))

    # Test 2: Hybrid queries
    try:
        result = await test_hybrid_query_integration()
        results.append(("Hybrid Queries", result))
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results.append(("Hybrid Queries", False))

    # Test 3: End-to-end
    try:
        result = await test_end_to_end_workflow()
        results.append(("End-to-End", result))
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results.append(("End-to-End", False))

    # Test 4: Performance
    try:
        result = await test_performance_benchmarks()
        results.append(("Performance", result))
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results.append(("Performance", False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Integration Test Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} - {name}")

    print()
    print(f"Total: {passed}/{total} tests passed ({100*passed/total:.0f}%)")

    if passed == total:
        print("\n🎉 All integration tests passed!")
        print("✅ System is PRODUCTION READY")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_integration_tests())
    exit(exit_code)

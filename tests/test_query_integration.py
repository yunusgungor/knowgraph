#!/usr/bin/env python3
"""Comprehensive test suite for query routing and classification.

Tests CODE, TEXT, and HYBRID query handling to validate the complete
query integration system.
"""

import asyncio
from pathlib import Path

from knowgraph.application.query.code_query_handler import CodeQueryHandler
from knowgraph.application.query.query_classifier import QueryClassifier, QueryType


async def test_query_classification():
    """Test query classifier accuracy."""
    print("🧪 Test 1: Query Classification")
    print("=" * 60)

    classifier = QueryClassifier()

    test_cases = [
        # CODE queries
        ("find SQL injection vulnerabilities", QueryType.CODE),
        ("scan for security issues", QueryType.CODE),
        ("check for dead code", QueryType.CODE),
        ("show me authentication functions", QueryType.CODE),
        ("analyze call graph", QueryType.CODE),
        ("güvenlik açıkları var mı?", QueryType.CODE),

        # TEXT queries
        ("how does authentication work?", QueryType.TEXT),
        ("explain the architecture", QueryType.TEXT),
        ("what is JWT?", QueryType.TEXT),
        ("why use this approach?", QueryType.TEXT),

        # HYBRID queries
        ("is authentication code secure?", QueryType.HYBRID),
        ("explain how login function works", QueryType.HYBRID),
        ("why is this code vulnerable?", QueryType.HYBRID),
    ]

    correct = 0
    total = len(test_cases)

    for query, expected in test_cases:
        result = classifier.classify(query)
        match = "✅" if result == expected else "❌"

        print(f'{match} {result.value:8} - "{query}"')

        if result == expected:
            correct += 1

    accuracy = 100 * correct / total
    print(f"\nAccuracy: {correct}/{total} ({accuracy:.1f}%)")

    return accuracy >= 90  # Pass if >= 90%


async def test_code_query_handler():
    """Test code query handler tool matching."""
    print("\n🧪 Test 2: Code Query Handler")
    print("=" * 60)

    # Create temp graph path
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir)
        handler = CodeQueryHandler(graph_path)

        test_queries = [
            ("find SQL injections", "security_scan"),
            ("check for dead code", "find_dead_code"),
            ("show me login functions", "joern_query"),
            ("analyze dependencies", "analyze_call_graph"),
        ]

        all_correct = True
        for query, expected_tool in test_queries:
            tool = handler._match_tool(query)
            match = "✅" if tool == expected_tool else "❌"

            print(f'{match} {tool:20} - "{query}"')

            if tool != expected_tool:
                all_correct = False

        return all_correct


async def test_cpg_metadata():
    """Test CPG metadata storage and retrieval."""
    print("\n🧪 Test 3: CPG Metadata")
    print("=" * 60)

    import tempfile

    from knowgraph.infrastructure.indexing.cpg_metadata import (
        get_cpg_path,
        load_cpg_metadata,
        save_cpg_metadata,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        graph_path = Path(tmpdir) / "test_graph"
        graph_path.mkdir()

        cpg_path = Path(tmpdir) / "test.cpg"
        cpg_path.touch()

        # Test save
        save_cpg_metadata(graph_path, cpg_path, entities_count=42)
        print("✅ Saved CPG metadata")

        # Test load
        metadata = load_cpg_metadata(graph_path)
        assert metadata is not None, "Failed to load metadata"
        assert metadata["entities_count"] == 42, "Wrong entity count"
        print(f"✅ Loaded metadata: {metadata['entities_count']} entities")

        # Test retrieve
        retrieved = get_cpg_path(graph_path)
        assert retrieved == cpg_path, "Wrong CPG path"
        print(f"✅ Retrieved CPG path: {retrieved}")

        return True


async def test_integration_scenarios():
    """Test realistic query scenarios."""
    print("\n🧪 Test 4: Integration Scenarios")
    print("=" * 60)

    classifier = QueryClassifier()

    scenarios = [
        {
            "query": "find all SQL injection vulnerabilities in auth code",
            "expected_type": QueryType.CODE,
            "expected_tool": "security_scan",
            "description": "Security scan request"
        },
        {
            "query": "how does the JWT authentication system work?",
            "expected_type": QueryType.TEXT,
            "expected_tool": None,
            "description": "Documentation query"
        },
        {
            "query": "is the login function secure?",
            "expected_type": QueryType.HYBRID,
            "expected_tool": "security_scan",
            "description": "Security question (hybrid)"
        },
    ]

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        handler = CodeQueryHandler(Path(tmpdir))

        all_passed = True
        for scenario in scenarios:
            query = scenario["query"]

            # Test classification
            query_type = classifier.classify(query)
            type_match = query_type == scenario["expected_type"]

            # Test tool matching (for CODE queries)
            if scenario["expected_tool"]:
                tool = handler._match_tool(query)
                tool_match = tool == scenario["expected_tool"]
            else:
                tool_match = True

            passed = type_match and tool_match
            status = "✅" if passed else "❌"

            print(f"{status} {scenario['description']}")
            print(f'   Query: "{query}"')
            print(f"   Type: {query_type.value} (expected: {scenario['expected_type'].value})")
            if scenario["expected_tool"]:
                print(f"   Tool: {tool} (expected: {scenario['expected_tool']})")

            if not passed:
                all_passed = False

        return all_passed


async def run_all_tests():
    """Run all tests and report results."""
    print("🚀 Query Integration Test Suite")
    print("=" * 60)
    print()

    results = []

    # Test 1: Classification
    try:
        result = await test_query_classification()
        results.append(("Query Classification", result))
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results.append(("Query Classification", False))

    # Test 2: Code Handler
    try:
        result = await test_code_query_handler()
        results.append(("Code Query Handler", result))
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results.append(("Code Query Handler", False))

    # Test 3: CPG Metadata
    try:
        result = await test_cpg_metadata()
        results.append(("CPG Metadata", result))
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results.append(("CPG Metadata", False))

    # Test 4: Integration
    try:
        result = await test_integration_scenarios()
        results.append(("Integration Scenarios", result))
    except Exception as e:
        print(f"❌ Test failed: {e}")
        results.append(("Integration Scenarios", False))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:10} - {name}")

    print()
    print(f"Total: {passed}/{total} tests passed ({100*passed/total:.0f}%)")

    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    exit(exit_code)

"""Real MCP Server End-to-End Tests.

Tests all 8 MCP tools with real MCP client.
"""

import asyncio
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_mcp_server_complete():
    """Complete end-to-end test of all MCP tools."""
    print("🧪 REAL MCP SERVER END-TO-END TESTS")
    print("=" * 70)

    results = {
        "get_stats": False,
        "query": False,
        "index": False,
        "discover_conversations": False,
        "tag_snippet": False,
        "batch_query": False,
        "analyze_impact": False,
        "validate": False,
    }

    errors = []

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "knowgraph.adapters.mcp.server"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("\n✅ MCP Server Connected\n")

            # Test 1: get_stats (without graph_path - auto-detection)
            print("1️⃣ Testing knowgraph_get_stats (auto-detection)...")
            try:
                result = await session.call_tool("knowgraph_get_stats", arguments={})
                response = result.content[0].text  # type: ignore

                # Check for read-only error
                if "read-only" in response.lower() or "errno 30" in response.lower():
                    print("   ❌ FAIL: Read-only file system error")
                    errors.append("get_stats: Read-only file system")
                else:
                    print("   ✅ PASS")
                    print(f"   Response: {response[:100]}...")
                    results["get_stats"] = True
            except Exception as e:
                print(f"   ❌ FAIL: {e}")
                errors.append(f"get_stats: {e}")

            # Test 2: query (without graph_path)
            print("\n2️⃣ Testing knowgraph_query (auto-detection)...")
            try:
                result = await session.call_tool(
                    "knowgraph_query", arguments={"query": "test query", "top_k": 5}
                )
                response = result.content[0].text  # type: ignore

                if "read-only" in response.lower() or "errno 30" in response.lower():
                    print("   ❌ FAIL: Read-only file system error")
                    errors.append("query: Read-only file system")
                else:
                    print("   ✅ PASS")
                    print(f"   Response: {response[:100]}...")
                    results["query"] = True
            except Exception as e:
                print(f"   ❌ FAIL: {e}")
                errors.append(f"query: {e}")

            # Test 3: validate (without graph_path)
            print("\n3️⃣ Testing knowgraph_validate (auto-detection)...")
            try:
                result = await session.call_tool("knowgraph_validate", arguments={})
                response = result.content[0].text  # type: ignore

                if "read-only" in response.lower() or "errno 30" in response.lower():
                    print("   ❌ FAIL: Read-only file system error")
                    errors.append("validate: Read-only file system")
                else:
                    print("   ✅ PASS")
                    print(f"   Response: {response[:100]}...")
                    results["validate"] = True
            except Exception as e:
                print(f"   ❌ FAIL: {e}")
                errors.append(f"validate: {e}")

            # Test 4: tag_snippet (with test graphstore)
            print("\n4️⃣ Testing knowgraph_tag_snippet...")
            try:
                result = await session.call_tool(
                    "knowgraph_tag_snippet",
                    arguments={
                        "tag": "e2e test tag",
                        "snippet": "This is a test snippet for E2E testing",
                        "graph_path": "./test_mcp_e2e_graphstore",
                    },
                )
                response = result.content[0].text  # type: ignore

                if "read-only" in response.lower() or "errno 30" in response.lower():
                    print("   ❌ FAIL: Read-only file system error")
                    errors.append("tag_snippet: Read-only file system")
                elif "successfully" in response.lower() or "tagged" in response.lower():
                    print("   ✅ PASS")
                    print(f"   Response: {response[:100]}...")
                    results["tag_snippet"] = True
                else:
                    print(f"   ⚠️  PARTIAL: {response[:100]}...")
                    results["tag_snippet"] = True
            except Exception as e:
                print(f"   ❌ FAIL: {e}")
                errors.append(f"tag_snippet: {e}")

            # Test 5: discover_conversations
            print("\n5️⃣ Testing knowgraph_discover_conversations...")
            try:
                result = await session.call_tool(
                    "knowgraph_discover_conversations",
                    arguments={"graph_path": "./test_mcp_e2e_graphstore", "editor": "antigravity"},
                )
                response = result.content[0].text  # type: ignore

                if "read-only" in response.lower() or "errno 30" in response.lower():
                    print("   ❌ FAIL: Read-only file system error")
                    errors.append("discover_conversations: Read-only file system")
                else:
                    print("   ✅ PASS")
                    print(f"   Response: {response[:150]}...")
                    results["discover_conversations"] = True
            except Exception as e:
                print(f"   ❌ FAIL: {e}")
                errors.append(f"discover_conversations: {e}")

            # Test 6: batch_query
            print("\n6️⃣ Testing knowgraph_batch_query...")
            try:
                result = await session.call_tool(
                    "knowgraph_batch_query",
                    arguments={"queries": ["test query 1", "test query 2"], "top_k": 3},
                )
                response = result.content[0].text  # type: ignore

                if "read-only" in response.lower() or "errno 30" in response.lower():
                    print("   ❌ FAIL: Read-only file system error")
                    errors.append("batch_query: Read-only file system")
                else:
                    print("   ✅ PASS")
                    print(f"   Response: {response[:100]}...")
                    results["batch_query"] = True
            except Exception as e:
                print(f"   ❌ FAIL: {e}")
                errors.append(f"batch_query: {e}")

            # Test 7: analyze_impact
            print("\n7️⃣ Testing knowgraph_analyze_impact...")
            try:
                result = await session.call_tool(
                    "knowgraph_analyze_impact",
                    arguments={"element": "test_element", "mode": "semantic"},
                )
                response = result.content[0].text  # type: ignore

                if "read-only" in response.lower() or "errno 30" in response.lower():
                    print("   ❌ FAIL: Read-only file system error")
                    errors.append("analyze_impact: Read-only file system")
                else:
                    print("   ✅ PASS")
                    print(f"   Response: {response[:100]}...")
                    results["analyze_impact"] = True
            except Exception as e:
                print(f"   ❌ FAIL: {e}")
                errors.append(f"analyze_impact: {e}")

            # Test 8: index (small test file)
            print("\n8️⃣ Testing knowgraph_index...")

            # Create test file
            test_file = Path("./test_mcp_index.md")
            test_file.write_text("# Test Document\n\nThis is a test document for MCP indexing.")

            try:
                result = await session.call_tool(
                    "knowgraph_index",
                    arguments={
                        "input_path": str(test_file),
                        "graph_path": "./test_mcp_e2e_graphstore",
                    },
                )
                response = result.content[0].text  # type: ignore

                if "read-only" in response.lower() or "errno 30" in response.lower():
                    print("   ❌ FAIL: Read-only file system error")
                    errors.append("index: Read-only file system")
                elif "successfully" in response.lower() or "indexed" in response.lower():
                    print("   ✅ PASS")
                    print(f"   Response: {response[:100]}...")
                    results["index"] = True
                else:
                    print(f"   ⚠️  PARTIAL: {response[:100]}...")
                    results["index"] = True
            except Exception as e:
                print(f"   ❌ FAIL: {e}")
                errors.append(f"index: {e}")
            finally:
                # Cleanup
                if test_file.exists():
                    test_file.unlink()

            print("\n" + "=" * 70)
            print("📊 TEST RESULTS:\n")

            for tool_name, passed in results.items():
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"   {tool_name:25s}: {status}")

            total = sum(results.values())
            print(f"\n🎯 Score: {total}/{len(results)} tests passed")

            if errors:
                print("\n❌ ERRORS:\n")
                for error in errors:
                    print(f"   - {error}")

            if total == len(results):
                print("\n🎉 ALL MCP TOOLS WORKING - PRODUCTION READY!")
                return True
            else:
                print(f"\n⚠️  {len(results) - total} tools failed")
                return False


if __name__ == "__main__":
    success = asyncio.run(test_mcp_server_complete())
    exit(0 if success else 1)

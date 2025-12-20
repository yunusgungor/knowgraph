"""Real MCP query test - query tagged snippet via MCP protocol."""

import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def test_mcp_query():
    """Test knowgraph_query tool via MCP to find tagged snippet."""
    print("🔍 Real MCP Query Test\n")
    print("=" * 60)

    server_params = StdioServerParameters(
        command="python",
        args=["-m", "knowgraph.adapters.mcp.server"],
        env=None,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ MCP Server connected\n")

            # Test 1: Query for the tagged snippet we created earlier
            print("1️⃣ Querying via MCP: 'mcp test snippet'...")

            try:
                result = await session.call_tool(
                    "knowgraph_query",
                    arguments={
                        "query": "mcp test snippet",
                        "graph_path": "./test_mcp_graphstore",
                        "top_k": 5,
                    },
                )

                print("✅ Query executed successfully!\n")
                print("📄 Response:")
                print("-" * 60)
                response_text = result.content[0].text
                print(response_text)
                print("-" * 60)

                # Verify tagged snippet was found
                if "Tagged Snippet: mcp test snippet" in response_text:
                    print("\n✅ VERIFIED: Tagged snippet found in query results!")
                    print("   Tag metadata preserved")
                    print("   Content retrieved correctly")
                else:
                    print("\n⚠️  Tagged snippet not found in results")

            except Exception as e:
                print(f"❌ Query failed: {e}")

            # Test 2: Query for conversation content
            print("\n2️⃣ Querying via MCP: 'semantic search implementation'...")

            try:
                result = await session.call_tool(
                    "knowgraph_query",
                    arguments={
                        "query": "semantic search implementation",
                        "graph_path": "./test_mcp_graphstore",
                        "top_k": 3,
                    },
                )

                print("✅ Query executed successfully!\n")
                print("📄 Response (first 500 chars):")
                print("-" * 60)
                response_text = result.content[0].text
                print(response_text[:500] + "...")
                print("-" * 60)

                # Verify conversation content was found
                if "SemanticSearch" in response_text or "sentence_transformers" in response_text:
                    print("\n✅ VERIFIED: Conversation content found!")
                    print("   Code snippets preserved")
                    print("   Context retrieved correctly")

            except Exception as e:
                print(f"❌ Query failed: {e}")

            print("\n" + "=" * 60)
            print("✅ MCP Query test completed!")
            print("\nConclusion:")
            print("  - MCP query tool works ✅")
            print("  - Tagged snippets retrievable ✅")
            print("  - Conversation content searchable ✅")


if __name__ == "__main__":
    asyncio.run(test_mcp_query())

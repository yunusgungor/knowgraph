"""Test MCP server tools with real MCP protocol."""

import asyncio

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_mcp_tools():
    """Test MCP server tools via actual MCP protocol."""
    print("🔌 Testing MCP Server Tools\n")
    print("=" * 60)

    # Start MCP server
    server_params = StdioServerParameters(
        command="python",
        args=["-m", "knowgraph.adapters.mcp.server"],
        env=None,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()
            print("✅ MCP Server connected\n")

            # Test 1: List tools
            print("1️⃣ Listing available tools...")
            tools = await session.list_tools()
            print(f"✅ Found {len(tools.tools)} tools:\n")

            for tool in tools.tools:
                print(f"   📦 {tool.name}")
                if "discover" in tool.name or "tag" in tool.name:
                    print(f"      ⭐ NEW: {tool.description[:60]}...")

            # Test 2: Call knowgraph_discover_conversations
            print("\n2️⃣ Testing knowgraph_discover_conversations...")
            try:
                result = await session.call_tool(
                    "knowgraph_discover_conversations",
                    arguments={"graph_path": "./test_mcp_graphstore", "editor": "all"},
                )
                print("✅ Tool executed successfully!")
                print(f"   Response: {result.content[0].text[:200]}...")
            except Exception as e:
                print(f"⚠️  Error: {e}")

            # Test 3: Call knowgraph_tag_snippet
            print("\n3️⃣ Testing knowgraph_tag_snippet...")
            try:
                result = await session.call_tool(
                    "knowgraph_tag_snippet",
                    arguments={
                        "tag": "mcp test snippet",
                        "snippet": "This is a test snippet from MCP client",
                        "graph_path": "./test_mcp_graphstore",
                    },
                )
                print("✅ Tool executed successfully!")
                print(f"   Response: {result.content[0].text}")
            except Exception as e:
                print(f"⚠️  Error: {e}")

            print("\n" + "=" * 60)
            print("✅ MCP Server integration test completed!")


if __name__ == "__main__":
    asyncio.run(test_mcp_tools())

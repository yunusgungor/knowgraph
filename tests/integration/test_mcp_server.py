import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Add project root to path
sys.path.append(os.getcwd())


async def run_test():
    # Load .env file
    from dotenv import load_dotenv

    load_dotenv()

    # Define server parameters
    # We run the actual CLI command to test the full entry point
    server_params = StdioServerParameters(
        command="python3", args=["-m", "knowgraph.adapters.cli.main", "serve"], env=os.environ.copy()
    )

    print("🔌 Connecting to MCP server...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 1. Initialize
            await session.initialize()
            print("✅ Initialized")

            # 2. List Tools
            tools = await session.list_tools()
            print(f"\n🛠️  Available Tools: {[t.name for t in tools.tools]}")

            tool_names = [t.name for t in tools.tools]
            if "knowgraph_query" not in tool_names:
                print("❌ FAIL: knowgraph_query tool missing!")
                return

            # 3. Call knowgraph_index
            print("\n📝 Testing knowgraph_index with 'vidsplice.md' (Large File Risk)...")
            test_data_path = os.path.join(os.getcwd(), "test_data/vidsplice.md")
            graph_path = os.path.join(os.getcwd(), "vidsplice_graph_store")

            # Create a mock sampling handler if possible or just expect failure/success
            # For now, we just call it. Expected: It might fail if no Sampling capability in client.
            try:
                index_result = await session.call_tool(
                    "knowgraph_index",
                    arguments={"input_path": test_data_path, "output_path": graph_path},
                )
                print(f"Index Result: {index_result}")
            except Exception as e:
                print(f"Index Call Failed: {e}")

            # 4. Call knowgraph_query
            print("\n🔍 Testing knowgraph_query after indexing...")

            result = await session.call_tool(
                "knowgraph_query",
                arguments={
                    "query": "What are the features of VidSplice?",
                    "graph_path": graph_path,
                },
            )

            print("\n📝 Result:")
            # MCP returns a list of content blocks
            for content in result.content:
                if content.type == "text":
                    print(f"---\n{content.text}\n---")

            if "Video Processing" in result.content[0].text:
                print("\n✅ PASS: Found expected content (Video Processing)")
            else:
                print("\n⚠️  WARNING: Expected content not found, but tool executed.")


if __name__ == "__main__":
    asyncio.run(run_test())

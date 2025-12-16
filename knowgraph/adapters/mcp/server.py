import asyncio
import json
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from knowgraph.adapters.mcp.methods import analyze_path_impact_report, index_graph
from knowgraph.adapters.mcp.utils import get_llm_provider, resolve_graph_path
from knowgraph.application.querying.query_engine import QueryEngine
from knowgraph.application.querying.query_expansion import QueryExpander
from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.domain.algorithms.graph_validator import validate_graph_consistency
from knowgraph.infrastructure.storage.manifest import Manifest

app = Server("knowgraph-mcp")

# Path to project root for resolving relative paths (defaults to current working directory)
PROJECT_ROOT = Path.cwd()


@app.call_tool()  # type: ignore
async def call_tool(name: str, arguments: Any) -> list[types.TextContent]:
    if name == "knowgraph_query":
        query = arguments.get("query")
        graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
        graph_path = resolve_graph_path(graph_path_arg, PROJECT_ROOT)

        provider = get_llm_provider(app)

        if not query:
            return [types.TextContent(type="text", text="Error: Query is required.")]

        try:
            # Initialize engine (retrieval + generation)
            engine = QueryEngine(graph_path)

            # Execute retrieval
            top_k = arguments.get("top_k", 20)
            max_hops = arguments.get("max_hops", 4)
            with_explanation = arguments.get("with_explanation", False)
            expand_query = arguments.get("expand_query", False)
            max_tokens = arguments.get("max_tokens", 3000)
            enable_hierarchical_lifting = arguments.get("enable_hierarchical_lifting", True)
            lift_levels = arguments.get("lift_levels", 2)
            system_prompt = arguments.get("system_prompt", None)

            # Query Expansion (now supports generic provider)
            if expand_query:
                try:
                    if provider:
                        # Use generic provider for expansion
                        expander = QueryExpander(intelligence_provider=provider)
                        expansion_terms = await expander.expand_query_async(query)
                        if expansion_terms:
                            query = f"{query} {' '.join(expansion_terms)}"
                    else:
                        # Fall back to OpenAI env vars
                        import os

                        if os.getenv("KNOWGRAPH_API_KEY"):
                            llm_model = os.getenv(
                                "KNOWGRAPH_LLM_MODEL", "amazon/nova-2-lite-v1:free"
                            )
                            expander = QueryExpander(provider="openai", model=llm_model)
                            expansion_terms = expander.expand_query(query)
                            if expansion_terms:
                                query = f"{query} {' '.join(expansion_terms)}"
                except Exception:
                    pass

            result = engine.query(
                query,
                top_k=top_k,
                max_hops=max_hops,
                max_tokens=max_tokens,
                with_explanation=with_explanation,
                enable_hierarchical_lifting=enable_hierarchical_lifting,
                lift_levels=lift_levels,
            )

            # Generate Answer using LLM Delegation
            answer = result.context

            if provider:
                base_system_prompt = (
                    system_prompt
                    if system_prompt
                    else "You are a helpful assistant. Use the following context to answer the user's question."
                )

                prompt = (
                    f"{base_system_prompt}\n\n"
                    f"Context:\n{result.context}\n\n"
                    f"Question: {query}\n\n"
                    f"Answer:"
                )
                if with_explanation and result.explanation:
                    prompt += f"\n\nExplanation Data:\n{json.dumps(result.explanation.to_dict(), indent=2, default=str)}"

                try:
                    generated_answer = await provider.generate_text(prompt)
                    if generated_answer:
                        answer = generated_answer
                except Exception as e:
                    answer = f"{result.context}\n\n[Generation Error: {e!s}]"

            return [types.TextContent(type="text", text=answer)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"Error executing query: {e!s}")]

    elif name == "knowgraph_index":
        input_path = arguments.get("input_path")
        resume_mode = arguments.get("resume", False)
        output_path = arguments.get("output_path", DEFAULT_GRAPH_STORE_PATH)
        gc = arguments.get("gc", False)

        if not input_path:
            return [types.TextContent(type="text", text="Error: input_path is required.")]

        # Resolve paths
        graph_path = resolve_graph_path(output_path, PROJECT_ROOT)

        # Determine provider
        provider = get_llm_provider(app)

        return await index_graph(input_path, graph_path, provider, resume_mode, gc)

    elif name == "knowgraph_analyze_impact":
        element = arguments.get("element")
        max_hops = arguments.get("max_hops", 4)
        graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
        mode = arguments.get("mode", "semantic")

        if not element:
            return [types.TextContent(type="text", text="Error: element is required.")]

        graph_path = resolve_graph_path(graph_path_arg, PROJECT_ROOT)

        try:
            if mode == "path":
                return analyze_path_impact_report(element, graph_path, max_hops)
            else:
                # Semantic impact analysis
                engine = QueryEngine(graph_path)
                result = engine.analyze_impact(element, max_hops=max_hops)
                return [types.TextContent(type="text", text=result.answer)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"Error executing impact analysis: {e!s}")]

    elif name == "knowgraph_validate":
        graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
        graph_path = resolve_graph_path(graph_path_arg, PROJECT_ROOT)

        try:
            result = validate_graph_consistency(graph_path)
            status = "VALID" if result.valid else "INVALID"
            message = f"Graph Validation Status: {status}\n"
            if not result.valid:
                message += f"\nErrors:\n{result.get_error_summary()}"
            else:
                message += "\nGraph is consistent and ready for queries."

            return [types.TextContent(type="text", text=message)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Validation failed: {e!s}")]

    elif name == "knowgraph_get_stats":
        graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
        graph_path = resolve_graph_path(graph_path_arg, PROJECT_ROOT)

        manifest_path = graph_path / "metadata" / "manifest.json"

        if not manifest_path.exists():
            return [types.TextContent(type="text", text="No manifest found. Graph might be empty.")]

        try:
            with open(manifest_path, encoding="utf-8") as f:
                data = json.load(f)

            manifest = Manifest.from_dict(data)
            stats = (
                f"Graph Stats (v{manifest.version})\n"
                f"Nodes: {manifest.node_count}\n"
                f"Edges: {manifest.edge_count}\n"
                f"Semantic Edges: {manifest.semantic_edge_count}\n"
                f"Files Indexed: {len(manifest.file_hashes)}"
            )
            return [types.TextContent(type="text", text=stats)]
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error reading stats: {e!s}")]

    elif name == "knowgraph_batch_query":
        queries = arguments.get("queries", [])
        graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
        graph_path = resolve_graph_path(graph_path_arg, PROJECT_ROOT)

        if not queries or not isinstance(queries, list):
            return [types.TextContent(type="text", text="Error: queries must be a non-empty list.")]

        provider = get_llm_provider(app)

        try:
            # Shared parameters for all queries
            top_k = arguments.get("top_k", 20)
            max_hops = arguments.get("max_hops", 4)
            max_tokens = arguments.get("max_tokens", 3000)
            enable_hierarchical_lifting = arguments.get("enable_hierarchical_lifting", True)
            lift_levels = arguments.get("lift_levels", 2)

            engine = QueryEngine(graph_path)
            results = []

            # Process queries sequentially (could be parallelized with asyncio.gather if needed)
            for query in queries:
                if not query or not isinstance(query, str):
                    results.append({"query": query, "error": "Invalid query format"})
                    continue

                try:
                    result = engine.query(
                        query,
                        top_k=top_k,
                        max_hops=max_hops,
                        max_tokens=max_tokens,
                        enable_hierarchical_lifting=enable_hierarchical_lifting,
                        lift_levels=lift_levels,
                    )

                    # Generate answer with LLM if provider available
                    answer = result.context
                    if provider:
                        try:
                            prompt = (
                                f"You are a helpful assistant. Use the following context to answer the user's question.\n\n"
                                f"Context:\n{result.context}\n\n"
                                f"Question: {query}\n\n"
                                f"Answer:"
                            )
                            generated_answer = await provider.generate_text(prompt)
                            if generated_answer:
                                answer = generated_answer
                        except Exception:
                            pass

                    results.append(
                        {
                            "query": query,
                            "answer": answer,
                            "nodes_retrieved": len(result.seed_nodes),
                            "execution_time": result.execution_time,
                        }
                    )
                except Exception as e:
                    results.append({"query": query, "error": str(e)})

            # Format results as text
            output = f"Batch Query Results ({len(queries)} queries)\n" + "=" * 50 + "\n\n"
            for i, res in enumerate(results, 1):
                output += f"Query {i}: {res.get('query', 'N/A')}\n"
                if "error" in res:
                    output += f"Error: {res['error']}\n"
                else:
                    output += f"Answer: {res.get('answer', 'N/A')}\n"
                    output += f"Nodes: {res.get('nodes_retrieved', 0)}, Time: {res.get('execution_time', 0):.2f}s\n"
                output += "\n"

            return [types.TextContent(type="text", text=output)]

        except Exception as e:
            return [types.TextContent(type="text", text=f"Error executing batch query: {e!s}")]

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


@app.list_resources()  # type: ignore
async def list_resources() -> list[types.Resource]:
    graph_path = resolve_graph_path(DEFAULT_GRAPH_STORE_PATH, PROJECT_ROOT)
    manifest_path = graph_path / "metadata" / "manifest.json"

    resources = []
    if manifest_path.exists():
        resources.append(
            types.Resource(
                uri=types.AnyUrl("knowgraph://default/manifest"),  # type: ignore
                name="Default Graph Manifest",
                description="Manifest file of the default knowledge graph",
                mimeType="application/json",
            )
        )
    return resources


@app.read_resource()  # type: ignore
async def read_resource(uri: Any) -> str | bytes:  # type: ignore
    if str(uri) == "knowgraph://default/manifest":
        graph_path = resolve_graph_path(DEFAULT_GRAPH_STORE_PATH, PROJECT_ROOT)
        manifest_path = graph_path / "metadata" / "manifest.json"
        if manifest_path.exists():
            return manifest_path.read_text(encoding="utf-8")
        raise ValueError("Manifest not found")

    raise ValueError(f"Unknown resource: {uri}")


@app.list_tools()  # type: ignore
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="knowgraph_query",
            description="Retrieve relevant context from the KnowGraph knowledge graph to answer a query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The natural language query to retrieve context for.",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional, defaults to ./graphstore).",
                    },
                    "with_explanation": {
                        "type": "boolean",
                        "description": "Include an explanation of how the answer was derived (default: false).",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of top results to return (default: 20).",
                    },
                    "max_hops": {
                        "type": "integer",
                        "description": "Maximum number of hops for graph traversal (default: 4).",
                    },
                    "expand_query": {
                        "type": "boolean",
                        "description": "Uses AI to expand query with synonyms and technical terms (default: false).",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum token count for the context window (default: 3000).",
                    },
                    "enable_hierarchical_lifting": {
                        "type": "boolean",
                        "description": "Enable hierarchical context lifting for broader context (default: true).",
                    },
                    "lift_levels": {
                        "type": "integer",
                        "description": "Number of directory levels to lift context from (default: 2).",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="knowgraph_analyze_impact",
            description="Analyze the impact of changing a specific element (code, function, etc.) in the graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "element": {
                        "type": "string",
                        "description": "The element (name or query) to analyze impact for.",
                    },
                    "max_hops": {
                        "type": "integer",
                        "description": "Maximum depth of dependency traversal (default: 4).",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional, defaults to ./graphstore).",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["semantic", "path"],
                        "description": "Analysis mode: 'semantic' (concept) or 'path' (file path pattern). Default: semantic.",
                    },
                },
                "required": ["element"],
            },
        ),
        types.Tool(
            name="knowgraph_validate",
            description="Validate the consistency and health of the knowledge graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional).",
                    },
                },
            },
        ),
        types.Tool(
            name="knowgraph_get_stats",
            description="Get basic statistics about the stored knowledge graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional).",
                    },
                },
            },
        ),
        types.Tool(
            name="knowgraph_index",
            description="Trigger indexing of a documentation directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {"type": "string", "description": "Path to markdown files."},
                    "output_path": {
                        "type": "string",
                        "description": "Path to graph storage (optional).",
                    },
                    "resume": {
                        "type": "boolean",
                        "description": "Resume indexing from checkpoint if interrupted (default: false).",
                    },
                    "gc": {
                        "type": "boolean",
                        "description": "Garbage collect deleted nodes during update (default: false).",
                    },
                },
                "required": ["input_path"],
            },
        ),
        types.Tool(
            name="knowgraph_batch_query",
            description="Execute multiple queries in batch for efficient processing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of natural language queries to process.",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional, defaults to ./graphstore).",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of top results to return per query (default: 20).",
                    },
                    "max_hops": {
                        "type": "integer",
                        "description": "Maximum number of hops for graph traversal (default: 4).",
                    },
                    "max_tokens": {
                        "type": "integer",
                        "description": "Maximum token count for the context window (default: 3000).",
                    },
                    "enable_hierarchical_lifting": {
                        "type": "boolean",
                        "description": "Enable hierarchical context lifting for broader context (default: true).",
                    },
                    "lift_levels": {
                        "type": "integer",
                        "description": "Number of directory levels to lift context from (default: 2).",
                    },
                },
                "required": ["queries"],
            },
        ),
    ]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        init_options = app.create_initialization_options()
        await app.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())

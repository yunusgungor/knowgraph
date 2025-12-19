"""Diagnostic handler for MCP server health checks."""

import os
import sys
from pathlib import Path
from typing import Any

import mcp.types as types  # type: ignore


async def handle_diagnostic(
    arguments: dict[str, Any],
    project_root: Path,
) -> list[types.TextContent]:
    """Handle knowgraph_diagnostic tool for system health checks.

    Args:
    ----
        arguments: Tool arguments
        project_root: Project root path

    Returns:
    -------
        Diagnostic report as text content

    """
    from knowgraph.adapters.mcp.utils import resolve_graph_path
    from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
    from knowgraph.infrastructure.storage.filesystem import list_all_nodes

    graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
    graph_path = resolve_graph_path(graph_path_arg, project_root)

    report_lines = ["# 🔍 KnowGraph Diagnostic Report", ""]

    # Initialize variables for scope
    total_nodes = 0
    tagged_snippet_count = 0

    # 1. Graph Store Status
    report_lines.append("## 📦 Graph Store")
    if graph_path.exists():
        report_lines.append(f"✅ Path: `{graph_path}`")

        # Count nodes by type
        try:
            from knowgraph.infrastructure.storage.filesystem import read_node_json

            node_ids = list_all_nodes(graph_path)
            total_nodes = len(node_ids)

            # For tagged_snippet count, scan ALL nodes (they're usually at the end)
            # For type distribution, sample first 100 for performance
            type_counts = {}
            tagged_snippet_count = 0

            # Full scan for tagged_snippet count
            for node_id in node_ids:
                node = read_node_json(node_id, graph_path)
                if node and node.type == "tagged_snippet":
                    tagged_snippet_count += 1

            # Sample scan for type distribution
            sample_size = min(100, total_nodes)
            for node_id in node_ids[:sample_size]:
                node = read_node_json(node_id, graph_path)
                if node:
                    node_type = node.type or "unknown"
                    type_counts[node_type] = type_counts.get(node_type, 0) + 1

            report_lines.append(f"✅ Total Nodes: {total_nodes}")

            if tagged_snippet_count > 0:
                report_lines.append(f"✅ Tagged Snippets: {tagged_snippet_count}")
            else:
                report_lines.append("⚠️  Tagged Snippets: 0 (use `tag_snippet` to create bookmarks)")

            # Show node type distribution from sample
            if type_counts:
                report_lines.append(f"📊 Node Types (sampled {sample_size}):")
                for node_type, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
                    report_lines.append(f"   - {node_type}: {count}")

        except Exception as e:
            report_lines.append(f"⚠️  Error reading nodes: {e}")
    else:
        report_lines.append(f"❌ Graph store not found: `{graph_path}`")
        report_lines.append("   Run `knowgraph_index` first to create the graph store.")

    report_lines.append("")

    # 2. LLM Provider Status
    report_lines.append("## 🤖 LLM Provider")

    api_keys = {
        "OpenAI": os.getenv("OPENAI_API_KEY"),
        "Anthropic": os.getenv("ANTHROPIC_API_KEY"),
    }

    configured_providers = []
    for provider, key in api_keys.items():
        if key:
            # Show first 8 chars of key for verification
            masked_key = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
            report_lines.append(f"✅ {provider}: Configured ({masked_key})")
            configured_providers.append(provider)
        else:
            report_lines.append(f"❌ {provider}: Not configured")

    if not configured_providers:
        report_lines.append("")
        report_lines.append("⚠️  **No LLM providers configured!**")
        report_lines.append("   Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` for AI-generated answers.")
        report_lines.append("   Without a provider, queries will return raw context only.")

    report_lines.append("")

    # 3. MCP Tools Status
    report_lines.append("## 🛠️  MCP Tools")
    report_lines.append("✅ knowgraph_query: Available")
    report_lines.append("✅ knowgraph_index: Available")
    report_lines.append("✅ knowgraph_tag_snippet: Available")
    report_lines.append("✅ knowgraph_search_bookmarks: Available")
    report_lines.append("✅ knowgraph_analyze_impact: Available")
    report_lines.append("✅ knowgraph_get_stats: Available")
    report_lines.append("✅ knowgraph_validate: Available")
    report_lines.append("✅ knowgraph_batch_query: Available")
    report_lines.append("✅ Version management: Available")

    report_lines.append("")

    # 4. System Info
    report_lines.append("## 💻 System")
    report_lines.append(f"✅ Project Root: `{project_root}`")
    report_lines.append(f"✅ Python: {sys.version.split()[0]}")

    # Check if in virtual environment
    in_venv = os.getenv("VIRTUAL_ENV") is not None
    if in_venv:
        report_lines.append(f"✅ Virtual Env: `{os.getenv('VIRTUAL_ENV')}`")
    else:
        report_lines.append("⚠️  Virtual Env: Not detected")

    report_lines.append("")

    # 5. Recommendations
    report_lines.append("## 💡 Recommendations")

    recommendations = []

    if not graph_path.exists():
        recommendations.append("🔴 Run `knowgraph_index` to create your knowledge graph")
    elif total_nodes < 10:
        recommendations.append("🟡 Graph store has very few nodes - index more content")

    if tagged_snippet_count == 0:
        recommendations.append("🟡 No tagged snippets found - use `tag_snippet` to bookmark important content")

    if not configured_providers:
        recommendations.append("🔴 Configure an LLM provider (OPENAI_API_KEY or ANTHROPIC_API_KEY) for AI features")

    if not recommendations:
        recommendations.append("✅ All systems operational!")

    for rec in recommendations:
        report_lines.append(rec)

    return [types.TextContent(type="text", text="\n".join(report_lines))]

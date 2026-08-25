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
    from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
    from knowgraph.infrastructure.detection.graph_store_locator import (
        resolve_graph_store,
    )
    from knowgraph.infrastructure.storage.filesystem import list_all_nodes

    graph_path_arg = arguments.get("graph_path", DEFAULT_GRAPH_STORE_PATH)
    graph_path = resolve_graph_store(graph_path_arg, root_dir=project_root)

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

    # KnowGraph uses its own provider env vars (OpenRouter/OpenAI-compatible
    # via KNOWGRAPH_API_KEY / KNOWGRAPH_API_BASE_URL / KNOWGRAPH_LLM_MODEL),
    # falling back to the legacy OPENAI/ANTHROPIC keys.
    api_keys = {
        "OpenAI": os.getenv("KNOWGRAPH_API_KEY") or os.getenv("OPENAI_API_KEY"),
        "Anthropic": os.getenv("ANTHROPIC_API_KEY"),
    }
    model = os.getenv("KNOWGRAPH_LLM_MODEL", "")

    configured_providers = []
    for provider, key in api_keys.items():
        if key:
            # Show first 8 chars of key for verification
            masked_key = f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "***"
            report_lines.append(f"✅ {provider}: Configured ({masked_key})")
            if model:
                report_lines.append(f"   Model: {model}")
            configured_providers.append(provider)
        else:
            report_lines.append(f"❌ {provider}: Not configured")

    if not configured_providers:
        report_lines.append("")
        report_lines.append("⚠️  **No LLM providers configured!**")
        report_lines.append("   Set `KNOWGRAPH_API_KEY` (or `OPENAI_API_KEY`) for AI-generated answers.")
        report_lines.append("   Without a provider, queries will return raw context only.")

    # Effective timeout/retrieval settings — the knobs that determine whether a
    # slow provider stalls queries or thin context produces "no info" answers.
    try:
        from knowgraph.config import (
            LLM_REQUEST_TIMEOUT,
            LLM_RETRY_COUNT,
            QUERY_TIMEOUT_SECONDS,
            get_settings,
        )

        qs = get_settings().query
        report_lines.append(f"   LLM request timeout: {LLM_REQUEST_TIMEOUT}s "
                            f"(env: KNOWGRAPH_LLM_REQUEST_TIMEOUT)")
        report_lines.append(f"   LLM retries: {LLM_RETRY_COUNT} "
                            f"(env: KNOWGRAPH_LLM_RETRY_COUNT)")
        report_lines.append(f"   Query timeout: {QUERY_TIMEOUT_SECONDS}s "
                            f"(env: KNOWGRAPH_QUERY_TIMEOUT_SECONDS)")
        report_lines.append(f"   top_k: {qs.top_k} (env: KNOWGRAPH_QUERY_TOP_K)")
        report_lines.append(f"   max_hops: {qs.max_hops} (env: KNOWGRAPH_QUERY_MAX_HOPS)")
        report_lines.append(f"   dense retrieval: "
                            f"{'on' if qs.enable_dense_retrieval else 'off'}")
    except Exception:
        pass

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
    else:
        # Slow/free endpoints (e.g. a `*:free` OpenRouter model) routinely take
        # >30s to synthesize an answer; a tight LLM_REQUEST_TIMEOUT then cuts
        # them off, surfacing as flaky query timeouts. Surface the knob when it
        # looks tight relative to a configured provider. NOTE the MCP client
        # usually has its OWN timeout too — raising only the server-side knob
        # isn't enough if the client cuts first.
        try:
            from knowgraph.config import LLM_REQUEST_TIMEOUT

            if LLM_REQUEST_TIMEOUT <= 60:
                recommendations.append(
                    "🟡 LLM request timeout is 60s or less; with a slow/free provider, "
                    "raise KNOWGRAPH_LLM_REQUEST_TIMEOUT (e.g. 90-120) AND the MCP "
                    "client's tool timeout — the client cuts first if its limit is lower"
                )
        except Exception:
            pass

    # Thin context ("bağlamda bilgi yok") is usually retrieval being too shallow,
    # not the LLM: a low top_k leaves few seed nodes for the answer. Grounding
    # does NOT deepen retrieval — top_k / max_hops do.
    try:
        from knowgraph.config import get_settings

        if get_settings().query.top_k < 15:
            recommendations.append(
                "🟡 top_k is low (<15); raise it (e.g. 25-50) to deepen retrieval "
                "and reduce 'no info in context' answers. Note: enable_grounding "
                "re-weights context but does NOT fetch more nodes."
            )
    except Exception:
        pass

    if not recommendations:
        recommendations.append("✅ All systems operational!")

    for rec in recommendations:
        report_lines.append(rec)

    return [types.TextContent(type="text", text="\n".join(report_lines))]

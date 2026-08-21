import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

import mcp.types as types
from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from pydantic import Field

from knowgraph.adapters.mcp.diagnostic_handler import handle_diagnostic
from knowgraph.adapters.mcp.handlers import (
    # Joern-specific handlers
    handle_analyze_call_graph,
    handle_analyze_conversations,
    handle_analyze_impact,
    handle_batch_query,
    handle_discover_conversations,
    handle_export_cpg,
    handle_find_dead_code,
    handle_generate_cpg,
    handle_get_stats,
    handle_index,
    handle_joern_query,
    handle_query,
    handle_search_bookmarks,
    handle_security_scan,
    handle_tag_snippet,
    handle_validate,
)
from knowgraph.adapters.mcp.utils import get_llm_provider, resolve_graph_path
from knowgraph.adapters.mcp.version_handlers import (
    handle_diff_versions,
    handle_list_versions,
    handle_rollback,
    handle_version_info,
)
from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.shared.versioning import (
    VersionStatus,
    get_current_version,
    register_version,
)

from knowgraph.version import __version__

app = MCPServer(
    "knowgraph-mcp",
    title="KnowGraph MCP",
    description="Code knowledge graph: index source code, answer security/impact/code queries over a semantic graph, and expose graph resources and reusable prompt templates.",
    instructions=(
        "KnowGraph indexes source code (markdown, Git repos, code directories) into a "
        "knowledge graph and answers queries over it. Use knowgraph_index to build a "
        "graph, then knowgraph_query / knowgraph_analyze_impact / knowgraph_security_scan "
        "to interrogate it. Graph data is exposed as resources under knowgraph://graph/."
    ),
    website_url="https://github.com/yunusgungor/knowgraph",
    version=__version__,
)
logger = logging.getLogger(__name__)

# Background LLM-detection task reference, kept alive across the server lifetime
_init_task: asyncio.Task | None = None


# Register API versions on module load
def _register_api_versions():
    """Register all KnowGraph API versions."""
    now = datetime.now()

    # Version 0.7.0 - Previous stable release
    register_version(
        version="0.7.0",
        status=VersionStatus.STABLE,
        release_date=now - timedelta(days=30),
        features=[
            "Basic query support",
            "Graph indexing",
            "Impact analysis",
            "Graph validation",
        ],
    )

    # Version 0.8.0 - Current stable with Joern
    register_version(
        version="0.8.0",
        status=VersionStatus.STABLE,
        release_date=now,
        features=[
            "Joern Code Analysis Integration",
            "Security Scanning",
            "Dead Code Detection",
            "Call Graph Analysis",
            "Daemon Support",
            "Batch query support",
            "Conversation discovery",
        ],
    )
    # Version 1.0.0 - Current stable release
    register_version(
        version="1.0.0",
        status=VersionStatus.STABLE,
        release_date=now,
        features=[
            "Taint Analysis Refinement",
            "Resilience Improvements",
            "Full System Verification",
        ],
    )
    logger.debug(f"Registered API versions, current: {get_current_version()}")


_register_api_versions()

# Cache for detected project root
_PROJECT_ROOT_CACHE: dict[str, Any] = {
    "root": None,
    "timestamp": None,
    "ttl": 3600,  # 1 hour cache
    "llm_detection_done": False,
    "llm_detection_running": False,
}


def _get_cached_project_root() -> Path | None:
    """Get cached project root if still valid."""
    if _PROJECT_ROOT_CACHE["root"] is None:
        return None

    elapsed = time.time() - _PROJECT_ROOT_CACHE["timestamp"]
    if elapsed > _PROJECT_ROOT_CACHE["ttl"]:
        logger.debug("Project root cache expired")
        return None

    logger.debug(f"Using cached project root: {_PROJECT_ROOT_CACHE['root']}")
    return _PROJECT_ROOT_CACHE["root"]


def _cache_project_root(root: Path) -> None:
    """Cache the detected project root."""
    _PROJECT_ROOT_CACHE["root"] = root
    _PROJECT_ROOT_CACHE["timestamp"] = time.time()
    logger.debug(f"Cached project root: {root}")


def _detect_project_root_sync() -> Path:
    """Detect project root synchronously (without LLM).

    Uses fast heuristic methods:
    1. Git repository root
    2. Project marker files
    3. Fallback to cwd

    Note: This provides a quick initial detection.
    Background LLM detection will refine this if needed.
    """
    from knowgraph.infrastructure.detection.project_detector import detect_project_root

    # Use sync detection (no LLM)
    detected = detect_project_root(use_llm=False)
    logger.debug(f"Initial project root detected (sync): {detected}")
    return detected


async def _detect_project_root_with_llm_async(start_path: Path | None = None) -> Path | None:
    """Detect project root using LLM in background.

    This runs after server initialization to refine the project root
    detection using LLM analysis.
    """
    if _PROJECT_ROOT_CACHE.get("llm_detection_running"):
        logger.debug("LLM detection already running, skipping")
        return None

    _PROJECT_ROOT_CACHE["llm_detection_running"] = True

    try:
        from knowgraph.infrastructure.detection.project_detector import (
            detect_project_root_with_llm,
        )

        logger.debug("Starting background LLM-based project root detection...")
        llm_detected = await detect_project_root_with_llm(start_path)

        if llm_detected:
            # Update cache with LLM-detected root
            current_root = _PROJECT_ROOT_CACHE.get("root")
            if current_root != llm_detected:
                logger.info(
                    f"LLM refined project root: {current_root} -> {llm_detected}"
                )
                _cache_project_root(llm_detected)
            else:
                logger.debug(f"LLM confirmed project root: {llm_detected}")
        else:
            logger.debug("LLM detection completed but no better root found")

        _PROJECT_ROOT_CACHE["llm_detection_done"] = True
        return llm_detected

    except Exception as e:
        logger.warning(f"Background LLM detection failed: {e}", exc_info=True)
        return None
    finally:
        _PROJECT_ROOT_CACHE["llm_detection_running"] = False


def _get_project_root() -> Path:
    """Get project root with auto-detection and caching.

    Priority:
    1. Cached detection result
    2. Auto-detection (git root, marker files)
    3. Fallback to current working directory
    """
    # 1. Check cache
    cached_root = _get_cached_project_root()
    if cached_root:
        return cached_root

    # 2. Auto-detect
    detected_root = _detect_project_root_sync()
    _cache_project_root(detected_root)
    return detected_root


# Path to project root for resolving relative paths
# Automatically detected using git root, project markers, or falls back to cwd
# Initially detected synchronously, then refined by LLM in background
# Cached for 1 hour to avoid repeated detection
PROJECT_ROOT = _get_project_root()


async def _initialize_llm_detection():
    """Initialize LLM-based project root detection in background.

    This is called after server initialization to refine the project root
    without blocking the server startup.
    """
    try:
        # Give server time to fully initialize
        await asyncio.sleep(2)

        current_root = _PROJECT_ROOT_CACHE.get("root")
        if current_root:
            await _detect_project_root_with_llm_async(current_root)
    except Exception as e:
        logger.warning(f"Failed to initialize LLM detection: {e}", exc_info=True)


def _join(items: list[types.TextContent]) -> str:
    return "\n".join(item.text for item in items)


@app.tool(description="Retrieve relevant context from the KnowGraph knowledge graph to answer a query.")
async def knowgraph_query(
    query: Annotated[str, Field(description="The natural language query to retrieve context for.")],
    ctx: Context | None = None,
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional, defaults to ./graphstore).")] = None,
    with_explanation: Annotated[bool, Field(description="Include an explanation of how the answer was derived (default: false).")] = False,
    top_k: Annotated[int, Field(description="Number of top results to return (default: 20).")] = 20,
    max_hops: Annotated[int, Field(description="Maximum number of hops for graph traversal (default: 4).")] = 4,
    expand_query: Annotated[bool, Field(description="Uses AI to expand query with synonyms and technical terms (default: false).")] = False,
    max_tokens: Annotated[int, Field(description="Maximum token count for the context window (default: 3000).")] = 3000,
    enable_hierarchical_lifting: Annotated[bool, Field(description="Enable hierarchical context lifting for broader context (default: true).")] = True,
    lift_levels: Annotated[int, Field(description="Number of directory levels to lift context from (default: 2).")] = 2,
) -> str:
    arguments: dict[str, Any] = {
        "query": query,
        "graph_path": graph_path,
        "with_explanation": with_explanation,
        "top_k": top_k,
        "max_hops": max_hops,
        "expand_query": expand_query,
        "max_tokens": max_tokens,
        "enable_hierarchical_lifting": enable_hierarchical_lifting,
        "lift_levels": lift_levels,
    }
    kwargs: dict[str, Any] = {}
    if ctx is not None:
        kwargs["server"] = ctx
    return _join(
        await handle_query(arguments, get_llm_provider(), PROJECT_ROOT, **kwargs)
    )


@app.tool(description="Trigger indexing of markdown files, Git repositories, or code directories.")
async def knowgraph_index(
    ctx: Context | None = None,
    input_path: Annotated[str, Field(description="Path to markdown files, local directory, or Git repository URL (GitHub, GitLab, Bitbucket). `source_path` is accepted as an alias.")] = None,
    output_path: Annotated[str, Field(description="Path to graph storage (optional).")] = None,
    resume: Annotated[bool, Field(description="Resume indexing from checkpoint if interrupted (default: false). Only works for local files.")] = False,
    gc: Annotated[bool, Field(description="Garbage collect deleted nodes during update (default: false).")] = False,
    include_patterns: Annotated[list[str], Field(description="File patterns to include (e.g., ['*.py', '*.md']). Only for repositories and code directories.")] = None,
    exclude_patterns: Annotated[list[str], Field(description="File patterns to exclude (e.g., ['node_modules/*', '*.lock']). Only for repositories and code directories.")] = None,
    access_token: Annotated[str, Field(description="GitHub Personal Access Token for private repositories.")] = None,
) -> str:
    arguments: dict[str, Any] = {
        "input_path": input_path,
        "output_path": output_path,
        "resume": resume,
        "gc": gc,
        "include_patterns": include_patterns,
        "exclude_patterns": exclude_patterns,
        "access_token": access_token,
    }
    kwargs: dict[str, Any] = {}
    if ctx is not None:
        kwargs["server"] = ctx
    return _join(
        await handle_index(arguments, get_llm_provider(), PROJECT_ROOT, **kwargs)
    )


@app.tool(description="Analyze the impact of changing a specific element (code, function, etc.) in the graph.")
async def knowgraph_analyze_impact(
    element: Annotated[str, Field(description="The element (name or query) to analyze impact for.")],
    max_hops: Annotated[int, Field(description="Maximum depth of dependency traversal (default: 4).")] = 4,
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional, defaults to ./graphstore).")] = None,
    mode: Annotated[Literal["semantic", "path"], Field(description="Analysis mode: 'semantic' (concept) or 'path' (file path pattern). Default: semantic.")] = "semantic",
) -> str:
    arguments: dict[str, Any] = {
        "element": element,
        "max_hops": max_hops,
        "graph_path": graph_path,
        "mode": mode,
    }
    return _join(await handle_analyze_impact(arguments, PROJECT_ROOT))


@app.tool(description="Validate the consistency and health of the knowledge graph.")
async def knowgraph_validate(
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional).")] = None,
) -> str:
    arguments: dict[str, Any] = {"graph_path": graph_path}
    return _join(await handle_validate(arguments, PROJECT_ROOT))


@app.tool(description="Get basic statistics about the stored knowledge graph.")
async def knowgraph_get_stats(
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional).")] = None,
) -> str:
    arguments: dict[str, Any] = {"graph_path": graph_path}
    return _join(await handle_get_stats(arguments, PROJECT_ROOT))


@app.tool(description="Auto-discover and index conversations from AI code editors (Antigravity, Cursor, GitHub Copilot). No manual export required!")
async def knowgraph_discover_conversations(
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional, defaults to ./graphstore).")] = None,
    editor: Annotated[Literal["all", "antigravity", "cursor", "github_copilot"], Field(description="Which editor's conversations to index (default: all).")] = "all",
) -> str:
    arguments: dict[str, Any] = {
        "graph_path": graph_path,
        "editor": editor,
    }
    return _join(
        await handle_discover_conversations(
            arguments, get_llm_provider(), PROJECT_ROOT
        )
    )


@app.tool(description="Tag and index an important snippet for later retrieval. Use this to bookmark important AI responses or code examples.")
async def knowgraph_tag_snippet(
    tag: Annotated[str, Field(description="Tag for the snippet (e.g., 'fastapi jwt detayı', 'important config')")],
    snippet: Annotated[str, Field(description="The content to tag and index")],
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional, defaults to ./graphstore).")] = None,
    conversation_id: Annotated[str, Field(description="Optional conversation ID for context")] = None,
    user_question: Annotated[str, Field(description="Optional user question that prompted this response")] = None,
) -> str:
    arguments: dict[str, Any] = {
        "tag": tag,
        "snippet": snippet,
        "graph_path": graph_path,
        "conversation_id": conversation_id,
        "user_question": user_question,
    }
    return _join(await handle_tag_snippet(arguments, PROJECT_ROOT))


@app.tool(description="Execute multiple queries in batch for efficient processing.")
async def knowgraph_batch_query(
    queries: Annotated[list[str], Field(description="List of natural language queries to process.")],
    ctx: Context | None = None,
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional, defaults to ./graphstore).")] = None,
    top_k: Annotated[int, Field(description="Number of top results to return per query (default: 20).")] = 20,
    max_hops: Annotated[int, Field(description="Maximum number of hops for graph traversal (default: 4).")] = 4,
    max_tokens: Annotated[int, Field(description="Maximum token count for the context window (default: 3000).")] = 3000,
    enable_hierarchical_lifting: Annotated[bool, Field(description="Enable hierarchical context lifting for broader context (default: true).")] = True,
    lift_levels: Annotated[int, Field(description="Number of directory levels to lift context from (default: 2).")] = 2,
) -> str:
    arguments: dict[str, Any] = {
        "queries": queries,
        "graph_path": graph_path,
        "top_k": top_k,
        "max_hops": max_hops,
        "max_tokens": max_tokens,
        "enable_hierarchical_lifting": enable_hierarchical_lifting,
        "lift_levels": lift_levels,
    }
    kwargs: dict[str, Any] = {}
    if ctx is not None:
        kwargs["server"] = ctx
    return _join(
        await handle_batch_query(arguments, get_llm_provider(), PROJECT_ROOT, **kwargs)
    )


@app.tool(description="Search tagged bookmarks/snippets with semantic matching. Find previously saved code snippets, examples, and important notes.")
async def knowgraph_search_bookmarks(
    query: Annotated[str, Field(description="Search query for finding bookmarks")],
    top_k: Annotated[int, Field(description="Number of bookmarks to return (default: 10)")] = 10,
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional, defaults to ./graphstore).")] = None,
) -> str:
    arguments: dict[str, Any] = {
        "query": query,
        "top_k": top_k,
        "graph_path": graph_path,
    }
    return _join(await handle_search_bookmarks(arguments, PROJECT_ROOT))


@app.tool(description="Analyze conversation patterns for topics and trends. Discover what topics are trending, when they were discussed, and knowledge evolution over time.")
async def knowgraph_analyze_conversations(
    topic: Annotated[str, Field(description="Optional specific topic to analyze (omit for trending topics)")] = None,
    time_window_days: Annotated[int, Field(description="Number of days to analyze (default: 7)")] = 7,
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional, defaults to ./graphstore).")] = None,
) -> str:
    arguments: dict[str, Any] = {
        "topic": topic,
        "time_window_days": time_window_days,
        "graph_path": graph_path,
    }
    return _join(await handle_analyze_conversations(arguments, PROJECT_ROOT))


@app.tool(description="List all versions in the knowledge graph history.")
async def knowgraph_list_versions(
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional, defaults to ./graphstore).")] = None,
    limit: Annotated[int, Field(description="Maximum number of versions to return (default: 50)")] = 50,
) -> str:
    arguments: dict[str, Any] = {
        "graph_path": graph_path,
        "limit": limit,
    }
    return _join(await handle_list_versions(arguments, PROJECT_ROOT))


@app.tool(description="Get detailed information about a specific version.")
async def knowgraph_version_info(
    version_id: Annotated[str, Field(description="Version identifier (e.g., 'v1', 'v2', 'v3')")],
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional, defaults to ./graphstore).")] = None,
) -> str:
    arguments: dict[str, Any] = {
        "version_id": version_id,
        "graph_path": graph_path,
    }
    return _join(await handle_version_info(arguments, PROJECT_ROOT))


@app.tool(description="Compare two versions and show differences in nodes, edges, and files.")
async def knowgraph_diff_versions(
    version1: Annotated[str, Field(description="First version ID (e.g., 'v1')")],
    version2: Annotated[str, Field(description="Second version ID (e.g., 'v3')")],
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional, defaults to ./graphstore).")] = None,
) -> str:
    arguments: dict[str, Any] = {
        "version1": version1,
        "version2": version2,
        "graph_path": graph_path,
    }
    return _join(await handle_diff_versions(arguments, PROJECT_ROOT))


@app.tool(description="Rollback manifest to a previous version (metadata only). Creates backup and requires confirmation.")
async def knowgraph_rollback(
    version_id: Annotated[str, Field(description="Version to rollback to (e.g., 'v3')")],
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional, defaults to ./graphstore).")] = None,
    create_backup: Annotated[bool, Field(description="Create backup before rollback (default: true)")] = True,
    force: Annotated[bool, Field(description="Skip validation checks (default: false)")] = False,
) -> str:
    arguments: dict[str, Any] = {
        "version_id": version_id,
        "graph_path": graph_path,
        "create_backup": create_backup,
        "force": force,
    }
    return _join(await handle_rollback(arguments, PROJECT_ROOT))


@app.tool(description="Run diagnostic checks on the KnowGraph system. Check graph store status, LLM provider configuration, and get recommendations.")
async def knowgraph_diagnostic(
    graph_path: Annotated[str, Field(description="Path to the graph storage directory (optional, defaults to ./graphstore).")] = None,
) -> str:
    arguments: dict[str, Any] = {"graph_path": graph_path}
    return _join(await handle_diagnostic(arguments, PROJECT_ROOT))


@app.tool(description="Execute native Joern DSL queries for advanced code analysis. Use predefined templates or custom queries.")
async def knowgraph_joern_query(
    cpg_path: Annotated[str, Field(description="Path to CPG binary file (required).")],
    query: Annotated[str, Field(description="Native Joern DSL query string (e.g., 'cpg.method.name.l').")] = None,
    query_name: Annotated[str, Field(description="Use predefined query template (e.g., 'find_sql_injections', 'find_buffer_overflows').")] = None,
    timeout: Annotated[int, Field(description="Query timeout in seconds (default: 60).")] = 60,
) -> str:
    arguments: dict[str, Any] = {
        "cpg_path": cpg_path,
        "query": query,
        "query_name": query_name,
        "timeout": timeout,
    }
    return _join(await handle_joern_query(arguments, PROJECT_ROOT))


@app.tool(description="Run security policy validation with 10 predefined CWE-mapped rules. Detect vulnerabilities like SQL injection, XSS, buffer overflows, etc. Auto-detects CPG from graph_path if not explicitly provided.")
async def knowgraph_security_scan(
    cpg_path: Annotated[str, Field(description="Path to CPG binary file (optional if graph_path is provided).")] = None,
    severity_filter: Annotated[Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"], Field(description="Minimum severity level for violations (default: MEDIUM).")] = "MEDIUM",
    policy_names: Annotated[list[str], Field(description="Specific policies to run (e.g., ['buffer_overflow', 'sql_injection']). Omit to run all.")] = None,
    graph_path: Annotated[str, Field(description="Path to graph storage for automatic CPG detection (optional, defaults to ./graphstore).")] = None,
) -> str:
    arguments: dict[str, Any] = {
        "cpg_path": cpg_path,
        "severity_filter": severity_filter,
        "policy_names": policy_names,
        "graph_path": graph_path,
    }
    return _join(await handle_security_scan(arguments, PROJECT_ROOT))


@app.tool(description="Detect unreachable methods using dominance analysis. Find methods that have no callers (potential dead code).")
async def knowgraph_find_dead_code(
    cpg_path: Annotated[str, Field(description="Path to CPG binary file (optional if graph_path is provided).")] = None,
    include_internal: Annotated[bool, Field(description="Include internal methods starting with underscore (default: false).")] = False,
    graph_path: Annotated[str, Field(description="Path to graph storage for automatic CPG detection (optional).")] = None,
) -> str:
    arguments: dict[str, Any] = {
        "cpg_path": cpg_path,
        "include_internal": include_internal,
        "graph_path": graph_path,
    }
    return _join(await handle_find_dead_code(arguments, PROJECT_ROOT))


@app.tool(description="Analyze call graph structure and relationships. Supports validation, recursive call detection, and call chain analysis.")
async def knowgraph_analyze_call_graph(
    cpg_path: Annotated[str, Field(description="Path to CPG binary file (optional if graph_path is provided).")] = None,
    analysis_type: Annotated[Literal["validate", "recursive", "call_chain"], Field(description="Type of analysis: 'validate' (health check), 'recursive' (find recursion), 'call_chain' (paths between methods).")] = None,
    method_name: Annotated[str, Field(description="Source method name (required for call_chain analysis).")] = None,
    target_method: Annotated[str, Field(description="Target method name (required for call_chain analysis).")] = None,
    graph_path: Annotated[str, Field(description="Path to graph storage for automatic CPG detection (optional).")] = None,
) -> str:
    arguments: dict[str, Any] = {
        "cpg_path": cpg_path,
        "analysis_type": analysis_type,
        "method_name": method_name,
        "target_method": target_method,
        "graph_path": graph_path,
    }
    return _join(await handle_analyze_call_graph(arguments, PROJECT_ROOT))


@app.tool(description="Export CPG to various formats for visualization and CI/CD integration. Supports JSON, SARIF, Neo4j, DOT, and GraphML.")
async def knowgraph_export_cpg(
    cpg_path: Annotated[str, Field(description="Path to source CPG binary file (required).")],
    output_path: Annotated[str, Field(description="Export destination path (required).")],
    format: Annotated[Literal["json", "sarif", "neo4j", "dot", "graphml"], Field(description="Export format (default: json).")] = "json",
    graph_path: Annotated[str, Field(description="Path to graph storage for automatic CPG detection (optional).")] = None,
) -> str:
    arguments: dict[str, Any] = {
        "cpg_path": cpg_path,
        "output_path": output_path,
        "format": format,
        "graph_path": graph_path,
    }
    return _join(await handle_export_cpg(arguments, PROJECT_ROOT))


@app.tool(description="Generate Code Property Graph dynamically from source code. Automatically detects language and generates CPG for analysis.")
async def knowgraph_generate_cpg(
    source_path: Annotated[str, Field(description="Path to source code directory or file (required). `input_path` is accepted as an alias.")] = None,
    language: Annotated[str, Field(description="Language hint for CPG generation (optional, auto-detected if not provided).")] = None,
    timeout: Annotated[int, Field(description="Generation timeout in seconds (default: 600).")] = 600,
) -> str:
    arguments: dict[str, Any] = {
        "source_path": source_path,
        "language": language,
        "timeout": timeout,
    }
    return _join(await handle_generate_cpg(arguments, PROJECT_ROOT))


@app.resource(
    "knowgraph://default/manifest",
    name="Default Graph Manifest",
    description="Manifest file of the default knowledge graph",
    mime_type="application/json",
)
async def _manifest() -> str:
    graph_path = resolve_graph_path(DEFAULT_GRAPH_STORE_PATH, PROJECT_ROOT)
    manifest_path = graph_path / "metadata" / "manifest.json"
    if not manifest_path.exists():
        raise ValueError("Manifest not found")
    return manifest_path.read_text(encoding="utf-8")


@app.resource(
    "knowgraph://graph/{graph_path}/manifest",
    name="Graph Manifest",
    description="Manifest (stats) of a specific knowledge graph at graph_path.",
    mime_type="application/json",
)
async def _graph_manifest(graph_path: str) -> str:
    resolved = resolve_graph_path(graph_path, PROJECT_ROOT)
    manifest_path = resolved / "metadata" / "manifest.json"
    if not manifest_path.exists():
        raise ValueError(f"Manifest not found at {resolved}")
    return manifest_path.read_text(encoding="utf-8")


@app.resource(
    "knowgraph://graph/{graph_path}/nodes",
    name="Graph Nodes",
    description="All node IDs stored in a specific knowledge graph at graph_path.",
    mime_type="application/json",
)
async def _graph_nodes(graph_path: str) -> str:
    from knowgraph.infrastructure.storage.filesystem import list_all_nodes

    resolved = resolve_graph_path(graph_path, PROJECT_ROOT)
    return json.dumps(list_all_nodes(resolved), ensure_ascii=False)


@app.resource(
    "knowgraph://graph/{graph_path}/stats",
    name="Graph Statistics",
    description="Live node/edge counts for a specific knowledge graph at graph_path.",
    mime_type="application/json",
)
async def _graph_stats(graph_path: str) -> str:
    import os

    resolved = resolve_graph_path(graph_path, PROJECT_ROOT)
    nodes_dir = resolved / "nodes"
    edges_file = resolved / "edges" / "edges.jsonl"
    stats = {
        "graph_path": str(resolved),
        "node_count": len(list(nodes_dir.glob("*.json"))) if nodes_dir.exists() else 0,
        "edge_count": (
            sum(1 for _ in open(edges_file, encoding="utf-8")) if edges_file.exists() else 0
        ),
    }
    return json.dumps(stats, ensure_ascii=False)


@app.prompt(
    name="graph_summary",
    title="Knowledge Graph Summary",
    description="Summarize what is stored in a KnowGraph instance.",
)
async def graph_summary_prompt(graph_path: str | None = None) -> str:
    """Produce a prompt that summarizes the default (or given) graph."""
    gp = graph_path or DEFAULT_GRAPH_STORE_PATH
    return (
        f"Summarize the knowledge graph at {gp}: list its overall size, the main "
        f"entities/topics stored, and anything notable. Read the manifest resource "
        f"knowgraph://graph/{gp}/manifest first."
    )


@app.prompt(
    name="security_scan",
    title="Security Scan Guide",
    description="Guide the agent to run a security scan and interpret results.",
)
async def security_scan_prompt(graph_path: str | None = None) -> str:
    """Produce a prompt that drives a security scan."""
    gp = graph_path or DEFAULT_GRAPH_STORE_PATH
    return (
        f"Run a security scan on the knowledge graph at {gp} using "
        f"knowgraph_security_scan, then summarize the vulnerabilities found by "
        f"severity and explain the highest-confidence findings."
    )


@app.prompt(
    name="impact_analysis",
    title="Impact Analysis Guide",
    description="Guide the agent to analyze the impact of changing an element.",
)
async def impact_analysis_prompt(element: str, graph_path: str | None = None) -> str:
    """Produce a prompt that drives impact analysis."""
    gp = graph_path or DEFAULT_GRAPH_STORE_PATH
    return (
        f"Analyze the impact of changing '{element}' in the knowledge graph at {gp} "
        f"using knowgraph_analyze_impact, and explain which files/nodes would be affected."
    )


def _configure_logging():
    """Configure logging to suppress noisy libraries."""
    # Suppress mcp internal logs
    logging.getLogger("mcp").setLevel(logging.WARNING)
    # Suppress httpx/httpcore logs (used by OpenAI/LLM providers)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


async def main() -> None:
    _configure_logging()
    # Start background LLM detection task (fire and forget); keep a module ref
    # to avoid the task being garbage-collected.
    global _init_task
    _init_task = asyncio.create_task(_initialize_llm_detection())

    transport = os.getenv("KNOWGRAPH_MCP_TRANSPORT", "stdio").lower()
    if transport == "http":
        # Streamable HTTP transport (e.g. for remote MCP access).
        host = os.getenv("KNOWGRAPH_MCP_HOST", "127.0.0.1")
        port = int(os.getenv("KNOWGRAPH_MCP_PORT", "8000"))
        await app.run_streamable_http_async(host=host, port=port)
    elif transport == "sse":
        host = os.getenv("KNOWGRAPH_MCP_HOST", "127.0.0.1")
        port = int(os.getenv("KNOWGRAPH_MCP_PORT", "8000"))
        await app.run_sse_async(host=host, port=port)
    else:
        await app.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())

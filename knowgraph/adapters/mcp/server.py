import asyncio
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

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

app = Server("knowgraph-mcp")
logger = logging.getLogger(__name__)


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


@app.call_tool()  # type: ignore
async def call_tool(name: str, arguments: Any) -> list[types.TextContent]:
    """Route tool calls to appropriate handlers."""
    provider = get_llm_provider(app)

    if name == "knowgraph_query":
        return await handle_query(arguments, provider, PROJECT_ROOT, server=app)

    elif name == "knowgraph_index":
        return await handle_index(arguments, provider, PROJECT_ROOT, server=app)

    elif name == "knowgraph_analyze_impact":
        return await handle_analyze_impact(arguments, PROJECT_ROOT)

    elif name == "knowgraph_validate":
        return await handle_validate(arguments, PROJECT_ROOT)

    elif name == "knowgraph_get_stats":
        return await handle_get_stats(arguments, PROJECT_ROOT)

    elif name == "knowgraph_discover_conversations":
        return await handle_discover_conversations(arguments, provider, PROJECT_ROOT)

    elif name == "knowgraph_tag_snippet":
        return await handle_tag_snippet(arguments, PROJECT_ROOT)

    elif name == "knowgraph_batch_query":
        return await handle_batch_query(arguments, provider, PROJECT_ROOT)

    elif name == "knowgraph_search_bookmarks":
        return await handle_search_bookmarks(arguments, PROJECT_ROOT)

    elif name == "knowgraph_analyze_conversations":
        return await handle_analyze_conversations(arguments, PROJECT_ROOT)

    elif name == "knowgraph_list_versions":
        return await handle_list_versions(arguments, PROJECT_ROOT)

    elif name == "knowgraph_version_info":
        return await handle_version_info(arguments, PROJECT_ROOT)

    elif name == "knowgraph_diff_versions":
        return await handle_diff_versions(arguments, PROJECT_ROOT)

    elif name == "knowgraph_rollback":
        return await handle_rollback(arguments, PROJECT_ROOT)

    elif name == "knowgraph_diagnostic":
        return await handle_diagnostic(arguments, PROJECT_ROOT)

    # Joern-specific tools
    elif name == "knowgraph_joern_query":
        return await handle_joern_query(arguments, PROJECT_ROOT)

    elif name == "knowgraph_security_scan":
        return await handle_security_scan(arguments, PROJECT_ROOT)

    elif name == "knowgraph_find_dead_code":
        return await handle_find_dead_code(arguments, PROJECT_ROOT)

    elif name == "knowgraph_analyze_call_graph":
        return await handle_analyze_call_graph(arguments, PROJECT_ROOT)

    elif name == "knowgraph_export_cpg":
        return await handle_export_cpg(arguments, PROJECT_ROOT)

    elif name == "knowgraph_generate_cpg":
        return await handle_generate_cpg(arguments, PROJECT_ROOT)

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
async def read_resource(uri: Any) -> str | bytes:
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
            description="Trigger indexing of markdown files, Git repositories, or code directories.",
            inputSchema={
                "type": "object",
                "properties": {
                    "input_path": {
                        "type": "string",
                        "description": "Path to markdown files, local directory, or Git repository URL (GitHub, GitLab, Bitbucket).",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to graph storage (optional).",
                    },
                    "resume": {
                        "type": "boolean",
                        "description": "Resume indexing from checkpoint if interrupted (default: false). Only works for local files.",
                    },
                    "gc": {
                        "type": "boolean",
                        "description": "Garbage collect deleted nodes during update (default: false).",
                    },
                    "include_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File patterns to include (e.g., ['*.py', '*.md']). Only for repositories and code directories.",
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "File patterns to exclude (e.g., ['node_modules/*', '*.lock']). Only for repositories and code directories.",
                    },
                    "access_token": {
                        "type": "string",
                        "description": "GitHub Personal Access Token for private repositories.",
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
        types.Tool(
            name="knowgraph_discover_conversations",
            description="Auto-discover and index conversations from AI code editors (Antigravity, Cursor, GitHub Copilot). No manual export required!",
            inputSchema={
                "type": "object",
                "properties": {
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional, defaults to ./graphstore).",
                    },
                    "editor": {
                        "type": "string",
                        "enum": ["all", "antigravity", "cursor", "github_copilot"],
                        "description": "Which editor's conversations to index (default: all).",
                    },
                },
            },
        ),
        types.Tool(
            name="knowgraph_tag_snippet",
            description="Tag and index an important snippet for later retrieval. Use this to bookmark important AI responses or code examples.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tag": {
                        "type": "string",
                        "description": "Tag for the snippet (e.g., 'fastapi jwt detayı', 'important config')",
                    },
                    "snippet": {
                        "type": "string",
                        "description": "The content to tag and index",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional, defaults to ./graphstore).",
                    },
                    "conversation_id": {
                        "type": "string",
                        "description": "Optional conversation ID for context",
                    },
                    "user_question": {
                        "type": "string",
                        "description": "Optional user question that prompted this response",
                    },
                },
                "required": ["tag", "snippet"],
            },
        ),
        types.Tool(
            name="knowgraph_search_bookmarks",
            description="Search tagged bookmarks/snippets with semantic matching. Find previously saved code snippets, examples, and important notes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query for finding bookmarks",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of bookmarks to return (default: 10)",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional, defaults to ./graphstore).",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="knowgraph_analyze_conversations",
            description="Analyze conversation patterns for topics and trends. Discover what topics are trending, when they were discussed, and knowledge evolution over time.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Optional specific topic to analyze (omit for trending topics)",
                    },
                    "time_window_days": {
                        "type": "integer",
                        "description": "Number of days to analyze (default: 7)",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional, defaults to ./graphstore).",
                    },
                },
            },
        ),
        types.Tool(
            name="knowgraph_list_versions",
            description="List all versions in the knowledge graph history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional, defaults to ./graphstore).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of versions to return (default: 50)",
                    },
                },
            },
        ),
        types.Tool(
            name="knowgraph_version_info",
            description="Get detailed information about a specific version.",
            inputSchema={
                "type": "object",
                "properties": {
                    "version_id": {
                        "type": "string",
                        "description": "Version identifier (e.g., 'v1', 'v2', 'v3')",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional, defaults to ./graphstore).",
                    },
                },
                "required": ["version_id"],
            },
        ),
        types.Tool(
            name="knowgraph_diff_versions",
            description="Compare two versions and show differences in nodes, edges, and files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "version1": {
                        "type": "string",
                        "description": "First version ID (e.g., 'v1')",
                    },
                    "version2": {
                        "type": "string",
                        "description": "Second version ID (e.g., 'v3')",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional, defaults to ./graphstore).",
                    },
                },
                "required": ["version1", "version2"],
            },
        ),
        types.Tool(
            name="knowgraph_rollback",
            description="Rollback manifest to a previous version (metadata only). Creates backup and requires confirmation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "version_id": {
                        "type": "string",
                        "description": "Version to rollback to (e.g., 'v3')",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional, defaults to ./graphstore).",
                    },
                    "create_backup": {
                        "type": "boolean",
                        "description": "Create backup before rollback (default: true)",
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Skip validation checks (default: false)",
                    },
                },
                "required": ["version_id"],
            },
        ),
        types.Tool(
            name="knowgraph_diagnostic",
            description="Run diagnostic checks on the KnowGraph system. Check graph store status, LLM provider configuration, and get recommendations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "graph_path": {
                        "type": "string",
                        "description": "Path to the graph storage directory (optional, defaults to ./graphstore).",
                    },
                },
            },
        ),
        # Joern-specific tools
        types.Tool(
            name="knowgraph_joern_query",
            description="Execute native Joern DSL queries for advanced code analysis. Use predefined templates or custom queries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cpg_path": {
                        "type": "string",
                        "description": "Path to CPG binary file (required).",
                    },
                    "query": {
                        "type": "string",
                        "description": "Native Joern DSL query string (e.g., 'cpg.method.name.l').",
                    },
                    "query_name": {
                        "type": "string",
                        "description": "Use predefined query template (e.g., 'find_sql_injections', 'find_buffer_overflows').",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Query timeout in seconds (default: 60).",
                    },
                },
                "required": ["cpg_path"],
            },
        ),
        types.Tool(
            name="knowgraph_security_scan",
            description="Run security policy validation with 10 predefined CWE-mapped rules. Detect vulnerabilities like SQL injection, XSS, buffer overflows, etc. Auto-detects CPG from graph_path if not explicitly provided.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cpg_path": {
                        "type": "string",
                        "description": "Path to CPG binary file (optional if graph_path is provided).",
                    },
                    "severity_filter": {
                        "type": "string",
                        "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                        "description": "Minimum severity level for violations (default: MEDIUM).",
                    },
                    "policy_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific policies to run (e.g., ['buffer_overflow', 'sql_injection']). Omit to run all.",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to graph storage for automatic CPG detection (optional, defaults to ./graphstore).",
                    },
                },
            },
        ),
        types.Tool(
            name="knowgraph_find_dead_code",
            description="Detect unreachable methods using dominance analysis. Find methods that have no callers (potential dead code).",
            inputSchema={
                "type": "object",
                "properties": {
                    "cpg_path": {
                        "type": "string",
                        "description": "Path to CPG binary file (optional if graph_path is provided).",
                    },
                    "include_internal": {
                        "type": "boolean",
                        "description": "Include internal methods starting with underscore (default: false).",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to graph storage for automatic CPG detection (optional).",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="knowgraph_analyze_call_graph",
            description="Analyze call graph structure and relationships. Supports validation, recursive call detection, and call chain analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cpg_path": {
                        "type": "string",
                        "description": "Path to CPG binary file (optional if graph_path is provided).",
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["validate", "recursive", "call_chain"],
                        "description": "Type of analysis: 'validate' (health check), 'recursive' (find recursion), 'call_chain' (paths between methods).",
                    },
                    "method_name": {
                        "type": "string",
                        "description": "Source method name (required for call_chain analysis).",
                    },
                    "target_method": {
                        "type": "string",
                        "description": "Target method name (required for call_chain analysis).",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to graph storage for automatic CPG detection (optional).",
                    },
                },
                "required": [],
            },
        ),
        types.Tool(
            name="knowgraph_export_cpg",
            description="Export CPG to various formats for visualization and CI/CD integration. Supports JSON, SARIF, Neo4j, DOT, and GraphML.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cpg_path": {
                        "type": "string",
                        "description": "Path to source CPG binary file (required).",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Export destination path (required).",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json", "sarif", "neo4j", "dot", "graphml"],
                        "description": "Export format (default: json).",
                    },
                    "graph_path": {
                        "type": "string",
                        "description": "Path to graph storage for automatic CPG detection (optional).",
                    },
                },
                "required": ["cpg_path", "output_path"],
            },
        ),
        types.Tool(
            name="knowgraph_generate_cpg",
            description="Generate Code Property Graph dynamically from source code. Automatically detects language and generates CPG for analysis.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "Path to source code directory or file (required).",
                    },
                    "language": {
                        "type": "string",
                        "description": "Language hint for CPG generation (optional, auto-detected if not provided).",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Generation timeout in seconds (default: 600).",
                    },
                },
                "required": ["source_path"],
            },
        ),
    ]


def _configure_logging():
    """Configure logging to suppress noisy libraries."""
    # Suppress mcp internal logs
    logging.getLogger("mcp").setLevel(logging.WARNING)
    # Suppress httpx/httpcore logs (used by OpenAI/LLM providers)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


async def main() -> None:
    _configure_logging()
    async with stdio_server() as (read_stream, write_stream):
        # Start background LLM detection task (fire and forget)
        _ = asyncio.create_task(_initialize_llm_detection())  # noqa: RUF006

        init_options = app.create_initialization_options()
        await app.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
# Version management tools added below

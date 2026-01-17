import asyncio
import contextlib
import logging
import sys
from collections.abc import Awaitable, Callable
from dataclasses import replace
from pathlib import Path

import mcp.types as types

from knowgraph.adapters.cli.index_command import run_index
from knowgraph.application.evolution.incremental_update import (
    apply_incremental_update,
    detect_delta,
)
from knowgraph.application.indexing.graph_builder import normalize_markdown_content
from knowgraph.application.querying.impact_analyzer import analyze_impact_by_path
from knowgraph.domain.intelligence.provider import IntelligenceProvider
from knowgraph.infrastructure.parsing.hasher import hash_content
from knowgraph.infrastructure.storage.filesystem import (
    list_all_nodes,
    read_all_edges,
    read_node_json,
)
from knowgraph.infrastructure.storage.manifest import read_manifest
from knowgraph.shared.security import validate_path

logger = logging.getLogger(__name__)


async def index_graph(
    input_path: str,
    graph_path: Path,
    provider: IntelligenceProvider,
    resume_mode: bool,
    gc: bool,
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    access_token: str | None = None,
    progress_callback: Callable[[str, int, int, str], Awaitable[None]] | None = None,
) -> list[types.TextContent]:
    """Handles the indexing process for markdown files, repositories, and code directories.

    Supports:
    - Local markdown files and directories
    - Git repository URLs (GitHub, GitLab, Bitbucket)
    - Code directories (with automatic conversion to markdown)
    - Resume mode and incremental updates

    Args:
        progress_callback: Optional callback for progress updates (stage, current, total, message)
    """
    from knowgraph.infrastructure.parsing.repo_ingestor import detect_source_type

    # Detect source type first
    source_type = detect_source_type(input_path)

    # For repositories and remote code directories, skip path validation
    if source_type == "repository":
        # No path validation needed for URLs
        pass
    else:
        # Validate local paths
        try:
            input_path_obj = validate_path(input_path, must_exist=True, must_be_file=False)
            input_path = str(input_path_obj)
        except Exception as e:
            return [types.TextContent(type="text", text=f"Error: Invalid input path: {e}")]

    # Redirect stdout to stderr to prevent polluting the MCP JSON-RPC stream
    with contextlib.redirect_stdout(sys.stderr):
        try:
            graph_path / "metadata" / "manifest.json"

            if resume_mode and source_type != "repository":
                # Resume mode only works for local files/directories
                manifest = read_manifest(graph_path)
                if not manifest:
                    return [
                        types.TextContent(
                            type="text", text="Error: Cannot resume, no manifest found."
                        )
                    ]

                # Only perform single-file delta optimization if input is a file
                if Path(input_path).is_file():
                    with open(input_path, encoding="utf-8") as file:
                        new_content = file.read()

                    delta = detect_delta(manifest, new_content, str(input_path), graph_path)

                    if delta.added_nodes:
                        # Enrich nodes with AI
                        tasks = []
                        for node in delta.added_nodes:
                            tasks.append(provider.extract_entities(node.content))

                        results = await asyncio.gather(*tasks)
                        enriched_nodes = []
                        for node, entities in zip(delta.added_nodes, results):
                            new_node = replace(
                                node, metadata={"entities": [e._asdict() for e in entities]}
                            )
                            enriched_nodes.append(new_node)

                        delta.added_nodes = enriched_nodes
                        delta.modified_nodes = enriched_nodes

                    normalized_content = normalize_markdown_content(new_content)
                    file_hash = hash_content(normalized_content)

                    apply_incremental_update(
                        delta, manifest, file_hash, str(input_path), graph_path, gc_orphans=True
                    )

                    return [
                        types.TextContent(
                            type="text",
                            text=f"Successfully resumed/updated indexing for {input_path}.",
                        )
                    ]

            # Use run_index for all cases - it has efficient hash checking
            # and only processes changed files at manifest level
            await run_index(
                input_path=input_path,
                output_path=str(graph_path),
                progress_callback=progress_callback,
                provider=provider,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                access_token=access_token,
            )

            # NEW: Code analysis integration
            try:
                from knowgraph.infrastructure.indexing.code_index_integration import (
                    CodeIndexIntegration,
                )

                # Only run on local directories (not remote repos)
                input_path_obj = Path(input_path)
                if input_path_obj.exists() and input_path_obj.is_dir():
                    logger.info("Running code analysis...")
                    integration = CodeIndexIntegration()
                    code_results = integration.process_code_directory(
                        input_path_obj,
                        graph_path
                    )

                    # Log results
                    if code_results["cpg_generated"]:
                        logger.info(f"Code analysis: {code_results['entities_extracted']} entities extracted")
                    else:
                        logger.info(f"Code analysis: {code_results.get('code_files_detected', 0)} files detected (no CPG)")

            except Exception as e:
                # Don't fail indexing if code analysis fails
                logger.warning(f"Code analysis failed (non-fatal): {e}")

            source_desc = (
                "repository"
                if source_type == "repository"
                else (
                    "code directory"
                    if source_type == "directory"
                    else (
                        "conversation history"
                        if source_type == "conversation"
                        else "markdown files"
                    )
                )
            )

            return [
                types.TextContent(
                    type="text",
                    text=f"Successfully indexed/updated {source_desc}: {input_path}.",
                ),
            ]

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            return [
                types.TextContent(type="text", text=f"Error indexing: {e!s}\n\n{error_details}")
            ]


def analyze_path_impact_report(
    element: str, graph_path: Path, max_hops: int
) -> list[types.TextContent]:
    """Performs impact analysis based on file paths."""
    with contextlib.redirect_stdout(sys.stderr):
        all_node_ids = list_all_nodes(graph_path)
        all_nodes = []
        for node_id in all_node_ids:
            node = read_node_json(node_id, graph_path)
            if node:
                all_nodes.append(node)

        all_edges = read_all_edges(graph_path)

        results = analyze_impact_by_path(element, all_nodes, all_edges, max_depth=max_hops)
        if not results:
            return [
                types.TextContent(
                    type="text", text=f"No nodes found matching path pattern: {element}"
                )
            ]

        # Format output
        output = f"Impact Analysis for Path Pattern: {element}\n" + "─" * 40 + "\n"
        for res in results:
            output += f"\n{res.get_summary()}"
            if res.dependent_nodes:
                output += "Dependent Files:\n"
                seen = set()
                for n in res.dependent_nodes[:20]:
                    if n.path not in seen:
                        output += f"  - {n.path}\n"
                        seen.add(n.path)
                if len(res.dependent_nodes) > 20:
                    output += f"  ... and {len(res.dependent_nodes)-20} more\n"
            else:
                output += "No dependencies found.\n"

        return [types.TextContent(type="text", text=output)]


def security_scan_vulnerabilities(
    graph_path: Path,
    scan_type: str = "all",
) -> list[types.TextContent]:
    """Scan codebase for security vulnerabilities using taint analysis.

    Uses Joern's data_flow edges to trace user input from sources to dangerous sinks.

    Args:
    ----
        graph_path: Path to knowledge graph
        scan_type: Type of vulnerabilities to scan for:
            - "all": Scan for all vulnerability types
            - "sql_injection": SQL injection only
            - "xss": Cross-site scripting only
            - "command_injection": Command injection only
            - "path_traversal": Path traversal only
            - "xxe": XML external entity only
            - "ssrf": Server-side request forgery only

    Returns:
    -------
        List of TextContent with scan results

    """
    from knowgraph.application.security.taint_analyzer import TaintAnalyzer
    from knowgraph.application.security.vulnerability_patterns import (
        VULNERABILITY_PATTERNS,
        VulnerabilityType,
    )

    with contextlib.redirect_stdout(sys.stderr):
        try:
            analyzer = TaintAnalyzer(str(graph_path))

            # Determine which vulnerabilities to scan for
            if scan_type == "all":
                results = analyzer.find_vulnerabilities()
            else:
                # Map scan type to vulnerability type
                scan_type_map = {
                    "sql_injection": VulnerabilityType.SQL_INJECTION,
                    "xss": VulnerabilityType.XSS,
                    "command_injection": VulnerabilityType.COMMAND_INJECTION,
                    "path_traversal": VulnerabilityType.PATH_TRAVERSAL,
                    "xxe": VulnerabilityType.XXE,
                    "ssrf": VulnerabilityType.SSRF,
                }

                vuln_type = scan_type_map.get(scan_type)
                if not vuln_type:
                    return [
                        types.TextContent(
                            type="text",
                            text=f"Invalid scan type: {scan_type}. Valid options: {', '.join(scan_type_map.keys())}, all",
                        )
                    ]

                pattern = VULNERABILITY_PATTERNS[vuln_type]
                results = analyzer.find_vulnerabilities(
                    source_patterns=pattern.sources,
                    sink_patterns=pattern.sinks,
                )

            # Format output
            if not results:
                output = "🔒 Security Scan Complete - No vulnerabilities detected!\n"
                output += f"Scan type: {scan_type}\n"
                return [types.TextContent(type="text", text=output)]

            # Group by severity
            critical = [v for v in results if v.severity == "Critical"]
            high = [v for v in results if v.severity == "High"]
            medium = [v for v in results if v.severity == "Medium"]
            low = [v for v in results if v.severity == "Low"]

            # Build report
            output = f"⚠️  Security Scan Results ({scan_type})\n"
            output += "=" * 60 + "\n\n"
            output += f"Total Vulnerabilities: {len(results)}\n"
            output += f"  🔴 Critical: {len(critical)}\n"
            output += f"  🟠 High: {len(high)}\n"
            output += f"  🟡 Medium: {len(medium)}\n"
            output += f"  🟢 Low: {len(low)}\n\n"

            # Show top 10 most critical vulnerabilities
            sorted_results = sorted(
                results,
                key=lambda v: (
                    {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}.get(v.severity, 4),
                    -v.confidence,
                ),
            )

            output += "Top Vulnerabilities:\n"
            output += "-" * 60 + "\n"

            for idx, vuln in enumerate(sorted_results[:10], 1):
                severity_icon = {
                    "Critical": "🔴",
                    "High": "🟠",
                    "Medium": "🟡",
                    "Low": "🟢",
                }.get(vuln.severity, "⚪")

                output += f"\n{idx}. {severity_icon} {vuln.vulnerability_type} "
                output += f"(Confidence: {vuln.confidence:.0%})\n"
                output += f"   Source: {vuln.source_description[:80]}...\n"
                output += f"   Sink: {vuln.sink_description[:80]}...\n"
                output += f"   Path length: {len(vuln.path)} hops\n"

            if len(results) > 10:
                output += f"\n... and {len(results) - 10} more vulnerabilities\n"

            output += "\n" + "=" * 60 + "\n"
            output += "💡 Recommendation: Review these findings and apply appropriate fixes.\n"
            output += "   Use prepared statements, input validation, and output escaping.\n"

            return [types.TextContent(type="text", text=output)]

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            return [
                types.TextContent(
                    type="text",
                    text=f"Error during security scan: {e!s}\n\n{error_details}",
                )
            ]

"""Joern integration MCP tool handlers."""

from pathlib import Path
from typing import Any

import mcp.types as types

from knowgraph.infrastructure.detection.graph_store_locator import resolve_graph_store
from knowgraph.shared.refactoring import build_error_response


async def handle_joern_query(arguments: dict[str, Any], PROJECT_ROOT: Path) -> list[types.TextContent]:
    """Execute native Joern DSL query.

    Allows AI assistants to run custom Joern queries or use predefined templates.
    """
    try:
        from knowgraph.application.security.joern_query_templates import (
            JoernQueryTemplate,
            get_vulnerability_query,
        )
        from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

        # Required parameters
        cpg_path_str = arguments.get("cpg_path")
        if not cpg_path_str:
            return [types.TextContent(type="text", text="Error: cpg_path is required")]

        cpg_path = Path(cpg_path_str)
        if not cpg_path.exists():
            return [types.TextContent(type="text", text=f"Error: CPG not found at {cpg_path}")]

        # Get query (direct or template)
        query = arguments.get("query")
        query_name = arguments.get("query_name")

        if query_name:
            # Use predefined template - try enum first, then vulnerability queries
            try:
                template = JoernQueryTemplate[query_name.upper()]
                query = template.value
            except KeyError:
                # Try vulnerability query
                query = get_vulnerability_query(query_name)
                if not query:
                    available = ", ".join([t.name.lower() for t in JoernQueryTemplate])
                    return [types.TextContent(
                        type="text",
                        text=f"Error: Unknown query template '{query_name}'. Available: {available}, sql_injection, buffer_overflow, command_injection, dangerous_functions"
                    )]
        elif not query:
            return [types.TextContent(type="text", text="Error: Either 'query' or 'query_name' is required")]

        timeout = arguments.get("timeout", 60)

        # Execute query
        executor = JoernQueryExecutor()
        result = executor.execute_query(cpg_path, query, timeout=timeout)

        # Format output
        output = "🔍 Joern Query Executed\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"**Query**: {query[:100]}{'...' if len(query) > 100 else ''}\n"
        output += f"**Results**: {result.node_count} nodes\n"
        output += f"**Execution Time**: {result.execution_time_ms:.0f}ms\n\n"

        if result.results:
            output += "**Results**:\n"
            for idx, res in enumerate(result.results[:20], 1):  # Limit to 20
                output += f"{idx}. {res}\n"
            if len(result.results) > 20:
                output += f"\n... and {len(result.results) - 20} more results\n"
        else:
            output += "_No results found_\n"

        return [types.TextContent(type="text", text=output)]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=build_error_response(e, "Error executing Joern query")
        )]


async def handle_security_scan(arguments: dict[str, Any], PROJECT_ROOT: Path) -> list[types.TextContent]:
    """Run security policy validation with CWE-mapped rules.

    Scans code for 10 predefined security vulnerabilities. When ``scan_type``
    is provided, runs the flow-based taint analysis (TaintAnalyzer) instead of
    the policy-engine scan.
    """
    try:
        # Flow-based taint scan (optional). Requires graph_path to locate the CPG.
        scan_type = arguments.get("scan_type")
        if scan_type:
            graph_path_arg = arguments.get("graph_path") or arguments.get("graph_store")
            if not graph_path_arg:
                return [types.TextContent(
                    type="text",
                    text="Error: 'graph_path' is required when 'scan_type' is set"
                )]
            from knowgraph.adapters.mcp.methods import security_scan_vulnerabilities

            graph_path = resolve_graph_store(graph_path_arg, root_dir=PROJECT_ROOT)
            return security_scan_vulnerabilities(graph_path, scan_type=scan_type)

        from knowgraph.application.security.policy_engine import PolicyEngine, Severity
        from knowgraph.infrastructure.indexing.cpg_metadata import get_cpg_path

        # Try to get CPG path from arguments or graph metadata
        cpg_path_str = arguments.get("cpg_path")
        graph_path_arg = arguments.get("graph_path")

        if not cpg_path_str and graph_path_arg:
            # Try to auto-detect CPG from graph metadata
            graph_path = resolve_graph_store(graph_path_arg, root_dir=PROJECT_ROOT)
            cpg_path = get_cpg_path(graph_path)

            if not cpg_path:
                return [types.TextContent(
                    type="text",
                    text="Error: No CPG found. Either provide 'cpg_path' or run 'knowgraph_index' first to generate CPG."
                )]
        elif cpg_path_str:
            cpg_path = Path(cpg_path_str)
            if not cpg_path.exists():
                return [types.TextContent(type="text", text=f"Error: CPG not found at {cpg_path}")]
        else:
            return [types.TextContent(
                type="text",
                text="Error: Either 'cpg_path' or 'graph_path' is required"
            )]

        # Optional parameters
        severity_filter_str = arguments.get("severity_filter", "MEDIUM")
        try:
            severity_filter = Severity[severity_filter_str.upper()]
        except KeyError:
            severity_filter = Severity.MEDIUM

        # Filter policies by name if policy_names is provided
        policy_names = arguments.get("policy_names")
        engine = PolicyEngine()
        policies_to_check = None

        if policy_names:
            # Match loosely: "sql_injection" should find "NoSQLInjection". Normalize
            # both sides to lowercase with punctuation stripped and check containment.
            def _norm(name: str) -> str:
                return "".join(ch for ch in name.lower() if ch.isalnum())

            wanted = [_norm(n) for n in policy_names]
            policies_to_check = [
                p for p in engine.policies
                if any(w in _norm(p.name) or _norm(p.name) in w for w in wanted)
            ]
            if not policies_to_check:
                return [types.TextContent(
                    type="text",
                    text=(
                        f"Error: None of the specified policies found: {policy_names}. "
                        f"Available: {', '.join(p.name for p in engine.policies)}"
                    )
                )]

        # Run policy validation
        violations = engine.validate_policies(
            cpg_path,
            policies=policies_to_check,
            severity_filter=severity_filter
        )

        # Format output
        output = "🔒 Security Policy Scan\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"**Scanned**: {cpg_path.name}\n"
        output += f"**Severity Filter**: {severity_filter.name}\n"
        output += f"**Violations Found**: {len(violations)}\n\n"

        if violations:
            # Group by severity - PolicyViolation is a dataclass, use attribute access
            by_severity = {}
            for v in violations:
                sev = v.severity  # attribute access
                if sev not in by_severity:
                    by_severity[sev] = []
                by_severity[sev].append(v)

            for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
                if sev in by_severity:
                    icon = "🔴" if sev == Severity.CRITICAL else "🟠" if sev == Severity.HIGH else "🟡" if sev == Severity.MEDIUM else "⚪"
                    output += f"\n{icon} **{sev.name}** ({len(by_severity[sev])} findings):\n"
                    for v in by_severity[sev][:5]:  # Limit to 5 per severity
                        # Access dataclass attributes
                        policy_name = v.policy.name if v.policy else "Unknown"
                        # Policy stores the CWE id in cwe_id, not cwe. It already
                        # includes the "CWE-" prefix, so only add it when absent.
                        cwe_id = (v.policy.cwe_id if v.policy and v.policy.cwe_id else "")
                        cwe_label = f"CWE-{cwe_id}" if cwe_id and not cwe_id.startswith("CWE") else cwe_id
                        output += f"  - **{policy_name}** ({cwe_label or 'CWE-N/A'})\n"
                        output += f"    Location: {v.location}\n"
                        if v.policy and hasattr(v.policy, "recommendation"):
                            output += f"    💡 {v.policy.recommendation}\n"
                    if len(by_severity[sev]) > 5:
                        output += f"  _... and {len(by_severity[sev]) - 5} more {sev.name} findings_\n"
        else:
            output += "✅ **No violations found!** Code passes all security policies.\n"

        return [types.TextContent(type="text", text=output)]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=build_error_response(e, "Error running security scan")
        )]


async def handle_find_dead_code(arguments: dict[str, Any], PROJECT_ROOT: Path) -> list[types.TextContent]:
    """Detect unreachable methods using dominance analysis.

    Finds methods that have no callers (potential dead code).
    """
    try:
        from knowgraph.application.analysis.dominance_analyzer import DominanceAnalyzer

        # Required parameters
        from knowgraph.infrastructure.indexing.cpg_metadata import get_cpg_path

        # Try to get CPG path from arguments or graph metadata
        cpg_path_str = arguments.get("cpg_path")
        graph_path_arg = arguments.get("graph_path")

        if not cpg_path_str and graph_path_arg:
            # Try to auto-detect CPG from graph metadata
            graph_path = resolve_graph_store(graph_path_arg, root_dir=PROJECT_ROOT)
            cpg_path = get_cpg_path(graph_path)

            if not cpg_path:
                return [types.TextContent(
                    type="text",
                    text="Error: No CPG found. Either provide 'cpg_path' or run 'knowgraph_index' first to generate CPG."
                )]
        elif cpg_path_str:
            cpg_path = Path(cpg_path_str)
            if not cpg_path.exists():
                return [types.TextContent(type="text", text=f"Error: CPG not found at {cpg_path}")]
        else:
            return [types.TextContent(
                type="text",
                text="Error: Either 'cpg_path' or 'graph_path' is required"
            )]

        # Optional parameters
        include_internal = arguments.get("include_internal", False)

        # Find dead code
        analyzer = DominanceAnalyzer()
        dead_methods = analyzer.find_dead_code(cpg_path)

        # Filter internal methods if needed
        if not include_internal:
            dead_methods = [m for m in dead_methods if not m.get("name", "").startswith("_")]

        # Format output
        output = "💀 Dead Code Detection\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"**Scanned**: {cpg_path.name}\n"
        output += f"**Dead Methods Found**: {len(dead_methods)}\n\n"

        if dead_methods:
            output += "**Unreachable Methods** (no callers):\n\n"
            for idx, method in enumerate(dead_methods[:15], 1):  # Limit to 15
                name = method.get("name", "Unknown")
                signature = method.get("signature", "")
                file_loc = method.get("filename", method.get("file", "Location not available"))

                output += f"{idx}. `{name}`\n"
                if signature:
                    output += f"   Signature: `{signature}`\n"
                output += f"   Location: {file_loc}\n\n"

            if len(dead_methods) > 15:
                output += f"_... and {len(dead_methods) - 15} more dead methods_\n\n"

            output += "💡 **Recommendations**:\n"
            output += "- Review if these methods are truly unused\n"
            output += "- Check for dynamic calls or reflection\n"
            output += "- Consider removing to reduce code complexity\n"
        else:
            output += "✅ **No dead code detected!** All methods have callers.\n"

        return [types.TextContent(type="text", text=output)]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=build_error_response(e, "Error finding dead code")
        )]


async def handle_analyze_call_graph(arguments: dict[str, Any], PROJECT_ROOT: Path) -> list[types.TextContent]:
    """Analyze call graph structure and relationships.

    Supports validation, recursive call detection, and call chain analysis.
    """
    try:
        from knowgraph.application.analysis.call_graph_analyzer import CallGraphAnalyzer

        # Required parameters
        cpg_path_str = arguments.get("cpg_path")
        analysis_type = arguments.get("analysis_type", "validate")
        graph_path_arg = arguments.get("graph_path")

        if not cpg_path_str and graph_path_arg:
            from knowgraph.infrastructure.indexing.cpg_metadata import get_cpg_path
            # Try to auto-detect CPG from graph metadata
            graph_path = resolve_graph_store(graph_path_arg, root_dir=PROJECT_ROOT)
            cpg_path = get_cpg_path(graph_path)

            if not cpg_path:
                return [types.TextContent(
                    type="text",
                    text="Error: No CPG found. Either provide 'cpg_path' or run 'knowgraph_index' first to generate CPG."
                )]
        elif cpg_path_str:
            cpg_path = Path(cpg_path_str)
            if not cpg_path.exists():
                return [types.TextContent(type="text", text=f"Error: CPG not found at {cpg_path}")]
        else:
            return [types.TextContent(
                type="text",
                text="Error: Either 'cpg_path' or 'graph_path' is required"
            )]

        analyzer = CallGraphAnalyzer()

        # Route to appropriate analysis
        if analysis_type == "validate":
            result = analyzer.validate_call_graph(cpg_path)

            output = "📊 Call Graph Validation\n"
            output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            output += f"**Status**: {'✅ Valid' if result.is_valid else '❌ Invalid'}\n"
            output += f"**Methods**: {result.total_methods}\n"  # Changed from "Total Methods:"
            output += f"**Call Edges**: {result.call_edges}\n"
            output += f"**Entry Points**: {len(result.entry_points)}\n"
            output += f"**Leaf Methods**: {len(result.leaf_methods)}\n\n"

            if result.entry_points:
                output += "**Entry Points** (no callers):\n"
                for ep in result.entry_points[:10]:
                    output += f"  - `{ep}`\n"
                if len(result.entry_points) > 10:
                    output += f"  _... and {len(result.entry_points) - 10} more_\n"

            return [types.TextContent(type="text", text=output)]

        elif analysis_type == "recursive":
            recursive_methods = analyzer.find_recursive_calls(cpg_path)

            output = "🔄 Recursive Call Detection\n"
            output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            output += f"**Recursive Methods Found**: {len(recursive_methods)}\n\n"

            if recursive_methods:
                for idx, method in enumerate(recursive_methods[:10], 1):
                    name = method.get("name", "Unknown")
                    rec_type = method.get("recursion_type", "direct")
                    output += f"{idx}. `{name}` ({rec_type} recursion)\n"

                if len(recursive_methods) > 10:
                    output += f"\n_... and {len(recursive_methods) - 10} more_\n"
            else:
                output += "✅ No recursive methods detected.\n"

            return [types.TextContent(type="text", text=output)]

        elif analysis_type == "call_chain":
            method_name = arguments.get("method_name")
            target_method = arguments.get("target_method")
            max_depth = arguments.get("max_depth", 5)

            if not method_name or not target_method:
                return [types.TextContent(
                    type="text",
                    text="Error: For call_chain analysis, both 'method_name' and 'target_method' are required"
                )]

            # Use the correct method name: find_call_chains (plural)
            chains = analyzer.find_call_chains(
                cpg_path,
                from_pattern=method_name,
                to_pattern=target_method,
                max_depth=max_depth
            )

            output = "🔗 Call Chain Analysis\n"
            output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            output += f"**From**: `{method_name}`\n"
            output += f"**To**: `{target_method}`\n"
            output += f"**Max Depth**: {max_depth}\n"
            output += f"**Paths Found**: {len(chains)}\n\n"

            if chains:
                for idx, chain in enumerate(chains[:5], 1):
                    output += f"**Path {idx}**: {' → '.join(f'`{m}`' for m in chain)}\n"

                if len(chains) > 5:
                    output += f"\n_... and {len(chains) - 5} more paths_\n"
            else:
                output += "❌ No call path found between these methods.\n"
                output += "\n💡 **Tip**: Try increasing max_depth or check if methods exist in CPG\n"

            return [types.TextContent(type="text", text=output)]


        else:
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown analysis_type '{analysis_type}'. Use 'validate', 'recursive', or 'call_chain'"
            )]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=build_error_response(e, "Error analyzing call graph")
        )]


async def handle_export_cpg(arguments: dict[str, Any], PROJECT_ROOT: Path) -> list[types.TextContent]:
    """Export CPG to various formats for visualization and CI/CD.

    Supports JSON, SARIF, Neo4j, DOT, and GraphML formats.
    """
    try:
        from knowgraph.core.joern import ExportFormat, JoernProvider
        from knowgraph.infrastructure.indexing.cpg_metadata import get_cpg_path

        # Required parameters
        cpg_path_str = arguments.get("cpg_path")
        output_path_str = arguments.get("output_path")
        format_str = arguments.get("format", "json")
        graph_path_arg = arguments.get("graph_path")

        if not cpg_path_str and graph_path_arg:
            # Try to auto-detect CPG from graph metadata
            graph_path = resolve_graph_store(graph_path_arg, root_dir=PROJECT_ROOT)
            cpg_path = get_cpg_path(graph_path)

            if not cpg_path:
                return [types.TextContent(
                    type="text",
                    text="Error: No CPG found. Either provide 'cpg_path' or run 'knowgraph_index' first to generate CPG."
                )]
        elif cpg_path_str:
            cpg_path = Path(cpg_path_str)
            if not cpg_path.exists():
                return [types.TextContent(type="text", text=f"Error: CPG not found at {cpg_path}")]
        else:
            return [types.TextContent(
                type="text",
                text="Error: Either 'cpg_path' or 'graph_path' is required"
            )]

        if not output_path_str:
            return [types.TextContent(type="text", text="Error: output_path is required")]

        output_path = Path(output_path_str)

        # Parse format
        try:
            export_format = ExportFormat[format_str.upper()]
        except KeyError:
            available = ", ".join([f.name.lower() for f in ExportFormat])
            return [types.TextContent(
                type="text",
                text=f"Error: Unknown format '{format_str}'. Available: {available}"
            )]

        # Export CPG with correct parameter order
        provider = JoernProvider()
        result_path = provider.export_cpg(cpg_path, export_format, output_path)  # Fixed order

        # Format output
        output = "💾 CPG Export Complete\n"  # Changed from "Successful"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"**Format**: {export_format.value.upper()}\n"
        output += f"**Source CPG**: {cpg_path}\n"
        output += f"**Exported To**: {result_path}\n\n"

        # Add format-specific info
        if export_format == ExportFormat.JSON:
            output += "📄 **JSON Format**:\n"
            output += "- Structured CPG data\n"
            output += "- Use for custom processing pipelines\n"
        elif export_format == ExportFormat.SARIF:
            output += "🔍 **SARIF Format**:\n"
            output += "- Static Analysis Results Interchange Format\n"
            output += "- Integrate with CI/CD tools\n"
        elif export_format == ExportFormat.NEO4J:
            output += "🗂️ **Neo4j Format**:\n"
            output += "- Import into Neo4j graph database\n"
            output += "- Run Cypher queries\n"
        elif export_format == ExportFormat.DOT:
            output += "🎨 **DOT Format**:\n"
            output += "- Graphviz visualization\n"
            output += "- Generate diagrams with `dot` command\n"
        elif export_format == ExportFormat.GRAPHML:
            output += "📊 **GraphML Format**:\n"
            output += "- XML-based graph format\n"
            output += "- Full metadata preserved\n"

        return [types.TextContent(type="text", text=output)]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=build_error_response(e, "Error exporting CPG")
        )]


async def handle_generate_cpg(arguments: dict[str, Any], PROJECT_ROOT: Path) -> list[types.TextContent]:
    """Generate Code Property Graph dynamically from source code.

    Allows AI assistants to generate CPGs on-the-fly without manual setup.
    """
    try:
        from knowgraph.core.joern import JoernProvider

        # Required parameters. Accept `input_path` as a backward-compatible
        # alias so callers can use the same argument name as knowgraph_index.
        source_path_str = arguments.get("source_path") or arguments.get("input_path")
        if not source_path_str:
            return [types.TextContent(type="text", text="Error: source_path is required")]

        source_path = Path(source_path_str)
        if not source_path.exists():
            return [types.TextContent(type="text", text=f"Error: Source path not found: {source_path}")]

        # Optional parameters
        language = arguments.get("language")  # Auto-detected if None
        timeout = arguments.get("timeout", 600)

        # Initialize Joern provider
        try:
            provider = JoernProvider()
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"Error: Joern not found. Run: knowgraph-setup-joern\n{e}"
            )]

        # Generate CPG
        output = "📦 Generating Code Property Graph\n"
        output += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        output += f"**Source**: {source_path}\n"
        if language:
            output += f"**Language**: {language}\n"
        output += f"**Timeout**: {timeout}s\n\n"
        output += "⏳ Generating CPG (this may take a while)...\n\n"

        try:
            cpg_path = provider.generate_cpg(
                repo_path=source_path,
                language=language,
                timeout=timeout
            )

            output += "✅ **CPG Generated Successfully!**\n\n"
            output += f"**CPG Path**: `{cpg_path}`\n\n"
            output += "💡 **Next Steps**:\n"
            output += "- Use `knowgraph_joern_query` to query the CPG\n"
            output += "- Use `knowgraph_security_scan` to find vulnerabilities\n"
            output += "- Use `knowgraph_find_dead_code` to detect unused code\n"
            output += "- Use `knowgraph_analyze_call_graph` to analyze call relationships\n"
            output += "- Use `knowgraph_export_cpg` to export in various formats\n"

            # Get CPG stats
            if cpg_path.exists():
                size_mb = cpg_path.stat().st_size / (1024 * 1024)
                output += f"\n📊 **CPG Size**: {size_mb:.2f} MB\n"

            return [types.TextContent(type="text", text=output)]

        except Exception as e:
            error_output = output
            error_output += "\n❌ **CPG Generation Failed**\n\n"
            error_output += f"Error: {e!s}\n\n"
            error_output += "💡 **Troubleshooting**:\n"
            error_output += "- Ensure Joern is installed: `knowgraph-setup-joern`\n"
            error_output += "- Check if source path contains supported code files\n"
            error_output += "- Try increasing timeout if source is large\n"
            return [types.TextContent(type="text", text=error_output)]

    except Exception as e:
        return [types.TextContent(
            type="text",
            text=build_error_response(e, "Error generating CPG")
        )]
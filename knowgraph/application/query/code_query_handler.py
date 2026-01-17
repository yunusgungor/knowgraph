"""Code query handler for routing to Joern analysis tools.

This module maps natural language code queries to appropriate Joern tools
and executes them, returning formatted results.
"""

import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CodeQueryHandler:
    """Handle code-specific queries using Joern tools."""

    # Pattern to tool mapping
    QUERY_PATTERNS = {
        # Security vulnerabilities
        r"(vulnerability|vulnerabilities|secure|security|injection|xss|exploit|güvenlik|açık)": "security_scan",

        # Dead code detection
        r"(dead code|unused|unreachable|kullanılmayan)": "find_dead_code",

        # Call graph analysis (general)
        r"(call graph|dependency|dependencies|bağımlı)": "analyze_call_graph",

        # Recursion analysis
        r"(recursion|recursive|loop|cycle|özyineleme|döngü)": "analyze_recursion",

        # Impact/Caller analysis
        r"(who calls|callers of|usage of|references to|kim çağırıyor|kullanımı)": "analyze_impact",

        # Call Chain analysis
        r"(chain|path from|calls between|zincir|yol)": "analyze_chain",

        # Method/function search (generic)

        # Method/function search (generic)
        r"(show|list|find|get).*(function|method|class|fonksiyon|metot)": "joern_query",
    }

    def __init__(self, graph_path: Path):
        """Initialize code query handler.

        Args:
            graph_path: Path to graph storage
        """
        self.graph_path = graph_path
        self.cpg_path = None

    async def handle(self, query: str) -> dict:
        """Handle a code query and return results.

        Args:
            query: User's natural language query

        Returns:
            Dictionary with results and metadata
        """
        # Get CPG path from graph metadata
        from knowgraph.infrastructure.indexing.cpg_metadata import get_cpg_path

        cpg_path = get_cpg_path(self.graph_path)

        if not cpg_path:
            return {
                "success": False,
                "tool": None,
                "message": "No CPG available. Index a code directory first.",
                "cpg_available": False,
                "results": []
            }

        # Determine which Joern tool to use
        tool = self._match_tool(query)

        if not tool:
            return {
                "success": False,
                "tool": None,
                "message": "Could not determine appropriate code analysis tool",
                "cpg_available": True,
                "results": []
            }

        logger.info(f"Executing {tool} for query: {query}")

        # Execute the appropriate Joern tool
        try:
            results = await self._execute_tool(tool, cpg_path, query)

            return {
                "success": True,
                "tool": tool,
                "message": f"Executed {tool} successfully",
                "query": query,
                "cpg_available": True,
                "results": results
            }

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "success": False,
                "tool": tool,
                "message": f"Execution failed: {e!s}",
                "cpg_available": True,
                "results": []
            }

    async def _execute_tool(self, tool: str, cpg_path: Path, query: str) -> list:
        """Execute a Joern tool and return results.

        Args:
            tool: Tool name
            cpg_path: Path to CPG
            query: Original query

        Returns:
            List of results
        """
        from knowgraph.core.joern import JoernProvider
        from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

        provider = JoernProvider()

        if tool == "security_scan":
            # Run security scan
            scan_results = provider.run_security_scan(cpg_path)
            return self._format_security_results(scan_results)

        elif tool == "find_dead_code":
            # Find dead code
            dead_code = provider.find_dead_code(cpg_path)
            return self._format_dead_code_results(dead_code)

        elif tool == "analyze_call_graph":
            # Analyze call graph
            analysis = provider.analyze_call_graph(cpg_path, "validate")
            return self._format_call_graph_results(analysis)

        elif tool == "joern_query":
            # Generic method search
            executor = JoernQueryExecutor(Path(provider.joern_path))
            result = executor.execute_query(cpg_path, "cpg.method.name.l", timeout=30)
            return result.results if result else []

        elif tool == "analyze_recursion":
            # Recursion detection
            analysis = provider.analyze_call_graph(cpg_path, "recursive")
            return self._format_recursion_results(analysis)

        elif tool == "analyze_impact":
            # Impact/Caller analysis
            # Extract method name from query
            method_name = self._extract_method_name(query, ["who calls", "callers of", "usage of", "references to", "kim çağırıyor", "kullanımı"])
            if not method_name:
                return [{"error": "Could not extract method name"}]
            
            result = provider.analyze_method_callers(cpg_path, method_name)
            return self._format_impact_results(result)

        elif tool == "analyze_chain":
            # Call chain analysis
            source, target = self._extract_chain_params(query)
            if not source or not target:
                return [{"error": "Could not extract source and target methods"}]
                
            chains = provider.find_call_chains(cpg_path, source, target)
            return self._format_chain_results(chains, source, target)

        else:
            return []

    def _format_security_results(self, results: dict) -> list:
        """Format security scan results."""
        if not results or not results.get("violations"):
            return []

        formatted = []
        for violation in results.get("violations", [])[:20]:
            formatted.append({
                "type": "security_vulnerability",
                "severity": violation.get("severity", "UNKNOWN"),
                "rule": violation.get("rule_name", "Unknown"),
                "message": violation.get("message", "No details")
            })

        return formatted

    def _format_dead_code_results(self, results: dict) -> list:
        """Format dead code detection results."""
        if not results or not results.get("unreachable_methods"):
            return []

        methods = results.get("unreachable_methods", [])
        return [{"method": m, "reason": "No callers found"} for m in methods[:30]]

    def _format_call_graph_results(self, results: dict) -> list:
        """Format call graph analysis results."""
        if not results:
            return []

        return [{"analysis": "call_graph", "result": str(results)}]

    def _format_recursion_results(self, results: dict) -> list:
        """Format recursion analysis results."""
        recursive_methods = results.get("recursive_methods", [])
        if not recursive_methods:
            return []
            
        formatted = []
        for m in recursive_methods:
            formatted.append({
                "type": "recursive_method",
                "method": m.get("name"),
                "line": m.get("line", -1)
            })
        return formatted

    def _format_impact_results(self, results: dict) -> list:
        """Format impact analysis results."""
        if not results:
            return []
            
        return [{
            "type": "impact_analysis",
            "target_method": results.get("method"),
            "callers": results.get("callers", []),
            "count": results.get("caller_count", 0)
        }]

    def _format_chain_results(self, chains: list, source: str, target: str) -> list:
        """Format call chain results."""
        if not chains:
            return []
            
        formatted = []
        for chain in chains:
            formatted.append({
                "type": "call_chain",
                "source": source,
                "target": target,
                "path": " -> ".join(chain)
            })
        return formatted

    def _extract_method_name(self, query: str, prefixes: list[str]) -> str | None:
        """Extract method name from query removing prefixes."""
        lower_query = query.lower()
        for prefix in prefixes:
            if prefix in lower_query:
                # Find the prefix in original case to preserve method casing
                start_idx = lower_query.find(prefix) + len(prefix)
                candidate = query[start_idx:].strip(" ?.")
                # Simple heuristic: take the first word or remaining string
                if " " in candidate:
                     # Check if it looks like "calls to method X"
                     parts = candidate.split()
                     return parts[0]
                return candidate
        return None

    def _extract_chain_params(self, query: str) -> tuple[str | None, str | None]:
        """Extract source and target from chain query."""
        # Simple regex for "from X to Y"
        import re
        match = re.search(r"(from|between)\s+(?P<source>.+?)\s+(to|and)\s+(?P<target>.+)", query, re.IGNORECASE)
        if match:
            return match.group("source").strip(), match.group("target").strip(" ?.")
        return None, None

    def _match_tool(self, query: str) -> Optional[str]:
        """Match query to appropriate Joern tool.

        Args:
            query: User's query

        Returns:
            Tool name or None
        """
        query_lower = query.lower()

        for pattern, tool in self.QUERY_PATTERNS.items():
            if re.search(pattern, query_lower):
                return tool

        # Default: generic method search if has code terms
        code_terms = ["function", "method", "class", "code", "fonksiyon", "metot", "kod"]
        if any(term in query_lower for term in code_terms):
            return "joern_query"

        return None

    def format_results(self, raw_results: dict) -> str:
        """Format code analysis results for user display.

        Args:
            raw_results: Raw results from Joern tool

        Returns:
            Formatted string for display
        """
        if not raw_results.get("success"):
            return f"❌ Code analysis failed: {raw_results.get('message', 'Unknown error')}"

        output = f"🔍 Code Analysis ({raw_results['tool']})\\n"
        output += "=" * 60 + "\\n\\n"

        if not raw_results.get("cpg_available"):
            output += "⚠️ No CPG available for this codebase.\\n"
            output += "Run indexing on a code directory to generate CPG.\\n"
            return output

        # Format based on tool type
        tool = raw_results["tool"]
        results = raw_results.get("results", [])

        if not results:
            output += "No results found.\\n"
            return output

        # Tool-specific formatting
        if tool == "security_scan":
            output += f"Found {len(results)} potential vulnerabilities:\\n\\n"
            for i, vuln in enumerate(results[:10], 1):
                output += f"{i}. {vuln}\\n"

        elif tool == "find_dead_code":
            output += f"Found {len(results)} unused methods:\\n\\n"
            for i, method in enumerate(results[:20], 1):
                output += f"  - {method}\\n"

        elif tool == "analyze_call_graph":
            output += "Call graph analysis results:\\n\\n"
            output += str(results)

            for i, item in enumerate(results[:20], 1):
                output += f"  {i}. {item}\\n"

        elif tool == "analyze_recursion":
            output += f"Found {len(results)} recursive methods:\\n\\n"
            for item in results:
                output += f"  - {item['method']} (Line {item['line']})\\n"

        elif tool == "analyze_impact":
            for item in results:
                output += f"Method '{item['target_method']}' is called by {item['count']} methods:\\n"
                for caller in item['callers']:
                    output += f"  <- {caller}\\n"

        elif tool == "analyze_chain":
            output += f"Found {len(results)} call chains:\\n\\n"
            for i, item in enumerate(results, 1):
                output += f"Chain {i}: {item['path']}\\n"

        else: # joern_query
            output += f"Found {len(results)} matches:\\n\\n"
            for i, item in enumerate(results[:20], 1):
                output += f"  {i}. {item}\\n"

        return output

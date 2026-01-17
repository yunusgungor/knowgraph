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

        # Variable Usage and Slicing (Prioritize 'usage of' for variables)
        r"(usage of|where is|variable|identifier|değişken|nerede)": "find_variable_usages",
        r"(slice|slicing|backwards slice|code affecting|dilimle|etkileyen)": "perform_slicing",

        # Literal/String Search
        r"(literal|hardcoded|string|constant|sabit|metin)": "find_literals",

        # Impact/Caller analysis
        r"(who calls|callers of|references to|kim çağırıyor|kullanımı)": "analyze_impact",

        # Call Chain analysis
        r"(chain|path from|calls between|zincir|yol)": "analyze_chain",

        # Complexity analysis
        r"(complexity|cyclomatic|complex|karmaşıklık|zorluk)": "analyze_complexity",

        # AST inspection
        r"(ast|syntax tree|soyut sözdizimi|ağaç)": "get_ast",

        # Type Hierarchy
        r"(subclasses|superclasses|inherits|extends|derived|hierarchy|alt sınıf|türetilmiş|hiyerarşi)": "get_type_hierarchy",

        # Visual Graphs (CFG, PDG, CDG)
        r"(cfg|control flow|akış grafiği)": "get_cfg",
        r"(pdg|program dependence|bağımlılık grafiği)": "get_pdg",
        r"(cdg|control dependence)": "get_cdg",

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

        elif tool == "analyze_complexity":
            method_name = self._extract_method_name(query, ["complexity of", "complexity for", "karmaşıklık"])
            if not method_name:
                 # Default to wildcards if no specific method named, or better, return error
                 return [{"error": "Could not extract method name for complexity analysis"}]
            result = provider.analyze_complexity(cpg_path, method_name)
            return self._format_complexity_results(result)

        elif tool == "get_ast":
            method_name = self._extract_method_name(query, ["ast of", "ast for", "syntax tree of", "ağacı"])
            if not method_name:
                return [{"error": "Could not extract method name for AST"}]
            result = provider.get_ast(cpg_path, method_name)
            return [{"type": "ast", "data": result}]

        elif tool == "get_type_hierarchy":
            # Reuse method extraction logic but for types
            type_name = self._extract_method_name(query, ["subclasses of", "superclasses of", "hierarchy of", "inherits", "extends", "alt sınıf"])
            if not type_name:
                return [{"error": "Could not extract type name"}]
            result = provider.get_type_hierarchy(cpg_path, type_name)
            return self._format_hierarchy_results(result, type_name)

        elif tool in ["get_cfg", "get_pdg", "get_cdg"]:
            graph_type = tool.split("_")[1].upper() # CFG, PDG, CDG
            method_name = self._extract_method_name(query, [
                f"{graph_type.lower()} of", f"{graph_type.lower()} for", 
                "control flow of", "dependence of", "grafiği"
            ])
            
            if not method_name:
                return [{"error": f"Could not extract method name for {graph_type}"}]
                
            if tool == "get_cfg":
                result = provider.get_cfg(cpg_path, method_name)
            elif tool == "get_pdg":
                result = provider.get_pdg(cpg_path, method_name)
            else:
                result = provider.get_cdg(cpg_path, method_name)
                
                
            return [{"type": "dot_graph", "graph_type": graph_type, "data": result}]

        elif tool == "find_variable_usages":
            var_name = self._extract_method_name(query, ["usage of", "variable", "identifier", "where is", "değişken", "nerede"])
            # Fallback: try to find the last word if regex fails
            if not var_name:
                 var_name = query.split()[-1]
            
            result = provider.find_variable_usages(cpg_path, var_name)
            return self._format_usage_results(result)

        elif tool == "perform_slicing":
            var_name = self._extract_method_name(query, ["slice of", "slice", "backwards slice", "dilimle", "code affecting"])
            if not var_name:
                 var_name = query.split()[-1]
            
            result = provider.perform_slicing(cpg_path, var_name)
            return self._format_slicing_results(result)

        elif tool == "find_literals":
            lit_pattern = self._extract_method_name(query, ["literal containing", "string containing", "hardcoded", "sabit"])
            if not lit_pattern:
                lit_pattern = query.split()[-1]
                
            result = provider.find_literals(cpg_path, lit_pattern)
            return self._format_literal_results(result)

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

        return formatted

    def _format_complexity_results(self, results: dict) -> list:
        if not results or "complexity" not in results:
            return []
        return [{"type": "complexity", "method": item["method"], "score": item["score"]} for item in results["complexity"]]

        return [{
            "type": "hierarchy",
            "base_types": results.get("base", []),
            "derived_types": results.get("derived", [])
        }]

    def _format_usage_results(self, results: dict) -> list:
        if not results.get("usages"):
            return [{"type": "usage", "variable": results.get("variable"), "error": "No usages found"}]
        
        formatted = []
        for usage in results["usages"]:
            formatted.append({
                "type": "usage",
                "variable": results.get("variable"),
                "method": usage["method"],
                "line": usage["line"],
                "filename": usage.get("filename", "unknown")
            })
        return formatted

    def _format_slicing_results(self, results: dict) -> list:
        if not results.get("slice"):
            return [{"type": "slice", "variable": results.get("variable"), "error": "Slice is empty"}]
            
        formatted = []
        for item in results["slice"]:
            formatted.append({
                "type": "slice",
                "variable": results.get("variable"),
                "method": item["method"],
                "line": item["line"],
                "filename": item.get("filename", "unknown"),
                "code": item["code"]
            })
        return formatted

    def _format_literal_results(self, results: dict) -> list:
        if not results.get("literals"):
             return [{"type": "literal", "pattern": results.get("pattern"), "error": "No literals found"}]
        
        formatted = []
        for item in results["literals"]:
            formatted.append({
                "type": "literal",
                "pattern": results.get("pattern"),
                "method": item["method"],
                "line": item["line"],
                "filename": item.get("filename", "unknown"),
                "code": item["code"]
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

            for i, item in enumerate(results, 1):
                output += f"Chain {i}: {item['path']}\\n"

        elif tool == "analyze_complexity":
            output += "Cyclomatic Complexity Results:\\n\\n"
            for item in results:
                score = item.get('score', 0)
                rating = "Low" if score < 5 else "Medium" if score < 10 else "High"
                output += f"Method: {item['method']}\\n"
                output += f"  Score: {score} ({rating})\\n"

        elif tool == "get_ast":
            output += "Abstract Syntax Tree (DOT):\\n\\n"
            # Just show first few lines if too long
            ast_data = results[0].get("data", "")
            if len(ast_data) > 500:
                output += ast_data[:500] + "... (truncated)\\n"
            else:
                output += ast_data + "\\n"

        elif tool == "get_type_hierarchy":
             item = results[0]
             if "error" in item:
                 output += f"Error: {item['error']}\\n"
             else:
                 output += f"Type Hierarchy:\\n"
                 output += f"  Base Types: {', '.join(item['base_types']) or 'None'}\\n"
                 output += f"  Derived Types: {', '.join(item['derived_types']) or 'None'}\\n"

        elif item_type == "dot_graph":
            graph_type = results[0].get("graph_type", "GRAPH")
            output += f"{graph_type} (DOT Format):\\n\\n"
            graph_data = results[0].get("data", "")
            if len(graph_data) > 500:
                output += graph_data[:500] + "... (truncated)\\n"
            else:
                output += graph_data + "\\n"

        elif item_type == "usage":
            if "error" in results[0]:
                 output += f"Error: {results[0]['error']}\\n"
            else:
                var = results[0].get("variable", "unknown")
                output += f"Variable Usage: '{var}'\\n\\n"
                for i, item in enumerate(results, 1):
                    file_info = f" ({item['filename']})" if item.get('filename') != 'unknown' else ""
                    output += f"{i}. {item['method']}:{item['line']}{file_info}\\n"

        elif item_type == "slice":
            if "error" in results[0]:
                 output += f"Error: {results[0]['error']}\\n"
            else:
                var = results[0].get("variable", "unknown")
                output += f"Backwards Slice (Code affecting '{var}'):\\n\\n"
                # Sort by line number for readability
                sorted_results = sorted(results, key=lambda x: x.get('line', 0))
                for item in sorted_results:
                    file_info = f"[{item.get('filename', 'unknown')}] "
                    output += f"{file_info}[{item['method']}:{item['line']}] {item['code']}\\n"

        elif item_type == "literal":
            if "error" in results[0]:
                 output += f"Error: {results[0]['error']}\\n"
            else:
                pattern = results[0].get("pattern", "unknown")
                output += f"Hardcoded Literals matching '{pattern}':\\n\\n"
                for i, item in enumerate(results, 1):
                     file_info = f" ({item.get('filename', 'unknown')})"
                     output += f"{i}. {item['code']} in {item['method']}:{item['line']}{file_info}\\n"

        else: # joern_query
            output += f"Found {len(results)} matches:\\n\\n"
            for i, item in enumerate(results[:20], 1):
                output += f"  {i}. {item}\\n"

        return output

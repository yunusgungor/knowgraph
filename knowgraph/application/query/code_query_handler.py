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
        # Recursion analysis
        r"(recursion|recursive|recursive calls|cycle|özyineleme)": "analyze_recursion",

        # Variable Usage and Slicing (Prioritize 'usage of' for variables)
        r"(usage of|where is|variable|identifier|değişken|nerede)": "find_variable_usages",
        r"(slice|slicing|backwards slice|code affecting|dilimle|etkileyen)": "perform_slicing",

        # Literal/String Search
        r"(literal|hardcoded|string|constant|sabit|metin)": "find_literals",

        # Annotations/Decorators
        r"(annotation|decorator|tagged with|annotated|@|dekoratör|etiket)": "find_annotations",

        # Imports/Dependencies
        r"(import|dependency|library|uses library|bağımlılık|kütüphane)": "find_imports",

        # Control Structures
        r"(loops in|conditions in|if statements|control structures|döngüler|koşullar)": "analyze_structures",

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

        # Visual Graphs (CFG, PDG, CDG, DDG)
        r"(cfg|control flow|akış grafiği)": "get_cfg",
        r"(pdg|program dependence|bağımlılık grafiği)": "get_pdg",
        r"(cdg|control dependence)": "get_cdg",
        r"(ddg|data dependence)": "get_ddg",

        # Method/function search (generic)
        r"(show|list|find|get).*(function|method|class|fonksiyon|metot)": "joern_query",

        # Metadata Lists (Files, Namespaces, Types)
        r"(list files|show files|all files|dosyalar)": "list_files",
        r"(list packages|show packages|namespaces|paketler)": "list_namespaces",
        r"(list types|show types|defined types|tipler)": "list_types",

        # Taint Analysis (Flow)
        r"(flow from|data flow|taint analysis|track data|akışı)": "analyze_taint",

        # Method Internals
        r"(parameters of|args of|arguments of|parametreler)": "get_params",
        r"(locals of|local variables|variables in|yerel değişkenler)": "get_locals",

        # Comments and Tags
        r"(comments|todos|fixmes|yorumlar)": "find_comments",
        r"(list tags|show tags|etiketler)": "list_tags",

        # Raw/Custom Query (Power User)
        r"(run query|execute query|joern script|custom query|raw query|sorgu çalıştır)": "run_custom_query",
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
            # Generic method search with pattern
            # Prioritize composite prefixes to avoid capturing 'function' as the name in 'find function X'
            prefixes = [
                "find function", "find method", "find class", "show function", "show method", 
                "list functions", "list methods", "get function", "search function",
                "find", "show", "list", "get", "search", "ara", "bul", "göster", 
                "function", "method", "class", "fonksiyon", "metot"
            ]
            pattern = self._extract_method_name(query, prefixes)
            if not pattern:
                pattern = query.split()[-1]
            
            result = provider.find_methods(cpg_path, pattern)
            return self._format_generic_results(result)

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
            elif tool == "get_ddg":
                result = provider.get_ddg(cpg_path, method_name)
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

        elif tool == "find_annotations":
            pattern = self._extract_method_name(query, ["annotated with", "tagged with", "decorator", "annotation", "etketli", "@"])
            if not pattern:
                 pattern = query.split()[-1].replace("@", "")
            result = provider.find_annotations(cpg_path, pattern)
            return self._format_annotation_results(result)

        elif tool == "find_imports":
            pattern = self._extract_method_name(query, ["uses library", "imports", "dependency", "bağımlılık"])
            if not pattern:
                 pattern = query.split()[-1]
            result = provider.find_imports(cpg_path, pattern)
            return self._format_import_results(result)

        elif tool == "analyze_structures":
            pattern = self._extract_method_name(query, ["loops in", "conditions in", "structures in", "structures of"])
            if not pattern:
                # Default wildcards if no method specified
                pattern = ".*"
            result = provider.analyze_structures(cpg_path, pattern)
            return self._format_structure_results(result)

        elif tool == "list_files":
            result = provider.list_files(cpg_path)
            # Wrap in list for consistency
            return [{"type": "file_list", "files": result["files"]}]

        elif tool == "list_namespaces":
            result = provider.list_namespaces(cpg_path)
            return [{"type": "namespace_list", "namespaces": result["namespaces"]}]

        elif tool == "list_types":
            result = provider.list_types(cpg_path)
            return [{"type": "type_list", "types": result["types"]}]

        elif tool == "analyze_taint":
            source, sink = self._extract_chain_params(query)
            if not source or not sink:
                 return [{"error": "Could not identify source and sink. Use 'flow from X to Y'"}]
            
            result = provider.analyze_taint_flow(cpg_path, source, sink)
            return [{"type": "taint_flow", "data": result}]

        elif tool == "get_params":
            method = self._extract_method_name(query, ["parameters of", "args of", "arguments of"])
            if not method: method = query.split()[-1]
            result = provider.get_method_params(cpg_path, method)
            return [{"type": "method_params", "data": result}]

        elif tool == "get_locals":
            method = self._extract_method_name(query, ["locals of", "local variables", "variables in"])
            if not method: method = query.split()[-1]
            result = provider.get_method_locals(cpg_path, method)
            return [{"type": "method_locals", "data": result}]

        elif tool == "find_comments":
            pattern = self._extract_method_name(query, ["comments", "todos", "fixmes"])
            if not pattern: pattern = "TODO" # Default to finding TODOs if generic
            result = provider.find_comments(cpg_path, pattern)
            return [{"type": "comment_list", "data": result}]

        elif tool == "list_tags":
            result = provider.list_tags(cpg_path)
            return [{"type": "tag_list", "tags": result["tags"]}]

        elif tool == "run_custom_query":
            # Extract the actual query string. 
            # Expecting "run query cpg.method.name.l" -> extract "cpg.method.name.l"
            # Logic: Split by tool keywords and take the rest
            clean_query = query
            keywords = ["run query", "execute query", "joern script", "custom query", "raw query", "sorgu çalıştır"]
            for kw in keywords:
                if kw in clean_query.lower():
                     # Find index and take substring after
                     idx = clean_query.lower().find(kw) + len(kw)
                     clean_query = clean_query[idx:].strip()
                     break
            
            # Remove potential quotes if user wrapped query in quotes
            if clean_query.startswith('"') and clean_query.endswith('"'):
                clean_query = clean_query[1:-1]
            if clean_query.startswith("'") and clean_query.endswith("'"):
                clean_query = clean_query[1:-1]
                
            result = provider.run_custom_query(cpg_path, clean_query)
            return [{"type": "custom_query_result", "data": result}]

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

    def _format_annotation_results(self, results: dict) -> list:
        if not results.get("findings"):
            return [{"type": "annotation", "pattern": results.get("pattern"), "error": "No matching annotations found"}]
        
        formatted = []
        for item in results["findings"]:
            formatted.append({
                "type": "annotation",
                "pattern": results.get("pattern"),
                "method": item["method"],
                "filename": item["filename"],
                "annotations": item["annotations"]
            })
        return formatted

    def _format_import_results(self, results: dict) -> list:
        if not results.get("imports"):
             return [{"type": "import", "pattern": results.get("pattern"), "error": "No imports found"}]
        
        formatted = []
        for item in results["imports"]:
            formatted.append({
                "type": "import",
                "pattern": results.get("pattern"),
                "import_stmt": item["import"],
                "filename": item["filename"]
            })
        return formatted

    def _format_structure_results(self, results: dict) -> list:
        if not results.get("structures"):
             return [{"type": "structure", "pattern": results.get("pattern"), "error": "No structures found"}]
        
        formatted = []
        for item in results["structures"]:
            formatted.append({
                "type": "structure",
                "pattern": results.get("pattern"),
                "method": item["method"],
                "filename": item["filename"],
                "loops": item["loops"],
                "ifs": item["ifs"]
            })
        return formatted

    def _extract_method_name(self, query: str, prefixes: list[str]) -> str | None:
        """Extract method name from query removing prefixes."""
        lower_query = query.lower()
        extracted = None
        
        for prefix in prefixes:
            if prefix in lower_query:
                # Find the prefix in original case to preserve method casing
                start_idx = lower_query.find(prefix) + len(prefix)
                candidate = query[start_idx:].strip(" ?.")
                # Simple heuristic: take the first word or remaining string
                if " " in candidate:
                     # Check if it looks like "calls to method X"
                     parts = candidate.split()
                     extracted = parts[0]
                else:
                     extracted = candidate
                break
        
        if extracted:
            # SANITIZATION: Remove quotes to prevent script injection in Scala
            return extracted.replace('"', '').replace("'", "")
            
        return None

    def _format_generic_results(self, results: dict) -> list:
        if not results.get("methods"):
             return [{"type": "generic", "pattern": results.get("pattern"), "error": "No methods found"}]
        
        formatted = []
        for item in results["methods"]:
            formatted.append({
                "type": "generic",
                "pattern": results.get("pattern"),
                "method": item["method"],
                "line": item["line"],
                "filename": item["filename"],
                "signature": item.get("signature", "")
            })
        return formatted

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


        # Tool-specific formatting
        tool = raw_results["tool"]
        results = raw_results.get("results", [])

        if not results:
            output += "No results found.\\n"
            return output

        # Determine result type from first item if available
        item_type = results[0].get("type", "unknown") if results and isinstance(results[0], dict) else "unknown"


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

        elif tool == "joern_query":
             if "error" in results[0]:
                 output += f"Error: {results[0]['error']}\\n"
             else:
                pattern = results[0].get("pattern", "unknown")
                output += f"Methods matching '{pattern}':\\n\\n"
                for i, item in enumerate(results, 1):
                    sig = f" ({item['signature']})" if item.get('signature') else ""
                    output += f"{i}. {item['method']}{sig} - {item['filename']}:{item['line']}\\n"

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

        elif item_type == "annotation":
            if "error" in results[0]:
                 output += f"Error: {results[0]['error']}\\n"
            else:
                pattern = results[0].get("pattern", "unknown")
                output += f"Methods with Annotation '@{pattern}':\\n\\n"
                for i, item in enumerate(results, 1):
                    output += f"{i}. {item['method']} ({item['filename']}) - [{item['annotations']}]\\n"

        elif item_type == "import":
             if "error" in results[0]:
                 output += f"Error: {results[0]['error']}\\n"
             else:
                pattern = results[0].get("pattern", "unknown")
                output += f"Imports matching '{pattern}':\\n\\n"
                for i, item in enumerate(results, 1):
                    output += f"{i}. {item['import_stmt']} (in {item['filename']})\\n"

        elif item_type == "structure":
             if "error" in results[0]:
                 output += f"Error: {results[0]['error']}\\n"
             else:
                output += f"Control Structures Analysis:\\n\\n"
                for i, item in enumerate(results, 1):
                    if item['loops'] > 0 or item['ifs'] > 0:
                        output += f"{i}. {item['method']} ({item['filename']}): Loops={item['loops']}, Ifs={item['ifs']}\\n"

        elif item_type == "file_list":
             files = results[0].get("files", [])
             output += f"Found {len(files)} Source Files:\\n\\n"
             for f in files[:50]: # Limit display
                 output += f"  - {f}\\n"
             if len(files) > 50:
                 output += f"  ... and {len(files)-50} more.\\n"

        elif item_type == "namespace_list":
             ns = results[0].get("namespaces", [])
             output += f"Found {len(ns)} Namespaces/Packages:\\n\\n"
             for n in ns:
                 output += f"  - {n}\\n"

        elif item_type == "type_list":
             types = results[0].get("types", [])
             output += f"Found {len(types)} Defined Types:\\n\\n"
             for t in types[:50]:
                 output += f"  - {t}\\n"
             if len(types) > 50:
                 output += f"  ... and {len(types)-50} more.\\n"

        elif item_type == "taint_flow":
             data = results[0].get("data", {})
             flows = data.get("flows", [])
             if not flows:
                 output += f"No data flow found from '{data.get('source')}' to '{data.get('sink')}'.\\n"
             else:
                 output += f"Found {len(flows)} Data Flow Paths form '{data.get('source')}' to '{data.get('sink')}':\\n\\n"
                 for i, flow in enumerate(flows, 1):
                     output += f"Path #{i}:\\n"
                     for step in flow:
                         output += f"  ⬇️  {step['method']} ({step['filename']}:{step['line']}) - `{step['code']}`\\n"

        elif item_type == "method_params":
             data = results[0].get("data", {})
             params = data.get("params", [])
             output += f"Parameters for method '{data.get('method')}':\\n\\n"
             if not params:
                 output += "  (No parameters)\\n"
             else:
                 for p in params:
                     output += f"  - {p['name']}: {p['type']}\\n"

        elif item_type == "method_locals":
             data = results[0].get("data", {})
             locals_ = data.get("locals", [])
             output += f"Local Variables in method '{data.get('method')}':\\n\\n"
             if not locals_:
                 output += "  (No local variables)\\n"
             else:
                 for l in locals_:
                     output += f"  - {l['name']} ({l['type']})\\n"

        elif item_type == "comment_list":
             data = results[0].get("data", {})
             comments = data.get("comments", [])
             pattern = data.get("pattern", "unknown")
             output += f"Comments/TODOs matching '{pattern}':\\n\\n"
             if not comments:
                  output += "  (No matching comments)\\n"
             else:
                  for c in comments:
                      output += f"  - {c['filename']}:{c['line']} -> {c['content']}\\n"

        elif item_type == "tag_list":
             tags = results[0].get("tags", [])
             output += f"Found {len(tags)} Tags:\\n\\n"
             for t in tags:
                 output += f"  - {t}\\n"

        elif item_type == "custom_query_result":
             data = results[0].get("data", {})
             query_str = data.get("query", "")
             res_list = data.get("results", [])
             count = data.get("count", 0)
             
             output += f"Custom Query Execution ('{query_str}'):\\n"
             output += f"Count: {count}\\n\\n"
             if not res_list:
                 output += "  (No results)\\n"
             else:
                 # Limit output for raw queries
                 for i, r in enumerate(res_list[:20]):
                     output += f"  [{i+1}] {r}\\n"
                 if len(res_list) > 20:
                     output += f"  ... and {len(res_list)-20} more.\\n"

        else: # joern_query
            output += f"Found {len(results)} matches:\\n\\n"
            for i, item in enumerate(results[:20], 1):
                output += f"  {i}. {item}\\n"

        return output

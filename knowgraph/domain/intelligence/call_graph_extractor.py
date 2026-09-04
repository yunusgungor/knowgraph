"""Call graph relationship extraction from Joern CPG.

Extracts function/method call relationships to create graph edges
representing caller → callee relationships.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class CallGraphExtractor:
    """Extract function call relationships from Joern CPG."""

    def __init__(self):
        """Initialize call graph extractor."""

    def extract_call_edges(self, cpg_path: Path) -> list[dict]:
        """Extract function call edges from CPG using caller→callee relationships.

        Args:
            cpg_path: Path to CPG binary

        Returns:
            List of edge dictionaries with source, target, and type
        """
        from knowgraph.core.joern import JoernProvider
        from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

        if not cpg_path.exists():
            logger.warning(f"CPG not found at {cpg_path}")
            return []

        try:
            provider = JoernProvider()
            executor = JoernQueryExecutor(Path(provider.joern_path))

            # For dynamically-typed languages (Python, JS), referencedDecl is
            # often empty. Use the enclosing method as caller and match the
            # call name against known method definitions for callee resolution.
            # Step 1: Collect all method names.  Step 2: For each call inside a
            # method, if the call name matches a known method, emit caller→callee.
            query = """
            val methods = cpg.method.name.l.toSet
            cpg.call.filter(c => !c.name.startsWith("<operator>") && !c.name.startsWith("<"))
              .map { c =>
                val caller = c.method.name
                val callee = c.name
                s"${caller}__KG_SEP__${callee}"
              }.dedup.l.filter { line =>
                val parts = line.split("__KG_SEP__")
                parts.length == 2 && methods.contains(parts(1)) && parts(0) != parts(1)
              }
            """

            result = executor.execute_query(cpg_path, query, timeout=60)

            if not result or not result.results:
                logger.warning("No call edges found via referencedDecl, falling back to name-based")
                return self._extract_call_edges_fallback(cpg_path, executor)

            edges = []
            seen = set()

            # Python builtins and common dunder methods that produce noisy edges
            _SKIP_TARGETS = frozenset({
                # Python builtins
                "len", "print", "str", "int", "float", "list", "dict", "set", "tuple",
                "type", "isinstance", "hasattr", "getattr", "setattr", "dir", "vars",
                "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
                "any", "all", "min", "max", "sum", "abs", "round", "open", "input",
                "super", "property", "staticmethod", "classmethod", "__import__",
                "format", "repr", "id", "hash", "callable", "iter", "next",
                # Common collection methods
                "append", "extend", "insert", "remove", "pop", "clear",
                "items", "keys", "values", "get", "update", "setdefault",
                "copy", "deepcopy", "upper", "lower", "strip", "split", "join",
                "replace", "startswith", "endswith", "find", "index", "count",
                "encode", "decode", "json", "echo",
            })

            for item in result.results:
                raw = item.get("raw", "")
                if "__KG_SEP__" not in raw:
                    continue
                parts = raw.split("__KG_SEP__")
                if len(parts) != 2:
                    continue
                caller, callee = parts[0].strip(), parts[1].strip()

                # Skip module-level and synthetic callers/callees
                if not caller or caller.startswith("<") or not callee or callee.startswith("<"):
                    continue
                if caller == callee:
                    continue
                if callee in _SKIP_TARGETS or callee.startswith("__"):
                    continue

                edge_key = f"{caller}->{callee}"
                if edge_key not in seen:
                    seen.add(edge_key)
                    edges.append({
                        "source": caller,
                        "target": callee,
                        "type": "calls",
                        "metadata": {}
                    })

            logger.info(f"Extracted {len(edges)} call relationships via referencedDecl")
            return edges

        except Exception as e:
            logger.error(f"Failed to extract call graph: {e}")
            return []

    def _extract_call_edges_fallback(
        self, cpg_path: Path, executor
    ) -> list[dict]:
        """Fallback: extract call edges from code text parsing."""
        query_calls = "cpg.call.code.l"
        query_methods = "cpg.method.name.l"

        result_calls = executor.execute_query(cpg_path, query_calls, timeout=60)
        result_methods = executor.execute_query(cpg_path, query_methods, timeout=30)

        if not result_calls or not result_calls.results:
            return []
        if not result_methods or not result_methods.results:
            return []

        method_names = set()
        for item in result_methods.results:
            name = item.get("raw", "").strip()
            if name and not name.startswith("<"):
                method_names.add(name)

        edges = []
        seen = set()

        for item in result_calls.results:
            code = item.get("raw", "").strip()
            if not code or "<operator>" in code or "__builtins__" in code:
                continue
            if "(" not in code:
                continue
            call_part = code.split("(")[0]
            callee = call_part.split(".")[-1].strip() if "." in call_part else call_part.strip()
            if callee in method_names:
                edge_key = f"unknown->{callee}"
                if edge_key not in seen:
                    seen.add(edge_key)
                    edges.append({"source": "unknown", "target": callee, "type": "calls", "metadata": {"code": code[:100]}})

        logger.info(f"Fallback extracted {len(edges)} call edges (caller=unknown)")
        return edges

    def edges_to_graph_format(self, edges: list[dict]) -> list[dict]:
        """Convert call edges to KnowGraph edge format.

        Args:
            edges: List of call edge dictionaries

        Returns:
            List of edges ready for graph insertion
        """
        graph_edges = []

        for edge in edges:
            graph_edge = {
                "id": f"call_{hash(edge['source'] + edge['target'])}",
                "source": f"code_method_{hash(edge['source'])}",
                "target": f"code_method_{hash(edge['target'])}",
                "type": edge["type"],
                "metadata": edge.get("metadata", {})
            }

            graph_edges.append(graph_edge)

        return graph_edges

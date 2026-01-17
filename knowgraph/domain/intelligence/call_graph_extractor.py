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
        """Extract function call edges from CPG.

        Args:
            cpg_path: Path to CPG binary

        Returns:
            List of edge dictionaries with source, target, and type

        Example:
            [
                {
                    'source': 'login',
                    'target': 'authenticate',
                    'type': 'calls',
                    'metadata': {}
                }
            ]
        """
        from knowgraph.core.joern import JoernProvider
        from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

        if not cpg_path.exists():
            logger.warning(f"CPG not found at {cpg_path}")
            return []

        try:
            provider = JoernProvider()
            executor = JoernQueryExecutor(Path(provider.joern_path))

            # Get all calls and methods for relationship building
            # Strategy: Extract calls, filter out operators, create edges based on context

            query_calls = "cpg.call.code.l"
            query_methods = "cpg.method.name.l"

            result_calls = executor.execute_query(cpg_path, query_calls, timeout=60)
            result_methods = executor.execute_query(cpg_path, query_methods, timeout=30)

            if not result_calls or not result_calls.results:
                logger.warning("No calls found in CPG")
                return []

            if not result_methods or not result_methods.results:
                logger.warning("No methods found for relationship building")
                return []

            # Build method name set for filtering
            method_names = set()
            for item in result_methods.results:
                name = item.get("raw", "").strip()
                if name and not name.startswith("<"):
                    method_names.add(name)

            logger.info(f"Found {len(method_names)} methods for relationship tracking")

            # Extract call relationships
            edges = []
            seen = set()

            for item in result_calls.results:
                code = item.get("raw", "").strip()

                if not code:
                    continue

                # Skip operators and builtins
                if any(x in code for x in ["<operator>", "__builtins__",  "="]):
                    continue

                # Parse call: "receiver.method(...)" or "method(...)"
                # Extract the called method name
                if "(" in code:
                    call_part = code.split("(")[0]

                    # Handle method.name or just name
                    if "." in call_part:
                        parts = call_part.split(".")
                        callee = parts[-1].strip()
                    else:
                        callee = call_part.strip()

                    # Only track if it's a known method
                    if callee in method_names:
                        # For simplicity, we can't easily determine caller from code
                        # So we'll create generic "calls" relationships
                        # Future: use more complex Joern query to get caller info

                        edge_key = f"unknown->{callee}"
                        if edge_key not in seen:
                            seen.add(edge_key)

                            edges.append({
                                "source": "unknown",  # Would need caller context
                                "target": callee,
                                "type": "calls",
                                "metadata": {"code": code[:100]}
                            })

            logger.info(f"Extracted {len(edges)} call relationships (simplified)")
            logger.warning("Call graph uses simplified extraction - caller info not available with current query")

            return edges

        except Exception as e:
            logger.error(f"Failed to extract call graph: {e}")
            return []

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

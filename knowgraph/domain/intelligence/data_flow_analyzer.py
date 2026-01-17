"""Data flow analysis module using Joern.

Tracks how data flows through code to identify potential security issues
and understand variable propagation.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DataFlowAnalyzer:
    """Analyze data flow through code using Joern."""

    def __init__(self):
        """Initialize data flow analyzer."""

    def analyze_data_flow(
        self,
        cpg_path: Path,
        source_method: Optional[str] = None,
        sink_method: Optional[str] = None
    ) -> list[dict]:
        """Analyze data flow from sources to sinks.

        Args:
            cpg_path: Path to CPG binary
            source_method: Optional source method to track from
            sink_method: Optional sink method to track to

        Returns:
            List of data flow paths

        Example:
            [
                {
                    'source': 'getUserInput',
                    'sink': 'executeQuery',
                    'path': ['getUserInput', 'sanitize', 'executeQuery'],
                    'risk': 'high'
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

            # Joern query for data flow
            # Note: This is a simplified version - full data flow requires complex queries
            if source_method and sink_method:
                # Track specific source to sink
                query = f"""
                cpg.method.name("{source_method}").parameter.reachableBy(
                    cpg.method.name("{sink_method}").parameter
                ).flows.l
                """
            else:
                # General data flow analysis - find common sources/sinks
                query = """
                cpg.method.name.l
                """

            result = executor.execute_query(cpg_path, query, timeout=60)

            if not result or not result.results:
                logger.warning("No data flows found")
                return []

            # Parse results into flow paths
            flows = []

            # For now, return simplified flow information
            # Full implementation would parse actual flow paths
            logger.info(f"Data flow analysis found {len(result.results)} potential flows")
            logger.warning("Data flow analysis is simplified - full implementation requires advanced Joern queries")

            return flows

        except Exception as e:
            logger.error(f"Failed to analyze data flow: {e}")
            return []

    def find_tainted_flows(self, cpg_path: Path) -> list[dict]:
        """Find potentially tainted data flows (user input → sensitive operations).

        Args:
            cpg_path: Path to CPG binary

        Returns:
            List of tainted flow paths
        """
        from knowgraph.core.joern import JoernProvider
        from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

        if not cpg_path.exists():
            logger.warning(f"CPG not found at {cpg_path}")
            return []

        try:
            provider = JoernProvider()
            executor = JoernQueryExecutor(Path(provider.joern_path))

            # Common sources of tainted data
            sources = ["input", "request", "param", "read", "get"]

            # Common sinks (sensitive operations)
            sinks = ["exec", "eval", "query", "write", "send"]

            tainted_flows = []

            # Check for methods that might handle tainted data
            query = "cpg.method.name.l"
            result = executor.execute_query(cpg_path, query, timeout=30)

            if result and result.results:
                methods = [item.get("raw", "") for item in result.results]

                # Find potential sources
                source_methods = [
                    m for m in methods
                    if any(s in m.lower() for s in sources)
                ]

                # Find potential sinks
                sink_methods = [
                    m for m in methods
                    if any(s in m.lower() for s in sinks)
                ]

                # Create potential flow pairs
                for source in source_methods[:10]:  # Limit to avoid too many
                    for sink in sink_methods[:10]:
                        tainted_flows.append({
                            "source": source,
                            "sink": sink,
                            "risk": "potential",
                            "type": "tainted_flow",
                            "verified": False  # Would need actual flow analysis
                        })

                logger.info(f"Found {len(tainted_flows)} potential tainted flows")

            return tainted_flows

        except Exception as e:
            logger.error(f"Failed to find tainted flows: {e}")
            return []

    def flows_to_graph_format(self, flows: list[dict]) -> list[dict]:
        """Convert data flows to KnowGraph edge format.

        Args:
            flows: List of flow dictionaries

        Returns:
            List of edges ready for graph insertion
        """
        graph_edges = []

        for flow in flows:
            edge = {
                "id": f"dataflow_{hash(flow['source'] + flow['sink'])}",
                "source": f"code_method_{hash(flow['source'])}",
                "target": f"code_method_{hash(flow['sink'])}",
                "type": "dataflow",
                "metadata": {
                    "risk": flow.get("risk", "unknown"),
                    "verified": flow.get("verified", False),
                    "flow_type": flow.get("type", "generic")
                }
            }

            graph_edges.append(edge)

        return graph_edges

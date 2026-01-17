"""
Taint Analysis Engine for Security Vulnerability Detection

Uses Joern's data_flow edges to trace user input from sources to dangerous sinks.
"""

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID

import networkx as nx

from knowgraph.application.security.vulnerability_patterns import (
    VULNERABILITY_PATTERNS,
    VulnerabilityType,
    get_all_sinks,
    get_all_sources,
)
from knowgraph.domain.models.node import Node

logger = logging.getLogger(__name__)


@dataclass
class TaintPath:
    """Represents a taint flow from source to sink.

    Attributes
    ----------
        source_node: UUID of the taint source node
        sink_node: UUID of the sink node
        path: List of node UUIDs representing the data flow path
        confidence: Confidence score (0.0-1.0)
        vulnerability_type: Type of vulnerability detected
        severity: Risk level (Critical, High, Medium, Low)
        source_description: Human-readable source description
        sink_description: Human-readable sink description
        path_description: Text description of the taint flow

    """

    source_node: UUID
    sink_node: UUID
    path: list[UUID]
    confidence: float
    vulnerability_type: str
    severity: str
    source_description: str
    sink_description: str
    path_description: str

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            **asdict(self),
            "source_node": str(self.source_node),
            "sink_node": str(self.sink_node),
            "path": [str(node_id) for node_id in self.path],
        }


class TaintAnalyzer:
    """Joern-powered taint analysis for security vulnerabilities.

    Traces data flow from user input sources to dangerous sinks
    using Joern's data_flow edges.
    """

    def __init__(self, graph_store_path: str):
        """Initialize taint analyzer.

        Args:
        ----
            graph_store_path: Path to KnowGraph graph store

        """
        self.graph_path = Path(graph_store_path)
        self.graph = self._load_graph()
        self.nodes = self._load_nodes()

        # Default patterns
        self.default_sources = get_all_sources()
        self.default_sinks = get_all_sinks()

    def _load_graph(self) -> nx.DiGraph:
        """Load NetworkX graph from graph store.

        Returns
        -------
            Directed graph with edges

        """
        from knowgraph.infrastructure.storage.filesystem import read_all_edges

        # Load all edges from storage
        edges = read_all_edges(self.graph_path)

        # Build NetworkX directed graph
        G = nx.DiGraph()
        for edge in edges:
            G.add_edge(
                edge.source,
                edge.target,
                type=edge.type,
                score=edge.score,
                metadata=edge.metadata,
            )

        return G

    def _load_nodes(self) -> dict[UUID, Node]:
        """Load node data from graph store.

        Returns
        -------
            Dictionary mapping node IDs to Node objects

        """
        from knowgraph.infrastructure.storage.filesystem import (
            list_all_nodes,
            read_node_json,
        )

        # List all node IDs
        node_ids = list_all_nodes(self.graph_path)

        # Load each node
        nodes = {}
        for node_id in node_ids:
            node = read_node_json(node_id, self.graph_path)
            if node:
                nodes[node.id] = node

        return nodes

    def find_vulnerabilities(
        self,
        source_patterns: list[str] | None = None,
        sink_patterns: list[str] | None = None,
        max_depth: int = 10,
    ) -> list[TaintPath]:
        """Find all taint flows from sources to sinks using Joern.

        Args:
        ----
            source_patterns: Custom source patterns (default: all known sources)
            sink_patterns: Custom sink patterns (default: all known sinks)
            max_depth: Maximum path length to search

        Returns:
        -------
            List of identified taint paths

        """
        from knowgraph.infrastructure.indexing.cpg_metadata import get_cpg_path
        from knowgraph.core.joern import JoernProvider

        cpg_path = get_cpg_path(self.graph_path)
        if not cpg_path or not cpg_path.exists():
            logger.warning("No CPG found for taint analysis")
            return []

        sources = source_patterns or self.default_sources
        sinks = sink_patterns or self.default_sinks
        
        # Determine specific vulnerabilities to look for based on sinks
        # Optimization: Map sinks to vulnerability types to avoid NxM scan if possible
        # For now, we iterate, but we can limit combinatorics.
        
        provider = JoernProvider()
        taint_paths = []
        
        logger.info(f"Scanning for vulnerabilities with {len(sources)} sources and {len(sinks)} sinks via Joern")

        # Optimization: Group sinks by potential vulnerability type if patterns allow, 
        # but Joern needs specific regex patterns.
        # We'll iterate but we can combine patterns with OR (|) eventually.
        # For compatibility with legacy test patterns (which might be simple substrings), we ensure regex safety.
        
        import re
        
        # Build node cache for lookup (File -> Line -> Node)
        # This is expensive O(N), but done once per analyze call
        node_map = {} # {filename: {line: node_id}}
        for node_id, node in self.nodes.items():
             if node.metadata and "file_path" in node.metadata:
                 fname = node.metadata["file_path"]
                 # Normalize filename to mimic Joern's output (often absolute or relative)
                 # We'll fuzzy match end of path
                 line = node.metadata.get("start_line", -1)
                 if line != -1:
                     if fname not in node_map: node_map[fname] = {}
                     node_map[fname][line] = node_id

        for source in sources:
            for sink in sinks:
                # Use Joern to analyze flow
                try:
                    # Sanitize patterns for regex
                    # If pattern is simple (alphanumeric+dot), treat as literal, else assume regex
                    src_regex = source if any(c in source for c in ".*^$") else re.escape(source)
                    sink_regex = sink if any(c in sink for c in ".*^$") else re.escape(sink)
                    
                    result = provider.analyze_taint_flow(cpg_path, src_regex, sink_regex)
                    
                    if not result or "flows" not in result:
                        continue
                        
                    for flow in result["flows"]:
                         # Convert Joern flow (list of steps) to UUID path
                         path_uuids = []
                         for step in flow:
                             # Try to find matching node
                             step_file = step["filename"]
                             step_line = step["line"]
                             
                             # Lookup
                             found_id = None
                             
                             # Exact match attempt
                             if step_file in node_map and step_line in node_map[step_file]:
                                 found_id = node_map[step_file][step_line]
                             else:
                                 # Fuzzy match filename (suffix)
                                 for f_key in node_map:
                                     if f_key.endswith(step_file) or step_file.endswith(f_key):
                                         if step_line in node_map[f_key]:
                                             found_id = node_map[f_key][step_line]
                                             break
                             
                             if found_id:
                                 path_uuids.append(found_id)
                             else:
                                 # If we can't map a step to a graph node, we might skip it or use a placeholder?
                                 # TaintPath requires UUIDs existing in graph.
                                 # We'll skip the step but keep the path if we have start/end.
                                 continue
                         
                         if len(path_uuids) >= 2:
                             # Construct TaintPath
                             tpath = self._create_taint_path(path_uuids[0], path_uuids[-1], path_uuids)
                             if tpath:
                                 # Deduplicate based on ID
                                 if not any(tp.source_node == tpath.source_node and tp.sink_node == tpath.sink_node for tp in taint_paths):
                                     taint_paths.append(tpath)
                                     
                except Exception as e:
                    logger.debug(f"Joern taint analysis failed for {source}->{sink}: {e}")
                    continue

        logger.info(f"Detected {len(taint_paths)} potential vulnerabilities")
        return taint_paths

    def _find_nodes_by_pattern(self, patterns: list[str]) -> list[UUID]:
        """Find nodes matching any of the given patterns.

        Args:
        ----
            patterns: List of string patterns to match

        Returns:
        -------
            List of matching node IDs

        """
        matching_nodes = []

        for node_id, node in self.nodes.items():
            content_lower = node.content.lower()

            # Check if any pattern matches
            for pattern in patterns:
                if pattern.lower() in content_lower:
                    matching_nodes.append(node_id)
                    break

        return matching_nodes

    def _find_dataflow_paths(
        self,
        source_id: UUID,
        sink_id: UUID,
        max_depth: int,
    ) -> list[list[UUID]]:
        """Find all paths from source to sink using data_flow edges.

        Uses BFS with depth limit to avoid infinite loops.

        Args:
        ----
            source_id: Source node ID
            sink_id: Sink node ID
            max_depth: Maximum path length

        Returns:
        -------
            List of paths (each path is a list of node IDs)

        """
        # Create subgraph with only data_flow edges
        dataflow_edges = [
            (u, v) for u, v, data in self.graph.edges(data=True)
            if data.get("type") == "data_flow"
        ]

        if not dataflow_edges:
            logger.warning("No data_flow edges found in graph")
            return []

        subgraph = self.graph.edge_subgraph(dataflow_edges)

        # Find all simple paths
        try:
            paths = nx.all_simple_paths(
                subgraph,
                source_id,
                sink_id,
                cutoff=max_depth,
            )
            return list(paths)
        except nx.NetworkXNoPath:
            return []
        except nx.NodeNotFound:
            logger.debug(f"Node not found in data flow subgraph: {source_id} or {sink_id}")
            return []

    def _create_taint_path(
        self,
        source_id: UUID,
        sink_id: UUID,
        path: list[UUID],
    ) -> TaintPath | None:
        """Create TaintPath from raw path data.

        Args:
        ----
            source_id: Source node ID
            sink_id: Sink node ID
            path: List of node IDs in the path

        Returns:
        -------
            TaintPath object or None if invalid

        """
        if not path or len(path) < 2:
            return None

        # Get node data
        source_node = self.nodes.get(source_id)
        sink_node = self.nodes.get(sink_id)

        if not source_node or not sink_node:
            return None

        # Determine vulnerability type
        vuln_type = self._classify_vulnerability(source_node, sink_node)

        # Get severity from pattern
        pattern = VULNERABILITY_PATTERNS.get(vuln_type)
        severity = pattern.severity if pattern else "Medium"

        # Calculate confidence score
        confidence = self._calculate_confidence(path)

        # Build descriptions
        source_desc = self._describe_node(source_node)
        sink_desc = self._describe_node(sink_node)
        path_desc = self._describe_path(path)

        return TaintPath(
            source_node=source_id,
            sink_node=sink_id,
            path=path,
            confidence=confidence,
            vulnerability_type=vuln_type.value if isinstance(vuln_type, VulnerabilityType) else str(vuln_type),
            severity=severity,
            source_description=source_desc,
            sink_description=sink_desc,
            path_description=path_desc,
        )

    def _classify_vulnerability(
        self,
        source_node: Node,
        sink_node: Node,
    ) -> VulnerabilityType | str:
        """Classify vulnerability type based on source and sink.

        Args:
        ----
            source_node: Source node
            sink_node: Sink node

        Returns:
        -------
            Vulnerability type enum or string

        """
        sink_content = sink_node.content.lower()

        # Check each pattern
        for vuln_type, pattern in VULNERABILITY_PATTERNS.items():
            for sink_pattern in pattern.sinks:
                if sink_pattern.lower() in sink_content:
                    return vuln_type

        return "Unknown"

    def _calculate_confidence(self, path: list[UUID]) -> float:
        """Calculate confidence score for taint path.

        Shorter paths and direct flows have higher confidence.

        Args:
        ----
            path: List of node IDs in the path

        Returns:
        -------
            Confidence score (0.0-1.0)

        """
        # Base confidence: 1.0 for direct flow (length 2)
        # Decrease by 0.1 for each additional hop
        base = 1.0
        penalty = (len(path) - 2) * 0.1
        confidence = max(0.0, base - penalty)

        return round(confidence, 2)

    def _describe_node(self, node: Node) -> str:
        """Generate human-readable node description.

        Args:
        ----
            node: Node to describe

        Returns:
        -------
            Description string

        """
        # Extract relevant snippet (first 100 chars)
        snippet = node.content[:100].strip()
        return f"{node.path}: {snippet}"

    def _describe_path(self, path: list[UUID]) -> str:
        """Generate human-readable path description.

        Args:
        ----
            path: List of node IDs

        Returns:
        -------
            Path description

        """
        path_parts = []
        for node_id in path:
            node = self.nodes.get(node_id)
            if node:
                # Extract function/variable name if possible
                snippet = node.content.split("\n")[0][:50]
                path_parts.append(snippet)

        return " → ".join(path_parts)

"""
Dataflow Query Results

Data structures for representing dataflow analysis results.
"""

from dataclasses import dataclass
from uuid import UUID

from knowgraph.domain.models.node import Node


@dataclass
class DataFlowResult:
    """Result from dataflow query.

    Attributes
    ----------
        paths: List of node ID paths from source to sink
        nodes: Node data mapped by ID
        source_pattern: Original source search pattern
        sink_pattern: Original sink search pattern
        path_count: Number of paths found

    """

    paths: list[list[UUID]]
    nodes: dict[UUID, Node]
    source_pattern: str
    sink_pattern: str
    path_count: int

    def to_mermaid(self) -> str:
        """Generate Mermaid flowchart diagram of dataflow.

        Returns
        -------
            Mermaid diagram as string

        """
        if not self.paths:
            return "graph TD\n  A[No paths found]"

        # Use flowchart format
        lines = ["graph TD"]

        # Track unique nodes and edges
        unique_edges = set()
        node_labels = {}

        # Process all paths
        for path_idx, path in enumerate(self.paths):
            for i in range(len(path) - 1):
                source_id = path[i]
                target_id = path[i + 1]

                # Create node labels (use first 30 chars of content)
                if source_id not in node_labels:
                    node = self.nodes.get(source_id)
                    if node:
                        label = node.content.split("\n")[0][:30].strip()
                        node_labels[source_id] = f"{str(source_id)[:8]}_{label}"

                if target_id not in node_labels:
                    node = self.nodes.get(target_id)
                    if node:
                        label = node.content.split("\n")[0][:30].strip()
                        node_labels[target_id] = f"{str(target_id)[:8]}_{label}"

                # Add edge
                edge = (source_id, target_id)
                if edge not in unique_edges:
                    unique_edges.add(edge)

        # Generate diagram
        for source_id, target_id in unique_edges:
            source_label = node_labels.get(source_id, str(source_id)[:8])
            target_label = node_labels.get(target_id, str(target_id)[:8])

            # Clean labels for Mermaid syntax
            source_label = source_label.replace('"', "'")
            target_label = target_label.replace('"', "'")

            lines.append(f'  {str(source_id)[:8]}["{source_label}"] --> {str(target_id)[:8]}["{target_label}"]')

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization.

        Returns
        -------
            Dictionary representation

        """
        return {
            "paths": [[str(node_id) for node_id in path] for path in self.paths],
            "nodes": {str(k): v.to_dict() for k, v in self.nodes.items()},
            "source_pattern": self.source_pattern,
            "sink_pattern": self.sink_pattern,
            "path_count": self.path_count,
        }

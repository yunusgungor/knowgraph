"""CPG Converter - Converts Joern CPG to KnowGraph nodes and edges.

This module enables full CPG integration by creating separate nodes from
CPG entities and converting CPG edges to KnowGraph edge types.
"""

import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from knowgraph.core.joern import JoernCPG
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node

logger = logging.getLogger(__name__)


@dataclass
class CPGConversionResult:
    """Result of CPG to KnowGraph conversion.

    Attributes
    ----------
        entity_nodes: Nodes created from CPG entities
        cpg_edges: Edges from CPG relationships
        chunk_node_id: Parent chunk node ID
        metadata: Conversion statistics

    """

    entity_nodes: list[Node]
    cpg_edges: list[Edge]
    chunk_node_id: UUID
    metadata: dict


class CPGConverter:
    """Converts Joern CPG to KnowGraph nodes and edges.

    Creates separate nodes for significant CPG entities (METHOD, CALL, etc.)
    and converts CPG edges to KnowGraph edge types (semantic, data_flow, etc.).
    """

    # CPG node types to create KnowGraph nodes for
    SIGNIFICANT_NODE_TYPES = {
        "METHOD", "CALL", "TYPE_DECL", "IDENTIFIER",
        "LOCAL", "LITERAL", "NAMESPACE_BLOCK"
    }

    def convert_cpg_to_graph(
        self,
        cpg: JoernCPG,
        chunk_node_id: UUID,
        file_path: str,
    ) -> CPGConversionResult:
        """Convert CPG to KnowGraph nodes and edges.

        Args:
        ----
            cpg: Joern CPG object
            chunk_node_id: Parent chunk node ID
            file_path: Source file path

        Returns:
        -------
            CPGConversionResult with entity nodes, edges, and metadata

        """
        entity_nodes = []
        cpg_edges = []

        # Map CPG node IDs to KnowGraph node IDs
        id_mapping = {}

        logger.info(f"Converting CPG: {len(cpg.nodes)} nodes, {len(cpg.edges)} edges")

        # Convert CPG nodes to entity nodes
        for cpg_node in cpg.nodes:
            node_type = cpg_node.get("labelV", cpg_node.get("label", ""))

            # Only create nodes for significant entities
            if node_type in self.SIGNIFICANT_NODE_TYPES:
                kg_node = self._cpg_node_to_knowgraph_node(
                    cpg_node,
                    chunk_node_id,
                    file_path,
                )
                entity_nodes.append(kg_node)
                id_mapping[cpg_node["id"]] = kg_node.id

        logger.debug(f"Created {len(entity_nodes)} entity nodes from {len(cpg.nodes)} CPG nodes")

        # Convert CPG edges to KnowGraph edges
        for cpg_edge in cpg.edges:
            edge_type = cpg_edge.get("labelE", cpg_edge.get("label", ""))
            source_cpg_id = cpg_edge["source"]
            target_cpg_id = cpg_edge["target"]

            # Only create edges if both nodes exist in mapping
            if source_cpg_id in id_mapping and target_cpg_id in id_mapping:
                kg_edge = Edge(
                    source=id_mapping[source_cpg_id],
                    target=id_mapping[target_cpg_id],
                    type=self._map_cpg_edge_type(edge_type),
                    score=0.9,  # CPG edges are high confidence
                    created_at=int(__import__("time").time()),
                    metadata={
                        "cpg_edge_type": edge_type,
                        "source": "joern_cpg",
                    },
                )
                cpg_edges.append(kg_edge)

        logger.info(f"✅ CPG conversion: {len(entity_nodes)} nodes, {len(cpg_edges)} edges")

        return CPGConversionResult(
            entity_nodes=entity_nodes,
            cpg_edges=cpg_edges,
            chunk_node_id=chunk_node_id,
            metadata={
                "cpg_nodes_total": len(cpg.nodes),
                "cpg_nodes_created": len(entity_nodes),
                "cpg_edges_total": len(cpg.edges),
                "cpg_edges_created": len(cpg_edges),
                "conversion_rate": len(cpg_edges) / len(cpg.edges) if cpg.edges else 0,
            },
        )

    def _cpg_node_to_knowgraph_node(
        self,
        cpg_node: dict,
        parent_id: UUID,
        file_path: str,
    ) -> Node:
        """Convert single CPG node to KnowGraph node.

        Args:
        ----
            cpg_node: CPG node dictionary
            parent_id: Parent chunk node ID
            file_path: Source file path

        Returns:
        -------
            KnowGraph Node object

        """
        import hashlib
        import time

        node_type = cpg_node.get("labelV", cpg_node.get("label", ""))
        name = cpg_node.get("NAME", cpg_node.get("CODE", cpg_node.get("FULL_NAME", "")))

        # Create content snippet from CODE attribute
        content = cpg_node.get("CODE", "")
        if len(content) > 200:
            content = content[:200] + "..."

        # If no content, use name
        if not content:
            content = name or f"<{node_type}>"

        # Create title from name or node type
        title = name[:100] if name else f"{node_type} entity"

        # Generate SHA-1 hash from CPG node ID (Node requires 40-char hash)
        cpg_id_str = str(cpg_node["id"])
        hash_value = hashlib.sha1(cpg_id_str.encode()).hexdigest()

        return Node(
            id=uuid4(),
            hash=hash_value,  # Proper SHA-1 hash (40 chars)
            title=title,
            content=content,
            path=file_path,
            type=self._map_cpg_node_type_to_knowgraph(node_type),
            token_count=len(content.split()),  # Rough estimate
            created_at=int(time.time()),
            header_depth=None,
            header_path=None,
            chunk_id=None,
            line_start=cpg_node.get("LINE_NUMBER"),
            line_end=cpg_node.get("LINE_NUMBER_END", cpg_node.get("LINE_NUMBER")),
            metadata={
                "cpg_type": node_type,
                "cpg_id": str(cpg_node["id"]),
                "name": name,
                "full_name": cpg_node.get("FULL_NAME", name),
                "parent_chunk_id": str(parent_id),
                "source": "joern_cpg",
                # Additional CPG attributes
                "signature": cpg_node.get("SIGNATURE", ""),
                "method_full_name": cpg_node.get("METHOD_FULL_NAME", ""),
                "type_full_name": cpg_node.get("TYPE_FULL_NAME", ""),
            },
        )

    def _map_cpg_node_type_to_knowgraph(self, cpg_type: str) -> str:
        """Map CPG node type to KnowGraph NodeType string.

        Args:
        ----
            cpg_type: CPG node type (e.g., METHOD, CALL)

        Returns:
        -------
            NodeType string literal ('code', 'text', etc.)

        """
        # NodeType is a Literal type, not an enum - use strings
        # Most CPG entities are 'code'
        return "code"  # All CPG entities are code


    def _map_cpg_edge_type(self, cpg_edge_type: str) -> str:
        """Map CPG edge type to KnowGraph edge type.

        Args:
        ----
            cpg_edge_type: CPG edge type (e.g., AST, CFG, DDG)

        Returns:
        -------
            KnowGraph edge type string

        """
        mapping = {
            # Abstract Syntax Tree
            "AST": "semantic",
            # Control Flow Graph
            "CFG": "control_flow",
            # Data Dependency Graph
            "DDG": "data_flow",
            # Control Dependency Graph
            "CDG": "control_flow",
            # Function calls
            "CALL": "reference",
            # Containment
            "CONTAINS": "hierarchy",
            "SOURCE_FILE": "hierarchy",
            # Bindings and references
            "REF": "reference",
            "BINDS": "reference",
            # Evaluation order
            "EVAL_TYPE": "semantic",
            "REACHING_DEF": "data_flow",
        }
        return mapping.get(cpg_edge_type, "semantic")

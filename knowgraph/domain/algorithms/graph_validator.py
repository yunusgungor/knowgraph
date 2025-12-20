"""Graph consistency validation for pre-flight query checks.

Implements validation rules from FR-058:
- No dangling edges (source/target nodes exist)
- No self-loops (source ≠ target)
- Valid edge types (hierarchy|lexical|reference|cross_file)
- Node hash integrity (SHA-1 format)
"""

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.storage.filesystem import (
    list_all_nodes,
    read_all_edges,
    read_node_json,
)

# SHA-1 hash is 40 hexadecimal characters
SHA1_PATTERN = re.compile(r"^[a-f0-9]{40}$")

# Valid edge types from FR-058 (Updated to include Reference Edges)
VALID_EDGE_TYPES = {"semantic", "reference"}


@dataclass
class ValidationResult:
    """Result of graph consistency validation.

    Attributes
    ----------
        valid: Whether graph passes all checks
        dangling_edges: Edges with missing source/target nodes
        self_loops: Edges where source == target
        invalid_edge_types: Edges with invalid type field
        invalid_node_hashes: Nodes with malformed SHA-1 hashes
        error_count: Total number of errors found

    """

    valid: bool
    dangling_edges: list[Edge]
    self_loops: list[Edge]
    invalid_edge_types: list[Edge]
    invalid_node_hashes: list[Node]

    @property
    def error_count(self) -> int:
        """Total number of errors across all categories."""
        return (
            len(self.dangling_edges)
            + len(self.self_loops)
            + len(self.invalid_edge_types)
            + len(self.invalid_node_hashes)
        )

    def get_error_summary(self) -> str:
        """Generate human-readable error summary."""
        if self.valid:
            return "✓ Graph validation passed"

        errors = []
        if self.dangling_edges:
            errors.append(f"- {len(self.dangling_edges)} dangling edge(s)")
        if self.self_loops:
            errors.append(f"- {len(self.self_loops)} self-loop(s)")
        if self.invalid_edge_types:
            errors.append(f"- {len(self.invalid_edge_types)} invalid edge type(s)")
        if self.invalid_node_hashes:
            errors.append(f"- {len(self.invalid_node_hashes)} invalid node hash(es)")

        return f"✗ Graph validation failed ({self.error_count} errors):\n" + "\n".join(errors)


def validate_graph_consistency(graph_store_path: Path) -> ValidationResult:
    """Validate graph consistency with all checks from FR-058.

    Performs comprehensive validation:
    1. Dangling edge detection (source/target nodes must exist)
    2. Self-loop detection (source must differ from target)
    3. Edge type validation (must be in VALID_EDGE_TYPES)
    4. Node hash integrity (must match SHA-1 format)

    Args:
    ----
        graph_store_path: Root storage directory containing nodes/ and edges/

    Returns:
    -------
        ValidationResult with all detected errors

    """
    # Load all nodes and edges
    node_ids = set(list_all_nodes(graph_store_path))
    edges = read_all_edges(graph_store_path)

    # Load node details for hash validation
    nodes = []
    for node_id in node_ids:
        node = read_node_json(node_id, graph_store_path)
        if node:
            nodes.append(node)

    # Check 1: Dangling edges
    dangling_edges = detect_dangling_edges(edges, node_ids)

    # Check 2: Self-loops
    self_loops = detect_self_loops(edges)

    # Check 3: Edge type validation
    invalid_edge_types = validate_edge_types(edges)

    # Check 4: Node hash integrity
    invalid_node_hashes = validate_node_hashes(nodes)

    # Determine overall validity
    valid = (
        len(dangling_edges) == 0
        and len(self_loops) == 0
        and len(invalid_edge_types) == 0
        and len(invalid_node_hashes) == 0
    )

    return ValidationResult(
        valid=valid,
        dangling_edges=dangling_edges,
        self_loops=self_loops,
        invalid_edge_types=invalid_edge_types,
        invalid_node_hashes=invalid_node_hashes,
    )


def detect_dangling_edges(edges: list[Edge], valid_node_ids: set[UUID]) -> list[Edge]:
    """Detect edges with source or target nodes that don't exist.

    Args:
    ----
        edges: List of all edges
        valid_node_ids: Set of all existing node IDs

    Returns:
    -------
        List of edges with missing source or target

    """
    dangling = []
    for edge in edges:
        if edge.source not in valid_node_ids or edge.target not in valid_node_ids:
            dangling.append(edge)
    return dangling


def detect_self_loops(edges: list[Edge]) -> list[Edge]:
    """Detect edges where source == target (self-loops).

    Args:
    ----
        edges: List of all edges

    Returns:
    -------
        List of edges with source == target

    """
    self_loops = []
    for edge in edges:
        if edge.source == edge.target:
            self_loops.append(edge)
    return self_loops


def validate_edge_types(edges: list[Edge]) -> list[Edge]:
    """Validate edge types against allowed set.

    Args:
    ----
        edges: List of all edges

    Returns:
    -------
        List of edges with invalid type field

    """
    invalid = []
    for edge in edges:
        if edge.type not in VALID_EDGE_TYPES:
            invalid.append(edge)
    return invalid


def validate_node_hashes(nodes: list[Node]) -> list[Node]:
    """Validate node hashes are valid SHA-1 format (40 hex chars).

    Args:
    ----
        nodes: List of all nodes

    Returns:
    -------
        List of nodes with malformed hash field

    """
    invalid = []
    for node in nodes:
        if not SHA1_PATTERN.match(node.hash):
            invalid.append(node)
    return invalid

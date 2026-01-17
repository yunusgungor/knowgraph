"""Type definitions for Joern integration."""

from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple


class ExportFormat(Enum):
    """Supported CPG export formats."""
    GRAPHML = "graphml"
    JSON = "json"
    NEO4J = "neo4j"
    SARIF = "sarif"
    DOT = "dot"


class JoernEntity(NamedTuple):
    """Entity extracted from Joern CPG.

    Attributes
    ----------
        name: Entity name (e.g., function name, variable name)
        type: Entity type (definition, reference, call)
        description: Human-readable description

    """

    name: str
    type: str  # definition, reference, call, import
    description: str


@dataclass
class JoernCPG:
    """Code Property Graph from Joern.

    Attributes
    ----------
        nodes: List of CPG nodes
        edges: List of CPG edges
        metadata: CPG metadata (language, version, etc.)

    """

    nodes: list[dict]
    edges: list[dict]
    metadata: dict

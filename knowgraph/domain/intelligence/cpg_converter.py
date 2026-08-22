"""CPG Converter - converts per-file Joern entities to KnowGraph nodes.

The indexing pipeline uses directory-level CPGs queried via native Joern DSL
(see ``cpg_provider.CPGProvider``). Entity nodes are built from the resulting
``Entity`` NamedTuples; the old GraphML export/parse path was removed.
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from uuid import UUID, uuid4

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node

logger = logging.getLogger(__name__)


@dataclass
class CPGConversionResult:
    """Result of entity to KnowGraph conversion.

    Attributes
    ----------
        entity_nodes: Nodes created from CPG entities
        cpg_edges: Edges from CPG relationships (always empty for native-query path)
        chunk_node_id: Parent chunk node ID
        metadata: Conversion statistics

    """

    entity_nodes: list[Node]
    cpg_edges: list[Edge]
    chunk_node_id: UUID
    metadata: dict


class CPGConverter:
    """Converts per-file Joern entities to KnowGraph code nodes.

    Entity nodes carry the source file path and link to their parent chunk via
    hierarchy edges added by the caller (graph_builder). No CPG edges are
    produced: per-file native queries don't yield edge lists.
    """

    def convert_entities_to_graph(
        self,
        entities: list,
        chunk_node_id: UUID,
        file_path: str,
    ) -> CPGConversionResult:
        """Convert per-file native-query entities to KnowGraph nodes.

        Args:
        ----
            entities: List of Entity (name/type/description) from CPGProvider.
            chunk_node_id: Parent chunk node ID.
            file_path: Source file path (node.path).

        Returns:
        -------
            CPGConversionResult with entity nodes (cpg_edges empty).
        """
        entity_nodes = []
        seen = set()

        for ent in entities:
            name = getattr(ent, "name", "")
            etype = getattr(ent, "type", "reference")
            description = getattr(ent, "description", "")

            if not name or name in seen:
                continue
            seen.add(name)

            node = Node(
                id=uuid4(),
                hash=hashlib.sha1(f"{name}:{file_path}".encode()).hexdigest(),
                title=name[:100],
                content=description[:200],
                path=file_path,
                type="code",
                token_count=len(description.split()),
                created_at=int(time.time()),
                header_depth=None,
                header_path=None,
                chunk_id=None,
                metadata={
                    "cpg_type": etype.upper(),
                    "name": name,
                    "parent_chunk_id": str(chunk_node_id),
                    "source": "joern_cpg",
                },
            )
            entity_nodes.append(node)

        logger.info(f"✅ Entity-based CPG conversion: {len(entity_nodes)} nodes from {len(entities)} entities")

        return CPGConversionResult(
            entity_nodes=entity_nodes,
            cpg_edges=[],
            chunk_node_id=chunk_node_id,
            metadata={
                "cpg_nodes_total": len(entities),
                "cpg_nodes_created": len(entity_nodes),
                "cpg_edges_total": 0,
                "cpg_edges_created": 0,
                "conversion_rate": 0,
            },
        )

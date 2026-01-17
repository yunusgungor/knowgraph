"""Code-to-documentation linking module.

Links code entities (methods, classes) to text nodes that mention them,
creating "documented_by" edges in the knowledge graph.
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class CodeDocsLinker:
    """Link code entities to documentation that mentions them."""

    def __init__(self):
        """Initialize code-docs linker."""

    def find_documentation_links(
        self,
        graph_path: Path,
        code_entities: list
    ) -> list[dict]:
        """Find documentation references to code entities.

        Args:
            graph_path: Path to graph storage
            code_entities: List of code entities (from CodeEntityExtractor)

        Returns:
            List of edge dictionaries linking code to docs

        Example:
            [
                {
                    'source': 'code_method_authenticate',
                    'target': 'doc_node_auth_md',
                    'type': 'documented_by',
                    'context': 'The authenticate() method...'
                }
            ]
        """
        from knowgraph.infrastructure.storage.filesystem import list_all_nodes

        if not graph_path.exists():
            logger.warning(f"Graph not found at {graph_path}")
            return []

        try:
            # Load all text nodes from graph
            all_nodes = list_all_nodes(graph_path)

            if not all_nodes:
                logger.warning("No nodes found in graph")
                return []

            # Filter text/markdown nodes
            # Nodes are Node objects, not dicts
            text_nodes = []
            for n in all_nodes:
                # Access node attributes directly
                node_type = getattr(n, "type", None)
                if node_type in ["text", "markdown", "file"]:
                    text_nodes.append(n)

            logger.info(f"Found {len(text_nodes)} text nodes to search")

            # Build entity name index
            entity_index = {}
            for entity in code_entities:
                name = entity.name if hasattr(entity, "name") else entity.get("name")
                entity_type = entity.entity_type if hasattr(entity, "entity_type") else entity.get("entity_type", "unknown")

                if name:
                    entity_index[name] = {
                        "entity": entity,
                        "type": entity_type
                    }

            logger.info(f"Indexing {len(entity_index)} code entities")

            # Find mentions
            links = []

            for node in text_nodes:
                # Access node content directly
                content = getattr(node, "content", "")

                if not content:
                    continue

                # Search for entity mentions
                for entity_name, entity_info in entity_index.items():
                    # Look for mentions (case-insensitive, word boundary)
                    pattern = r"\b" + re.escape(entity_name) + r"\b"

                    matches = list(re.finditer(pattern, content, re.IGNORECASE))

                    if matches:
                        # Extract context around first mention
                        match = matches[0]
                        start = max(0, match.start() - 50)
                        end = min(len(content), match.end() + 50)
                        context = content[start:end].strip()

                        # Get node ID (UUID object, convert to string)
                        node_id = str(getattr(node, "id", ""))

                        link = {
                            "source": f"code_{entity_info['type']}_{hash(entity_name)}",
                            "target": node_id,
                            "type": "documented_by",
                            "metadata": {
                                "entity_name": entity_name,
                                "mention_count": len(matches),
                                "context": context
                            }
                        }

                        links.append(link)

            logger.info(f"Found {len(links)} code-to-docs links")
            return links

        except Exception as e:
            logger.error(f"Failed to find doc links: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return []

    def links_to_graph_format(self, links: list[dict]) -> list[dict]:
        """Convert links to KnowGraph edge format.

        Args:
            links: List of link dictionaries

        Returns:
            List of edges ready for graph insertion
        """
        graph_edges = []

        for link in links:
            edge = {
                "id": f"doclink_{hash(link['source'] + link['target'])}",
                "source": link["source"],
                "target": link["target"],
                "type": link["type"],
                "metadata": link.get("metadata", {})
            }

            graph_edges.append(edge)

        return graph_edges

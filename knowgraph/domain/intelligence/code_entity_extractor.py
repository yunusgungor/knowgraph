"""Code entity extraction from Joern CPG for KnowGraph integration.

This module extracts code entities (methods, classes, calls) from Joern CPG
and converts them into KnowGraph-compatible nodes for semantic search.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CodeEntity:
    """Represents a code entity extracted from CPG."""

    name: str
    entity_type: str  # method, class, call, import
    file_path: Optional[str]
    line_number: Optional[int]
    signature: Optional[str]
    description: str
    language: str
    metadata: dict


class CodeEntityExtractor:
    """Extract code entities from Joern CPG for graph indexing."""

    def __init__(self):
        """Initialize the code entity extractor."""

    def extract_entities(self, cpg_path: Path) -> list[CodeEntity]:
        """Extract code entities from CPG.

        Args:
            cpg_path: Path to CPG binary file

        Returns:
            List of code entities
        """
        from knowgraph.core.joern import JoernProvider
        from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

        if not cpg_path.exists():
            logger.warning(f"CPG not found at {cpg_path}")
            return []

        try:
            provider = JoernProvider()
            executor = JoernQueryExecutor(Path(provider.joern_path))

            entities = []

            # Extract methods
            method_entities = self._extract_methods(cpg_path, executor)
            entities.extend(method_entities)

            # NEW: Extract classes
            class_entities = self._extract_classes(cpg_path, executor)
            entities.extend(class_entities)

            logger.info(f"Extracted {len(method_entities)} methods and {len(class_entities)} classes ({len(entities)} total)")
            return entities

        except Exception as e:
            logger.error(f"Failed to extract entities from CPG: {e}")
            return []

    def _extract_classes(self, cpg_path: Path, executor) -> list[CodeEntity]:
        """Extract class entities from CPG.

        Args:
            cpg_path: Path to CPG binary
            executor: JoernQueryExecutor instance

        Returns:
            List of class entities
        """
        # Query for all type declarations (classes, interfaces)
        query = "cpg.typeDecl.name.l"

        try:
            result = executor.execute_query(cpg_path, query, timeout=30)

            if not result or not result.results:
                logger.warning("No classes found in CPG")
                return []

            entities = []

            for item in result.results:
                class_name = item.get("raw", "").strip()

                # Skip internal/builtin types
                if not class_name or class_name in ["<module>", "ANY"] or class_name.startswith("<"):
                    continue

                entity = CodeEntity(
                    name=class_name,
                    entity_type="class",
                    file_path=None,
                    line_number=None,
                    signature=None,
                    description=f"Class: {class_name}",
                    language="unknown",
                    metadata={}
                )

                entities.append(entity)

            logger.info(f"Extracted {len(entities)} classes from CPG")
            return entities

        except Exception as e:
            logger.error(f"Failed to extract classes: {e}")
            return []

    def _extract_methods(self, cpg_path: Path, executor) -> list[CodeEntity]:
        """Extract method entities from CPG.

        Args:
            cpg_path: Path to CPG binary
            executor: JoernQueryExecutor instance

        Returns:
            List of method entities
        """
        # Use simple Joern query - results are already parsed
        query = "cpg.method.name.l"

        try:
            result = executor.execute_query(cpg_path, query, timeout=30)

            if not result or not result.results:
                logger.warning("No methods found in CPG")
                return []

            entities = []

            # Results are already parsed as list[dict]
            # Each result: {'raw': 'method_name'}
            for item in result.results:
                method_name = item.get("raw", "").strip()

                if not method_name or method_name in ["<module>", "<init>", "<clinit>"]:
                    continue  # Skip special methods

                # Create entity with available info
                # We can't get file/line info from simple query, but that's OK for now
                entity = CodeEntity(
                    name=method_name,
                    entity_type="method",
                    file_path=None,  # Would need separate query
                    line_number=None,
                    signature=None,
                    description=f"Method: {method_name}",
                    language="unknown",  # Would need filename to infer
                    metadata={}
                )

                entities.append(entity)

            logger.info(f"Extracted {len(entities)} methods from CPG")
            return entities

        except Exception as e:
            logger.error(f"Failed to extract methods: {e}")
            return []

    def _infer_language(self, filename: str) -> str:
        """Infer programming language from filename.

        Args:
            filename: File path or name

        Returns:
            Inferred language name
        """
        if not filename or filename == "<unknown>":
            return "unknown"

        # Use os.path instead of Path for simple suffix extraction
        import os

        from knowgraph.infrastructure.indexing.code_file_detector import CodeFileDetector
        _, ext = os.path.splitext(filename)
        suffix = ext.lower()

        language = CodeFileDetector.SUPPORTED_LANGUAGES.get(suffix, "unknown")

        return language

    def entities_to_graph_nodes(self, entities: list[CodeEntity]) -> list[dict]:
        """Convert code entities to KnowGraph node format.

        Args:
            entities: List of code entities

        Returns:
            List of node dictionaries ready for graph insertion
        """
        nodes = []

        for entity in entities:
            node = {
                "id": f"code_{entity.entity_type}_{hash(entity.name + str(entity.file_path))}",
                "type": f"code_{entity.entity_type}",
                "name": entity.name,
                "content": entity.description,
                "metadata": {
                    "entity_type": entity.entity_type,
                    "file_path": entity.file_path,
                    "line_number": entity.line_number,
                    "signature": entity.signature,
                    "language": entity.language,
                    **entity.metadata
                }
            }

            nodes.append(node)

        return nodes

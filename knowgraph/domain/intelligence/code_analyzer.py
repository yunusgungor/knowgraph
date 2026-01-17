"""Code Analyzer using AST for static analysis."""

import ast
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from knowgraph.config import (
    JOERN_ENABLED,
    JOERN_FAST_LANGUAGES,
    JOERN_LANGUAGE_MAP,
    JOERN_MIN_FILE_SIZE,
)
from knowgraph.domain.intelligence.provider import Entity

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from knowgraph.core.joern import JoernCPG


class ASTAnalyzer:
    """Analyzer that uses Python AST to extract entities from code."""

    def extract_entities(self, content: str) -> list[Entity]:
        """Extract entities from code using AST.

        Handles both raw code and markdown-wrapped code blocks.
        """
        try:
            code_blocks = re.findall(r"```(?:\w+)?\n(.*?)\n```", content, re.DOTALL)
            code_to_parse = "\n".join(code_blocks) if code_blocks else content
            tree = ast.parse(code_to_parse)
            entities = []

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    entities.append(Entity(name=node.name, type="definition", description=f"Class definition: {node.name}"))
                elif isinstance(node, ast.FunctionDef):
                    entities.append(Entity(name=node.name, type="definition", description=f"Function definition: {node.name}"))
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = getattr(node, "module", "") or ""
                    for name in node.names:
                        alias = name.asname or name.name
                        entities.append(Entity(name=alias, type="reference", description=f"Imported from {module}" if module else f"Import: {name.name}"))
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            entities.append(Entity(name=target.id, type="definition", description=f"Variable definition: {target.id}"))
                elif isinstance(node, ast.Call):
                    call_name = None
                    if isinstance(node.func, ast.Name):
                        call_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        call_name = node.func.attr
                    if call_name:
                        entities.append(Entity(name=call_name, type="reference", description=f"Code call to {call_name}"))
            return entities
        except (SyntaxError, Exception):
            entities = []

            # Improved Regex Patterns for Multilingual Support
            # 1. Classes / Types (Python, JS, TS, Java, C#, Go)
            class_patterns = [
                r"(?:class|interface|type|struct)\s+(\w+)",  # Standard class/type
                r"type\s+(\w+)\s+struct",  # Go structs
                r"export\s+(?:default\s+)?(?:class|interface|type)\s+(\w+)", # JS/TS export
            ]

            for pattern in class_patterns:
                defs = re.findall(pattern, code_to_parse)
                for name in defs:
                    entities.append(Entity(name=name, type="definition", description=f"Extracted type: {name}"))

            # 2. Functions / Methods
            func_patterns = [
                r"(?:def|function|func)\s+(\w+)", # Python, JS, Go
                r"func\s+\((?:[^)]+)\)\s+(\w+)",  # Go methods: func (r Receiver) MethodName()
                r"(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|_)\s*=>", # JS/TS Arrows: const x = () =>
                r"(?:const|let|var)\s+(\w+)\s*=\s*function", # JS/TS Expressions: const x = function()
                r"(?:public|private|protected|static|async)\s+(?:[\w\[\]<>]+\s+)?(\w+)\s*\(", # Java/C#/TS methods
            ]

            for pattern in func_patterns:
                defs = re.findall(pattern, code_to_parse)
                for func_name in defs:
                    # Filter out common false positives
                    if func_name not in ["if", "for", "while", "switch", "catch"]:
                        entities.append(Entity(name=func_name, type="definition", description=f"Extracted function: {func_name}"))

            return entities


class CodeAnalyzer:
    """Unified code analyzer with hybrid AST + Joern backend."""

    def __init__(self, use_joern: bool | None = None):
        self.ast_analyzer = ASTAnalyzer()
        self.joern_provider = None
        self.use_joern =use_joern if use_joern is not None else JOERN_ENABLED

        if self.use_joern:
            try:
                from knowgraph.core.joern import JoernProvider
                self.joern_provider = JoernProvider()
                logger.info("Joern backend enabled")
            except Exception as e:
                logger.warning(f"Joern unavailable: {e}")
                self.use_joern = False

    def _detect_language(self, file_path: str) -> str | None:
        path = Path(file_path)
        extension = path.suffix.lstrip(".")
        return extension if extension in JOERN_LANGUAGE_MAP else None

    def _count_lines(self, content: str) -> int:
        lines = content.split("\n")
        return len([line for line in lines if line.strip() and not line.strip().startswith("#")])

    def _should_use_joern(self, content: str, file_path: str) -> bool:
        if not self.use_joern or not self.joern_provider:
            return False
        language = self._detect_language(file_path)
        if not language or language in JOERN_FAST_LANGUAGES:
            return False
        loc = self._count_lines(content)
        return loc >= JOERN_MIN_FILE_SIZE

    def extract_entities(self, content: str, file_path: str = "") -> list[Entity]:
        """Extract entities from code (backward compatible).

        Args:
        ----
            content: Source code content
            file_path: Optional file path for language detection

        Returns:
        -------
            List of Entity objects

        """
        entities, _ = self.extract_entities_with_cpg(content, file_path)
        return entities

    def extract_entities_with_cpg(
        self,
        content: str,
        file_path: str = ""
    ) -> tuple[list[Entity], "JoernCPG | None"]:
        """Extract entities and optionally return CPG for advanced processing.

        Args:
        ----
            content: Source code content
            file_path: Optional file path for language detection

        Returns:
        -------
            Tuple of (entities, cpg) where cpg is None if Joern not used

        """
        if self._should_use_joern(content, file_path):
            try:
                return self._extract_with_joern(content, file_path)
            except Exception as e:
                logger.warning(f"Joern failed, fallback to AST: {e}")

        if not self.joern_provider:
             return self.ast_analyzer.extract_entities(content), None

        # Fallback if logic reaches here
        return self.ast_analyzer.extract_entities(content), None

    def _extract_with_joern(
        self,
        content: str,
        file_path: str
    ) -> tuple[list[Entity], "JoernCPG"]:
        """
        Returns:
        -------
            Tuple of (entities, cpg)

        """
        assert self.joern_provider is not None, "JoernProvider must be initialized"
        import tempfile


        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / Path(file_path).name
            temp_path.write_text(content)
            cpg_path = self.joern_provider.generate_cpg(temp_path.parent)
            graphml_path = self.joern_provider.export_graphml(cpg_path)
            cpg = self.joern_provider.parse_graphml_to_cpg(graphml_path)
            joern_entities = self.joern_provider.extract_entities_from_cpg(cpg)

            # Convert JoernEntity (NamedTuple) to Entity (dataclass)
            entities = []
            for je in joern_entities:
                entities.append(Entity(
                    name=je.name,
                    type=je.type,
                    description=je.description,
                ))

            return entities, cpg

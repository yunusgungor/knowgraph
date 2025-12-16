"""Code Analyzer using AST for static analysis."""

import ast
from typing import Any

from knowgraph.domain.intelligence.provider import Entity


class ASTAnalyzer:
    """Analyzer that uses Python AST to extract entities from code."""

    def extract_entities(self, code: str) -> list[Entity]:
        """Extract classes and functions from code using AST."""
        try:
            tree = ast.parse(code)
            entities = []

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    entities.append(
                        Entity(
                            name=node.name,
                            type="class",
                            description=self._get_docstring(node) or "Class definition",
                        )
                    )
                elif isinstance(node, ast.FunctionDef):
                    entities.append(
                        Entity(
                            name=node.name,
                            type="function",
                            description=self._get_docstring(node) or "Function definition",
                        )
                    )

            return entities
        except SyntaxError:
            # Not valid Python code, return empty to let LLM handle it
            return []
        except Exception:
            return []

    def _get_docstring(self, node: Any) -> str | None:
        """Extract docstring from an AST node."""
        return ast.get_docstring(node)

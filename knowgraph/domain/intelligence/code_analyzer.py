"""Code Analyzer using AST for static analysis."""

import ast
import re

from knowgraph.domain.intelligence.provider import Entity


class ASTAnalyzer:
    """Analyzer that uses Python AST to extract entities from code."""

    def extract_entities(self, content: str) -> list[Entity]:
        """Extract entities from code using AST.

        Handles both raw code and markdown-wrapped code blocks.
        """
        try:
            entities = []

            # 1. Clean content if it's markdown-wrapped
            # Look for fenced code blocks
            code_blocks = re.findall(r"```(?:\w+)?\n(.*?)\n```", content, re.DOTALL)
            if code_blocks:
                # Merge all code blocks for analysis
                code_to_parse = "\n".join(code_blocks)
            else:
                # Assume it's raw code if no fences found
                code_to_parse = content

            tree = ast.parse(code_to_parse)
            entities = []

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    entities.append(
                        Entity(
                            name=node.name,
                            type="definition",
                            description=f"Class definition: {node.name}",
                        )
                    )
                elif isinstance(node, ast.FunctionDef):
                    entities.append(
                        Entity(
                            name=node.name,
                            type="definition",
                            description=f"Function definition: {node.name}",
                        )
                    )
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    module = getattr(node, "module", "") or ""
                    for name in node.names:
                        alias = name.asname or name.name
                        entities.append(
                            Entity(
                                name=alias,
                                type="reference",
                                description=(
                                    f"Imported from {module}" if module else f"Import: {name.name}"
                                ),
                            )
                        )
                elif isinstance(node, ast.Assign):
                    # Capture top-level variable/constant definitions
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            entities.append(
                                Entity(
                                    name=target.id,
                                    type="definition",
                                    description=f"Variable definition: {target.id}",
                                )
                            )
                elif isinstance(node, ast.Call):
                    # Extract function/class calls for referencing
                    call_name = None
                    if isinstance(node.func, ast.Name):
                        call_name = node.func.id
                    elif isinstance(node.func, ast.Attribute):
                        # Handle case like: os.path.join -> join
                        call_name = node.func.attr

                    if call_name:
                        entities.append(
                            Entity(
                                name=call_name,
                                type="reference",
                                description=f"Code call to {call_name}",
                            )
                        )

            return entities
        except (SyntaxError, Exception):
            # Not valid Python code, try generic regex fallback for other languages
            # This ensures we still get some entities for JS/TS/Go etc.
            entities = []
            # Generic class/function detection
            class_defs = re.findall(r"(?:class|interface|type)\s+(\w+)", code_to_parse)
            for c in class_defs:
                entities.append(
                    Entity(name=c, type="definition", description=f"Extracted definition: {c}")
                )

            func_defs = re.findall(r"(?:def|function|func)\s+(\w+)", code_to_parse)
            for f in func_defs:
                entities.append(
                    Entity(name=f, type="definition", description=f"Extracted definition: {f}")
                )

            return entities

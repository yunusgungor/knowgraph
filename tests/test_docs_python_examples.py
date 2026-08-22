"""Verify Python code blocks in the docs are at least well-formed.

Scans every ```python fence in the markdown docs/ + README, then:
  1. Compiles each block (catches syntax errors).
  2. Resolves its top-level ``import`` / ``from ... import`` statements by
     executing them in isolation (catches references to modules or names that
     no longer exist).

It does NOT run block bodies: they often depend on surrounding variables or
have side effects, and the goal is to catch the "this snippet no longer
matches the live API" class of rot, not to execute documentation.
"""

import ast
import re
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_FILES = [
    REPO_ROOT / "README.md",
    *(REPO_ROOT / "docs").glob("*.md"),
]

FENCE_RE = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _iter_examples():
    """Yield (label, src) for every python fence across the docs."""
    for path in DOC_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(REPO_ROOT).as_posix()
        for i, match in enumerate(FENCE_RE.finditer(text), 1):
            # Markdown nested lists indent fence bodies; normalize before parse.
            yield f"{rel}#python-block-{i}", textwrap.dedent(match.group(1))


def _top_level_imports(src: str) -> str:
    """Rebuild a snippet containing only the block's top-level imports.

    Imports nested inside functions/classes are skipped (they read lazily and
    may depend on the function's runtime context).
    """
    tree = ast.parse(src)
    lines = src.splitlines()
    picked = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            picked.extend(lines[node.lineno - 1 : node.end_lineno])
    return "\n".join(picked)


EXAMPLES = list(_iter_examples())


@pytest.mark.parametrize(("label", "src"), EXAMPLES, ids=[lbl for lbl, _ in EXAMPLES])
def test_python_block_is_valid(label, src):
    """The code block compiles and its top-level imports resolve."""
    # 1. Compile (syntax).
    ast.parse(src)
    # 2. Resolve top-level imports.
    imports = _top_level_imports(src)
    if not imports.strip():
        return
    try:
        exec(imports, {})  # noqa: S102
    except (ImportError, ModuleNotFoundError) as e:
        pytest.fail(f"{label} has a broken import: {e}")

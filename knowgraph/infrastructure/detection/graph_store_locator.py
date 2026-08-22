"""Workspace-aware graph store path resolution.

Single source of truth for "where is the graph store". Both the CLI and the MCP
server resolve graph paths here so they agree on a per-workspace location.

Priority (highest first):
1. Explicit flag passed by the caller (``--output`` / ``--graph-store``).
2. ``KNOWGRAPH_GRAPH_STORE_PATH`` env / ``.env`` (config already reads it; this
   finally wires it into the CLI).
3. ``{workspace_root}/graphstore`` — the workspace root is auto-detected via git
   root / project markers, falling back to cwd (see ``detect_project_root``).
"""

import os
from pathlib import Path

from knowgraph.config import DEFAULT_GRAPH_STORE_PATH
from knowgraph.infrastructure.detection.project_detector import detect_project_root


def resolve_workspace_root() -> Path:
    """Return the auto-detected project/workspace root (git root, markers, cwd)."""
    return detect_project_root(use_llm=False)


def resolve_graph_store(explicit: str | None = None, root_dir: Path | None = None) -> Path:
    """Resolve the graph store path for a workspace.

    Single resolver shared by the CLI and the MCP server.

    Args:
    ----
        explicit: A path supplied by the caller (e.g. ``--output`` / ``--graph-store``,
            or an MCP tool ``graph_path``). ``None`` (or empty) means "auto-discover".
        root_dir: Workspace root to resolve relative paths against. When ``None``
            (CLI), the root is auto-detected via git/markers/cwd. The MCP server
            passes its detected ``PROJECT_ROOT`` here so both agree.

    Returns:
    -------
        An absolute path. Relative paths resolve against the root, so a bare
        ``"graphstore"`` always lands inside the workspace root rather than
        whatever directory the process happened to start in.
    """
    root = resolve_workspace_root() if root_dir is None else root_dir

    # Highest priority: explicit flag, if it looks like the user really set one.
    if explicit and str(explicit).strip():
        path = Path(str(explicit).strip())
        if path.is_absolute():
            return path.resolve()
        # Relative: resolve against the root.
        return (root / path).resolve()

    # Next: env override (KNOWGRAPH_GRAPH_STORE_PATH from .env / environment).
    env_path = os.getenv("KNOWGRAPH_GRAPH_STORE_PATH")
    if env_path and str(env_path).strip():
        path = Path(env_path.strip())
        if path.is_absolute():
            return path.resolve()
        return (root / path).resolve()

    # Default: graphstore inside the root.
    return (root / DEFAULT_GRAPH_STORE_PATH).resolve()


if __name__ == "__main__":
    # ponytail: self-check — run `python -m knowgraph.infrastructure.detection.graph_store_locator`
    import tempfile

    root = resolve_workspace_root()
    assert (root / DEFAULT_GRAPH_STORE_PATH).resolve() == resolve_graph_store(None)
    assert resolve_graph_store("x") == (root / "x").resolve()
    assert resolve_graph_store(None, root_dir=root) == (root / DEFAULT_GRAPH_STORE_PATH).resolve()
    with tempfile.TemporaryDirectory() as d:
        assert resolve_graph_store(d) == Path(d).resolve()
    # env override wins over default, but explicit still wins over env
    os.environ["KNOWGRAPH_GRAPH_STORE_PATH"] = "from_env"
    assert resolve_graph_store(None) == (root / "from_env").resolve()
    assert resolve_graph_store("explicit") == (root / "explicit").resolve()
    del os.environ["KNOWGRAPH_GRAPH_STORE_PATH"]
    print("graph_store_locator self-check OK")

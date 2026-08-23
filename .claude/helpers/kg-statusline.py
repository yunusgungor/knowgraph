#!/usr/bin/env python3
"""knowgraph statusline shim (cross-platform).

Prints a compact graph summary for the Claude Code status line:
    k 12n/3e/5f v2      (node/edge/file counts, version id)
    k no graph          (graphstore not indexed yet)
Optionally appends " stale" when a git-tracked source file is newer than the
graph's manifest (mtime proxy; informative only).

Works on macOS/Linux/Windows: pure stdlib, no shell, resolves the graphstore
from KNOWGRAPH_GRAPH_STORE_PATH -> git root -> cwd.
"""

import json
import os
import subprocess
import sys


def resolve_store():
    """Mirror of knowgraph's `resolve_graph_store`: env flag, else git root."""
    env_val = os.environ.get("KNOWGRAPH_GRAPH_STORE_PATH") or ""
    if env_val:
        p = env_val
        if not os.path.isabs(p):
            p = os.path.join(os.getcwd(), p)
        return os.path.normpath(p)
    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, timeout=3,
    ).stdout.strip()
    if not root:
        root = os.getcwd()
    return os.path.join(root, "graphstore")


def git_tracked_roots():
    """Return (project_root, [relative tracked files]). Best-effort."""
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3,
        ).stdout.strip()
    except subprocess.SubprocessError:
        return None, []
    if not root:
        return None, []
    try:
        ls = subprocess.run(
            ["git", "-C", root, "ls-files", "-z"],
            capture_output=True, text=True, timeout=5,
        ).stdout
        files = [f for f in ls.split("\0") if f]
    except subprocess.SubprocessError:
        return None, []
    return root, files


def main() -> None:
    store = resolve_store()
    manifest = os.path.join(store, "metadata", "manifest.json")

    if not os.path.isfile(manifest):
        sys.stdout.write("k no graph")
        return

    try:
        with open(manifest, encoding="utf-8") as fh:
            m = json.load(fh)
    except (OSError, ValueError):
        sys.stdout.write("k no graph")
        return

    nodes = m.get("node_count", 0)
    edges = m.get("edge_count", 0)
    files = len(m.get("file_hashes", {}))
    ver = m.get("version_id", "?")
    updated = int(m.get("updated_at", 0) or 0)

    out = f"k {nodes}n/{edges}e/{files}f {ver}"

    # Stale proxy: any tracked file newer than the manifest's updated_at.
    if updated:
        root, tracked = git_tracked_roots()
        if root:
            newest = 0
            for rel in tracked:
                try:
                    mt = os.stat(os.path.join(root, rel)).st_mtime
                    newest = max(newest, mt)
                except OSError:
                    continue
            if newest > updated:
                out += " stale"

    sys.stdout.write(out)


if __name__ == "__main__":
    main()

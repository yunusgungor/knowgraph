#!/usr/bin/env python3
"""knowgraph hooks shim (cross-platform). Dispatch on argv[1].

    session-start  — print a short "KG state" block; stdout becomes
                     SessionStart context so the agent starts graph-aware.
    post-edit      — best-effort incremental re-index of the edited file via
                     `python -m knowgraph.adapters.cli.main index ...`; never
                     blocks (backgrounded), never errors.
    stop | *       — no-op (kept for symmetry; exit 0).

Pure stdlib, no shell, so it runs on macOS/Linux/Windows.
"""

import json
import os
import subprocess
import sys

INDEXABLE = {".py", ".md", ".js", ".ts", ".jsx", ".tsx", ".go",
             ".java", ".c", ".cpp", ".h", ".rs", ".sh"}


def resolve_store():
    """Mirror of knowgraph's `resolve_graph_store`."""
    env_val = os.environ.get("KNOWGRAPH_GRAPH_STORE_PATH") or ""
    if env_val:
        p = env_val if os.path.isabs(env_val) else os.path.join(os.getcwd(), env_val)
        return os.path.normpath(p)
    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, timeout=3,
    ).stdout.strip()
    if not root:
        root = os.getcwd()
    return os.path.join(root, "graphstore")


def kg_summary(store: str) -> None:
    manifest = os.path.join(store, "metadata", "manifest.json")
    if not os.path.isfile(manifest):
        print("  graph: not indexed yet (run 'knowgraph index <path>')")
        return
    try:
        with open(manifest, encoding="utf-8") as fh:
            m = json.load(fh)
    except (OSError, ValueError):
        m = {}
    n = m.get("node_count", 0)
    e = m.get("edge_count", 0)
    f = len(m.get("file_hashes", {}))
    v = m.get("version_id", "?")
    print(f"  graph: {n} nodes, {e} edges, {f} files ({v})")


def session_start() -> None:
    store = resolve_store()
    print("[knowgraph] KG state — graph-first workflow is available.")
    print(f"  store: {store}")
    kg_summary(store)
    print("  tools: knowgraph_query / batch_query / analyze_impact / analyze_call_graph")
    print("  docs:  .claude/skills/knowgraph/SKILL.md and .agent/rules/knowgraph.md")
    print("  tip:   query the graph BEFORE grepping source.")


def post_edit() -> None:
    file_path = os.environ.get("CLAUDE_TOOL_INPUT_FILE_PATH") or ""
    ext = os.path.splitext(file_path)[1]
    if not file_path or not os.path.isfile(file_path) or ext.lower() not in INDEXABLE:
        return
    if not os.path.isfile(os.path.join(resolve_store(), "metadata", "manifest.json")):
        return
    # Background best-effort re-index, never blocks the agent.
    subprocess.Popen(  # noqa: S603 - fixed argv; file_path is validated as an existing file above.
        [sys.executable, "-m", "knowgraph.adapters.cli.main",
         "index", file_path, "--incremental"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "session-start":
        session_start()
    elif cmd == "post-edit":
        post_edit()
    # stop / anything else: no-op.
    sys.exit(0)


if __name__ == "__main__":
    main()

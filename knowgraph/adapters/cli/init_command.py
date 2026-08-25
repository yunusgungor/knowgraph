"""`knowgraph init` — install the `.claude/` integration into a project.

Graft-style: the `.claude/` wiring (statusline + hooks shims, skill, settings)
and the KnowGraph MCP registration are shipped as templates **inside this
package** and written into a target project by the CLI. Idempotent:
`.claude/` owned files are overwritten deterministically; `.mcp.json` is deep-
merged preserving any other servers; the local settings file is gitignored.

Usage:
    knowgraph init [DIR]           # install into DIR (default: cwd)
    knowgraph init --dry-run [DIR] # preview what would be written
    knowgraph init --no-build [DIR] # skip auto-building the graph
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Templates — single source of truth. These are the files `init` writes.
# When you update a template here, regenerate installed copies with
# `knowgraph init <dir>` (owned files are overwritten).
# ---------------------------------------------------------------------------

SETTINGS_JSON = """\
{
  "statusLine": {
    "type": "command",
    "command": "python .claude/helpers/kg-statusline.py"
  },
  "subagentStatusLine": {
    "type": "command",
    "command": "python .claude/helpers/kg-statusline.py"
  },
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/helpers/kg-hooks.py session-start",
            "timeout": 15000
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python .claude/helpers/kg-hooks.py post-edit",
            "timeout": 20000
          }
        ]
      }
    ]
  },
  "permissions": {
    "allow": [
      "Bash(python:*)",
      "Bash(python3:*)"
    ]
  }
}
"""

STATUSLINE_PY = """\
#!/usr/bin/env python3
\"\"\"knowgraph statusline shim (cross-platform).

Prints a compact graph summary for the Claude Code status line:
    k 12n/3e/5f v2      (node/edge/file counts, version id)
    k no graph          (graphstore not indexed yet)
Optionally appends " stale" when a git-tracked source file is newer than the
graph's manifest (mtime proxy; informative only).

Works on macOS/Linux/Windows: pure stdlib, no shell, resolves the graphstore
from KNOWGRAPH_GRAPH_STORE_PATH -> git root -> cwd.
\"\"\"

import json
import os
import subprocess
import sys


def resolve_store():
    \"\"\"Mirror of knowgraph's `resolve_graph_store`: env flag, else git root.\"\"\"
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
    \"\"\"Return (project_root, [relative tracked files]). Best-effort.\"\"\"
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
        files = [f for f in ls.split("\\0") if f]
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
"""

HOOKS_PY = """\
#!/usr/bin/env python3
\"\"\"knowgraph hooks shim (cross-platform). Dispatch on argv[1].

    session-start  — print a short "KG state" block; stdout becomes
                     SessionStart context so the agent starts graph-aware.
    post-edit      — best-effort incremental re-index of the edited file via
                     `python -m knowgraph.adapters.cli.main index ...`; never
                     blocks (backgrounded), never errors.
    stop | *       — no-op (kept for symmetry; exit 0).

Pure stdlib, no shell, so it runs on macOS/Linux/Windows.
\"\"\"

import json
import os
import subprocess
import sys

INDEXABLE = {".py", ".md", ".js", ".ts", ".jsx", ".tsx", ".go",
             ".java", ".c", ".cpp", ".h", ".rs", ".sh"}


def resolve_store():
    \"\"\"Mirror of knowgraph's `resolve_graph_store`.\"\"\"
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
    subprocess.Popen(
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
"""

SKILL_MD = """\
---
name: knowgraph
description: Query the KnowGraph knowledge graph (MCP) before grepping or reading source — get code dependencies, callers, dead code, change impact, and security findings fast. Complete usage guide for all 21 tools.
---

# KnowGraph Skill — Graph First, Code Second

You are working in a repo with a **KnowGraph MCP server** available as
`knowgraph_*` tools (the graph is your long-term memory / architectural map).
This skill is the complete authoritative usage guide (21 tools); a fuller
best-practice reference lives in the repo's `.agent/rules/knowgraph.md`.

**Core rule:** before you reach for `grep`, `rg`, or open a file to understand a
code path, **query the graph**. The graph already traced imports, calls, and
dependencies — reading it once is far cheaper than re-exploring source yourself.
"Graph first, code second."

The graph is **stateless**: use fully-qualified names (`auth.py`,
`QueryEngine.query_async`), never "that file" or "it". When a path is ambiguous,
include it (`src/api/auth.py` vs `tests/api/auth.py`). All names below are exact
MCP tool names.

## 1. When to use

Consult before reading source for any task that involves: understanding how code
works, tracing who calls what, finding dead/unused code, assessing the impact of
a change, answering factual "is X true?" questions, or security review.

- **Pre-flight:** before complex ops run `knowgraph_validate`; for graph size
  `knowgraph_get_stats`; for system/LLM health `knowgraph_diagnostic`.
- **Context:** enable `enable_hierarchical_lifting=True` (default) for code,
  `lift_levels=2`; for fact-verification set `enable_grounding=True` (marks
  unverified entities with a `[grounding]` note, zero extra LLM calls); to drop
  stale conversation edges use `enable_temporal_filter=True` (batch_query only;
  grounding implies temporal filtering).
- **Naming:** precise queries with `expand_query=False` (symbols, class/function
  names); broad queries with `expand_query=True` (natural language).
- **Debugging/learning:** use `with_explanation=True`.

## 2. The 21 tools

### Build & index
- **`knowgraph_index`** — index markdown files, Git repos (GitHub/GitLab/
  Bitbucket URLs), or code directories. Params: `input_path` (alias
  `source_path`), `output_path`, `resume` (local files only), `gc` (prune
  deleted nodes + metadata), `include_patterns`/`exclude_patterns` (repos/dirs
  only, e.g. `["node_modules/*","*.lock"]`), `access_token`. Note:
  `--enable-short-unit` (SC-quote + P3 `grounded` edges) is **CLI-only** — not
  on the MCP tool.
- **`knowgraph_generate_cpg`** (Admin) — regenerate the Code Property Graph.
  `source_path` (alias `input_path`), `language` (auto), `timeout` (600s).
- **`knowgraph_export_cpg`** (Admin) — export for viz/CI. `cpg_path`,
  `output_path`, `format` (`graphml`|`dot`|`graphson`|`neo4jcsv`).
- **`knowgraph_discover_conversations`** — auto-index AI-editor conversations
  (Antigravity, Cursor, GitHub Copilot), no manual export. `editor`.

### Query & analyze
- **`knowgraph_query`** — natural-language retrieval. Params: `query` (req),
  `graph_path`, `with_explanation`, `top_k` (20), `max_hops` (4), `expand_query`,
  `max_tokens` (`LLM_MAX_INPUT_TOKENS`=32000), `enable_hierarchical_lifting` (True),
  `lift_levels` (2), `enable_grounding` (False), `api_version`, `min_api_version`.
  No `system_prompt` MCP param.
- **`knowgraph_batch_query`** — run 2+ related questions at once; shares context
  loading. Preferred for "explain the whole subsystem". Params: `queries` (req),
  `graph_path`, `top_k`, `max_hops`, `max_tokens`, `enable_hierarchical_lifting`,
  `lift_levels`, `enable_grounding`, **`enable_temporal_filter`**.
- **`knowgraph_analyze_impact`** — blast radius of changing `element`.
  `element` (req), `max_hops` (4), `graph_path`, `mode` (`semantic`|`path`).
  `path` = file-based; `semantic` = concept-based.
- **`knowgraph_analyze_call_graph`** — `analysis_type` (`validate`|`recursive`|
  `call_chain`). For `call_chain` both `method_name` (source) and `target_method`
  (target) are required.
- **`knowgraph_find_dead_code`** — methods with no callers (dominance analysis).
  `cpg_path`, `include_internal` (False), `graph_path`.
- **`knowgraph_security_scan`** — **6** CWE-mapped policies (`NoBufferOverflow`
  CWE-120, `NoCommandInjection` CWE-78, `NoSQLInjection` CWE-89,
  `NoHardcodedSecrets` CWE-798, `NoWeakCrypto` CWE-327, `NoPathTraversal`
  CWE-22). `severity_filter` (`CRITICAL`|`HIGH`|`MEDIUM`|`LOW`), `policy_names`
  (loose match), `graph_path`, `scan_type` (taint instead:
  `all`|`sql_injection`|`xss`|`command_injection`|`path_traversal`|`xxe`|`ssrf`).
  Some docs say 10; the engine ships **6** (`PolicyEngine.POLICIES`).
- **`knowgraph_joern_query`** (Advanced) — raw Joern DSL. `cpg_path` (req),
  `query` or `query_name`, `timeout` (60). No `graph_path`.
- **`knowgraph_diagnostic`** — graph store, LLM provider health, recommendations.

### State & versioning
- **`knowgraph_validate`** — real checks (`GraphValidator` FR-058): dangling
  edges, self-loops, valid edge types, SHA-1 hash integrity. Does **not** check
  manifest correctness or orphan nodes. `graph_path`.
- **`knowgraph_get_stats`** — node/edge/semantic-edge counts + files indexed.
- **`knowgraph_list_versions`** — `limit` (50).
- **`knowgraph_version_info`** — `version_id`; created-at, manifest hash,
  node/edge/file counts.
- **`knowgraph_diff_versions`** — `version1`, `version2`; node/edge/file diffs.
- **`knowgraph_rollback`** (Admin) — `version_id`, `create_backup` (True),
  `force` (False). Metadata-only; backs up first. MCP param is `force=True`;
  CLI equivalent needs `--force` in non-interactive shells.

### Bookmarks & conversations
- **`knowgraph_tag_snippet`** — save a solution/decision (Semantic Bookmarking).
  `tag` (req), `snippet` (req), `graph_path`, `conversation_id`, `user_question`.
- **`knowgraph_search_bookmarks`** — retrieve tagged snippets. `query` (req),
  `top_k` (10).
- **`knowgraph_analyze_conversations`** — trends/topics/evolution. `topic`,
  `time_window_days` (7), `graph_path`.

## 3. Parameter cheat-sheet

| Parameter | Purpose | Default | When / guidance |
|---|---|---|---|
| `top_k` | seed nodes fetched | 20 | precision 10–15; recall 30–50; broad 50+ |
| `max_hops` | traversal depth | 4 | direct 2; standard 4; deep 6–8; avoid >8 |
| `max_tokens` | LLM output cap | 4096 | focused 1500–2000; standard 4096; broad 5000+ |
| `enable_hierarchical_lifting` | include parent-dir context | True | code always; docs optional |
| `lift_levels` | dir levels to lift | 2 | Python/JS 1–2; Java/C++ 2–3 |
| `enable_grounding` | prefer graph evidence; mark unverified | False | fact-check True; exploration False |
| `enable_temporal_filter` | drop superseded-conversation edges | False | batch_query only; grounding implies it |
| `with_explanation` | show reasoning path | False | debugging always; production optional |
| `expand_query` | AI query expansion | False | natural language / vague True; symbols False |

> `system_prompt` does **not** exist as an MCP tool param (internal handler
> layer only).

## 4. Query recipes

| Recipe | Params |
|---|---|
| **Quick fact** | `top_k=10, max_hops=2` |
| **Deep analysis** | `top_k=30, max_hops=6, with_explanation=True` |
| **Conceptual search** | `expand_query=True, top_k=40` |
| **Precise lookup** | `top_k=5, max_hops=2, expand_query=False` |
| **Architecture overview** | `enable_hierarchical_lifting=True, lift_levels=3` |
| **Verified answer** | `enable_grounding=True, with_explanation=True` |

### Decision tree
| Intent | Tool |
|---|---|
| find security issues | `knowgraph_security_scan` (6 policies; `scan_type` for taint) |
| is this code used? | `knowgraph_find_dead_code` |
| who calls this function? | `knowgraph_analyze_call_graph` (`analysis_type="call_chain"`) |
| find infinite loops | `knowgraph_analyze_call_graph` (`analysis_type="recursive"`) |
| how does X work? | `knowgraph_query` |
| is this answer grounded? | `knowgraph_query` + `enable_grounding=True` |
| what if I change X? | `knowgraph_analyze_impact` |
| explain the whole system | `knowgraph_batch_query` (5–10 questions) |
| custom code query | `knowgraph_joern_query` |
| save this solution | `knowgraph_tag_snippet` |
| what did we discuss about X? | `knowgraph_search_bookmarks` |
| what changed since yesterday? | `knowgraph_diff_versions` |
| load past chats | `knowgraph_discover_conversations` |
| undo bad indexing | `knowgraph_rollback` (Admin) |
| regenerate code graph | `knowgraph_generate_cpg` (Admin) |
| export graph data | `knowgraph_export_cpg` (Admin) |

## 5. Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| Manifest not found | graph not indexed | run `knowgraph_index` first |
| Empty results `[]` | query not in graph | raise `top_k`, try `expand_query=True` |
| Hallucination | LLM invents info | `with_explanation=True` + `enable_grounding=True` |
| Rate limit (429) | too many requests | rely on RateLimiter; check API-key layer |
| Timeout | query too complex | lower `max_hops` or `top_k` |
| Joern slow | JoernDaemon warming up | first query is slower; retry |

### Health & repair flow
1. `knowgraph_diagnostic()` — system health
2. `knowgraph_validate()` — graph integrity
3. `knowgraph_index(input_path=..., gc=True)` — clean up if needed
4. `knowgraph_rollback(version_id=...)` — undo a bad index (after
   `knowgraph_list_versions`)

## 6. Workflows

**Debug a bug** — map first, then read only the needed file:
```
knowgraph_query(query="Why does AuthService session fail?", top_k=20, max_hops=3,
                enable_grounding=True, with_explanation=True)
knowgraph_analyze_impact(element="src/auth/service.py", mode="path", max_hops=4)
knowgraph_search_bookmarks(query="session timeout bug")
```

**Refactor safely** — know the blast radius before editing:
```
knowgraph_analyze_impact(element="RateLimiter", mode="semantic", max_hops=6)
knowgraph_analyze_call_graph(analysis_type="validate")
```

**Security pass**:
```
knowgraph_security_scan(severity_filter="MEDIUM")
knowgraph_analyze_call_graph(method_name="unsafe_input", target_method="db.execute",
                             analysis_type="call_chain")
knowgraph_find_dead_code()
```

**Session start / onboarding**:
```
knowgraph_discover_conversations(editor="all")
knowgraph_analyze_conversations(time_window_days=7)
knowgraph_search_bookmarks(query="recent architectural decisions", top_k=5)
knowgraph_batch_query(queries=["How does session handling work?",
                               "What calls QueryEngine.query_async?"])
```

## Gotchas (accurate to this codebase)

- `enable_temporal_filter` exists only on `knowgraph_batch_query`, not
  `knowgraph_query`; grounding on query implies temporal filtering.
- There is **no `system_prompt`** tool param (internal only).
- `knowgraph_security_scan` ships **6** policies (the tool description may say
  10 on older builds; `PolicyEngine.POLICIES` has 6).
- `knowgraph_validate` does NOT check manifest correctness or orphan nodes
  (only dangling edges, self-loops, edge types, SHA-1 hashes).
- `knowgraph_rollback` (MCP) takes a `force=True` param; CLI equivalent needs
  `--force` in non-interactive shells. Both always back up first.
- Graph store is gitignored (`graphstore/`); the statusline/hooks show "no
  graph" until you run `knowgraph index <path>` once.

## Keeping the graph fresh
The `.claude` wiring re-indexes edited source files in the background
(`kg-hooks.py post-edit`). For a large structural change or a stale graph, run
`knowgraph index <path> --incremental` (or `gc=True` to prune deletions)
explicitly. Save valuable insights with `knowgraph_tag_snippet` so future
sessions find them.
"""

MCP_SERVER_ENTRY = {
    "command": "python",
    "args": ["-m", "knowgraph.adapters.mcp.server"],
}

# Map of (relative_path, content) for the files `init` owns and overwrites.
_OWNED_FILES = (
    (".claude/settings.json", SETTINGS_JSON),
    (".claude/helpers/kg-statusline.py", STATUSLINE_PY),
    (".claude/helpers/kg-hooks.py", HOOKS_PY),
    (".claude/skills/knowgraph/SKILL.md", SKILL_MD),
)

_LOCAL_SETTINGS = ".claude/settings.local.json"
_GITIGNORE_ENTRY = ".claude/settings.local.json"


def _write_file(path: Path, content: str) -> None:
    """Write a file, creating parent dirs. Matches `_write_jvm_config` pattern."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_claude_files(target_dir: Path, dry_run: bool = False) -> list[str]:
    """Write the owned `.claude/` files. Returns list of written rel paths."""
    written = []
    for rel, content in _OWNED_FILES:
        path = target_dir / rel
        if dry_run:
            action = "create" if not path.exists() else "overwrite"
            written.append(f"  would {action:<14} {rel}")
        else:
            _write_file(path, content)
            written.append(f"  wrote          {rel}")
    return written


def merge_mcp_json(target_dir: Path, dry_run: bool = False) -> list[str]:
    """Ensure `mcpServers.knowgraph` is present; preserve other servers."""
    mcp_path = target_dir / ".mcp.json"
    data: dict = {}
    if mcp_path.exists():
        try:
            data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    servers = data.setdefault("mcpServers", {})
    if "knowgraph" in servers:
        return ["  kept           .mcp.json (mcpServers.knowgraph exists)"]
    servers["knowgraph"] = dict(MCP_SERVER_ENTRY)
    if dry_run:
        return ["  would merge    .mcp.json (add mcpServers.knowgraph)"]
    _write_file(mcp_path, json.dumps(data, indent=2) + "\n")
    return ["  merged         .mcp.json (added mcpServers.knowgraph)"]


def ensure_gitignored(target_dir: Path, dry_run: bool = False) -> list[str]:
    """Append settings.local.json to .gitignore if not present."""
    gi = target_dir / ".gitignore"
    if gi.exists() and _GITIGNORE_ENTRY in gi.read_text(encoding="utf-8", errors="ignore"):
        return [f"  kept           .gitignore (already ignores {_LOCAL_SETTINGS})"]
    if dry_run:
        return [f"  would append   .gitignore (+ {_LOCAL_SETTINGS})"]

    # Append with a leading newline only when the file is non-empty and doesn't
    # already end with one (so we never butt against the last line).
    existing = gi.read_text(encoding="utf-8", errors="ignore") if gi.exists() else ""
    content = existing
    if content and not content.endswith("\n"):
        content += "\n"
    content += _GITIGNORE_ENTRY + "\n"
    gi.write_text(content, encoding="utf-8")
    return [f"  added          .gitignore (+ {_LOCAL_SETTINGS})"]


@click.command(name="init")
@click.argument("target_dir", type=click.Path(), default=".")
@click.option("--dry-run", is_flag=True, help="Show what would be written; write nothing.")
@click.option("--no-build", is_flag=True, help="Do not build the graph after wiring.")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output.")
def init_command(target_dir: str, dry_run: bool, no_build: bool, verbose: bool) -> None:
    """Install the knowgraph `.claude/` integration into a project.

    Writes the statusline + hooks shims, the skills/SKILL.md guide, merges the
    KnowGraph MCP server into `.mcp.json`, and gitignores the local settings
    file. Idempotent: owned files are overwritten, other servers preserved.
    """
    target = Path(target_dir).expanduser().resolve()
    try:
        lines: list[str] = []
        lines += write_claude_files(target, dry_run=dry_run)
        lines += merge_mcp_json(target, dry_run=dry_run)
        lines += ensure_gitignored(target, dry_run=dry_run)

        if dry_run:
            echo_lines(target, lines, prefix="Dry run — would install into")
            return

        for ln in lines:
            click.echo(ln)
        click.echo(f"✓ Installed knowgraph .claude integration in {target}")

        if not no_build:
            gs = target / "graphstore" / "metadata" / "manifest.json"
            if not gs.exists():
                click.echo(
                    "  Next: run 'knowgraph index <path>' to build the graph "
                    "(statusline will then show counts)."
                )
            else:
                click.echo("  Graph already exists — statusline will show counts.")
    except Exception as error:  # pragma: no cover
        click.echo(f"Error: {error}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


def echo_lines(target: Path, lines: list[str], prefix: str) -> None:
    click.echo(f"{prefix} {target}")
    for ln in lines:
        click.echo(ln)

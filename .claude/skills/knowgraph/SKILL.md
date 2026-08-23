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
  `max_tokens` (`LLM_MAX_TOKENS`=4096), `enable_hierarchical_lifting` (True),
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

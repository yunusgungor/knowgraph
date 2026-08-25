# KnowGraph Configuration Guide

**Version:** 1.0.1
**Last Updated:** August 22, 2026

This document describes the configuration options for KnowGraph v1.0.1.
Configuration is **environment-driven** and read from the environment plus an
optional `.env` file at startup. Most variables are centralized as constants /
Pydantic settings in `knowgraph/config.py`; a few (API key/base URL, MCP
transport/host/port) are read directly with `os.getenv` at their point of use
(e.g. `knowgraph/adapters/mcp/server.py`).

---

## 1. Configuration Model

KnowGraph uses **Pydantic `BaseSettings`** groups, each mapped to an env prefix:

| Settings Group | Env Prefix | Class |
|----------------|-----------|-------|
| Performance | `KNOWGRAPH_PERF_` | `PerformanceSettings` |
| Memory | `KNOWGRAPH_MEMORY_` | `MemorySettings` |
| Query | `KNOWGRAPH_QUERY_` | `QuerySettings` |
| Application | `KNOWGRAPH_` | `KnowGraphSettings` |

At runtime the cached singleton is fetched via:

```python
from knowgraph.config import get_settings
settings = get_settings()          # cached
settings.query.top_k
settings.performance.max_workers
settings.memory.warning_threshold_mb
```

---

## 2. Performance Settings (`KNOWGRAPH_PERF_*`)

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `KNOWGRAPH_PERF_MAX_WORKERS` | `10` | 1–50 | Max concurrent workers for parallel processing |
| `KNOWGRAPH_PERF_CACHE_SIZE` | `1000` | 100–10000 | LRU cache size for embeddings & tokenization |
| `KNOWGRAPH_PERF_BATCH_SIZE` | `10` | 1–100 | Batch size for processing operations |

---

## 3. Memory Settings (`KNOWGRAPH_MEMORY_*`)

| Variable | Default | Description |
|----------|---------|-------------|
| `KNOWGRAPH_MEMORY_WARNING_THRESHOLD_MB` | `500` | Warn when an operation uses > this MB |
| `KNOWGRAPH_MEMORY_CRITICAL_THRESHOLD_MB` | `1000` | Error when an operation uses > this MB |
| `KNOWGRAPH_MEMORY_AUTO_GC` | `true` | Auto-trigger GC on high memory |

The memory guard that consumes these is `knowgraph.shared.memory_profiler`:

```python
from knowgraph.shared.memory_profiler import memory_guard, memory_profiled, log_memory_stats

with memory_guard(operation_name="my_op", warning_threshold_mb=200, critical_threshold_mb=500, auto_gc=True):
    ...  # memory-intensive work

@memory_profiled(warning_threshold_mb=100, critical_threshold_mb=500)
def my_fn():
    ...
```

---

## 4. Query Settings (`KNOWGRAPH_QUERY_*`)

| Variable | Default | Range | Description |
|----------|---------|-------|-------------|
| `KNOWGRAPH_QUERY_TOP_K` | `20` | 1–100 | Number of top results to return |
| `KNOWGRAPH_QUERY_MAX_HOPS` | `4` | 1–10 | Maximum graph traversal depth |
| `KNOWGRAPH_QUERY_ENABLE_QUERY_EXPANSION` | `true` | bool | Enable LLM-powered query expansion |
| `KNOWGRAPH_QUERY_TIMEOUT_SECONDS` | `30.0` | 1–300 | Retrieval-only timeout (excludes LLM synthesis) |
| `KNOWGRAPH_QUERY_ENABLE_DENSE_RETRIEVAL` | `true` | bool | Enable hybrid dense retrieval when a dense index exists |
| `KNOWGRAPH_QUERY_DENSE_SEARCH_WEIGHT` | `0.3` | 0.0–1.0 | Weight of dense cosine scores in hybrid fusion (remainder = sparse BM25) |

> **`KNOWGRAPH_QUERY_TIMEOUT_SECONDS`** bounds *retrieval only* (graph traversal, context assembly); it does **not** include LLM answer synthesis. Use `KNOWGRAPH_QUERY_TOTAL_TIMEOUT` for the whole query path.

---

## 5. General / LLM Settings (`KNOWGRAPH_*`)

| Variable | Default | Description |
|----------|---------|-------------|
| `KNOWGRAPH_LOG_LEVEL` | `INFO` | Logging level (`DEBUG/INFO/WARNING/ERROR`) |
| `KNOWGRAPH_GRAPH_STORE_PATH` | `./graphstore` | Path to graph storage directory |
| `KNOWGRAPH_LLM_MODEL` | `gpt-4o-mini` | LLM model to use |
| `KNOWGRAPH_API_KEY` | - | OpenAI/OpenRouter API key |
| `KNOWGRAPH_API_BASE_URL` | `https://api.openai.com/v1` | Custom OpenAI-compatible base URL |
| `KNOWGRAPH_LLM_RETRY_COUNT` | `5` | Max provider-internal retries (HTTP/429 errors) |
| `KNOWGRAPH_LLM_RETRY_DELAY` | `1.0` | Base backoff delay (sec) |
| `KNOWGRAPH_LLM_MAX_TOKENS` | `4096` | Max tokens the LLM may **generate** per completion (output cap) |
| `KNOWGRAPH_LLM_MAX_INPUT_TOKENS` | `32000` | Approx. max **input** tokens — model-context guard for `assemble_context` |
| `KNOWGRAPH_LLM_REQUEST_TIMEOUT` | `60` | Budget for a single `generate_text` call (whole-call: rate-limiter + HTTP + retries). Tune per provider speed. |
| `KNOWGRAPH_LLM_SYNTHESIS_TIMEOUT` | `120` | Whole-synthesis budget at MCP handler level (retries included). Must fit the MCP client's tool-call timeout. |
| `KNOWGRAPH_LLM_SYNTHESIS_RETRIES` | `2` | Handler-level retries of `_generate_llm_answer` on transient failures (timeout/empty). |
| `KNOWGRAPH_QUERY_TOTAL_TIMEOUT` | `120` | Whole-query-path budget (query-expansion + retrieval + assembly + synthesis). The real client-window guarantee. Tune per MCP client timeout. |
| `KNOWGRAPH_WORKERS` | auto (≤5) | Concurrent API requests / indexing workers |
| `KNOWGRAPH_BATCH_SIZE` | auto-tuned to RAM | LLM batch size for entity extraction |
| `KNOWGRAPH_PROJECT_ROOT` | auto-detect | Override project root detection |

> **LLM timeout hierarchy** — three nested layers (most to least granular):
>
> 1. `LLM_REQUEST_TIMEOUT` (60s, per `generate_text` call) — wraps rate-limiter + HTTP + provider retries. Can raise to 90–120s for slow/free providers.
> 2. `LLM_SYNTHESIS_TIMEOUT` (120s, whole synthesis) — wraps `_generate_llm_answer` retries. Must be ≤ `QUERY_TOTAL_TIMEOUT`.
> 3. `QUERY_TOTAL_TIMEOUT` (120s, whole query path) — wraps expansion + retrieval + synthesis. This is the real client-window guarantee. **MCP client timeout must be ≥ this value.**
>
> **For slow/free providers**: raise all three to match your MCP client's tool-call timeout. A good starting point is `KNOWGRAPH_LLM_REQUEST_TIMEOUT=90`, `KNOWGRAPH_LLM_SYNTHESIS_TIMEOUT=110`, `KNOWGRAPH_QUERY_TOTAL_TIMEOUT=115` and set your MCP client timeout to ≥120s.

---

## 6. Joern / CPG Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `KNOWGRAPH_JOERN_ENABLED` | `true` | Enable/disable Joern analysis |
| `KNOWGRAPH_JOERN_PATH` | auto-detect | Explicit Joern installation path |
| `KNOWGRAPH_JOERN_TIMEOUT` | `120` | Joern analysis/query timeout (sec) |
| `KNOWGRAPH_JOERN_DAEMON` | `true` | Run a persistent single-JVM Joern daemon (vs. per-query JVM) |
| `KNOWGRAPH_JOERN_DAEMON_BOOT_TIMEOUT` | `120` | Initial daemon JVM+REPL boot timeout (sec) |
| `KNOWGRAPH_JOERN_EXPORT_TIMEOUT` | `300` | CPG export timeout (sec) |
| `KNOWGRAPH_CPG_NODES_ENABLED` | `true` | Fold Joern CPG nodes into the graph |
| `KNOWGRAPH_CPG_NODE_TYPES` | `METHOD,CALL,TYPE_DECL,IDENTIFIER,LOCAL` | CPG node types to create graph nodes for |
| `KNOWGRAPH_CPG_NODES_ENABLED=false` | - | Keep the graph smaller (metadata-only extraction) |

**Joern daemon note:** when `KNOWGRAPH_JOERN_DAEMON=true` (default), queries run
on a long-lived REPL instead of starting a fresh JVM per query. Disable it for
one-shot environments (e.g. tests) where daemon lifecycle is undesirable.

---

## 7. MCP Server Transport

The MCP server can run over different transports via `KNOWGRAPH_MCP_TRANSPORT`:

| Variable | Default | Description |
|----------|---------|-------------|
| `KNOWGRAPH_MCP_TRANSPORT` | `stdio` | `stdio`, `http`, or `sse` |
| `KNOWGRAPH_MCP_HOST` | `127.0.0.1` | Bind host for HTTP/SSE transport |
| `KNOWGRAPH_MCP_PORT` | `8000` | Bind port for HTTP/SSE transport |

```bash
# Standard (AI editors)
knowgraph serve

# Remote HTTP MCP
KNOWGRAPH_MCP_TRANSPORT=http KNOWGRAPH_MCP_PORT=8000 knowgraph serve
```

---

## 8. `.env` File

All variables load from a `.env` file in the working directory (see
`.env.example`). Minimum working example:

```env
KNOWGRAPH_API_KEY=sk-...
KNOWGRAPH_LLM_MODEL=gpt-4o-mini
KNOWGRAPH_LOG_LEVEL=INFO
KNOWGRAPH_GRAPH_STORE_PATH=./graphstore
```

### OpenRouter example

```env
KNOWGRAPH_API_BASE_URL=https://openrouter.ai/api/v1
KNOWGRAPH_LLM_MODEL=x-ai/grok-4.1-fast
KNOWGRAPH_API_KEY=sk-or-v1-...
```

### Joern tuning example

```env
KNOWGRAPH_JOERN_DAEMON=true
KNOWGRAPH_JOERN_TIMEOUT=180
KNOWGRAPH_JOERN_ENABLED=true
```

---

## 9. Project Root Detection

KnowGraph automatically resolves the workspace root to isolate graph stores:

1. **Environment variable**: `KNOWGRAPH_PROJECT_ROOT` (highest priority)
2. **Git root**: if inside a git repository (monorepo aware)
3. **Project markers**: `pyproject.toml`, `package.json`, `Cargo.toml`
4. **Current working directory**: fallback

> **Monorepo**: use `KNOWGRAPH_PROJECT_ROOT` to force sub-project isolation; the
> git root produces a unified graph otherwise. The MCP server additionally
> refines root detection with an LLM in the background.

---

## 10. Performance Tuning Recommendations

### Worker counts
| Scenario | `KNOWGRAPH_WORKERS` |
|----------|---------------------|
| Small project (<100 files) | 5–10 |
| Medium (100–1000 files) | 15–20 |
| Large (>1000 files) | 20–30 |
| Low-memory / rate-limited | 1–5 |

> The engine caps auto-detected workers at 5 by default to avoid LLM rate
> limits (`get_optimal_workers`).

### Memory thresholds by RAM
| Environment | Warning (MB) | Critical (MB) |
|-------------|--------------|---------------|
| Docker (2GB) | 300 | 800 |
| Balanced (16GB) | 500 | 1000 |
| High-mem server (64GB) | 2000 | 5000 |

```env
KNOWGRAPH_MEMORY_WARNING_THRESHOLD_MB=300
KNOWGRAPH_MEMORY_CRITICAL_THRESHOLD_MB=800
```

### Query cache / edge loading (code-level constants)
- Query result cache: in-memory LRU, `_query_cache_max_size = 128`, TTL `300s`.
- Lazy edge loading guarded by memory_guard (`warning=200MB`, `critical=500MB`).

---

## 11. Summary

- **Defaults are production-ready.** Only customize for resource-constrained
  environments, specific performance targets, or when monitoring shows
  bottlenecks.
- All runtime config is **environment-driven** (env vars / `.env`), grouped
  under `KNOWGRAPH_`, `KNOWGRAPH_PERF_`, `KNOWGRAPH_MEMORY_`, and
  `KNOWGRAPH_QUERY_` prefixes.
- Structural tunables (concurrency within specific modules, e.g. the bookmark
  tagging batch size) remain code-level; they are documented inline in
  `knowgraph/*` sources.
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.1] - 2026-09-04

### ⚡ Performance
- **QueryEngine instance cache** (up to 4, keyed by graph path): dense indexes are loaded once and reused across MCP queries instead of being reloaded per query — repeat queries answer in ~1.5s.
- **Call graph via Joern**: call-graph extraction rewritten from code-text parsing to caller→callee method-level Joern queries, adding complete call edges (0 → 4688) and data-flow edges (0 → 100).

### 🐛 Fixes
- **`python -m knowgraph` entry point** (`knowgraph/__main__.py`): a PATH-independent way to run the CLI when the console script's `Scripts` folder is not on PATH (common on Windows after `pip install`). README Quick Start now points to the fallback.
- **Noisy reference symbols filtered**: `test_*`/`Test*` symbols, builtins (`__init__`, common params) and generic framework symbols excluded from reference edges — edge noise cut by ~27%, entity coverage 12% → 97%, orphan nodes 30% → 9%.
- **CPG/AST fallback fixed**: AST extraction now triggers when Joern's CPG returns empty entities (not only when no CPG provider exists); parallel CPG generation dropped so a single CPG yields the complete call graph.
- **Test data excluded from indexing**: `test_graphs` filtered out of the graph (test nodes 741 → 7, −99%).
- **Windows Joern support**: broken `joern-parse.bat` bypassed by invoking language-specific frontends directly with auto-detected dominant language.
- **Code index integration**: `CodeIndexIntegration` wired into the CLI `index` path for call/data-flow edges.
- **Architecture cleanups**: shared constants extracted to `_constants.py`; `LANGUAGE_MAP` re-exported from helpers (breaks circular imports); `detect_project_root_with_llm` provider injectable for testability.

### ⚙️ Configuration Simplification
- **Timeout env overrides removed**: `KNOWGRAPH_LLM_REQUEST_TIMEOUT`, `KNOWGRAPH_LLM_SYNTHESIS_TIMEOUT`, and `KNOWGRAPH_QUERY_TOTAL_TIMEOUT` are no longer configurable — timeouts are now fixed defaults (request 60s, synthesis 120s, query total 120s). README config snippets, `docs/CONFIGURATION.md`, `knowgraph_diagnostic`, and timeout error hints no longer reference the env vars.

## [1.1.0] - 2026-08-25

### 🚀 New Features
- **Hybrid Dense Retrieval**: semantic dense retrieval layer using `sentence-transformers/all-MiniLM-L6-v2` with local-hash deterministic fallback when neural model unavailable. Dense and sparse scores fused via min-max weighted sum. Backend pinned per index (`dense_meta.json`) to prevent vector-space mixing.
- **Local-Hash Deterministic Embeddings**: zero-dependency `LocalHashEmbedder` using `zlib.crc32` feature hashing over `SparseEmbedder` tokens. Always available as a fallback; never degrades to sparse-only.
- **`knowgraph-setup` command**: evolves `knowgraph-setup-joern` into a one-command installer for both Joern AND the `all-MiniLM-L6-v2` embedding model. Model pre-installs to `~/.knowgraph/models/` for offline access. `knowgraph-setup-joern` kept as compat alias.
- **`DenseEmbedder` pre-installed model loading**: loads from `~/.knowgraph/models/all-MiniLM-L6-v2` when present; Hub lazy-fallback otherwise. First-use runtime download eliminated.
- **`knowgraph-diagnostic` enhancement**: surfaces `LLM_REQUEST_TIMEOUT`, `LLM_SYNTHESIS_TIMEOUT`, `QUERY_TOTAL_TIMEOUT`, `top_k`, `max_hops`, and dense-retrieval state; recommends timeout/policy fixes for slow providers.

### 🔧 Anti-Hallucination Fixes
- **Query expansion sanitizer**: `_sanitize_expansion_terms` drops terms that look like code identifiers (camelCase/snake_case, dots, parens); keeps only generic language keywords.
- **Anti-hallucination prompt rewrite**: default system prompt demands prose ("in your own words — do not paste context verbatim"), retains KNOWN_IDENTIFIERS allowlist, drops over-restrictive "and present in the context" coupling that caused verbatim-context-echo.
- **`known_identifiers` allowlist wired through**: `entity_names` serialized from all retrieval (not just when grounding enabled); MCP handler passes `KNOWN_IDENTIFIERS` in prompt.
- **CODE/HYBRID routing fix**: when Joern code-handler returns no results, handler falls through to semantic retrieval instead of returning raw code dump.

### ⚡ LLM Resilience & Timeout Fixes
- **Whole-call LLM timeout**: `asyncio.timeout(LLM_REQUEST_TIMEOUT)` on `_chat_completion` wraps rate-limiter wait + HTTP attempts + provider retries; a slow/free provider fails fast instead of hanging ~180s.
- **Per-attempt timeout**: `asyncio.timeout(LLM_REQUEST_TIMEOUT)` in `_raw_completion` for each HTTP attempt (fail-fast on hung connections).
- **Non-retryable timeouts**: `TimeoutError` propagates immediately through the retry loop; no backoff delay on timeouts (saves the user from waiting when the endpoint is dead).
- **Whole-synthesis timeout** (`LLM_SYNTHESIS_TIMEOUT=120s`): all `_generate_llm_answer` retries bounded by one outer timeout; a cold provider degrades to raw context promptly rather than burning ~180s server-side.
- **Whole-query timeout** (`QUERY_TOTAL_TIMEOUT=120s`): bounds the entire `handle_query` compute (query expansion + retrieval + assemble_context + LLM synthesis) so the response never hangs past the MCP client window; returns `[Generation Error]` on budget exhaustion.
- **Answer synthesis retries** (`LLM_SYNTHESIS_RETRIES=2`): handler-level retry of `generate_text` on transient failures (timeout/empty) with small backoff; "first weak, second strong" inconsistency eliminated.
- **Generous defaults**: `LLM_REQUEST_TIMEOUT=60s`, `LLM_SYNTHESIS_TIMEOUT=120s`, `QUERY_TOTAL_TIMEOUT=120s` — slow/free providers get enough time to complete; these are safety nets against infinite hangs, not speed limits.
- **`KNOWGRAPH_LLM_REQUEST_TIMEOUT` env knob** for per-attempt HTTP timeout.
- **`KNOWGRAPH_LLM_SYNTHESIS_TIMEOUT` env knob** for whole-synthesis budget.
- **`KNOWGRAPH_QUERY_TOTAL_TIMEOUT` env knob** for whole-query-path budget.
- **Timeout hint in `[Generation Error]`**: when a timeout occurs, `raise KNOWGRAPH_LLM_REQUEST_TIMEOUT or use a faster endpoint` is appended.
- **`knowgraph_diagnostic` recommendations**: warns when LLM_REQUEST_TIMEOUT ≤60 for slow providers (suggests raising both server and MCP client timeout); warns when top_k <15 (suggests raising for deeper retrieval).

### ⚡ Retrieval Fixes
- **Deterministic node ordering**: `traverse_graph_reference_aware` returns `sorted(visited)` instead of raw `set`; `retrieve` (sync) collects nodes in `expanded_node_ids` order instead of `ThreadPoolExecutor(as_completed)` completion order. Same query now returns same node set/context every time.
- **`assemble_context` edges passthrough**: async path now passes `edges=active_edges` to `assemble_context` (matches sync path), enabling `ref_path_quality` to differentiate importance ties.
- **Same-file chunk cohesion** (`assemble_context`): when one chunk of a file is selected, the file's other chunks are promoted within the token budget (Phase A: best block per path; Phase B: force siblings; Phase C: fill leftovers). Large files' formula chunks no longer lost to cheaper one-off files.
- **Context budget fix**: `query()`/`query_async()` default `max_tokens` changed from `LLM_MAX_TOKENS` (4096, model output cap) to `LLM_MAX_INPUT_TOKENS` (32000, safe model-context cap) — large-file chunks (~15K tokens) now fit; extreme params no longer overflow model context.
- **`LLM_MAX_INPUT_TOKENS`** (32000, `KNOWGRAPH_LLM_MAX_INPUT_TOKENS`) is the true model-context guard for `assemble_context`.
- **Explanation data truncation**: `build_llm_prompt` caps `explanation_data` to 10K chars to prevent extreme params (top_k=40, hops=6, explanation=true) from exceeding model context limit.
- **Synthesis retry** (`LLM_SYNTHESIS_RETRIES=2`): bounded handler-level retry of `_generate_llm_answer` on transient failures (timeout/empty) with small backoff (0.5s×attempt); "first weak, second strong" inconsistency eliminated.
- **`knowgraph_query` diagnostic** surfaces: LLM request timeout, query timeout, top_k, max_hops, dense retrieval state — actionable recommendations for slow/thin-context queries.

### 🔧 Other Fixes
- `code_index_integration.py` dense index build uses append (load+add) instead of overwrite; preserves pre-existing dense entries.
- `code_index_integration.py` uses `select_dense_embedder(for_backend=...)` to maintain backend consistency with the existing dense index.
- `node.path` added to `ContextBlock` in `context_assembly.py` for same-file cohesion grouping.
- All timeout constants (`LLM_REQUEST_TIMEOUT`, `LLM_SYNTHESIS_TIMEOUT`, `QUERY_TOTAL_TIMEOUT`) configurable via env vars (`KNOWGRAPH_LLM_REQUEST_TIMEOUT`, `KNOWGRAPH_LLM_SYNTHESIS_TIMEOUT`, `KNOWGRAPH_QUERY_TOTAL_TIMEOUT`).

### 🧪 Release-Hardening (tests green again)
- **Anti-hallucination wording restored**: the default answer prompt again demands prose ("in your own words — do not paste the context verbatim") while keeping the code-snippet guidance added later; a later edit had dropped the anti-echo clause and broke the regression test.
- **Stale tests updated to v1.1.0 defaults/APIs**: `QuerySettings.timeout_seconds` (30→60s), query `max_tokens` default (3000→32000), and query-engine tests re-pinned to the single-pass retrieval methods (`retrieve_with_scores` / `retrieve_async_with_scores`, 3-tuple returns) introduced by the v1.1.0 query-pipeline optimization.
- **Test-suite portability**: conversation regression tests run via `asyncio.run` (Python 3.14 no longer auto-creates an event loop); Joern native-binary permission tests skip on Windows where POSIX execute-bit semantics don't apply.

## [1.0.1] - 2026-08-23

### ⚓ Graph Engineering: Grounding & Anti-Hallucination
- **Answer Grounding**: `enable_grounding` query flag prefers graph-evidence-backed nodes in context; generated answers are annotated with entities not found in the retrieved graph — zero extra LLM calls (`grounding_evaluator.verify_entities_in_answer`).
- **Entity Resolution**: Exact-name entity matching fast-path (from the `entity_resolver` technique) embedded in `graph_builder._sc_relations_to_edges` for resolving SC-extractor relation objects at build time.
- **Temporal Filtering**: `enable_temporal_filter` drops superseded-conversation edges before traversal; grounding implies temporal filtering.
- **SC-Quoted Extraction** (`index --enable-short-unit`): R-008 SC-quote + P3 entailment chain publiches verified relations as `grounded` graph edges (`score=0.9`, `source="sc_p3"`).
- **Version Negotiation**: MCP queries accept `api_version` / `min_api_version`; negotiation against the server registry, unsupported versions rejected up front.

### 🚀 Indexing & Storage
- Surface SC-extractor relations as grounded graph edges; relations whose object lives only inside the subject's own document are skipped (anti-fabrication).
- Reference-symbol table cached on disk to skip re-reading all existing nodes on incremental builds.
- CPG entity nodes built once per file (not per chunk); edges appended to `edges.jsonl` instead of full rewrite on incremental index.
- LLM skipped for code chunks (Joern is the code extractor); auto-tuned LLM batch size to available RAM.

### ⚡ Performance & Resilience
- Persistent single-JVM Joern daemon (`KNOWGRAPH_JOERN_DAEMON`, default on); Joern balances fixed auto-detect worker cap to avoid rate limits.
- LLM retry loop + circuit breaker in the OpenAI provider; dynamic rate limiting on all provider calls.
- Cached generated LLM answers (avoid re-billing the same question) and query-result cache invalidated on graph change.
- `MAX_TOKENS` (context cap) decoupled from `LLM_MAX_TOKENS` (output cap).

### 🔧 Fixes
- Hierarchical context lifting now applies to **async/MCP/batch queries**, not just the sync CLI path (`lift_hierarchical_context` in `_query_async_impl`).
- `batch_query_async` accepts `enable_grounding` / `enable_temporal_filter`; MCP `knowgraph_batch_query` exposes both.
- Conversation auto-linking wired (was raising `TypeError`); conversation enrichment reuses cached edges.
- Query sync path routes CODE/HYBRID/DATAFLOW through the code handler; Joern CLI-unavailable degrades safely.
- GC disabled for repository/conversation sources; version chain preserved on stats update; suffix-safe version parser.
- Graph store path resolution unified across CLI and MCP.

## [1.0.0] - 2026-01-18

### 🚀 Stability & Correctness
- **Graph Consistency**: Fixed critical issue where `knowgraph_get_stats` reported 0 edges.
- **Edge Generation**: Implemented correct Semantic and Reference edge generation for proper code graph connectivity.
- **Data Integrity**: Removed random UUID generation for edges, resolving dangling edge issues that caused `INVALID` graph states.
- **Validation**: Added `call` and `ast` to valid edge types, ensuring CPG edges pass validation.
- **Versioning**: Implemented a unified "Single Source of Truth" versioning system (`knowgraph.version`).

## [0.9.0] - 2026-01-17

### ✨ Deep Code Analysis Enhancements
- **Taint Analysis**: Improved Joern taint flow queries for better security auditing.
- **Search Capabilities**:
  - Added case-insensitive search for Joern queries.
  - Added pattern-based method search.
  - Added support for listing files, namespaces, and types.
- **Advanced Analysis**:
  - Added Variable Usage Finding and Code Slicing (Data/Control slicers).
  - Added tools to query CFG (Control Flow Graph), PDG (Program Dependence Graph), and CDG (Control Dependence Graph).
  - Added Cyclomatic Complexity and Type Hierarchy analysis.
- **Smart Routing**: Implemented intelligent routing to direct code/data-flow queries to specific handlers.

## [0.8.1] - 2026-01-17

### 🔄 CI/CD & Documentation
- **CI Pipeline**: Added Java 21 setup and `knowgraph-setup-joern` to GitHub Actions.
- **Documentation**: Major overhaul of User Guide and README. Added explicit Joern setup steps.
- **Joern Setup**: 
  - Automatically fixes permissions for executables in `joern-cli/bin`.
  - Improved CPG generation reliability and cleanup.
- **OpenSpec**: Added AI Agent OpenSpec documentation.

## [0.8.0] - 2025-12-27

### 🚀 Initial Joern Integration
- **Engine**: Introduced Code Property Graph (CPG) Engine powered by Joern.
- **New Tools**:
  - `knowgraph_security_scan`: Automated vulnerability detection.
  - `knowgraph_find_dead_code`: Reachability analysis.
  - `knowgraph_analyze_call_graph`: Call chain traceability.
- **Architecture**: Implemented Joern Daemon for high-performance querying and caching.

## [0.6.2] - 2025-12-20

### Beta Release
- **Features**: Graph versioning, time-travel debugging, and conversation intelligence.
- **Search**: FTS5-based bookmark search and indexing.
- **Health**: Added diagnostic handlers for system health checks.

## [0.5.0] - 2025-12-19

### 🤖 AI-Powered Indexing
- **Smart Graph Builder**: Moved `SmartGraphBuilder` into `graph_builder.py` for AI-assisted indexing.
- Removed unused code-analyzer methods, exception classes, and type definitions; bumped version.

## [0.2.3] - 2025-12-16

### 🔧 Fixes
- `PROJECT_ROOT` resolution now uses the current working directory.
- Bumped version.

## [0.2.2] - 2025-12-16

### 🔧 Fixes
- `retriever.py`: include the original error in the retriever error message.

## [0.2.1] - 2025-12-16

### 🔧 CI Fixes
- Resolved mypy, coverage, and linting issues.

## [0.2.0] - 2025-12-16

### 🚀 Performance Engine & CI Fixes
- Initial public release milestone: project scaffolding, repository ingestion, and CI setup.
- Fixed coverage and linting issues.

[1.0.1]: https://github.com/yunusgungor/knowgraph/compare/v1.0.0...v1.0.1

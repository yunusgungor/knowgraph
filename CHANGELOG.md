# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

# KnowGraph Architecture & Joern Integration

**Version**: 1.1.0  
**Status**: Production Ready  
**Last Updated**: August 22, 2026

---

## System Architecture Overview

KnowGraph combines **Graph RAG** with **Joern Code Property Graph** analysis for comprehensive code understanding.

```
┌─────────────────────────────────────────────────────────────┐
│                    KnowGraph System                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │   Indexing   │────────▶│    Query     │                  │
│  │   Pipeline   │         │   Pipeline   │                  │
│  └──────────────┘         └──────────────┘                  │
│         │                        │                           │
│         ▼                        ▼                           │
│  ┌──────────────────────────────────────┐                   │
│  │      Graph Storage (NetworkX)        │                   │
│  │  • Nodes: Code entities, docs        │                   │
│  │  • Edges: Relationships, flows,      │                   │
│  │           grounded, SUPERSEDES       │                   │
│  └──────────────────────────────────────┘                   │
│         │           │                  │                     │
│         ▼           ▼                  ▼                     │
│  ┌─────────────┐ ┌────────────────┐ ┌────────────────┐      │
│  │ Joern CPG   │ │ Graph Eng.     │ │  Semantic      │      │
│  │  Analysis   │ │ Claims Layer   │ │   Search       │      │
│  │             │ │ (grounding,    │ │                │      │
│  │             │ │ temporal, SC)  │ │                │      │
│  └─────────────┘ └────────────────┘ └────────────────┘      │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Graph Engineering / Claims Layer (v1.1.0)

KnowGraph ports the **Graph Engineering verification layer** —
`knowgraph.domain.claims` — to ground answers in real graph evidence with
**zero extra LLM calls** during query time.

| Module | Role | Live? |
|--------|------|-------|
| `sc_extractor` | R-008 SC-quote + P3 entailment chain: forces verbatim both-entity quotes on every extracted relation, verifies entailment before publication. | ✅ **live** — indexing (`--enable-short-unit`) |
| `unitizer` | D-1 deterministic, LLM-free sentence → self-contained subject-anchored proposition decomposition + rule edges. | ✅ **live** — called by `sc_extractor` |
| `temporal_filter` | `filter_edges_by_temporal` — drops edges sourced from superseded nodes before traversal. | ✅ **live** — retriever (`enable_temporal_filter`) |
| `temporal_resolver` | Builds `SUPERSEDES` / `CONTRADICTS` edges from claim timestamps; point-in-time queries. | ✅ **live** — post-index `build_temporal_edges` hook |
| `grounding_evaluator` | Entity-in-answer classification (`grounded` / `isolated` / `absent`) against the active subgraph. | ⚠️ **partially live** — only `verify_entities_in_answer` (MCP answer annotation). `GroundingEvaluator.evaluate_and_filter`, `RatchetLoop`, `QueryPathEvaluator` are tested-library only (no production call). |
| `entity_resolver` | Canonical entity resolution, contextual disambiguation, inspectable merges. | ❌ **dead code (production)** — no production import; tested library only. |
| `dag_planner`, `reflective_loop`, `traversal_engine` | — | ❌ dead code (kept as tested library modules, YAGNI) |

**Where it hooks in:**
- **Indexing** (`--enable-short-unit`): after LLM entity extraction, non-code
  chunks run the SC-quote + P3 chain; published relations become `grounded`
  graph edges (`score=0.9`, `source="sc_p3"`).
- **Query** (`enable_grounding`): grounded (evidence-backed) nodes are preferred
  in context ranking (×1.2 bonus, isolated ×0.5 penalty); the raw LLM answer is
  annotated with unbacked entities via `grounding_evaluator.verify_entities_in_answer`
  (annotation, never a strip).
- **Query** (`enable_temporal_filter`): `filter_edges_by_temporal` drops edges
  originating from superseded nodes before traversal.
- **Grounding implies temporal filtering** (a single evidence-awareness lever).

---

## Joern Integration Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│              Joern Integration Components                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Phase 1: Index Integration                                  │
│  ┌──────────────────────────────────────────────┐            │
│  │ CodeFileDetector → CodeIndexIntegration      │            │
│  │         ↓                    ↓                │            │
│  │   JoernProvider  →  CodeEntityExtractor      │            │
│  │         ↓                    ↓                │            │
│  │   CPG Metadata  →  Graph Storage             │            │
│  └──────────────────────────────────────────────┘            │
│                                                               │
│  Phase 2: Query Integration                                  │
│  ┌──────────────────────────────────────────────┐            │
│  │ User Query → QueryClassifier                 │            │
│  │         ↓              ↓         ↓            │            │
│  │      CODE          TEXT      HYBRID          │            │
│  │         ↓              ↓         ↓            │            │
│  │ CodeQueryHandler  Semantic   Both            │            │
│  └──────────────────────────────────────────────┘            │
│                                                               │
│  Phase 3: Code relation extraction (CodeIndexIntegration)    │
│  ┌──────────────────────────────────────────────┐            │
│  │ CallGraphExtractor → call edges              │            │
│  │ DataFlowAnalyzer → data_flow edges           │            │
│  │ CodeDocsLinker → documentation links         │            │
│  └──────────────────────────────────────────────┘            │
│                                                               │
│  Phase 4: Performance & incremental                          │
│  ┌──────────────────────────────────────────────┐            │
│  │ CPGCache → 24h caching                       │            │
│  │ IncrementalCPGUpdater → change detection     │            │
│  │ ParallelCPGGenerator → parallel CPG          │            │
│  └──────────────────────────────────────────────┘            │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Indexing Flow

```
Input Directory
    ↓
CodeFileDetector (14+ languages)
    ↓
IncrementalCPGUpdater (change detection)
    ↓
    ├─ No changes → Use cached / persisted CPG
    └─ Changes detected
        ↓
        ├─ Small repo → Single CPG
        └─ Large repo → ParallelCPGGenerator
            ↓
        JoernProvider (CPG generation)
            ↓
        CodeEntityExtractor (methods, classes)
            ↓
        CallGraphExtractor (call edges)      ─┐
        DataFlowAnalyzer (data_flow edges)    ├→ written to Graph Storage
        CodeDocsLinker (documentation links)  ─┘
            ↓
        CPGCache (24h storage)
            ↓
        Graph Storage (NetworkX)
```

### Query Flow

```
User Query
    ↓
QueryClassifier (pattern-based routing)
    ↓
    ├─ CODE → CodeQueryHandler
    │           ↓
    │       Joern Tools
    │       (security_scan, find_dead_code, etc.)
    │
    ├─ TEXT → Semantic Search
    │           ↓
    │       Vector similarity
    │
    └─ HYBRID → Both (parallel)
                ↓
            Merge results
                ↓
   [optional] enable_grounding / enable_temporal_filter
                ↓
       Grounded ranking + entity-in-answer
       verification (zero extra LLM calls)
```

---

## Module Architecture

### Phase 1: Index Integration

**CodeFileDetector**
- Purpose: Detect code files by language
- Input: Directory path
- Output: List of CodeFile objects
- Languages: 15 (Python, JS, Java, C/C++, Go, etc.)

**CodeIndexIntegration**
- Purpose: Orchestrate code analysis pipeline
- Components: All Phase 1-4 modules
- Flow: Detection → CPG → Extraction → Caching

**CodeEntityExtractor**
- Purpose: Extract methods and classes from CPG
- Input: CPG path
- Output: Entity list (methods, classes)
- Performance: ~474 entities in 30s on a small repo

**CPG Metadata**
- Purpose: Persist CPG paths for query-time use
- Storage: JSON metadata files
- Retrieval: Fast lookup by source path

### Phase 2: Query Integration

**QueryClassifier**
- Purpose: Classify query type
- Algorithm: Keyword matching + pattern recognition
- Accuracy: High (verified in `tests/test_query_integration.py`)
- Types: CODE, TEXT, HYBRID, DATAFLOW

**CodeQueryHandler**
- Purpose: Route CODE queries to Joern tools
- Tools: 4 (security_scan, joern_query, find_dead_code, call_graph)
- Execution: Async with timeout
- Performance: 2-5s per query

### Phase 3: Code Relation Extraction (CodeIndexIntegration)

These modules run during indexing (via `CodeIndexIntegration.process_code_directory`,
invoked by the MCP `knowgraph_index` tool on local directories) and **write
`call` / `data_flow` edges into the graph store**:

**CallGraphExtractor**
- Purpose: Extract function call relationships
- Input: CPG
- Output: `call` edges (caller → callee), written against real code nodes
- Used by: `code_index_integration` (index time); `knowgraph_analyze_call_graph` (query time)

**DataFlowAnalyzer**
- Purpose: Extract tainted data flows
- Algorithm: Source → Sink analysis
- Output: `data_flow` edges
- Used by: `code_index_integration` (index time); `knowgraph_security_scan` with `scan_type` (query time)

**CodeDocsLinker**
- Purpose: Link code entities to documentation
- Strategy: Name matching + proximity
- Output: Code-doc links

**JoernQueryExecutor** (query-time)
- Purpose: Execute arbitrary native Joern DSL queries on demand
- Used by: `knowgraph_joern_query`, `knowgraph_security_scan` (policy scan)
- Backed by the persistent Joern daemon (`KNOWGRAPH_JOERN_DAEMON`)

### Phase 4: Performance & Incremental

**CPGCache**
- Purpose: Cache generated CPGs
- Validity: 24 hours
- Storage: ~/.knowgraph/cpg_cache/
- Benefit: <1s re-indexing

**IncrementalCPGUpdater**
- Purpose: Detect file changes (added/modified/deleted)
- Algorithm: change detection over code files
- Output: skip CPG regeneration when unchanged

**ParallelCPGGenerator**
- Purpose: Generate CPGs in parallel (large / multi-language repos)

**JoernDaemon**
- Purpose: Persistent single-JVM Joern REPL (avoids per-query JVM boot)
- Flag: `KNOWGRAPH_JOERN_DAEMON` (default `true`)
- Disable for one-shot environments (e.g. tests)

> The CLI `knowgraph index` path (`run_index` → `SmartGraphBuilder`) folds CPG
> **entity nodes** + `hierarchy` edges into the graph but does **not** emit CPG
> `call`/`data_flow` edges; those are produced by the MCP `knowgraph_index`
> code-analysis stage (`CodeIndexIntegration`). The stored CPG is available for
> query-time native Joern queries in both cases.

---

## Performance Characteristics

### Indexing Performance

Typical values for a small project (~9 files); scale with project size.

| Metric | Value | Notes |
|--------|-------|-------|
| Code detection | <1s | 14+ languages |
| CPG generation | 20-30s | small project |
| Entity extraction | 5-10s | ~474 entities on a small repo |
| **Total (first run)** | **~30s** | Full analysis |
| **Total (cached)** | **<1s** | Incremental |

> Call-graph and data-flow extraction runs as part of the **code-analysis
> indexing stage** (`CodeIndexIntegration`, MCP `knowgraph_index` on local
> directories); security/Joern tool queries are **query-time** over the stored
> CPG — see [Phase 3](#phase-3-code-relation-extraction-codeindexintegration).

### Query Performance

| Query Type | Time | Notes |
|------------|------|-------|
| CODE | 2-5s | Joern execution |
| TEXT | <1s | Semantic search |
| HYBRID | 2-5s | Parallel execution |

### Memory Usage

| Component | Memory | Notes |
|-----------|--------|-------|
| CPG | 50-100MB | Per project |
| Graph | 10-50MB | NetworkX |
| Cache | 100-500MB | 24h retention |

---

## Scalability

### Horizontal Scaling

- **Parallel CPG Generation**: Multi-language projects
- **Concurrent Queries**: Async execution
- **Distributed Caching**: Shared cache layer (future)

### Vertical Scaling

- **Incremental Updates**: Only changed files
- **Lazy Loading**: On-demand entity extraction
- **Smart Caching**: 24h CPG retention

---

## Security Considerations

### Data Flow Analysis

- **Taint Tracking**: User input → Dangerous sinks
- **Vulnerability Detection**: SQL injection, XSS, command injection
- **Path Analysis**: Complete flow paths

### Code Analysis

- **Static Analysis**: No code execution
- **Sandboxed**: Joern runs in isolated process
- **Read-only**: No code modification

---

## Integration Points

### MCP Server

The MCP tools are thin wrappers over handlers (`knowgraph/adapters/mcp/handlers/`)
registered via `@app.tool` in `server.py`.

```python
# Index (methods.index_graph is the live implementation behind knowgraph_index)
await methods.index_graph(
    input_path=path,
    graph_path=graph,
    provider=provider,
    resume_mode=False,
    gc=True,
)

# Query (handler behind knowgraph_query)
from knowgraph.adapters.mcp.handlers.query import handle_query

result = await handle_query(
    {"query": query_text, "graph_path": str(graph_path)},
    provider,
    project_root,
)
```

### Direct API

```python
# Code analysis
from knowgraph.infrastructure.indexing.code_index_integration import CodeIndexIntegration

integration = CodeIndexIntegration()
result = integration.process_code_directory(source_dir, graph_dir)

# Query routing
from knowgraph.application.query.code_query_handler import CodeQueryHandler
from knowgraph.application.query.query_classifier import QueryClassifier, QueryType

classifier = QueryClassifier()
query_type = classifier.classify(query)

if query_type == QueryType.CODE:
    handler = CodeQueryHandler(graph_path)
    result = await handler.handle(query)
```

---

## Testing Architecture

The project has an extensive test suite (`tests/`, 800+ tests) covering graph
building, query engine (sync + async), retrieval, traversal, grounding
(`test_grounding_evaluator.py`, `test_entity_resolver.py`, `test_sc_extractor.py`),
temporal filtering (`test_temporal_edges.py`, `test_temporal_resolver.py`), claims
unitizer (`test_claims_unitizer.py`), versioning, conversation linking, security /
taint analysis, MCP e2e, and resilience (circuit breaker, throttling).

Key suites include `test_integration_full.py`, `test_e2e_simple.py`,
`test_query_integration.py`, `test_grounding_evaluator.py`, and
`test_mcp_e2e.py`.

---

## Deployment Architecture

### Production Setup

```
┌─────────────────────────────────────────┐
│         Application Layer               │
│  (Claude Desktop, Cursor, etc.)         │
└─────────────────┬───────────────────────┘
                  │ MCP Protocol
┌─────────────────▼───────────────────────┐
│         KnowGraph MCP Server            │
│  • Query routing                        │
│  • Index management                     │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│      Core Processing Layer              │
│  • Joern integration (13 modules)       │
│  • Graph algorithms (NetworkX)          │
│  • Semantic search                      │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│         Storage Layer                   │
│  • Graph DB (NetworkX + SQLite)         │
│  • CPG Cache (~/.knowgraph/cpg_cache/)  │
│  • Metadata (JSON)                      │
└─────────────────────────────────────────┘
```

---

## Future Enhancements

### Planned Features

- **Distributed CPG Generation**: Multi-machine processing
- **Real-time Updates**: Watch mode for file changes
- **ML-based Classification**: Enhanced query routing
- **Custom Security Rules**: User-defined vulnerability patterns
- **Call Graph Visualization**: Interactive graph rendering

### Performance Optimizations

- **Streaming CPG**: Process large files incrementally
- **Delta CPG**: Only analyze changed functions
- **Persistent Daemon**: ✅ *implemented* — single-JVM Joern daemon
  (`KNOWGRAPH_JOERN_DAEMON`, default on)
- **Query Caching**: ✅ *implemented* — LLM answer cache + query-result cache
  (both invalidated on graph change)

---

## Conclusion

KnowGraph's architecture combines:
- ✅ Graph theory (NetworkX)
- ✅ Static analysis (Joern CPG)
- ✅ Semantic search (embeddings)
- ✅ Smart caching (performance)
- ✅ Incremental updates (efficiency)
- ✅ Answer grounding (Graph Engineering claims layer)

**Result**: Production-ready system with a large, actively maintained test
suite (graph, query, grounding, Joern, MCP, resilience) covering the full
indexing → storage → query → grounding pipeline.

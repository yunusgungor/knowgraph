# 🏗️ KnowGraph Architecture and Technical Details

This document contains in-depth architectural design, working principles, and technical details of KnowGraph (v0.6.0).

> **Main Documentation**: See [README.md](../README.md) for installation and quick start.

## 📖 Table of Contents

1. [Core Concepts](#-core-concepts)
2. [Version Control Subsystem (NEW)](#-version-control-subsystem)
3. [Automation Pipeline (NEW)](#-automation-pipeline)
4. [Advanced Graph Algorithms](#-advanced-graph-algorithms)
5. [Conversational Knowledge Graph](#-conversational-knowledge-graph)
6. [Security Subsystem](#-security-subsystem)
7. [Observability & Resilience](#-observability-resilience)
8. [Storage and Persistence Strategy](#-storage-persistence)
9. [Layered Architecture](#-layered-architecture)

---

## 🧬 Core Concepts

### Node Model

Each node represents a piece of information in the knowledge graph:

```python
@dataclass(frozen=True)
class Node:
    id: UUID                    # Unique identifier
    hash: str                   # SHA-1 content hash
    title: str                  # Chunk title
    content: str                # Full content
    type: NodeType              # "code", "text", "readme", "config", "conversation_snippet"
    metadata: dict              # Flexible metadata
```

### Edge Model

Edges represent relationships with semantic weights and types:

```python
@dataclass(frozen=True)
class Edge:
    source: UUID
    target: UUID
    type: EdgeType              # "semantic", "import", "call", "inherit", "mention"
    score: float                # 0.0 to 1.0
    metadata: dict              # e.g., line numbers
```

---

## 🔄 Version Control Subsystem (v0.6.0)

KnowGraph implements a custom version control system tailored for knowledge graphs, utilizing a **Snapshot-based Manifest** approach.

### 1. Manifest Structure
The state of the graph is tracked in a `manifest.json` file.

```json
{
  "versions": [
    {
      "id": "v0.6.0-a1",
      "timestamp": 1702982400,
      "author": "system",
      "message": "Initial index",
      "stats": {
        "node_count": 150,
        "edge_count": 450
      },
      "checksum": "sha256:..."
    }
  ],
  "current_head": "v0.6.0-a1"
}
```

### 2. Diff Algorithm (Set Difference)
The `GraphDiffer` component calculates the delta between two version snapshots ($V_1$ and $V_2$) using set theory operations on Node IDs and Hashes.

Let $N(V)$ be the set of nodes in version $V$.

*   **Added Nodes**: $N_{added} = N(V_2) \setminus N(V_1)$
*   **Deleted Nodes**: $N_{deleted} = N(V_1) \setminus N(V_2)$
*   **Modified Nodes**: $N_{modified} = \{ n \in N(V_1) \cap N(V_2) \mid hash(n, V_1) \neq hash(n, V_2) \}$

This ensures $O(n)$ complexity for generating diff reports.

### 3. Rollback Mechanism (Atomic Transaction)
Rollback operations are treated as critical transactions to prevent data corruption.

1.  **Lock**: Acquire write lock on GraphStore.
2.  **Verify**: Check target version integrity (checksum).
3.  **Restore**:
    *   Reload nodes/edges from the target snapshot.
    *   Rebuild Sparse Index (TF-IDF).
    *   Limit Cache validation to target timestamp.
4.  **Prune**: Remove subsequent versions from Manifest (if hard rollback).
5.  **Release**: Release lock.

---

## 🔗 Automation Pipeline (v0.6.0)

KnowGraph employs an **Event-Driven Architecture** for post-indexing tasks.

### Architecture

```
[ Indexing Engine ]
       │
       ▼
[ Event Bus ]  <-- (Publishes: INDEXING_COMPLETE)
       │
       ├──> [ Hook: ConversationLinker ]
       │        │
       │        └─> (Regex/Semantic Search) -> Create "mentions" edge
       │
       ├──> [ Hook: AutoTagger ]
       │        │
       │        └─> (LLM Classification) -> Add tags to metadata
       │
       └──> [ Hook: AnalyticsGenerator ]
                │
                └─> (Graph Stats) -> Update dashboard
```

### Hook Lifecycle
Each hook implements a standard interface:
1.  `setup()`: Prepare resources (e.g., load models).
2.  `execute(event)`: Run the logic (async).
3.  `teardown()`: Cleanup.

---

## 🧠 Advanced Graph Algorithms

### 1. Edge-Type Aware Centrality
Standard PageRank treats all links equally. We use a **Weighted PageRank** where edge types heavily influence the score.

$$ PR(u) = (1-d) + d \sum_{v \in B(u)} \frac{PR(v) \cdot W(v,u)}{OutDegree(v)} $$

Where $W(v,u)$ is the weight based on edge type:
*   `inherit`: 1.5 (Structural backbone)
*   `call`: 1.0 (Functional flow)
*   `import`: 0.8 (Dependency)
*   `semantic`: 0.5 (Looser relation)

### 2. Reference-First Traversal
During query expansion (BFS), neighbors are prioritized not just by edge weight, but by explicit code references.

*   **Heuristic**: If Node A has a Docstring `@see Node B`, the edge $A \to B$ gets a priority boost (+2.0), ensuring documentation links are followed before generic semantic matches.

### 3. Hierarchical Context Lifting
When a node is retrieved, we "lift" context effectively:

1.  Identify Node Path (`src/api/auth.py`)
2.  Traverse up $K$ levels (`src/api/`, `src/`).
3.  Fetch `README.md` or `__init__.py` from each level.
4.  Summarize (if too large) and prepend to the Context Window.

This provides the LLM with the "architectural intent" of the module.

---

## 💬 Conversational Knowledge Graph

We model conversations as first-class citizens in the graph.

### Snippet Node
*   **Type**: `conversation_snippet`
*   **Content**: The AI's response or user's question.
*   **Metadata**: `original_conversation_id`, `timestamp`, `tags`.

### Linking Strategy
How do we connect Chat to Code?

1.  **Explicit References**: If chat contains file paths (`src/main.py`), create a hard link.
2.  **Semantic Overlap**: Embedding similarity between Chat Embedding and Code Embedding. If $Similarity > 0.85$, create a `semantic` edge.

---

## 🛡️ Security Subsystem

KnowGraph limits access to the filesystem strictly to prevent "Path Traversal" attacks.

### 1. Allowed Parent Directory Check
Every file access is validated against the **Project Root**.
- **Rule**: `Realpath(TargetFile)` must start with `Realpath(ProjectRoot)`.
- **Implementation**: `knowgraph.shared.security.validate_path(path)`.
- **Prevention**: Prevents indexing `../../etc/passwd` or accessing files outside the workspace.

### 2. Input Sanitization
AQL (Graph Query Language) inputs and CLI arguments are sanitized to prevent injection attacks during system calls (e.g., git commands).

---

## 👁️ Observability & Resilience (v0.6.0)

KnowGraph is designed to be "Glass Box", not "Black Box".

### 1. Prometheus-Style Metrics
The system emits structured metrics for monitoring:
- `knowgraph_indexing_duration_seconds`: Histogram
- `knowgraph_query_latency_seconds`: Histogram
- `knowgraph_active_requests`: Gauge
- `knowgraph_circuit_breaker_state`: Gauge (0=Closed, 1=Open)

### 2. Tracing Spans
Major operations (Indexing, Querying, Expansion) are wrapped in **Tracing Spans**.
- **Trace ID**: Propagated through async calls.
- **Attributes**: `user_id`, `query_hash`, `hop_count`.
- **Mock Support**: For testing, spans emit events that can be verified without a running Jaeger instance.

### 3. Enterprise Resilience Patterns
Located in `knowgraph/shared/`:

*   **Circuit Breaker**: 
    - *Closed*: Normal.
    - *Open*: Fails fast after $N$ errors.
    - *Half-Open*: Probes dependency with limited traffic.
*   **Token Bucket Rate Limiter**: 
    - Per-user/Per-IP limits.
    - Allows burst traffic (e.g., initial page load).
*   **Adaptive Throttling**: 
    - Monitors CPU/Memory.
    - Queues requests when load > Threshold.

---

## 8. Storage and Persistence Strategy

### 1. Temporary Index Lifecycle
To ensure consistency during long-running indexing operations, KnowGraph uses a **Two-Phase Commit** strategy:
1.  **Staging**: New nodes and edges are written to a `temporary_index` directory alongside the main database.
2.  **Commit**: Upon successful completion, the staging files overwrite the production files atomically.
3.  **Cleanup**: A dedicated cleanup routine ensures `temporary_index` folders are deleted even if the process crashes (on next run).

### 2. Cache Versioning
The `CacheManager` implements schema versioning. If the internal schema changes (e.g., newer embedding model), the cache is automatically invalidated or migrated to prevent loading incompatible data.

---

## 9. Layered Architecture

```
knowgraph/
├── domain/                          # Core Logic
│   ├── models/ (Node, Edge, VersionManifest)
│   └── algorithms/ (PageRank, Traversal, Diff)
│
├── application/                     # Orchestration
│   ├── versioning/ (VersionManager, RollbackService)
│   ├── automation/ (HookManager, EventBus)
│   └── querying/ (QueryEngine)
│
├── infrastructure/                  # Adapters
│   ├── storage/ (FileSystem, JSONL)
│   ├── intelligence/ (OpenAI, MCP)
│   └── hooks/ (Linker, Tagger implementations)
│
└── adapters/                        # Interface
    ├── cli/
    └── mcp/
```

This strict separation ensures that adding a new feature (like Versioning) doesn't break existing logic (like Querying).

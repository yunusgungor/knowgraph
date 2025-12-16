# 🏗️ KnowGraph Architecture and Technical Details

This document contains in-depth architectural design, working principles, and technical details of KnowGraph.

> **Main Documentation**: See [README.md](../README.md) for installation and quick start.

## 📖 Table of Contents

- [Core Concepts](#-core-concepts)
- [Architecture](#-architecture)
- [How It Works](#-how-it-works)
- [Advanced Usage](#-advanced-usage)
- [Performance](#-performance)
- [Troubleshooting](#-troubleshooting)
- [API Reference](#-api-reference)
- [Development and Testing](#-development-and-testing)

---

## 🧬 Core Concepts

### Node Model

Each node represents a piece of information in the knowledge graph:

```python
@dataclass(frozen=True)
class Node:
    # Identity
    id: UUID                    # Unique identifier
    hash: str                   # SHA-1 content hash (40 characters)
    
    # Content
    title: str                  # Chunk title
    content: str                # Full content
    path: str                   # Source file path
    
    # Metadata
    type: NodeType              # "code", "text", "readme", "config"
    token_count: int            # Token count calculated with Tiktoken
    created_at: int             # Unix timestamp
    
    # Hierarchy (optional)
    header_depth: int | None    # H1-H4 level (1-4)
    header_path: str | None     # Breadcrumb (e.g., "H1 > H2 > H3")
    line_start: int | None      # Start line
    line_end: int | None        # End line
```

**Node Types and Role Weights:**

| Type | Weight | Usage |
|------|--------|-------|
| `code` | 0.9 | Sections containing code blocks |
| `config` | 0.8 | Configuration files |
| `readme` | 0.7 | Documentation |
| `text` | 0.6 | Plain text content |

### Edge Model

Edges represent relationships between nodes:

```python
@dataclass(frozen=True)
class Edge:
    source: UUID                # Source node
    target: UUID                # Target node
    type: EdgeType              # "semantic"
    score: float                # Relationship strength [0.0, 1.0]
    created_at: int             # Unix timestamp
    metadata: dict[str, str]    # Additional information
```

**Edge Types:**
- `semantic`: Relationships between entities extracted by AI

### Graph Properties

- **Directed**: Edges are directional (source → target)
- **Weighted**: Each edge has a score value between 0-1
- **Dynamic**: Can be updated with incremental updates
- **Persistent**: Stored on disk in JSONL format

### Scoring Formulas

#### Node Importance Score

```
importance = α·similarity + β·centrality + γ·is_seed
```

- **α (ALPHA)**: 0.6 - Similarity weight
- **β (BETA)**: 0.3 - Centrality weight
- **γ (GAMMA)**: 0.1 - Seed node bonus weight

**Additional Factors:**
- **Role Weight**: Multiplier based on node type (0.6-0.9)
- **Token Penalty**: Penalty for long content (max 10%)

#### Centrality Composite Score

```
composite = w₁·betweenness + w₂·degree + w₃·closeness + w₄·eigenvector
```

- **w₁**: 0.5 - Betweenness (architectural boundaries)
- **w₂**: 0.2 - Degree (API surface)
- **w₃**: 0.2 - Closeness (accessibility)
- **w₄**: 0.1 - Eigenvector (importance)

## 🏗️ Architecture

KnowGraph has a 4-layer structure designed with Clean Architecture principles:

```
knowgraph/
├── domain/              # Business logic and algorithms
│   ├── models/         # Core data models (Node, Edge, Graph)
│   ├── algorithms/     # Graph algorithms (traversal, centrality)
│   └── intelligence/   # AI provider interfaces
├── application/         # Use cases and orchestration
│   ├── indexing/       # Graph building and indexing
│   ├── querying/       # Query engine and retrieval
│   ├── evolution/      # Incremental updates
│   └── export/         # Data export utilities
├── infrastructure/      # External dependencies
│   ├── storage/        # Filesystem operations
│   ├── parsing/        # Markdown parsing
│   ├── embedding/      # Sparse embeddings (TF-IDF)
│   ├── intelligence/   # LLM providers (OpenAI, etc.)
│   └── search/         # Vector search
└── adapters/           # External interfaces
    ├── cli/            # Command-line interface
    ├── mcp/            # MCP server implementation
    └── api/            # REST API (future)
```

## 🤖 MCP Server Architecture

KnowGraph's MCP (Model Context Protocol) implementation operates as an isolated layer under the `adapters/mcp` module. This layer acts as a bridge between AI editors (Claude, Cursor) and KnowGraph's core domain logic.

### 1. Server Lifecycle
*   **Initialization**: The `mcp.server.Server` class is initialized.
*   **Capabilities**: The server declares its capabilities for resource reading (`read_resource`) and tool calling (`call_tool`).
*   **Connection**: Communicates via standard input/output (stdin/stdout) using `stdio_server`.

### 2. Tool Definitions

The MCP server exposes the following tools to the outside world:

| Tool Name | Description | Critical Parameters |
| :--- | :--- | :--- |
| **`knowgraph_query`** | Performs semantic search on the knowledge graph. | `query`, `top_k`, `max_hops`, `with_explanation`, `expand_query` |
| **`knowgraph_index`** | Indexes Markdown files. | `input_path`, `resume` (continue from checkpoint), `gc` (garbage collection) |
| **`knowgraph_analyze_impact`** | Performs change impact analysis. | `element` (file/concept), `mode` ("path"/"semantic"), `max_hops` |
| **`knowgraph_validate`** | Validates database consistency. | `graph_path` |
| **`knowgraph_get_stats`** | Provides statistical summary. | `graph_path` |
| **`knowgraph_batch_query`** | Processes multiple queries in a single batch. | `queries` (list), other query parameters... |

### 3. Request Flow Diagram

The journey of an MCP request within the system is as follows:

1.  **Client (AI Editor)**: Sends a `call_tool("knowgraph_query", {...})` request in JSON-RPC format.
2.  **Adapter Layer (`server.py`)**: Intercepts the request and validates parameters.
3.  **Protocol Safety**: Uses `contextlib.redirect_stdout(sys.stderr)` to prevent `print` outputs from the domain layer from corrupting the JSON stream.
4.  **Application Layer (`QueryEngine`)**: Routes the request to business logic.
5.  **Infrastructure Layer (`NetworkX`, `FS`)**: Reads the graph from disk and runs traversal algorithms.
6.  **Response**: The result is packaged into a `TextContent` object and returned to the client.

### 4. Security and Isolation

*   **Path Validation**: All file path arguments are checked with `knowgraph.shared.security.validate_path` to prevent path traversal attacks (ensuring safety outside the project root).
*   **Error Handling**: Domain errors are caught and converted into MCP protocol-compliant error messages, preventing server crashes.

## 🔬 How It Works

### Indexing Pipeline

KnowGraph transforms markdown files into a knowledge graph in 5 steps:

1. **Parse Headers**: Splits into sections based on H1-H4 headers.
2. **Smart Chunking**: Token-aware chunking preserving logical boundaries.
3. **Entity Extraction**: Extracts important nodes (functions, classes) using LLM.
4. **Build Graph**: Creates semantic edges based on entity overlap.
5. **Persist to Disk**: Saves in JSONL format.

### Query Pipeline

A query becomes an answer in 8 steps:

1. **Query Expansion** (Optional): Enriches the query (e.g., "login fail" -> "auth error").
2. **Sparse Search**: Finds most relevant seed nodes using TF-IDF.
3. **Graph Traversal**: Explores related nodes via BFS (max_hops).
4. **Centrality Analysis**: Calculates node importance (betweenness, etc.) using NetworkX.
5. **Node Scoring**: Combines similarity and centrality scores.
6. **Context Assembly**: Selects top nodes fitting the token limit.
7. **LLM Response**: Sends context to LLM for answer generation.
8. **Explanation**: Generates source references and reasoning paths.

### Hierarchical Lifting

Adds folder structure to the context, enabling the LLM to understand project hierarchy. For instance, when querying `authentication.md`, summaries of `api/README.md` and `docs/README.md` are added to the context.

## 🚀 Advanced Usage

### Custom Intelligence Providers

You can create your own LLM provider (e.g., local model, custom API).

```python
from knowgraph.domain.intelligence.provider import IntelligenceProvider, Entity

class CustomProvider(IntelligenceProvider):
    async def extract_entities(self, content: str) -> list[Entity]:
        # Implementation...
        pass
    
    async def generate_response(self, query: str, context: str, system_prompt: str = "") -> str:
        # Implementation...
        pass
```

### Query Optimization Strategies

- **Precision-Focused**: `top_k=10`, `max_hops=2`, `expand_query=False`. Fast and precise.
- **Recall-Focused**: `top_k=50`, `max_hops=8`, `expand_query=True`. Comprehensive but slower.
- **Balanced**: `top_k=20`, `max_hops=4`, `with_explanation=True`. Default balanced setting.

## 📊 Performance

### Benchmarks

| Metric | Value | Description |
|--------|-------|-------------|
| **Indexing Speed** | ~100 files/min | Average markdown files |
| **Query Latency** | <2s | Sparse search + traversal + centrality |
| **Memory Usage** | <500MB | For a graph with 10K nodes |

## 🔧 Troubleshooting

### Common Issues

- **Empty Results**: Increase `top_k` or `max_hops`, try `expand_query=True`.
- **Slow Queries**: Decrease `max_hops`, disable `hierarchical-lifting`.
- **Hallucination**: Use `with_explanation=True` to verify sources.
- **No Manifest Found**: Run `knowgraph index`.

## 📖 API Reference

### QueryEngine

```python
engine = QueryEngine(graph_store_path=Path("./graphstore"))
result = engine.query(
    query_text="Question...",
    top_k=20,
    max_hops=4,
    with_explanation=True
)
```

### SmartGraphBuilder

```python
builder = SmartGraphBuilder(provider)
await builder.build_from_directory(Path("./docs"))
```

## 🛠️ Development and Testing

```bash
# Setup dev environment
pip install -e ".[dev]"
pre-commit install

# Run tests
pytest
pytest --cov=knowgraph
```

The project adheres to **100% mypy strict mode** and **Clean Architecture** principles.

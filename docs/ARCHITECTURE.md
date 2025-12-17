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
├── domain/                          # Business logic and algorithms (Core Layer)
│   ├── models/                     # Core data models
│   │   ├── node.py                # Node data model
│   │   └── edge.py                # Edge data model
│   ├── algorithms/                 # Graph algorithms
│   │   ├── traversal.py           # Graph traversal (BFS/DFS)
│   │   ├── centrality.py          # Centrality calculations (PageRank, Betweenness)
│   │   ├── graph_validator.py     # Graph validation and consistency checks
│   │   └── success_criteria.py    # Success metrics and evaluation
│   └── intelligence/               # AI provider interfaces
│       ├── provider.py            # IntelligenceProvider abstract class
│       └── code_analyzer.py       # AST-based code analysis (ASTAnalyzer)
│
├── application/                     # Use cases and orchestration
│   ├── indexing/                   # Graph building and indexing
│   │   └── smart_graph_builder.py # Hybrid indexing engine (SmartGraphBuilder)
│   ├── querying/                   # Query engine
│   │   ├── query_engine.py        # Main query engine (QueryEngine, QueryResult)
│   │   ├── retriever.py           # Graph traversal and node collection (QueryRetriever)
│   │   ├── context_assembly.py    # Context building (ContextBlock)
│   │   ├── query_expansion.py     # Query expansion (QueryExpander)
│   │   ├── explanation.py         # Explanation generation (ReasoningPath, ExplanationObject)
│   │   └── impact_analyzer.py     # Impact analysis (ImpactAnalysisResult)
│   ├── evolution/                  # Incremental updates
│   │   └── incremental_update.py  # Delta analysis (DeltaAnalysis)
│   └── export/                     # Data export utilities
│       └── graph_exporter.py      # Export to NetworkX, JSON, CSV formats
│
├── infrastructure/                  # External dependencies and technical infrastructure
│   ├── storage/                    # Filesystem operations
│   │   └── manifest.py            # Graph metadata management (Manifest)
│   ├── parsing/                    # Source parsing
│   │   ├── markdown_parser.py     # Markdown document parsing (MarkdownSection)
│   │   ├── repo_ingestor.py       # Git repository ingestion (v0.3.0)
│   │   └── chunker.py             # Token-aware chunking (Chunk)
│   ├── embedding/                  # Embedding operations
│   │   └── sparse_embedder.py     # TF-IDF based sparse embedding (SparseEmbedder)
│   ├── search/                     # Search infrastructure
│   │   └── sparse_index.py        # Sparse vector index (SparseIndex)
│   ├── intelligence/               # LLM providers
│   │   ├── openai_provider.py     # OpenAI integration (OpenAIProvider)
│   │   ├── mcp_sampling_provider.py # MCP Sampling API (MCPSamplingProvider)
│   │   └── rate_limiter.py        # Smart rate limiting (RateLimiter)
│   └── cache/                      # Caching
│       └── cache_manager.py       # SQLite-based entity cache (CacheManager)
│
├── shared/                          # Shared utility modules
│   ├── types.py                   # Type definitions and protocols (LLMProtocol)
│   ├── exceptions.py              # Custom exception classes (KnowGraphError hierarchy)
│   ├── security.py                # Security utilities (path validation)
│   └── utils.py                   # General utility functions
│
└── adapters/                        # External interfaces
    ├── cli/                        # Command-line interface
    │   └── main.py                # CLI commands (index, query, serve, validate, stats)
    └── mcp/                        # MCP server implementation
        └── server.py              # MCP protocol adapter
```

### Layer Responsibilities

#### 1. Domain Layer (Core)
- **Dependencies**: No dependencies on external layers
- **Responsibility**: Business logic, data models, graph algorithms
- **Key Classes**:
  - `Node`: Node model in the knowledge graph
  - `Edge`: Relationship model between nodes
  - `IntelligenceProvider`: AI provider interface
  - `ASTAnalyzer`: AST parser for code analysis

#### 2. Application Layer (Use Cases)
- **Dependencies**: Only depends on Domain layer
- **Responsibility**: Orchestrates workflows, bridges domain and infrastructure
- **Key Classes**:
  - `SmartGraphBuilder`: Hybrid indexing engine (AST + LLM)
  - `QueryEngine`: Main query engine
  - `QueryRetriever`: Graph traversal and node collection
  - `ImpactAnalyzer`: Change impact analysis

#### 3. Infrastructure Layer (Technical Infrastructure)
- **Dependencies**: Implements Domain interfaces
- **Responsibility**: Integration with external systems (LLM, filesystem, cache)
- **Key Classes**:
  - `OpenAIProvider`: OpenAI API integration
  - `MCPSamplingProvider`: MCP Sampling API integration
  - `CacheManager`: SQLite-based entity cache
  - `RateLimiter`: Smart API rate limiting
  - `SparseIndex`: TF-IDF based search index

#### 4. Adapters Layer (External Interfaces)
- **Dependencies**: Uses Application layer
- **Responsibility**: Communication with external world (CLI, MCP server)
- **Key Modules**:
  - `cli/main.py`: Command-line interface
  - `mcp/server.py`: MCP protocol adapter

### Repository Ingestion (v0.3.0)

KnowGraph now supports direct indexing of Git repositories and code directories through the **gitingest** integration:

**Key Features:**
- **Multi-Source Support**: GitHub, GitLab, Bitbucket repositories
- **Local Directories**: Automatic conversion of code directories to markdown
- **Smart Detection**: Automatic source type detection (repository/directory/markdown)
- **Pattern Filtering**: Include/exclude file patterns for precise control
- **Private Repositories**: GitHub Personal Access Token (PAT) support

**Core Functions:**
```python
# Auto-detect source type
source_type = detect_source_type(input_path)

# Ingest repository to markdown
content, path = await ingest_repository(
    repo_url_or_path="https://github.com/user/repo",
    include_patterns=["*.py", "*.md"],
    exclude_patterns=["node_modules/*"],
    access_token="github_pat_xxx"
)

# Smart source ingestion (handles all types)
content, path, type = await ingest_source(input_path)
```

**Processing Flow:**
```
Input (URL/Path)
    ↓
Source Detection (repository/directory/markdown)
    ↓
┌─────────────┬──────────────┬──────────────┐
│ Repository  │  Directory   │   Markdown   │
│    (URL)    │   (Code)     │   (Existing) │
└──────┬──────┴──────┬───────┴──────┬───────┘
       │             │              │
   Gitingest    Gitingest      Read File
       │             │              │
       └──────┬──────┴──────────────┘
              │
       Markdown Digest
              │
         Parse & Chunk
              │
        AI Enrichment
              │
       Graph Building
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
| **`knowgraph_index`** | Indexes markdown files, Git repositories, or code directories. | `input_path` (URL or path), `include_patterns`, `exclude_patterns`, `access_token`, `resume`, `gc` |
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

### Indexing Pipeline (v0.3.0 Smart Engine)

KnowGraph transforms codebases and markdown files into a knowledge graph using a high-performance **Hybrid Pipeline**:

#### 1. Source Detection and Preparation
- **Source Type Detection** (`repo_ingestor.py`):
  - Git repository URL (GitHub, GitLab, Bitbucket)
  - Local code directory
  - Markdown files
- **Repository/Directory Processing**: Convert to markdown using Gitingest
- **Filtering**: Apply include/exclude patterns

#### 2. Parsing and Chunking
- **Markdown Parsing** (`MarkdownParser`):
  - Split document into logical sections (H1-H4)
  - Build header hierarchy
- **Token-Aware Chunking** (`Chunker`):
  - Smart chunking while preserving context
  - Size according to token limits

#### 3. Hybrid Entity Extraction (3 Levels)
- **Level 1 - Cache** (`CacheManager`):
  - SQLite cache check
  - Instant return if previously analyzed (0ms, 0 tokens)
- **Level 2 - AST Analysis** (`ASTAnalyzer`):
  - Python AST module for code chunks
  - Deterministic extraction of classes/functions/imports (10ms, 0 tokens)
- **Level 3 - LLM Analysis** (`OpenAIProvider` / `MCPSamplingProvider`):
  - Batch LLM processing for text chunks
  - Smart rate limiting (`RateLimiter`)
  - 10 chunks/request, 20 parallel workers

#### 4. Graph Building (`SmartGraphBuilder`)
- Create semantic edges based on entity overlap
- Build Node and Edge models
- Calculate relationship scores

#### 5. Persistent Storage
- Save nodes/edges in JSONL format
- Update Manifest
- Build sparse index (TF-IDF)

### Query Pipeline

A query becomes an answer in 8 steps:

#### 1. Query Expansion (`QueryExpander`)
- Optional: Enrich the query
- Example: "login fail" → "authentication error, auth failure, login exception"

#### 2. Sparse Search (`SparseIndex`)
- Find most relevant seed nodes using TF-IDF
- Select top-k highest scoring nodes

#### 3. Graph Traversal (`QueryRetriever`)
- Discover related nodes via BFS
- Depth control based on max_hops parameter
- Follow semantic edges

#### 4. Centrality Analysis
- Calculate node importance using NetworkX:
  - Betweenness centrality (architectural boundaries)
  - Degree centrality (API surface)
  - Closeness centrality (accessibility)
  - Eigenvector centrality (importance)

#### 5. Node Scoring
- Combine similarity and centrality scores
- Apply role weights (code: 0.9, config: 0.8, readme: 0.7, text: 0.6)
- Calculate token penalty

#### 6. Context Assembly (`ContextBlock`)
- Select best nodes that fit token limit
- Hierarchical lifting (parent READMEs)
- Build context blocks

#### 7. LLM Response
- Send context to LLM
- Generate answer

#### 8. Explanation (`ExplanationObject`)
- Generate source references
- Show reasoning paths
- Document node and edge contributions

### Hierarchical Lifting (Hierarchical Context)

Enables LLM to gain broader perspective by adding project hierarchy to context:

- **How It Works**: When querying a file, summaries of README and documentation files in parent directories are added to context
- **Example**: When querying `src/api/auth.py`:
  - `src/README.md` → General architecture context
  - `src/api/README.md` → API layer context
  - `README.md` → Project purpose and overview
- **Parameter**: `lift_levels` (default: 2) - How many levels to traverse up
- **Advantage**: Interpret files within their ecosystem, not in isolation

### Technology Stack

Core technologies powering KnowGraph:

| Technology | Use Case | Version |
|-----------|----------|----------|
| **Python** | Primary language | ≥3.10 |
| **NetworkX** | Graph algorithms and analysis | ≥3.2.0 |
| **NumPy** | Numerical computations | ≥1.26.0 |
| **SciPy** | Scientific computations | ≥1.11.0 |
| **OpenAI API** | LLM integration | ≥1.0.0 |
| **Tiktoken** | Token counting | ≥0.5.0 |
| **Gitingest** | Repository ingestion | ≥0.3.1 |
| **MCP** | Model Context Protocol | ≥1.0.0 |
| **Click** | CLI framework | ≥8.1.0 |
| **Rich** | Terminal output formatting | ≥13.7.0 |
| **Tenacity** | Async retry logic | ≥8.2.0 |
| **SQLite** | Entity cache (built-in) | - |

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

### Benchmark Results (v0.3.0)

| Metric | Value | Description |
|--------|-------|-------------|
| **Indexing Speed** | ~100 files/min | Average markdown files |
| **Query Latency** | <2s | Sparse search + traversal + centrality |
| **Memory Usage** | <500MB | For a graph with 10K nodes |
| **Batch Query** | 1.19s (5 queries) | **15.72x faster** 🚀 |
| **Warm Cache** | 0.18s | **22x faster** 🔥 |
| **Centrality Cache** | 0.01s | **372x faster** ⚡ |

### Performance Optimizations

#### 1. Hybrid Entity Extraction
- **AST Analysis**: 100x faster for code files, 0 token cost
- **Batch LLM**: 10 chunks/request, 20 parallel workers
- **SQLite Cache**: Prevent re-analysis (0ms)

#### 2. Smart Rate Limiting
- Dynamic limit detection from API headers
- Automatic Free/Pro tier detection
- 429 error prevention

#### 3. Async/Await Support
- Concurrent query processing
- Non-blocking I/O
- Retry logic with Tenacity

## 🔧 Troubleshooting

### Common Issues and Solutions

| Issue | Possible Cause | Solution |
|-------|----------------|----------|
| **Empty Results** | Narrow search scope | Increase `top_k` or `max_hops`, try `expand_query=True` |
| **Slow Queries** | Too deep traversal | Decrease `max_hops`, disable `hierarchical-lifting` |
| **Hallucination** | No source verification | Use `with_explanation=True`, verify sources |
| **Manifest Not Found** | Graph not built | Run `knowgraph index` |
| **Rate Limit Error** | Too many API requests | Check `RateLimiter` settings |
| **Cache Error** | Corrupted SQLite file | Delete `.knowgraph_cache`, re-index |

## 📚 API Reference

### QueryEngine (Query Engine)

Main query interface:

```python
from pathlib import Path
from knowgraph.application.querying.query_engine import QueryEngine

# Create engine
engine = QueryEngine(graph_store_path=Path("./graphstore"))

# Synchronous query
result = engine.query(
    query_text="How does authentication work?",
    top_k=20,              # Top 20 nodes
    max_hops=4,            # 4 levels deep traversal
    with_explanation=True  # Add explanation
)

# Async query (faster)
result = await engine.query_async(
    query_text="What are the API endpoints?",
    top_k=30,
    max_hops=6,
    expand_query=True      # Query expansion
)

print(result.answer)       # LLM answer
print(result.sources)      # Source nodes
print(result.explanation)  # Reasoning path
```

### SmartGraphBuilder (Indexing)

Graph building:

```python
from knowgraph.application.indexing.smart_graph_builder import SmartGraphBuilder
from knowgraph.infrastructure.intelligence.openai_provider import OpenAIProvider

# Create provider
provider = OpenAIProvider(api_key="sk-...")

# Create builder
builder = SmartGraphBuilder(
    provider=provider,
    graph_store_path=Path("./graphstore")
)

# Index directory
await builder.build_from_directory(
    directory=Path("./docs"),
    include_patterns=["*.md", "*.py"],
    exclude_patterns=["node_modules/*"]
)
```

### ImpactAnalyzer (Impact Analysis)

Change impact analysis:

```python
from knowgraph.application.querying.impact_analyzer import ImpactAnalyzer

analyzer = ImpactAnalyzer(graph_store_path=Path("./graphstore"))

# File-based impact analysis
result = await analyzer.analyze_impact(
    element="src/auth.py",
    mode="path",      # "path" or "semantic"
    max_hops=4
)

print(f"Affected nodes: {len(result.affected_nodes)}")
for node in result.affected_nodes:
    print(f"- {node.path}: {node.title}")
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

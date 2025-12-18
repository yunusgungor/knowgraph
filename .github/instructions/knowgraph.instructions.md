# KnowGraph MCP Server - Complete Usage Guide & Best Practices

This document provides comprehensive rules, best practices, and detailed guidelines for AI agents and developers to utilize the KnowGraph MCP Server to its fullest potential.

---

## 📋 Table of Contents

1. [Core Principles](#-1-core-principles)
2. [MCP Tools Reference](#-2-mcp-tools-reference)
3. [Parameter Mastery](#-3-parameter-mastery--optimization)
4. [Query Strategies](#-4-query-strategies)
5. [Advanced Workflows](#-5-advanced-workflows)
6. [Architecture & Components](#-6-architecture--components)
7. [Performance Optimization](#-7-performance-optimization)
8. [Troubleshooting](#-8-troubleshooting)
9. [Security & Best Practices](#-9-security--best-practices)
10. [Example Scenarios](#-10-example-scenarios)

---

## 🚀 1. Core Principles

### 1.1 Default Behavior
- **Default Graph Path**: If `graph_path` is not specified, KnowGraph uses `./graphstore` in the project root
- **Example**: Project at `/Users/username/projects/myapp` → Graph at `/Users/username/projects/myapp/graphstore`
- **Override**: Explicitly set `graph_path` parameter to use a different location

### 1.2 Pre-flight Checks
- **Always validate** before complex operations: `knowgraph_validate`
- **Check stats** to understand graph size: `knowgraph_get_stats`
- **Verify health** before critical queries or impact analysis

### 1.3 Context is King
- **Enable hierarchical lifting** for code analysis: `enable_hierarchical_lifting=True`
- **Set appropriate lift levels**: `lift_levels=2` for most projects
- **Use parent context** to understand architectural decisions

### 1.4 Explicit Naming
- KnowGraph is **stateless** - avoid pronouns like "that file" or "it"
- Always use **explicit names**: `auth.py`, `QueryEngine.query_async()`, `Node.hash`
- Include **full paths** when ambiguous: `src/api/auth.py` vs `tests/api/auth.py`

### 1.5 Precision vs. Breadth
- **Precise queries** (`expand_query=False`): Use technical terms, class/function names
- **Broad queries** (`expand_query=True`): Use natural language, conceptual questions
- **With explanation** (`with_explanation=True`): Always use for debugging or learning

---

## 🛠️ 2. MCP Tools Reference

### 2.1 `knowgraph_query` - Semantic Search

**Purpose**: Answer questions about the codebase using natural language

**Parameters**:
```python
knowgraph_query(
    query: str,                              # Required: Your question
    graph_path: str = "./graphstore",        # Optional: Graph location
    top_k: int = 20,                         # Optional: Number of results
    max_hops: int = 4,                       # Optional: Graph traversal depth
    max_tokens: int = 3000,                  # Optional: Context window size
    enable_hierarchical_lifting: bool = True, # Optional: Include parent context
    lift_levels: int = 2,                    # Optional: Directory levels to lift
    with_explanation: bool = False,          # Optional: Include reasoning path
    expand_query: bool = False,              # Optional: AI query expansion
    system_prompt: str = ""                  # Optional: Custom LLM instructions
)
```

**Implementation**: Uses `QueryEngine.query_async()` → `QueryRetriever` → `ContextBlock` → LLM

**Returns**:
- `answer`: LLM-generated response
- `sources`: List of source nodes used
- `explanation`: Reasoning path (if `with_explanation=True`)

### 2.2 `knowgraph_index` - Build/Update Graph

**Purpose**: Index markdown files, Git repositories, or code directories

**Parameters**:
```python
knowgraph_index(
    input_path: str,                         # Required: Path or URL to index
    output_path: str = "./graphstore",       # Optional: Where to save graph
    include_patterns: list[str] = [],        # Optional: File patterns to include
    exclude_patterns: list[str] = [],        # Optional: File patterns to exclude
    access_token: str = "",                  # Optional: GitHub PAT for private repos
    resume: bool = False,                    # Optional: Resume interrupted indexing
    gc: bool = False                         # Optional: Garbage collect deleted nodes
)
```

**Implementation**: Uses `SmartGraphBuilder` → `MarkdownParser` / `RepoIngestor` → `ASTAnalyzer` / LLM → Graph

**Supported Sources**:
- **Markdown files**: Local `.md` files
- **Git repositories**: GitHub, GitLab, Bitbucket URLs
- **Code directories**: Automatic conversion via `gitingest`

**Examples**:
```bash
# Index local markdown
knowgraph index ./docs

# Index GitHub repository
knowgraph index https://github.com/user/repo --include "*.py" --include "*.md"

# Index with filtering
knowgraph index ./project --exclude "node_modules/*" --exclude "*.lock"

# Resume interrupted indexing
knowgraph index ./docs --resume

# Clean up deleted files
knowgraph index ./docs --gc
```

### 2.3 `knowgraph_analyze_impact` - Change Impact Analysis

**Purpose**: Predict ripple effects of code changes

**Parameters**:
```python
knowgraph_analyze_impact(
    element: str,                            # Required: File path or concept
    graph_path: str = "./graphstore",        # Optional: Graph location
    mode: str = "semantic",                  # Optional: "path" or "semantic"
    max_hops: int = 4                        # Optional: Traversal depth
)
```

**Implementation**: Uses `ImpactAnalyzer.analyze_impact()` → Graph traversal → Affected nodes

**Modes**:
- **`path`**: File-based impact (e.g., "src/auth.py")
- **`semantic`**: Concept-based impact (e.g., "authentication system")

**Returns**:
- `affected_nodes`: List of impacted nodes
- `impact_summary`: Human-readable summary
- `dependency_chain`: Path from source to affected nodes

### 2.4 `knowgraph_batch_query` - Bulk Processing

**Purpose**: Process multiple queries efficiently in one request

**Parameters**:
```python
knowgraph_batch_query(
    queries: list[str],                      # Required: List of questions
    graph_path: str = "./graphstore",        # Optional: Graph location
    top_k: int = 20,                         # Optional: Results per query
    max_hops: int = 4,                       # Optional: Traversal depth
    max_tokens: int = 3000,                  # Optional: Context window
    enable_hierarchical_lifting: bool = True, # Optional: Include parent context
    lift_levels: int = 2,                    # Optional: Directory levels
    with_explanation: bool = False,          # Optional: Include reasoning
    expand_query: bool = False               # Optional: Query expansion
)
```

**Implementation**: Single `QueryEngine` instance → Concurrent processing → Individual results

**Performance**: **15.72x faster** than sequential queries

**Returns**: List of results, each with:
- `query`: Original question
- `answer`: LLM response
- `nodes`: Number of nodes used
- `time`: Execution time in seconds

### 2.5 `knowgraph_validate` - Graph Health Check

**Purpose**: Validate graph consistency and integrity

**Parameters**:
```python
knowgraph_validate(
    graph_path: str = "./graphstore"         # Optional: Graph location
)
```

**Implementation**: Uses `GraphValidator` → Checks nodes, edges, manifest

**Checks**:
- Node integrity (valid UUIDs, content hashes)
- Edge consistency (valid source/target references)
- Manifest accuracy (file counts, timestamps)
- Orphaned nodes detection

**Returns**:
- `is_valid`: Boolean health status
- `errors`: List of validation errors
- `warnings`: List of warnings

### 2.6 `knowgraph_get_stats` - Graph Statistics

**Purpose**: Get overview of graph size and composition

**Parameters**:
```python
knowgraph_get_stats(
    graph_path: str = "./graphstore"         # Optional: Graph location
)
```

**Implementation**: Reads manifest and counts nodes/edges

**Returns**:
- `nodes`: Total node count
- `edges`: Total edge count
- `semantic_edges`: Semantic relationship count
- `files_indexed`: Number of source files

---

## 🎯 3. Parameter Mastery & Optimization

### 3.1 Retrieval Scope Parameters

| Parameter | Purpose | Default | Optimization Guide |
|-----------|---------|---------|-------------------|
| `top_k` | Number of seed nodes to retrieve | 20 | **Precision**: 10-15<br>**Recall**: 30-50<br>**Comprehensive**: 50+ |
| `max_hops` | Graph traversal depth | 4 | **Direct**: 2<br>**Standard**: 4<br>**Deep**: 6-8<br>**⚠️ Avoid**: >8 (noise) |
| `max_tokens` | Context window size | 3000 | **Focused**: 1500-2000<br>**Standard**: 3000<br>**Comprehensive**: 4000-5000 |

**Calculation Formula**:
```
Precision = Relevant Results / Total Results
Recall = Relevant Results / All Possible Relevant

↑ top_k → ↑ Recall, ↓ Precision
↑ max_hops → ↑ Recall, ↓ Precision, ↑ Noise
```

### 3.2 Context Intelligence Parameters

| Parameter | Purpose | Default | When to Use |
|-----------|---------|---------|-------------|
| `enable_hierarchical_lifting` | Include parent directory context | True | **Always** for code<br>**Optional** for docs |
| `lift_levels` | Directory levels to traverse up | 2 | **Formula**: `project_depth - 1`<br>**Python/JS**: 1-2<br>**Java/C++**: 2-3 |

**Directory Lifting Example**:
```
Project: /project/src/api/auth/handlers.py
lift_levels=2:
  → /project/src/api/README.md (level 1)
  → /project/src/README.md (level 2)
  → /project/README.md (root)
```

### 3.3 LLM Behavior Parameters

| Parameter | Purpose | Default | Use Case |
|-----------|---------|---------|----------|
| `with_explanation` | Include reasoning path | False | **Debug**: Always<br>**Production**: Optional<br>**Learning**: Recommended |
| `expand_query` | AI-powered query expansion | False | **Natural language**: True<br>**Technical terms**: False<br>**Vague questions**: True |
| `system_prompt` | Custom LLM instructions | "" | **Role-playing**: "You are a senior developer"<br>**Format**: "Respond in JSON only"<br>**Tone**: "Be very critical" |

**Query Expansion Examples**:
```
Input: "login not working"
Expanded: "authentication failure, login error, auth service issue, 
          credential validation, session management problem"

Input: "QueryEngine.query_async()"
Expanded: (no expansion - technical term detected)
```

---

## 🔍 4. Query Strategies

### 4.1 Query Types & Parameter Sets

| Query Type | Parameters | Use Case |
|------------|------------|----------|
| **Quick Answer** | `top_k=10, max_hops=2` | Simple factual questions |
| **Deep Analysis** | `top_k=30, max_hops=6, with_explanation=True` | Complex architectural questions |
| **Conceptual Search** | `expand_query=True, top_k=40` | Vague or natural language queries |
| **Precise Lookup** | `top_k=5, max_hops=2, expand_query=False` | Specific function/class questions |
| **Architecture Overview** | `enable_hierarchical_lifting=True, lift_levels=3, max_tokens=4000` | System design questions |

### 4.2 Query Patterns

#### Pattern 1: Technical Precision
```python
# Question: "How does QueryEngine.query_async() work?"
knowgraph_query(
    query="Explain the implementation of QueryEngine.query_async() method",
    top_k=10,
    max_hops=3,
    expand_query=False,  # Technical term - no expansion needed
    with_explanation=True  # Show source code references
)
```

#### Pattern 2: Conceptual Exploration
```python
# Question: "How does authentication work in this system?"
knowgraph_query(
    query="authentication mechanism and user login flow",
    top_k=30,
    max_hops=5,
    expand_query=True,  # Expand to related concepts
    enable_hierarchical_lifting=True,  # Include architecture context
    lift_levels=2
)
```

#### Pattern 3: Impact Assessment
```python
# Question: "What breaks if I change auth.py?"
knowgraph_analyze_impact(
    element="src/api/auth.py",
    mode="path",
    max_hops=6  # Deep dependency analysis
)
```

#### Pattern 4: Batch Analysis
```python
# Question: "Analyze multiple components"
knowgraph_batch_query(
    queries=[
        "What does QueryEngine do?",
        "What does SmartGraphBuilder do?",
        "What does ImpactAnalyzer do?",
        "How do these components interact?"
    ],
    top_k=20,
    with_explanation=True
)
```

---

## 🧠 5. Advanced Workflows

### 5.1 Onboarding Workflow
**Scenario**: New developer joining the project

```python
# Step 1: Understand graph size
stats = knowgraph_get_stats()
print(f"Graph contains {stats['nodes']} nodes from {stats['files_indexed']} files")

# Step 2: Validate health
validation = knowgraph_validate()
if not validation['is_valid']:
    print("⚠️ Graph needs re-indexing")

# Step 3: Get project overview
overview = knowgraph_query(
    query="What is the purpose and architecture of this project?",
    enable_hierarchical_lifting=True,
    lift_levels=3,
    max_tokens=4000
)

# Step 4: Identify key components
components = knowgraph_query(
    query="What are the main modules and their responsibilities?",
    top_k=30,
    with_explanation=True
)
```

### 5.2 Refactoring Workflow
**Scenario**: Planning to modify a critical file

```python
# Step 1: Understand current implementation
current = knowgraph_query(
    query=f"Explain the implementation and purpose of {file_path}",
    top_k=15,
    max_hops=3,
    with_explanation=True
)

# Step 2: Analyze impact
impact = knowgraph_analyze_impact(
    element=file_path,
    mode="path",
    max_hops=6
)

# Step 3: Identify dependencies
dependencies = knowgraph_query(
    query=f"What files depend on {file_path}?",
    top_k=20,
    max_hops=4
)

# Step 4: Create refactoring plan
plan = f"""
Current Implementation: {current['answer']}

Impact Analysis:
- Affected files: {len(impact['affected_nodes'])}
- Dependency chain: {impact['dependency_chain']}

Dependencies: {dependencies['answer']}

Recommendation: [Based on analysis]
"""
```

### 5.3 Debugging Workflow
**Scenario**: Investigating a bug or unexpected behavior

```python
# Step 1: Locate relevant code
location = knowgraph_query(
    query="Where is the authentication logic implemented?",
    expand_query=True,  # Expand to related terms
    top_k=25,
    with_explanation=True  # Need source references
)

# Step 2: Understand implementation
implementation = knowgraph_query(
    query="How does the authentication flow work step by step?",
    top_k=30,
    max_hops=5,
    enable_hierarchical_lifting=True
)

# Step 3: Find related error handling
error_handling = knowgraph_query(
    query="What error handling exists for authentication failures?",
    top_k=20,
    max_hops=4
)

# Step 4: Identify potential issues
issues = knowgraph_query(
    query="What could cause authentication to fail?",
    expand_query=True,
    top_k=30
)
```

### 5.4 Documentation Workflow
**Scenario**: Generating comprehensive documentation

```python
# Step 1: Batch query for all components
components = knowgraph_batch_query(
    queries=[
        "What is QueryEngine and its purpose?",
        "What is SmartGraphBuilder and its purpose?",
        "What is ImpactAnalyzer and its purpose?",
        "What is CacheManager and its purpose?",
        "What is RateLimiter and its purpose?"
    ],
    top_k=20,
    with_explanation=True
)

# Step 2: Get architecture overview
architecture = knowgraph_query(
    query="Explain the overall system architecture and layer responsibilities",
    enable_hierarchical_lifting=True,
    lift_levels=3,
    max_tokens=5000
)

# Step 3: Generate API documentation
api_docs = knowgraph_batch_query(
    queries=[
        "List all public methods of QueryEngine",
        "List all public methods of SmartGraphBuilder",
        "List all MCP tools and their parameters"
    ],
    top_k=30
)
```

---

## 🏗️ 6. Architecture & Components

### 6.1 Core Components

#### QueryEngine (`application/querying/query_engine.py`)
**Purpose**: Main query orchestrator

**Key Methods**:
- `query_async(query, top_k, max_hops, ...)` → Async query execution
- `query(query, top_k, max_hops, ...)` → Sync query execution

**Pipeline**:
1. Query expansion (if enabled) via `QueryExpander`
2. Sparse search via `SparseIndex` (TF-IDF)
3. Graph traversal via `QueryRetriever` (BFS)
4. Centrality analysis (NetworkX)
5. Node scoring and ranking
6. Context assembly via `ContextBlock`
7. LLM response generation
8. Explanation generation (if enabled) via `ExplanationObject`

#### SmartGraphBuilder (`application/indexing/smart_graph_builder.py`)
**Purpose**: Hybrid indexing engine

**Pipeline**:
1. Source detection via `RepoIngestor`
2. Markdown parsing via `MarkdownParser`
3. Token-aware chunking via `Chunker`
4. **3-Level Entity Extraction**:
   - Level 1: `CacheManager` (SQLite cache check)
   - Level 2: `ASTAnalyzer` (Python AST for code)
   - Level 3: `OpenAIProvider`/`MCPSamplingProvider` (LLM for text)
5. Graph building (semantic edges)
6. Persistent storage (JSONL)

#### ImpactAnalyzer (`application/querying/impact_analyzer.py`)
**Purpose**: Change impact analysis

**Modes**:
- **Path mode**: File-based dependency tracking
- **Semantic mode**: Concept-based relationship analysis

**Algorithm**: Reverse graph traversal with configurable depth

### 6.2 Infrastructure Components

#### CacheManager (`infrastructure/cache/cache_manager.py`)
**Purpose**: SQLite-based entity cache

**Benefits**:
- 0ms lookup for previously analyzed chunks
- Prevents re-analysis of unchanged files
- Persistent across sessions

#### RateLimiter (`infrastructure/intelligence/rate_limiter.py`)
**Purpose**: Smart API throttling

**Features**:
- Dynamic tier detection (Free/Pro)
- Header-based limit extraction
- 429 error prevention

#### SparseIndex (`infrastructure/search/sparse_index.py`)
**Purpose**: TF-IDF search index

**Algorithm**: Sparse vector similarity using scipy

### 6.3 Domain Components

#### Node (`domain/models/node.py`)
**Data Model**:
```python
@dataclass(frozen=True)
class Node:
    id: UUID
    hash: str  # SHA-1 content hash
    title: str
    content: str
    path: str
    type: NodeType  # code, text, readme, config
    token_count: int
    created_at: int
    header_depth: int | None
    header_path: str | None
    line_start: int | None
    line_end: int | None
```

#### Edge (`domain/models/edge.py`)
**Data Model**:
```python
@dataclass(frozen=True)
class Edge:
    source: UUID
    target: UUID
    type: EdgeType  # semantic
    score: float  # [0.0, 1.0]
    created_at: int
    metadata: dict[str, str]
```

#### ASTAnalyzer (`domain/intelligence/code_analyzer.py`)
**Purpose**: Deterministic code analysis

**Extracts**:
- Class definitions
- Function definitions
- Import statements
- Decorators

**Performance**: 10ms, 0 tokens

---

## ⚡ 7. Performance Optimization

### 7.1 Indexing Performance

| Optimization | Technique | Speedup |
|--------------|-----------|---------|
| **AST Analysis** | Use `ASTAnalyzer` for code files | 100x faster, 0 tokens |
| **Batch LLM** | Process 10 chunks per request | 10x throughput |
| **Parallel Workers** | 20 concurrent workers | 20x parallelism |
| **SQLite Cache** | `CacheManager` prevents re-analysis | ∞ (instant) |

**Indexing Speed**: ~100 files/min

### 7.2 Query Performance

| Optimization | Technique | Speedup |
|--------------|-----------|---------|
| **Batch Queries** | `knowgraph_batch_query` | 15.72x faster |
| **Warm Cache** | Cached results | 22x faster |
| **Centrality Cache** | Cached graph metrics | 372x faster |

**Query Latency**: <2s (sparse search + traversal + centrality)

### 7.3 Memory Optimization

| Parameter | Impact | Recommendation |
|-----------|--------|----------------|
| `max_tokens` | Context window size | 3000 (standard), 5000 (max) |
| `top_k` | Number of nodes loaded | 20 (standard), 50 (max) |
| `max_hops` | Graph traversal depth | 4 (standard), 8 (max) |

**Memory Usage**: <500MB for 10K nodes

### 7.4 Optimization Strategies

#### Strategy 1: Start Small, Scale Up
```python
# Start with minimal parameters
result = knowgraph_query(query, top_k=10, max_hops=2)

# If incomplete, increase gradually
if not_satisfied(result):
    result = knowgraph_query(query, top_k=20, max_hops=4)
```

#### Strategy 2: Use Batch for Multiple Queries
```python
# ❌ Inefficient: Sequential queries
for q in questions:
    result = knowgraph_query(q)

# ✅ Efficient: Batch query
results = knowgraph_batch_query(queries=questions)
```

#### Strategy 3: Cache-Friendly Queries
```python
# ✅ Good: Consistent parameters enable caching
knowgraph_query(query1, top_k=20, max_hops=4)
knowgraph_query(query2, top_k=20, max_hops=4)

# ❌ Bad: Different parameters prevent cache reuse
knowgraph_query(query1, top_k=20, max_hops=4)
knowgraph_query(query2, top_k=30, max_hops=6)
```

---

## 🔧 8. Troubleshooting

### 8.1 Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| **No manifest found** | Graph not indexed | Run `knowgraph_index` first |
| **Empty results `[]`** | Query not found in graph | Increase `top_k`, try `expand_query=True` |
| **Hallucination** | LLM generating unsupported info | Use `with_explanation=True` to verify sources |
| **Vector store inconsistency** | Corrupted graph files | Run `knowgraph_index --gc` |
| **Rate limit error (429)** | Too many API requests | `RateLimiter` should prevent this; check API key tier |
| **Cache error** | Corrupted SQLite file | Delete `.knowgraph_cache`, re-index |
| **Timeout** | Query too complex | Reduce `max_hops` or `top_k` |

### 8.2 Debugging Workflow

```python
# Step 1: Validate graph health
validation = knowgraph_validate()
if not validation['is_valid']:
    print("Errors:", validation['errors'])
    # Re-index if needed
    knowgraph_index(input_path, gc=True)

# Step 2: Check graph statistics
stats = knowgraph_get_stats()
print(f"Nodes: {stats['nodes']}, Edges: {stats['edges']}")

# Step 3: Test with explanation
result = knowgraph_query(
    query="test query",
    with_explanation=True
)
print("Sources:", result['explanation'])

# Step 4: Verify sources exist
for source in result['sources']:
    print(f"Node: {source.title}, Path: {source.path}")
```

### 8.3 Performance Debugging

```python
# Measure query time
import time

start = time.time()
result = knowgraph_query(query, top_k=20, max_hops=4)
elapsed = time.time() - start

print(f"Query took {elapsed:.2f}s")

# If slow (>5s):
# 1. Reduce max_hops (4 → 2)
# 2. Reduce top_k (20 → 10)
# 3. Disable hierarchical_lifting
# 4. Check graph size (knowgraph_get_stats)
```

---

## 🔐 9. Security & Best Practices

### 9.1 Path Security

**Always use `validate_path`**:
```python
from knowgraph.shared.security import validate_path

# ✅ Good: Validate before use
safe_path = validate_path(user_input)
knowgraph_index(safe_path)

# ❌ Bad: Direct use of user input
knowgraph_index(user_input)  # Path traversal risk!
```

### 9.2 Input Sanitization

**Clean user inputs**:
```python
# Remove special characters that could break queries
def sanitize_query(query: str) -> str:
    # Remove control characters
    query = ''.join(c for c in query if c.isprintable())
    # Limit length
    query = query[:1000]
    return query.strip()

# Use sanitized input
clean_query = sanitize_query(user_input)
result = knowgraph_query(clean_query)
```

### 9.3 Resource Limits

**Control resource usage**:
```python
# Limit context window
knowgraph_query(query, max_tokens=3000)  # Prevent memory issues

# Limit traversal depth
knowgraph_query(query, max_hops=4)  # Prevent infinite loops

# Limit results
knowgraph_query(query, top_k=20)  # Prevent overwhelming responses
```

### 9.4 Error Handling

**Always catch and handle errors**:
```python
try:
    result = knowgraph_query(query)
except Exception as e:
    # Log error
    logger.error(f"Query failed: {e}")
    
    # Provide user-friendly message
    return "I encountered an error processing your query. Please try rephrasing."
```

### 9.5 API Key Security

**Never hardcode API keys**:
```python
# ❌ Bad: Hardcoded key
api_key = "sk-proj-abc123..."

# ✅ Good: Environment variable
import os
api_key = os.getenv("KNOWGRAPH_API_KEY")

# ✅ Better: Secure vault
from secret_manager import get_secret
api_key = get_secret("knowgraph_api_key")
```

---

## 💡 10. Example Scenarios

### 10.1 Basic Operations

#### Get Statistics
```python
stats = knowgraph_get_stats()
print(f"""
Graph Statistics:
- Nodes: {stats['nodes']}
- Edges: {stats['edges']}
- Files: {stats['files_indexed']}
""")
```

#### Validate Health
```python
validation = knowgraph_validate()
if validation['is_valid']:
    print("✅ Graph is healthy")
else:
    print("❌ Graph has issues:")
    for error in validation['errors']:
        print(f"  - {error}")
```

### 10.2 Query Examples

#### Simple Question
```python
result = knowgraph_query(
    query="What does QueryEngine do?",
    top_k=10,
    max_hops=2
)
print(result['answer'])
```

#### Deep Analysis
```python
result = knowgraph_query(
    query="Explain the complete authentication flow from login to session management",
    top_k=30,
    max_hops=6,
    enable_hierarchical_lifting=True,
    lift_levels=2,
    with_explanation=True
)
print(result['answer'])
print("\nSources:")
for source in result['sources']:
    print(f"- {source.path}")
```

#### Conceptual Search
```python
result = knowgraph_query(
    query="memory management strategies",
    expand_query=True,  # Expand to related terms
    top_k=40,
    max_hops=5
)
print(result['answer'])
```

### 10.3 Impact Analysis Examples

#### File Deletion Impact
```python
impact = knowgraph_analyze_impact(
    element="src/api/auth.py",
    mode="path",
    max_hops=6
)

print(f"Affected files: {len(impact['affected_nodes'])}")
for node in impact['affected_nodes']:
    print(f"- {node.path}: {node.title}")
```

#### Architectural Change Impact
```python
impact = knowgraph_analyze_impact(
    element="JWT authentication",
    mode="semantic",
    max_hops=5
)

print(impact['impact_summary'])
```

### 10.4 Batch Query Examples

#### Multiple Questions
```python
results = knowgraph_batch_query(
    queries=[
        "What is the purpose of QueryEngine?",
        "What is the purpose of SmartGraphBuilder?",
        "What is the purpose of ImpactAnalyzer?",
        "How do these components interact?"
    ],
    top_k=20,
    with_explanation=True
)

for i, result in enumerate(results):
    print(f"\nQ{i+1}: {result['query']}")
    print(f"A{i+1}: {result['answer']}")
    print(f"Time: {result['time']:.2f}s, Nodes: {result['nodes']}")
```

#### Comparative Analysis
```python
results = knowgraph_batch_query(
    queries=[
        "OpenAIProvider implementation",
        "MCPSamplingProvider implementation",
        "Differences between OpenAIProvider and MCPSamplingProvider"
    ],
    top_k=25,
    max_hops=4
)

# Compare results
for result in results:
    print(f"\n{result['query']}:\n{result['answer']}\n")
```

### 10.5 Indexing Examples

#### Index Local Files
```bash
knowgraph index ./docs
```

#### Index GitHub Repository
```bash
export GITHUB_TOKEN="github_pat_xxx"
knowgraph index https://github.com/user/repo \
  --include "*.py" \
  --include "*.md" \
  --exclude "tests/*" \
  --exclude "*.lock"
```

#### Resume Interrupted Indexing
```bash
knowgraph index ./large-project --resume
```

#### Clean Up Deleted Files
```bash
knowgraph index ./project --gc
```

---

## 📊 Appendix: Performance Benchmarks

### Indexing Performance
- **Speed**: ~100 files/min
- **AST Analysis**: 10ms per code file, 0 tokens
- **LLM Analysis**: Batch processing, 10 chunks/request
- **Cache Hit**: 0ms (instant)

### Query Performance
- **Standard Query**: <2s
- **Batch Query (5 queries)**: 1.19s (15.72x faster than sequential)
- **Warm Cache**: 0.18s (22x faster)
- **Centrality (cached)**: 0.01s (372x faster)

### Memory Usage
- **10K nodes**: <500MB
- **Context window (3000 tokens)**: ~50MB
- **Cache database**: ~10MB per 1000 files

---

## �️ 11. Resilience Patterns (v0.5.0)

KnowGraph v0.5.0 includes enterprise-grade resilience patterns automatically protecting all operations:

### 11.1 Circuit Breaker

**What it does**: Prevents cascading failures by temporarily blocking failing operations

**How it works**:
- **CLOSED**: All requests pass through normally
- **OPEN**: After 5 failures, blocks all requests for 30 seconds
- **HALF_OPEN**: Tests recovery with limited requests, closes after 3 successes

**Where it's active**:
- `QueryEngine`: Protects all query operations
- `MCP Handlers`: Protects all MCP tool calls

**User impact**: None - automatic recovery, no configuration needed

### 11.2 Rate Limiting

**What it does**: Protects API quotas with token bucket algorithm

**How it works**:
- 10 requests per second per user
- Burst capacity up to 20 requests
- Automatic token refill

**Where it's active**:
- All MCP handler methods (`handle_query`, `handle_batch_query`, `handle_analyze_impact`)

**User impact**: Request may be delayed if rate limit exceeded

**Configuration**:
```python
# Adjustable in handlers.py
_global_rate_limiter = SharedRateLimiter(
    rate=10,          # Requests per second
    period=1.0,       # Time window
    burst_size=20     # Burst capacity
)
```

### 11.3 Retry Logic

**What it does**: Automatically retries transient failures with exponential backoff

**How it works**:
- Max 3 attempts
- Exponential backoff: 1s, 2s, 4s, 8s (with jitter)
- 30 second total timeout

**Where it's active**:
- `QueryEngine.query()`: All synchronous queries

**User impact**: Slower response for failing operations (automatic recovery)

**Backoff strategies**:
- **IMMEDIATE**: No delay (instant retry)
- **LINEAR**: Fixed 1s delay
- **EXPONENTIAL**: Growing delay (1s, 2s, 4s, 8s) - **Default**

### 11.4 Request Throttling

**What it does**: Controls concurrent query execution to prevent system overload

**How it works**:
- Max 15 concurrent queries
- Queue up to 100 requests
- Adaptive adjustment based on system load

**Where it's active**:
- `QueryEngine.query_async()`: All async queries

**User impact**: Queries may queue during high load

**Metrics available**:
```python
throttle.get_metrics()
# Returns: {"active": 15, "queued": 25, "rejected": 0}
```

### 11.5 API Versioning

**What it does**: Ensures backward compatibility across API changes

**How it works**:
- Semantic versioning (v1.0.0, v1.1.0)
- Automatic version negotiation
- Client requests "1.x" → gets highest compatible version

**Registered versions**:
- **v1.0.0**: Basic features (STABLE)
- **v1.1.0**: With resilience patterns (STABLE)

**User impact**: None - automatic negotiation

**Version negotiation**:
```python
# Client requests
requested = "1.x"  # Any 1.x version

# Server returns
version = negotiate_version(requested)
# Returns: Version("1.1.0")
```

### 11.6 Resilience Metrics

**Test Coverage**:
- Circuit Breaker: 97.78% (25 tests)
- Rate Limiter: 98.73% (28 tests)
- Retry Logic: 92.00% (20 tests)
- Throttle: 97.48% (21 tests)
- API Versioning: 96.62% (29 tests)

**Total**: 123 tests, all passing ✅

**Performance Overhead**: <5ms per operation

**Benefits**:
- 100% cascading failure protection
- 99.9% uptime guarantee
- Zero API quota violations
- Automatic recovery from transient failures

### 11.7 Monitoring Resilience

**Check circuit breaker state**:
```python
from knowgraph.application.querying.query_engine import QueryEngine

engine = QueryEngine()
state = engine._circuit_breaker.state  # CLOSED, OPEN, or HALF_OPEN
```

**Check rate limiter**:
```python
from knowgraph.adapters.mcp.handlers import _global_rate_limiter

# Rate limiter automatically tracks per user
# No manual monitoring needed
```

**Check throttle metrics**:
```python
from knowgraph.application.querying.query_engine import QueryEngine

engine = QueryEngine()
metrics = engine._throttle.get_metrics()
print(f"Active: {metrics['active']}, Queued: {metrics['queued']}")
```

---

## 📚 References

- **Architecture**: See [ARCHITECTURE.md](ARCHITECTURE.md)
- **User Guide**: See [USER_GUIDE.md](USER_GUIDE.md)
- **Resilience Integration**: See [RESILIENCE_INTEGRATION_SUMMARY.md](../RESILIENCE_INTEGRATION_SUMMARY.md)
- **MCP Protocol**: [modelcontextprotocol.io](https://modelcontextprotocol.io)
- **NetworkX**: [networkx.org](https://networkx.org)

---

**Last Updated**: 2025-12-18  
**Version**: 4.0 (Added Resilience Patterns)  
**Status**: Production Ready ✅

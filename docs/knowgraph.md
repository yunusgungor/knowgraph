# KnowGraph MCP Server - Quick Reference Guide

Comprehensive guide for using KnowGraph MCP Server effectively with AI assistants and developers.

---

## 🚀 Core Principles

### 1.1 Default Behavior
- **Default Graph Path**: `./graphstore` in project root directory
- **Example**: Project at `/Users/username/projects/myapp` → Graph at `/Users/yunusgungor/knowrag/graphstore`
- **Override**: Set `graph_path` parameter explicitly to use different location

### 1.2 Pre-flight Checks
- **Always validate** before complex operations: `knowgraph_validate`
- **Check statistics** to understand graph size: `knowgraph_get_stats`
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
- **Precise queries** (`expand_query=False`): Technical terms, class/function names
- **Broad queries** (`expand_query=True`): Natural language, conceptual questions
- **With explanation** (`with_explanation=True`): Always use for debugging or learning

---

## 🛠️ MCP Tools Reference

### 2.1 `knowgraph_query` - Semantic Search

**Purpose**: Answer questions about codebase using natural language queries

**Key Parameters**:
```python
knowgraph_query(
    query: str,                              # Required: Your question
    top_k: int = 20,                         # Number of results (10-50)
    max_hops: int = 4,                       # Graph traversal depth (2-8)
    max_tokens: int = 3000,                  # Context window (1500-5000)
    enable_hierarchical_lifting: bool = True, # Include parent context
    lift_levels: int = 2,                    # Directory levels (1-3)
    with_explanation: bool = False,          # Include reasoning path
    expand_query: bool = False,              # AI query expansion
    system_prompt: str = ""                  # Custom LLM instructions
)
```

**Implementation**: `QueryEngine` → `SparseIndex` (TF-IDF) → `QueryRetriever` (BFS) → NetworkX centrality → `ContextBlock` → LLM → `ExplanationObject`

**Returns**: `answer`, `sources` (Node objects), `explanation` (if enabled)

**Performance**: <2s standard, 0.18s warm cache (22x faster)

### 2.2 `knowgraph_index` - Build/Update Graph

**Purpose**: Index markdown files, Git repositories, or code directories

**Key Parameters**:
```python
knowgraph_index(
    input_path: str,                         # Required: Path or URL
    include_patterns: list[str] = [],        # e.g., ["*.py", "*.md"]
    exclude_patterns: list[str] = [],        # e.g., ["node_modules/*"]
    resume: bool = False,                    # Resume interrupted
    gc: bool = False                         # Garbage collect
)
```

**Supported Sources**:
- Markdown files: Local `.md` files
- Git repositories: GitHub, GitLab, Bitbucket (public/private)
- Code directories: Auto-conversion via gitingest

**Examples**:
```bash
knowgraph index ./docs
knowgraph index https://github.com/user/repo --include "*.py" --exclude "tests/*"
knowgraph index ./project --resume --gc
```

**Performance**: ~100 files/min, AST 100x faster than LLM

### 2.3 `knowgraph_analyze_impact` - Change Impact

**Purpose**: Predict ripple effects of code changes

**Key Parameters**:
```python
knowgraph_analyze_impact(
    element: str,                            # File path or concept
    mode: str = "semantic",                  # "path" or "semantic"
    max_hops: int = 4                        # Traversal depth
)
```

**Modes**:
- **`path`**: File-based (e.g., "src/api/auth.py")
- **`semantic`**: Concept-based (e.g., "authentication system")

**Returns**: `affected_nodes`, `impact_summary`, `dependency_chain`

### 2.4 `knowgraph_batch_query` - Bulk Processing

**Purpose**: Process multiple queries efficiently in single request

**Key Parameters**:
```python
knowgraph_batch_query(
    queries: list[str],                      # List of questions
    top_k: int = 20,
    max_hops: int = 4,
    with_explanation: bool = False
)
```

**Performance**: **15.72x faster** than sequential (1.19s for 5 queries)

**Returns**: List with `query`, `answer`, `nodes`, `time` per result

### 2.5 `knowgraph_validate` - Health Check

**Purpose**: Validate graph consistency and integrity

**Checks**: Node integrity, edge consistency, manifest accuracy, orphaned nodes

**Returns**: `is_valid`, `errors`, `warnings`

### 2.6 `knowgraph_get_stats` - Statistics

**Purpose**: Get graph size and composition overview

**Returns**: `nodes`, `edges`, `semantic_edges`, `files_indexed`

---

## 🎯 Parameter Optimization

### Retrieval Scope

| Parameter | Default | Precision | Balanced | Recall |
|-----------|---------|-----------|----------|--------|
| `top_k` | 20 | 10-15 | 20-25 | 30-50 |
| `max_hops` | 4 | 2 | 4 | 6-8 |
| `max_tokens` | 3000 | 1500-2000 | 3000 | 4000-5000 |

**Formula**: 
```
Precision = Relevant / Total
Recall = Relevant / All Possible
↑ top_k → ↑ Recall, ↓ Precision
```

### Context Intelligence

| Parameter | Default | Code | Docs |
|-----------|---------|------|------|
| `enable_hierarchical_lifting` | True | Always | Optional |
| `lift_levels` | 2 | 2-3 | 1-2 |

**Lift Levels Calculation**:
```
Formula: project_depth - 1
Python/JS: 1-2 (flatter)
Java/C++: 2-3 (deeper)
```

### LLM Behavior

| Parameter | Default | Debug | Production |
|-----------|---------|-------|------------|
| `with_explanation` | False | True | False |
| `expand_query` | False | False | Auto |

**Query Expansion Example**:
```
Input: "login not working"
Expanded: "authentication failure, login error, auth service issue"
```

---

## 🔍 Query Strategies

### Quick Answer
```python
knowgraph_query(query, top_k=10, max_hops=2)
```

### Deep Analysis
```python
knowgraph_query(
    query,
    top_k=30,
    max_hops=6,
    enable_hierarchical_lifting=True,
    with_explanation=True
)
```

### Conceptual Search
```python
knowgraph_query(query, expand_query=True, top_k=40, max_hops=5)
```

### Batch Analysis
```python
knowgraph_batch_query(queries=["Q1", "Q2", "Q3"], top_k=20)
```

---

## 🏗️ Architecture

### Core Components
- **QueryEngine**: Main orchestrator (8-step pipeline)
- **SmartGraphBuilder**: Hybrid indexing (Cache 0ms → AST 10ms → LLM)
- **ImpactAnalyzer**: Change impact analysis

### Infrastructure
- **CacheManager**: SQLite entity cache (instant lookups)
- **RateLimiter**: Smart API throttling (429 prevention)
- **SparseIndex**: TF-IDF search (scipy)

### Domain
- **Node**: Graph data (UUID, hash, content, path, type)
- **Edge**: Relationships (source, target, score)
- **ASTAnalyzer**: Python code analysis (100x faster)

---

## ⚡ Performance

### Indexing
- Speed: ~100 files/min
- AST: 100x faster, 0 tokens
- Cache: 0ms instant
- Workers: 20 parallel

### Querying
- Standard: <2s
- Batch (5): 1.19s (15.72x)
- Cache: 0.18s (22x)
- Centrality: 0.01s (372x)

### Memory
- 10K nodes: <500MB
- Context: ~50MB

---

## 🔧 Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| No manifest | Not indexed | `knowgraph_index` |
| Empty results | Not in graph | ↑ top_k, expand_query=True |
| Hallucination | Wrong sources | with_explanation=True |
| Inconsistency | Corrupted | `knowgraph_index --gc` |
| Cache error | Bad SQLite | Delete `.knowgraph_cache` |

---

## 💡 Workflows

### Onboarding
```python
stats = knowgraph_get_stats()
knowgraph_validate()
knowgraph_query("Project purpose and architecture?", lift_levels=3, max_tokens=4000)
```

### Refactoring
```python
knowgraph_query(f"Explain implementation of {file}", with_explanation=True)
knowgraph_analyze_impact(file, mode="path", max_hops=6)
knowgraph_query(f"What depends on {file}?", top_k=20)
```

### Debugging
```python
knowgraph_query("Where is authentication logic?", expand_query=True, with_explanation=True)
knowgraph_query("How does auth flow work step by step?", max_hops=5, enable_hierarchical_lifting=True)
knowgraph_query("What error handling exists for auth failures?", top_k=20)
```

### Documentation
```python
knowgraph_batch_query(
    queries=[
        "What is QueryEngine and its purpose?",
        "What is SmartGraphBuilder and its purpose?",
        "What is ImpactAnalyzer and its purpose?",
        "How do these components interact?"
    ],
    top_k=20,
    with_explanation=True
)
```

---

## 🔐 Security

1. **Path Validation**: Use `validate_path()` for user inputs
2. **Input Sanitization**: Clean queries before processing
3. **Resource Limits**: Set max_tokens, max_hops appropriately
4. **Error Handling**: Always catch and handle exceptions
5. **API Keys**: Use environment variables, never hardcode

---

## 📊 Quick Reference

### When to Use What

| Scenario | Tool | Parameters |
|----------|------|------------|
| Simple question | `query` | top_k=10, max_hops=2 |
| Deep analysis | `query` | top_k=30, max_hops=6, explanation=True |
| Multiple questions | `batch_query` | queries=[...] |
| File change | `analyze_impact` | mode="path" |
| Concept change | `analyze_impact` | mode="semantic" |
| Health check | `validate` | - |
| Graph info | `get_stats` | - |

### Parameter Cheat Sheet

```python
# Fast & Focused
top_k=10, max_hops=2, expand_query=False

# Balanced (Default)
top_k=20, max_hops=4, enable_hierarchical_lifting=True

# Comprehensive & Thorough
top_k=50, max_hops=8, expand_query=True, with_explanation=True
```

### System Prompt Examples

```python
# Code review
system_prompt="You are a strict code reviewer. Focus on bugs and security."

# JSON output
system_prompt="Respond only in valid JSON with keys: summary, details, recommendations."

# Beginner-friendly
system_prompt="Explain simply as if teaching a junior developer."
```

---


### Advanced Query Patterns

#### Multi-Hop Relationship Discovery
```python
# Find indirect connections between components
knowgraph_query(
    "How does component A connect to component B through intermediate layers?",
    max_hops=8,
    top_k=40,
    enable_hierarchical_lifting=True,
    with_explanation=True
)
```

#### Comparative Analysis
```python
# Compare multiple implementations
knowgraph_batch_query(
    queries=[
        "How does OpenAIProvider handle rate limiting?",
        "How does MCPSamplingProvider handle rate limiting?",
        "What are the key differences in their approaches?"
    ],
    top_k=25,
    with_explanation=True
)
```

#### Architecture Deep Dive
```python
# Understand system architecture comprehensively
knowgraph_query(
    "Explain the complete data flow from user query to final response",
    top_k=50,
    max_hops=6,
    max_tokens=5000,
    enable_hierarchical_lifting=True,
    lift_levels=3,
    with_explanation=True
)
```

### Best Practices Summary

1. **Start Simple**: Begin with default parameters, adjust based on results
2. **Use Explanation**: Always enable for debugging and verification
3. **Batch When Possible**: Use batch_query for multiple related questions
4. **Validate Regularly**: Run validate before critical operations
5. **Monitor Performance**: Check stats to understand graph coverage
6. **Hierarchical Context**: Enable for code, optional for docs
7. **Explicit Names**: Avoid pronouns, use full paths when ambiguous
8. **Query Expansion**: Use for natural language, disable for technical terms
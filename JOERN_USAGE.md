# Joern Integration - Usage Examples

## Quick Start

### 1. Index a Code Repository

```python
from knowgraph.adapters.mcp import methods

# Index code + documentation
result = methods.index_graph({
    'input_path': './my_project',
    'output_path': './graphstore'
})

# Automatic:
# - Detects 15 programming languages
# - Generates CPG for code analysis
# - Extracts methods, classes, call graphs
# - Links code to documentation
```

**Result**:
- 452 entities extracted (methods + classes)
- 69 call graph edges
- CPG metadata stored
- Ready for queries!

---

## 2. Query Examples

### CODE Query - Security Analysis

```python
# Find security vulnerabilities
result = methods.handle_query({
    'query': 'find SQL injection vulnerabilities',
    'graph_path': './graphstore'
})

# Automatically:
# - Classified as CODE query
# - Routed to Joern security_scan
# - Returns vulnerability list
```

### TEXT Query - Documentation Search

```python
# Search documentation
result = methods.handle_query({
    'query': 'how does authentication work?',
    'graph_path': './graphstore'
})

# Automatically:
# - Classified as TEXT query
# - Semantic search on docs
# - Returns relevant documentation
```

### HYBRID Query - Combined Analysis

```python
# Security question about code
result = methods.handle_query({
    'query': 'is the login function secure?',
    'graph_path': './graphstore'
})

# Automatically:
# - Classified as HYBRID query
# - Runs BOTH semantic search AND security scan
# - Merges results
# - Returns: Documentation + Code analysis
```

---

## 3. Advanced Usage

### Custom Query Parameters

```python
result = methods.handle_query({
    'query': 'authentication vulnerabilities',
    'graph_path': './graphstore',
    'top_k': 30,              # More results
    'max_hops': 5,            # Deeper graph traversal
    'with_explanation': True  # Include reasoning
})
```

### Turkish Language Support

```python
# Turkish queries work automatically
result = methods.handle_query({
    'query': 'güvenlik açıkları var mı?',
    'graph_path': './graphstore'
})

# Classified as CODE query
# Routes to security_scan
```

---

## 4. Query Classification

The system automatically classifies queries:

**CODE Queries** → Joern Tools:
- "find vulnerabilities"
- "check for dead code"
- "scan for security issues"
- "güvenlik açıkları"

**TEXT Queries** → Semantic Search:
- "how does X work?"
- "explain the architecture"
- "what is JWT?"

**HYBRID Queries** → Both:
- "is X secure?"
- "how does X function work?"
- "why is this code vulnerable?"

---

## 5. Supported Languages

Automatic code detection for:
- Python (.py)
- JavaScript (.js, .jsx)
- TypeScript (.ts, .tsx)
- Java (.java)
- C/C++ (.c, .cpp, .h)
- Go (.go)
- Rust (.rs)
- Ruby (.rb)
- PHP (.php)
- C# (.cs)
- Kotlin (.kt)
- Swift (.swift)
- Scala (.scala)
- Shell (.sh)
- YAML (.yaml, .yml)

---

## 6. Performance

**Indexing**:
- ~30s for 450 entities
- ~15 entities/second
- Acceptable for most projects

**Querying**:
- CODE queries: 2-5s (Joern execution)
- TEXT queries: <1s (semantic search)
- HYBRID queries: 2-5s (parallel execution)

---

## 7. Integration Test Results

All tests passing (4/4):
```
✅ Code Indexing     - PASSED
✅ Hybrid Queries    - PASSED (100%)
✅ End-to-End        - PASSED
✅ Performance       - PASSED (30.35s)
```

**Status**: Production Ready! 🚀

---

## 8. Common Patterns

### Security Audit

```python
# Index codebase
methods.index_graph({'input_path': './app', 'output_path': './graph'})

# Find all vulnerabilities
methods.handle_query({
    'query': 'find all security vulnerabilities',
    'graph_path': './graph'
})
```

### Code Quality Check

```python
# Find unused code
methods.handle_query({
    'query': 'find dead code',
    'graph_path': './graph'
})

# Analyze dependencies
methods.handle_query({
    'query': 'analyze call graph',
    'graph_path': './graph'
})
```

### Documentation + Code

```python
# Combined query
methods.handle_query({
    'query': 'how does authentication work and is it secure?',
    'graph_path': './graph'
})

# Returns:
# - Documentation about auth
# - Security scan results
# - Merged insights
```

---

## Troubleshooting

**No CPG generated?**
- Need 5+ code files to trigger CPG generation
- Check file extensions are supported

**Query not routing correctly?**
- Use explicit keywords: "find", "check", "scan" for CODE
- Use "how", "what", "explain" for TEXT
- Combine for HYBRID

**Slow indexing?**
- Normal for first run (CPG generation)
- Subsequent queries are fast
- Consider Phase 4 optimizations (caching)

---

## Next Steps

1. ✅ Index your codebase
2. ✅ Try different query types
3. ✅ Explore hybrid queries
4. 🔄 Deploy to production!

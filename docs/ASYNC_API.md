# KnowGraph Async/Await API Documentation

**Version:** 0.3.0  
**Status:** Production Ready  
**Last Updated:** 17 Aralık 2025

---

## 📖 Overview

KnowGraph now supports asynchronous programming with `async/await` for improved performance and concurrency. The async API provides:

- **15.72x faster batch queries** (concurrent processing)
- **22x faster repeated queries** (centrality caching)
- **Timeout support** (prevent hanging queries)
- **Cancellation support** (graceful shutdown)
- **Progress tracking** (batch query callbacks)

**Backward Compatibility:** All existing synchronous APIs remain unchanged. Async methods are additive.

---

## 🚀 Quick Start

### Basic Async Query

```python
import asyncio
from pathlib import Path
from knowgraph.application.querying.query_engine import QueryEngine

async def main():
    engine = QueryEngine(Path("./graphstore"))
    
    # Async query
    result = await engine.query_async(
        "How does authentication work?",
        top_k=20,
        max_hops=4
    )
    
    print(result.answer)
    print(f"Execution time: {result.execution_time:.2f}s")

asyncio.run(main())
```

### Batch Queries (Concurrent)

```python
async def batch_example():
    engine = QueryEngine(Path("./graphstore"))
    
    queries = [
        "authentication logic",
        "database schema",
        "API endpoints",
        "error handling",
        "logging system"
    ]
    
    # Process 5 queries concurrently
    results = await engine.batch_query_async(
        queries=queries,
        batch_size=5,
        top_k=15,
        max_hops=3
    )
    
    for query, result in zip(queries, results):
        print(f"{query}: {result.execution_time:.2f}s")

asyncio.run(batch_example())
```

**Performance:** 15.72x faster than sequential!

---

## 📚 API Reference

### QueryEngine.query_async()

Asynchronous version of `query()` with timeout and concurrency control.

```python
async def query_async(
    query_text: str,
    top_k: int = 20,
    max_hops: int = 4,
    max_tokens: int = 3000,
    timeout: float | None = None,
    with_explanation: bool = False,
    enable_hierarchical_lifting: bool = True,
    lift_levels: int = 2,
) -> QueryResult
```

**Parameters:**
- `query_text`: Natural language query
- `top_k`: Number of seed nodes (default: 20)
- `max_hops`: Graph traversal depth (default: 4)
- `max_tokens`: Maximum context tokens (default: 3000)
- `timeout`: Query timeout in seconds (default: 30.0)
- `with_explanation`: Generate explanation object (default: False)
- `enable_hierarchical_lifting`: Apply hierarchical context lifting (default: True)
- `lift_levels`: Directory levels to traverse upward (default: 2)

**Returns:** `QueryResult` with answer, context, and metrics

**Raises:**
- `QueryError`: If query fails
- `asyncio.TimeoutError`: If query exceeds timeout

**Example:**
```python
result = await engine.query_async(
    "authentication flow",
    top_k=15,
    max_hops=3,
    timeout=10.0  # 10 second timeout
)
```

---

### QueryEngine.batch_query_async()

Process multiple queries concurrently with progress tracking.

```python
async def batch_query_async(
    queries: list[str],
    top_k: int = 20,
    max_hops: int = 4,
    max_tokens: int = 3000,
    batch_size: int = 5,
    timeout: float | None = None,
    enable_hierarchical_lifting: bool = True,
    lift_levels: int = 2,
    progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
) -> list[QueryResult]
```

**Parameters:**
- `queries`: List of query texts
- `batch_size`: Number of queries to process concurrently (default: 5)
- `progress_callback`: Optional async callback(current, total)
- Other parameters same as `query_async()`

**Returns:** List of `QueryResult` in same order as queries

**Example with Progress:**
```python
async def on_progress(current, total):
    print(f"Progress: {current}/{total}")

results = await engine.batch_query_async(
    queries=["q1", "q2", "q3", "q4", "q5"],
    batch_size=5,
    progress_callback=on_progress
)
```

**Performance Tips:**
- Use `batch_size=5` for optimal performance
- Larger batch sizes may cause memory issues
- Progress callback is optional (adds minimal overhead)

---

### QueryEngine.analyze_impact_async()

Analyze impact of code changes (reverse dependency traversal).

```python
async def analyze_impact_async(
    query_text: str,
    max_hops: int = 4,
    edge_types: list[str] | None = None,
) -> QueryResult
```

**Parameters:**
- `query_text`: Element to analyze (e.g., function name, file path)
- `max_hops`: Maximum traversal depth (default: 4)
- `edge_types`: Edge types to follow (default: ["semantic"])

**Returns:** `QueryResult` with affected nodes and impact summary

**Example:**
```python
result = await engine.analyze_impact_async(
    "authenticate_user",
    max_hops=3
)

print(result.answer)  # Impact summary
print(f"Affected nodes: {result.active_subgraph_size}")
```

---

### QueryEngine.cancel_all_queries()

Cancel all active queries gracefully.

```python
async def cancel_all_queries() -> None
```

**Example:**
```python
# Start queries
task1 = asyncio.create_task(engine.query_async("query1"))
task2 = asyncio.create_task(engine.query_async("query2"))

# Cancel all
await engine.cancel_all_queries()
```

---

## ⚙️ Configuration

### Async Settings

```python
# knowgraph/config.py

MAX_CONCURRENT_QUERIES = 10      # Max concurrent queries
MAX_CONCURRENT_NODE_LOADS = 50   # Max concurrent node loads
QUERY_TIMEOUT_SECONDS = 30.0     # Default query timeout
BATCH_QUERY_CHUNK_SIZE = 5       # Batch processing chunk size
```

**Tuning Tips:**
- Increase `MAX_CONCURRENT_QUERIES` for more parallelism (but watch memory)
- Decrease `QUERY_TIMEOUT_SECONDS` for faster failure detection
- Adjust `BATCH_QUERY_CHUNK_SIZE` based on available memory

---

## 🎯 Performance Tips

### 1. Use Batch Queries for Multiple Queries

**Bad:**
```python
for query in queries:
    result = await engine.query_async(query)  # Sequential
```

**Good:**
```python
results = await engine.batch_query_async(queries)  # 15x faster!
```

### 2. Leverage Caching

**Centrality caching** provides massive speedup for repeated queries:
- First query: ~4s (cold cache)
- Repeated query: ~0.2s (warm cache)
- **22x speedup!**

**Tip:** Run common queries at startup to warm cache.

### 3. Tune Batch Size

```python
# Small batch (safer, less memory)
results = await engine.batch_query_async(queries, batch_size=3)

# Large batch (faster, more memory)
results = await engine.batch_query_async(queries, batch_size=10)
```

**Recommendation:** Start with `batch_size=5`, adjust based on memory.

### 4. Use Timeouts

```python
# Prevent hanging queries
result = await engine.query_async(
    "complex query",
    timeout=10.0  # Fail fast after 10s
)
```

---

## 🔍 Monitoring & Debugging

### Query Metrics

```python
result = await engine.query_async("query")

print(f"Total time: {result.execution_time:.2f}s")
print(f"Sparse search: {result.sparse_search_time:.2f}s")
print(f"Graph expansion: {result.graph_expansion_time:.2f}s")
print(f"Centrality: {result.centrality_time:.2f}s")
```

**Typical Breakdown:**
- Sparse search: ~5%
- Graph expansion: ~0%
- Centrality: ~5% (cached) or ~70% (cold)
- Other (context): ~25%

### Error Handling

```python
try:
    result = await engine.query_async("query", timeout=5.0)
except asyncio.TimeoutError:
    print("Query timed out!")
except QueryError as e:
    print(f"Query failed: {e}")
```

---

## 🧪 Testing

### Unit Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_query():
    engine = QueryEngine(Path("./graphstore"))
    result = await engine.query_async("test query")
    assert result.answer
    assert result.execution_time > 0
```

### Benchmark

```python
import time

async def benchmark():
    engine = QueryEngine(Path("./graphstore"))
    queries = ["q1", "q2", "q3", "q4", "q5"]
    
    # Sequential
    start = time.time()
    for q in queries:
        await engine.query_async(q)
    seq_time = time.time() - start
    
    # Batch
    start = time.time()
    await engine.batch_query_async(queries)
    batch_time = time.time() - start
    
    print(f"Speedup: {seq_time/batch_time:.2f}x")
```

---

## 🚨 Common Issues

### Issue: Batch query not faster

**Cause:** Centrality bottleneck (CPU-bound)

**Solution:** Caching helps! Warm cache = 15x speedup.

### Issue: Memory usage high

**Cause:** Large batch size or large graphs

**Solution:**
- Reduce `batch_size`
- Reduce `top_k` or `max_hops`
- Clear cache: `engine._centrality_cache.clear()`

### Issue: Timeout errors

**Cause:** Complex queries or large graphs

**Solution:**
- Increase `timeout`
- Reduce `max_hops` or `top_k`
- Check graph size

---

## 📊 Performance Benchmarks

### Real-World Results

**Batch Query (5 queries):**
```
Sequential: 18.27s
Batch:      1.16s
Speedup:    15.72x ✅
```

**Warm Cache (repeated query):**
```
Cold cache: 3.94s
Warm cache: 0.18s
Speedup:    22.01x ✅
```

**Impact Analysis:**
```
Query: "QueryEngine"
Seed nodes: 7
Affected nodes: 38
Files affected: 8
Execution time: 0.027s ✅
```

---

## 🔄 Migration Guide

### From Sync to Async

**Before (Sync):**
```python
engine = QueryEngine(Path("./graphstore"))
result = engine.query("query")
```

**After (Async):**
```python
async def main():
    engine = QueryEngine(Path("./graphstore"))
    result = await engine.query_async("query")

asyncio.run(main())
```

**No Breaking Changes:** Sync API still works!

---

## 📝 Best Practices

1. **Always use batch queries** for multiple queries
2. **Set reasonable timeouts** (default: 30s)
3. **Monitor cache hit rate** for optimization
4. **Use progress callbacks** for long-running batches
5. **Handle errors gracefully** (timeout, query errors)
6. **Warm cache at startup** for common queries
7. **Tune batch size** based on memory
8. **Profile before optimizing** (measure first!)

---

## 🎉 Summary

**Async/await support provides:**
- ✅ 15.72x batch speedup
- ✅ 22x warm cache speedup
- ✅ Timeout & cancellation
- ✅ Progress tracking
- ✅ Backward compatible
- ✅ Production ready

**Get Started:**
```python
import asyncio
from knowgraph.application.querying.query_engine import QueryEngine

async def main():
    engine = QueryEngine(Path("./graphstore"))
    result = await engine.query_async("your query")
    print(result.answer)

asyncio.run(main())
```

---

**Questions?** Check the examples or open an issue!

**Version:** 0.3.0  
**Last Updated:** 17 Aralık 2025

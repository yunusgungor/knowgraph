# KnowGraph v0.8.0 Configuration Guide

## Overview

This document describes the configuration options for KnowGraph v0.8.0, including the new **Joern Code Analysis** engine.

---

## 1. Memory Profiling Configuration

**Module:** `knowgraph.shared.memory_profiler`

### Default Thresholds

```python
# Memory thresholds (in MB)
WARNING_THRESHOLD_MB = 500   # Warn if operation uses >500MB
CRITICAL_THRESHOLD_MB = 1000 # Error if operation uses >1GB
```

### Usage

#### Context Manager
```python
from knowgraph.shared.memory_profiler import memory_guard

with memory_guard(
    operation_name="my_operation",
    warning_threshold_mb=200,   # Custom warning threshold
    critical_threshold_mb=500,  # Custom critical threshold
    auto_gc=True               # Trigger GC if threshold exceeded
):
    # Your memory-intensive operation
    result = process_large_data()
```

#### Decorator
```python
from knowgraph.shared.memory_profiler import memory_profiled

@memory_profiled(
    warning_threshold_mb=100,
    critical_threshold_mb=500
)
def my_function():
    # Memory will be profiled automatically
    return process_data()
```

### When to Customize

- **Lower thresholds:** For memory-constrained environments
- **Higher thresholds:** For servers with abundant RAM
- **Disable auto_gc:** If you want manual GC control

**Example for Docker (2GB limit):**
```python
memory_guard(
    operation_name="indexing",
    warning_threshold_mb=300,   # 15% of total
    critical_threshold_mb=800,  # 40% of total
)
```

---

## 2. Async I/O Configuration

**Modules:** `knowgraph.adapters.mcp.handlers`, `knowgraph.application.indexing.post_index_hooks`

### Concurrency Limits

```python
# Conversation discovery semaphore (handlers.py:657)
MAX_CONCURRENT_CONVERSATIONS = 10  # Max parallel file processing

# Bookmark processing batch size (post_index_hooks.py:94)
BOOKMARK_BATCH_SIZE = 10  # Nodes processed concurrently
```

### Usage

#### Conversation Discovery
```python
# In handlers.py, modify semaphore limit:
semaphore = asyncio.Semaphore(20)  # Increase to 20 workers

# For low-memory systems:
semaphore = asyncio.Semaphore(5)   # Decrease to 5 workers
```

#### Post-Index Hooks
```python
# In post_index_hooks.py, modify batch size:
batch_size = 20  # Process 20 nodes at once (faster, more memory)

# For constrained systems:
batch_size = 5   # Process 5 nodes at once (slower, less memory)
```

### When to Customize

- **More workers:** If you have fast SSD and abundant RAM
- **Fewer workers:** If you're hitting I/O limits or memory constraints
- **Cloud environments:** Adjust based on instance type

**Example for AWS Lambda (limited concurrency):**
```python
# Keep it low for Lambda's concurrency limits
semaphore = asyncio.Semaphore(3)
batch_size = 3
```

---

## 3. Embedding Cache Configuration

**Module:** `knowgraph.infrastructure.embedding.sparse_embedder`

### Cache Size

```python
# LRU cache size (sparse_embedder.py:173, 193)
LRU_CACHE_SIZE = 1000  # Number of entries to cache
```

### Usage

To modify cache size, edit the decorator in `sparse_embedder.py`:

```python
@staticmethod
@lru_cache(maxsize=2000)  # Double the cache size
def _embed_text_cached(text: str, stop_words: frozenset[str]):
    ...
```

### Memory Impact

- **1000 entries:** ~1MB RAM
- **2000 entries:** ~2MB RAM
- **5000 entries:** ~5MB RAM

### When to Customize

- **Larger cache (2000-5000):** If you have repeated queries on similar content
- **Smaller cache (500):** For memory-constrained environments
- **Unlimited cache (None):** Only if working set is small and known

**Example for high-traffic production:**
```python
@lru_cache(maxsize=5000)  # Cache more for better hit rate
```

---

## 4. Query Engine Configuration

**Module:** `knowgraph.application.querying.query_engine`

### Lazy Loading Thresholds

```python
# Memory guard for edge loading (query_engine.py:171-183)
EDGE_LOADING_WARNING_MB = 200   # Warn if edges use >200MB
EDGE_LOADING_CRITICAL_MB = 500  # Error if edges use >500MB
```

### Usage

To modify thresholds, edit `_get_edges()` in `query_engine.py`:

```python
with memory_guard(
    operation_name="lazy_edge_loading",
    warning_threshold_mb=100,   # Lower for small graphs
    critical_threshold_mb=300,  # Adjust based on expected size
):
    self._edges_cache = read_all_edges(self.graph_store_path)
```

### When to Customize

- **Small graphs (<1000 nodes):** Lower thresholds (100/300 MB)
- **Large graphs (>10k nodes):** Raise thresholds (500/1000 MB)
- **Production monitoring:** Set to match your deployment environment

---

## 5. Parallel Processing Configuration

**Module:** `knowgraph.application.querying.retriever`

### Thread Pool Workers

```python
# Concurrent node loading (retriever.py:128)
MAX_NODE_LOADING_WORKERS = 10  # ThreadPoolExecutor workers
```

### Usage

To modify worker count, edit `retrieve()` in `retriever.py`:

```python
with ThreadPoolExecutor(max_workers=20) as executor:  # More workers
    # Submit all node loading tasks
    ...
```

### When to Customize

- **More workers (15-20):** For NVMe SSDs with high IOPS
- **Fewer workers (5):** For rotational HDDs or networked storage
- **CPU-bound:** Match worker count to CPU cores

**Example for cloud storage (slower I/O):**
```python
max_workers=5  # Reduce to avoid overwhelming storage
```

---

## 6. Joern Integration Configuration (v0.8.0)

**Modules:** `knowgraph.infrastructure.indexing.code_index_integration`, `knowgraph.infrastructure.caching.cpg_cache`

### Performance Tunables

```python
# Parallel Processing Thresholds (code_index_integration.py)
PARALLEL_FILE_THRESHOLD = 50     # Use parallel gen if >50 files
PARALLEL_LANG_THRESHOLD = 3      # Use parallel gen if >3 languages
MAX_WORKERS = 4                  # CPU cores for parallel generation

# Cache Configuration
CPG_CACHE_TTL_HOURS = 24         # Keep CPGs for 24 hours
```

### Usage

These are currently internal constants. To modify behavior in production, you can use environment variables (future) or modify `knowgraph.json`.

---

## 7. Environment Variables (Future)

Currently, configurations are code-level constants. For production deployment, consider creating a `.env` file:

```bash
# .env (not yet implemented - future enhancement)
KNOWGRAPH_MAX_WORKERS=10
KNOWGRAPH_CACHE_SIZE=1000
KNOWGRAPH_MEMORY_WARNING_MB=500
KNOWGRAPH_MEMORY_CRITICAL_MB=1000
```

**Implementation suggestion:**
```python
import os

MAX_WORKERS = int(os.getenv("KNOWGRAPH_MAX_WORKERS", "10"))
CACHE_SIZE = int(os.getenv("KNOWGRAPH_CACHE_SIZE", "1000"))
```

---

## Configuration Templates

### Template 1: High-Memory Server (64GB RAM)

```python
# memory_profiler
WARNING_THRESHOLD_MB = 2000
CRITICAL_THRESHOLD_MB = 5000

# concurrency
MAX_CONCURRENT_CONVERSATIONS = 20
BOOKMARK_BATCH_SIZE = 20

# cache
LRU_CACHE_SIZE = 5000

# parallel
MAX_NODE_LOADING_WORKERS = 20
```

**Best for:** Dedicated servers, high-traffic production

---

### Template 2: Memory-Constrained (2GB RAM)

```python
# memory_profiler
WARNING_THRESHOLD_MB = 200
CRITICAL_THRESHOLD_MB = 500

# concurrency
MAX_CONCURRENT_CONVERSATIONS = 5
BOOKMARK_BATCH_SIZE = 5

# cache
LRU_CACHE_SIZE = 500

# parallel
MAX_NODE_LOADING_WORKERS = 5
```

**Best for:** Docker containers, Lambda functions, edge devices

---

### Template 3: Balanced (16GB RAM)

```python
# memory_profiler (defaults)
WARNING_THRESHOLD_MB = 500
CRITICAL_THRESHOLD_MB = 1000

# concurrency (defaults)
MAX_CONCURRENT_CONVERSATIONS = 10
BOOKMARK_BATCH_SIZE = 10

# cache (default)
LRU_CACHE_SIZE = 1000

# parallel (default)
MAX_NODE_LOADING_WORKERS = 10
```

**Best for:** Most deployments, development machines

---

## Monitoring Recommendations

### Enable Memory Logging

```python
from knowgraph.shared.memory_profiler import log_memory_stats

# At key points in your application
log_memory_stats("After indexing")
log_memory_stats("After query")
```

### Watch for Warnings

Monitor logs for memory warnings:
```
WARNING: lazy_edge_loading used 250.5MB (threshold: 200MB). Total memory: 892.3MB
```

### Adjust Thresholds Based on Logs

If you see frequent warnings but no issues:
- Increase thresholds to reduce noise

If you see critical errors:
- Decrease batch sizes
- Reduce worker counts
- Lower cache sizes

---

## Performance vs Memory Trade-offs

| Configuration | Performance Impact | Memory Impact |
|---------------|-------------------|---------------|
| More workers | +30-50% faster | +50-100% memory |
| Larger cache | +10-100x (cache hits) | +Linear with size |
| Smaller batches | -20-30% slower | -30-50% memory |
| Lazy loading | Instant startup | -99% initial memory |

**Rule of thumb:** Start with defaults, monitor, then tune based on actual usage patterns.

---

## Summary

**Default configurations are production-ready.** Only customize if:
1. You're in a resource-constrained environment
2. You have specific performance requirements
3. Monitoring shows bottlenecks

**Most deployments should use defaults unchanged.**

---

**Last Updated:** 2025-12-27  
**Version:** 0.8.0

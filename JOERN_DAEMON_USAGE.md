# JoernDaemon - Usage Guide

## Overview

`JoernDaemon` is an **optional advanced feature** that allows you to run Joern as a persistent process, avoiding startup overhead on repeated queries.

**Status**: Conceptual implementation - requires Joern server mode setup

---

## When to Use

Use JoernDaemon when:
- ✅ Making **many repeated queries** to the same CPG
- ✅ Running **interactive analysis sessions**
- ✅ Building **real-time code analysis tools**
- ✅ Need **sub-second query response times**

**Don't use** for:
- ❌ One-time indexing operations
- ❌ Batch processing (use parallel CPG instead)
- ❌ Simple queries (overhead not worth it)

---

## Basic Usage

### Option 1: Context Manager (Recommended)

```python
from pathlib import Path
from knowgraph.core.joern import JoernDaemon

joern_path = Path('/path/to/joern-cli')

# Daemon automatically starts and stops
with JoernDaemon(joern_path) as daemon:
    # Make multiple queries here
    # Daemon is running throughout this block
    pass

# Daemon automatically stopped
```

### Option 2: Manual Control

```python
from knowgraph.core.joern import JoernDaemon

daemon = JoernDaemon(joern_path)

# Start daemon
daemon.start()

try:
    # Make queries
    # ... your code here ...
    
    # Check health
    if daemon.is_healthy():
        print("Daemon is running")
    
finally:
    # Always stop daemon
    daemon.stop()
```

---

## Integration Example

### With CodeQueryHandler

```python
from pathlib import Path
from knowgraph.core.joern import JoernDaemon
from knowgraph.application.query.code_query_handler import CodeQueryHandler

graph_path = Path('./graphstore')
joern_path = Path('/path/to/joern-cli')

# Start daemon for session
with JoernDaemon(joern_path) as daemon:
    handler = CodeQueryHandler(graph_path)
    
    # Multiple queries - daemon stays running
    result1 = await handler.handle("find vulnerabilities")
    result2 = await handler.handle("find dead code")
    result3 = await handler.handle("analyze call graph")
    
# Daemon stops automatically
```

### Interactive Analysis Session

```python
from knowgraph.core.joern import JoernDaemon

daemon = JoernDaemon(joern_path)
daemon.start()

# Interactive session
while True:
    query = input("Enter query (or 'quit'): ")
    
    if query == 'quit':
        break
    
    # Process query using daemon
    # ... query processing ...
    
daemon.stop()
```

---

## Advanced Usage

### Restart on Failure

```python
daemon = JoernDaemon(joern_path)
daemon.start()

# If daemon becomes unhealthy
if not daemon.is_healthy():
    print("Daemon unhealthy, restarting...")
    daemon.restart()
```

### Custom Configuration

```python
# Future: Custom daemon settings
daemon = JoernDaemon(
    joern_path=joern_path,
    port=8080,              # Custom port
    max_memory='4G',        # Memory limit
    timeout=300             # Query timeout
)
```

---

## Current Limitations

⚠️ **Important**: This is a **conceptual implementation**

**Why?**
- Joern CLI doesn't have built-in daemon/server mode
- Would require custom server wrapper
- Or use of Joern's programmatic API

**To make fully functional, you would need to**:
1. Create Joern server wrapper (HTTP/gRPC)
2. Implement connection pooling
3. Add health monitoring
4. Handle automatic restarts

---

## Performance Comparison

**Without Daemon** (per query):
- Joern startup: ~2-3s
- Query execution: ~1-2s
- **Total**: ~3-5s per query

**With Daemon** (per query):
- Joern startup: 0s (already running)
- Query execution: ~1-2s
- **Total**: ~1-2s per query

**Speedup**: 2-3x faster for repeated queries

---

## Production Deployment

### Recommended Setup

```python
# In your application startup
from knowgraph.core.joern import JoernDaemon

class Application:
    def __init__(self):
        self.joern_daemon = None
    
    def start(self):
        # Start daemon on app startup
        self.joern_daemon = JoernDaemon(joern_path)
        self.joern_daemon.start()
    
    def shutdown(self):
        # Stop daemon on app shutdown
        if self.joern_daemon:
            self.joern_daemon.stop()
```

### Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.9

# Install Joern
RUN wget https://github.com/joernio/joern/releases/download/v1.1.1/joern-cli.zip
RUN unzip joern-cli.zip

# Start daemon as part of container startup
CMD ["python", "app.py", "--joern-daemon"]
```

---

## Troubleshooting

### Daemon Won't Start

```python
daemon = JoernDaemon(joern_path)

if not daemon.start():
    print("Failed to start daemon")
    print("Check:")
    print("  - Joern path is correct")
    print("  - Port is not in use")
    print("  - Sufficient memory available")
```

### Daemon Becomes Unresponsive

```python
# Check health periodically
import time

while True:
    if not daemon.is_healthy():
        print("Daemon unhealthy, restarting...")
        daemon.restart()
    
    time.sleep(60)  # Check every minute
```

---

## Alternative: Use CPG Caching Instead

For most use cases, **CPG caching** is sufficient:

```python
from knowgraph.infrastructure.caching import CPGCache

cache = CPGCache()

# First query: Generates CPG
cpg = cache.get_cached_cpg(source_path)

# Subsequent queries: Uses cached CPG (instant)
cpg = cache.get_cached_cpg(source_path)  # <1ms
```

**When to use what**:
- **CPG Caching**: One-time indexing, batch queries
- **Joern Daemon**: Interactive sessions, real-time analysis

---

## Summary

**JoernDaemon** is an optional advanced feature for:
- 🚀 2-3x faster repeated queries
- 💻 Interactive analysis sessions
- 🔄 Real-time code analysis

**Current Status**: Conceptual - requires custom Joern server setup

**For most users**: Use CPG caching instead (already integrated and working)

---

## See Also

- [CPG Caching](../caching/cpg_cache.py) - Simpler alternative
- [Parallel CPG](../indexing/parallel_cpg.py) - For large repos
- [Incremental Updates](../indexing/incremental_cpg.py) - For re-indexing

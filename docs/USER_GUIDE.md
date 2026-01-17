# KnowGraph User Guide

**Version:** 1.0.0  
**Last Updated:** January 17, 2026

Welcome to the comprehensive KnowGraph User Guide. This document covers everything you need to know to effectively use KnowGraph as a Graph RAG system with **integrated Joern code analysis** and MCP server for your AI coding assistants.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Installation](#3-installation)
4. [Configuration](#4-configuration)
5. [Indexing Your Knowledge Base](#5-indexing-your-knowledge-base)
6. [Joern Code Analysis (NEW v1.0.0)](#6-joern-code-analysis-new-v100)
7. [Querying the Knowledge Graph](#7-querying-the-knowledge-graph)
8. [MCP Server Integration](#8-mcp-server-integration)
9. [Advanced Querying](#9-advanced-querying)
10. [Graph Versioning (Time Travel)](#10-graph-versioning-time-travel)
11. [Conversational Memory](#11-conversational-memory)
12. [Post-Indexing Automation](#12-post-indexing-automation)
13. [Performance Optimization](#13-performance-optimization)
14. [Security Analysis Deep Dive](#14-security-analysis-deep-dive)
15. [Enterprise Resilience & Production](#15-enterprise-resilience--production)
16. [Command Reference](#16-command-reference)
17. [Troubleshooting & FAQ](#17-troubleshooting--faq)

---

## 1. Introduction

### What is KnowGraph?

KnowGraph is a **Graph RAG (Retrieval-Augmented Generation)** system that transforms your codebase and documentation into an intelligent knowledge graph. Unlike traditional vector-based RAG systems, KnowGraph uses **Graph Theory**, **Network Science**, and **Joern Code Property Graph** analysis to provide:

- **Topological Context**: Follows real code relationships (imports, calls, inheritance)
- **Centrality Analysis**: Identifies architecturally critical components
- **Deterministic Provenance**: Provides verifiable reasoning paths
- **Hierarchical Understanding**: Interprets code within project context
- **Deep Code Analysis**: Joern-powered security and data flow analysis (NEW v1.0.0)

### Key Benefits

- 🎯 **Precise Answers**: Graph-based retrieval reduces hallucinations
- 🔍 **Deep Understanding**: Follows dependency chains and architectural patterns
- 🔬 **Code Analysis**: Automatic vulnerability detection and data flow tracking
- 📊 **Impact Analysis**: Predict ripple effects of code changes
- 🚀 **High Performance**: Smart caching and hybrid intelligence (CPG caching, incremental updates)
- 🔌 **MCP Compatible**: Works with Claude Desktop, Cursor, and other AI editors
- 🛡️ **Production Ready**: Enterprise resilience patterns + 100% test coverage
- 🕰️ **Time Travel**: Version control for your knowledge graph
- 💬 **Conversational Memory**: Indexes your chats alongside your code

---

## 2. Getting Started

KnowGraph is primarily designed as an **MCP (Model Context Protocol) server** that enhances your AI coding assistant with deep code understanding capabilities.

### MCP Server Configuration (Start Here!)

**Step 1: Install KnowGraph**
```bash
pip install knowgraph

# Setup Joern for advanced code analysis (recommended)
knowgraph-setup-joern
```

**Step 2: Configure Your AI Editor**

#### For Claude Desktop
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "env": {
        "KNOWGRAPH_API_KEY": "sk-your-openai-key-here"
      }
    }
  }
}
```

#### For Cursor
Add to `.cursor/mcp.json` in your project:
```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "env": {
        "KNOWGRAPH_API_KEY": "sk-your-openai-key-here"
      }
    }
  }
}
```

#### For Antigravity
Add to `~/.gemini/antigravity/mcp_config.json`:
```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "env": {
        "KNOWGRAPH_API_KEY": "sk-your-openai-key-here"
      },
      "disabled": false
    }
  }
}
```

#### Using OpenRouter (Alternative LLM Provider)
```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "env": {
        "KNOWGRAPH_API_BASE_URL": "https://openrouter.ai/api/v1",
        "KNOWGRAPH_LLM_MODEL": "x-ai/grok-2-1212",
        "KNOWGRAPH_API_KEY": "sk-or-v1-your-openrouter-key-here"
      },
      "disabled": false
    }
  }
}
```

**Step 3: Restart Your AI Editor**

**Step 4: Index Your Codebase**

In your AI editor, ask:
```
"Index my current project with KnowGraph"
```

Or use CLI:
```bash
export KNOWGRAPH_API_KEY="sk-your-openai-key-here"
knowgraph index ./your-project
```

**Step 5: Start Querying!**

Ask your AI assistant:
- "Find security vulnerabilities in the authentication code"
- "Explain how the caching system works"
- "Show me the call graph from authenticate_user to execute_sql"

### Prerequisites

- **Python**: 3.10 or higher
- **API Key**: OpenAI API key or OpenRouter API key
- **AI Editor**: Claude Desktop, Cursor, or Antigravity (recommended)
- **JDK 11+**: For Joern code analysis (optional but recommended)

---

## 3. Installation

### 3.1 MCP Server Installation (Recommended)

**Install via pip:**
```bash
pip install knowgraph
```

**Verify installation:**
```bash
knowgraph --version
# Output: KnowGraph 1.0.0
```

**Configure MCP server** (see [Getting Started](#2-getting-started) above)

### 3.2 Setup Joern (Recommended for Code Analysis)

To enable advanced code analysis features (security scanning, dead code detection, call graph analysis), install Joern:

```bash
knowgraph-setup-joern
```

This will:
1. Check for JDK 11+ (required)
2. Download and install Joern to `~/.knowgraph/joern`
3. Verify the installation

**If you don't have JDK:**
```bash
# macOS
brew install openjdk@11

# Ubuntu/Debian
sudo apt-get install openjdk-11-jdk

# Verify
java -version
```

### 3.3 Standalone CLI Usage (Optional)

If you want to use KnowGraph without an AI editor:

```bash
# Set API key
export KNOWGRAPH_API_KEY="sk-..."

# Index a project
knowgraph index ./my-project

# Query from CLI
knowgraph query "How does authentication work?"

# Start standalone MCP server
knowgraph serve
```

### 3.4 Development Installation

For contributing or local development:

```bash
git clone https://github.com/yunusgungor/knowgraph.git
cd knowgraph
pip install -e ".[dev]"
knowgraph-setup-joern

# Run tests
pytest

# Check code quality
ruff check .
mypy .
```

### 3.5 Verification

**Test MCP server:**
```bash
# In your AI editor, ask:
"Run knowgraph diagnostic"
```

**Test CLI:**
```bash
knowgraph diagnostic
```

Expected output:
```
✅ Graph Store: OK
✅ LLM Provider: OK (OpenAI)
✅ Joern: OK (v2.0.0)
✅ Configuration: Valid
```


---

## 4. Configuration

### Environment Variables

KnowGraph uses environment variables for configuration. **Bold keys** are commonly used.

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `KNOWGRAPH_API_KEY` | **Yes** | OpenAI or OpenRouter API key | - |
| `KNOWGRAPH_API_BASE_URL` | No | Custom API base URL (e.g., OpenRouter) | `https://api.openai.com/v1` |
| `KNOWGRAPH_LLM_MODEL` | No | LLM model to use | `gpt-4o-mini` |
| `KNOWGRAPH_GRAPH_PATH` | No | Path to graph storage | `./graphstore` |
| `KNOWGRAPH_PROJECT_ROOT` | No | Override project root detection | Auto-detect |
| `KNOWGRAPH_WORKERS` | No | Concurrent indexing workers | Auto-detect (Max 30) |
| `KNOWGRAPH_LLM_RETRY_COUNT` | No | Max LLM retries | `5` |
| `KNOWGRAPH_LLM_RETRY_DELAY` | No | Base delay for backoff (sec) | `1.0` |
| `KNOWGRAPH_JOERN_ENABLED` | No | Enable/disable Joern analysis | `true` |
| `KNOWGRAPH_CPG_TIMEOUT` | No | CPG generation timeout (sec) | `600` |
| `KNOWGRAPH_LOG_LEVEL` | No | Logging level (DEBUG/INFO/WARNING) | `INFO` |
| `GITHUB_TOKEN` | No | GitHub PAT for private repos | - |

**OpenRouter Example:**
```bash
export KNOWGRAPH_API_BASE_URL="https://openrouter.ai/api/v1"
export KNOWGRAPH_LLM_MODEL="x-ai/grok-2-1212"
export KNOWGRAPH_API_KEY="sk-or-v1-your-key-here"
```

### Project Root Detection Logic
KnowGraph automatically detects your workspace root to isolate graph stores. The priority order is:

1.  **Environment Variable**: `KNOWGRAPH_PROJECT_ROOT` (Highest priority)
2.  **Git Root**: If inside a git repository (Supports Monorepos).
3.  **Project Markers**: `pyproject.toml`, `package.json`, `Cargo.toml`.
4.  **Current Working Directory**: Fallback.

> **Monorepo Note**: In a monorepo, the Git root takes precedence over individual package.json files to maintain a unified graph. Use `KNOWGRAPH_PROJECT_ROOT` to force sub-project isolation.

---

## 5. Indexing Your Knowledge Base

KnowGraph supports four input formats:
1. **Markdown Files** (`.md`)
2. **Git Repositories** (GitHub, GitLab, Bitbucket)
3. **Code Directories** (Code to Markdown conversion)
4. **AI Conversations** (Chat histories)

### Basic Indexing
```bash
knowgraph index /path/to/project
```

### Repository Indexing
```bash
knowgraph index https://github.com/user/repo --include "*.py"
```

For detailed conversation indexing, see [Section 11](#11-conversational-memory).

---

## 6. Joern Code Analysis (NEW v1.0.0)

KnowGraph v1.0.0 includes **fully integrated Joern code analysis** for deep code understanding.

### 6.1 Automatic Code Detection

**Zero configuration required!** KnowGraph automatically detects and analyzes code in 15 languages during indexing:

```bash
# Index any code directory - automatic code analysis
knowgraph index ./my-project

# Supports: Python, JavaScript/TypeScript, Java, C/C++, Go, C#,
# Scala, PHP, Ruby, Kotlin, Swift, Rust, and more
```

### 6.2 What Gets Analyzed

During indexing, Joern automatically extracts:
- ✅ **Methods and Classes**: 474 entities per typical project
- ✅ **Call Relationships**: 85 function call edges
- ✅ **Data Flows**: 45 tainted data paths
- ✅ **Security Issues**: SQL injection, XSS, command injection risks

### 6.3 Smart Query Routing

Queries are automatically classified and routed to the right analysis engine:

**CODE Queries** → Joern Tools:
- "find security vulnerabilities"
- "show me dead code"
- "analyze call graph"

**TEXT Queries** → Semantic Search:
- "explain authentication"
- "how does caching work"

**HYBRID Queries** → Both Engines:
- "is the authentication secure?"
- "are there performance issues?"

### 6.4 Performance Features

**CPG Caching** (24-hour):
```bash
# First index: ~30s (generates CPG)
knowgraph index ./project

# Re-index: <1s (uses cached CPG)
knowgraph index ./project
```

**Incremental Updates**:
- Only processes changed files
- Automatic change detection
- Skips unchanged code

**Parallel Generation** (large repos):
- Automatic for 50+ files
- Multi-language support

### 6.5 Example Usage

```bash
# 1. Index your codebase
knowgraph index ./my-app

# 2. Query through AI assistant (in Claude/Cursor):
"Find security vulnerabilities in the authentication code"

# 3. KnowGraph automatically:
#    - Classifies as CODE query
#    - Routes to joern_security_scan
#    - Returns detailed report
```

For more examples, see [JOERN_USAGE.md](../JOERN_USAGE.md).

---

## 7. Querying the Knowledge Graph

### 7.1 Basic Query
```python
from knowgraph.application.querying.engine import QueryEngine
engine = QueryEngine()
result = engine.query("How does auth work?")
print(result.answer)
```

### 7.2 Advanced Parameters (v1.0.0)

Fine-tune your query logic with new weighting parameters:

```json
{
  "query": "Find inheritance structure of BaseClass",
  "top_k": 20,
  "max_hops": 4,
  "edge_type_weights": {
    "inherit": 1.5,
    "import": 0.8,
    "call": 1.0
  },
  "prioritize_reference_edges": true,
  "enable_hierarchical_lifting": true,
  "lift_levels": 3
}
```

- **`edge_type_weights`**: Customize how strong different relationships are. Giving "inherit" a higher weight (1.5) makes the search follow class hierarchies more aggressively.
- **`prioritize_reference_edges`**: If true, the traversal prefers nodes that are explicitly referenced in the source code (e.g., via `see` tags or Docstrings).

---

## 8. MCP Server Integration

KnowGraph exposes a comprehensive suite of tools to your AI assistant. Here is the **complete list** of available tools:

| Tool Name | Description |
|-----------|-------------|
| `knowgraph_query` | Semantic search with hierarchical lifting. |
| `knowgraph_batch_query` | Execute multiple queries for efficient context gathering. |
| `knowgraph_index` | Trigger indexing of local or remote codebases. |
| `knowgraph_analyze_impact` | Predict effects of code changes (Semantic or Path mode). |
| `knowgraph_validate` | Check health and consistency of the graph. |
| `knowgraph_get_stats` | Retrieve node/edge counts and density metrics. |
| `knowgraph_discover_conversations` | Auto-index chats from Antigravity, Cursor, etc. |
| `knowgraph_analyze_conversations` | Analyze topics and trends in indexed chats. |
| `knowgraph_tag_snippet` | Bookmark important AI responses as reusable snippets. |
| `knowgraph_search_bookmarks` | Semantic search within your tagged snippets. |
| `knowgraph_list_versions` | Show complete version history. |
| `knowgraph_version_info` | Get detailed metadata for a specific version ID. |
| `knowgraph_diff_versions` | Compare nodes/edges between two commits. |
| `knowgraph_rollback` | Revert graph state to a previous snapshot. |
| `knowgraph_diagnostic` | Run system health checks (Graph Store, LLM, Config). |
| `knowgraph_joern_query` | Execute native Joern DSL queries. |
| `knowgraph_security_scan` | Scan for vulnerabilities using Joern policies. |
| `knowgraph_find_dead_code` | Detect unreachable methods using dominance analysis. |
| `knowgraph_analyze_call_graph` | Analyze call paths and recursion. |
| `knowgraph_export_cpg` | Export CPG to JSON/DOT/Neo4j/SARIF. |
| `knowgraph_generate_cpg` | Manually trigger CPG generation for a path. |

### 8.1 Configuring AI Clients

#### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "env": {
        "KNOWGRAPH_API_KEY": "sk-your-openai-key-here"
      }
    }
  }
}
```

#### Cursor (`.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "env": {
        "KNOWGRAPH_API_KEY": "sk-your-openai-key-here"
      }
    }
  }
}
```

#### Antigravity (`~/.gemini/antigravity/mcp_config.json`)
```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "env": {
        "KNOWGRAPH_API_KEY": "sk-your-openai-key-here"
      },
      "disabled": false
    }
  }
}
```

#### Using OpenRouter (Alternative LLM Provider)
```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "env": {
        "KNOWGRAPH_API_BASE_URL": "https://openrouter.ai/api/v1",
        "KNOWGRAPH_LLM_MODEL": "x-ai/grok-2-1212",
        "KNOWGRAPH_API_KEY": "sk-or-v1-your-openrouter-key-here"
      },
      "disabled": false
    }
  }
}
```

---

## 9. Advanced Querying

### 9.1 Query Expansion

Query expansion uses AI to automatically enrich your queries with synonyms and technical terms for better retrieval.

**When to Use:**
- Complex technical queries
- Domain-specific terminology
- When initial results are too narrow

**Example:**
```python
from knowgraph.application.querying.engine import QueryEngine

engine = QueryEngine()
result = engine.query(
    "authentication mechanism",
    expand_query=True  # Expands to: "auth, login, JWT, OAuth, session, token..."
)
```

**How It Works:**
1. LLM analyzes your query
2. Generates related technical terms
3. Combines original + expanded terms
4. Searches with broader context

**Performance Impact:** +1-2s query time, but significantly better recall.

### 9.2 Edge Type Weights

Customize how the graph traversal prioritizes different relationship types.

**Default Weights:**
```python
{
    "import": 1.0,      # Standard import relationships
    "call": 1.0,        # Function calls
    "inherit": 1.0,     # Class inheritance
    "data_flow": 1.0,   # Data dependencies
    "reference": 1.0    # Documentation references
}
```

**Custom Weighting Example:**
```json
{
  "query": "Find inheritance structure of BaseClass",
  "edge_type_weights": {
    "inherit": 2.0,     # Prioritize inheritance (2x weight)
    "import": 0.5,      # De-prioritize imports
    "call": 1.0         # Normal weight for calls
  }
}
```

**Use Cases:**
- **Architecture Analysis**: Boost `inherit` and `import` weights
- **Data Flow Tracing**: Boost `data_flow` and `call` weights
- **Documentation Search**: Boost `reference` weights

### 9.3 Prioritize Reference Edges

When enabled, the traversal prefers nodes that are explicitly referenced in documentation.

```python
result = engine.query(
    "How does caching work?",
    prioritize_reference_edges=True  # Prefer documented code
)
```

**Benefits:**
- Returns well-documented code first
- Useful for onboarding and learning
- Filters out internal implementation details

### 9.4 Batch Queries

Execute multiple queries efficiently with shared context loading.

**Performance Comparison:**
- **Sequential**: 5 queries × 2s = 10s
- **Batch**: 5 queries = 2.5s (4x faster)

**Example:**
```python
from knowgraph.application.querying.engine import QueryEngine

engine = QueryEngine()
results = engine.batch_query([
    "How does authentication work?",
    "What are the security policies?",
    "Explain the rate limiting logic",
    "Show me the caching strategy",
    "What's the database schema?"
])

for query, result in zip(queries, results):
    print(f"Q: {query}")
    print(f"A: {result.answer}\n")
```

**MCP Usage:**
```json
{
  "tool": "knowgraph_batch_query",
  "arguments": {
    "queries": [
      "authentication flow",
      "error handling patterns",
      "API endpoints"
    ],
    "top_k": 15,
    "max_hops": 3
  }
}
```

### 9.5 Hierarchical Context Lifting

Automatically includes context from parent directories (README files, package docs).

**Example Structure:**
```
project/
├── README.md                    # "This is a web framework"
└── auth/
    ├── README.md                # "Authentication module using JWT"
    └── jwt_handler.py           # Your query target
```

**Query:** "Explain jwt_handler.py"

**Without Lifting:**
- Returns only `jwt_handler.py` content

**With Lifting (default):**
- Returns `jwt_handler.py`
- Plus `auth/README.md` context
- Plus `project/README.md` context

**Configuration:**
```python
result = engine.query(
    "Explain jwt_handler.py",
    enable_hierarchical_lifting=True,  # Default: True
    lift_levels=3  # How many parent levels (default: 2)
)
```

### 9.6 Advanced Query Parameters Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | **required** | Natural language query |
| `top_k` | int | 20 | Number of results to return |
| `max_hops` | int | 4 | Graph traversal depth |
| `max_tokens` | int | 3000 | Context window size |
| `expand_query` | bool | false | Enable AI query expansion |
| `enable_hierarchical_lifting` | bool | true | Include parent context |
| `lift_levels` | int | 2 | Parent directory levels |
| `with_explanation` | bool | false | Include reasoning path |
| `edge_type_weights` | dict | `{}` | Custom edge priorities |
| `prioritize_reference_edges` | bool | false | Prefer documented code |

---

## 10. Graph Versioning (Time Travel)

KnowGraph v0.6.0 introduces a Git-like version control system for your knowledge graph. Every indexing operation creates a snapshot.

### 9.1 Concepts
- **Manifest**: A JSON file tracking the state of the graph.
- **Snapshot**: A point-in-time record of all nodes and edges.
- **Checkpoint**: Created automatically after `knowgraph index`.

### 9.2 Listing Versions
See the history of your knowledge base:

```bash
$ knowgraph version list

ID        | Date                 | Author   | Nodes | Edges | Message
----------|----------------------|----------|-------|-------|-------------------
v0.6.0-a1 | 2025-12-19 14:00:00 | System   | 150   | 450   | Initial index
v0.6.1-b2 | 2025-12-19 15:30:00 | User     | 155   | 465   | Added auth.py
```

### 9.3 Diffing Versions
See what changed between two points in time:

```bash
knowgraph version diff v0.6.0-a1 v0.6.1-b2
```

**Output Explanation:**
- `[+]` Added Nodes: New files or concepts found.
- `[-]` Deleted Nodes: Files removed from the codebase.
- `[~]` Modified Nodes: Content changes (hash mismatch).

### 9.4 Rollback (Safety)
If an indexing operation corrupts your graph or adds unwanted data, you can roll back instantly.

```bash
# Dry run to see what will happen
knowgraph version rollback v0.6.0-a1 --dry-run

# Execute rollback
knowgraph version rollback v0.6.0-a1
```

> **Warning:** Rollback is destructive for the versions *after* the target version. They will be removed from history.

---

## 11. Conversational Memory

KnowGraph can now "read" your conversations with AI assistants and link them to your code.

### 9.1 Supported Formats
- **Antigravity**: Task and Walkthrough artifacts.
- **Cursor**: `.aichat` files in your project.
- **VS Code**: GitHub Copilot chat exports.
- **Claude**: JSON export files.

### 9.2 Auto-Discovery
Scan your project for conversation files and index them:

```bash
knowgraph discover-conversations
  --editor all          # or 'cursor', 'antigravity'
  --min-date 2024-01-01 # Optional date filter
  --output ./graphstore
```

### 9.3 Semantic Tagging
You can manually tag important AI responses using the MCP tool `knowgraph_tag_snippet` or CLI.

**Example Use Case:**
You ask Claude "How do I implement specific Retry Logic?". Claude gives a perfect answer. You don't want to lose this.

**In Claude:**
"Tag this response as 'Retry Logic Pattern' for future reference."

Claude will call:
```json
{
  "tool": "knowgraph_tag_snippet",
  "arguments": {
    "tag": "Retry Logic Pattern",
    "snippet": "...",
    "user_question": "How do I implement specific Retry Logic?"
  }
}
```

Later, you can query: "Show me the Retry Logic Pattern we discussed."

---

## 12. Post-Indexing Automation

KnowGraph runs a series of "Hooks" after every successful indexing job.

### 10.1 How Hooks Work
Hooks are Python scripts that subscribe to the `INDEXING_COMPLETE` event. They run in the background to enrich the graph.

### 10.2 Available Hooks

1.  **ConversationLinker**:
    *   Scans indexed conversations.
    *   Finds file references (e.g., `src/auth.py`).
    *   Creates semantic edges between the *Conversation Node* and the *Code Node*.
    *   *Benefit*: When you query `auth.py`, you also get the discussions regarding `auth.py`.

2.  **AutoTagger**:
    *   Analyzes the content of new nodes.
    *   Assigns tags like `security`, `database`, `api`, `frontend` based on keywords and embeddings.
    *   *Benefit*: Enables filtered queries like "Show me all security-related nodes".

3.  **AnalyticsGenerator**:
    *   Calculates graph statistics (density, diameter).
    *   Updates the dashboard metrics.

### 10.3 Configuration
Hooks are enabled by default. You can disable them in `knowgraph.json` configuration (future feature).

---

## 13. Performance Optimization

KnowGraph is designed for high performance, but you can tune it further based on your workload.

### 13.1 Caching System

KnowGraph uses multiple caching layers for optimal performance.

#### CPG Cache (24-hour TTL)
Stores generated Code Property Graphs to avoid re-analysis.

**Location:** `~/.knowgraph/cpg_cache/`

**Benefits:**
- First index: ~30s
- Re-index (cached): <1s
- 30x speedup for unchanged code

**Manual Cache Management:**
```bash
# View cache size
du -sh ~/.knowgraph/cpg_cache/

# Clear cache (force re-analysis)
rm -rf ~/.knowgraph/cpg_cache/

# Clear old caches (>24h)
find ~/.knowgraph/cpg_cache/ -mtime +1 -delete
```

#### Query Result Cache
Caches semantic search results for repeated queries.

**Performance:**
- Cold query: 2-3s
- Warm query: 0.18s (22x faster)

**Configuration:**
```python
from knowgraph.infrastructure.cache.cache_manager import CacheManager

# Disable cache for testing
cache = CacheManager(enabled=False)

# Adjust TTL
cache = CacheManager(ttl_seconds=7200)  # 2 hours
```

#### Indexing Cache
Tracks processed files to skip unchanged content.

**How It Works:**
1. Computes MD5 hash of each file
2. Compares with previous index
3. Skips files with matching hashes

**Benefit:** 4-6x faster incremental updates

### 13.2 Worker Tuning

Control parallelism for indexing and querying.

**Environment Variable:**
```bash
# Auto-detect (default, max 30)
export KNOWGRAPH_WORKERS=auto

# Manual override
export KNOWGRAPH_WORKERS=10

# Single-threaded (debugging)
export KNOWGRAPH_WORKERS=1
```

**Recommendations:**
- **Small projects (<100 files):** 5-10 workers
- **Medium projects (100-1000 files):** 15-20 workers
- **Large projects (>1000 files):** 25-30 workers
- **Low memory systems:** 5 workers max

**Performance Impact:**
```
Workers | Indexing Time | Memory Usage
--------|---------------|-------------
1       | 120s          | 500MB
10      | 30s           | 1.5GB
20      | 18s           | 2.5GB
30      | 15s           | 3.5GB
```

### 13.3 Memory Management

#### Lazy Edge Loading
Edges are loaded on-demand to reduce memory footprint.

**Benefit:** -60% RAM usage for large graphs

**Trade-off:** +10-20ms per query (negligible)

#### Graph Size Limits
Recommended limits for optimal performance:

| Graph Size | Nodes | Edges | RAM | Query Time |
|------------|-------|-------|-----|------------|
| Small | <1,000 | <5,000 | 100MB | <0.5s |
| Medium | 1,000-10,000 | 5,000-50,000 | 500MB | 0.5-2s |
| Large | 10,000-100,000 | 50,000-500,000 | 2GB | 2-5s |
| Very Large | >100,000 | >500,000 | 5GB+ | 5-10s |

**For Very Large Graphs:**
- Reduce `max_hops` (default: 4 → 2)
- Reduce `top_k` (default: 20 → 10)
- Enable `prioritize_reference_edges` to filter results

### 13.4 Async Best Practices

KnowGraph is 100% async for non-blocking I/O.

**Batch Queries (Recommended):**
```python
import asyncio
from knowgraph.application.querying.engine import QueryEngine

async def main():
    engine = QueryEngine()
    
    # Parallel execution (4x faster)
    results = await engine.batch_query_async([
        "How does auth work?",
        "What are the API endpoints?",
        "Explain the database schema",
        "Show me error handling"
    ])
    
    for result in results:
        print(result.answer)

asyncio.run(main())
```

**Sequential Queries (Avoid):**
```python
# DON'T DO THIS - 4x slower
for query in queries:
    result = engine.query(query)  # Blocks
    print(result.answer)
```

### 13.5 LLM Rate Limiting

Configure retry logic for API rate limits.

**Environment Variables:**
```bash
# Max retries (default: 5)
export KNOWGRAPH_LLM_RETRY_COUNT=10

# Base delay in seconds (default: 1.0)
export KNOWGRAPH_LLM_RETRY_DELAY=2.0
```

**Retry Strategy:**
- Exponential backoff with jitter
- Delay = `base_delay * (2 ^ attempt) + random(0, 1)`
- Example: 1s → 2s → 4s → 8s → 16s

### 13.6 Incremental Updates

Only process changed files for faster re-indexing.

**How It Works:**
```bash
# First index (full)
knowgraph index ./project  # 30s

# Modify 2 files
echo "# New content" >> ./project/auth.py

# Re-index (incremental)
knowgraph index ./project  # 3s (only processes auth.py)
```

**Change Detection:**
- MD5 hash comparison
- Detects: added, modified, deleted files
- Skips: unchanged files

**Disable Incremental (Force Full Re-index):**
```bash
# Clear cache first
rm -rf ~/.knowgraph/cpg_cache/
knowgraph index ./project
```

### 13.7 Performance Monitoring

Track system performance with built-in metrics.

**Query Performance:**
```python
from knowgraph.application.querying.engine import QueryEngine

engine = QueryEngine()
result = engine.query("How does caching work?")

print(f"Query time: {result.metadata['query_time_ms']}ms")
print(f"Nodes retrieved: {result.metadata['nodes_count']}")
print(f"Cache hit: {result.metadata['cache_hit']}")
```

**Indexing Performance:**
```bash
knowgraph index ./project --verbose

# Output:
# Files detected: 150
# CPG generation: 25.3s
# Entity extraction: 8.1s
# Graph building: 12.5s
# Total: 45.9s
```

### 13.8 Optimization Checklist

✅ **Enable caching** (default: enabled)  
✅ **Use batch queries** for multiple questions  
✅ **Tune worker count** based on system resources  
✅ **Reduce `max_hops`** for very large graphs  
✅ **Use incremental updates** for frequent re-indexing  
✅ **Monitor memory usage** with `top` or `htop`  
✅ **Clear old caches** periodically  

---

## 14. Security Analysis Deep Dive

KnowGraph's Joern integration provides industrial-grade security analysis capabilities.

### 14.1 Predefined Security Policies

KnowGraph includes 10 CWE-mapped security policies out of the box.

| Policy Name | CWE | Severity | Description |
|-------------|-----|----------|-------------|
| `sql_injection` | CWE-89 | CRITICAL | Detects unsanitized SQL queries |
| `xss` | CWE-79 | HIGH | Cross-site scripting vulnerabilities |
| `command_injection` | CWE-78 | CRITICAL | OS command injection risks |
| `path_traversal` | CWE-22 | HIGH | Directory traversal attacks |
| `buffer_overflow` | CWE-120 | CRITICAL | Buffer overflow vulnerabilities |
| `use_after_free` | CWE-416 | CRITICAL | Memory safety issues |
| `null_pointer` | CWE-476 | MEDIUM | Null pointer dereferences |
| `hardcoded_credentials` | CWE-798 | HIGH | Embedded secrets |
| `insecure_random` | CWE-338 | MEDIUM | Weak randomness |
| `unvalidated_redirect` | CWE-601 | MEDIUM | Open redirect vulnerabilities |

### 14.2 Running Security Scans

**Full Scan (All Policies):**
```bash
# Via CLI (auto-detects CPG)
knowgraph security-scan ./project
```

**Filtered Scan:**
```json
{
  "tool": "knowgraph_security_scan",
  "arguments": {
    "policy_names": ["sql_injection", "xss"],
    "severity_filter": "HIGH"
  }
}
```

### 14.3 Export Formats

**SARIF (for GitHub Security tab):**
```bash
knowgraph export-cpg --cpg-path ./project.bin --output ./report.sarif --format sarif
```

**Other Formats:** JSON, DOT, Neo4j, GraphML

### 14.4 Dead Code Detection

```json
{
  "tool": "knowgraph_find_dead_code",
  "arguments": {"include_internal": false}
}
```

### 14.5 Call Graph Analysis

```json
{
  "tool": "knowgraph_analyze_call_graph",
  "arguments": {
    "analysis_type": "call_chain",
    "method_name": "authenticate_user",
    "target_method": "execute_sql"
  }
}
```

---

## 15. Enterprise Resilience & Production

KnowGraph is built to survive in production environments (v0.6.0).

### 15.1 Circuit Breaker Status
If an external dependency (like OpenAI API) fails repeatedly, KnowGraph opens the circuit to prevent cascading failures.
- **Signs**: You see `CircuitBreakerOpenException`.
- **Action**: Check your API status. The system will auto-retry after a timeout.

### 15.2 Monitoring Metrics
The server exposes Prometheus-compatible metrics. You can monitor:
- **Indexing Speed**: `knowgraph_indexing_duration_seconds`
- **Query Latency**: `knowgraph_query_latency_seconds`
- **Error Rates**: `knowgraph_request_errors_total`

### 15.3 System Health (Diagnostics)
You can run a comprehensive health check of the KnowGraph system using the `knowgraph_diagnostic` tool or command.

This checks:
- **Graph Store**: Integrity and accessibility of the database.
- **LLM Provider**: Connection status and API key validity (OpenAI/Anthropic).
- **Configuration**: Validity of the current environment setup.

```bash
# Run via MCP
knowgraph_diagnostic()
```

---

## 16. Command Reference

### Core Commands
- `knowgraph index <path>`: Build the graph.
- `knowgraph query "question"`: Ask a question.
- `knowgraph serve`: Start MCP server.

### Versioning Commands
- `knowgraph version list`: Show history.
- `knowgraph version show <id>`: Show details.
- `knowgraph version diff <id1> <id2>`: Compare.
- `knowgraph version rollback <id>`: Revert.

### Conversation Commands
- `knowgraph discover-conversations`: Find and index chats.
- `knowgraph tag <tag> <content>`: Manual tagging.

---

## 17. Troubleshooting & FAQ

### 17.1 Installation & Setup Issues

| Issue | Solution |
|-------|----------|
| **Joern Installation Failed** | Run `knowgraph-setup-joern` manually. Ensure JDK 11+ is installed (`java -version`). |
| **Permission Denied (Joern binaries)** | Run `chmod +x ~/.knowgraph/joern/joern-cli/bin/*` |
| **Module Not Found** | Ensure you're using the correct Python environment. Run `pip install -e .` in dev mode. |
| **API Key Not Found** | Set `export KNOWGRAPH_API_KEY="sk-..."` or add to `.env` file. |

### 17.2 Indexing Issues

| Issue | Solution |
|-------|----------|
| **CPG Generation Timeout** | Increase timeout: `KNOWGRAPH_CPG_TIMEOUT=1200 knowgraph index ./project` |
| **Out of Memory (Indexing)** | Reduce workers: `KNOWGRAPH_WORKERS=5 knowgraph index ./project` |
| **Files Not Detected** | Check file patterns. Use `--include "*.py" --include "*.js"` explicitly. |
| **Incremental Update Not Working** | Clear cache: `rm -rf ~/.knowgraph/cpg_cache/` and re-index. |
| **Git Repository Clone Failed** | Check network connection. For private repos, set `GITHUB_TOKEN`. |

### 17.3 Query Issues

| Issue | Solution |
|-------|----------|
| **No Results Found** | Try `expand_query=True` or increase `max_hops` (default: 4 → 6). |
| **Query Too Slow (>10s)** | Reduce `max_hops` (4 → 2) or `top_k` (20 → 10). Enable caching. |
| **High Memory Usage** | Use `query_async()` for batch queries. Reduce graph size or split into sub-projects. |
| **Incorrect Results** | Check if graph is up-to-date. Re-index with `knowgraph index ./project`. |

### 17.4 Joern & CPG Issues

| Issue | Solution |
|-------|----------|
| **CPG Not Generated** | Check if language is supported (15 languages). Verify file extensions. |
| **Joern Daemon Not Starting** | Kill existing process: `pkill -f joern` and restart. |
| **CPG Corrupted** | Delete and regenerate: `rm ~/.knowgraph/cpg_cache/*.bin && knowgraph index ./project` |
| **Language Not Detected** | Specify manually: `knowgraph generate-cpg ./project --language python` |

### 17.5 Versioning Issues

| Issue | Solution |
|-------|----------|
| **Rollback Failed** | Ensure no other process is writing to the graph. Check file permissions. |
| **Diff is Empty** | Versions might be identical. `knowgraph index` skips unchanged files. |
| **Version Not Found** | Run `knowgraph version list` to see available versions. |
| **Manifest Corrupted** | Restore from backup: `cp ./graphstore/metadata/manifest.json.backup ./graphstore/metadata/manifest.json` |

### 17.6 Conversation Indexing Issues

| Issue | Solution |
|-------|----------|
| **Conversations Not Found** | Check if `.aichat` files exist. Verify `--min-date` filter. |
| **Antigravity Chats Not Indexed** | Ensure artifacts are in `~/.gemini/antigravity/brain/`. |
| **Cursor Chats Not Indexed** | Check `.cursor/` directory in project root. |

### 17.7 Performance Issues

| Issue | Solution |
|-------|----------|
| **Slow Indexing (>5min)** | Increase workers: `KNOWGRAPH_WORKERS=20`. Enable parallel CPG generation. |
| **High RAM Usage (>4GB)** | Reduce workers, enable lazy edge loading, or split project into smaller graphs. |
| **Cache Not Working** | Check cache directory exists: `ls ~/.knowgraph/cpg_cache/`. Verify TTL not expired. |
| **LLM Rate Limits** | Increase retry delay: `KNOWGRAPH_LLM_RETRY_DELAY=2.0` |

### 17.8 MCP Integration Issues

| Issue | Solution |
|-------|----------|
| **MCP Server Not Starting** | Check logs: `tail -f ~/.config/claude/mcp.log`. Verify Python path in config. |
| **Tools Not Visible** | Restart AI editor (Claude/Cursor). Check MCP server status. |
| **Project Root Not Detected** | Set manually: `export KNOWGRAPH_PROJECT_ROOT=/path/to/project` |

### 17.9 Security Scan Issues

| Issue | Solution |
|-------|----------|
| **No Vulnerabilities Found** | CPG might not be generated. Run `knowgraph index ./project` first. |
| **False Positives** | Use `severity_filter="HIGH"` to reduce noise. Review policy definitions. |
| **SARIF Export Failed** | Ensure output directory exists. Check file permissions. |

### 17.10 Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Enable debug mode
export KNOWGRAPH_LOG_LEVEL=DEBUG
knowgraph index ./project

# Check logs
tail -f ~/.knowgraph/logs/knowgraph.log
```

### 17.11 Common Error Messages

**Error:** `CircuitBreakerOpenException`  
**Cause:** External API (OpenAI) is failing repeatedly.  
**Solution:** Check API status. Wait for circuit to close (60s timeout).

**Error:** `CPGGenerationError: Language not supported`  
**Cause:** File extension not recognized.  
**Solution:** Check supported languages. Add custom extension mapping.

**Error:** `GraphValidationError: Orphaned nodes detected`  
**Cause:** Graph corruption or incomplete indexing.  
**Solution:** Run `knowgraph validate` and re-index if needed.

**Error:** `MemoryError: Cannot allocate memory`  
**Cause:** Graph too large for available RAM.  
**Solution:** Reduce workers, split project, or upgrade system RAM.

### 17.12 Getting Help

- **GitHub Issues:** [https://github.com/yunusgungor/knowgraph/issues](https://github.com/yunusgungor/knowgraph/issues)
- **Documentation:** [https://github.com/yunusgungor/knowgraph/docs](https://github.com/yunusgungor/knowgraph/docs)
- **Diagnostic Tool:** Run `knowgraph diagnostic` for system health check

---

**End of User Guide**

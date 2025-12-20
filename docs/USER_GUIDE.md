# KnowGraph User Guide

**Version:** 0.6.0  
**Last Updated:** December 2025

Welcome to the comprehensive KnowGraph User Guide. This document covers everything you need to know to effectively use KnowGraph as a Graph RAG system and MCP server for your AI coding assistants.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Installation](#3-installation)
4. [Configuration](#4-configuration)
5. [Indexing Your Knowledge Base](#5-indexing-your-knowledge-base)
6. [Querying the Knowledge Graph](#6-querying-the-knowledge-graph)
7. [MCP Server Integration](#7-mcp-server-integration)
8. [Advanced Features](#8-advanced-features)
9. [Graph Versioning (Time Travel)](#9-graph-versioning-time-travel) (NEW)
10. [Conversational Memory](#10-conversational-memory) (NEW)
11. [Post-Indexing Automation](#11-post-indexing-automation) (NEW)
12. [Enterprise Resilience & Metrics](#12-enterprise-resilience--metrics) (NEW)
13. [Command Reference](#13-command-reference)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Introduction

### What is KnowGraph?

KnowGraph is a **Graph RAG (Retrieval-Augmented Generation)** system that transforms your codebase and documentation into an intelligent knowledge graph. Unlike traditional vector-based RAG systems, KnowGraph uses **Graph Theory** and **Network Science** to provide:

- **Topological Context**: Follows real code relationships (imports, calls, inheritance)
- **Centrality Analysis**: Identifies architecturally critical components
- **Deterministic Provenance**: Provides verifiable reasoning paths
- **Hierarchical Understanding**: Interprets code within project context

### Key Benefits

- 🎯 **Precise Answers**: Graph-based retrieval reduces hallucinations
- 🔍 **Deep Understanding**: Follows dependency chains and architectural patterns
- 📊 **Impact Analysis**: Predict ripple effects of code changes
- 🚀 **High Performance**: Smart caching and hybrid intelligence
- 🔌 **MCP Compatible**: Works with Claude Desktop, Cursor, and other AI editors
- 🛡️ **Production Ready**: Enterprise resilience patterns
- 🕰️ **Time Travel**: Version control for your knowledge graph
- 💬 **Conversational Memory**: Indexes your chats alongside your code

---

## 2. Getting Started

### Prerequisites

- **Python**: 3.10 or higher
- **API Key**: OpenAI API key (for entity extraction)
- **AI Editor** (optional): Claude Desktop, Cursor, or Antigravity

### Quick Start (30 Seconds)

```bash
# 1. Install KnowGraph
pip install knowgraph

# 2. Set your API key
export KNOWGRAPH_API_KEY="sk-..."

# 3. Index your documentation
knowgraph index /path/to/docs

# 4. Start the MCP server
knowgraph serve
```

---

## 3. Installation

```bash
pip install knowgraph
```

For development:
```bash
git clone https://github.com/yunusgungor/knowgraph.git
cd knowgraph
pip install -e ".[dev]"
```

---

## 4. Configuration

### Environment Variables

KnowGraph uses environment variables for configuration. **Bold keys** are commonly used.

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `KNOWGRAPH_API_KEY` | **Yes** | OpenAI API key for LLM operations | - |
| `KNOWGRAPH_MODEL` | No | OpenAI model to use | `gpt-5-nano` |
| `KNOWGRAPH_GRAPH_PATH` | No | Path to graph storage | `./graphstore` |
| `KNOWGRAPH_PROJECT_ROOT` | No | Override project root detection | Auto-detect |
| `KNOWGRAPH_WORKERS` | No | Concurrent indexing workers | Auto-detect (Max 30) |
| `KNOWGRAPH_LLM_RETRY_COUNT` | No | Max LLM retries | `5` |
| `KNOWGRAPH_LLM_RETRY_DELAY` | No | Base delay for backoff (sec) | `1.0` |
| `GITHUB_TOKEN` | No | GitHub PAT for private repos | - |

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

For detailed conversation indexing, see [Section 10](#10-conversational-memory).

---

## 6. Querying the Knowledge Graph

### 6.1 Basic Query
```python
from knowgraph.application.querying.engine import QueryEngine
engine = QueryEngine()
result = engine.query("How does auth work?")
print(result.answer)
```

### 6.2 Advanced Parameters (v0.6.0)

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

## 7. MCP Server Integration

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

---

## 9. Graph Versioning (Time Travel)

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

## 10. Conversational Memory

KnowGraph can now "read" your conversations with AI assistants and link them to your code.

### 10.1 Supported Formats
- **Antigravity**: Task and Walkthrough artifacts.
- **Cursor**: `.aichat` files in your project.
- **VS Code**: GitHub Copilot chat exports.
- **Claude**: JSON export files.

### 10.2 Auto-Discovery
Scan your project for conversation files and index them:

```bash
knowgraph discover-conversations
  --editor all          # or 'cursor', 'antigravity'
  --min-date 2024-01-01 # Optional date filter
  --output ./graphstore
```

### 10.3 Semantic Tagging
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

## 11. Post-Indexing Automation

KnowGraph runs a series of "Hooks" after every successful indexing job.

### 11.1 How Hooks Work
Hooks are Python scripts that subscribe to the `INDEXING_COMPLETE` event. They run in the background to enrich the graph.

### 11.2 Available Hooks

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

### 11.3 Configuration
Hooks are enabled by default. You can disable them in `knowgraph.json` configuration (future feature).

---

## 12. Enterprise Resilience & Metrics

KnowGraph is built to survive in production environments (v0.6.0). 

### 12.1 Circuit Breaker Status
If an external dependency (like OpenAI API) fails repeatedly, KnowGraph opens the circuit to prevent cascading failures.
- **Signs**: You see `CircuitBreakerOpenException`.
- **Action**: Check your API status. The system will auto-retry after a timeout.

### 12.2 Monitoring Metrics
The server exposes Prometheus-compatible metrics. You can monitor:
- **Indexing Speed**: `knowgraph_indexing_duration_seconds`
- **Query Latency**: `knowgraph_query_latency_seconds`
- **Error Rates**: `knowgraph_request_errors_total`

### 12.3 System Health (Diagnostics)
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

## 13. Command Reference

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

## 14. Troubleshooting

| Issue | Solution |
|-------|----------|
| **Rollback Failed** | Ensure no other process is writing to the graph. Check permissions. |
| **Conversations Not Found** | Check if `.aichat` files are in the scanned directory. Verify `--min-date`. |
| **High Memory Usage** | Graph algorithms can be memory intensive for >10k nodes. Use `query_async`. |
| **Diff is Empty** | The versions might be identical. `knowgraph index` skips unchanged files. |

For more help, please file an issue on GitHub.

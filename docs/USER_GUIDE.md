# KnowGraph User Guide

**Version:** 1.0.1  
**Last Updated:** August 22, 2026

Welcome to the comprehensive KnowGraph User Guide. This document covers everything you need to know to effectively use KnowGraph as a Graph RAG system with **integrated Joern code analysis** and MCP server for your AI coding assistants.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Getting Started](#2-getting-started)
3. [Installation](#3-installation)
4. [Configuration](#4-configuration)
5. [Indexing Your Knowledge Base](#5-indexing-your-knowledge-base)
6. [Joern Code Analysis](#6-joern-code-analysis)
7. [Querying the Knowledge Graph](#7-querying-the-knowledge-graph)
8. [MCP Server Integration](#8-mcp-server-integration)
9. [Advanced Querying](#9-advanced-querying)
10. [Graph Engineering: Grounding & Anti-Hallucination](#10-graph-engineering-grounding--anti-hallucination)
11. [Graph Versioning (Time Travel)](#11-graph-versioning-time-travel)
12. [Conversational Memory](#12-conversational-memory)
13. [Post-Indexing Automation](#13-post-indexing-automation)
14. [Performance Optimization](#14-performance-optimization)
15. [Security Analysis Deep Dive](#15-security-analysis-deep-dive)
16. [Enterprise Resilience & Production](#16-enterprise-resilience--production)
17. [Command Reference](#17-command-reference)
18. [Troubleshooting & FAQ](#18-troubleshooting--faq)

---

## 1. Introduction

### What is KnowGraph?

KnowGraph is a **Graph RAG (Retrieval-Augmented Generation)** system that transforms your codebase and documentation into an intelligent knowledge graph. Unlike traditional vector-based RAG systems, KnowGraph uses **Graph Theory**, **Network Science**, and **Joern Code Property Graph** analysis to provide:

- **Topological Context**: Follows real code relationships (imports, calls, inheritance)
- **Centrality Analysis**: Identifies architecturally critical components
- **Deterministic Provenance**: Provides verifiable reasoning paths
- **Hierarchical Understanding**: Interprets code within project context
- **Deep Code Analysis**: Joern-powered security and data flow analysis
- **Answer Grounding**: Verifies generated answers against graph evidence (anti-hallucination)
- **Temporal Filtering**: Drops superseded-conversation edges before traversal
- **SC-Quoted Extraction**: Self-contained, P3-verified relation extraction with zero fabricated edges

### Key Benefits

- 🎯 **Precise Answers**: Graph-based retrieval reduces hallucinations
- 🔍 **Deep Understanding**: Follows dependency chains and architectural patterns
- 🔬 **Code Analysis**: Automatic vulnerability detection and data flow tracking
- 📊 **Impact Analysis**: Predict ripple effects of code changes
- ⚓ **Answer Grounding**: Evidence-backed answers with entity-level verification
- 🚀 **High Performance**: Smart caching and hybrid intelligence (CPG caching, incremental updates)
- 🔌 **MCP Compatible**: Works with Claude Desktop, Cursor, and other AI editors
- 🛡️ **Production Ready**: Enterprise resilience patterns + full test coverage
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
        "KNOWGRAPH_LLM_MODEL": "x-ai/grok-4.1-fast",
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
# Output: KnowGraph 1.0.1
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

**Test the CLI:**
```bash
knowgraph --version
# Output: KnowGraph 1.0.1

# Index a small folder and run a query
knowgraph index ./tests/fixtures
knowgraph query "how does authentication work?"
```

**Test the MCP server (health check):**
The `knowgraph_diagnostic` tool checks Graph Store health, LLM provider
connectivity, and configuration validity. In your AI editor, ask:

```
"Run the knowgraph diagnostic"
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
| `KNOWGRAPH_WORKERS` | No | Concurrent API requests / indexing workers | Auto-detect (Max 5) |
| `KNOWGRAPH_BATCH_SIZE` | No | LLM batch size for entity extraction (auto-tuned to RAM) | Auto-detect |
| `KNOWGRAPH_LLM_RETRY_COUNT` | No | Max LLM retries | `5` |
| `KNOWGRAPH_LLM_RETRY_DELAY` | No | Base delay for backoff (sec) | `1.0` |
| `KNOWGRAPH_LLM_MAX_TOKENS` | No | Max tokens the LLM may GENERATE per completion (output cap) | `4096` |
| `KNOWGRAPH_LLM_MAX_INPUT_TOKENS` | No | Approx. max INPUT tokens per completion (model context guard) | `32000` |
| `KNOWGRAPH_JOERN_ENABLED` | No | Enable/disable Joern analysis | `true` |
| `KNOWGRAPH_JOERN_PATH` | No | Explicit Joern installation path (auto-detected if unset) | Auto-detect |
| `KNOWGRAPH_JOERN_TIMEOUT` | No | Joern query/analysis timeout (sec) | `120` |
| `KNOWGRAPH_JOERN_DAEMON` | No | Run a persistent single-JVM Joern daemon (vs. per-query JVM) | `true` |
| `KNOWGRAPH_JOERN_DAEMON_BOOT_TIMEOUT` | No | Initial daemon boot timeout (sec) | `120` |
| `KNOWGRAPH_JOERN_EXPORT_TIMEOUT` | No | CPG export timeout (sec) | `300` |
| `KNOWGRAPH_CPG_NODES_ENABLED` | No | Fold Joern CPG nodes into the graph | `true` |
| `KNOWGRAPH_CPG_NODE_TYPES` | No | CPG node types to create graph nodes for | `METHOD,CALL,TYPE_DECL,IDENTIFIER,LOCAL` |
| `KNOWGRAPH_LOG_LEVEL` | No | Logging level (DEBUG/INFO/WARNING/ERROR) | `INFO` |
| `KNOWGRAPH_MCP_TRANSPORT` | No | MCP transport: `stdio`, `http`, or `sse` | `stdio` |
| `KNOWGRAPH_MCP_HOST` | No | MCP HTTP/SSE bind host | `127.0.0.1` |
| `KNOWGRAPH_MCP_PORT` | No | MCP HTTP/SSE bind port | `8000` |
| `KNOWGRAPH_PERF_*` | No | Pydantic perf settings (`max_workers`, `cache_size`, `batch_size`) | See config |
| `KNOWGRAPH_MEMORY_*` | No | Pydantic memory settings (`warning_threshold_mb`, `critical_threshold_mb`, `auto_gc`) | 500/1000/true |
| `KNOWGRAPH_QUERY_*` | No | Pydantic query settings (`top_k`, `max_hops`, `enable_query_expansion`, `timeout_seconds`) | See config |
| `GITHUB_TOKEN` | No | GitHub PAT for private repos | - |

**OpenRouter Example:**
```bash
export KNOWGRAPH_API_BASE_URL="https://openrouter.ai/api/v1"
export KNOWGRAPH_LLM_MODEL="x-ai/grok-4.1-fast"
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

### Index Options (CLI)
```bash
# Incremental indexing — only process new/modified files (faster re-index)
knowgraph index /path/to/project --incremental

# Auto-discover and link AI editor conversations after indexing
knowgraph index /path/to/project --link-conversations

# Run the SC-quote + P3 anti-hallucination chain on non-code chunks.
# Publishes verified relations as `grounded` graph edges (Graph Engineering).
knowgraph index /path/to/project --enable-short-unit

# Verbose output for indexing diagnostics
knowgraph index /path/to/project --verbose

# Custom output location
knowgraph index /path/to/project --output ./my_graphstore
```

### Index Options (MCP tool `knowgraph_index`)
In addition to the above, the MCP tool exposes file filters and GC:
```json
{
  "tool": "knowgraph_index",
  "arguments": {
    "input_path": "https://github.com/user/repo",
    "include_patterns": ["*.py"],
    "exclude_patterns": ["node_modules/*", "*.lock"],
    "gc": true
  }
}
```
`gc` is also available on the `knowgraph update` CLI. GC is only meaningful for
local sources (repository/conversation sources skip it automatically).

> **GC note**: Garbage collection for repository and conversation sources is
> automatically disabled — those are indexed through ephemeral temp dirs, and
> GC against them would wrongly wipe the graph.

For detailed conversation indexing, see [Section 12](#12-conversational-memory).

---

## 6. Joern Code Analysis

KnowGraph includes **fully integrated Joern code analysis** for deep code understanding.

### 6.1 Automatic Code Detection

**Zero configuration required!** KnowGraph automatically detects and analyzes code in 14+ languages during indexing:

```bash
# Index any code directory - automatic code analysis
knowgraph index ./my-project

# Supports: Python, JavaScript/TypeScript, Java, C/C++, Go, C#,
# Scala, PHP, Ruby, Kotlin, Swift, Rust, and more
```

### 6.2 What Gets Analyzed

During indexing, Joern extracts code entities and folds them into the graph:
- ✅ **Methods, classes, identifiers, locals** (`KNOWGRAPH_CPG_NODE_TYPES`) become
  graph **nodes**, linked to their source chunk via `hierarchy` edges (when
  `KNOWGRAPH_CPG_NODES_ENABLED=true`, the default).
- ✅ **Entity metadata** (`entities`) drives `semantic` and `reference` edges.

Code relationships are extracted by the **code analysis pipeline**
(`CodeIndexIntegration`):
- ✅ **Call edges** (`call`): function call relationships between code nodes.
- ✅ **Data-flow edges** (`data_flow`): tainted data flows (source → sink).

> **Note**: the CLI `knowgraph index` path builds the graph via
> `SmartGraphBuilder` (entity nodes + `hierarchy` edges only). The full
> call/data-flow edge extraction runs through the **MCP `knowgraph_index`**
> tool's code-analysis stage on local directories. In both cases the stored CPG
> is available for query-time native Joern queries
> (`knowgraph_analyze_call_graph`, `knowgraph_joern_query`, taint analysis).

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

For more query examples, see the [Example Usage Guide](USAGE_GUIDE.md).

---

## 7. Querying the Knowledge Graph

### 7.1 Basic Query
```python
from knowgraph.application.querying.query_engine import QueryEngine
engine = QueryEngine("./graphstore")
result = engine.query("How does auth work?")
print(result.answer)
```

### 7.2 Data-Flow Query

The engine's async `query_dataflow` finds taint paths from a source to a sink:

```python
result = await engine.query_dataflow(
    source_pattern="user input from HTTP request",
    sink_pattern="SQL query execution",
    max_path_length=10,
    edge_types=["data_flow"],   # default: data_flow
)
print(result.to_mermaid())
```

This traverses `data_flow` edges. Those edges are produced by the
code-analysis indexing stage (see [§6.2](#62-what-gets-analyzed)); if your
graph was indexed via the CLI path (which builds `SmartGraphBuilder` only),
there may be no `data_flow` edges to trace.

### 7.3 Advanced Parameters

Fine-tune your query logic with the query parameters:

```json
{
  "query": "Find inheritance structure of BaseClass",
  "top_k": 20,
  "max_hops": 4,
  "max_tokens": 4096,
  "expand_query": false,
  "enable_hierarchical_lifting": true,
  "lift_levels": 2,
  "enable_grounding": false
}
```

- **`enable_hierarchical_lifting` / `lift_levels`**: include parent-directory context (READMEs, package docs) for nodes deep in a directory tree.
- **`enable_grounding`**: prefer graph-evidence-backed nodes and annotate unbacked answer entities (see [§10](#10-graph-engineering-grounding--anti-hallucination)).
- **`expand_query`**: AI synonym/term expansion.
- `max_tokens` is the LLM **output** cap (`LLM_MAX_TOKENS`, default 4096).

> There is no `edge_type_weights` / `prioritize_reference_edges` parameter in
> the query engine or MCP tools — see [§9.2](#92-edge-types-in-the-graph).

---

## 8. MCP Server Integration

KnowGraph exposes a comprehensive suite of tools to your AI assistant. Here is the **complete list** of available tools:

| Tool Name | Description |
|-----------|-------------|
| `knowgraph_query` | Semantic search with hierarchical lifting, optional grounding & API version negotiation. |
| `knowgraph_batch_query` | Execute multiple queries for efficient context gathering (supports `enable_grounding` / `enable_temporal_filter`). |
| `knowgraph_index` | Trigger indexing of local or remote codebases. |
| `knowgraph_analyze_impact` | Predict effects of code changes (Semantic or Path mode). |
| `knowgraph_validate` | Check health and consistency of the graph. |
| `knowgraph_get_stats` | Retrieve node/edge counts and density metrics. |
| `knowgraph_discover_conversations` | Auto-index chats from Antigravity, Cursor, GitHub Copilot. |
| `knowgraph_analyze_conversations` | Analyze topics and trends in indexed chats. |
| `knowgraph_tag_snippet` | Bookmark important AI responses as reusable snippets. |
| `knowgraph_search_bookmarks` | Semantic search within your tagged snippets. |
| `knowgraph_list_versions` | Show complete version history. |
| `knowgraph_version_info` | Get detailed metadata for a specific version ID. |
| `knowgraph_diff_versions` | Compare nodes/edges between two commits. |
| `knowgraph_rollback` | Revert graph state to a previous snapshot. |
| `knowgraph_diagnostic` | Run system health checks (Graph Store, LLM, Config). |
| `knowgraph_joern_query` | Execute native Joern DSL queries, or a **predefined template** via `query_name`. |
| `knowgraph_security_scan` | Scan for vulnerabilities using Joern policies (or flow-based taint analysis via `scan_type`). |
| `knowgraph_find_dead_code` | Detect unreachable methods using dominance analysis. |
| `knowgraph_analyze_call_graph` | Analyze call paths and recursion. |
| `knowgraph_export_cpg` | Export CPG to JSON/DOT/Neo4j/SARIF. |
| `knowgraph_generate_cpg` | Manually trigger CPG generation for a path. |

> The server also exposes **graph resources** under `knowgraph://graph/…`
> (`/manifest`, `/nodes`, `/stats`) and reusable **prompt templates**
> (`graph_summary`, `security_scan`, `impact_analysis`).

#### Key `knowgraph_query` parameters (v1.0.1)

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enable_grounding` | bool | `false` | Prefer graph-evidence-backed nodes in context; demote graph-isolated content. Implies temporal filtering. |
| `api_version` | string | current | Requested API version to negotiate against the server registry (e.g. `"1.0.1"`). |
| `min_api_version` | string | - | Minimum acceptable API version. Rejected if `api_version` is below this. |
| `expand_query` | bool | `false` | Uses AI to expand the query with synonyms and technical terms. |

#### `knowgraph_security_scan` — flow-based taint analysis

Instead of the policy scan (6 policy rules, see [§15](#15-security-analysis-deep-dive)),
pass `scan_type` to run Joern taint-analysis for a specific vulnerability type —
`all`, `sql_injection`, `xss`, `command_injection`, `path_traversal`, `xxe`,
`ssrf` (the `xss`/`xxe`/`ssrf` types come from the `vulnerability_patterns`
taint register, not the policy engine):

#### `knowgraph_joern_query` — named templates

Besides raw DSL, `knowgraph_joern_query` accepts a `query_name` that resolves to
a predefined template. The exact template name and the vulnerability aliases
`sql_injection`, `buffer_overflow`, `command_injection`, `dangerous_functions`
are valid. Parameters: `cpg_path` (required), `query` **or** `query_name`,
`timeout` (default 60s).

#### Other tool parameters worth knowing

- `knowgraph_tag_snippet` also accepts `conversation_id` (optional, contextualizes
  the snippet) alongside `tag`, `snippet`, `user_question`, `graph_path`.
- `knowgraph_index` accepts `access_token` (GitHub PAT) for private repositories,
  and also exposes `include_patterns`, `exclude_patterns`, `resume`, `gc`.

#### Graph resources

The MCP server exposes resources under `knowgraph://…`:
`knowgraph://default/manifest` (default graph), `knowgraph://graph/{graph_path}/manifest`,
`/nodes`, and `/stats` — plus reusable prompt templates (`graph_summary`,
`security_scan`, `impact_analysis`).

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
        "KNOWGRAPH_LLM_MODEL": "x-ai/grok-4.1-fast",
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
from knowgraph.application.querying.query_engine import QueryEngine

engine = QueryEngine("./graphstore")
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

### 9.2 Edge Types in the Graph

KnowGraph stores edges of the following types (`knowgraph/shared/types.py`):

| Edge type | Meaning |
|-----------|---------|
| `semantic` | Shared-entity overlap between chunks (AI entity extraction, Jaccard > 0.2) |
| `reference` | Definition/reference symbol edges (`relation: "dependency"`) |
| `hierarchy` | CPG entity node → its source chunk (`child_of_chunk`) |
| `call` | Function call edges (produced by the code-analysis stage, MCP index on local dirs) |
| `data_flow` | Tainted data-flow edges, source → sink (same code-analysis stage) |
| `conversation_references_code` | Auto-linked conversation → code node edges |
| `supersedes` / `contradicts` | Temporal claim edges built by the post-index hook |
| `grounded` | SC-quote + P3 verified relations (`--enable-short-unit`) |
| `control_flow`, `ast` | Declared in the literal; not emitted during indexing (available via native Joern queries) |

**Node types** (`knowgraph/shared/types.py`): `code`, `text`, `config`,
`documentation`, `conversation`, `tagged_snippet`, `readme`, `entity_node`.

> **Note**: there is currently **no `edge_type_weights` / `prioritize_reference_edges`
> parameter** in the query engine or MCP tools. Traversal follows
> `reference`/`call`/`data_flow`/`hierarchy`/`control_flow` edges as directed
> adjacency, and other types as undirected.

### 9.3 Batch Queries

Execute multiple queries efficiently with shared context loading.

**Performance Comparison:**
- **Sequential**: 5 queries × 2s = 10s
- **Batch**: 5 queries = 2.5s (4x faster)

**Example:**
```python
from knowgraph.application.querying.query_engine import QueryEngine

engine = QueryEngine("./graphstore")
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

### 9.4 Hierarchical Context Lifting

Automatically includes context from parent directories (README files, package docs).
Applies to the sync CLI path (`knowgraph query`) **and** async/MCP queries
(`lift_hierarchical_context` is called in both `query()` and `query_async()`).

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

### 9.5 Advanced Query Parameters Reference

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | **required** | Natural language query |
| `top_k` | int | 20 | Number of results to return |
| `max_hops` | int | 4 | Graph traversal depth |
| `max_tokens` | int | `LLM_MAX_TOKENS` (4096) | LLM output token cap |
| `expand_query` | bool | false | Enable AI query expansion |
| `enable_hierarchical_lifting` | bool | true | Include parent context |
| `lift_levels` | int | 2 | Parent directory levels |
| `with_explanation` | bool | false | Include reasoning path |
| `enable_grounding` | bool | false | Prefer graph-evidence-backed nodes (see [§10](#10-graph-engineering-grounding--anti-hallucination)) |
| `enable_temporal_filter` | bool | false | Drop superseded-conversation edges before traversal. **Note**: exposed on the Python API and `knowgraph_batch_query`, but **not** on the `knowgraph_query` MCP tool (opening `enable_grounding` there still implies temporal filtering). |

---

## 10. Graph Engineering: Grounding & Anti-Hallucination

KnowGraph v1.0.1 ships a **Graph Engineering verification layer** that anchors
generated answers to the graph's actual evidence. This is an opt-in set of
features that run with **zero extra LLM calls** — they reuse graph facts
already retrieved during query execution.

### 10.1 Answer Grounding (`enable_grounding`)

When enabled on a query, two things happen:

1. **Evidence-backed ranking**: nodes that appear in at least one edge of the
   active subgraph (i.e. are *grounded*) are preferred in the assembled context;
   isolated nodes are demoted. This makes the context budget favor content that
   is actually connected to the rest of the graph.
2. **Answer-level annotation**: after the LLM generates an answer, every
   entity surface form in the answer is classified against the retrieved
   subgraph:
   - **grounded** — appears in the answer *and* is an endpoint of a grounded edge
   - **isolated** — appears in the answer, known to the graph, but has no edge
     in the active subgraph
   - **absent** — appears in the answer but is not in the graph's entity set

   Any *isolated* or *absent* entity is surfaced as a trailing note on the
   answer (e.g. `[grounding] these entities in the answer were not found in the
   retrieved graph; verify: …`). **Nothing is ever stripped** — grounding is an
   annotation, not a filter, and grounding is not truth (a grounded entity can
   still be the subject of a fabricated claim).

```bash
# CLI
knowgraph query "How does authentication work?" --enable-grounding

# MCP
{
  "tool": "knowgraph_query",
  "arguments": {
    "query": "How does authentication work?",
    "enable_grounding": true
  }
}
```

> **Note**: enabling grounding implies temporal filtering (see below), so
> superseded-conversation edges are dropped from the traversal too.

### 10.2 Temporal Filtering (`enable_temporal_filter`)

Conversation indexing can create duplicate/conflicting facts over time. When
enabled, the retriever runs `filter_edges_by_temporal` before graph traversal,
which drops edges that originate from a *superseded* node: it collects the
**targets** of `SUPERSEDES` edges as stale, then removes **any** edge whose
source is one of those stale nodes. This supports "stale fact never current" —
the latest claim wins. (`SUPERSEDES`/`CONTRADICTS` edges themselves are already
excluded from traversal independently, via the traversal engine.)

```python
result = await engine.query_async(
    "Who was the CEO of Nova Dynamics?",
    enable_temporal_filter=True,
)
```

*Note:* grounding implies temporal filtering (`enable_grounding=True` turns on
temporal filtering too).

### 10.3 SC-Quoted Extraction (`--enable-short-unit`)

During indexing, `--enable-short-unit` runs the **R-008 SC-quote + P3 entailment
chain** on non-code chunks (docs, READMEs, prose) that passed LLM entity
extraction:

1. **Unitizer (D-1)**: deterministic, LLM-free sentence decomposition into
   self-contained, subject-anchored propositions.
2. **SC-quote extraction (D-2)**: forces the LLM to attach a **verbatim,
   both-entity quote** from the source unit to every extracted relation.
   Relations without a valid quote are omitted entirely (anti-fabrication).
3. **P3 entailment verification (D-3)**: a verifier decides whether the quote
   actually entails the claimed (subject, predicate, object) before the edge is
   published.
4. **Grounded edges**: each published relation becomes a `grounded` edge in the
   graph (resolved against the producing node and best-matching *other* node).
   A relation whose object only exists within the subject's own document is not
   turned into an edge (a within-document relation is not a cross-document edge).

```bash
knowgraph index ./my-project --enable-short-unit
```

Verified relations are stored on node `metadata["relations"]` and become
queryable `grounded` edges with `score=0.9` and `source="sc_p3"`.

### 10.4 Version Negotiation

MCP clients can request a specific API version and a minimum acceptable
version. The server negotiates against its version registry and rejects
unsupported versions up front:

```json
{
  "tool": "knowgraph_query",
  "arguments": {
    "query": "…",
    "api_version": "1.0.1",
    "min_api_version": "1.0.0"
  }
}
```

---

## 11. Graph Versioning (Time Travel)

KnowGraph introduces a Git-like version control system for your knowledge graph. Every indexing operation creates a snapshot.

### 11.1 Concepts
- **Manifest**: A JSON file tracking the state of the graph.
- **Snapshot**: A point-in-time record of all nodes and edges.
- **Checkpoint**: Created automatically after `knowgraph index`.

### 11.2 Listing Versions
See the history of your knowledge base:

```bash
$ knowgraph version versions --limit 50 --verbose
# Output format (per version):
#   v1.0.1      2026-08-22T…         Nodes: 1,234  Edges: 4,567  Files: 120
#   v1.0.0      2026-08-20T…
```

Flags: `--limit N` (default 50), `--verbose` (shows added/modified/deleted
change counts and metadata), `--graph-store <path>`.

### 11.3 Diffing Versions
See what changed between two points in time:

```bash
knowgraph version diff v1.0.0 v1.0.1
```

**Output Explanation:**
- `[+]` Added Nodes: New files or concepts found.
- `[-]` Deleted Nodes: Files removed from the codebase.
- `[~]` Modified Nodes: Content changes (hash mismatch).

### 11.4 Rollback (Safety)
If an indexing operation corrupts your graph or adds unwanted data, you can roll back instantly. Rollback is **metadata-only** (manifest) — you re-index to restore files.

```bash
# Execute rollback (requires a confirmation prompt when stdin is a TTY)
knowgraph version rollback v1.0.0

# Non-interactive / CI: must pass --force (skips the prompt and validation)
knowgraph version rollback v1.0.0 --force

# Skip creating a backup before rollback
knowgraph version rollback v1.0.0 --no-backup
```

> **Warning:** Rollback is destructive for the versions *after* the target
> version — they are removed from history. A backup is created by default
> (`--no-backup` to skip). `--force` is required in non-interactive shells
> where no TTY is attached.

---

## 12. Conversational Memory

KnowGraph can now "read" your conversations with AI assistants and link them to your code.

### 12.1 Supported Formats
- **Antigravity**: Task and Walkthrough artifacts.
- **Cursor**: `.aichat` files in your project.
- **VS Code**: GitHub Copilot chat exports.
- **Claude**: JSON export files.

### 12.2 Auto-Discovery
Scan your project for conversation files and index them:

```bash
knowgraph discover-conversations
  --editor all          # or 'antigravity', 'cursor', 'github_copilot'
  --output ./graphstore # optional output location
  --dry-run             # preview what would be indexed without writing
  --verbose
```

### 12.3 Semantic Tagging
You can manually tag important AI responses using the MCP tool `knowgraph_tag_snippet`.

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

## 13. Post-Indexing Automation

KnowGraph runs a series of "Hooks" after every successful indexing job.

### 13.1 How Hooks Work
After an indexing job, a set of post-index hooks is invoked synchronously from
`index_helpers.run_post_index_hooks` (not via an event bus — there is no
`INDEXING_COMPLETE` event). They live in
`knowgraph.application.indexing.post_index_hooks`. Which hooks run depends on
the index flags, not a generic "after every job" rule.

### 13.2 Available Hooks

1.  **Auto conversation linking** (`auto_link_conversations`):
    *   Scans indexed conversations (triggered by `--link-conversations` or the MCP index tool).
    *   Finds file references (e.g., `src/auth.py`).
    *   Creates semantic edges between the *Conversation Node* and the *Code Node*.
    *   *Benefit*: When you query `auth.py`, you also get the discussions regarding `auth.py`.

2.  **Temporal edge building** (`build_temporal_edges`):
    *   Builds `SUPERSEDES` / `CONTRADICTS` edges across conversation claims.
    *   *Benefit*: powers `enable_temporal_filter` so stale facts never appear current.

3.  **Bookmark auto-tagging** (`auto_tag_bookmarks`):
    *   Analyzes the content of newly indexed snippets.
    *   Assigns tags (e.g., `security`, `database`, `api`, `frontend`) based on keywords and embeddings.
    *   *Benefit*: enables filtered queries like "Show me all security-related nodes".

4.  **Stats collection** (`collect_index_stats`):
    *   Calculates graph statistics (node/edge counts, density) for the manifest.

### 13.3 When Each Hook Runs

| Hook | Runs when |
|------|-----------|
| `auto_link_conversations` | `--link-conversations` flag, **or** the source type is `conversation` |
| `build_temporal_edges` | **every** index job (best-effort) |
| `auto_tag_bookmarks` | only when `--verbose` is set (not the MCP index path) |
| `collect_index_stats` | only when `--verbose` is set (not the MCP index path) |

---

## 14. Performance Optimization

KnowGraph is designed for high performance, but you can tune it further based on your workload.

### 14.1 Caching System

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

### 14.2 Worker Tuning

Control parallelism for indexing and querying.

**Environment Variable:**
```bash
# Auto-detect (default, capped at 5 to avoid LLM rate limits)
export KNOWGRAPH_WORKERS=auto

# Manual override
export KNOWGRAPH_WORKERS=10

# Single-threaded (debugging)
export KNOWGRAPH_WORKERS=1
```

**Recommendations:**
- **Small projects (<100 files):** 5 workers
- **Medium projects (100-1000 files):** 5-10 workers
- **Large projects (>1000 files):** 10-20 workers (mind LLM rate limits)
- **Low memory systems:** 1-5 workers max

> The auto-detected value is capped at **5** (`get_optimal_workers()` →
> `recommend_workers(max_workers=5)`) specifically to avoid hitting LLM rate
> limits. Set `KNOWGRAPH_WORKERS` explicitly to override.

**Performance Impact** (illustrative, small project):
```
Workers | Indexing Time | Memory Usage
--------|---------------|-------------
1       | ~120s         | ~500MB
5       | ~35s          | ~1.5GB
10      | ~25s          | ~2GB
```

### 14.3 Memory Management

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
- Enable `enable_grounding` to favor evidence-backed nodes, or split the project into smaller graphs

### 14.4 Async Best Practices

KnowGraph is 100% async for non-blocking I/O.

**Batch Queries (Recommended):**
```python
import asyncio
from knowgraph.application.querying.query_engine import QueryEngine

async def main():
    engine = QueryEngine("./graphstore")
    
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

### 14.5 LLM Rate Limiting

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

### 14.6 Incremental Updates

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

### 14.7 Performance Monitoring

Track system performance with built-in metrics.

**Query Performance:**
```python
from knowgraph.application.querying.query_engine import QueryEngine

engine = QueryEngine("./graphstore")
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

### 14.8 Optimization Checklist

✅ **Enable caching** (default: enabled)  
✅ **Use batch queries** for multiple questions  
✅ **Tune worker count** based on system resources  
✅ **Reduce `max_hops`** for very large graphs  
✅ **Use incremental updates** for frequent re-indexing  
✅ **Monitor memory usage** with `top` or `htop`  
✅ **Clear old caches** periodically  

---

## 15. Security Analysis Deep Dive

KnowGraph's Joern integration provides industrial-grade security analysis capabilities.

### 15.1 Predefined Security Policies

KnowGraph ships a set of CWE-mapped security policies in `PolicyEngine`
(`knowgraph/application/security/policy_engine.py`). `policy_names` is matched
**loosely** — e.g. `sql_injection`, `nosql`, or `SQLInjection` all find
`NoSQLInjection`; a friendly lowercase form works.

| Canonical Policy | Friendly names | CWE | Severity | Description |
|------------------|---------------|-----|----------|-------------|
| `NoSQLInjection` | `sql_injection`, `sqli` | CWE-89 | CRITICAL | Unsanitized SQL queries (parameterized/raw calls reachable from input) |
| `NoCommandInjection` | `command_injection` | CWE-78 | CRITICAL | OS command injection risks |
| `NoBufferOverflow` | `buffer_overflow` | CWE-120 | CRITICAL | Unsafe buffer copy operations |
| `NoHardcodedSecrets` | `hardcoded_credentials`, `hardcoded_secrets` | CWE-798 | HIGH | Embedded passwords / API keys / tokens |
| `NoWeakCrypto` | `insecure_random`, `weak_crypto` | CWE-327 | HIGH | Weak cryptographic algorithms (MD5/SHA1/DES/RC4) |
| `NoPathTraversal` | `path_traversal` | CWE-22 | HIGH | Directory traversal attacks |

> **On xss/xxe/ssrf**: these are **not** in the `PolicyEngine` set, and there is
> no `xss`/`use_after_free`/`null_pointer`/`unvalidated_redirect` *template* in
> `joern_query_templates.py` either. To scan for cross-site scripting, XXE, or
> SSRF, use `scan_type` (`xss`, `xxe`, `ssrf`) — those run taint analysis from
> the `vulnerability_patterns` register. To extend the policy engine, pass a
> custom `Policy` via `PolicyEngine(custom_policies=[...])`.

### 15.2 Running Security Scans

> Security scanning (and all Joern tools) runs through MCP tools
> (`knowgraph_security_scan`) — there is no standalone `security-scan` CLI
> subcommand. The CPG is auto-detected from `graph_path` or supplied via
> `cpg_path`.

**Full Scan (All Policies):**
```json
{
  "tool": "knowgraph_security_scan",
  "arguments": {
    "graph_path": "./graphstore"
  }
}
```

**Filtered Scan:**
```json
{
  "tool": "knowgraph_security_scan",
  "arguments": {
    "policy_names": ["sql_injection", "command_injection"],
    "severity_filter": "HIGH"
  }
}
```

**Flow-based taint analysis** (`scan_type`) — instead of the policy scan, run
Joern taint-analysis for a specific vulnerability class:
```json
{
  "tool": "knowgraph_security_scan",
  "arguments": {
    "scan_type": "sql_injection",
    "graph_path": "./graphstore"
  }
}
```

### 15.3 Export Formats

CPG export runs through the `knowgraph_export_cpg` MCP tool.

**SARIF (for GitHub Security tab):**
```json
{
  "tool": "knowgraph_export_cpg",
  "arguments": {
    "cpg_path": "./project.bin",
    "output_path": "./report.sarif",
    "format": "sarif"
  }
}
```

**Other Formats:** `json`, `dot`, `neo4j`, `graphml`

### 15.4 Dead Code Detection

```json
{
  "tool": "knowgraph_find_dead_code",
  "arguments": {"include_internal": false}
}
```

### 15.5 Call Graph Analysis

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

## 16. Enterprise Resilience & Production

KnowGraph is built to survive in production environments.

### 16.1 Circuit Breaker Status
If an external dependency (like OpenAI API) fails repeatedly, KnowGraph opens the circuit to prevent cascading failures.
- **Signs**: You see `CircuitBreakerOpenException`.
- **Action**: Check your API status. The system will auto-retry after a timeout.

### 16.2 Monitoring Metrics

KnowGraph records Prometheus-compatible metrics (namespace prefix `knowgraph`)
into the default `prometheus_client` registry. **KnowGraph does not serve an
HTTP `/metrics` endpoint** itself — scrape it by wiring your own
`prometheus_client` handler (e.g. `start_http_server`) or read the registry.

| Metric | Type |
|--------|------|
| `knowgraph_requests_total` | Counter |
| `knowgraph_request_duration_seconds` | Histogram |
| `knowgraph_queries_total` | Counter |
| `knowgraph_query_duration_seconds` | Histogram |
| `knowgraph_query_results` | Summary |
| `knowgraph_cache_hits_total` | Counter |
| `knowgraph_cache_misses_total` | Counter |
| `knowgraph_cache_size` | Gauge |
| `knowgraph_nodes_total` | Gauge |
| `knowgraph_edges_total` | Gauge |
| `knowgraph_graph_operations_total` | Counter |
| `knowgraph_errors_total` | Counter |
| `knowgraph_indexed_documents_total` | Counter |
| `knowgraph_indexing_duration_seconds` | Histogram |

### 16.3 System Health (Diagnostics)
Run a comprehensive health check of the KnowGraph system with the
`knowgraph_diagnostic` MCP tool. It reports five sections:

1. **📦 Graph Store** — total nodes, tagged-snippet count, node-type distribution.
2. **🤖 LLM Provider** — presence of `OPENAI_API_KEY` / `ANTHROPIC_API_KEY`.
3. **🛠️ MCP Tools** — the tool surface available to clients.
4. **💻 System** — project root, Python version, virtual environment.
5. **💡 Recommendations** — actionable suggestions based on the above.

```bash
# Run via MCP (in your AI editor, ask: "run the knowgraph diagnostic")
knowgraph_diagnostic()
```

---

## 17. Command Reference

### Core Commands
- `knowgraph index <path>`: Build the graph. Flags: `--incremental`, `--link-conversations`, `--enable-short-unit`, `--verbose`, `-o/--output`. (File filters `include_patterns`/`exclude_patterns` and `gc` are MCP-tool options.)
- `knowgraph query "question"`: Ask a question. Flags: `--enable-grounding`, `--expand-query`, `--explain`, `--top-k`, `--max-hops`, `--max-tokens`, `-g/--graph-store`, `-v/--verbose`, `--mode query|impact`.
- `knowgraph update <path>`: Incrementally update an existing graph. Flags: `--gc`, `-g/--graph-store`, `-v/--verbose`.
- `knowgraph serve`: Start MCP server (transport: `KNOWGRAPH_MCP_TRANSPORT`).

### Versioning Commands
- `knowgraph version versions [--limit N] [--verbose]`: Show history.
- `knowgraph version show <id>`: Show details.
- `knowgraph version diff <id1> <id2>`: Compare.
- `knowgraph version rollback <id> [--force] [--no-backup]`: Revert (metadata-only).

### Conversation Commands
- `knowgraph discover-conversations`: Find and index chats (`--editor all|cursor|antigravity|github_copilot`, `--dry-run`, `--verbose`).
- `knowgraph list-conversations`: List indexed conversations.
- Tag snippets via the MCP tool `knowgraph_tag_snippet` (no `tag` CLI subcommand).

---

## 18. Troubleshooting & FAQ

### 18.1 Installation & Setup Issues

| Issue | Solution |
|-------|----------|
| **Joern Installation Failed** | Run `knowgraph-setup-joern` manually. Ensure JDK 11+ is installed (`java -version`). |
| **Permission Denied (Joern binaries)** | Run `chmod +x ~/.knowgraph/joern/joern-cli/bin/*` |
| **Module Not Found** | Ensure you're using the correct Python environment. Run `pip install -e .` in dev mode. |
| **API Key Not Found** | Set `export KNOWGRAPH_API_KEY="sk-..."` or add to `.env` file. |

### 18.2 Indexing Issues

| Issue | Solution |
|-------|----------|
| **CPG Generation Timeout** | Increase timeout: `KNOWGRAPH_JOERN_TIMEOUT=1200 knowgraph index ./project` |
| **Out of Memory (Indexing)** | Reduce workers: `KNOWGRAPH_WORKERS=5 knowgraph index ./project` |
| **Files Not Detected** | Use the MCP tool `knowgraph_index` with `include_patterns: ["*.py", "*.js"]`. |
| **Incremental Update Not Working** | Clear cache: `rm -rf ~/.knowgraph/cpg_cache/` and re-index. |
| **Git Repository Clone Failed** | Check network connection. For private repos, set `GITHUB_TOKEN`. |

### 18.3 Query Issues

| Issue | Solution |
|-------|----------|
| **No Results Found** | Try `expand_query=True` or increase `max_hops` (default: 4 → 6). |
| **Query Too Slow (>10s)** | Reduce `max_hops` (4 → 2) or `top_k` (20 → 10). Enable caching. |
| **High Memory Usage** | Use `query_async()` for batch queries. Reduce graph size or split into sub-projects. |
| **Incorrect Results** | Check if graph is up-to-date. Re-index with `knowgraph index ./project`. |

### 18.4 Joern & CPG Issues

| Issue | Solution |
|-------|----------|
| **CPG Not Generated** | Check if language is supported (14+ languages). Verify file extensions. |
| **Joern Daemon Not Starting** | Kill existing process: `pkill -f joern` and restart. |
| **CPG Corrupted** | Delete and regenerate: `rm ~/.knowgraph/cpg_cache/*.bin && knowgraph index ./project` |
| **Language Not Detected** | Use the MCP tool `knowgraph_generate_cpg` with `source_path` and `language="python"`. |

### 18.5 Versioning Issues

| Issue | Solution |
|-------|----------|
| **Rollback Failed** | Ensure no other process is writing to the graph. Check file permissions. |
| **Diff is Empty** | Versions might be identical. `knowgraph index` skips unchanged files. |
| **Version Not Found** | Run `knowgraph version versions` to see available versions. |
| **Manifest Corrupted** | Restore from backup: `cp ./graphstore/metadata/manifest.json.backup ./graphstore/metadata/manifest.json` |

### 18.6 Conversation Indexing Issues

| Issue | Solution |
|-------|----------|
| **Conversations Not Found** | Check that `.aichat` files (Cursor) or editor artifacts exist. Run `knowgraph discover-conversations --dry-run` to see what would be indexed. |
| **Antigravity Chats Not Indexed** | Ensure artifacts are in `~/.gemini/antigravity/brain/`. |
| **Cursor Chats Not Indexed** | Check `.cursor/` directory in project root. |

### 18.7 Performance Issues

| Issue | Solution |
|-------|----------|
| **Slow Indexing (>5min)** | Increase workers via `KNOWGRAPH_WORKERS` (e.g. 5–10; auto-detect is capped at 5). |
| **High RAM Usage (>4GB)** | Reduce workers, enable lazy edge loading, or split project into smaller graphs. |
| **Cache Not Working** | Check cache directory exists: `ls ~/.knowgraph/cpg_cache/`. Verify TTL not expired. |
| **LLM Rate Limits** | Increase retry delay: `KNOWGRAPH_LLM_RETRY_DELAY=2.0` |

### 18.8 MCP Integration Issues

| Issue | Solution |
|-------|----------|
| **MCP Server Not Starting** | Check logs: `tail -f ~/.config/claude/mcp.log`. Verify Python path in config. |
| **Tools Not Visible** | Restart AI editor (Claude/Cursor). Check MCP server status. |
| **Project Root Not Detected** | Set manually: `export KNOWGRAPH_PROJECT_ROOT=/path/to/project` |

### 18.9 Security Scan Issues

| Issue | Solution |
|-------|----------|
| **No Vulnerabilities Found** | CPG might not be generated. Run `knowgraph index ./project` first. |
| **False Positives** | Use `severity_filter="HIGH"` to reduce noise. Review policy definitions. |
| **SARIF Export Failed** | Ensure output directory exists. Check file permissions. |

### 18.10 Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Enable debug mode
export KNOWGRAPH_LOG_LEVEL=DEBUG
knowgraph index ./project

# Check logs
tail -f ~/.knowgraph/logs/knowgraph.log
```

### 18.11 Common Error Messages

**Error:** `CircuitBreakerOpenException`  
**Cause:** External API (OpenAI) is failing repeatedly.  
**Solution:** Check API status. Wait for circuit to close (60s timeout).

**Error:** `CPGGenerationError: Language not supported`  
**Cause:** File extension not recognized.  
**Solution:** Check supported languages. Add custom extension mapping.

**Error:** `GraphValidationError: Orphaned nodes detected`  
**Cause:** Graph corruption or incomplete indexing.  
**Solution:** Run the MCP tool `knowgraph_validate`, then re-index with
`knowgraph index ./project`.

**Error:** `MemoryError: Cannot allocate memory`  
**Cause:** Graph too large for available RAM.  
**Solution:** Reduce workers, split project, or upgrade system RAM.

### 18.12 Getting Help

- **GitHub Issues:** [https://github.com/yunusgungor/knowgraph/issues](https://github.com/yunusgungor/knowgraph/issues)
- **Documentation:** [https://github.com/yunusgungor/knowgraph/docs](https://github.com/yunusgungor/knowgraph/docs)
- **Diagnostic Tool:** Use the MCP tool `knowgraph_diagnostic` (or ask your AI editor to "run the knowgraph diagnostic") for a system health check

---

**End of User Guide**

# 🧠 KnowGraph: Graph RAG & MCP Server for Code
[![CI](https://github.com/yunusgungor/knowgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/yunusgungor/knowgraph/actions/workflows/ci.yml)

<div align="center">

**The Cognitive Revolution for Your Codebase (Graph RAG for LLMs)**

> **"Your code is not just text, it's a living graph."**
> Shift from the probabilistic world of vector similarity (Standard RAG) to the deterministic clarity of **Graph Theory** and **NetworkX**.

[![Status](https://img.shields.io/badge/Status-Production%20Ready-success?style=flat-square&logo=github)](https://github.com/yunusgungor/knowgraph)
[![Theory](https://img.shields.io/badge/Theory-Graph_Topology-purple?style=flat-square&logo=wikipedia)](https://en.wikipedia.org/wiki/Network_theory)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green?style=flat-square&logo=server)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[⚡ Quick Start](#-cognitive-upgrade-in-30-seconds-quick-start) • [🔬 The Difference](#-why-knowgraph-the-scientific-edge) • [🧪 The Lab](#-the-lab-cognitive-capability-tests) • [📚 Knowledge Base](#-knowledge-base)

</div>

---

## 🔬 Why KnowGraph? (The Scientific Edge)

Traditional AI assistants view your code as a "bag of similar words" (Vector Space). However, software engineering is **topological**; it relies on logical connections, not just textual proximity.

KnowGraph leverages **Graph Theory** and **Network Science** principles to offer 4 revolutionary capabilities:

| Capability | Traditional RAG | 🧠 KnowGraph |
| :--- | :--- | :--- |
| **1. Topological Context** | Retrieves random files. | Follows real connections (import, call, inherit) via **Graph Traversal (BFS/DFS)**. |
| **2. Centrality Analysis** | Focuses on keyword frequency. | Identifies **architecturally critical** components (Hub Nodes) using `PageRank`. |
| **3. Deterministic Provenance** | High hallucination risk. | Cites the **reasoning path** and source files as irrefutable proof. |
| **4. Cognitive Hierarchy** | Analyzes files in isolation. | Interprets files in **enriched context** using parent `README`s and project purpose. |

---

## 🚀 Performance Engine (v0.6.0)

KnowGraph is built for scale. The **Smart Indexing Engine** processes large repositories efficiently:

*   **⚡ Hybrid Intelligence:** Code files are analyzed using **AST (Abstract Syntax Tree)** via `ASTAnalyzer` for 100x speed and 0-token cost, while text files use Batch LLM processing through `OpenAIProvider` or `MCPSamplingProvider`.
*   **🧠 Persistent Memory:** Built-in SQLite Caching via `CacheManager` (`.knowgraph_cache`) ensures you never re-index unchanged files. Resumes instantly after interruptions.
*   **🛡️ Smart Rate Limiter:** The `RateLimiter` class automatically respects API limits (Free/Pro tiers) by dynamically throttling requests based on headers, preventing 429 errors.
*   **🏎️ Concurrent Batching:** `SmartGraphBuilder` processes 10 chunks per call with 20 parallel workers, maximizing throughput.
*   **📊 Graph Algorithms:** Leverages NetworkX for centrality calculations (Betweenness, Degree, Closeness, Eigenvector) to identify architecturally critical components.

---

## 🎯 Key Features

### 1. 📊 Time-Travel Debugging (Graph Versioning - v0.6.0)

KnowGraph now treats your knowledge graph as a versioned artifact, similar to Git for your code.

*   **Snapshots:** Every `knowgraph index` creates a new, immutable version checkpoint.
*   **Diffing:** See exactly how your knowledge graph evolved. Which nodes were added? Which relationships broke?
*   **Rollback:** Broke something? Instantly revert to a previous healthy state with `knowgraph version rollback`.

```bash
# Compare current graph with the previous version
knowgraph version diff HEAD HEAD~1

# Rollback to a safe state
knowgraph version rollback v0.5.9-stable
```

### 2. 🔗 Conversational Intelligence (v0.6.0)

Your code doesn't live in a vacuum. It lives in the conversations you have with your AI assistant. KnowGraph now indexes **Code + Conversations** together.

*   **Multi-Editor Support:** Supports Antigravity (Gemini), Cursor (`.aichat`), GitHub Copilot, and Claude Desktop.
*   **Semantic Linking:** Automatically links chat discussions to the code files they mention.
*   **Unified Search:** Query code and chat history simultaneously. "Show me the authentication code AND the discussion where we decided to use JWT."

```bash
# Auto-discover and index all AI conversations
knowgraph discover-conversations
```

### 3. ⚡ Smart Automation (Post-Indexing Hooks - v0.6.0)

The workflow doesn't end with indexing. KnowGraph triggers intelligent agents after every update.

*   **Auto-Tagging:** Automatically tags nodes with concepts like "Security Critical", "Legacy Code", or "Performance Hotspot" based on analysis.
*   **Analytics:** Generates growth reports and health metrics automatically.
*   **Dynamic Linking:** Connects new code to existing documentation in real-time.

### 4. 🛡️ Resilience & Production Readiness (v0.5.0)

KnowGraph is built for production with enterprise-grade resilience patterns:

*   **🔌 Circuit Breaker:** Automatic failure detection and recovery.
*   **⏱️ Rate Limiting:** Token bucket algorithm with burst capacity.
*   **🔄 Retry Logic:** Exponential backoff with jitter.
*   **🚦 Request Throttling:** Adaptive concurrency control.
*   **📋 API Versioning:** Semantic versioning with automatic negotiation.

### Core Capabilities

*   **🔍 Semantic Search:** Natural language queries with context-aware retrieval via `QueryEngine`
*   **⚡ Async/Await Support:** 15x faster batch queries with concurrent processing using `query_async()`
*   **🚀 Performance Caching:** 22x speedup on repeated queries through `CacheManager`
*   **📊 Impact Analysis:** Predict ripple effects of code changes using `ImpactAnalyzer`
*   **🎯 Hierarchical Context:** Automatic lifting of parent README context for enriched understanding
*   **🧠 Graph Traversal:** BFS/DFS exploration of code relationships (imports, calls, inheritance)
*   **✅ Graph Validation:** Ensure knowledge graph consistency via `GraphValidator`

#### Performance Highlights (v0.6.0)

| Feature | Performance | Improvement |
|---------|-------------|-------------|
| **Batch Queries** | 1.19s (5 queries) | **15.72x faster** 🚀 |
| **Warm Cache** | 0.18s | **22x faster** 🔥 |
| **Centrality** | 0.01s (cached) | **372x faster** ⚡ |
| **Indexing** | ~10 files/sec | **Optimized AST** 🏎️ |

See [CHANGELOG.md](CHANGELOG.md) for details.

---

## ⚡ Cognitive Upgrade in 30 Seconds (Quick Start)

Connect KnowGraph as an MCP server to boost your AI editor's IQ.

### 1. Installation

```bash
pip install knowgraph
```

### 2. Brain Link (Configuration)

Add the following to your **Claude Desktop** (`claude_desktop_config.json`) or **Cursor** settings:

```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "env": {
        "KNOWGRAPH_API_KEY": "sk-..."
      }
    }
  }
}
```

### 3. Index Your Knowledge Base

```bash
# Index local markdown files
knowgraph index /path/to/markdown/files

# Index a GitHub repository directly
knowgraph index https://github.com/user/repo

# Index conversations from your editor
knowgraph discover-conversations
```

### 4. Cheat Sheet: Version Control

```bash
# List all graph versions
knowgraph version list

# Show details of a specific version
knowgraph version show <version_id>

# See what changed between updates
knowgraph version diff <old_id> <new_id>

# Revert to a previous state
knowgraph version rollback <version_id>
```

---

## 🧪 The Lab: Cognitive Capability Tests

Run these **scientific experiments** (prompts) to witness the KnowGraph difference.

<details open>
<summary><b>🧪 Click to Expand: Ready-to-use Commands</b></summary>

> 🤖 **User (Stats):** "Show me the node and edge statistics of my KnowGraph database."
>
> 🤖 **User (Time Travel):** "List the available versions of the knowledge graph and tell me what changed in the last update."
>
> 🤖 **User (Conversational Memory):** "Find the conversation where we discussed the 'Retry Logic' implementation and show me the relevant code snippets."

</details>

<details open>
<summary><b>🦋 Experiment 1: The "Butterfly Effect" Analysis (Impact Analysis)</b> - <i>Predict chaotic consequences.</i></summary>
> 🤖 **User:** "Analyze the 'butterfly effect' if I delete `include/video_processor.hpp`. Show the chain of broken dependencies, both direct and indirect (N-Hop)."
</details>

<details open>
<summary><b>🕸️ Experiment 2: Semantic Network Discovery (Conceptual Integration)</b> - <i>Meaning beyond keywords.</i></summary>
> 🤖 **User:** "Explain FFmpeg's 'memory management' strategies and 'buffering' mechanisms. Expand my query with technical terminology (Query Expansion) and provide logical proof (explanation) for your answer."
</details>

<details open>
<summary><b>🦴 Experiment 3: Architectural X-Ray (Deep Architecture)</b> - <i>Reveal invisible connections.</i></summary>
> 🤖 **User:** "Trace the connection between the `RATE_LIMIT` value in `docker-compose.yml` and `rate_limiter.cpp` deep in the C++ code, including all intermediate layers, up to 8 hops deep (Deep Hop)."
</details>

---

## 📚 Knowledge Base

For those who want to dive into the deep tech:

*   **[📖 User Guide](docs/USER_GUIDE.md)**: Comprehensive guide covering versioning, indexing, querying, and troubleshooting.
*   **[🔧 MCP Rules & Detailed Prompts](docs/KNOWGRAPH_MCP_RULES.md)**: Best practices for using KnowGraph with AI assistants.
*   **[🏗️ Architecture & Algorithms](docs/ARCHITECTURE.md)**: Graph theory, node weighting algorithms, and system architecture.
*   **[📦 Repository Indexing](docs/REPOSITORY_INDEXING.md)**: Guide for indexing Git repositories and code directories.

## 🤝 Contribute to Science

This project is open source and grows with collective intelligence. PRs are welcome.

## 📄 License

[MIT](LICENSE)

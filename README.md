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

## 🚀 Performance Engine (v0.3.0)

KnowGraph is built for scale. The **Smart Indexing Engine** processes large repositories efficiently:

*   **⚡ Hybrid Intelligence:** Code files are analyzed using **AST (Abstract Syntax Tree)** via `ASTAnalyzer` for 100x speed and 0-token cost, while text files use Batch LLM processing through `OpenAIProvider` or `MCPSamplingProvider`.
*   **🧠 Persistent Memory:** Built-in SQLite Caching via `CacheManager` (`.knowgraph_cache`) ensures you never re-index unchanged files. Resumes instantly after interruptions.
*   **🛡️ Smart Rate Limiter:** The `RateLimiter` class automatically respects API limits (Free/Pro tiers) by dynamically throttling requests based on headers, preventing 429 errors.
*   **🏎️ Concurrent Batching:** `SmartGraphBuilder` processes 10 chunks per call with 20 parallel workers, maximizing throughput.
*   **📊 Graph Algorithms:** Leverages NetworkX for centrality calculations (Betweenness, Degree, Closeness, Eigenvector) to identify architecturally critical components.

---

## 🎯 Key Features

### Multi-Source Indexing (v0.3.0)

KnowGraph now supports **three input formats** for maximum flexibility:

| Source Type | Description | Example |
|------------|-------------|---------|
| 📝 **Markdown Files** | Original functionality, optimized for documentation | `knowgraph index ./docs` |
| 🔗 **Git Repositories** | Direct indexing from GitHub, GitLab, Bitbucket | `knowgraph index https://github.com/user/repo` |
| 📁 **Code Directories** | Automatic conversion to markdown via gitingest | `knowgraph index ./my-project` |

**Advanced Filtering:**
```bash
# Include only Python and Markdown files
knowgraph index https://github.com/user/repo --include "*.py" --include "*.md"

# Exclude dependencies and build artifacts
knowgraph index ./project --exclude "node_modules/*" --exclude "*.lock"

# Index private repositories
export GITHUB_TOKEN="github_pat_xxx"
knowgraph index https://github.com/company/private-repo
```

### Core Capabilities

*   **🔍 Semantic Search:** Natural language queries with context-aware retrieval via `QueryEngine`
*   **⚡ Async/Await Support:** 15x faster batch queries with concurrent processing using `query_async()`
*   **🚀 Performance Caching:** 22x speedup on repeated queries through `CacheManager`
*   **📊 Impact Analysis:** Predict ripple effects of code changes using `ImpactAnalyzer`
*   **🔄 Batch Processing:** Process multiple queries efficiently (15.72x faster) with `batch_query`
*   **✅ Graph Validation:** Ensure knowledge graph consistency via `GraphValidator`
*   **📈 Statistics & Metrics:** Monitor graph health and coverage with `get_stats`
*   **🎯 Query Expansion:** Semantic query enrichment through `QueryExpander`
*   **📝 Explanation Generation:** Transparent reasoning paths via `ExplanationObject`
*   **🏛️ Hierarchical Lifting:** Context from parent directories for better understanding

#### Performance Highlights (v0.3.0)

| Feature | Performance | Improvement |
|---------|-------------|-------------|
| **Batch Queries** | 1.19s (5 queries) | **15.72x faster** 🚀 |
| **Warm Cache** | 0.18s | **22x faster** 🔥 |
| **Centrality** | 0.01s (cached) | **372x faster** ⚡ |

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

> 💡 **Auto-Detection**: KnowGraph automatically detects your project root using:
> 1. Git repository root (if in a git repo)
> 2. Project marker files (pyproject.toml, package.json, Cargo.toml, etc.)
> 3. Current working directory (fallback)
> 
> Each project automatically uses its own `graphstore` directory!

> 📝 **New in v0.3.0:** KnowGraph now supports multiple input formats:
> - **Markdown files** (`.md`) - Original functionality
> - **Git repositories** (GitHub, GitLab, Bitbucket) - NEW! 🎉
> - **Code directories** (automatically converted to markdown) - NEW! 🎉
> 
> While we still recommend [Gittodoc](https://gittodoc.com/) for pre-processing, you can now index repositories directly!

### 3. Index Your Knowledge Base

```bash
# Index local markdown files
knowgraph index /path/to/markdown/files

# NEW: Index a GitHub repository directly
knowgraph index https://github.com/user/repo

# NEW: Index with filtering
knowgraph index https://github.com/user/repo \
  --include "*.py" --include "*.md" \
  --exclude "node_modules/*"
```

For more details, see [Repository Indexing Guide](docs/REPOSITORY_INDEXING.md).

### 4. Usage

Set your environment variables and start chatting with your AI assistant.

---

## 🧪 The Lab: Cognitive Capability Tests

Run these **scientific experiments** (prompts) to witness the KnowGraph difference.

### Experiment 0: Warm-up & Calibration
*Start the engines and test basic instruments.*

<details open>
<summary><b>🧪 Click to Expand: Ready-to-use Commands</b></summary>

> 🤖 **User (Stats):** "Show me the node and edge statistics of my KnowGraph database."
>
> 🤖 **User (Health):** "Validate the health and consistency of the knowledge graph."
>
> 🤖 **User (Expansion Only):** "What are the video processing memory strategies? Search by expanding the query with similar technical terms."
>
> 🤖 **User (Proof Only):** "What security measures are taken in the Docker configuration? Provide your logical explanation along with the answer."

*   **Background:** These commands allow you to test the core functions of the MCP server (`get_stats`, `validate`, `expand_query`, `with_explanation`) individually (atomically).
</details>

<details open>
<summary><b>🦋 Experiment 1: The "Butterfly Effect" Analysis (Impact Analysis)</b> - <i>Predict chaotic consequences.</i></summary>

> 🤖 **User:** "Analyze the 'butterfly effect' if I delete `include/video_processor.hpp`. Show the chain of broken dependencies, both direct and indirect (N-Hop)."

*   **Background:** `knowgraph_analyze_impact(mode="path")`. The system performs reverse graph traversal to map the dependency tree.
</details>

<details open>
<summary><b>🕸️ Experiment 2: Semantic Network Discovery (Conceptual Integration)</b> - <i>Meaning beyond keywords.</i></summary>

> 🤖 **User:** "Explain FFmpeg's 'memory management' strategies and 'buffering' mechanisms. Expand my query with technical terminology (Query Expansion) and provide logical proof (explanation) for your answer."

*   **Background:** `expand_query=True` + `with_explanation=True`. The LLM semantically expands "buffering" to terms like "ring buffer", "zero-copy", and "allocation".
</details>

<details open>
<summary><b>🦴 Experiment 3: Architectural X-Ray (Deep Architecture)</b> - <i>Reveal invisible connections.</i></summary>

> 🤖 **User:** "Trace the connection between the `RATE_LIMIT` value in `docker-compose.yml` and `rate_limiter.cpp` deep in the C++ code, including all intermediate layers, up to 8 hops deep (Deep Hop)."

*   **Background:** `max_hops=8`. Based on "Small World Network" theory, it finds the shortest paths between distant nodes.
</details>

<details open>
<summary><b>🛡️ Experiment 4: Resilience Audit</b> - <i>Test the system's immune system.</i></summary>

> 🤖 **User:** "Analyze the system's survival mechanisms (Try-Catch blocks, Docker Restart Policy) when a 'video processing' operation crashes (exception)."

*   **Background:** Queries both code-level error handling and orchestration-level (Docker) recovery policies holistically.
</details>

<details open>
<summary><b>🔌 Experiment 5: Discovering Invisible Links (Infrastructure Audit)</b> - <i>Blind spots between infrastructure and code.</i></summary>

> 🤖 **User:** "Explain how SSL certificates generated by `ssl/generate_cert.sh` are mounted into the Docker container and how the application reads them in the code. Prove the chain."

*   **Background:** Bridges the gap between DevOps and Developer worlds. Traces the Shell script -> YAML -> Source Code chain.
</details>

<details open>
<summary><b>⛓️ Experiment 6: Dependency Chain Reaction (Dependency Graph)</b> - <i>Risk analysis for library updates.</i></summary>

> 🤖 **User:** "If I change the Boost library version in `CMakeLists.txt`, which source code files using (including) this library should I quarantine and test?"

*   **Background:** `knowgraph_analyze_impact`. Maps the propagation of external dependencies (3rd party libs) within the code.
</details>

<details open>
<summary><b>🩺 Experiment 7: System Check-Up (Health & Maintenance)</b> - <i>Audit your cognitive engine.</i></summary>

> 🤖 **User:** "First, validate the topological consistency of the knowledge graph. If the graph is healthy, report the node and edge statistics (stats)."

*   **Background:** `knowgraph_validate` -> `knowgraph_get_stats`. Checks the data integrity and scale of the MCP server.
</details>

<details open>
<summary><b>🧬 Experiment 8: Semantic Mutation (Conceptual Evolution)</b> - <i>Impact of abstract changes.</i></summary>

> 🤖 **User:** "We decided to replace 'JWT Authentication' with 'OAuth2'. Apart from `auth.cpp`, which components (API server, Docker config, etc.) will be affected by this conceptual change?"

*   **Background:** `mode="semantic"`. Analyzes modules semantically linked to auth logic (session management, header parsing) even if the exact string "JWT" is absent.
</details>

<details open>
<summary><b>🔭 Experiment 9: Hierarchical Cognition (High-Context Lifting)</b> - <i>See the big picture.</i></summary>

> 🤖 **User:** "Describe the role of `src/api_server.cpp` in the general architecture, using information from both its content and the `README`/`CMakeLists.txt` files in the project root. Use a wide 4000-token window for the answer."

*   **Background:** `enable_hierarchical_lifting=True` + `lift_levels=3` + `max_tokens=4000`. Interprets the file not just by its code, but within the context of its ecosystem (folder and project).
</details>

<details open>
<summary><b>🎨 Experiment 10: The "Impossible" Synthesis (Sequence Diagram)</b> - <i>Push existing limits.</i></summary>

> 🤖 **User:** "Assume I am a new developer. Draw a text-based 'Sequence Diagram' showing the path of a request from `main.cpp` until video processing is complete. Support every step with proofs (file references)."

*   **Background:** Tests the engine's limits (Deep Traversal + Semantic Understanding + Synthesis). Combines scattered procedures into a single coherent flow.
</details>

<details>
<summary><b>🌑 Experiment 11: Negative Existence Proof (Void Detection)</b> - <i>Find what is missing.</i></summary>

> 🤖 **User:** "Is there a 'LICENSE' file among the indexed files, and has its content created any nodes in the graph?"

*   **Background:** Existence/Absence check. Queries directly across nodes in the graph.
</details>

---

## 📚 Knowledge Base

For those who want to dive into the deep tech:

*   **[📖 User Guide](docs/USER_GUIDE.md)**: Comprehensive guide covering installation, configuration, indexing, querying, and troubleshooting.
*   **[🔧 MCP Rules & Detailed Prompts](docs/KNOWGRAPH_MCP_RULES.md)**: Best practices for using KnowGraph with AI assistants.
*   **[🏗️ Architecture & Algorithms](docs/ARCHITECTURE.md)**: Graph theory, node weighting algorithms, and system architecture.
*   **[📦 Repository Indexing](docs/REPOSITORY_INDEXING.md)**: Guide for indexing Git repositories and code directories.

## 🤝 Contribute to Science

This project is open source and grows with collective intelligence. PRs are welcome.

## 📄 License

[MIT](LICENSE)

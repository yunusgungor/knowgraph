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

## 🚀 Performance Engine (v0.2.0)

KnowGraph is built for scale. The new **Smart Indexing Engine** processes large repositories efficiently:

*   **⚡ Hybrid Intelligence:** Code files are analyzed using **AST (Abstract Syntax Tree)** for 100x speed and 0-token cost, while standard files use Batch LLM processing.
*   **🧠 Persistent Memory:** Built-in SQLite Caching (`.knowgraph_cache`) ensures you never re-index unchanged files. Resumes instantly after interruptions.
*   **🛡️ Smart Rate Limiter:** Automatically respects API limits (Free/Pro tiers) by dynamically throttling requests based on headers, preventing 429 errors.
*   **🏎️ Concurrent Batching:** Processes 10 chunks per call with 20 parallel workers, maximizing throughput.

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

> ⚠️ **Note:** KnowGraph thrives on structured information in Markdown (`.md`) format. We strongly recommend using [Gittodoc](https://gittodoc.com/) to convert your source code into an optimized graph-ready format.

### 3. Usage

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

*   **[MCP Rules & Detailed Prompts](docs/KNOWGRAPH_MCP_RULES.md)**
*   **[Architecture & Algorithms](docs/ARCHITECTURE.md)**: Graph theory, node weighting algorithms, and system architecture.

## 🤝 Contribute to Science

This project is open source and grows with collective intelligence. PRs are welcome.

## 📄 License

[MIT](LICENSE)

# 🧠 KnowGraph: Graph RAG & MCP Server for Code (v1.0.1 🚀)

[![CI](https://github.com/yunusgungor/knowgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/yunusgungor/knowgraph/actions/workflows/ci.yml)
[![Joern](https://img.shields.io/badge/Powered_by-Joern_CPG-orange?style=flat-square)](https://joern.io)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green?style=flat-square&logo=server)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

<div align="center">

**Transform your AI coding assistant with deep code understanding**

> **"Your code is not just text, it's a living graph."**  
> Shift from vector similarity to the deterministic clarity of **Graph Theory** and **Joern Code Property Graph**.

> **v1.0.1 — Answer Grounding & Anti-Hallucination.** Evidence-backed answers
> with entity-level verification, temporal filtering, SC-quoted (P3-verified)
> relation extraction, and API version negotiation.

[⚡ Quick Start](#-quick-start) • [📚 Full Documentation](docs/USER_GUIDE.md) • [📘 Example Usage Guide](docs/USAGE_GUIDE.md)

</div>

---

## 🔬 Why KnowGraph?

KnowGraph is an **MCP (Model Context Protocol) server** that enhances AI coding assistants with:

- **🎯 Graph-Based Code Understanding**: Follows real relationships (imports, calls, inheritance)
- **🔍 Deep Security Analysis**: Joern-powered vulnerability detection (SQL injection, buffer overflows via policy scans; XSS/XXE/SSRF via taint analysis)
- **⚓ Answer Grounding**: Verifies generated answers against graph evidence (anti-hallucination)
- **📊 Impact Analysis**: Predict ripple effects of code changes
- **🕰️ Time-Travel Debugging**: Version control for your knowledge graph
- **💬 Conversational Memory**: Index and search your AI chat history
- **⚡ High Performance**: ~30s indexing, <1s re-indexing (small project) with smart caching

**Supported Languages:** Python, JavaScript/TypeScript, Java, C/C++, Go, Rust, C#, Scala, PHP, Ruby, Kotlin, Swift, and more (14+ languages)

---

## ⚡ Quick Start

### 1. Installation

```bash
pip install knowgraph

# Install optional components (recommended): Joern code analysis + the
# all-MiniLM-L6-v2 embedding model for dense retrieval. Both go under ~/.knowgraph.
knowgraph-setup
```

### 2. MCP Server Configuration

#### Global Timeout (all MCP servers at once)

If you want a single timeout setting for all MCP servers, set it globally:

```json
{
  "mcpServers": {
    "__global__": {
      "timeout": 300000
    }
  }
}
```

This sets a 300-second (5 minute) default timeout for every MCP tool call — ideal for slow/free providers where synthesis may take 60–120s.

#### For Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "timeout": 120000,
      "env": {
        "KNOWGRAPH_API_KEY": "sk-your-openai-key-here",
        "KNOWGRAPH_API_BASE_URL": "https://openrouter.ai/api/v1",
        "KNOWGRAPH_LLM_MODEL": "x-ai/grok-4.1-fast",
        "KNOWGRAPH_LLM_REQUEST_TIMEOUT": "120",
        "KNOWGRAPH_LLM_SYNTHESIS_TIMEOUT": "115",
        "KNOWGRAPH_QUERY_TOTAL_TIMEOUT": "118"
      }
    }
  }
}
```
> **Timeout tip**: For slow/free providers, raise all three env vars to 90–120s and the MCP client `timeout` to 120000 (120s) so the client doesn't cut before the server responds.
> `KNOWGRAPH_LLM_REQUEST_TIMEOUT` is the per-call budget; `KNOWGRAPH_LLM_SYNTHESIS_TIMEOUT`
> is the whole-synthesis budget (retries included); `KNOWGRAPH_QUERY_TOTAL_TIMEOUT` is the
> entire query-path budget (retrieval + synthesis). Raise your MCP client's tool-call timeout
> to match (≥ 120s).

#### For Cursor

Add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "timeout": 120000,
      "env": {
        "KNOWGRAPH_API_KEY": "sk-your-openai-key-here",
        "KNOWGRAPH_API_BASE_URL": "https://openrouter.ai/api/v1",
        "KNOWGRAPH_LLM_MODEL": "x-ai/grok-4.1-fast",
        "KNOWGRAPH_LLM_REQUEST_TIMEOUT": "120",
        "KNOWGRAPH_LLM_SYNTHESIS_TIMEOUT": "115",
        "KNOWGRAPH_QUERY_TOTAL_TIMEOUT": "118"
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
      "timeout": 120000,
      "env": {
        "KNOWGRAPH_API_BASE_URL": "https://openrouter.ai/api/v1",
        "KNOWGRAPH_LLM_MODEL": "x-ai/grok-4.1-fast",
        "KNOWGRAPH_API_KEY": "sk-your-openai-key-here",
        "KNOWGRAPH_LLM_REQUEST_TIMEOUT": "120",
        "KNOWGRAPH_LLM_SYNTHESIS_TIMEOUT": "115",
        "KNOWGRAPH_QUERY_TOTAL_TIMEOUT": "118"
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

### 3. Restart Your AI Editor

That's it! KnowGraph is now ready to use.

---

## 📚 Documentation

For detailed usage, configuration, and advanced features, see the **[User Guide](docs/USER_GUIDE.md)**.

**Quick Links:**
- [Installation & Setup](docs/USER_GUIDE.md#3-installation)
- [MCP Server Integration](docs/USER_GUIDE.md#8-mcp-server-integration)
- [Joern Code Analysis](docs/USER_GUIDE.md#6-joern-code-analysis)
- [Graph Engineering: Grounding & Anti-Hallucination](docs/USER_GUIDE.md#10-graph-engineering-grounding--anti-hallucination)
- [Advanced Querying](docs/USER_GUIDE.md#9-advanced-querying)
- [Performance Optimization](docs/USER_GUIDE.md#14-performance-optimization)
- [Security Analysis](docs/USER_GUIDE.md#15-security-analysis-deep-dive)
- [Troubleshooting](docs/USER_GUIDE.md#18-troubleshooting--faq)
- **[📘 Example Usage Guide](docs/USAGE_GUIDE.md)**: All commands, combinations and workflows.
- [Architecture](docs/ARCHITECTURE.md)

---

## 🤝 Contributing

Contributions are welcome! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

---

## 📄 License

[MIT](LICENSE)

---

## 🔗 Links

- **GitHub**: [yunusgungor/knowgraph](https://github.com/yunusgungor/knowgraph)
- **Documentation**: [User Guide](docs/USER_GUIDE.md)
- **Issues**: [Report a bug](https://github.com/yunusgungor/knowgraph/issues)
- **MCP Protocol**: [Model Context Protocol](https://modelcontextprotocol.io)
- **Joern**: [Code Property Graph](https://joern.io)


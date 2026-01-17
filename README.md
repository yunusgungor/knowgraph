# 🧠 KnowGraph: Graph RAG & MCP Server for Code (v1.0.0 🚀)

[![CI](https://github.com/yunusgungor/knowgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/yunusgungor/knowgraph/actions/workflows/ci.yml)
[![Joern](https://img.shields.io/badge/Powered_by-Joern_CPG-orange?style=flat-square)](https://joern.io)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green?style=flat-square&logo=server)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

<div align="center">

**Transform your AI coding assistant with deep code understanding**

> **"Your code is not just text, it's a living graph."**  
> Shift from vector similarity to the deterministic clarity of **Graph Theory** and **Joern Code Property Graph**.

[⚡ Quick Start](#-quick-start) • [📚 Full Documentation](docs/USER_GUIDE.md) • [📘 Example Usage Guide](docs/USAGE_GUIDE.md)

</div>

---

## 🔬 Why KnowGraph?

KnowGraph is an **MCP (Model Context Protocol) server** that enhances AI coding assistants with:

- **🎯 Graph-Based Code Understanding**: Follows real relationships (imports, calls, inheritance)
- **🔍 Deep Security Analysis**: Joern-powered vulnerability detection (SQL injection, XSS, buffer overflows)
- **📊 Impact Analysis**: Predict ripple effects of code changes
- **🕰️ Time-Travel Debugging**: Version control for your knowledge graph
- **💬 Conversational Memory**: Index and search your AI chat history
- **⚡ High Performance**: 30s indexing, <1s re-indexing with smart caching

**Supported Languages:** Python, JavaScript/TypeScript, Java, C/C++, Go, Rust, C#, Scala, PHP, Ruby, Kotlin, Swift, and more (15+ languages)

---

## ⚡ Quick Start

### 1. Installation

```bash
pip install knowgraph

# Setup Joern for advanced code analysis (recommended)
knowgraph-setup-joern
```

### 2. MCP Server Configuration

#### For Claude Desktop
Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "knowgraph": {
      "command": "knowgraph",
      "args": ["serve"],
      "env": {
        "KNOWGRAPH_API_BASE_URL": "https://openrouter.ai/api/v1",
        "KNOWGRAPH_LLM_MODEL": "x-ai/grok-4.1-fast",
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
        "KNOWGRAPH_API_BASE_URL": "https://openrouter.ai/api/v1",
        "KNOWGRAPH_LLM_MODEL": "x-ai/grok-4.1-fast",
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
        "KNOWGRAPH_API_BASE_URL": "https://openrouter.ai/api/v1",
        "KNOWGRAPH_LLM_MODEL": "x-ai/grok-4.1-fast",
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

### 3. Restart Your AI Editor

That's it! KnowGraph is now ready to use.

---

## 📚 Documentation

For detailed usage, configuration, and advanced features, see the **[User Guide](docs/USER_GUIDE.md)**.

**Quick Links:**
- [Installation & Setup](docs/USER_GUIDE.md#3-installation)
- [MCP Server Integration](docs/USER_GUIDE.md#8-mcp-server-integration)
- [Joern Code Analysis](docs/USER_GUIDE.md#6-joern-code-analysis-new-v100)
- [Advanced Querying](docs/USER_GUIDE.md#9-advanced-querying)
- [Performance Optimization](docs/USER_GUIDE.md#13-performance-optimization)
- [Security Analysis](docs/USER_GUIDE.md#14-security-analysis-deep-dive)
- [Troubleshooting](docs/USER_GUIDE.md#17-troubleshooting--faq)
- **[📘 Example Usage Guide (New!)](docs/USAGE_GUIDE.md)**: All commands, combinations and workflows.
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

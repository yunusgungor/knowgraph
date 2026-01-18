# KnowGraph v{VERSION}

<!-- Brief description of the release -->

## 🎉 Highlights

<!-- Main features or changes in this release -->

## 📝 Changelog

<!-- Detailed changelog - this can be auto-populated from CHANGELOG.md -->

## 📦 Installation

### PyPI (Recommended)
```bash
pip install --upgrade knowgraph
```

### From source
```bash
pip install git+https://github.com/yunusgungor/knowgraph.git@v{VERSION}
```

## 🔧 Setup

### MCP Server Integration

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
        "KNOWGRAPH_API_KEY": "sk-your-api-key-here"
      }
    }
  }
}
```

### Joern Setup (Optional - for advanced code analysis)
```bash
knowgraph-setup-joern
```

## 📚 Documentation

- [User Guide](https://github.com/yunusgungor/knowgraph/blob/main/docs/USER_GUIDE.md)
- [Usage Guide](https://github.com/yunusgungor/knowgraph/blob/main/docs/USAGE_GUIDE.md)
- [Architecture](https://github.com/yunusgungor/knowgraph/blob/main/docs/ARCHITECTURE.md)

## 🔗 Links

- [GitHub Repository](https://github.com/yunusgungor/knowgraph)
- [PyPI Package](https://pypi.org/project/knowgraph/)
- [Issue Tracker](https://github.com/yunusgungor/knowgraph/issues)

## 🙏 Contributors

<!-- List of contributors for this release -->

---

**Full Changelog**: https://github.com/yunusgungor/knowgraph/compare/v{PREVIOUS_VERSION}...v{VERSION}

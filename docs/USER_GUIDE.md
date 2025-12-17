# KnowGraph User Guide

**Version:** 0.4.0  
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
9. [Command Reference](#9-command-reference)
10. [Troubleshooting](#10-troubleshooting)
11. [Best Practices](#11-best-practices)
12. [FAQ](#12-faq)

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

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    AI Editor (Claude/Cursor)            │
└───────────────────────┬─────────────────────────────────┘
                        │ MCP Protocol
┌───────────────────────▼─────────────────────────────────┐
│                  KnowGraph MCP Server                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Tools: query, index, analyze_impact, validate  │  │
│  └──────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│              Knowledge Graph (GraphStore)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │  Nodes   │  │  Edges   │  │  Sparse Index (TF-IDF)│  │
│  │ (JSONL)  │  │ (JSONL)  │  │                       │  │
│  └──────────┘  └──────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Getting Started

### Prerequisites

- **Python**: 3.10 or higher
- **Operating System**: macOS, Linux, or Windows
- **API Key**: OpenAI API key (for entity extraction and query expansion)
- **AI Editor** (optional): Claude Desktop or Cursor for MCP integration

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

That's it! Your AI editor can now access your knowledge graph.

---

## 3. Installation

### Standard Installation

```bash
pip install knowgraph
```

### Development Installation

For contributing or customization:

```bash
# Clone the repository
git clone https://github.com/yunusgungor/knowgraph.git
cd knowgraph

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Verify Installation

```bash
knowgraph --version
# Output: KnowGraph version 0.3.0

knowgraph --help
# Shows available commands
```

### Optional Dependencies

For repository indexing (v0.3.0+):

```bash
pip install gitingest>=0.3.1
```

This is automatically installed with `knowgraph`, but you can install it separately if needed.

---

## 4. Configuration

### Environment Variables

KnowGraph uses environment variables for configuration:

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `KNOWGRAPH_API_KEY` | Yes | OpenAI API key for LLM operations | - |
| `KNOWGRAPH_MODEL` | No | OpenAI model to use | `gpt-4o-mini` |
| `KNOWGRAPH_GRAPH_PATH` | No | Path to graph storage | `./graphstore` |
| `GITHUB_TOKEN` | No | GitHub PAT for private repos | - |

### Setting Environment Variables

**macOS/Linux:**
```bash
export KNOWGRAPH_API_KEY="sk-..."
export KNOWGRAPH_MODEL="gpt-4o-mini"
export GITHUB_TOKEN="github_pat_..."
```

**Windows (PowerShell):**
```powershell
$env:KNOWGRAPH_API_KEY="sk-..."
$env:KNOWGRAPH_MODEL="gpt-4o-mini"
```

**Persistent Configuration:**

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, etc.):
```bash
# KnowGraph Configuration
export KNOWGRAPH_API_KEY="sk-..."
export KNOWGRAPH_MODEL="gpt-4o-mini"
export KNOWGRAPH_GRAPH_PATH="$HOME/.knowgraph/graphstore"
```

### MCP Server Configuration

For Claude Desktop, edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

**For Cursor/VSCode:**

Same configuration works for all editors:

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
> 1. **Git repository root** - If you're in a git repository
> 2. **Project marker files** - Looks for pyproject.toml, package.json, Cargo.toml, go.mod, etc.
> 3. **Current working directory** - Falls back to where the MCP server was started
> 
> Each project automatically uses its own `graphstore` directory!
> 
> **Example:** If you're working in `/Users/john/myproject` (a git repo), the graphstore will be at `/Users/john/myproject/graphstore`.

---

## 5. Indexing Your Knowledge Base

### Overview

Indexing transforms your source files into a searchable knowledge graph. KnowGraph supports four input formats:

1. **Markdown Files** (`.md`) - Original functionality
2. **Git Repositories** (GitHub, GitLab, Bitbucket) - Added in v0.3.0
3. **Code Directories** - Automatic conversion to markdown
4. **AI Conversations** - Chat histories from AI code editors - NEW in v0.4.0

### 5.1 Indexing Markdown Files

**Basic Usage:**
```bash
knowgraph index /path/to/markdown/files
```

**Recursive Indexing:**
```bash
# Indexes all .md files in directory and subdirectories
knowgraph index /path/to/docs
```

**Custom Output Path:**
```bash
knowgraph index /path/to/docs --output-path /custom/graphstore
```

### 5.2 Indexing Git Repositories

**Public Repository:**
```bash
knowgraph index https://github.com/microsoft/TypeScript
```

**Private Repository:**
```bash
export GITHUB_TOKEN="github_pat_..."
knowgraph index https://github.com/company/private-repo
```

**With Filtering:**
```bash
knowgraph index https://github.com/user/repo \
  --include "*.py" --include "*.md" \
  --exclude "tests/*" --exclude "*.lock"
```

**Supported Platforms:**
- GitHub: `https://github.com/user/repo`
- GitLab: `https://gitlab.com/user/repo`
- Bitbucket: `https://bitbucket.org/user/repo`

### 5.3 Indexing Code Directories

**Basic Usage:**
```bash
knowgraph index /path/to/my-project
```

**With Patterns:**
```bash
knowgraph index /path/to/my-project \
  --include "src/**/*.py" \
  --include "docs/**/*.md" \
  --exclude "node_modules/*" \
  --exclude "__pycache__/*" \
  --exclude "*.pyc"
```

### 5.4 Indexing AI Conversations (NEW in v0.4.0)

KnowGraph can automatically discover and index conversations from AI code editors - no manual export needed!

**Supported Editors:**
- 🤖 **Antigravity** (Gemini): Conversation artifacts (task.md, walkthrough.md, implementation_plan.md)
- 🎯 **Cursor**: .aichat files
- 🧠 **Claude Desktop**: JSON conversation exports
- 🐙 **GitHub Copilot**: VSCode chat histories

**Auto-Discovery:**

```bash
# Discover and index all conversations
knowgraph discover-conversations

# Specify output directory
knowgraph discover-conversations --output ./graphstore

# Filter by specific editor
knowgraph discover-conversations --editor antigravity
knowgraph discover-conversations --editor cursor
knowgraph discover-conversations --editor copilot

# Preview without indexing (dry-run)
knowgraph discover-conversations --dry-run

# Verbose output
knowgraph discover-conversations --verbose
```

**Manual Indexing:**

You can also index specific conversation files directly:

```bash
# Index a GitHub Copilot conversation
knowgraph index path/to/conversation.json

# Index a Cursor .aichat file
knowgraph index path/to/chat.aichat

# Index Claude Desktop export
knowgraph index path/to/claude_export.json
```

**Querying Conversations:**

Once indexed, conversations are searchable like any other content:

```bash
# Find FastAPI implementation examples
knowgraph query "FastAPI REST API implementation"

# Search for authentication code
knowgraph query "JWT authentication example"

# Find specific conversation topics
knowgraph query "database migration discussion"
```

**Why Index Conversations?**
- 💡 Preserve important AI-generated code snippets
- 🔍 Search across all your coding sessions
- 📚 Build a knowledge base from AI interactions
- 🏷️ Tag and bookmark critical responses
- 📊 Track your learning and problem-solving patterns

**Via MCP (in Claude/Cursor):**

```json
{
  "tool": "knowgraph_discover_conversations",
  "arguments": {
    "graph_path": "./graphstore",
    "editor": "all"
  }
}
```

### 5.5 Advanced Indexing Options

**Resume After Interruption:**
```bash
# Only works for local files
knowgraph index /path/to/docs --resume
```

**Garbage Collection:**
```bash
# Remove deleted nodes during update
knowgraph index /path/to/docs --gc
```

**File Size Limit:**
```bash
# Via Python API
from knowgraph.infrastructure.parsing.repo_ingestor import ingest_source

content, path, type = ingest_source(
    input_path="https://github.com/user/repo",
    max_file_size=1024000  # 1MB max per file
)
```

### 5.6 Indexing Workflow

When you run `knowgraph index`, the following happens:

1. **Source Detection**: Automatically detects input type
2. **Content Extraction**: 
   - Markdown: Direct parsing
   - Repository/Directory: Conversion via gitingest
   - Conversations: Format-specific parsing
3. **Parsing**: Splits into logical sections (H1-H4 headers)
4. **Chunking**: Token-aware chunking (preserves context)
5. **Entity Extraction**:
   - **Code files**: AST analysis (fast, 0 tokens)
   - **Text files**: LLM batch processing
   - **Caching**: SQLite cache prevents re-processing
6. **Graph Building**: Creates nodes and semantic edges
7. **Indexing**: Builds TF-IDF sparse index
8. **Persistence**: Saves to JSONL files

### 5.7 Monitoring Indexing Progress

```bash
knowgraph index /path/to/large/repo
```

Output shows:
```
🔍 Detecting source type...
✓ Source type: repository
📥 Ingesting repository...
✓ Repository ingested: 1,234 files
📝 Parsing markdown...
✓ Parsed 456 sections
🧠 Extracting entities...
  ├─ Code files: 234 (AST analysis)
  ├─ Text files: 222 (LLM processing)
  └─ Cached: 0
🔗 Building graph...
✓ Created 975 nodes, 2,079 edges
💾 Saving to graphstore...
✓ Indexing complete!
```

---

## 6. Querying the Knowledge Graph

### 6.1 Basic Queries

**Via MCP (in Claude/Cursor):**
```
"What are the main authentication mechanisms in this codebase?"
```

The AI assistant will automatically use the `knowgraph_query` tool.

**Via Python API:**
```python
from knowgraph.application.querying.engine import QueryEngine
from pathlib import Path

engine = QueryEngine(graph_store_path=Path("./graphstore"))
result = engine.query(
    query_text="What are the main authentication mechanisms?",
    top_k=20,
    max_hops=4
)

print(result.answer)
print(result.sources)
```

### 6.2 Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | Required | Natural language question |
| `top_k` | int | 20 | Number of seed nodes to retrieve |
| `max_hops` | int | 4 | Maximum graph traversal depth |
| `max_tokens` | int | 3000 | Maximum context window size |
| `with_explanation` | bool | false | Include reasoning path |
| `expand_query` | bool | false | Use AI to expand query terms |
| `enable_hierarchical_lifting` | bool | true | Include parent context |
| `lift_levels` | int | 2 | Directory levels to lift |

### 6.3 Query Optimization Strategies

**Precision-Focused (Fast):**
```json
{
  "query": "How does login work?",
  "top_k": 10,
  "max_hops": 2,
  "expand_query": false
}
```

**Recall-Focused (Comprehensive):**
```json
{
  "query": "How does login work?",
  "top_k": 50,
  "max_hops": 8,
  "expand_query": true,
  "with_explanation": true
}
```

**Balanced (Recommended):**
```json
{
  "query": "How does login work?",
  "top_k": 20,
  "max_hops": 4,
  "with_explanation": true
}
```

### 6.4 Query Expansion

Enable query expansion to find semantically related content:

```json
{
  "query": "memory management",
  "expand_query": true
}
```

The LLM expands "memory management" to include:
- "allocation"
- "deallocation"
- "garbage collection"
- "memory leak"
- "buffer overflow"

### 6.5 Hierarchical Lifting

Include parent directory context for better understanding:

```json
{
  "query": "What does api_server.cpp do?",
  "enable_hierarchical_lifting": true,
  "lift_levels": 3
}
```

This includes:
- File content
- Parent directory README
- Grandparent directory README
- Project root README

### 6.6 Batch Queries

Process multiple queries efficiently:

```json
{
  "queries": [
    "How does authentication work?",
    "What are the main API endpoints?",
    "How is error handling implemented?"
  ],
  "top_k": 20,
  "max_hops": 4
}
```

---

## 7. MCP Server Integration

### 7.1 Available MCP Tools

KnowGraph exposes 6 tools via the MCP protocol:

| Tool | Description | Use Case |
|------|-------------|----------|
| `knowgraph_query` | Semantic search | Answer questions about codebase |
| `knowgraph_index` | Index files/repos | Add new knowledge |
| `knowgraph_analyze_impact` | Impact analysis | Predict change effects |
| `knowgraph_validate` | Validate graph | Check consistency |
| `knowgraph_get_stats` | Get statistics | Monitor graph health |
| `knowgraph_batch_query` | Batch queries | Process multiple questions |

### 7.2 Using MCP Tools in Claude Desktop

**Example Conversation:**

**You:** "Show me the statistics of my knowledge graph."

**Claude:** *Uses `knowgraph_get_stats` tool*
```
Graph Statistics:
- Nodes: 975
- Edges: 2,079
- Files Indexed: 3
- Semantic Edges: 2,079
```

**You:** "How does the video processing pipeline work?"

**Claude:** *Uses `knowgraph_query` tool with appropriate parameters*
```
The video processing pipeline consists of three main stages:
1. Input validation (video_processor.hpp)
2. Frame extraction (frame_extractor.cpp)
3. Output encoding (encoder.cpp)

[Detailed explanation with source references]
```

### 7.3 Impact Analysis

**You:** "If I delete video_processor.hpp, what will break?"

**Claude:** *Uses `knowgraph_analyze_impact` tool*
```
Impact Analysis for video_processor.hpp:

Direct Dependencies (1 hop):
- frame_extractor.cpp (imports video_processor.hpp)
- main.cpp (includes video_processor.hpp)

Indirect Dependencies (2-3 hops):
- encoder.cpp (uses frame_extractor.cpp)
- api_server.cpp (calls main processing loop)

Total Affected Files: 12
Risk Level: HIGH
```

### 7.4 Graph Validation

**You:** "Validate the health of my knowledge graph."

**Claude:** *Uses `knowgraph_validate` tool*
```
Graph Validation Results:

✓ All nodes have valid UUIDs
✓ All edges reference existing nodes
✓ No orphaned nodes detected
✓ Manifest is consistent
✓ Index is up to date

Status: HEALTHY
```

### 7.3 Semantic Bookmarking (NEW in v0.4.0)

Tag and save important AI responses for later retrieval.

**Via MCP Tool:**

```json
{
  "tool": "knowgraph_tag_snippet",
  "arguments": {
    "tag": "important implementation",
    "snippet": "Complete FastAPI authentication example with JWT tokens...",
    "graph_path": "./graphstore",
    "conversation_id": "optional-conversation-id",
    "user_question": "How do I implement JWT auth?"
  }
}
```

**Parameters:**
- `tag` (required): Label for the snippet (e.g., "auth pattern", "database migration")
- `snippet` (required): The AI response content to save
- `graph_path` (optional): Graph storage path
- `conversation_id` (optional): Link to source conversation
- `user_question` (optional): Original question for context

**Querying Tagged Snippets:**

Tagged snippets are automatically indexed and searchable:

```bash
# Find by tag
knowgraph query "important implementation"

# Find by content
knowgraph query "JWT authentication"

# Find by question
knowgraph query "How do I implement auth"
```

**Use Cases:**
- 💡 Save breakthrough solutions
- 📚 Build personal code snippet library
- 🏷️ Organize learning by topic
- 🔍 Quick reference for common patterns
- 📊 Track important decisions

**Example Workflow:**

1. Ask AI a question in your editor
2. Get a great response with code
3. Tag it using `knowgraph_tag_snippet`
4. Later, query by tag or content
5. Retrieve the exact solution instantly

**Best Practices:**
- Use descriptive tags ("jwt-auth-pattern" not "code1")
- Include user question for context
- Tag only truly important responses
- Use consistent tag naming conventions

---

## 8. Advanced Features

### 8.1 Custom Intelligence Providers

Create your own LLM provider:

```python
from knowgraph.domain.intelligence.provider import IntelligenceProvider, Entity

class CustomProvider(IntelligenceProvider):
    async def extract_entities(self, content: str) -> list[Entity]:
        # Your implementation
        # Could use local models, custom APIs, etc.
        pass
    
    async def generate_response(
        self, 
        query: str, 
        context: str, 
        system_prompt: str = ""
    ) -> str:
        # Your implementation
        pass

# Use custom provider
from knowgraph.application.indexing.smart_builder import SmartGraphBuilder

builder = SmartGraphBuilder(provider=CustomProvider())
await builder.build_from_directory(Path("./docs"))
```

### 8.2 Graph Export

Export your graph for analysis:

```python
from knowgraph.application.export.exporter import GraphExporter
from pathlib import Path

exporter = GraphExporter(graph_store_path=Path("./graphstore"))

# Export to NetworkX format
nx_graph = exporter.to_networkx()

# Export to JSON
json_data = exporter.to_json()

# Export to CSV
exporter.to_csv(output_dir=Path("./exports"))
```

### 8.3 Incremental Updates

Update your graph without full re-indexing:

```bash
# Add new files
knowgraph index /path/to/new/docs

# Update existing files (with garbage collection)
knowgraph index /path/to/docs --gc
```

The system:
- Detects unchanged files (via SHA-1 hash)
- Skips re-processing (uses cache)
- Updates only modified content
- Removes deleted nodes (with `--gc`)

### 8.4 Custom Scoring Weights

Adjust node importance scoring:

```python
from knowgraph.domain.algorithms.scoring import NodeScorer

# Default weights
scorer = NodeScorer(
    alpha=0.6,  # Similarity weight
    beta=0.3,   # Centrality weight
    gamma=0.1   # Seed bonus weight
)

# Custom weights (favor centrality)
scorer = NodeScorer(
    alpha=0.4,
    beta=0.5,
    gamma=0.1
)
```

### 8.5 Performance Tuning

**For Large Repositories:**

```bash
# Increase batch size (more memory, faster)
export KNOWGRAPH_BATCH_SIZE=20

# Increase worker count (more CPU, faster)
export KNOWGRAPH_WORKERS=30

# Reduce context window (less memory)
knowgraph query "..." --max-tokens 2000
```

**For Low-Resource Systems:**

```bash
# Reduce batch size
export KNOWGRAPH_BATCH_SIZE=5

# Reduce workers
export KNOWGRAPH_WORKERS=5

# Disable hierarchical lifting
knowgraph query "..." --no-hierarchical-lifting
```

---

## 9. Command Reference

### 9.1 CLI Commands

**`knowgraph index`**

Index files, directories, or repositories.

```bash
knowgraph index [OPTIONS] INPUT_PATH
```

Options:
- `--output-path PATH`: Graph storage path (default: `./graphstore`)
- `--resume`: Resume from checkpoint (local files only)
- `--gc`: Garbage collect deleted nodes
- `--include PATTERN`: Include file pattern (repeatable)
- `--exclude PATTERN`: Exclude file pattern (repeatable)
- `--access-token TOKEN`: GitHub PAT for private repos

**`knowgraph serve`**

Start the MCP server.

```bash
knowgraph serve [OPTIONS]
```

Options:
- `--graph-path PATH`: Graph storage path (default: `./graphstore`)
- `--log-level LEVEL`: Logging level (default: `INFO`)

**`knowgraph query`**

Query the knowledge graph (CLI mode).

```bash
knowgraph query [OPTIONS] QUERY_TEXT
```

Options:
- `--top-k INT`: Number of seed nodes (default: 20)
- `--max-hops INT`: Maximum traversal depth (default: 4)
- `--max-tokens INT`: Context window size (default: 3000)
- `--expand-query`: Enable query expansion
- `--with-explanation`: Include reasoning path
- `--no-hierarchical-lifting`: Disable hierarchical lifting

**`knowgraph validate`**

Validate graph consistency.

```bash
knowgraph validate [OPTIONS]
```

Options:
- `--graph-path PATH`: Graph storage path

**`knowgraph stats`**

Show graph statistics.

```bash
knowgraph stats [OPTIONS]
```

Options:
- `--graph-path PATH`: Graph storage path

### 9.2 Python API Reference

**QueryEngine**

```python
from knowgraph.application.querying.engine import QueryEngine
from pathlib import Path

engine = QueryEngine(graph_store_path=Path("./graphstore"))

result = engine.query(
    query_text="How does X work?",
    top_k=20,
    max_hops=4,
    max_tokens=3000,
    with_explanation=True,
    expand_query=False,
    enable_hierarchical_lifting=True,
    lift_levels=2
)

print(result.answer)
print(result.sources)
print(result.explanation)
```

**SmartGraphBuilder**

```python
from knowgraph.application.indexing.smart_builder import SmartGraphBuilder
from knowgraph.infrastructure.intelligence.openai_provider import OpenAIProvider
from pathlib import Path

provider = OpenAIProvider(api_key="sk-...")
builder = SmartGraphBuilder(provider=provider)

await builder.build_from_directory(
    directory=Path("./docs"),
    output_path=Path("./graphstore"),
    resume=False,
    gc=False
)
```

**Repository Ingestor**

```python
from knowgraph.infrastructure.parsing.repo_ingestor import (
    ingest_source,
    detect_source_type
)

# Detect source type
source_type = detect_source_type("https://github.com/user/repo")
# Returns: "repository"

# Ingest source
content, path, type = await ingest_source(
    input_path="https://github.com/user/repo",
    include_patterns=["*.py", "*.md"],
    exclude_patterns=["tests/*"],
    access_token="github_pat_..."
)
```

---

## 10. Troubleshooting

### 10.1 Common Issues

**Issue: "No manifest found"**

```
Error: No manifest found at ./graphstore/metadata/manifest.json
```

**Solution:**
```bash
# Index your knowledge base first
knowgraph index /path/to/docs
```

**Issue: "Empty query results"**

```
Query returned 0 results
```

**Solutions:**
1. Increase `top_k`: `--top-k 50`
2. Increase `max_hops`: `--max-hops 8`
3. Enable query expansion: `--expand-query`
4. Check if files are indexed: `knowgraph stats`

**Issue: "GitingestNotInstalledError"**

```
GitingestNotInstalledError: gitingest is not installed
```

**Solution:**
```bash
pip install gitingest>=0.3.1
```

**Issue: "API rate limit exceeded"**

```
RateLimitError: Rate limit exceeded
```

**Solutions:**
1. Wait for rate limit reset
2. Use a paid OpenAI API key (higher limits)
3. Reduce batch size: `export KNOWGRAPH_BATCH_SIZE=5`

**Issue: "Private repository access denied"**

```
RepositoryIngestorError: Failed to ingest repository: 404
```

**Solutions:**
1. Set GitHub token: `export GITHUB_TOKEN="github_pat_..."`
2. Verify token has repo access
3. Check repository URL is correct

### 10.2 Debugging

**Enable Debug Logging:**

```bash
export KNOWGRAPH_LOG_LEVEL=DEBUG
knowgraph index /path/to/docs
```

**Check Graph Health:**

```bash
knowgraph validate
knowgraph stats
```

**Inspect Graph Files:**

```bash
# View manifest
cat graphstore/metadata/manifest.json | python -m json.tool

# Count nodes
ls graphstore/nodes | wc -l

# View a node
cat graphstore/nodes/<uuid>.json | python -m json.tool
```

### 10.3 Performance Issues

**Slow Indexing:**

1. **Enable caching** (automatic with `.knowgraph_cache`)
2. **Reduce batch size** for memory-constrained systems
3. **Use include/exclude patterns** to filter files
4. **Disable LLM processing** for code-only repos (uses AST)

**Slow Queries:**

1. **Reduce `max_hops`**: Try 2-3 instead of 4-6
2. **Disable hierarchical lifting**: `--no-hierarchical-lifting`
3. **Reduce `top_k`**: Try 10 instead of 20
4. **Reduce `max_tokens`**: Try 2000 instead of 3000

**High Memory Usage:**

1. **Reduce batch size**: `export KNOWGRAPH_BATCH_SIZE=5`
2. **Reduce workers**: `export KNOWGRAPH_WORKERS=5`
3. **Process in chunks**: Index directories separately

---

## 11. Best Practices

### 11.1 Indexing Best Practices

**1. Use Appropriate Filters**

```bash
# Good: Specific patterns
knowgraph index /project \
  --include "src/**/*.py" \
  --include "docs/**/*.md" \
  --exclude "tests/*" \
  --exclude "*.pyc" \
  --exclude "__pycache__/*"

# Bad: No filters (indexes everything)
knowgraph index /project
```

**2. Index Documentation First**

```bash
# Start with high-value content
knowgraph index /project/docs
knowgraph index /project/README.md

# Then add code
knowgraph index /project/src
```

**3. Use Incremental Updates**

```bash
# Initial index
knowgraph index /project/docs

# Later, add new content
knowgraph index /project/docs/new-feature.md

# Update with garbage collection
knowgraph index /project/docs --gc
```

**4. Organize by Concern**

```bash
# Separate graphs for different concerns
knowgraph index /project/backend --output-path ./graphs/backend
knowgraph index /project/frontend --output-path ./graphs/frontend
knowgraph index /project/docs --output-path ./graphs/docs
```

### 11.2 Querying Best Practices

**1. Start Broad, Then Narrow**

```
# First query (broad)
"What are the main components of the authentication system?"

# Follow-up (narrow)
"How does the JWT token validation work in the auth middleware?"
```

**2. Use Hierarchical Lifting for Architecture Questions**

```json
{
  "query": "What is the overall architecture?",
  "enable_hierarchical_lifting": true,
  "lift_levels": 3,
  "max_tokens": 4000
}
```

**3. Use Impact Analysis Before Changes**

```
"If I change the database schema in user.py, what else will be affected?"
```

**4. Request Explanations for Critical Decisions**

```json
{
  "query": "How should I implement feature X?",
  "with_explanation": true
}
```

### 11.3 Security Best Practices

**1. Protect API Keys**

```bash
# Good: Environment variables
export KNOWGRAPH_API_KEY="sk-..."

# Bad: Hardcoded in scripts
knowgraph serve --api-key "sk-..."  # Don't do this!
```

**2. Use GitHub Tokens Securely**

```bash
# Good: Environment variable
export GITHUB_TOKEN="github_pat_..."

# Bad: Command line argument (visible in history)
knowgraph index https://github.com/user/repo --access-token "github_pat_..."
```

**3. Validate Input Sources**

```bash
# Good: Verify repository ownership
knowgraph index https://github.com/trusted-org/repo

# Caution: Unknown sources
knowgraph index https://github.com/random-user/repo  # Review first!
```

### 11.4 Maintenance Best Practices

**1. Regular Validation**

```bash
# Weekly health check
knowgraph validate
knowgraph stats
```

**2. Periodic Re-indexing**

```bash
# Monthly full re-index (with garbage collection)
rm -rf graphstore
knowgraph index /project --gc
```

**3. Monitor Graph Size**

```bash
# Check graph size
du -sh graphstore
# If too large, use more aggressive filtering
```

**4. Backup Your Graph**

```bash
# Backup before major changes
tar -czf graphstore-backup-$(date +%Y%m%d).tar.gz graphstore
```

---

## 12. FAQ

### General Questions

**Q: What's the difference between KnowGraph and traditional RAG?**

A: Traditional RAG uses vector similarity (embeddings) to find relevant content. KnowGraph uses **graph topology** to follow actual code relationships (imports, calls, inheritance). This provides:
- More precise context
- Deterministic reasoning paths
- Better understanding of architecture
- Lower hallucination rate

**Q: Do I need to use Gittodoc?**

A: No! As of v0.3.0, KnowGraph can directly index Git repositories and code directories using the integrated gitingest tool. However, Gittodoc can still be useful for pre-processing very large codebases.

**Q: Can I use KnowGraph without an AI editor?**

A: Yes! You can use the CLI (`knowgraph query`) or Python API directly. The MCP server is optional.

**Q: What languages does KnowGraph support?**

A: KnowGraph works with any language. For code files, it uses AST analysis (currently Python, JavaScript, TypeScript) for fast entity extraction. For other languages, it falls back to LLM-based extraction.

### Indexing Questions

**Q: How long does indexing take?**

A: Depends on size:
- Small project (100 files): ~1-2 minutes
- Medium project (1,000 files): ~10-15 minutes
- Large project (10,000 files): ~1-2 hours

AST analysis is instant; LLM processing depends on API speed.

**Q: Can I index private repositories?**

A: Yes! Set `GITHUB_TOKEN` environment variable with a Personal Access Token that has repo access.

**Q: Does indexing cost money?**

A: Yes, for LLM-based entity extraction (text files). Code files use free AST analysis. Typical costs:
- Small project: $0.10-0.50
- Medium project: $1-5
- Large project: $10-50

Costs are one-time; cached results are reused.

**Q: Can I pause and resume indexing?**

A: Yes, for local files use `--resume`. For repositories, you'll need to restart (gitingest doesn't support resume).

### Querying Questions

**Q: Why are my query results empty?**

A: Common reasons:
1. Graph not indexed yet
2. Query too specific (increase `top_k`, `max_hops`)
3. Content not in indexed files
4. Try enabling `expand_query`

**Q: How do I get better answers?**

A: Tips:
1. Enable `with_explanation` to see reasoning
2. Use `expand_query` for semantic search
3. Increase `max_hops` for deeper traversal
4. Enable `hierarchical_lifting` for context
5. Ask specific questions

**Q: Can I query multiple graphs?**

A: Not directly, but you can:
1. Merge graphs (export and combine)
2. Query each separately
3. Use separate MCP servers (different ports)

### Performance Questions

**Q: How much memory does KnowGraph use?**

A: Typical usage:
- Indexing: 500MB - 2GB (depends on batch size)
- Querying: 100MB - 500MB (depends on graph size)
- MCP Server: 50MB - 200MB (idle)

**Q: Can I run KnowGraph on a laptop?**

A: Yes! KnowGraph is designed for local development. Minimum requirements:
- 4GB RAM (8GB recommended)
- 1GB disk space (for medium project)
- Python 3.10+

**Q: How do I speed up queries?**

A: Optimization tips:
1. Reduce `max_hops` (2-3 instead of 4-6)
2. Reduce `top_k` (10 instead of 20)
3. Disable `hierarchical_lifting` if not needed
4. Use smaller `max_tokens` (2000 instead of 3000)

### Integration Questions

**Q: Does KnowGraph work with VS Code?**

A: Not directly (VS Code doesn't support MCP yet). But you can:
1. Use the Python API in VS Code extensions
2. Use the CLI from VS Code terminal
3. Wait for MCP support in VS Code

**Q: Can I use KnowGraph with other LLMs?**

A: Yes! Implement a custom `IntelligenceProvider`:
- Local models (Ollama, LM Studio)
- Other APIs (Anthropic, Cohere, etc.)
- Custom fine-tuned models

**Q: Can I integrate KnowGraph into my application?**

A: Yes! Use the Python API:
```python
from knowgraph.application.querying.engine import QueryEngine
engine = QueryEngine(graph_store_path=Path("./graphstore"))
result = engine.query("How does X work?")
```

### Troubleshooting Questions

**Q: "No manifest found" error?**

A: Run `knowgraph index /path/to/docs` first to create the graph.

**Q: "GitingestNotInstalledError"?**

A: Run `pip install gitingest>=0.3.1`.

**Q: MCP server not responding?**

A: Check:
1. Server is running: `ps aux | grep knowgraph`
2. Config is correct in `claude_desktop_config.json`
3. Restart Claude Desktop
4. Check logs: `~/Library/Logs/Claude/mcp*.log`

**Q: High API costs?**

A: Reduce costs:
1. Use AST analysis (code files, free)
2. Enable caching (automatic)
3. Filter files with `--include`/`--exclude`
4. Use cheaper model: `export KNOWGRAPH_MODEL=gpt-4o-mini`

---

## Appendix A: File Patterns

### Common Include Patterns

```bash
# Python projects
--include "*.py" --include "*.pyi" --include "*.md"

# JavaScript/TypeScript
--include "*.js" --include "*.ts" --include "*.jsx" --include "*.tsx" --include "*.md"

# Documentation only
--include "*.md" --include "*.rst" --include "*.txt"

# Source code only (multiple languages)
--include "src/**/*.py" --include "src/**/*.js" --include "src/**/*.java"
```

### Common Exclude Patterns

```bash
# Dependencies
--exclude "node_modules/*" --exclude "vendor/*" --exclude ".venv/*"

# Build artifacts
--exclude "dist/*" --exclude "build/*" --exclude "*.pyc" --exclude "__pycache__/*"

# Tests (if not needed)
--exclude "tests/*" --exclude "test/*" --exclude "*_test.py"

# Lock files
--exclude "*.lock" --exclude "package-lock.json" --exclude "poetry.lock"

# Minified files
--exclude "*.min.js" --exclude "*.min.css"
```

---

## Appendix B: Graph Storage Format

### Directory Structure

```
graphstore/
├── metadata/
│   └── manifest.json          # Graph metadata and file hashes
├── nodes/
│   ├── <uuid1>.json          # Node data (one file per node)
│   ├── <uuid2>.json
│   └── ...
├── edges/
│   └── edges.jsonl           # All edges (one JSON per line)
├── index/
│   └── sparse_index.pkl      # TF-IDF index for fast search
└── .cache/
    └── .knowgraph_cache      # SQLite cache for entity extraction
```

### Node Format

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "hash": "a94a8fe5ccb19ba61c4c0873d391e987982fbbd3",
  "title": "Authentication Flow",
  "content": "# Authentication Flow\n\nThe system uses JWT...",
  "path": "/path/to/docs/auth.md",
  "type": "text",
  "token_count": 234,
  "created_at": 1702345678,
  "header_depth": 1,
  "header_path": "Authentication",
  "line_start": 1,
  "line_end": 50
}
```

### Edge Format

```json
{
  "source": "550e8400-e29b-41d4-a716-446655440000",
  "target": "660e8400-e29b-41d4-a716-446655440001",
  "type": "semantic",
  "score": 0.85,
  "created_at": 1702345678,
  "metadata": {
    "shared_entities": "JWT, authentication, token"
  }
}
```

---

## Appendix C: Scoring Formulas

### Node Importance Score

```
importance = α·similarity + β·centrality + γ·is_seed + role_weight - token_penalty
```

Where:
- **α (ALPHA)**: 0.6 - Similarity weight
- **β (BETA)**: 0.3 - Centrality weight  
- **γ (GAMMA)**: 0.1 - Seed node bonus
- **role_weight**: 0.6-0.9 (based on node type)
- **token_penalty**: 0-0.1 (for very long content)

### Centrality Composite Score

```
composite = w₁·betweenness + w₂·degree + w₃·closeness + w₄·eigenvector
```

Where:
- **w₁**: 0.5 - Betweenness centrality (architectural boundaries)
- **w₂**: 0.2 - Degree centrality (API surface)
- **w₃**: 0.2 - Closeness centrality (accessibility)
- **w₄**: 0.1 - Eigenvector centrality (importance)

---

## Appendix D: Resources

### Documentation

- [GitHub Repository](https://github.com/yunusgungor/knowgraph)
- [Architecture Guide](./ARCHITECTURE.md)
- [MCP Rules](./KNOWGRAPH_MCP_RULES.md)
- [Repository Indexing](./REPOSITORY_INDEXING.md)

### Related Projects

- [Model Context Protocol](https://modelcontextprotocol.io)
- [Gitingest](https://github.com/coderamp-labs/gitingest)
- [Gittodoc](https://gittodoc.com)
- [NetworkX](https://networkx.org)

### Community

- [Issues](https://github.com/yunusgungor/knowgraph/issues)
- [Discussions](https://github.com/yunusgungor/knowgraph/discussions)
- [Contributing](../CONTRIBUTING.md)

---

## Changelog

### v0.3.0 (December 2024)

- ✨ **New**: Direct Git repository indexing
- ✨ **New**: Code directory indexing with automatic markdown conversion
- ✨ **New**: Include/exclude pattern filtering
- ✨ **New**: GitHub Personal Access Token support
- 🔧 **Improved**: MCP tool definitions
- 📚 **Improved**: Documentation and user guide

### v0.2.0 (November 2024)

- ✨ **New**: Smart Indexing Engine with hybrid intelligence
- ✨ **New**: SQLite caching for entity extraction
- ✨ **New**: Smart rate limiter
- ✨ **New**: Concurrent batching
- 🔧 **Improved**: Performance and scalability

### v0.1.0 (October 2024)

- 🎉 Initial release
- ✨ Graph RAG implementation
- ✨ MCP server integration
- ✨ Markdown indexing
- ✨ Semantic search

---

**End of User Guide**

For questions or issues, please visit our [GitHub repository](https://github.com/yunusgungor/knowgraph).

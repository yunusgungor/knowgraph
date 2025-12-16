# Repository and Code Directory Indexing

KnowGraph now supports indexing not just markdown files, but also Git repositories and code directories using the integrated `gitingest` tool.

## Features

- **Markdown Files**: Index local markdown files and directories (original functionality)
- **Git Repositories**: Index remote Git repositories from GitHub, GitLab, Bitbucket
- **Code Directories**: Index local code directories with automatic conversion to markdown
- **Smart Detection**: Automatically detects source type (repository, directory, markdown)
- **Flexible Filtering**: Include/exclude file patterns for precise control
- **Private Repositories**: Support for GitHub Personal Access Tokens

## Installation

The gitingest dependency is automatically installed with knowgraph:

```bash
pip install knowgraph
# or for development
pip install -e .
```

## Usage

### CLI Usage

```bash
# Index local markdown files (original)
knowgraph index /path/to/markdown/files

# Index a GitHub repository
knowgraph index https://github.com/user/repo

# Index a GitLab repository
knowgraph index https://gitlab.com/user/repo

# Index a local code directory
knowgraph index /path/to/code/directory
```

### MCP Server Usage

The MCP server's `knowgraph_index` tool now accepts additional parameters:

```json
{
  "input_path": "https://github.com/user/repo",
  "include_patterns": ["*.py", "*.md"],
  "exclude_patterns": ["node_modules/*", "*.lock"],
  "access_token": "github_pat_xxx"
}
```

#### Parameters

- **`input_path`** (required): Path to markdown files, local directory, or Git repository URL
- **`output_path`** (optional): Path to graph storage (defaults to `./graphstore`)
- **`resume`** (optional): Resume indexing from checkpoint (only for local files)
- **`gc`** (optional): Garbage collect deleted nodes during update
- **`include_patterns`** (optional): File patterns to include (e.g., `["*.py", "*.md"]`)
- **`exclude_patterns`** (optional): File patterns to exclude (e.g., `["node_modules/*"]`)
- **`access_token`** (optional): GitHub Personal Access Token for private repositories

### Python API Usage

```python
from knowgraph.infrastructure.parsing.repo_ingestor import ingest_source

# Ingest any source (automatically detects type)
content, output_path, source_type = ingest_source(
    input_path="https://github.com/user/repo",
    include_patterns=["*.py", "*.md"],
    exclude_patterns=["node_modules/*", "*.lock"],
    access_token="github_pat_xxx"
)

print(f"Source type: {source_type}")
print(f"Markdown saved to: {output_path}")
```

## Examples

### Example 1: Index a Public Repository

```bash
knowgraph index https://github.com/microsoft/TypeScript-Node-Starter
```

This will:
1. Download the repository using gitingest
2. Convert all files to markdown format
3. Index the markdown into the knowledge graph
4. Store the graph in `./graphstore`

### Example 2: Index a Private Repository

```bash
export GITHUB_TOKEN="github_pat_xxx"
knowgraph index https://github.com/company/private-repo
```

Or via MCP:

```json
{
  "name": "knowgraph_index",
  "arguments": {
    "input_path": "https://github.com/company/private-repo",
    "access_token": "github_pat_xxx"
  }
}
```

### Example 3: Index Only Python Files

```json
{
  "name": "knowgraph_index",
  "arguments": {
    "input_path": "https://github.com/user/repo",
    "include_patterns": ["*.py"],
    "exclude_patterns": ["tests/*", "*.pyc"]
  }
}
```

### Example 4: Index Local Code Directory

```bash
knowgraph index /path/to/my/project
```

This will automatically detect that it's a code directory and convert it to markdown before indexing.

### Example 5: Query After Indexing

```json
{
  "name": "knowgraph_query",
  "arguments": {
    "query": "How does authentication work in this codebase?",
    "top_k": 20,
    "max_hops": 6
  }
}
```

## Source Type Detection

KnowGraph automatically detects the source type:

- **Repository**: URLs containing `github.com`, `gitlab.com`, or `bitbucket.org`
- **Directory**: Local paths containing code files (`.py`, `.js`, `.ts`, etc.)
- **Markdown**: Local paths with `.md` extension or directories containing only markdown

You can also force a specific type:

```python
from knowgraph.infrastructure.parsing.repo_ingestor import ingest_source

content, path, type = ingest_source(
    input_path="/path/to/dir",
    force_type="directory"  # Force treating as code directory
)
```

## Best Practices

### 1. Use Include/Exclude Patterns for Large Repositories

```json
{
  "include_patterns": ["src/**/*.py", "docs/**/*.md"],
  "exclude_patterns": [
    "node_modules/*",
    "dist/*",
    "*.lock",
    "*.min.js",
    "__pycache__/*"
  ]
}
```

### 2. Set Appropriate File Size Limits

```python
ingest_source(
    input_path="https://github.com/user/repo",
    max_file_size=1024000  # 1MB max per file
)
```

### 3. For Private Repositories

Always use environment variables or secure storage for access tokens:

```bash
export GITHUB_TOKEN="github_pat_xxx"
```

### 4. Query Optimization

After indexing a repository, use hierarchical lifting for better context:

```json
{
  "query": "What are the main components?",
  "enable_hierarchical_lifting": true,
  "lift_levels": 3,
  "max_hops": 6
}
```

## Architecture

The repository indexing workflow:

1. **Source Detection**: Automatically detects if input is a repository, directory, or markdown
2. **Gitingest Processing**: For repositories/code directories, uses gitingest to convert to markdown
3. **Markdown Parsing**: Parses the generated or existing markdown into sections
4. **Chunking**: Splits sections into token-aware chunks
5. **AI Enrichment**: Extracts entities and relationships using LLM
6. **Graph Building**: Creates nodes and semantic edges
7. **Indexing**: Builds sparse index for fast retrieval

## Error Handling

### Gitingest Not Installed

If you see:
```
GitingestNotInstalledError: gitingest is not installed
```

Install it with:
```bash
pip install gitingest>=0.3.1
```

### Repository Access Error

For private repositories:
```
RepositoryIngestorError: Failed to ingest repository: 404
```

Ensure you have:
1. Valid GitHub Personal Access Token
2. Correct repository URL
3. Appropriate repository permissions

### Network Errors

If ingestion fails due to network issues:
- Check your internet connection
- Verify the repository URL is accessible
- Try again with retry logic

## Limitations

1. **Repository Size**: Very large repositories (>1GB) may take significant time to process
2. **Binary Files**: Binary files are excluded by default (can be configured)
3. **Resume Mode**: Only works for local files, not for remote repositories
4. **Rate Limiting**: GitHub API rate limits apply for public repositories without tokens

## Contributing

To add support for additional Git hosting platforms:

1. Update `detect_source_type()` in `repo_ingestor.py`
2. Add tests in `test_repo_ingestor.py`
3. Update this documentation

## Related Documentation

- [Gitingest Documentation](https://github.com/coderamp-labs/gitingest)
- [KnowGraph Architecture](./ARCHITECTURE.md)
- [MCP Server Guide](./MCP_RULES.md)

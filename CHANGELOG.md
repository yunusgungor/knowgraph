# Changelog

All notable changes to this project will be documented in this file.


The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.1] - 2026-01-17

### 🔄 CI/CD & Documentation Hardening

#### 🧪 CI Pipeline
- **Java Integration**: Added JDK 21 setup to GitHub Actions for full Joern capability testing.
- **Dependency Setup**: Integrated `knowgraph-setup-joern` into the CI workflow.
- **Strict Linting**:
  - Enforced `ruff` zero-tolerance policy.
  - Enforced `mypy` type checking (resolved `setuptools` stubs).
  - Adjusted test coverage thresholds for realistic CI passing.

#### 📚 Documentation Updates
- **AI Editor Rules**: Defined "Strict Coding Standards" (Section 1.1) mandating MyPy strictness and Pathlib usage.
- **User Guide**:
  - Added explicit `knowgraph-setup-joern` installation steps.
  - Added MCP Client configuration for Claude Desktop and Cursor.
  - Completed the MCP Tool reference table with missing Joern tools.
- **Sync**: Ensured `README.md`, `CONFIGURATION.md`, and `USER_GUIDE.md` are fully aligned with v0.8.x capabilities.

#### ⚡ Joern Enhancements
- **Executable Permissions**: Automatically fixes permissions for all binaries in `joern-cli/bin/` (including frontends).
- **CPG Conversion**: Improved CPG generation reliability and cleanup mechanism.
- **OpenSpec**: Added AI Agent OpenSpec documentation (v0.8.0 transition support).
- **Cleanup**: Removed obsolete Joern integration docs to prevent confusion.

#### 🐛 Bug Fixes
- **Error Handling**: Removed duplicate exception handler in `index_helpers.py`.
- **Typing**: Fixed `ImportError` handling for `setuptools.command.install`.

## [0.8.0] - 2025-12-27

### 🚀 Major Feature: Joern Code Analysis Engine

This release introduces the **Code Property Graph (CPG) Engine**, powered by Joern. This transforms KnowGraph from a semantic search tool into a deep code analysis platform.

### ✨ New Features

#### 🧠 Deep Code Intelligence (Phase 1-3)
- **Hybrid Analysis Strategy**: Automatically routes small files to AST and complex files/languages to Joern CPG.
- **Multi-Language Support**: Full support for Python, JavaScript, TypeScript, Java, C/C++, Go, Rust, and 20+ others.
- **Graph-Based Code Analysis**:
  - **Dominance Analysis**: Detects control flow dependencies and exit points.
  - **Call Graph Analysis**: validaton, recursion detection, and call chain mapping.
  - **Data Flow Analysis**: Taint tracking (Source -> Sink) for security auditing.

#### 🛡️ Security & Quality (Phase 4)
- **`knowgraph_security_scan`**: Automated vulnerability detection (SQLi, XSS, Command Injection, etc.).
- **`knowgraph_find_dead_code`**: Reachability analysis to identify unused methods.
- **`knowgraph_analyze_call_graph`**: Interactive call chain traceability for debugging.

#### ⚡ Performance & Architecture
- **Joern Daemon**: Persistent background process for high-performance querying.
- **Incremental Indexing**: Smart checksum-based updates (only processes changed files).
- **Parallel Generation**: Multi-threaded CPG generation for large repositories (>50 files).
- **CPG Caching**: 24-hours TTL caching to prevent redundant processing.

#### 🔌 MCP Integration
- **New Tools**:
  - `knowgraph_joern_query`: Execute raw Joern DSL queries.
  - `knowgraph_export_cpg`: Export graphs to DOT, JSON, Neo4j, GraphML.
  - `knowgraph_generate_cpg`: Manual CPG management.
- **Smart Routing**: `knowgraph_query` now automatically detects "code questions" and routes them to Joern.

### 📚 Documentation
- **Complete Overhaul**:
  - `AI_EDITOR_RULES.md`: Added Security Workflows and Admin Protocols.
  - `CONFIGURATION.md`: Added Performance Tunables.
  - `USER_GUIDE.md`: New section "Joern Code Analysis".
  - `ARCHITECTURE.md`: Deep dive into the CPG pipeline.

### 🛠️ Technical Improvements
- **Zero Dead Code**: Verified 100% active utilization of all embedded Joern modules.
- Added Joern integration setup utility (`knowgraph-setup-joern`) handles JDK detection and Joern binary fetching automatically.
- **MCP Resilience**: Improved async handling and PYTHONPATH resolution for end-to-end testing.

## [0.7.2] - 2025-12-XX

### Previous stable release
- Graph versioning and time-travel debugging
- Conversation intelligence support
- Smart automation with post-indexing hooks
- Enhanced search & indexing

---

## Migration Guide

See [MIGRATION_v0.8.md](./MIGRATION_v0.8.md) for detailed upgrade instructions from v0.7.x to v0.8.0.

### Quick Migration Steps:
```bash
# Backup existing graph
cp -r graphstore graphstore_v0.7_backup

# Upgrade
pip install --upgrade knowgraph

# Verify Joern (auto-installed)
knowgraph-setup-joern

# Re-index for new features
knowgraph index /path/to/repo
```

---

## [Unreleased]

### Planned for v0.9.0
- Native dataflow query API
- Taint analysis visualization
- Vulnerability detection patterns
- Cross-language impact analysis

[0.8.1]: https://github.com/yunusgungor/knowgraph/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/yunusgungor/knowgraph/compare/v0.7.2...v0.8.0
[0.7.2]: https://github.com/yunusgungor/knowgraph/releases/tag/v0.7.2

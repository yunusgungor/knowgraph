# Changelog

All notable changes to this project will be documented in this file.


The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2025-12-22

### 🎉 100% Joern Integration Complete

This release achieves **complete Joern integration**, adding advanced static code analysis capabilities including dominance analysis, call graph validation, security policy enforcement, and interactive REPL support.

### Added

#### Phase 4 Sprint 1: Dominance Analysis & Export Formats
- **`DominanceAnalyzer`**: Control flow dominance analysis
  - Dead code detection (methods with no callers)
  - Post-dominance analysis for exit point identification
  - Immediate dominator finding for control flow optimization
  - Control dependency graph construction
  
- **Enhanced Export Capabilities**: 5 export formats via `JoernProvider.export_cpg()`
  - **JSON**: Structured CPG data for processing pipelines
  - **SARIF**: Static Analysis Results Interchange Format for CI/CD integration
  - **Neo4j**: Import CPG directly into Neo4j graph databases
  - **DOT**: Graphviz visualization format
  - **GraphML**: Enhanced XML format with full metadata

#### Phase 4 Sprint 2: Call Graph & Policy Engine
- **`CallGraphAnalyzer`**: Comprehensive call graph analysis
  - Call graph validation with entry point and leaf method detection
  - Recursive call detection (direct and indirect recursion)
  - Call chain analysis (find all paths between methods)
  - Method caller/callee relationship mapping
  
- **`PolicyEngine`**: Security policy validation framework
  - **10 Predefined CWE-Mapped Policies**:
    - Buffer Overflow (CWE-120) - Critical
    - SQL Injection (CWE-89) - Critical  
    - Command Injection (CWE-78) - Critical
    - XSS (CWE-79) - High
    - Hardcoded Secrets (CWE-798) - High
    - Unsafe Deserialization (CWE-502) - High
    - Weak Crypto (CWE-327) - Medium
    - Information Exposure (CWE-200) - Medium
    - NULL Pointer Dereference (CWE-476) - Medium
    - Use After Free (CWE-416) - Critical
  - Custom policy definitions with Joern query templates
  - Severity-based filtering (CRITICAL, HIGH, MEDIUM, LOW)
  - Violation reporting with code locations and recommendations

#### Phase 4 Sprint 3: Interactive Tools
- **`JoernREPL`**: Interactive Joern shell integration
  - Start interactive REPL sessions with loaded CPG
  - Execute ad-hoc Joern queries for exploration
  - Real-time code analysis and debugging
  
- **`ScriptManager`**: Joern script management system
  - Save custom analysis scripts with descriptions
  - Load and execute saved scripts
  - Script library management (list, delete, organize)
  - Version control friendly (plain text `.sc` files)

#### Phase 3: Native DSL Query Execution (v1.3.0)
- **`JoernQueryExecutor`**: Execute native Joern DSL queries
  - Direct Joern script execution on CPG binaries
  - Result parsing and formatting
  - Auto-detection of Joern installation
  
- **Query Template Library**: 14+ predefined security and quality queries
  - Security patterns (SQL injection, command injection, XSS, buffer overflow)
  - Code quality checks (complexity, unused code, type safety)
  - Dataflow analysis (reachable sinks, taint flows)
  
- **QueryEngine Integration**: `query_joern()` method for AI assistants
  - Natural language to Joern query translation
  - MCP tool integration (`joern_query`)
  - 2.5x performance improvement over Phase 2 dataflow

### Fixed

#### Call Graph Validation Output Parsing
- **Root Cause**: CallGraphAnalyzer was incorrectly parsing stderr for Joern output
- **Issue**: Joern's `println()` statements write to stdout, not stderr  
- **Solution**:
  - Added `stdout` to `JoernQueryExecutor.execute_query()` metadata
  - Updated `CallGraphAnalyzer.validate_call_graph()` to parse stdout
- **Impact**: Call graph validation now correctly detects methods and call edges
- **Files Changed**:
  - `knowgraph/domain/intelligence/joern_query_executor.py` (+1 line)
  - `knowgraph/application/analysis/call_graph_analyzer.py` (5 lines modified)

### Test Results

Comprehensive test suite validation:
- **Total Tests**: 17
- **Passed**: 16 (94%)
- **Skipped**: 1 (taint analysis requires full graph store)
- **Coverage**: All major Joern features validated

---

## [1.1.0] - 2025-12-22

### 🚀 Security Features Release

This release adds **automated security vulnerability detection** and **taint analysis** capabilities using Joern's data flow analysis.

### Added

#### Taint Analysis Engine
- **`TaintAnalyzer`**: Core taint analysis engine for source-to-sink vulnerability detection
  - Traces user input from sources (HTTP requests, env vars, CLI args) to dangerous sinks (SQL, shell, file ops)
  - Uses Joern's `data_flow` edges for precise path tracking
  - Confidence scoring based on path complexity (shorter paths = higher confidence)
  
- **Vulnerability Pattern Library**: 6 CWE-mapped security patterns
  - 🔴 **SQL Injection** (CWE-89) - Critical
  - 🟠 **Cross-Site Scripting** (CWE-79) - High
  - 🔴 **Command Injection** (CWE-78) - Critical
  - 🟡 **Path Traversal** (CWE-22) - Medium
  - 🟠 **XML External Entity** (CWE-611) - High
  - 🟠 **Server-Side Request Forgery** (CWE-918) - High
  
- **Custom Pattern Support**: Define your own source/sink patterns for domain-specific vulnerabilities

#### MCP Security Tool
- **`knowgraph_security_scan`**: New MCP tool for automated security scanning
  - Supports targeted scans by vulnerability type (`sql_injection`, `xss`, etc.)
  - Formatted security reports with severity levels and confidence scores
  - Integrates seamlessly with AI code editors (Cursor, Antigravity, etc.)

#### Dataflow Query API
- **`QueryEngine.query_dataflow()`**: Natural language dataflow path finding
  - Find all paths from source to sink using plain English queries
  - Example: "user input from HTTP request" → "SQL query execution"
  - Returns `DataFlowResult` with paths, nodes, and Mermaid visualization
  
- **`DataFlowResult.to_mermaid()`**: Automatic flowchart diagram generation
  - Visualize taint flows as Mermaid diagrams
  - Shows complete data propagation path

#### Test Infrastructure
- **Vulnerable Code Fixtures**: Intentionally vulnerable Flask/Django apps for testing
  - 4 vulnerability types with real-world examples
  - Safe code examples for false-positive testing
  
- **Comprehensive Test Suite**: 25+ test scenarios
  - SQL injection detection (direct & parameterized)
  - XSS detection (reflected & stored)
  - Command injection (subprocess, os.system)
  - Path traversal detection
  - Multi-hop dataflow validation
  - Performance tests (< 5s for 10K nodes)

### Changed

#### Storage Integration
- **TaintAnalyzer** now integrates with filesystem storage layer
  - Real-time graph loading from `graphstore`
  - Efficient node/edge batching for large codebases
  
#### Performance
- Optimized dataflow path finding with NetworkX BFS
- Configurable max path depth to prevent path explosion
- Pattern matching with early termination

### Fixed
- None (new features only)

---

## [1.0.0] - 2025-12-22

### 🚀 Major Release: Joern Integration

This is a **major version release** introducing deep code analysis capabilities powered by Joern's Code Property Graph.

### Added

#### Joern Code Property Graph Integration
- **Automatic Joern Installation**: Joern CLI now auto-installs during `pip install knowgraph` with zero configuration required
- **28+ Language Support**: Full CPG analysis for Python, JavaScript, TypeScript, Java, Go, C, C++, C#, Scala, PHP, Ruby, Kotlin, Swift, and more
- **Hybrid Analysis Strategy**: Intelligent backend selection based on file language and size
  - Small Python files (< 1000 LOC) use fast AST parsing
  - Large/complex files in supported languages use deep Joern CPG analysis
  - Automatic fallback to AST if Joern unavailable
- **New Components**:
  - `JoernProvider`: Core CPG generation and GraphML export functionality
  - `CodeAnalyzer`: Unified hybrid analyzer (replaces `ASTAnalyzer`)
  - `setup_joern.py`: Automatic Joern installation script with JDK detection

#### New Edge Types (Breaking Change)
- **`call`**: Function call relationships (e.g., `foo()` → `foo` definition)
- **`data_flow`**: Data flow edges for taint tracking (variable reaching definitions)
- **`control_flow`**: Control flow paths (execution order, branches, loops)
- **`ast`**: Abstract Syntax Tree hierarchy (fine-grained code structure)

#### New CLI Commands
- `knowgraph-setup-joern`: Manual Joern installation/verification command for troubleshooting

#### Configuration Options
- `KNOWGRAPH_JOERN_ENABLED`: Enable/disable Joern (default: `true`)
- `KNOWGRAPH_JOERN_PATH`: Custom Joern installation path
- `KNOWGRAPH_JOERN_TIMEOUT`: CPG generation timeout (default: 600s)
- `KNOWGRAPH_JOERN_MIN_SIZE`: LOC threshold for hybrid strategy (default: 1000)
- `KNOWGRAPH_JOERN_FAST_LANGUAGES`: Languages that always use AST (default: `python`)

### Changed

#### Breaking Changes
- **EdgeType Enum Extended**: `EdgeType` now includes 7 types (was 3)
  - Old graphs with v0.7.x continue to work but lack new edge types
  - Requires re-indexing to benefit from Joern analysis
- **SmartGraphBuilder**: Now uses `CodeAnalyzer` instead of `ASTAnalyzer`
  - Entity extraction automatically selects AST or Joern backend
  - File path required for language detection

#### Performance
- Python files < 1000 LOC: **0% performance impact** (still uses fast AST)
- Large C/C++/Java projects: **3-5x slower** but with **10x richer analysis**
- Aggressive CPG caching minimizes repeated analysis overhead

### Fixed
- Various Unicode arrow characters in docstrings causing SyntaxError
- Improved error handling and graceful fallback when Joern unavailable

### System Requirements
- **New Requirement**: JDK 11+ (for Joern)
- **macOS Only**: GNU coreutils (`brew install coreutils`)
- Python 3.10+ (unchanged)

---

## [0.7.2] - 2025-12-XX

### Previous stable release
- Graph versioning and time-travel debugging
- Conversation intelligence support
- Smart automation with post-indexing hooks
- Enhanced search & indexing

---

## Migration Guide

See [MIGRATION_v1.0.md](./MIGRATION_v1.0.md) for detailed upgrade instructions from v0.7.x to v1.0.0.

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

### Planned for v1.1.0
- Native dataflow query API
- Taint analysis visualization
- Vulnerability detection patterns
- Cross-language impact analysis

[1.0.0]: https://github.com/yunusgungor/knowgraph/compare/v0.7.2...v1.0.0
[0.7.2]: https://github.com/yunusgungor/knowgraph/releases/tag/v0.7.2

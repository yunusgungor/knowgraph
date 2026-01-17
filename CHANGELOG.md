# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-18

### 🚀 Stability & Correctness
- **Graph Consistency**: Fixed critical issue where `knowgraph_get_stats` reported 0 edges.
- **Edge Generation**: Implemented correct Semantic and Reference edge generation for proper code graph connectivity.
- **Data Integrity**: Removed random UUID generation for edges, resolving dangling edge issues that caused `INVALID` graph states.
- **Validation**: Added `call` and `ast` to valid edge types, ensuring CPG edges pass validation.
- **Versioning**: Implemented a unified "Single Source of Truth" versioning system (`knowgraph.version`).

## [0.9.0] - 2026-01-17

### ✨ Deep Code Analysis Enhancements
- **Taint Analysis**: Improved Joern taint flow queries for better security auditing.
- **Search Capabilities**:
  - Added case-insensitive search for Joern queries.
  - Added pattern-based method search.
  - Added support for listing files, namespaces, and types.
- **Advanced Analysis**:
  - Added Variable Usage Finding and Code Slicing (Data/Control slicers).
  - Added tools to query CFG (Control Flow Graph), PDG (Program Dependence Graph), and CDG (Control Dependence Graph).
  - Added Cyclomatic Complexity and Type Hierarchy analysis.
- **Smart Routing**: Implemented intelligent routing to direct code/data-flow queries to specific handlers.

## [0.8.1] - 2026-01-17

### 🔄 CI/CD & Documentation
- **CI Pipeline**: Added Java 21 setup and `knowgraph-setup-joern` to GitHub Actions.
- **Documentation**: Major overhaul of User Guide and README. Added explicit Joern setup steps.
- **Joern Setup**: 
  - Automatically fixes permissions for executables in `joern-cli/bin`.
  - Improved CPG generation reliability and cleanup.
- **OpenSpec**: Added AI Agent OpenSpec documentation.

## [0.8.0] - 2025-12-27

### 🚀 Initial Joern Integration
- **Engine**: Introduced Code Property Graph (CPG) Engine powered by Joern.
- **New Tools**:
  - `knowgraph_security_scan`: Automated vulnerability detection.
  - `knowgraph_find_dead_code`: Reachability analysis.
  - `knowgraph_analyze_call_graph`: Call chain traceability.
- **Architecture**: Implemented Joern Daemon for high-performance querying and caching.

## [0.7.2] - 2025-12-20

### Beta Release
- **Features**: Graph versioning, time-travel debugging, and conversation intelligence.
- **Search**: FTS5-based bookmark search and indexing.
- **Health**: Added diagnostic handlers for system health checks.

[1.0.0]: https://github.com/yunusgungor/knowgraph/compare/v0.9.0...v1.0.0
[0.9.0]: https://github.com/yunusgungor/knowgraph/compare/v0.8.1...v0.9.0
[0.8.1]: https://github.com/yunusgungor/knowgraph/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/yunusgungor/knowgraph/compare/v0.7.2...v0.8.0

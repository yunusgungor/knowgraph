## 🏗️ Architecture at a Glance

KnowGraph implements **Clean Architecture** with 4 distinct layers:

| Layer | Key Components | Responsibility |
|-------|----------------|----------------|
| **Adapters** | `cli/main.py`, `mcp/server.py` | External interfaces (CLI, MCP server) |
| **Application** | `QueryEngine`, `SmartGraphBuilder`, `ImpactAnalyzer` | Use cases and orchestration |
| **Infrastructure** | `OpenAIProvider`, `CacheManager`, `SparseIndex` | External dependencies (LLM, cache, search) |
| **Shared** | `CircuitBreaker`, `RateLimiter`, `Retry`, `Throttle`, `Versioning` | Resilience patterns (v0.5.0) |
| **Domain** | `Node`, `Edge`, `ASTAnalyzer`, `GraphValidator` | Core business logic and algorithms |

**Technology Stack:**
- **Graph Theory:** NetworkX for centrality analysis (Betweenness, Degree, Closeness, Eigenvector)
- **Code Analysis:** Python AST module via `ASTAnalyzer` for deterministic entity extraction
- **LLM Integration:** OpenAI API and MCP Sampling for semantic understanding
- **Caching:** SQLite-based `CacheManager` for performance optimization
- **Search:** TF-IDF sparse embeddings via `SparseIndex`
- **Resilience:** Enterprise patterns for production (Circuit Breaker, Rate Limiting, Retry, Throttling, Versioning) - v0.5.0

For detailed architecture documentation, see [ARCHITECTURE.md](docs/ARCHITECTURE.md).

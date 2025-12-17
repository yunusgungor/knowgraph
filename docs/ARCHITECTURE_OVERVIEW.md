## 🏗️ Architecture at a Glance

KnowGraph implements **Clean Architecture** with 4 distinct layers:

| Layer | Key Components | Responsibility |
|-------|----------------|----------------|
| **Adapters** | `cli/main.py`, `mcp/server.py` | External interfaces (CLI, MCP server) |
| **Application** | `QueryEngine`, `SmartGraphBuilder`, `ImpactAnalyzer` | Use cases and orchestration |
| **Infrastructure** | `OpenAIProvider`, `CacheManager`, `RateLimiter`, `SparseIndex` | External dependencies (LLM, cache, search) |
| **Domain** | `Node`, `Edge`, `ASTAnalyzer`, `GraphValidator` | Core business logic and algorithms |

**Technology Stack:**
- **Graph Theory:** NetworkX for centrality analysis (Betweenness, Degree, Closeness, Eigenvector)
- **Code Analysis:** Python AST module via `ASTAnalyzer` for deterministic entity extraction
- **LLM Integration:** OpenAI API and MCP Sampling for semantic understanding
- **Caching:** SQLite-based `CacheManager` for performance optimization
- **Search:** TF-IDF sparse embeddings via `SparseIndex`
- **Rate Limiting:** Smart `RateLimiter` with dynamic API tier detection

For detailed architecture documentation, see [ARCHITECTURE.md](docs/ARCHITECTURE.md).

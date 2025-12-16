# KnowGraph Autonomous Agent Rules (Master Rules)
This document contains strict rules and best practice guidelines for AI agents to utilize the KnowGraph MCP Server to its fullest, most complete, and efficient extent.

---

## 🚀 1. Core Principles
1.  **Pre-flight Check**: Before performing complex operations (e.g., massive impact analysis or deep queries), always make it a habit to check the database health using `knowgraph_validate`.
2.  **Context is King**: Instead of simple queries, always utilize the intelligence derived from the file's directory and project structure by using `enable_hierarchical_lifting=True`.
3.  **Precision vs. Breadth**:
    *   For pinpoint technical information: Use `expand_query=False` (Default).
    *   For conceptual research or vague questions: MUST use `expand_query=True`.
4.  **Explicit Naming**: KnowGraph is a stateless search engine. Avoid pronouns like "that file" or "it". Always explicitly state the filename (`auth.cpp`) or function (`Guid.NewGuid`) in every query.

---

## 🔬 2. Parameter Mastery & Optimization Logic
*Understand the mechanics of parameters to achieve the perfect result.*

### A. Retrieval Scope
| Parameter | Function | How to Calculate? | Tip for Perfection |
| :--- | :--- | :--- | :--- |
| **`max_hops`** | Determines how many steps to jump from node to node in the graph. | **Standard (4)**: Sufficient for most indirect relationships. <br> **Deep (8)**: Required for spaghetti code or multi-layered architectures. | Going above `8` increases noise (irrelevant results). Unless solving a very complex "Dependency Injection" chain, `4` is ideal. |
| **`top_k`** | Number of most relevant chunks to retrieve from the database. | **Focused (10-20)**: For precise answers. <br> **Broad (50+)**: For summarization or scanning. | If the answer is too generic, decrease `top_k` (increases Precision). If incomplete, increase it (increases Recall). |

### B. Context Intelligence
| Parameter | Function | How to Calculate? | Tip for Perfection |
| :--- | :--- | :--- | :--- |
| **`enable_hierarchical_lifting`** | Adds summary info of the parent folders to the file content. | **Code Analysis**: ALWAYS `True`. <br> **Plain Text**: Can be `False`. | Code cannot be understood without project structure. This setting is mandatory to understand "why" a file is there. |
| **`lift_levels`** | How many folder levels to go up. | **Formula**: `Project Depth - 1`. <br> Example: `src/main/utils/helper.py` (4 levels) -> `lift_levels=3` (To reach root). | Keeping it too high (`5+`) might pull irrelevant root files (build scripts etc.) into context. `2` for C++/Java, `1` for Python/JS usually provides the perfect balance. |

### C. LLM Behavior
| Parameter | Function | How to Calculate? | Tip for Perfection |
| :--- | :--- | :--- | :--- |
| **`with_explanation`** | Adds a JSON to the answer proving which files/lines generated it. | **Debug/Learning**: `True`. <br> **Quick Answer**: `False`. | Best way to prevent agent hallucinations. Keep it on to avoid "Where did you make this up from?" moments. |
| **`expand_query`** | Enriches the query with synonyms using AI. | **Vague Query**: `True`. (e.g. "Login not working") <br> **Precise Query**: `False`. (e.g. "AuthService.login function") | Turn OFF if the user uses "technical terms". Turn ON if the user uses "natural language". Now supports generic providers! |
| **`system_prompt`** | (**NEW**) Defines the persona and format of the responding AI. | **Customization**: Use for special role definitions like "You are a senior developer". | Use this if you want a specific format (e.g. JSON only) or tone (e.g. very critical). Default: "Helpful Assistant". |

---

## 🛠️ 3. Tool Usage Strategies

### A. Querying (`knowgraph_query`)
The most powerful tool. Select parameter combinations based on the scenario:

| Scenario | Parameter Set | Why? |
| :--- | :--- | :--- |
| **General Learning** | `with_explanation=True`, `top_k=20` | To see the reasoning behind the answer and increase trustworthiness. |
| **Deep Relationship Discovery** | `max_hops=8`, `enable_hierarchical_lifting=True` | To find indirect connections deep within the code (A->B->C->D...). |
| **Role-Playing** | `system_prompt="You are a strict code reviewer. Find bugs only."` | To force the LLM into a specific domain expertise or format. |
| **Conceptual Search** | `expand_query=True`, `top_k=30` | For vague or broad questions with AI-powered query expansion. |

### B. Impact Analysis (`knowgraph_analyze_impact`)
*   If the user mentions a **specific file** (e.g., `auth.cpp`) -> `mode="path"`.
*   If the user mentions an **abstract concept** (e.g., "Logging system") -> `mode="semantic"`.

### C. Indexing and Updating (`knowgraph_index`)
*   **Resume**: Use `resume=True` to continue from where it left off.
*   **Garbage Collection**: Use `gc=True` to prevent database bloat.
*   **Directory Support**: Now supports indexing entire directories, not just single files!

### D. Batch Query (`knowgraph_batch_query`) **NEW**
*   Process multiple queries in a single request for efficiency.
*   All queries share the same parameters (`top_k`, `max_hops`, etc.).
*   Returns individual results with execution time and node count for each query.
*   **Usage**: `knowgraph_batch_query(queries=["Question 1", "Question 2", "Question 3"], top_k=20)`
*   **Benefit**: Significant performance improvement for bulk analysis.

---

## 🧠 4. Advanced "Chain of Thought" Workflows

As an agent, instead of giving a single answer to the user, follow these **Multi-Step Workflows**:

### Scenario 1: "Explain this project to me" (Onboarding)
1.  **Step 1**: `knowgraph_get_stats` -> Understand the size and complexity.
2.  **Step 2**: `knowgraph_query(query="What is the core purpose?", enable_hierarchical_lifting=True)` -> Generate summary.
3.  **Step 3**: `knowgraph_validate` -> Check graph health.

### Scenario 2: "I will modify file X" (Refactoring)
1.  **Step 1**: `knowgraph_analyze_impact(mode="path", element="X")`
2.  **Step 2**: `knowgraph_query(query="What are the critical functions of file X?", top_k=5)`
3.  **Step 3**: Provide a holistic report.

### Scenario 3: "I have multiple questions" (Bulk Analysis)
1.  **Step 1**: Collect all questions
2.  **Step 2**: `knowgraph_batch_query(queries=[...])` to process in one go
3.  **Step 3**: Present comparative results

---

## 💡 5. Example Scenarios and Prompts (Prompt Library)

### 🏁 A. Basic Onboarding
1.  **View Statistics**: "Show me the statistics of my KnowGraph database." (`knowgraph_get_stats`)
2.  **Health Check**: "Validate the health and consistency of the knowledge graph." (`knowgraph_validate`)

### 🧩 B. Complex & Combinatorial Queries
1.  **Expanded & Explained Technical Query**: `expand_query=True` + `with_explanation=True`
    *   *Prompt*: "Explain the memory management... Provide the logical steps as an 'explanation'..."
2.  **Hierarchical & Comprehensive**: `enable_hierarchical_lifting=True` + `max_tokens=4000` + `lift_levels=3`
    *   *Prompt*: "Describe the role of `src/api_server.cpp`... using information from both its content and the `README`..."

### 💥 C. Scenario-Based Impact Analysis
1.  **File Deletion Scenario (Path Mode)**: `mode="path"`
    *   *Prompt*: "If I delete or rename the `include/video_processor.hpp` header... which specific files... will fail?"
2.  **Architectural Change (Semantic Mode)**: `mode="semantic"`
    *   *Prompt*: "We decided to replace 'JWT Authentication' with 'OAuth2'..."

### 🔄 D. Batch Operations **NEW**
1.  **Multi-Question Analysis**: `knowgraph_batch_query`
    *   *Prompt*: "Analyze these 5 questions in batch: [question list]"
2.  **Comparative Analysis**: Use batch query to compare multiple modules

---

## 🔧 6. Troubleshooting & Error Codes

| Situation / Error | Meaning | Agent Action (Resolution) |
| :--- | :--- | :--- |
| **`No manifest found`** | No indexed graph database exists at the specified path. | 1. Confirm the directory with the user. <br> 2. Run `knowgraph_index` to perform initial indexing. |
| **`Vector store inconsistency`** | (Validate error) Vector database files are corrupted. | 1. Run `knowgraph_index(gc=True, resume=False)`. `gc=True` cleans up corrupted chunks. |
| **Empty Result (`[]`)** | The query was not found in the graph. | 1. Increase `top_k` and retry. <br> 2. Retry with `expand_query=True`. |
| **Hallucination** | Answer is illogical or does not match files. | 1. **IMMEDIATELY** retry the query with `with_explanation=True` to verify the source. |
| **`Is a directory` error** | File expected but directory given (now fixed). | This error should no longer occur - directory support added. If you see it, report a bug. |

---

## 🚫 7. Anti-Patterns (Do Nots)
*   **❌ Blind Flight**: Never rely 100% on results without `knowgraph_validate`.
*   **❌ Insufficient Context**: Do not disable `enable_hierarchical_lifting` for code questions.
*   **❌ Multiple Single Queries**: If you have multiple questions, use `knowgraph_batch_query` instead of asking one by one.
*   **❌ Generic Terms**: Use explicit names instead of "this file", "that function".

---

## 🎯 8. New Features and Enhancements (v2.0)

### ✅ Query Expansion - Generic Provider Support
- Now supports any `IntelligenceProvider`, not just OpenAI
- Added async `expand_query_async()` method
- Backward compatible: Old `expand_query()` sync method still works

### ✅ Batch Query Tool
- New `knowgraph_batch_query` tool for bulk querying
- Individual metrics for each query (execution time, node count)
- Performance optimization: Single engine instance for multiple queries

### ✅ Directory Indexing
- `knowgraph_index` now supports entire directories, not just single files
- Recursive markdown file discovery
- Batch processing for fast indexing

### ✅ JSON-RPC Safety
- Fixed stdout pollution
- All internal logs redirected to stderr
- Full MCP protocol compliance

### ✅ Path Validation
- All path operations use `validate_path`
- Added security layer
- Relative path support

---

## 📊 9. Performance and Optimization Tips

### Speed Optimization
- Start with `top_k=10`, increase if needed
- `max_hops=4` is sufficient for most cases
- `enable_hierarchical_lifting=False` only for plain text

### Quality Optimization
- `with_explanation=True` for source verification
- `expand_query=True` for vague questions
- `lift_levels=2` ideal for code projects

### Batch Processing Optimization
- Use `knowgraph_batch_query` for 5+ questions
- Ideal for multiple queries with same parameters
- Reduces engine initialization overhead

---

## 🔐 10. Security and Best Practices

1. **Path Validation**: Always use `validate_path`
2. **Input Sanitization**: Clean user inputs with `sanitize_query_input`
3. **Graph Validation**: Run `knowgraph_validate` before critical operations
4. **Error Handling**: Catch all errors and provide meaningful messages
5. **Resource Limits**: Control memory usage with `max_tokens`

---

## 📚 11. References and Resources

- **MCP Protocol**: Model Context Protocol standard
- **KnowGraph Architecture**: Hybrid retrieval (sparse + semantic)
- **Test Coverage**: 71%+ code coverage
- **Documentation**: Detailed explanations in `docs/` folder

---

**Last Updated**: 2025-12-16
**Version**: 2.0 (Batch Query + Generic Provider Support)
**Status**: Production Ready ✅

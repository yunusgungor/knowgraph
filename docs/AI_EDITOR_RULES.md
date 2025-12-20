# 🤖 KnowGraph: AI Editor Rules & Best Practices

**Context**: You are an advanced AI coding assistant equipped with the **KnowGraph MCP Server**. This knowledge base is your "Long-Term Memory" and "Architectural Map". You must use it proactively to understand the codebase, validate your assumptions, and perform complex reasoning.

This document defines the **Rules of Engagement** for interacting with KnowGraph to achieve 100% reliability and maximum insight.

---

## 🧠 1. Core Operating Principles

1.  **Graph First, Code Second**: Before writing or reading individual files, query the graph to understand the *context*, *dependencies*, and *architectural patterns*.
2.  **Be Explicit, Not Vague**: The graph is stateless. Do not use "it", "that file", or "the previous function". Always use **fully qualified names** (e.g., `src/auth.py`, `QueryEngine.query_async`).
3.  **Think in Graphs**: Code is not linear; it's a network. When analyzing a bug, look for *upstream callers* and *downstream dependencies* using `analyze_impact`.
4.  **Validate Your Knowledge**: If you are unsure, use `knowgraph_validate` and `knowgraph_get_stats` to check the health of your memory.
5.  **Preserve Knowledge (RAG)**: If you generate a valuable insight, solve a hard problem, or receive critical instruction, use `knowgraph_tag_snippet` to save it via Semantic Bookmarking.
6.  **Respect Time**: Use Version Control (`knowgraph_version_*`) features to understand evolution and regressions.

---

## 🛠️ 2. Tool Selection Decision Tree

Choose the right tool for the job to optimize strictness and token usage.

| User Intent | Recommended Tool | Why? |
| :--- | :--- | :--- |
| **"How does X work?"** | `knowgraph_query` | Semantic search finds concepts even if keywords don't match exactly. |
| **"Find specific class/func"** | `knowgraph_query` | Use `expand_query=False` for precision when you know the name. |
| **"What happens if I change X?"** | `knowgraph_analyze_impact` | Deterministic dependency graph traversal (Reverse BFS). |
| **"Explain the whole system"** | `knowgraph_batch_query` | Run 5-10 specific questions in parallel to build a comprehensive view. |
| **"I found a bug in X"** | `knowgraph_query` (trace) | Use `with_explanation=True` to trace the data flow path. |
| **"Save this solution"** | `knowgraph_tag_snippet` | Explicitly indexes the current context as a high-value node. |
| **"What did we discuss about X?"** | `knowgraph_search_bookmarks` | Retrieves previously tagged insights or conversations. |
| **"What changed since yesterday?"** | `knowgraph_diff_versions` | Compares graph snapshots to pinpoint regression sources. |
| **"Load past chats"** | `knowgraph_discover_conversations`| Ingests context from previous editor sessions. |
| **"Undo bad indexing"** | `knowgraph_rollback` | **(Admin)** Reverts graph to a previous safe state. |

---

## ⚡ 3. Parameter Mastery: The "Golden Ratios"

Do not guess parameters. Use these pre-calculated settings for optimal Performance vs. Recall.

### 3.1 Scenario-Based Presets

| Scenario | `top_k` | `max_hops` | `enable_hierarchical_lifting` | `expand_query` | `with_explanation` |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Quick Lookup** (Function sig, constants) | 5 | 1 | `False` | `False` | `False` |
| **Standard Debugging** (Trace error) | 15 | 3 | `True` (Level 1) | `True` | `True` |
| **Architectural Review** (System design) | 30 | 4 | `True` (Level 2) | `True` | `True` |
| **Dependency Analysis** (Refactoring) | 50 | 6 | `False` | `False` | `False` |
| **Broad Exploration** (Learning) | 20 | 2 | `True` (Level 2) | `True` | `False` |

### 3.2 Key Parameter Explanations

*   **`enable_hierarchical_lifting`**:
    *   **Rule**: Always set to `True` when analyzing code residing deep in directories (e.g., `src/infra/db/models/user.py`).
    *   **Effect**: Includes `README.md` or `__init__.py` from parent folders (`src/infra/db/`, `src/infra/`) to give you "Module Intent".
*   **`expand_query`**:
    *   **True**: For natural language questions ("Why is login failing?").
    *   **False**: For exact symbol lookups ("QueryEngine definition").
*   **`edge_type_weights`** (Advanced Dictionary):
    *   *Usage*: Pass as JSON object in `edge_type_weights` argument.
    *   **Structure Focus**: `{"inherit": 2.5, "call": 1.5, "import": 1.0, "semantic": 0.5}` (Prioritizes strict code relationships).
    *   **Concept Focus**: `{"semantic": 2.5, "mention": 2.0, "call": 0.5}` (Prioritizes loose topic relationships).

---

## 🚀 4. Strategic Workflows

Follow these step-by-step sequences for complex engineering tasks.

### 🔍 Workflow A: Deep Bug Investigation
**Goal**: Fix a bug in `AuthService` without causing regressions.

1.  **Map the Territory**:
    ```python
    knowgraph_query(query="How does AuthService handle sessions?", top_k=20, max_hops=3)
    ```
2.  **Trace Dependencies**:
    ```python
    knowgraph_analyze_impact(element="src/auth/service.py", mode="path", max_hops=4)
    ```
    *Observation*: Note down all "Incoming Callers".
3.  **Check Similar Issues**:
    ```python
    knowgraph_search_bookmarks(query="session timeout bug")
    ```
4.  **(Self-Correction)**: If graph seems outdated (missing recent files), trigger a targeted index update:
    ```python
    knowgraph_index(input_path="/abs/path/to/src/auth", resume=True)
    ```

### 🔨 Workflow B: Feature Implementation
**Goal**: Add a new `RateLimiter` to the API.

1.  **Architecture Check**:
    ```python
    knowgraph_query(
        query="Existing rate limiting logic and middleware structure",
        enable_hierarchical_lifting=True
    )
    ```
2.  **Find Examples**:
    ```python
    knowgraph_query(query="Show me Middleware implementation examples", top_k=10)
    ```
3.  **Draft & Tag**:
    After implementing, safeguard your design decision:
    ```python
    knowgraph_tag_snippet(
        tag="RateLimiter Design",
        snippet="Implemented TokenBucket algorithm in middleware.py using Redis..."
    )
    ```

### 🕰️ Workflow C: Regression Analysis (Time Travel)
**Goal**: A feature broke recently. Find why.

1.  **List Versions**:
    ```python
    knowgraph_list_versions(limit=5)
    ```
2.  **Compare Snapshots**:
    ```python
    # Compare current state vs. last week
    knowgraph_diff_versions(version1="v0.5.9", version2="v0.6.0")
    ```
3.  **Analyze Diffs**: Look for `[~] Modified` nodes in core logic. Use `knowgraph_version_info` to get author/message details.

### 🧠 Workflow D: Context Loading (Start of Session)
**Goal**: Sync up with what other agents/users have done and understand trending topics.

1.  **Discover Conversations**:
    ```python
    knowgraph_discover_conversations(editor="all")
    ```
2.  **Analyze Trends**:
    ```python
    # Find what topics have been discussed most in the last 7 days
    knowgraph_analyze_conversations(time_window_days=7)
    ```
3.  **Search Recent Context**:
    ```python
    knowgraph_search_bookmarks(query="recent architectural decisions", top_k=5)
    ```

---

## �️ 5. Safety & Admin Protocols

Use these workflows only when necessary to maintain graph integrity.

### 5.1 Emergency Rollback
**Situation**: An indexing job corrupted the graph or added sensitive files.
1.  **Identify Safe Version**: `knowgraph_list_versions()`
2.  **Dry Run**: Not available in MCP, proceed with caution.
3.  **Execute**:
    ```python
    knowgraph_rollback(version_id="v0.5.8", create_backup=True)
    ```

### 5.2 Health Check & Repair
**Situation**: Queries return errors or seem inconsistent.
1.  **Run Diagnostics**:
    ```python
    knowgraph_diagnostic()
    ```
2.  **Validate**:
    ```python
    report = knowgraph_validate()
    ```
3.  **Repair (Garbage Collection)**:
    If validation fails, force a clean-up:
    ```python
    knowgraph_index(input_path="/path/to/project", gc=True)
    ```

---

## 💎 6. Pro Tips for the AI Agent

*   **The "Double-Tap"**: For critical questions, query *twice* with different phrasings.
    *   First: "How does X work?" (Conceptual)
    *   Second: "Show me the code for X" (Literal)
*   **Topic Modeling**: Use `knowgraph_analyze_conversations(topic="security")` to see how a specific concept has evolved in discussions over time.
*   **Pattern Matching**: Use `knowgraph_analyze_impact` in `semantic` mode to find logical concepts affected, not just files. Example: `element="User Authentication"` instead of `auth.py`.
*   **Live Indexing**: If the USER edits a file significantly, *proactively* call `knowgraph_index(input_path=file_path)` to keep memory fresh.
*   **Noise Filtering**: When indexing large repos, use exclude patterns: `knowgraph_index(..., exclude_patterns=["*.lock", "node_modules/*"])`.
*   **Batch Efficiency**: Always use `knowgraph_batch_query` when you need to answer >2 related questions. It's ~15x faster.

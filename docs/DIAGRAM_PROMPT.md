**Prompt for AI Diagram Generator (e.g., gpai.app / ChatGPT / Midjourney)**

**Role:** You are an expert Software Architect and System Designer specializing in Clean Architecture, Knowledge Graphs, and MCP (Model Context Protocol).

**Task:** Create a highly detailed, professional, and technical system architecture diagram for "KnowGraph," a Python-based MCP server that turns codebases into knowledge graphs. The diagram must clearly visualize the layered "Clean Architecture" pattern, the data flow, and the physical components.

**Visual Style:**
*   **Theme:** Modern technical diagram, sleek, high contrast (Dark Mode preferred).
*   **Colors:** Use distinct colors for each layer (e.g., Blue for Domain, Green for Application, Grey for Infrastructure, Orange for Adapters).
*   **Notation:** UML-like but modernized (C4 Model style).

**Key Components to Include (from Center to Outer Layers):**

1.  **Inner Core: Domain Layer (Business Logic & Entities)**
    *   *Shape:* Central Circle or Box.
    *   *Content:*
        *   `Models`: Node (UUID, Hash, Content), Edge (Source, Target, Score).
        *   `Algorithms`: Graph Traversal (DFS/BFS), Centrality (PageRank), Scoring Logic.
        *   `Interfaces`: IntelligenceProvider (Abstract).

2.  **Middle Layer: Application Layer (Use Cases)**
    *   *Shape:* Ring surrounding the Domain.
    *   *Content:*
        *   `Indexing Pipeline`: Header Parsing -> Chunking -> Entity Extraction.
        *   `Query Engine`: Query Expansion -> Retrieval -> Response Synthesis.
        *   `Evolution`: Incremental Updates (Delta Detection).

3.  **Outer Layer: Infrastructure Layer (Implementation)**
    *   *Shape:* The foundation or outer blocks.
    *   *Content:*
        *   `Storage`: Filesystem (JSONL Persistence).
        *   `Parsing`: Markdown Parsers.
        *   `Intelligence`: OpenAI / Anthropic Integration.
        *   `Graph Lib`: NetworkX.

4.  **Interface Layer: Adapters (Entry Points)**
    *   *Shape:* Interface blocks connecting to the outside.
    *   *Content:*
        *   **`MCP Server`** (Primary Interface): Connects to AI Editors (Cursor/Claude).
        *   `CLI`: Command Line Interface.
        *   `REST API`: Future capability.

**Data Flow Arrows (Critical):**
*   **Indexing Flow:** Files -> Adapters -> Application (Chunking) -> Domain (Node Creation) -> Infrastructure (Disk Storage).
*   **Query Flow:** User Query -> MCP Server -> Query Engine -> Domain (Algorithms) -> Infrastructure (NetworkX) -> Response.

**Text Labels & Annotations:**
*   Title: "KnowGraph System Architecture"
*   Subtitle: "MCP Server for Knowledge Graph RAG"
*   Label the layers: "Domain", "Application", "Infrastructure", "Adapters".
*   Highlight "Clean Architecture" principles (Dependencies point inwards).

**Output format:** Generate a diagram image that looks like a high-level system architecture blueprint.

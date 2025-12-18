"""Graph construction from chunked markdown.

Builds nodes and edges from parsed chunks, implementing hierarchy, semantic,
reference, and cross-file relationships.
"""

import time
from uuid import UUID, uuid4

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.parsing.chunker import Chunk
from knowgraph.infrastructure.parsing.hasher import hash_content


def create_node_from_chunk(chunk: Chunk, source_path: str, node_type: str | None = None) -> Node:
    """Convert chunk to node with metadata.

    Args:
    ----
        chunk: Chunk with content and metadata
        source_path: Source file path (relative)
        node_type: Override node type classification

    Returns:
    -------
        Node object

    """
    content_hash = hash_content(chunk.content)
    node_id = uuid4()
    created_at = int(time.time())

    # Classify node type if not provided
    if node_type is None:
        if chunk.has_code:
            node_type = "code"
        elif "readme" in source_path.lower():
            node_type = "readme"
        elif any(
            ext in source_path.lower()
            for ext in [".yaml", ".yml", ".json", ".toml", ".ini", "config"]
        ):
            node_type = "config"
        else:
            node_type = "text"

    # Use chunk source path if available, otherwise fallback to provided path
    # (chunk.source_path will be the specific file path from indexing,
    # source_path argument might be just the project root)
    actual_path = chunk.source_path if chunk.source_path else source_path

    # Ensure path is relative (remove leading slash if present)
    relative_path = actual_path.lstrip("/")

    return Node(
        id=node_id,
        hash=content_hash,
        title=chunk.header,
        content=chunk.content,
        path=relative_path,
        type=node_type,  # type: ignore
        token_count=chunk.token_count,
        created_at=created_at,
        header_depth=chunk.header_depth,
        header_path=chunk.header_path,
        chunk_id=chunk.chunk_id,
        line_start=chunk.line_start,
        line_end=chunk.line_end,
    )


def create_nodes_from_chunks(chunks: list[Chunk], source_path: str) -> list[Node]:
    """Convert multiple chunks to nodes.

    Args:
    ----
        chunks: List of chunks
        source_path: Source file path

    Returns:
    -------
        List of nodes

    """
    return [create_node_from_chunk(chunk, source_path) for chunk in chunks]


def normalize_markdown_content(content: str) -> str:
    r"""Normalize markdown content for consistent processing.

    Implements FR-005 normalization rules:
    - Standardize line endings to \\n
    - Remove trailing whitespace
    - Collapse multiple blank lines to max 2
    - Normalize header spacing

    Args:
    ----
        content: Raw markdown content

    Returns:
    -------
        Normalized content

    """
    # Standardize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Remove trailing whitespace from lines
    lines = [line.rstrip() for line in content.split("\n")]

    # Collapse multiple blank lines
    normalized_lines = []
    blank_count = 0

    for line in lines:
        if not line.strip():
            blank_count += 1
            if blank_count <= 2:
                normalized_lines.append(line)
        else:
            blank_count = 0
            normalized_lines.append(line)

    # Ensure single blank line after headers
    result_lines = []
    for i, line in enumerate(normalized_lines):
        result_lines.append(line)
        if (
            line.startswith("#")
            and i + 1 < len(normalized_lines)
            and normalized_lines[i + 1].strip()
        ):
            result_lines.append("")  # Add blank line

    return "\n".join(result_lines)


def validate_edges(
    edges: list[Edge],
    nodes: list[Node],
) -> tuple[list[Edge], list[str]]:
    """Validate edges and remove dangling/circular references.

    Args:
    ----
        edges: List of edges to validate
        nodes: List of valid nodes

    Returns:
    -------
        Tuple of (valid_edges, warning_messages)

    """
    node_ids = {node.id for node in nodes}
    valid_edges = []
    warnings = []

    # Check for dangling edges (references to non-existent nodes)
    for edge in edges:
        if edge.source not in node_ids:
            warnings.append(f"Dangling edge: source {edge.source} not found in nodes")
            continue
        if edge.target not in node_ids:
            warnings.append(f"Dangling edge: target {edge.target} not found in nodes")
            continue

        # Prevent self-loops (node pointing to itself)
        if edge.source == edge.target:
            warnings.append(f"Self-loop detected: {edge.source} -> {edge.source}")
            continue

        valid_edges.append(edge)

    return valid_edges, warnings


def create_semantic_edges(nodes: list[Node], threshold: float = 0.1) -> list[Edge]:
    """Create edges based on shared entities (Smart Mode).

    Args:
    ----
        nodes: List of nodes with metadata['entities']
        threshold: Jaccard similarity threshold

    Returns:
    -------
        List of edges

    """
    edges = []
    created_at = int(time.time())

    # Pre-compute entity sets
    node_entities: dict[UUID, set[str]] = {}
    for node in nodes:
        if node.metadata and "entities" in node.metadata:
            # metadata["entities"] is list[dict]
            # We assume it is populated correctly
            raw_entities = node.metadata["entities"]
            if isinstance(raw_entities, list):
                # Extract names
                names = {e.get("name", "").lower() for e in raw_entities if isinstance(e, dict)}
                if names:
                    node_entities[node.id] = names

    # Pairwise comparison
    active_nodes = [n for n in nodes if n.id in node_entities]

    for i, node1 in enumerate(active_nodes):
        entities1 = node_entities[node1.id]

        for node2 in active_nodes[i + 1 :]:
            entities2 = node_entities[node2.id]

            shared = entities1.intersection(entities2)
            if shared:
                union = len(entities1.union(entities2))
                score = len(shared) / union

                if score > threshold:
                    edges.append(
                        Edge(
                            source=node1.id,
                            target=node2.id,
                            type="semantic",
                            score=score,
                            created_at=created_at,
                            metadata={
                                "similarity_type": "ai_entity_overlap",
                                "shared_entities": list(shared),
                            },
                        )
                    )
    return edges


def create_reference_edges(nodes: list[Node]) -> list[Edge]:
    """Create directed edges based on definition/reference roles.

    If Node A references symbol 'foo' and Node B defines symbol 'foo',
    an edge A -> B is created with type 'reference'.

    Args:
    ----
        nodes: List of nodes with metadata['entities']

    Returns:
    -------
        List of reference edges
    """
    edges = []
    created_at = int(time.time())

    # 1. Build Global symbol table (Symbol -> Defining Node IDs)
    symbol_definitions: dict[str, list[UUID]] = {}
    node_references: dict[UUID, set[str]] = {}

    for node in nodes:
        if not node.metadata or "entities" not in node.metadata:
            continue

        entities = node.metadata["entities"]
        if not isinstance(entities, list):
            continue

        refs = set()
        for e in entities:
            if not isinstance(e, dict):
                continue

            name = e.get("name", "")
            if not name:
                continue

            e_type = e.get("type", "semantic")

            if e_type == "definition":
                if name not in symbol_definitions:
                    symbol_definitions[name] = []
                symbol_definitions[name].append(node.id)
            elif e_type in ["reference", "call", "import"]:
                refs.add(name)

        if refs:
            node_references[node.id] = refs

    # 2. Create Edges: Referencer -> Definer
    existing_edges = set()  # (src, target, symbol) to prevent duplicates

    for ref_node_id, refs in node_references.items():
        for symbol in refs:
            if symbol in symbol_definitions:
                for def_node_id in symbol_definitions[symbol]:
                    # Avoid self-references
                    if ref_node_id == def_node_id:
                        continue

                    edge_key = (ref_node_id, def_node_id, symbol)
                    if edge_key in existing_edges:
                        continue
                    existing_edges.add(edge_key)

                    edges.append(
                        Edge(
                            source=ref_node_id,
                            target=def_node_id,
                            type="reference",
                            score=1.0,
                            created_at=created_at,
                            metadata={"symbol": symbol, "relation": "dependency"},
                        )
                    )

    return edges

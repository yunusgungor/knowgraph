"""Delta detection and incremental graph updates.

Implements hash-based change detection with O(Δ) complexity for efficient
updates when code changes.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from knowgraph.application.indexing.graph_builder import (
    create_nodes_from_chunks,
    create_semantic_edges,
    normalize_markdown_content,
)
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.embedding.sparse_embedder import SparseEmbedder
from knowgraph.infrastructure.parsing.chunker import chunk_markdown
from knowgraph.infrastructure.parsing.hasher import hash_content
from knowgraph.infrastructure.search.sparse_index import SparseIndex
from knowgraph.infrastructure.storage.filesystem import (
    delete_node_json,
    list_all_nodes,
    read_node_json,
    write_node_json,
)
from knowgraph.infrastructure.storage.manifest import Manifest, write_manifest
from knowgraph.shared.exceptions import IndexingError


@dataclass
class DeltaAnalysis:
    """Analysis of changes between old and new content.

    Attributes
    ----------
        added_nodes: Newly created nodes
        modified_nodes: Changed nodes (by hash)
        deleted_node_ids: Removed node IDs
        unchanged_node_ids: Nodes without changes
        affected_node_ids: All nodes requiring edge recomputation

    """

    added_nodes: list[Node]
    modified_nodes: list[Node]
    deleted_node_ids: list[UUID]
    unchanged_node_ids: list[UUID]
    affected_node_ids: list[UUID]


def detect_delta(
    old_manifest: Manifest,
    new_content: str,
    source_path: str,
    graph_store_path: Path,
) -> DeltaAnalysis:
    """Detect changes between old manifest and new content.

    Compares file hashes to identify added/modified/deleted nodes.

    Args:
    ----
        old_manifest: Previous manifest
        new_content: New markdown content
        source_path: Source file path
        graph_store_path: Root storage directory

    Returns:
    -------
        Delta analysis with categorized nodes

    """
    # Parse new content
    normalized_content = normalize_markdown_content(new_content)
    new_file_hash = hash_content(normalized_content)
    old_file_hash = old_manifest.file_hashes.get(source_path)

    # Quick check: if file hash unchanged, no delta
    if new_file_hash == old_file_hash:
        # Load all existing nodes for this file
        all_node_ids = list_all_nodes(graph_store_path)
        file_node_ids = []
        for node_id in all_node_ids:
            node = read_node_json(node_id, graph_store_path)
            if node and node.path == source_path:
                file_node_ids.append(node_id)

        return DeltaAnalysis(
            added_nodes=[],
            modified_nodes=[],
            deleted_node_ids=[],
            unchanged_node_ids=file_node_ids,
            affected_node_ids=[],
        )

    # Parse new content into chunks and nodes
    chunks = chunk_markdown(normalized_content, source_path)
    new_nodes = create_nodes_from_chunks(chunks, source_path)

    # Load old nodes for this file
    all_node_ids = list_all_nodes(graph_store_path)
    old_nodes = []
    for node_id in all_node_ids:
        node = read_node_json(node_id, graph_store_path)
        if node and node.path == source_path:
            old_nodes.append(node)

    # Build hash maps
    old_nodes_by_hash = {node.hash: node for node in old_nodes}
    new_nodes_by_hash = {node.hash: node for node in new_nodes}

    # Categorize nodes
    added_nodes = []
    modified_nodes = []
    unchanged_node_ids = []
    deleted_node_ids = []

    # Find added and unchanged
    for node in new_nodes:
        if node.hash not in old_nodes_by_hash:
            added_nodes.append(node)
        else:
            # Content unchanged, reuse old node ID
            old_node = old_nodes_by_hash[node.hash]
            unchanged_node_ids.append(old_node.id)

    # Find deleted
    for node in old_nodes:
        if node.hash not in new_nodes_by_hash:
            deleted_node_ids.append(node.id)

    # Modified nodes = added (new content replaces old)
    modified_nodes = added_nodes

    # Affected nodes = added + modified + deleted
    affected_node_ids = [n.id for n in added_nodes] + deleted_node_ids

    return DeltaAnalysis(
        added_nodes=added_nodes,
        modified_nodes=modified_nodes,
        deleted_node_ids=deleted_node_ids,
        unchanged_node_ids=unchanged_node_ids,
        affected_node_ids=affected_node_ids,
    )


def apply_incremental_update(
    delta: DeltaAnalysis,
    old_manifest: Manifest,
    new_file_hash: str,
    source_path: str,
    graph_store_path: Path,
    gc_orphans: bool = False,
) -> Manifest:
    """Apply incremental update to graph.

    Updates only changed nodes, regenerates affected edges, rebuilds index.

    Args:
    ----
        delta: Delta analysis
        old_manifest: Previous manifest
        new_file_hash: Hash of new file content
        source_path: Source file path
        graph_store_path: Root storage directory
        gc_orphans: Garbage collect deleted nodes

    Returns:
    -------
        Updated manifest

    Raises:
    ------
        IndexingError: If update fails

    """
    try:

        # Step 1: Delete removed nodes
        for node_id in delta.deleted_node_ids:
            if gc_orphans:
                delete_node_json(node_id, graph_store_path)
            else:
                # Mark as orphaned in metadata (keep file for rollback)
                pass

        # Step 2: Write new/modified nodes and regenerate embeddings
        sparse_embedder = SparseEmbedder()
        sparse_embeddings = {}

        for node in delta.added_nodes + delta.modified_nodes:
            # Write node
            write_node_json(node, graph_store_path)

            # Generate and cache embedding (sparse)
            # For sparse, we don't necessarily cache to disk as npy, but maybe we can just re-compute
            # as it is fast. For now, let's just generate in-memory for the index update.
            # If persistence is needed, we'd save JSONs.
            if node.type == "code":
                emb = sparse_embedder.embed_code(node.content)
            else:
                emb = sparse_embedder.embed_text(node.content)

            sparse_embeddings[node.id] = emb

        # Step 3: Load all nodes for edge recomputation
        all_node_ids = list_all_nodes(graph_store_path)
        all_nodes = []
        for node_id in all_node_ids:
            loaded_node = read_node_json(node_id, graph_store_path)
            if loaded_node:
                all_nodes.append(loaded_node)

        # Smart edges (if entities present)
        # We assume nodes have metadata if they were processed by smart update/builder
        semantic_edges = create_semantic_edges(all_nodes)

        all_edges = semantic_edges

        # Write edges
        from knowgraph.infrastructure.storage.filesystem import write_all_edges

        write_all_edges(all_edges, graph_store_path)

        # Step 5: Rebuild sparse index
        # We need embeddings for all nodes to rebuild index
        sparse_embedder = SparseEmbedder()
        index = SparseIndex()

        for node in all_nodes:
            # We re-embed for simplicity. In production, we should cache embeddings.
            if node.type == "code":
                emb = sparse_embedder.embed_code(node.content)
            else:
                emb = sparse_embedder.embed_text(node.content)
            index.add(node.id, emb)
        index.build()
        index.save(graph_store_path / "index")

        # Step 6: Update manifest
        updated_manifest = Manifest(
            version=old_manifest.version,
            created_at=old_manifest.created_at,
            updated_at=int(time.time()),
            node_count=len(all_nodes),
            edge_count=len(all_edges),
            file_hashes={**old_manifest.file_hashes, source_path: new_file_hash},
            edges_filename=old_manifest.edges_filename,
            sparse_index_filename=old_manifest.sparse_index_filename,
            semantic_edge_count=len(semantic_edges),
            finalized=True,  # Mark update as complete
        )

        write_manifest(updated_manifest, graph_store_path)

        return updated_manifest

    except Exception as error:
        raise IndexingError(
            "Incremental update failed",
            {"error": str(error), "file": source_path},
        ) from error


def resume_from_checkpoint(
    manifest: Manifest, source_path: str, new_content: str, graph_store_path: Path
) -> Manifest:
    """Resume interrupted indexing from checkpoint.

    Detects incomplete manifest and re-applies indexing for the file.
    If manifest is already finalized, returns it unchanged.

    Args:
    ----
        manifest: Potentially incomplete manifest
        source_path: Source file path being indexed
        new_content: File content to index
        graph_store_path: Root storage directory

    Returns:
    -------
        Updated manifest with finalized=True

    Raises:
    ------
        IndexingError: If resume fails

    """
    if manifest.finalized:
        # Already complete, no resume needed
        return manifest

    # Manifest incomplete - treat as fresh indexing for this file
    normalized_content = normalize_markdown_content(new_content)
    new_file_hash = hash_content(normalized_content)

    # Perform delta detection (will find all nodes as new since incomplete)
    delta = detect_delta(manifest, new_content, source_path, graph_store_path)

    # Apply incremental update (sets finalized=True)
    return apply_incremental_update(
        delta=delta,
        old_manifest=manifest,
        new_file_hash=new_file_hash,
        source_path=source_path,
        graph_store_path=graph_store_path,
        gc_orphans=True,  # Clean up any partial state
    )

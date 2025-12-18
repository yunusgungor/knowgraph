"""File system operations for nodes and edges."""

import json
from pathlib import Path
from uuid import UUID

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.shared.cache_versioning import invalidate_all_caches
from knowgraph.shared.exceptions import StorageError

# LRU cache for frequently accessed nodes (improves repeated queries)
_node_cache: dict[tuple[Path, UUID], Node | None] = {}
_cache_max_size = 1000
_cache_version: int = 0  # Incremented on invalidation


def _prune_cache_if_needed() -> None:
    """Prune cache if it exceeds max size (simple FIFO)."""
    if len(_node_cache) > _cache_max_size:
        # Remove oldest 20% of entries
        to_remove = len(_node_cache) // 5
        for _ in range(to_remove):
            _node_cache.pop(next(iter(_node_cache)))


def clear_node_cache() -> None:
    """Clear the node cache. Useful for testing or memory management."""
    global _cache_version
    _node_cache.clear()
    _cache_version += 1


def get_cache_stats() -> dict[str, int]:
    """Get cache statistics."""
    return {
        "size": len(_node_cache),
        "max_size": _cache_max_size,
        "utilization": int((len(_node_cache) / _cache_max_size) * 100),
        "version": _cache_version,
    }


def ensure_directory(directory_path: Path) -> None:
    """Create directory if it doesn't exist.

    Args:
    ----
        directory_path: Path to directory

    Raises:
    ------
        StorageError: If directory creation fails

    """
    try:
        directory_path.mkdir(parents=True, exist_ok=True)
    except Exception as error:
        raise StorageError(
            f"Failed to create directory: {directory_path}",
            {"error": str(error)},
        ) from error


def write_node_json(node: Node, graph_store_path: Path) -> None:
    """Write node to JSON file.

    File location: {graph_store_path}/nodes/{node.id}.json

    Args:
    ----
        node: Node to write
        graph_store_path: Root graph storage directory

    Raises:
    ------
        StorageError: If write operation fails

    """
    # Ensure graph_store_path is a Path object
    if isinstance(graph_store_path, str):
        graph_store_path = Path(graph_store_path)

    nodes_dir = graph_store_path / "nodes"
    ensure_directory(nodes_dir)

    node_file = nodes_dir / f"{node.id}.json"
    temp_file = node_file.with_suffix(".tmp")

    try:
        # Atomic write: write to temp file, then rename
        with open(temp_file, "w", encoding="utf-8") as file:
            json.dump(node.to_dict(), file, indent=2, ensure_ascii=False)
        temp_file.rename(node_file)

        # Trigger cache invalidation after successful write
        invalidate_all_caches()
    except Exception as error:
        if temp_file.exists():
            temp_file.unlink()
        raise StorageError(
            f"Failed to write node: {node.id}",
            {"error": str(error), "path": str(node_file)},
        ) from error


def read_node_json(node_id: UUID, graph_store_path: Path, use_cache: bool = True) -> Node | None:
    """Read node from JSON file with optional caching.

    Args:
    ----
        node_id: Node UUID to read
        graph_store_path: Root graph storage directory
        use_cache: Whether to use in-memory cache (default: True)

    Returns:
    -------
        Node object or None if not found

    Raises:
    ------
        StorageError: If read operation fails (excluding not found)

    """
    # Check cache first
    if use_cache:
        cache_key = (graph_store_path, node_id)
        if cache_key in _node_cache:
            return _node_cache[cache_key]

    node_file = graph_store_path / "nodes" / f"{node_id}.json"

    if not node_file.exists():
        if use_cache:
            _node_cache[cache_key] = None
            _prune_cache_if_needed()
        return None

    try:
        with open(node_file, encoding="utf-8") as file:
            data = json.load(file)
        node = Node.from_dict(data)

        # Cache the result
        if use_cache:
            _node_cache[cache_key] = node
            _prune_cache_if_needed()

        return node
    except Exception as error:
        raise StorageError(
            f"Failed to read node: {node_id}",
            {"error": str(error), "path": str(node_file)},
        ) from error


def delete_node_json(node_id: UUID, graph_store_path: Path) -> bool:
    """Delete node JSON file.

    Args:
    ----
        node_id: Node UUID to delete
        graph_store_path: Root graph storage directory

    Returns:
    -------
        True if deleted, False if not found

    Raises:
    ------
        StorageError: If delete operation fails

    """
    node_file = graph_store_path / "nodes" / f"{node_id}.json"

    if not node_file.exists():
        return False

    try:
        node_file.unlink()
        return True
    except Exception as error:
        raise StorageError(
            f"Failed to delete node: {node_id}",
            {"error": str(error), "path": str(node_file)},
        ) from error


def append_edge_jsonl(edge: Edge, graph_store_path: Path) -> None:
    """Append edge to JSONL file.

    File location: {graph_store_path}/edges/edges.jsonl

    Args:
    ----
        edge: Edge to append
        graph_store_path: Root graph storage directory

    Raises:
    ------
        StorageError: If append operation fails

    """
    edges_dir = graph_store_path / "edges"
    ensure_directory(edges_dir)

    edges_file = edges_dir / "edges.jsonl"

    try:
        with open(edges_file, "a", encoding="utf-8") as file:
            json.dump(edge.to_dict(), file, ensure_ascii=False)
            file.write("\n")
    except Exception as error:
        raise StorageError(
            f"Failed to append edge: {edge.source} -> {edge.target}",
            {"error": str(error), "path": str(edges_file)},
        ) from error


def read_all_edges(graph_store_path: Path) -> list[Edge]:
    """Read all edges from JSONL file.

    Args:
    ----
        graph_store_path: Root graph storage directory

    Returns:
    -------
        List of edges (empty if file doesn't exist)

    Raises:
    ------
        StorageError: If read operation fails

    """
    edges_file = graph_store_path / "edges" / "edges.jsonl"

    if not edges_file.exists():
        return []

    edges = []
    try:
        with open(edges_file, encoding="utf-8") as file:
            for line_number, line in enumerate(file, 1):
                if line.strip():
                    try:
                        data = json.loads(line)
                        edges.append(Edge.from_dict(data))
                    except Exception as parse_error:
                        raise StorageError(
                            f"Failed to parse edge at line {line_number}",
                            {"error": str(parse_error), "line": line.strip()},
                        ) from parse_error
    except StorageError:
        raise
    except Exception as error:
        raise StorageError(
            "Failed to read edges file",
            {"error": str(error), "path": str(edges_file)},
        ) from error

    return edges


def write_all_edges(edges: list[Edge], graph_store_path: Path) -> None:
    """Write all edges to JSONL file (overwrites existing).

    Args:
    ----
        edges: List of edges to write
        graph_store_path: Root graph storage directory

    Raises:
    ------
        StorageError: If write operation fails

    """
    edges_dir = graph_store_path / "edges"
    ensure_directory(edges_dir)

    edges_file = edges_dir / "edges.jsonl"
    temp_file = edges_file.with_suffix(".tmp")

    try:
        with open(temp_file, "w", encoding="utf-8") as file:
            for edge in edges:
                json.dump(edge.to_dict(), file, ensure_ascii=False)
                file.write("\n")
        temp_file.rename(edges_file)
    except Exception as error:
        if temp_file.exists():
            temp_file.unlink()
        raise StorageError(
            "Failed to write edges file",
            {"error": str(error), "path": str(edges_file)},
        ) from error


def list_all_nodes(graph_store_path: Path) -> list[UUID]:
    """List all node UUIDs in storage.

    Args:
    ----
        graph_store_path: Root graph storage directory

    Returns:
    -------
        List of node UUIDs

    Raises:
    ------
        StorageError: If directory listing fails

    """
    nodes_dir = graph_store_path / "nodes"

    if not nodes_dir.exists():
        return []

    try:
        node_ids = []
        for file_path in nodes_dir.glob("*.json"):
            try:
                node_id = UUID(file_path.stem)
                node_ids.append(node_id)
            except ValueError:
                # Skip invalid UUID filenames
                continue
        return node_ids
    except Exception as error:
        raise StorageError(
            "Failed to list nodes",
            {"error": str(error), "path": str(nodes_dir)},
        ) from error

"""Manifest management for graph metadata and versioning."""

import json
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from knowgraph.shared.cache_versioning import invalidate_all_caches
from knowgraph.shared.exceptions import StorageError

logger = logging.getLogger(__name__)


@dataclass
class Manifest:
    """Graph snapshot metadata.

    Tracks version information, statistics, and configuration for incremental
    updates and consistency validation.

    Attributes
    ----------
        version: Schema version (e.g., "1.0.0")
        created_at: Unix timestamp of initial creation
        updated_at: Unix timestamp of last update
        node_count: Total number of nodes
        edge_count: Total number of edges
        file_hashes: Mapping of source file paths to SHA-1 hashes
        edges_filename: Filename for the edges data
        sparse_index_filename: Filename for the sparse index data
        semantic_edge_count: Number of semantic edges
        finalized: Whether indexing completed successfully (for checkpoint/resume)
        version_id: Version identifier (e.g., "v1", "v2"); auto-incremented
        previous_version_id: Previous version ID for version chain

    """

    version: str
    node_count: int
    edge_count: int
    file_hashes: dict[str, str]
    edges_filename: str
    sparse_index_filename: str
    created_at: int | None = None
    updated_at: int | None = None
    semantic_edge_count: int = 0
    finalized: bool = False
    version_id: str = "v1"
    previous_version_id: str | None = None

    def __post_init__(self) -> None:
        """Set default timestamps if not provided."""
        if self.created_at is None:
            self.created_at = int(time.time())
        if self.updated_at is None:
            self.updated_at = int(time.time())

    def to_dict(self: "Manifest") -> dict[str, object]:
        """Serialize manifest to dictionary."""
        return {
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "file_hashes": self.file_hashes,
            "files": {
                "edges": self.edges_filename,
                "sparse_index": self.sparse_index_filename,
            },
            "semantic_edge_count": self.semantic_edge_count,
            "finalized": self.finalized,
            "version_id": self.version_id,
            "previous_version_id": self.previous_version_id,
        }

    @classmethod
    def from_dict(cls: type["Manifest"], data: dict[str, object]) -> "Manifest":
        """Deserialize manifest from dictionary."""
        from typing import cast

        return cls(
            version=cast(str, data["version"]),
            created_at=cast(int, data["created_at"]),
            updated_at=cast(int, data["updated_at"]),
            node_count=cast(int, data["node_count"]),
            edge_count=cast(int, data["edge_count"]),
            file_hashes=cast(dict[str, str], data["file_hashes"]),
            edges_filename=cast(str, data["files"]["edges"]),
            sparse_index_filename=cast(
                str, data["files"].get("sparse_index", data["files"].get("vectors"))
            ),  # Fallback for migration
            semantic_edge_count=cast(
                int, data.get("semantic_edge_count", data.get("lexical_edge_count", 0))
            ),  # Fallback
            finalized=cast(bool, data.get("finalized", False)),
            version_id=cast(str, data.get("version_id", "v1")),
            previous_version_id=cast(str | None, data.get("previous_version_id")),
        )

    @classmethod
    def create_new(
        cls: type["Manifest"],
        edges_filename: str,
        sparse_index_filename: str,
        version: str = "1.0.0",
        created_at: int | None = None,
    ) -> "Manifest":
        """Create a new manifest with default values.

        Args:
        ----
            edges_filename: Filename for the edges data
            sparse_index_filename: Filename for the sparse index data
            version: Schema version (default: "1.0.0")
            created_at: Unix timestamp of initial creation (default: current time)

        Returns:
        -------
            New manifest instance

        """
        now = int(time.time())
        return cls(
            version=version,
            created_at=created_at or now,
            updated_at=now,
            node_count=0,
            edge_count=0,
            file_hashes={},
            edges_filename=edges_filename,
            sparse_index_filename=sparse_index_filename,
        )


@contextmanager
def acquire_manifest_lock(graph_store_path: Path, timeout: float = 30.0) -> Iterator[None]:
    """Acquire exclusive lock on manifest file for concurrent update safety.

    Uses a lock file to prevent concurrent modifications. Implements timeout
    with exponential backoff for lock acquisition.

    Args:
    ----
        graph_store_path: Root graph storage directory
        timeout: Maximum seconds to wait for lock (default: 30.0)

    Yields:
    ------
        None when lock is acquired

    Raises:
    ------
        StorageError: If lock cannot be acquired within timeout

    """
    metadata_dir = graph_store_path / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    lock_file = metadata_dir / "manifest.lock"
    start_time = time.time()
    backoff = 0.1  # Start with 100ms backoff

    # Try to acquire lock
    while True:
        try:
            # Create lock file with exclusive access (fails if exists)
            lock_file.touch(exist_ok=False)
            break
        except FileExistsError:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise StorageError(
                    f"Failed to acquire manifest lock within {timeout}s timeout",
                    {"lock_file": str(lock_file)},
                )
            time.sleep(backoff)
            backoff = min(backoff * 2, 1.0)  # Exponential backoff, max 1s

    try:
        yield
    finally:
        # Always release lock
        if lock_file.exists():
            lock_file.unlink()


def write_manifest(manifest: Manifest, graph_store_path: Path) -> None:
    """Write manifest to JSON file with exclusive locking and automatic backup.

    Uses file locking to ensure thread-safe concurrent updates.
    Creates timestamped backup before writing to prevent data loss.

    File location: {graph_store_path}/metadata/manifest.json
    Backups: {graph_store_path}/metadata/backups/manifest.*.backup

    Args:
    ----
        manifest: Manifest to write
        graph_store_path: Root graph storage directory

    Raises:
    ------
        StorageError: If write operation fails

    """
    # Import here to avoid circular dependency
    from knowgraph.infrastructure.storage.manifest_backup import ManifestBackupManager
    from knowgraph.infrastructure.storage.version_history import VersionHistoryManager

    with acquire_manifest_lock(graph_store_path):
        metadata_dir = graph_store_path / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)

        manifest_file = metadata_dir / "manifest.json"

        # Read existing manifest for version tracking
        existing_manifest = None
        if manifest_file.exists():
            try:
                existing_manifest = read_manifest(graph_store_path)
            except Exception:
                pass  # If read fails, treat as new

        # Auto-increment version if file hashes changed
        if existing_manifest:
            # Check if this is an actual update (file hashes changed)
            if existing_manifest.file_hashes != manifest.file_hashes:
                # Increment version
                current_version_num = int(existing_manifest.version_id.lstrip("v"))
                manifest.version_id = f"v{current_version_num + 1}"
                manifest.previous_version_id = existing_manifest.version_id
            else:
                # No changes, keep same version
                manifest.version_id = existing_manifest.version_id
                manifest.previous_version_id = existing_manifest.previous_version_id

        # Create backup before writing (only if manifest exists)
        if manifest_file.exists():
            try:
                backup_mgr = ManifestBackupManager(metadata_dir)
                backup_path = backup_mgr.backup_manifest(max_backups=5)
                if backup_path:
                    logger.debug(f"Created manifest backup: {backup_path}")
            except Exception as backup_error:
                # Log but don't fail the write operation
                logger.warning(f"Failed to create manifest backup: {backup_error}")

        temp_file = manifest_file.with_suffix(".tmp")

        try:
            with open(temp_file, "w", encoding="utf-8") as file:
                json.dump(manifest.to_dict(), file, indent=2, ensure_ascii=False)
            temp_file.rename(manifest_file)

            # Create version snapshot in history (only if file hashes actually changed)
            if existing_manifest is None or existing_manifest.file_hashes != manifest.file_hashes:
                try:
                    version_mgr = VersionHistoryManager(graph_store_path)
                    version_mgr.add_version(
                        node_count=manifest.node_count,
                        edge_count=manifest.edge_count,
                        file_hashes=manifest.file_hashes,
                        previous_file_hashes=(
                            existing_manifest.file_hashes if existing_manifest else {}
                        ),
                        metadata={"finalized": manifest.finalized},
                    )
                    logger.info(f"Created version snapshot: {manifest.version_id}")
                except Exception as version_error:
                    # Log but don't fail the write operation
                    logger.warning(f"Failed to create version snapshot: {version_error}")

            # Trigger cache invalidation after successful manifest update
            invalidate_all_caches()
        except Exception as error:
            if temp_file.exists():
                temp_file.unlink()
            raise StorageError(
                "Failed to write manifest",
                {"error": str(error), "path": str(manifest_file)},
            ) from error


def read_manifest(graph_store_path: Path) -> Manifest | None:
    """Read manifest from JSON file with automatic backup recovery.

    If the manifest file is corrupted, automatically attempts to restore
    from the latest backup.

    Args:
    ----
        graph_store_path: Root graph storage directory

    Returns:
    -------
        Manifest object or None if not found

    Raises:
    ------
        StorageError: If read operation fails (excluding not found)

    """
    # Import here to avoid circular dependency
    from knowgraph.infrastructure.storage.manifest_backup import ManifestBackupManager

    manifest_file = graph_store_path / "metadata" / "manifest.json"

    if not manifest_file.exists():
        return None

    try:
        with open(manifest_file, encoding="utf-8") as file:
            data = json.load(file)
        return Manifest.from_dict(data)
    except (json.JSONDecodeError, KeyError, ValueError) as error:
        # Manifest is corrupted, try to restore from backup
        logger.error(f"Manifest corrupted: {error}. Attempting recovery from backup...")

        try:
            backup_mgr = ManifestBackupManager(graph_store_path / "metadata")
            if backup_mgr.restore_latest_backup():
                logger.info("Successfully restored manifest from backup")
                # Try reading again
                with open(manifest_file, encoding="utf-8") as file:
                    data = json.load(file)
                return Manifest.from_dict(data)
            else:
                raise StorageError(
                    "Failed to restore manifest from backup (no backups available)",
                    {"error": str(error), "path": str(manifest_file)},
                ) from error
        except Exception as recovery_error:
            raise StorageError(
                "Failed to read and recover manifest",
                {
                    "original_error": str(error),
                    "recovery_error": str(recovery_error),
                    "path": str(manifest_file),
                },
            ) from recovery_error
    except Exception as error:
        # Other errors (permission, IO, etc.)
        raise StorageError(
            "Failed to read manifest",
            {"error": str(error), "path": str(manifest_file)},
        ) from error


def update_manifest_stats(manifest: Manifest, node_count: int, edge_count: int) -> Manifest:
    """Update manifest with new node and edge counts.

    Args:
    ----
        manifest: Existing manifest
        node_count: New node count
        edge_count: New edge count

    Returns:
    -------
        Updated manifest (new instance, original unchanged)

    """
    return Manifest(
        version=manifest.version,
        created_at=manifest.created_at,
        updated_at=int(time.time()),
        node_count=node_count,
        edge_count=edge_count,
        file_hashes=manifest.file_hashes,
        edges_filename=manifest.edges_filename,
        sparse_index_filename=manifest.sparse_index_filename,
        semantic_edge_count=manifest.semantic_edge_count,
    )

"""Version history tracking and management for knowledge graphs."""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FileChangeSummary:
    """Summary of file changes in a version."""

    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        """Total number of file changes."""
        return len(self.added) + len(self.modified) + len(self.deleted)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "added": self.added,
            "modified": self.modified,
            "deleted": self.deleted,
            "total_changes": self.total_changes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FileChangeSummary":
        """Deserialize from dictionary."""
        return cls(
            added=data.get("added", []),
            modified=data.get("modified", []),
            deleted=data.get("deleted", []),
        )


@dataclass
class VersionSnapshot:
    """Single version snapshot in graph history."""

    version_id: str
    timestamp: int
    created_at_iso: str
    node_count: int
    edge_count: int
    file_count: int
    file_changes: FileChangeSummary
    manifest_hash: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "version_id": self.version_id,
            "timestamp": self.timestamp,
            "created_at_iso": self.created_at_iso,
            "node_count": self.node_count,
            "edge_count": self.edge_count,
            "file_count": self.file_count,
            "file_changes": self.file_changes.to_dict(),
            "manifest_hash": self.manifest_hash,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VersionSnapshot":
        """Deserialize from dictionary."""
        return cls(
            version_id=data["version_id"],
            timestamp=data["timestamp"],
            created_at_iso=data["created_at_iso"],
            node_count=data["node_count"],
            edge_count=data["edge_count"],
            file_count=data["file_count"],
            file_changes=FileChangeSummary.from_dict(data["file_changes"]),
            manifest_hash=data["manifest_hash"],
            metadata=data.get("metadata", {}),
        )


class VersionHistoryManager:
    """Manages version history for knowledge graph."""

    def __init__(self, graph_store_path: Path):
        """Initialize version history manager.

        Args:
            graph_store_path: Root graph storage directory
        """
        self.graph_store_path = Path(graph_store_path)
        self.metadata_dir = self.graph_store_path / "metadata"
        self.versions_file = self.metadata_dir / "versions.jsonl"
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        """Ensure version storage directory and file exist."""
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        if not self.versions_file.exists():
            self.versions_file.touch()

    def add_version(
        self,
        node_count: int,
        edge_count: int,
        file_hashes: dict[str, str],
        previous_file_hashes: dict[str, str] | None = None,
        metadata: dict | None = None,
    ) -> VersionSnapshot:
        """Add a new version to history.

        Args:
            node_count: Number of nodes in this version
            edge_count: Number of edges in this version
            file_hashes: Current file hash mapping
            previous_file_hashes: Previous version's file hashes (for diff)
            metadata: Optional metadata (tags, notes, etc.)

        Returns:
            Created version snapshot
        """
        # Generate version ID
        current_versions = self.list_versions(limit=1)
        if current_versions:
            last_version = current_versions[0]
            version_num = int(last_version.version_id.lstrip("v")) + 1
        else:
            version_num = 1
        version_id = f"v{version_num}"

        # Calculate file changes
        file_changes = self._calculate_file_changes(file_hashes, previous_file_hashes or {})

        # Create manifest hash for quick comparison
        manifest_hash = self._hash_file_dict(file_hashes)

        # Create snapshot
        timestamp = int(time.time())
        snapshot = VersionSnapshot(
            version_id=version_id,
            timestamp=timestamp,
            created_at_iso=datetime.fromtimestamp(timestamp).isoformat(),
            node_count=node_count,
            edge_count=edge_count,
            file_count=len(file_hashes),
            file_changes=file_changes,
            manifest_hash=manifest_hash,
            metadata=metadata or {},
        )

        # Append to versions file
        with open(self.versions_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(snapshot.to_dict()) + "\n")

        logger.info(f"Created version {version_id} with {file_changes.total_changes} file changes")
        return snapshot

    def get_version(self, version_id: str) -> VersionSnapshot | None:
        """Get specific version by ID.

        Args:
            version_id: Version identifier (e.g., "v1", "v2")

        Returns:
            Version snapshot or None if not found
        """
        if not self.versions_file.exists():
            return None

        with open(self.versions_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                if data["version_id"] == version_id:
                    return VersionSnapshot.from_dict(data)
        return None

    def list_versions(self, limit: int = 50) -> list[VersionSnapshot]:
        """List versions in reverse chronological order.

        Args:
            limit: Maximum number of versions to return

        Returns:
            List of version snapshots (newest first)
        """
        if not self.versions_file.exists():
            return []

        versions = []
        with open(self.versions_file, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                versions.append(VersionSnapshot.from_dict(json.loads(line)))

        # Reverse to get newest first
        versions.reverse()
        return versions[:limit]

    def _calculate_file_changes(
        self, current_hashes: dict[str, str], previous_hashes: dict[str, str]
    ) -> FileChangeSummary:
        """Calculate file changes between versions.

        Args:
            current_hashes: Current file hash mapping
            previous_hashes: Previous file hash mapping

        Returns:
            File change summary
        """
        current_files = set(current_hashes.keys())
        previous_files = set(previous_hashes.keys())

        added = list(current_files - previous_files)
        deleted = list(previous_files - current_files)
        modified = [
            f for f in current_files & previous_files if current_hashes[f] != previous_hashes[f]
        ]

        return FileChangeSummary(
            added=sorted(added), modified=sorted(modified), deleted=sorted(deleted)
        )

    def _hash_file_dict(self, file_hashes: dict[str, str]) -> str:
        """Create hash of file_hashes dictionary for quick manifest comparison.

        Args:
            file_hashes: File hash mapping

        Returns:
            SHA-256 hash of the dictionary
        """
        # Sort keys for deterministic hashing
        sorted_items = sorted(file_hashes.items())
        content = json.dumps(sorted_items, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]  # First 16 chars

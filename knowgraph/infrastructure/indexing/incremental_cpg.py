"""Incremental CPG update module for efficient re-indexing.

Only regenerates CPG for changed files instead of entire codebase.
"""

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class IncrementalCPGUpdater:
    """Manage incremental CPG updates for changed files."""

    def __init__(self, graph_path: Path):
        """Initialize incremental updater.

        Args:
            graph_path: Path to graph storage
        """
        self.graph_path = graph_path
        self.metadata_dir = graph_path / "metadata"
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        self.file_hashes_path = self.metadata_dir / "file_hashes.json"

    def get_file_hash(self, file_path: Path) -> str:
        """Calculate hash of file content.

        Args:
            file_path: Path to file

        Returns:
            MD5 hash of file content
        """
        try:
            content = file_path.read_bytes()
            return hashlib.md5(content).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to hash {file_path}: {e}")
            return ""

    def load_file_hashes(self) -> dict:
        """Load previously stored file hashes.

        Returns:
            Dictionary of file_path -> hash
        """
        if not self.file_hashes_path.exists():
            return {}

        try:
            with open(self.file_hashes_path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load file hashes: {e}")
            return {}

    def save_file_hashes(self, hashes: dict):
        """Save file hashes to metadata.

        Args:
            hashes: Dictionary of file_path -> hash
        """
        try:
            with open(self.file_hashes_path, "w") as f:
                json.dump(hashes, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save file hashes: {e}")

    def detect_changes(self, code_files: list) -> dict:
        """Detect which files have changed since last index.

        Args:
            code_files: List of CodeFile objects or Path objects

        Returns:
            Dictionary with 'added', 'modified', 'deleted', 'unchanged' lists
        """
        old_hashes = self.load_file_hashes()
        new_hashes = {}

        changes = {
            "added": [],
            "modified": [],
            "deleted": [],
            "unchanged": []
        }

        # Check current files
        for code_file in code_files:
            # Handle both CodeFile objects and Path objects
            if hasattr(code_file, "path"):
                file_path = code_file.path
            else:
                file_path = code_file

            file_str = str(file_path)
            new_hash = self.get_file_hash(file_path)
            new_hashes[file_str] = new_hash

            if file_str not in old_hashes:
                changes["added"].append(file_path)
            elif old_hashes[file_str] != new_hash:
                changes["modified"].append(file_path)
            else:
                changes["unchanged"].append(file_path)

        # Check for deleted files
        for old_file in old_hashes:
            if old_file not in new_hashes:
                changes["deleted"].append(Path(old_file))

        # Save new hashes
        self.save_file_hashes(new_hashes)

        return changes

    def should_regenerate_cpg(self, changes: dict) -> bool:
        """Determine if CPG should be regenerated.

        Args:
            changes: Changes dictionary from detect_changes

        Returns:
            True if CPG regeneration needed
        """
        # Regenerate if any files added, modified, or deleted
        return (
            len(changes["added"]) > 0 or
            len(changes["modified"]) > 0 or
            len(changes["deleted"]) > 0
        )

    def get_change_summary(self, changes: dict) -> str:
        """Get human-readable summary of changes.

        Args:
            changes: Changes dictionary

        Returns:
            Summary string
        """
        summary = []

        if changes["added"]:
            summary.append(f"{len(changes['added'])} added")
        if changes["modified"]:
            summary.append(f"{len(changes['modified'])} modified")
        if changes["deleted"]:
            summary.append(f"{len(changes['deleted'])} deleted")
        if changes["unchanged"]:
            summary.append(f"{len(changes['unchanged'])} unchanged")

        return ", ".join(summary) if summary else "no changes"

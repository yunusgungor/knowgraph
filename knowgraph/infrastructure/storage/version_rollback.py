"""Version rollback management for knowledge graphs."""

import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from knowgraph.infrastructure.storage.manifest import Manifest, read_manifest, write_manifest
from knowgraph.infrastructure.storage.version_history import VersionHistoryManager

logger = logging.getLogger(__name__)


@dataclass
class RollbackResult:
    """Result of a rollback operation."""

    success: bool
    from_version: str
    to_version: str
    backup_path: Path | None
    message: str
    errors: list[str]

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "success": self.success,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "backup_path": str(self.backup_path) if self.backup_path else None,
            "message": self.message,
            "errors": self.errors,
        }


class RollbackManager:
    """Manages version rollback operations."""

    def __init__(self, graph_store_path: Path):
        """Initialize rollback manager.

        Args:
            graph_store_path: Root graph storage directory
        """
        self.graph_store_path = Path(graph_store_path)
        self.metadata_dir = self.graph_store_path / "metadata"
        self.version_mgr = VersionHistoryManager(graph_store_path)

    def rollback_to_version(
        self,
        target_version_id: str,
        create_backup: bool = True,
        force: bool = False,
    ) -> RollbackResult:
        """Rollback manifest to a previous version.

        This performs a MANIFEST-ONLY rollback:
        - Updates manifest to target version's metadata
        - Does NOT restore actual node/edge files
        - Creates backup of current state
        - User needs to re-index to fully restore

        Args:
            target_version_id: Version to rollback to (e.g., "v3")
            create_backup: Whether to create backup before rollback
            force: Skip validation checks

        Returns:
            RollbackResult with operation details
        """
        errors = []

        try:
            # 1. Load current manifest
            current_manifest = read_manifest(self.graph_store_path)
            if not current_manifest:
                return RollbackResult(
                    success=False,
                    from_version="unknown",
                    to_version=target_version_id,
                    backup_path=None,
                    message="No manifest found in graph store",
                    errors=["Graph store not initialized"],
                )

            current_version = current_manifest.version_id

            # 2. Load target version
            target_snapshot = self.version_mgr.get_version(target_version_id)
            if not target_snapshot:
                return RollbackResult(
                    success=False,
                    from_version=current_version,
                    to_version=target_version_id,
                    backup_path=None,
                    message=f"Version '{target_version_id}' not found",
                    errors=[f"No version snapshot for {target_version_id}"],
                )

            # 3. Validation (unless forced)
            if not force:
                validation_errors = self._validate_rollback(current_manifest, target_snapshot)
                if validation_errors:
                    return RollbackResult(
                        success=False,
                        from_version=current_version,
                        to_version=target_version_id,
                        backup_path=None,
                        message="Rollback validation failed",
                        errors=validation_errors,
                    )

            # 4. Create backup
            backup_path = None
            if create_backup:
                try:
                    backup_path = self._create_rollback_backup(current_version)
                    logger.info(f"Created rollback backup at {backup_path}")
                except Exception as e:
                    errors.append(f"Backup creation warning: {e}")
                    # Continue anyway if backup fails

            # 5. Update manifest to target version
            # Note: We keep file_hashes from current manifest since we're not restoring files
            # This is a metadata-only rollback
            rollback_manifest = Manifest(
                version=current_manifest.version,
                node_count=target_snapshot.node_count,
                edge_count=target_snapshot.edge_count,
                file_hashes=current_manifest.file_hashes,  # Keep current files
                edges_filename=current_manifest.edges_filename,
                sparse_index_filename=current_manifest.sparse_index_filename,
                created_at=current_manifest.created_at,
                updated_at=int(time.time()),
                semantic_edge_count=target_snapshot.edge_count,
                finalized=True,
                version_id=f"{target_version_id}-rollback",
                previous_version_id=current_version,
            )

            # 6. Write updated manifest
            write_manifest(rollback_manifest, self.graph_store_path)

            logger.info(
                f"Rolled back from {current_version} to {target_version_id} "
                f"(manifest metadata only)"
            )

            return RollbackResult(
                success=True,
                from_version=current_version,
                to_version=target_version_id,
                backup_path=backup_path,
                message=(
                    f"Successfully rolled back manifest from {current_version} to {target_version_id}. "
                    "Note: This is a metadata-only rollback. "
                    "Re-run 'knowgraph index' to restore actual files."
                ),
                errors=errors,
            )

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return RollbackResult(
                success=False,
                from_version=current_version if "current_version" in locals() else "unknown",
                to_version=target_version_id,
                backup_path=None,
                message=f"Rollback failed: {e}",
                errors=[str(e)],
            )

    def _validate_rollback(self, current_manifest: Manifest, target_snapshot) -> list[str]:
        """Validate rollback operation.

        Args:
            current_manifest: Current manifest
            target_snapshot: Target version snapshot

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check if rolling back to same version
        if current_manifest.version_id == target_snapshot.version_id:
            errors.append("Already at target version")

        # Check if target version is newer (shouldn't rollback forward)
        current_num = int(current_manifest.version_id.lstrip("v").split("-")[0])
        target_num = int(target_snapshot.version_id.lstrip("v"))
        if target_num >= current_num:
            errors.append(
                f"Cannot rollback to newer or equal version "
                f"({target_snapshot.version_id} >= {current_manifest.version_id})"
            )

        return errors

    def _create_rollback_backup(self, current_version: str) -> Path:
        """Create backup before rollback.

        Args:
            current_version: Current version ID

        Returns:
            Path to backup directory
        """
        from datetime import datetime

        # Create backups directory
        backups_dir = self.metadata_dir / "rollback_backups"
        backups_dir.mkdir(exist_ok=True)

        # Create timestamped backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"pre_rollback_{current_version}_{timestamp}"
        backup_path = backups_dir / backup_name

        # Copy manifest
        manifest_file = self.metadata_dir / "manifest.json"
        if manifest_file.exists():
            backup_path.mkdir()
            shutil.copy2(manifest_file, backup_path / "manifest.json")

            # Also backup versions.jsonl
            versions_file = self.metadata_dir / "versions.jsonl"
            if versions_file.exists():
                shutil.copy2(versions_file, backup_path / "versions.jsonl")

        return backup_path

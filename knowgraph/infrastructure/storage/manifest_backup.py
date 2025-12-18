"""Manifest backup and recovery management."""

import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ManifestBackupManager:
    """Manages manifest.json backups for disaster recovery."""

    def __init__(self, manifest_dir: Path):
        """Initialize backup manager.

        Args:
            manifest_dir: Directory containing manifest.json (typically graphstore/metadata)
        """
        self.manifest_dir = Path(manifest_dir)
        self.manifest_path = self.manifest_dir / "manifest.json"
        self.backup_dir = self.manifest_dir / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup_manifest(self, max_backups: int = 5) -> Path | None:
        """Create timestamped backup of manifest.json.

        Args:
            max_backups: Maximum number of backups to keep (default: 5)

        Returns:
            Path to created backup, or None if manifest doesn't exist
        """
        if not self.manifest_path.exists():
            logger.warning(f"Manifest not found at {self.manifest_path}, skipping backup")
            return None

        try:
            # Create timestamped backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_path = self.backup_dir / f"manifest.{timestamp}.backup"

            shutil.copy2(self.manifest_path, backup_path)
            logger.info(f"Manifest backed up to {backup_path}")

            # Prune old backups
            self._prune_old_backups(max_backups)

            return backup_path
        except Exception as e:
            logger.error(f"Failed to backup manifest: {e}")
            return None

    def restore_latest_backup(self) -> bool:
        """Restore manifest.json from latest backup.

        Returns:
            True if restore successful, False otherwise
        """
        backups = self._list_backups()
        if not backups:
            logger.error("No backups available to restore")
            return False

        try:
            latest_backup = backups[0]  # Already sorted newest first
            logger.info(f"Restoring manifest from {latest_backup}")

            # Backup current (potentially corrupted) manifest
            if self.manifest_path.exists():
                corrupted_path = self.manifest_path.with_suffix(".json.corrupted")
                shutil.copy2(self.manifest_path, corrupted_path)
                logger.info(f"Corrupted manifest saved to {corrupted_path}")

            # Restore from backup
            shutil.copy2(latest_backup, self.manifest_path)
            logger.info("Manifest restored successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to restore manifest: {e}")
            return False

    def restore_from_backup(self, backup_path: Path) -> bool:
        """Restore manifest.json from specific backup.

        Args:
            backup_path: Path to specific backup file

        Returns:
            True if restore successful, False otherwise
        """
        if not backup_path.exists():
            logger.error(f"Backup not found: {backup_path}")
            return False

        try:
            # Backup current manifest
            if self.manifest_path.exists():
                corrupted_path = self.manifest_path.with_suffix(".json.corrupted")
                shutil.copy2(self.manifest_path, corrupted_path)

            # Restore from specified backup
            shutil.copy2(backup_path, self.manifest_path)
            logger.info(f"Manifest restored from {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore from {backup_path}: {e}")
            return False

    def _list_backups(self) -> list[Path]:
        """List all backup files, sorted by modification time (newest first).

        Returns:
            List of backup file paths
        """
        if not self.backup_dir.exists():
            return []

        backups = list(self.backup_dir.glob("manifest.*.backup"))
        # Sort by name (which contains timestamp), newest first
        # We rely on name sort because mtime might be identical in fast tests
        backups.sort(key=lambda p: p.name, reverse=True)
        return backups

    def _prune_old_backups(self, max_backups: int) -> None:
        """Remove old backups, keeping only max_backups most recent.

        Args:
            max_backups: Maximum number of backups to retain
        """
        backups = self._list_backups()
        if len(backups) <= max_backups:
            return

        # Remove oldest backups
        for old_backup in backups[max_backups:]:
            try:
                old_backup.unlink()
                logger.debug(f"Pruned old backup: {old_backup}")
            except Exception as e:
                logger.warning(f"Failed to prune backup {old_backup}: {e}")

    def get_backup_stats(self) -> dict:
        """Get statistics about available backups.

        Returns:
            Dictionary with backup information
        """
        backups = self._list_backups()

        if not backups:
            return {
                "backup_count": 0,
                "latest_backup": None,
                "total_size_mb": 0.0,
            }

        total_size = sum(b.stat().st_size for b in backups)

        return {
            "backup_count": len(backups),
            "latest_backup": str(backups[0]),
            "latest_backup_time": datetime.fromtimestamp(backups[0].stat().st_mtime).isoformat(),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "backups": [str(b) for b in backups],
        }

"""Cache Manager for storing and retrieving analysis results."""

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

from knowgraph.domain.intelligence.provider import Entity

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages persistent caching of analysis results using SQLite."""

    def __init__(self, cache_dir: str = ".knowgraph_cache"):
        """Initialize cache manager."""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "analysis_cache.db"
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            # Enable WAL mode for better concurrency
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn  # type: ignore[no-any-return]

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS entities (
                    chunk_hash TEXT PRIMARY KEY,
                    data JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entities_hash ON entities(chunk_hash)")

    def get_entities(self, chunk_hash: str) -> list[Entity] | None:
        """Retrieve entities for a chunk hash if they exist."""
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM entities WHERE chunk_hash = ?", (chunk_hash,))
            row = cursor.fetchone()
            if row:
                data = json.loads(row[0])
                return [Entity(**item) for item in data]
            return None
        except Exception:
            return None

    def save_entities(self, chunk_hash: str, entities: list[Entity]) -> None:
        """Save entities for a chunk hash."""
        try:
            conn = self._get_conn()
            data = json.dumps([e._asdict() for e in entities])
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO entities (chunk_hash, data)
                    VALUES (?, ?)
                    """,
                    (chunk_hash, data),
                )
        except Exception:
            pass

    def check_integrity(self) -> bool:
        """Check SQLite database integrity.

        Returns:
            True if database is healthy, False if corrupted.
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            result = cursor.fetchone()
            return result is not None and result[0] == "ok"
        except Exception as e:
            logger.error(f"Cache integrity check failed: {e}")
            return False

    def rebuild_cache_if_corrupted(self) -> None:
        """Auto-rebuild corrupted cache database."""
        if not self.check_integrity():
            logger.warning("Cache corrupted, rebuilding...")
            try:
                # Close all connections
                if hasattr(self._local, "conn"):
                    self._local.conn.close()
                    delattr(self._local, "conn")

                # Backup corrupted DB (for debugging)
                if self.db_path.exists():
                    backup_path = self.db_path.with_suffix(".db.corrupted")
                    self.db_path.rename(backup_path)
                    logger.info(f"Corrupted cache backed up to {backup_path}")

                # Reinitialize
                self._init_db()
                logger.info("Cache rebuilt successfully")
            except Exception as e:
                logger.error(f"Failed to rebuild cache: {e}")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache size, entry count, and health status.
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            # Count entries
            cursor.execute("SELECT COUNT(*) FROM entities")
            entry_count = cursor.fetchone()[0]

            # Database size
            db_size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
            db_size_mb = db_size_bytes / (1024 * 1024)

            # Health check
            is_healthy = self.check_integrity()

            return {
                "entry_count": entry_count,
                "size_mb": round(db_size_mb, 2),
                "size_bytes": db_size_bytes,
                "is_healthy": is_healthy,
                "db_path": str(self.db_path),
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "entry_count": 0,
                "size_mb": 0.0,
                "size_bytes": 0,
                "is_healthy": False,
                "error": str(e),
            }

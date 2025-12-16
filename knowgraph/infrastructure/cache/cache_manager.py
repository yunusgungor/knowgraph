"""Cache Manager for storing and retrieving analysis results."""

import json
import sqlite3
import threading
from pathlib import Path

from knowgraph.domain.intelligence.provider import Entity


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

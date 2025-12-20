"""Cache versioning and invalidation system.

Provides automatic cache invalidation based on graph version changes,
TTL-based expiration, and event-driven cache refresh mechanisms.
"""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CacheVersion:
    """Cache version metadata.

    Attributes
    ----------
        graph_version: Version from manifest (updated_at timestamp)
        cache_created_at: When this cache entry was created
        ttl: Time-to-live in seconds (None = no expiration)
        cache_key: Unique identifier for this cache entry
    """

    graph_version: int
    cache_created_at: int
    ttl: int | None = None
    cache_key: str | None = None

    def is_valid(self, current_graph_version: int) -> bool:
        """Check if cache is still valid.

        Args:
        ----
            current_graph_version: Current graph version from manifest

        Returns:
        -------
            True if cache is valid, False if invalidated
        """
        # Check version mismatch
        if self.graph_version != current_graph_version:
            return False

        # Check TTL expiration
        if self.ttl is not None:
            age = int(time.time()) - self.cache_created_at
            if age > self.ttl:
                return False

        return True


class CacheVersionManager:
    """Manages cache versioning and invalidation.

    Tracks graph version and automatically invalidates caches when
    the graph is updated.
    """

    def __init__(self, graph_store_path: Path):
        """Initialize cache version manager.

        Args:
        ----
            graph_store_path: Path to graph storage
        """
        self.graph_store_path = Path(graph_store_path)
        self._current_version: int | None = None
        self._version_last_checked: int = 0
        self._version_check_interval: int = 5  # Check version every 5 seconds

    def get_current_version(self) -> int:
        """Get current graph version from manifest.

        Returns:
        -------
            Unix timestamp of last graph update
        """
        # Cache version for a few seconds to avoid repeated file I/O
        now = int(time.time())
        if (
            self._current_version is not None
            and (now - self._version_last_checked) < self._version_check_interval
        ):
            return int(self._current_version)

        manifest_path = self.graph_store_path / "metadata" / "manifest.json"

        if not manifest_path.exists():
            # No manifest yet, use current time
            self._current_version = now
            self._version_last_checked = now
            return self._current_version

        try:
            import json

            with open(manifest_path, encoding="utf-8") as f:
                data = json.load(f)

            self._current_version = data.get("updated_at", now)
            self._version_last_checked = now
            return int(self._current_version)

        except Exception:
            # Fallback to current time
            self._current_version = now
            self._version_last_checked = now
            return int(self._current_version)

    def create_cache_version(
        self, cache_key: str | None = None, ttl: int | None = None
    ) -> CacheVersion:
        """Create a new cache version entry.

        Args:
        ----
            cache_key: Optional unique identifier for cache entry
            ttl: Optional time-to-live in seconds

        Returns:
        -------
            CacheVersion object
        """
        return CacheVersion(
            graph_version=self.get_current_version(),
            cache_created_at=int(time.time()),
            ttl=ttl,
            cache_key=cache_key,
        )

    def is_cache_valid(self, cache_version: CacheVersion) -> bool:
        """Check if a cache entry is still valid.

        Args:
        ----
            cache_version: Cache version to validate

        Returns:
        -------
            True if valid, False if invalidated
        """
        return cache_version.is_valid(self.get_current_version())

    def invalidate_on_update(self) -> None:
        """Force version refresh (call after graph updates).

        This should be called after any graph modification to ensure
        caches are invalidated immediately.
        """
        self._current_version = None
        self._version_last_checked = 0


# Global cache storage with versioning
_versioned_cache: dict[str, tuple[Any, CacheVersion]] = {}
_cache_manager: CacheVersionManager | None = None


def initialize_cache_manager(graph_store_path: Path) -> None:
    """Initialize the global cache manager.

    Args:
    ----
        graph_store_path: Path to graph storage
    """
    global _cache_manager
    _cache_manager = CacheVersionManager(graph_store_path)


def set_cached(
    key: str, value: Any, ttl: int | None = None, graph_store_path: Path | None = None
) -> None:
    """Store a value in versioned cache.

    Args:
    ----
        key: Cache key
        value: Value to cache
        ttl: Optional time-to-live in seconds
        graph_store_path: Optional path to graph storage (for version tracking)
    """
    global _cache_manager

    if _cache_manager is None and graph_store_path is not None:
        initialize_cache_manager(graph_store_path)

    if _cache_manager is not None:
        cache_version = _cache_manager.create_cache_version(cache_key=key, ttl=ttl)
    else:
        # Fallback: no version tracking
        cache_version = CacheVersion(
            graph_version=int(time.time()),
            cache_created_at=int(time.time()),
            ttl=ttl,
            cache_key=key,
        )

    _versioned_cache[key] = (value, cache_version)


def get_cached(key: str, default: Any = None) -> Any:
    """Get a value from versioned cache.

    Automatically checks validity and returns default if invalid/missing.

    Args:
    ----
        key: Cache key
        default: Default value if not found or invalid

    Returns:
    -------
        Cached value or default
    """
    if key not in _versioned_cache:
        return default

    value, cache_version = _versioned_cache[key]

    # Check validity
    if _cache_manager is not None:
        if not _cache_manager.is_cache_valid(cache_version):
            # Invalidate and remove
            del _versioned_cache[key]
            return default
    else:
        # Fallback: just check TTL
        if not cache_version.is_valid(cache_version.graph_version):
            del _versioned_cache[key]
            return default

    return value


def invalidate_cache(key: str | None = None) -> None:
    """Invalidate cache entries.

    Args:
    ----
        key: Specific key to invalidate (None = clear all)
    """
    if key is None:
        _versioned_cache.clear()
    elif key in _versioned_cache:
        del _versioned_cache[key]


def invalidate_all_caches() -> None:
    """Invalidate all caches (graph update event)."""
    _versioned_cache.clear()

    # Also clear module-level caches
    from knowgraph.domain.algorithms.centrality import clear_centrality_cache
    from knowgraph.infrastructure.storage.filesystem import clear_node_cache

    clear_node_cache()
    clear_centrality_cache()

    # Force version refresh
    if _cache_manager is not None:
        _cache_manager.invalidate_on_update()


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics.

    Returns:
    -------
        Dictionary with cache statistics
    """
    valid_count = 0
    invalid_count = 0

    for _, (_, cache_version) in _versioned_cache.items():
        if _cache_manager is not None:
            if _cache_manager.is_cache_valid(cache_version):
                valid_count += 1
            else:
                invalid_count += 1
        else:
            valid_count += 1  # Can't validate without manager

    return {
        "total_entries": len(_versioned_cache),
        "valid_entries": valid_count,
        "invalid_entries": invalid_count,
        "graph_version": _cache_manager.get_current_version() if _cache_manager else None,
    }

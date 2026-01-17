"""CPG caching module for improved query performance.

Caches generated CPGs to avoid regeneration on subsequent queries.
"""

import hashlib
import logging
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class CPGCache:
    """Manage CPG file caching."""

    def __init__(self, cache_dir: Path | None = None):
        """Initialize CPG cache.

        Args:
            cache_dir: Directory for cached CPGs (default: ~/.knowgraph/cpg_cache)
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".knowgraph" / "cpg_cache"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"CPG cache initialized at {self.cache_dir}")

    def get_cache_key(self, source_path: Path) -> str:
        """Generate cache key for source directory.

        Args:
            source_path: Path to source code directory

        Returns:
            Cache key (hash of path + mtime)
        """
        # Use absolute path + last modified time
        abs_path = source_path.resolve()

        # Get latest modification time in directory
        try:
            latest_mtime = max(
                f.stat().st_mtime
                for f in abs_path.rglob("*")
                if f.is_file()
            )
        except ValueError:
            latest_mtime = 0

        # Create hash
        key_str = f"{abs_path}:{latest_mtime}"
        cache_key = hashlib.md5(key_str.encode()).hexdigest()

        return cache_key

    def get_cached_cpg(self, source_path: Path) -> Path | None:
        """Get cached CPG if available and valid.

        Args:
            source_path: Path to source code directory

        Returns:
            Path to cached CPG or None if not available
        """
        cache_key = self.get_cache_key(source_path)
        cached_cpg = self.cache_dir / f"{cache_key}.bin"

        if cached_cpg.exists():
            # Check if cache is still valid (< 24 hours old)
            cache_age = datetime.now().timestamp() - cached_cpg.stat().st_mtime

            if cache_age < 86400:  # 24 hours
                logger.info(f"Using cached CPG: {cached_cpg}")
                return cached_cpg
            else:
                logger.info("Cached CPG expired, will regenerate")
                cached_cpg.unlink()

        return None

    def cache_cpg(self, source_path: Path, cpg_path: Path) -> Path:
        """Cache a generated CPG.

        Args:
            source_path: Path to source code directory
            cpg_path: Path to generated CPG

        Returns:
            Path to cached CPG
        """
        cache_key = self.get_cache_key(source_path)
        cached_cpg = self.cache_dir / f"{cache_key}.bin"

        # Copy CPG to cache
        shutil.copy2(cpg_path, cached_cpg)

        logger.info(f"Cached CPG: {cached_cpg}")

        return cached_cpg

    def clear_cache(self, max_age_days: int = 7):
        """Clear old cached CPGs.

        Args:
            max_age_days: Remove CPGs older than this many days
        """
        cutoff = datetime.now().timestamp() - (max_age_days * 86400)

        removed = 0
        for cpg_file in self.cache_dir.glob("*.bin"):
            if cpg_file.stat().st_mtime < cutoff:
                cpg_file.unlink()
                removed += 1

        logger.info(f"Cleared {removed} old CPGs from cache")

        return removed

    def get_cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        cpg_files = list(self.cache_dir.glob("*.bin"))

        total_size = sum(f.stat().st_size for f in cpg_files)

        return {
            "cache_dir": str(self.cache_dir),
            "cached_cpgs": len(cpg_files),
            "total_size_mb": total_size / (1024 * 1024),
            "oldest": min((f.stat().st_mtime for f in cpg_files), default=0),
            "newest": max((f.stat().st_mtime for f in cpg_files), default=0)
        }

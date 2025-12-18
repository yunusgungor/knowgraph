"""Resource detection for auto-tuning based on system resources."""

import logging

logger = logging.getLogger(__name__)

# Try to import psutil, fallback to defaults if not available
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not installed, using default worker count")


class ResourceDetector:
    """Detects system resources and recommends optimal configuration."""

    @staticmethod
    def get_available_ram_gb() -> float:
        """Get available RAM in gigabytes.

        Returns:
            Available RAM in GB, or 8.0 if psutil not available.
        """
        if not PSUTIL_AVAILABLE:
            return 8.0  # Default assumption

        try:
            return psutil.virtual_memory().available / (1024**3)
        except Exception as e:
            logger.warning(f"Failed to detect RAM: {e}, using default")
            return 8.0

    @staticmethod
    def get_cpu_count() -> int:
        """Get number of CPU cores.

        Returns:
            Number of CPU cores, or 4 if detection fails.
        """
        if not PSUTIL_AVAILABLE:
            import os

            return os.cpu_count() or 4

        try:
            return psutil.cpu_count(logical=True) or 4
        except Exception:
            return 4

    @staticmethod
    def recommend_workers(max_workers: int = 20) -> int:
        """Recommend optimal worker count based on available RAM.

        Strategy:
        - <4GB RAM: 5 workers (conservative)
        - 4-8GB RAM: 10 workers
        - 8-16GB RAM: 15 workers
        - >16GB RAM: 20 workers (maximum)

        Args:
            max_workers: Maximum workers to recommend (default: 20)

        Returns:
            Recommended number of workers.
        """
        ram_gb = ResourceDetector.get_available_ram_gb()

        if ram_gb < 4:
            workers = 5
        elif ram_gb < 8:
            workers = 10
        elif ram_gb < 16:
            workers = 15
        else:
            workers = max_workers

        logger.info(f"Auto-detected {workers} workers based on {ram_gb:.1f}GB available RAM")
        return min(workers, max_workers)

    @staticmethod
    def recommend_batch_size(default: int = 15) -> int:
        """Recommend batch size for LLM requests based on RAM.

        Args:
            default: Default batch size

        Returns:
            Recommended batch size.
        """
        ram_gb = ResourceDetector.get_available_ram_gb()

        if ram_gb < 4:
            batch_size = 5
        elif ram_gb < 8:
            batch_size = 10
        else:
            batch_size = default

        return batch_size

    @staticmethod
    def get_system_info() -> dict:
        """Get comprehensive system information.

        Returns:
            Dictionary with system resource information.
        """
        if not PSUTIL_AVAILABLE:
            return {
                "available_ram_gb": 8.0,
                "cpu_count": 4,
                "psutil_available": False,
                "note": "Install psutil for accurate detection: pip install psutil",
            }

        try:
            memory = psutil.virtual_memory()
            return {
                "available_ram_gb": memory.available / (1024**3),
                "total_ram_gb": memory.total / (1024**3),
                "ram_percent_used": memory.percent,
                "cpu_count": psutil.cpu_count(logical=True),
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "psutil_available": True,
            }
        except Exception as e:
            return {"error": str(e), "psutil_available": True, "note": "Failed to get system info"}

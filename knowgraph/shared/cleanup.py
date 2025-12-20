"""Resource cleanup utilities for graceful shutdown.

Provides centralized cleanup functions for ProcessPoolExecutors and other resources.
"""


def cleanup_all_resources() -> None:
    """Manually cleanup all resources.

    Useful for explicit cleanup in tests or before application restart.
    """
    from knowgraph.application.querying.centrality_mp import shutdown_process_pool
    from knowgraph.domain.algorithms.centrality import _shutdown_process_pool
    from knowgraph.infrastructure.storage.filesystem import clear_node_cache

    # Shutdown process pools
    try:
        _shutdown_process_pool()
    except Exception:
        pass

    try:
        shutdown_process_pool()
    except Exception:
        pass

    # Clear caches
    try:
        clear_node_cache()
    except Exception:
        pass


# Auto-register cleanup handlers on module import
# This ensures cleanup happens even if user doesn't call anything
# Note: Individual modules also register via atexit for redundancy

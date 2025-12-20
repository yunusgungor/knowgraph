"""Static KnowGraph System - File-based Graph Retrieval-Augmented Generation.

A production-grade library for converting Git repositories into queryable
knowledge graphs with explainable reasoning paths.
"""

__version__ = "0.5.0"
__author__ = "Yunus Güngör"
__license__ = "MIT"

# Import cleanup utilities to ensure atexit handlers are registered
from knowgraph.shared.cleanup import cleanup_all_resources

# Public API will be defined as components are implemented
__all__: list[str] = ["cleanup_all_resources"]

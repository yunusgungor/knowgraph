"""Joern Integration Core Package.

This package provides core functionality for Joern integration, including:
- Installation and management (manager.py)
- CPG generation and analysis (provider.py)
- Daemon process management (process.py)
- Type definitions (types.py)
"""

from knowgraph.core.joern.manager import install_joern, verify_installation
from knowgraph.core.joern.process import JoernDaemon
from knowgraph.core.joern.provider import JoernNotFoundError, JoernProvider
from knowgraph.core.joern.types import ExportFormat, JoernCPG, JoernEntity

__all__ = [
    "ExportFormat",
    "JoernCPG",
    "JoernDaemon",
    "JoernEntity",
    "JoernNotFoundError",
    "JoernProvider",
    "install_joern",
    "verify_installation",
]

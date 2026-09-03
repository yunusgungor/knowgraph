"""Support ``python -m knowgraph`` as a PATH-independent entry point.

Mirrors the ``knowgraph`` console script so the CLI stays reachable even when
the Python ``Scripts`` directory is not on PATH (common on Windows after a
plain ``pip install``).
"""

from knowgraph.adapters.cli.main import cli

if __name__ == "__main__":
    cli()

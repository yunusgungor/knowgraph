"""Shared pytest fixtures and configuration for KnowGraph tests."""

from __future__ import annotations

import os
import shutil

import pytest

# Use the persistent Joern daemon (default true) so the test suite exercises
# the same code path as production and runs faster: --script pays a fresh JVM
# per query, while the daemon reuses one JVM across the whole pytest process.
# Set KNOWGRAPH_JOERN_DAEMON=false to force --script when needed.
os.environ.setdefault("KNOWGRAPH_JOERN_DAEMON", "true")

from knowgraph.core.joern.provider import JoernProvider


def joern_available() -> bool:
    """Return True when the Joern CLI binary is installed and usable."""
    try:
        JoernProvider()
        return True
    except Exception:
        return bool(shutil.which("joern")) or bool(shutil.which("joern-cli"))


requires_joern = pytest.mark.skipif(
    not joern_available(),
    reason="Joern CLI is not installed (run: knowgraph-setup-joern)",
)

"""Shared pytest fixtures and configuration for KnowGraph tests."""

from __future__ import annotations

import os
import shutil

import pytest

# Disable the persistent Joern daemon in the unit test suite. Each test file
# runs in its own subprocess in CI/pytest, so a daemon would pay the ~60s JVM
# boot per module. Executors fall back to one-shot --script, which is
# deterministic and fast enough. The daemon itself is exercised explicitly by
# tests/test_joern_daemon.py (which passes use_daemon=True explicitly).
os.environ.setdefault("KNOWGRAPH_JOERN_DAEMON", "false")

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

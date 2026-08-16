"""Shared pytest fixtures and configuration for KnowGraph tests."""

from __future__ import annotations

import shutil

import pytest

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

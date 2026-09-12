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

from knowgraph.config import (
    KnowGraphSettings,
    MemorySettings,
    PerformanceSettings,
    QuerySettings,
    get_settings,
)
from knowgraph.core.joern.provider import JoernProvider


# Experiment E-001 (docs/experiments/E-001.md): hermetic settings per test.
# pydantic-settings BaseSettings implicitly reads the repo-root `.env`
# (KNOWGRAPH_QUERY_TIMEOUT_SECONDS=30.0) plus ambient KNOWGRAPH_* vars, so
# default-asserting tests depended on cwd/env (30.0 from repo root, 60.0 from
# /tmp). This autouse fixture strips the settings namespaces and ignores
# `.env` per test. Override tests still pass: monkeypatch.setenv inside the
# test runs after this fixture, and real env vars are still read.
_HERMETIC_ENV_PREFIXES = ("KNOWGRAPH_PERF_", "KNOWGRAPH_MEMORY_", "KNOWGRAPH_QUERY_")
_HERMETIC_ENV_VARS = ("KNOWGRAPH_LOG_LEVEL", "KNOWGRAPH_GRAPH_STORE_PATH")


@pytest.fixture(autouse=True)
def _hermetic_settings(monkeypatch):
    for var in list(os.environ):
        if var.startswith(_HERMETIC_ENV_PREFIXES) or var in _HERMETIC_ENV_VARS:
            monkeypatch.delenv(var, raising=False)
    for cls in (PerformanceSettings, MemorySettings, QuerySettings, KnowGraphSettings):
        monkeypatch.setitem(cls.model_config, "env_file", os.devnull)
    get_settings.cache_clear()


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

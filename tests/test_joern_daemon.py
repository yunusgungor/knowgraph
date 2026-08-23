"""Tests for the persistent Joern daemon (single-JVM REPL).

Verifies that ``JoernQueryExecutor`` routes queries through a shared
``JoernDaemon`` when enabled, falls back to one-shot ``--script`` when
disabled, and that repeated queries on the same CPG reuse the loaded JVM.
"""

import os
import tempfile
import time
from pathlib import Path

import pytest
from conftest import requires_joern

pytestmark = requires_joern


@pytest.fixture(scope="module")
def sample_cpg():
    """Generate a small CPG once for the whole module."""
    tmp = Path(tempfile.mkdtemp(prefix="kg_daemon_test_"))
    src = tmp / "src"
    src.mkdir()
    (src / "a.py").write_text(
        "def foo(x):\n"
        "    return x + 1\n"
        "\n"
        "def bar():\n"
        "    return foo(2)\n"
    )
    from knowgraph.core.joern import JoernProvider

    cpg = JoernProvider().generate_cpg(src)
    yield cpg
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)


def test_daemon_execute_query_returns_results(sample_cpg):
    """Daemon mode returns a JoernQueryResult with parsed items."""
    from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

    ex = JoernQueryExecutor(use_daemon=True)
    result = ex.execute_query(
        sample_cpg, 'cpg.method.where(_.filename("a.py")).name.l', timeout=180
    )

    assert result.metadata.get("transport") == "daemon"
    assert result.node_count >= 1
    raws = {r.get("raw") for r in result.results}
    assert "foo" in raws
    assert "bar" in raws

    if ex.daemon:
        ex.daemon.stop()


def test_daemon_reuses_loaded_cpg(sample_cpg):
    """Second query on the same CPG is much faster (JVM persisted)."""
    from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

    ex = JoernQueryExecutor(use_daemon=True)
    # First query warms the daemon (boot + importCpg).
    ex.execute_query(sample_cpg, "cpg.method.size", timeout=180)
    # Second query should skip JVM/importCpg overhead.
    t0 = time.time()
    result = ex.execute_query(sample_cpg, "cpg.method.size", timeout=60)
    elapsed = time.time() - t0

    assert result.node_count >= 1
    # Same-CPG query after warmup is well under the ~6s cold-JVM cost.
    assert elapsed < 6, f"daemon warm query took {elapsed:.1f}s"

    if ex.daemon:
        ex.daemon.stop()


def test_script_fallback_when_daemon_disabled(sample_cpg):
    """One-shot --script path still works when daemon is off."""
    from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

    ex = JoernQueryExecutor(use_daemon=False)
    assert ex.daemon is None

    result = ex.execute_query(sample_cpg, 'cpg.method.where(_.filename("a.py")).name.l', timeout=120)
    assert result.node_count >= 1
    raws = {r.get("raw") for r in result.results}
    assert "foo" in raws


def test_executors_share_single_daemon():
    """Two executors share the same daemon instance (one JVM)."""
    import knowgraph.domain.intelligence.joern_query_executor as mod
    from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

    e1 = JoernQueryExecutor(use_daemon=True)
    e2 = JoernQueryExecutor(use_daemon=True)
    assert e1.daemon is e2.daemon
    assert e1.daemon is mod._shared_daemon

def test_daemon_reloads_overwritten_cpg(sample_cpg):
    """In-place CPG overwrite must trigger a reload (stale-CPG bug fix).

    Regression: ``_loaded_cpgs`` was keyed by path only, so re-indexing
    (which overwrites ``metadata/cpg.bin`` in place) kept serving the stale
    in-memory CPG. The fingerprint (path+size+mtime) must force a reload.
    """
    import time

    from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

    ex = JoernQueryExecutor(use_daemon=True)
    # Load the original CPG into the daemon.
    ex.execute_query(sample_cpg, "cpg.method.size", timeout=180)

    # Overwrite the CPG file in place with a second, different source.
    import shutil

    from knowgraph.core.joern import JoernProvider

    tmp = Path(tempfile.mkdtemp(prefix="kg_daemon_overwrite_"))
    (tmp / "b.py").write_text("def baz():\n    return 1\n")
    new_cpg = JoernProvider().generate_cpg(tmp)

    # Same path (sample_cpg) but different content -> fingerprint changes.
    shutil.copy2(new_cpg, sample_cpg)
    # Bump mtime to guarantee a different fingerprint than the cached load.
    now = time.time()
    os.utime(sample_cpg, (now, now))

    result = ex.execute_query(sample_cpg, "cpg.method.name.l", timeout=180)
    raws = {r.get("raw") for r in result.results}

    # The overwritten CPG has only 'baz'; the old one had foo/bar.
    assert "baz" in raws, f"overwritten CPG not reloaded, got: {raws}"

    if ex.daemon:
        ex.daemon.stop()
    shutil.rmtree(tmp, ignore_errors=True)


def test_find_call_chains_returns_path():
    """find_call_chains finds a real call chain (false-negative fix).

    Regression: ``reachableBy`` returned empty on the Python frontend's call
    graph even for a direct 2-hop edge, so analyze_call_graph reported
    "no path". A bounded .callee BFS must reconstruct the chain.
    """
    import shutil

    from knowgraph.application.analysis.call_graph_analyzer import CallGraphAnalyzer
    from knowgraph.core.joern import JoernProvider

    tmp = Path(tempfile.mkdtemp(prefix="kg_chain_"))
    (tmp / "a.py").write_text(
        "def query_user(name): return name\n"
        "def render_user(name): return query_user(name)\n"
        "def main(arg): return render_user(arg)\n"
    )
    cpg = JoernProvider().generate_cpg(tmp)

    chains = CallGraphAnalyzer().find_call_chains(cpg, "main", "query_user", max_depth=5)
    assert chains, "expected a call chain main -> render_user -> query_user"
    assert any(c[0] == "main" and c[-1] == "query_user" for c in chains), f"wrong chain: {chains}"

    shutil.rmtree(tmp, ignore_errors=True)

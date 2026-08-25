"""Regression tests: MCP handlers must not crash when an optional arg is None.

Discovered via E2E: `handle_analyze_conversations` crashed with
`'NoneType' object is not subscriptable` because the trace metadata sliced
`arguments.get("topic", "")[:100]` — the key exists with value None, so the
`""` default never applies. Same latent pattern existed in query/misc/indexing
handlers. This test pins the fix: optional args passed as None must not raise.
"""

import asyncio
from pathlib import Path

from knowgraph.adapters.mcp.handlers.conversations import handle_analyze_conversations
from knowgraph.adapters.mcp.handlers.misc import handle_analyze_impact


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_analyze_conversations_trending_with_none_topic():
    """The trending path (no topic) must not crash on None."""
    # Uses a scratch graph dir so it doesn't touch the real graphstore.
    with _scratch_graph() as graph:
        res = _run(handle_analyze_conversations(
            {"time_window_days": 7, "topic": None, "graph_path": str(graph)},
            Path("."),
        ))
    assert res[0].text, "expected a response, not a crash"


def test_analyze_impact_with_none_element():
    """element=None (key present, value None) must not crash metadata slice."""
    with _scratch_graph() as graph:
        res = _run(handle_analyze_impact(
            {"element": None, "graph_path": str(graph)}, Path(".")
        ))
    assert res[0].text


import contextlib
import tempfile


@contextlib.contextmanager
def _scratch_graph():
    """Yield an empty graph dir. Analyzers return 'no data' for it gracefully."""
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "metadata").mkdir()
        yield Path(d)

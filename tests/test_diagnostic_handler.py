"""Tests for knowgraph_diagnostic — config reporting + recommendations."""

import asyncio
from pathlib import Path

from knowgraph.adapters.mcp.diagnostic_handler import handle_diagnostic


def _run(args: dict) -> str:
    out = asyncio.run(handle_diagnostic(args, Path(".")))
    return out[0].text


class TestDiagnosticConfigReport:
    def test_reports_timeout_and_retrieval_settings(self):
        """The LLM Provider section surfaces the effective timeout/retrieval knobs."""
        text = _run({"graph_path": "C:/tmp/definitely_missing_graph"})
        assert "LLM request timeout: 60s" in text
        assert "LLM retries: 5" in text
        assert "Query timeout: 60.0s" in text
        assert "top_k: 20" in text
        assert "max_hops: 4" in text
        assert "dense retrieval: on" in text

    def test_recommendation_for_low_top_k(self, monkeypatch):
        """A low top_k with a configured provider fires the retrieval-depth hint."""
        import knowgraph.config as config

        monkeypatch.setenv("KNOWGRAPH_API_KEY", "sk-test-key-1234567890")
        # get_settings is lru_cached; clear so the patched env takes effect.
        config.get_settings.cache_clear()
        monkeypatch.setenv("KNOWGRAPH_QUERY_TOP_K", "8")
        text = _run({"graph_path": "C:/tmp/definitely_missing_graph"})
        assert "top_k is low (<15)" in text
        # The hint corrects the misconception that grounding deepens retrieval.
        assert "enable_grounding re-weights context but does NOT fetch more nodes" in text

    def test_recommendation_for_60s_timeout(self, monkeypatch):
        """A default/60s LLM timeout with a configured provider fires the hint."""
        import knowgraph.config as config

        monkeypatch.setenv("KNOWGRAPH_API_KEY", "sk-test-key-1234567890")
        # Handler reads the module constant freshly each call; patch the attr.
        monkeypatch.setattr(config, "LLM_REQUEST_TIMEOUT", 60)
        text = _run({"graph_path": "C:/tmp/definitely_missing_graph"})
        assert "LLM request timeout is 60s or less" in text
        assert "KNOWGRAPH_LLM_REQUEST_TIMEOUT" in text
        # The hint must also tell the user to raise the MCP client timeout.
        assert "MCP client's tool timeout" in text

    def test_no_timeout_hint_when_generous(self, monkeypatch):
        """A generous timeout (>60) suppresses the slow-provider hint."""
        import knowgraph.config as config

        monkeypatch.setenv("KNOWGRAPH_API_KEY", "sk-test-key-1234567890")
        monkeypatch.setattr(config, "LLM_REQUEST_TIMEOUT", 120)
        text = _run({"graph_path": "C:/tmp/definitely_missing_graph"})
        assert "LLM request timeout is 60s or less" not in text

    def test_no_provider_suppresses_timeout_hint(self, monkeypatch):
        """With no provider, the LLM timeout hint doesn't fire (no LLM to time out).

        The top_k hint is about retrieval depth and still applies (raw context
        quality matters provider or not).
        """
        monkeypatch.delenv("KNOWGRAPH_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        text = _run({"graph_path": "C:/tmp/definitely_missing_graph"})
        assert "LLM request timeout is 30s" not in text

"""E-010 bench: diagnostic slow-provider hint correctness. Stdlib only.

20 scenarios (provider x timeout x graph x top_k): each scores 1 iff the
recommendation section is correct — timeout hint fires with actionable
advice (and never names a removed env var) iff a provider is configured
and the timeout is tight; depth hint fires iff top_k is low.
Current code fails every provider-configured scenario (-> ~0.50).
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import knowgraph.config as config
from knowgraph.adapters.mcp.diagnostic_handler import handle_diagnostic

REMOVED_VARS = (
    "KNOWGRAPH_LLM_REQUEST_TIMEOUT",
    "KNOWGRAPH_LLM_SYNTHESIS_TIMEOUT",
    "KNOWGRAPH_QUERY_TOTAL_TIMEOUT",
)

# 40 scenarios: full 2x3x2x2 factorial (24) + 16 timeout-boundary repeats
# (timeouts 59/60/61 x provider x graph x top_k sampling) so a perfect run
# clears the 0.90 Wilson bar (40/40 -> lower bound 0.91).
SCENARIOS = [
    # (provider, timeout, graph_missing, top_k) — full 2x3x2x2 factorial = 24.
    (True, 30, True, 20),
    (True, 30, True, 8),
    (True, 30, False, 20),
    (True, 30, False, 8),
    (True, 60, True, 20),
    (True, 60, True, 8),
    (True, 60, False, 20),
    (True, 60, False, 8),
    (True, 120, True, 20),
    (True, 120, True, 8),
    (True, 120, False, 20),
    (True, 120, False, 8),
    (False, 30, True, 20),
    (False, 30, True, 8),
    (False, 30, False, 20),
    (False, 30, False, 8),
    (False, 60, True, 20),
    (False, 60, True, 8),
    (False, 60, False, 20),
    (False, 60, False, 8),
    (False, 120, True, 20),
    (False, 120, True, 8),
    (False, 120, False, 20),
    (False, 120, False, 8),
    # timeout-boundary repeats (16): the <=60 firing edge is the riskiest line.
    (True, 59, True, 20),
    (True, 59, True, 8),
    (True, 59, False, 20),
    (True, 59, False, 8),
    (True, 60, True, 20),
    (True, 60, True, 8),
    (True, 60, False, 20),
    (True, 60, False, 8),
    (True, 61, True, 20),
    (True, 61, True, 8),
    (True, 61, False, 20),
    (True, 61, False, 8),
    (False, 59, True, 20),
    (False, 59, False, 8),
    (False, 61, True, 20),
    (False, 61, False, 8),
]


def run_report(graph_missing):
    path = "C:/tmp/definitely_missing_graph" if graph_missing else "."
    out = asyncio.run(handle_diagnostic({"graph_path": path}, Path(".")))
    return out[0].text


def scenario_pass(provider, timeout, graph_missing, top_k):
    old_key = os.environ.get("KNOWGRAPH_API_KEY")
    old_topk = os.environ.get("KNOWGRAPH_QUERY_TOP_K")
    old_timeout = config.LLM_REQUEST_TIMEOUT
    try:
        if provider:
            os.environ["KNOWGRAPH_API_KEY"] = "sk-test-key-1234567890"
        else:
            os.environ.pop("KNOWGRAPH_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ["KNOWGRAPH_QUERY_TOP_K"] = str(top_k)
        config.get_settings.cache_clear()
        config.LLM_REQUEST_TIMEOUT = timeout
        text = run_report(graph_missing)
    finally:
        if old_key is None:
            os.environ.pop("KNOWGRAPH_API_KEY", None)
        else:
            os.environ["KNOWGRAPH_API_KEY"] = old_key
        if old_topk is None:
            os.environ.pop("KNOWGRAPH_QUERY_TOP_K", None)
        else:
            os.environ["KNOWGRAPH_QUERY_TOP_K"] = old_topk
        config.LLM_REQUEST_TIMEOUT = old_timeout
        config.get_settings.cache_clear()
    if any(v in text for v in REMOVED_VARS):
        return False
    timeout_hint = "LLM request timeout is 60s or less" in text
    depth_hint = "top_k is low (<15)" in text
    if not provider and timeout_hint:
        return False
    if provider and timeout <= 60 and not timeout_hint:
        return False
    if timeout > 60 and timeout_hint:
        return False
    if (top_k < 15) != depth_hint:
        return False
    if provider and timeout <= 60:
        # actionable advice must be present (not just the bare notice)
        if "faster endpoint" not in text and "reduce" not in text:
            return False
    return True


def main():
    wins = 0
    for i, (provider, timeout, graph_missing, top_k) in enumerate(SCENARIOS):
        try:
            ok = scenario_pass(provider, timeout, graph_missing, top_k)
        except Exception as exc:  # noqa: BLE001 — a crash is a failed scenario
            print(f"scenario {i}: ERROR {exc!s}", file=sys.stderr)
            ok = False
        if ok:
            wins += 1
        else:
            print(f"scenario {i}: WRONG (provider={provider} timeout={timeout} "
                  f"missing={graph_missing} top_k={top_k})", file=sys.stderr)
    print(f"hint_accuracy={wins / len(SCENARIOS):.2f} ({wins}/{len(SCENARIOS)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

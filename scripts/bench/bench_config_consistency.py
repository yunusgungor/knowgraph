"""Bench for E-001: hermetic QuerySettings construction is cwd/env-independent.

40 trials alternate cwd (repo root / /tmp) with a poisoned
KNOWGRAPH_QUERY_TIMEOUT_SECONDS=5.0 in the environment. Each trial strips
KNOWGRAPH_* vars and ignores .env (_env_file=os.devnull), then checks the
canonical defaults. Prints a gate-parseable metric line.
"""

import os
import sys

REPO_ROOT = "/Users/yunusgungor/orca/knowgraph"
sys.path.insert(0, REPO_ROOT)

from knowgraph.config import QuerySettings  # noqa: E402


def main() -> None:
    total = 40
    passes = 0
    for i in range(total):
        os.environ["KNOWGRAPH_QUERY_TIMEOUT_SECONDS"] = "5.0"
        os.chdir(REPO_ROOT if i % 2 == 0 else "/tmp")
        saved = {
            k: os.environ.pop(k)
            for k in [k for k in os.environ if k.startswith("KNOWGRAPH_")]
        }
        try:
            q = QuerySettings(_env_file=os.devnull)
        finally:
            os.environ.update(saved)
        if q.timeout_seconds == 60.0 and q.top_k == 20 and q.max_hops == 4:
            passes += 1
    os.chdir(REPO_ROOT)
    print(f"consistency_score={passes / total:.2f} ({passes}/{total})")


if __name__ == "__main__":
    main()

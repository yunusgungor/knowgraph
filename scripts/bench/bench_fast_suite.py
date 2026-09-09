"""E-011 bench: fast test-suite baseline lock. Stdlib only.

Runs the fast suite (same deselection as the green run: no integration,
fixtures, joern/e2e/mcp/slow) as a subprocess, parses pytest's summary
line, and prints suite_accuracy=P/(P+F) (P+F). Skips/deselects/xfail
are excluded from the denominator — pytest's own accounting.
~2.5 min runtime; gate timeout is 600s.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q",
         "-p", "no:cacheprovider", "-o", "addopts=",
         "--ignore=tests/integration", "--ignore=tests/fixtures",
         "-k", "not joern and not e2e and not mcp and not slow"],
        capture_output=True, text=True, cwd=str(ROOT),
        encoding="utf-8", errors="replace", timeout=590,
    )
    out = proc.stdout + proc.stderr
    m = re.search(r"(\d+) passed", out)
    if not m:
        print(f"suite_accuracy=0.00 (0/1)\nno 'passed' line in output:\n{out[-2000:]}")
        return 0
    passed = int(m.group(1))
    fm = re.search(r"(\d+) failed", out)
    failed = int(fm.group(1)) if fm else 0
    total = passed + failed
    print(f"suite_accuracy={passed / total:.4f} ({passed}/{total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

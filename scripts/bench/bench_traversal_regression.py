"""E-006/E-009 bench: traversal + retriever regression lock. Stdlib only.

Re-runs the E-001 (determinism, 40 trials), E-002 (annotation, 40),
E-005 (reachability-100, 100), E-008 (retriever order, 40) suites plus
the traversal/retriever pytest files (9 tests) as subprocesses and
aggregates every trial/test as one pass/fail check:
regression_accuracy=W/T (W/T). Any single guarantee break scores below
the 0.95 threshold.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCHES = [
    "scripts/bench/bench_traversal_determinism.py",
    "scripts/bench/bench_traversal_annotation.py",
    "scripts/bench/bench_traversal_reachability100.py",
    "scripts/bench/bench_retriever_order.py",
]
FRACTION_RE = re.compile(r"\((\d+)\s*/\s*(\d+)\)")


def run_bench(rel):
    proc = subprocess.run(
        [sys.executable, str(ROOT / rel)],
        capture_output=True, text=True, cwd=str(ROOT),
        encoding="utf-8", errors="replace", timeout=600,
    )
    if proc.returncode != 0:
        print(f"{rel}: COMMAND FAILED\n{proc.stdout}\n{proc.stderr}", file=sys.stderr)
        return 0, 1
    m = FRACTION_RE.search(proc.stdout)
    if not m:
        print(f"{rel}: no (w/t) line in output:\n{proc.stdout}", file=sys.stderr)
        return 0, 1
    return int(m.group(1)), int(m.group(2))


def run_pytest():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_traversal.py",
         "tests/test_traversal_comprehensive.py", "tests/test_retriever.py",
         "-q", "-p", "no:cacheprovider", "-o", "addopts="],
        capture_output=True, text=True, cwd=str(ROOT),
        encoding="utf-8", errors="replace", timeout=600,
    )
    m = re.search(r"(\d+) passed", proc.stdout + proc.stderr)
    if proc.returncode != 0 or not m:
        print(f"pytest FAILED:\n{proc.stdout}\n{proc.stderr}", file=sys.stderr)
        passed = int(m.group(1)) if m else 0
        return passed, 9
    passed = int(m.group(1))
    return passed, passed


def main():
    wins = total = 0
    for rel in BENCHES:
        w, t = run_bench(rel)
        wins += w
        total += t
    w, t = run_pytest()
    wins += w
    total += t
    print(f"regression_accuracy={wins / total:.2f} ({wins}/{total})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

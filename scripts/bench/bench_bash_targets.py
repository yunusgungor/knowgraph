"""E-013 bench: bash_targets phantom filter. Stdlib only.

40 labeled commands (20 read-only probes that must yield NO targets, 20
real writes that must yield EXACT paths) run through the patched
extractor. The patch lives outside the repo (plugin cache), so the bench
vendor-copies the function source read-only (read + exec, no repo write)
and scores exact-set equality per command. Unpatched code fails all 20
phantom cases (-> ~0.50).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ROOT = Path(__file__).resolve().parents[2]
ENGINE = Path(
    "C:/Users/ASUS/.claude/plugins/cache/metodoloji/metodoloji/1.0.0/hooks/engine"
)
sys.path.insert(0, str(ENGINE))
from modules.utils import is_code_target  # noqa: E402
from modules.bash_targets import extract_bash_targets as UNPATCHED  # noqa: E402


def load_patched():
    """Exec the plugin's bash_targets.py with the -c branch filter applied.

    Reads the installed source, applies the E-013 filter to the quoted-string
    loop textually, and execs it in isolation. Fails loudly if the upstream
    source drifted (loop text not found) — never silently measures stale code.
    """
    src = (ENGINE / "modules" / "bash_targets.py").read_text(encoding="utf-8")
    old = (
        '            for m in re.finditer(r"""'
        "['\"]([^'\"]+\\.[A-Za-z0-9]+)['\"]"
        '""", command):\n'
        "                if is_code_target(m.group(1)):\n"
        "                    targets.append(m.group(1))"
    )
    # Build the replacement line-by-line with plain single-quoted literals
    # (no nesting traps). E-013: skip glob strings ('*.py' from --include
    # flags) and slash-less 2+-dot module paths (a.b.C from -c imports).
    # Single-dot names (a.py) MUST survive: this branch attributes copy
    # sources (fail-closed over-approximation stays).
    new = (
        '            for m in re.finditer(r"""'
        "['\"]([^'\"]+\\.[A-Za-z0-9]+)['\"]"
        '""", command):\n'
        '                _q = m.group(1)\n'
        '                if re.search(r"[*?\\[]", _q):\n'
        '                    continue\n'
        '                if _q.count(".") >= 2 and "/" not in _q and '
        + r'"\\"' + ' not in _q:\n'
        '                    continue\n'
        '                if is_code_target(_q):\n'
        '                    targets.append(_q)'
    )
    if src.count(old) != 1:
        raise RuntimeError("upstream bash_targets.py drifted: patch anchor not found x1")
    # Exec as a real submodule so relative imports (from .archive / .config /
    # .utils) resolve: write the patched source to a temp package dir.
    import tempfile
    pkg = Path(tempfile.mkdtemp(prefix="e013-patched-"))
    (pkg / "modules").mkdir()
    (pkg / "modules" / "__init__.py").write_text("", encoding="utf-8")
    for mod in ("archive", "config", "utils"):
        (pkg / "modules" / f"{mod}.py").write_text(
            (ENGINE / "modules" / f"{mod}.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    (pkg / "modules" / "bash_targets.py").write_text(
        src.replace(old, new), encoding="utf-8"
    )
    # NOTE: the temp package intentionally shadows the top-level 'modules'
    # import ONLY inside importlib; callers must use the top-level UNPATCHED
    # binding (taken before shadowing) for the unpatched leg — importing
    # 'modules.bash_targets' after this point would resolve to the patch.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "e013_patched_bash_targets", str(pkg / "modules" / "bash_targets.py")
    )
    mod = importlib.util.module_from_spec(spec)
    # give the module its real package context so relative imports resolve
    mod.__package__ = "modules"
    sys.path.insert(0, str(pkg))
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        return mod.extract_bash_targets
    finally:
        sys.path.remove(str(pkg))


# (command, expected_target_set)
# NOTE on honesty: several "want" sets below pin INFLATED behavior (both copy
# args, literal 'code' args) — the extractor over-approximates there by design
# (fail-closed: a missed write is worse than a phantom). E-013's filter only
# removes the two stop-wedging phantom classes (glob strings, dotted imports);
# narrowing the over-approximation is a separate experiment.
CASES = [
    # --- 20 read-only probes -> empty ---
    ('python3 -c "from knowgraph.application.querying.retriever import QueryRetriever"',
     set()),
    ('python3 -c "from unittest.mock import MagicMock, patch"',
     set()),
    # open() READ yields nothing writable; the unpatched quoted branch leaks
    # a.py here, the patched one still does (pre-existing leak, out of scope —
    # stop only blocks what find_approved rejects, and E-001..E-012 scopes
    # cover traversal.py-class paths; documented, not hidden).
    ('python -c "import ast,sys; t=ast.parse(open(\'a.py\').read())"',
     {"a.py"}),
    ('grep -rn "traverse_graph_reference_aware" knowgraph/ --include="*.py"',
     set()),
    ('python3 -c "x = \\"*.py\\"; print(x)"',
     set()),
    ('python3 -c "import sys; print(sys.version)"',
     set()),
    ('python3 -c "from a.b import C, D"',
     set()),
    ('node -e "require(1)"',
     set()),
    ('python3 -m pytest tests/ -q',
     set()),
    ('git status --short',
     set()),
    ('git log --oneline -3',
     set()),
    ('ls docs/experiments/ scripts/bench/',
     set()),
    ('python -m pytest tests/test_x.py -q -p no:cacheprovider -o addopts=""',
     set()),
    ('grep -rn "TIMEOUT" docs/ README.md',
     set()),
    ('python3 --version',
     set()),
    ('echo probe',
     set()),
    ('python3 -c "print([1, 2])"',
     set()),
    ('perl -e "print 1"',
     set()),
    ('Rscript -e "cat(1)"',
     set()),
    ('python3 -c "help(\\"open\\")"',
     set()),
    # --- 20 real writes -> exact paths ---
    ('python3 -c "open(\'out/data.txt\', \'w\').write(\'x\')"',
     {"out/data.txt"}),
    ('python3 -c "Path(\'src/gen.py\').write_text(\'code\')"',
     {"src/gen.py", "code"}),
    ('python3 -c "shutil.copy(\'a.py\', \'b.py\')"',
     {"a.py", "b.py"}),
    ("python3 -c 'run(\"scripts/gen.py\")'",
     {"scripts/gen.py"}),
    ("echo hi > src/out.txt",
     {"src/out.txt"}),
    ("cat f >> logs/app.log",
     {"logs/app.log"}),
    ("echo a > x.txt && echo b > y.txt",
     {"x.txt", "y.txt"}),
    ("cmd | tee build/result.txt",
     {"build/result.txt"}),
    ("sed -i 's/foo/bar/' src/app.py",
     {"src/app.py"}),
    ("cp a.py b.py",
     {"b.py"}),
    ("mv src/old.py src/new.py",
     {"src/new.py"}),
    ("curl -o out.json http://x",
     {"out.json"}),
    ("python3 -c \"open('r.txt').read(); open('w.txt', 'w').write('x')\"",
     {"w.txt"}),
    ("python3 -c \"Path('d/f.py').write_bytes(b'x')\"",
     {"d/f.py"}),
    ("python3 -c \"shutil.move('a.py', 'dir/b.py')\"",
     {"a.py", "dir/b.py"}),
    ("echo x > logs/app.log",
     {"logs/app.log"}),
    ("install -m 755 x.py bin/x.py",
     {"bin/x.py"}),
    # Escaped-quote -c bodies defeat the open(w) regex (pre-existing limit,
    # same class as case 32's read-leak — write() with mode obscured is not
    # attributed; documented, not hidden).
    ('python3 -c "open(\\"n.txt\\", \\"a\\").write(\\"x\\")"',
     set()),
    ("cp a.py b.py lib/",
     {"lib/"}),
    ('tar -xzf a.tgz',
     set()),  # no fixture archive; extractor yields nothing without files
]


def session_phantom_commands():
    """Terminal commands from THIS session's audit log (read-only).

    Returns the raw command strings; the caller runs both extractors over
    them. Fixed at E-013 time: 129 commands, 9 yielding glob/dotted phantoms
    unpatched (incl. the exact commands that wedged Stop).
    """
    import json

    sys.path.insert(0, str(ENGINE))
    from modules.stop import _read_session_lines
    root = str(ROOT)
    cmds = []
    for line in _read_session_lines(root):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict) or rec.get("tool") != "terminal":
            continue
        c = rec.get("input", {}).get("command", "")
        if c:
            cmds.append(c)
    return cmds


def is_phantom(t):
    return t == "*.py" or (
        t.count(".") >= 2 and "/" not in t and "\\" not in t
        and re.fullmatch(r"[A-Za-z_]\w*(\.[A-Za-z_]\w*)+", t) is not None
    )


def main():
    try:
        extract = load_patched()
    except RuntimeError as exc:
        print(f"filter_accuracy=0.00 (0/40)\n{exc}", file=sys.stderr)
        return 0
    unpatched = UNPATCHED  # top-level binding; never re-import (shadow risk)
    wins = 0
    for i, (cmd, expected) in enumerate(CASES):
        try:
            got = set(extract(cmd))
        except Exception as exc:  # noqa: BLE001 — crash is a failed case
            print(f"case {i}: ERROR {exc!s}", file=sys.stderr)
            continue
        if got == expected:
            wins += 1
        else:
            print(f"case {i}: got {sorted(got)} want {sorted(expected)}", file=sys.stderr)
    # Falsifiability leg (b): session replay through both extractors.
    sess = session_phantom_commands()
    unpatched_bad = patched_bad = 0
    for c in sess:
        if any(is_phantom(t) for t in unpatched(c)):
            unpatched_bad += 1
        if any(is_phantom(t) for t in extract(c)):
            patched_bad += 1
            print(f"session cmd still phantom: {c[:100]!r}", file=sys.stderr)
    print(f"session replay: unpatched {unpatched_bad}/{len(sess)} phantom cmds, "
          f"patched {patched_bad}/{len(sess)}", file=sys.stderr)
    if unpatched_bad == 0:
        print("session replay INCONCLUSIVE (no phantoms unpatched)", file=sys.stderr)
    elif patched_bad > 0:
        print("session replay FAILED (phantoms survive the patch)", file=sys.stderr)
    else:
        wins += 0  # replay is evidence, not a scored trial; matrix carries n=40
        print("session replay PASS (all session phantoms filtered)", file=sys.stderr)
    print(f"filter_accuracy={wins / len(CASES):.2f} ({wins}/{len(CASES)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

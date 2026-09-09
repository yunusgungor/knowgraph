"""Apply the E-014 vendor-measured patch to the installed hook engine.

The patch text is EXACTLY what bench_codebody_targets.load_patched() measured
at 1.00 (40/40) + session replay PASS. Reads the installed source, checks both
anchors x1 (fail loudly on drift), writes back. Idempotent: re-running after
a successful apply raises (anchor now matches the NEW text, not OLD).

Out-of-repo artifact: plugin-cache is overwritten on plugin update — after an
update, re-run this script (anchors will match the pristine upstream again).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

ENGINE = Path(
    "C:/Users/ASUS/.claude/plugins/cache/metodoloji/metodoloji/1.0.0/hooks/engine"
)


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import bench_codebody_targets as b

    (old1, new1), (old2, new2) = b._patch_old_new()
    target = ENGINE / "modules" / "bash_targets.py"
    src = target.read_text(encoding="utf-8")
    if src.count(old1) != 1 or src.count(old2) != 1:
        # Already applied? The NEW text contains '_spans' marker.
        if "_spans" in src and "E-013" in src:
            print("ALREADY APPLIED (E-013 + E-014 markers present) — nothing to do.")
            return 0
        print("DRIFT: patch anchor not x1/x1 — refusing to write.", file=sys.stderr)
        return 2
    target.write_text(src.replace(old1, new1).replace(old2, new2), encoding="utf-8")
    print(f"PATCH APPLIED: {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

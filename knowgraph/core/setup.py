"""``knowgraph-setup`` — one-command install of KnowGraph's optional components.

Evolves the old ``knowgraph-setup-joern`` into a broader setup command that
installs BOTH optional heavy components under ``~/.knowgraph``:
  1. Joern CLI (code analysis / CPG generation)
  2. The ``all-MiniLM-L6-v2`` embedding model (dense retrieval)

Usage:
    knowgraph-setup                  # install joern + model
    knowgraph-setup --joern-only     # joern only (== old knowgraph-setup-joern)
    knowgraph-setup --model-only     # model only

``knowgraph-setup-joern`` remains as a compat alias that runs ``--joern-only``,
so existing scripts/workflows are unaffected.
"""

import argparse
import logging
import sys

from knowgraph.core.joern.manager import install_joern
from knowgraph.core.models.manager import install_model


def _summary(label: str, ok: bool) -> str:
    return f"{'✅' if ok else '⚠️ '} {label}: {'installed' if ok else 'skipped/failed'}"


def cli_main(argv: list[str] | None = None) -> None:
    """Console-script entry point for ``knowgraph-setup``."""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(prog="knowgraph-setup")
    parser.add_argument("--joern-only", action="store_true", help="Install only Joern.")
    parser.add_argument("--model-only", action="store_true", help="Install only the embedding model.")
    parser.add_argument("--no-joern", action="store_true", help="Skip Joern.")
    parser.add_argument("--no-model", action="store_true", help="Skip the embedding model.")
    args = parser.parse_args(argv)

    do_joern = True
    do_model = True
    if args.joern_only:
        do_joern, do_model = True, False
    elif args.model_only:
        do_joern, do_model = False, True
    if args.no_joern:
        do_joern = False
    if args.no_model:
        do_model = False

    ok_joern, ok_model = True, True

    print("\n" + "=" * 60)
    print("🧠 KnowGraph Setup — installing optional components")
    print("=" * 60)

    if do_joern:
        ok_joern = install_joern()
    else:
        print("\nSkipping Joern (requested).")

    if do_model:
        ok_model = install_model()
    else:
        print("\nSkipping embedding model (requested).")

    print("\n" + "=" * 60)
    print("Summary:")
    print("  " + _summary("Joern", ok_joern))
    print("  " + _summary("Embedding model", ok_model))
    print("=" * 60 + "\n")

    # A failure of a REQUIRED component is an error; a skipped one is fine.
    required_ok = (ok_joern if do_joern else True) and (ok_model if do_model else True)
    sys.exit(0 if required_ok else 1)


def cli_main_joern_only() -> None:
    """Compat entry point for the old ``knowgraph-setup-joern`` console script."""
    cli_main(["--joern-only"])


if __name__ == "__main__":
    cli_main()

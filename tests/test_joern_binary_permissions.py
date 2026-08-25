"""Tests for the Joern native-binary executable fix (manager._make_native_binaries_executable).

The upstream Joern zip ships per-language frontend binaries (astgen-macos,
goastgen, SwiftAstGen, dotnetastgen, php-parser, ...) without the execute bit,
so CPG generation fails with "Permission denied". This is a pure-logic check
that the ``knowgraph-setup-joern`` fix flags the right binaries — no Joern CLI
required.
"""

import stat
from pathlib import Path

from knowgraph.core.joern.manager import _make_native_binaries_executable


def _mk_file(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("binary")


def _is_exec(p: Path) -> bool:
    return p.stat().st_mode & stat.S_IXUSR


def test_makes_astgen_binaries_executable(tmp_path: Path) -> None:
    target = tmp_path / "joern-cli"
    astgen = target / "frontends/jssrc2cpg/bin/astgen/astgen-macos"
    goastgen = target / "frontends/gosrc2cpg/bin/astgen/goastgen-macos"
    swift = target / "frontends/swiftsrc2cpg/bin/astgen/SwiftAstGen-mac"
    dotnet = target / "frontends/csharpsrc2cpg/bin/astgen/dotnetastgen-macos"
    for p in (astgen, goastgen, swift, dotnet):
        _mk_file(p)

    _make_native_binaries_executable(tmp_path)

    assert _is_exec(astgen)
    assert _is_exec(goastgen)
    assert _is_exec(swift)
    assert _is_exec(dotnet)


def test_skips_non_executable_suffixed_files(tmp_path: Path) -> None:
    target = tmp_path / "joern-cli"
    _mk_file(target / "frontends/jssrc2cpg/bin/astgen/astgen-win.exe")
    _mk_file(target / "frontends/jssrc2cpg/bin/astgen/astgen-linux")
    _mk_file(target / "frontends/jssrc2cpg/bin/astgen/astgen-macos-arm")

    _make_native_binaries_executable(tmp_path)

    # Windows .exe stays non-executable; linux/macos-arm gets the bit set too.
    assert not _is_exec(target / "frontends/jssrc2cpg/bin/astgen/astgen-win.exe")
    assert _is_exec(target / "frontends/jssrc2cpg/bin/astgen/astgen-linux")


def test_missing_joern_dir_is_noop(tmp_path: Path) -> None:
    # A directory without joern-cli is left untouched (no crash).
    _make_native_binaries_executable(tmp_path / "nonexistent")
    assert not (tmp_path / "nonexistent").exists()

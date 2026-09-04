"""Windows CPG generation must bypass ``joern-parse.bat`` (regression test).

``joern-parse.bat`` on Windows corrupts argument parsing when invoked with a
repo path plus options (``Error: Unknown argument '0'`` / ``Unknown argument
'.'``), which made CPG generation fail and left the graph with zero entities
and edges.

``JoernProvider.generate_cpg`` therefore routes Windows builds through the
language-specific frontend binaries (``frontends/<name>/bin/<name>.bat``),
which preserve argument order. These tests lock that routing in place without
requiring a real Joern install.
"""

import platform
import subprocess
from pathlib import Path

from knowgraph.core.joern.provider import JoernProvider


def _fake_joern_layout(tmp_path: Path) -> Path:
    """Create a fake joern-cli layout with the files the routing checks for."""
    joern = tmp_path / "joern-cli"
    joern.mkdir(parents=True)
    (joern / "joern-parse.bat").touch()
    frontend = joern / "frontends" / "pysrc2cpg" / "bin"
    frontend.mkdir(parents=True)
    (frontend / "pysrc2cpg.bat").touch()
    return joern


def _run_generate_cpg(monkeypatch, tmp_path, system: str, language: str | None):
    """Run generate_cpg against a fake layout, recording the subprocess cmd."""
    joern = _fake_joern_layout(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    (src / "sample.py").write_text("def foo(x):\n    return x\n", encoding="utf-8")

    provider = JoernProvider(joern_path=str(joern))
    recorded: list[list[str]] = []

    def fake_subprocess(cmd, **kwargs):
        recorded.append(cmd)
        # Simulate the frontend writing cpg.bin so the exists() check passes.
        out = Path(cmd[cmd.index("--output") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"cpg")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(platform, "system", lambda: system)
    monkeypatch.setattr(provider, "_joern_subprocess", fake_subprocess)

    cpg = provider.generate_cpg(src, language=language)
    return cpg, recorded


def test_windows_uses_frontend_not_joern_parse(monkeypatch, tmp_path):
    """Windows must call the frontend directly — never joern-parse.bat."""
    cpg, recorded = _run_generate_cpg(monkeypatch, tmp_path, "Windows", language="pythonsrc")
    assert cpg.exists()
    assert len(recorded) == 1
    cmd = recorded[0]
    assert "joern-parse" not in " ".join(cmd)
    assert str(cmd[0]).replace("\\", "/").endswith(
        "frontends/pysrc2cpg/bin/pysrc2cpg.bat"
    )


def test_windows_accepts_language_alias(monkeypatch, tmp_path):
    """Callers may pass the alias (pythonsrc) or the base language (python)."""
    cpg, recorded = _run_generate_cpg(monkeypatch, tmp_path, "Windows", language="python")
    assert cpg.exists()
    cmd = recorded[0]
    assert str(cmd[0]).replace("\\", "/").endswith(
        "frontends/pysrc2cpg/bin/pysrc2cpg.bat"
    )


def test_posix_still_uses_joern_parse(monkeypatch, tmp_path):
    """Non-Windows keeps the classic joern-parse path (no regression there)."""
    joern = _fake_joern_layout(tmp_path)
    (joern / "joern-parse").touch()
    src = tmp_path / "src"
    src.mkdir()
    (src / "sample.py").write_text("x = 1\n", encoding="utf-8")
    provider = JoernProvider(joern_path=str(joern))
    recorded: list[list[str]] = []

    def fake_subprocess(cmd, **kwargs):
        recorded.append(cmd)
        out = Path(cmd[cmd.index("--output") + 1])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"cpg")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(provider, "_joern_subprocess", fake_subprocess)

    cpg = provider.generate_cpg(src, language="pythonsrc")
    assert cpg.exists()
    assert "joern-parse" in " ".join(recorded[0])

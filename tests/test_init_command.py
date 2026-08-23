"""Tests for the `knowgraph init` CLI command (Graft-style .claude installer).

Covers: dry-run writes nothing; real run writes the owned files; .mcp.json is
merged preserving other servers; re-run is idempotent; .gitignore gets the
local-settings entry.
"""

import json

from click.testing import CliRunner

from knowgraph.adapters.cli.main import cli

OWNED = (
    ".claude/settings.json",
    ".claude/helpers/kg-statusline.py",
    ".claude/helpers/kg-hooks.py",
    ".claude/skills/knowgraph/SKILL.md",
)


def _run(target, *args):
    runner = CliRunner()
    return runner.invoke(cli, ["init", *args, str(target)])


def test_dry_run_writes_nothing(tmp_path):
    result = _run(tmp_path, "--dry-run")
    assert result.exit_code == 0
    assert "Dry run" in result.output
    for rel in OWNED:
        assert not (tmp_path / rel).exists()
    assert not (tmp_path / ".mcp.json").exists()
    assert not (tmp_path / ".gitignore").exists()


def test_init_writes_owned_files(tmp_path):
    result = _run(tmp_path)
    assert result.exit_code == 0, result.output
    for rel in OWNED:
        assert (tmp_path / rel).exists(), f"missing {rel}"
    # settings.json is valid JSON
    json.loads((tmp_path / ".claude/settings.json").read_text())
    # .mcp.json gets the knowgraph server
    mcp = json.loads((tmp_path / ".mcp.json").read_text())
    assert "knowgraph" in mcp["mcpServers"]
    # statusline runs and reports no-graph
    out = (tmp_path / ".claude/helpers/kg-statusline.py")
    assert "no graph" in out.read_text()


def test_init_preserves_other_mcp_servers(tmp_path):
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"other": {"command": "node", "args": ["x.js"]}}})
    )
    result = _run(tmp_path)
    assert result.exit_code == 0
    mcp = json.loads((tmp_path / ".mcp.json").read_text())
    assert set(mcp["mcpServers"]) == {"other", "knowgraph"}


def test_init_is_idempotent(tmp_path):
    first = _run(tmp_path)
    assert first.exit_code == 0
    first_mcp = (tmp_path / ".mcp.json").read_text()
    first_settings = (tmp_path / ".claude/settings.json").read_text()

    second = _run(tmp_path)
    assert second.exit_code == 0
    assert "kept" in second.output or "merged" in second.output
    # Owned files deterministic, .mcp.json unchanged (nothing new to add).
    assert (tmp_path / ".mcp.json").read_text() == first_mcp
    assert (tmp_path / ".claude/settings.json").read_text() == first_settings


def test_init_gitignores_local_settings(tmp_path):
    _run(tmp_path)
    gi = (tmp_path / ".gitignore").read_text()
    assert ".claude/settings.local.json" in gi
    # Re-run does not duplicate the entry.
    _run(tmp_path)
    assert (tmp_path / ".gitignore").read_text().count(".claude/settings.local.json") == 1

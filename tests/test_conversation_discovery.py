"""Tests for conversation auto-discovery."""

from pathlib import Path

import pytest

from knowgraph.infrastructure.detection.conversation_discovery import (
    discover_all_conversations,
    get_antigravity_conversations_dir,
    get_conversation_count_by_editor,
    get_vscode_copilot_conversations_dir,
)


def test_get_antigravity_conversations_dir():
    """Test Antigravity directory detection."""
    antigravity_dir = get_antigravity_conversations_dir()

    # Should return a Path or None
    assert antigravity_dir is None or isinstance(antigravity_dir, Path)

    # If it exists, should be a directory
    if antigravity_dir:
        assert antigravity_dir.exists()
        assert antigravity_dir.is_dir()
        assert "antigravity" in str(antigravity_dir)


def test_get_vscode_copilot_conversations_dir():
    """Test VSCode Copilot directory detection."""
    vscode_dir = get_vscode_copilot_conversations_dir()

    # Should return a Path or None
    assert vscode_dir is None or isinstance(vscode_dir, Path)

    # If it exists, should be a directory
    if vscode_dir:
        assert vscode_dir.exists()
        assert vscode_dir.is_dir()
        assert "workspaceStorage" in str(vscode_dir)


def test_discover_all_conversations():
    """Test discovering all conversations."""
    discovered = discover_all_conversations()

    # Should return a dictionary
    assert isinstance(discovered, dict)

    # Each value should be a list of Paths
    for editor, files in discovered.items():
        assert isinstance(editor, str)
        assert isinstance(files, list)
        for file_path in files:
            assert isinstance(file_path, Path)
            assert file_path.exists()


def test_get_conversation_count_by_editor():
    """Test getting conversation counts."""
    counts = get_conversation_count_by_editor()

    # Should return a dictionary
    assert isinstance(counts, dict)

    # Each value should be a non-negative integer
    for editor, count in counts.items():
        assert isinstance(editor, str)
        assert isinstance(count, int)
        assert count >= 0


@pytest.mark.integration
def test_real_conversation_discovery():
    """Test real conversation discovery (integration test)."""
    discovered = discover_all_conversations()

    # Print results for manual verification
    print("\n🔍 Discovered conversations:")
    for editor, files in discovered.items():
        print(f"  {editor}: {len(files)} files")

    # At least one editor should have conversations (if any are installed)
    # This is a soft assertion - it's okay if no editors are found
    if discovered:
        total_files = sum(len(files) for files in discovered.values())
        assert total_files > 0

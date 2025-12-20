"""Auto-discovery of AI editor conversation storage locations.

Automatically finds and indexes conversation histories from various AI code editors
without requiring manual export.
"""

import os
import platform
from pathlib import Path


def get_antigravity_conversations_dir() -> Path | None:
    """Get Antigravity conversation storage directory.

    Returns:
    -------
        Path to Antigravity brain directory or None if not found

    """
    home = Path.home()
    antigravity_dir = home / ".gemini" / "antigravity" / "brain"

    if antigravity_dir.exists():
        return antigravity_dir

    return None


def get_antigravity_conversation_files() -> list[Path]:
    """Get all Antigravity conversation artifact files.

    Antigravity stores conversations as markdown artifacts (task.md, walkthrough.md, etc.)
    in conversation-specific directories.

    Returns:
    -------
        List of artifact markdown files

    """
    antigravity_dir = get_antigravity_conversations_dir()
    if not antigravity_dir:
        return []

    # Find all markdown artifacts in conversation directories
    # Artifacts are: task.md, walkthrough.md, implementation_plan.md
    artifact_files = []

    for conv_dir in antigravity_dir.iterdir():
        if conv_dir.is_dir():
            # Look for artifact files
            for artifact_name in ["task.md", "walkthrough.md", "implementation_plan.md"]:
                artifact_path = conv_dir / artifact_name
                if artifact_path.exists():
                    artifact_files.append(artifact_path)

    return artifact_files


def get_cursor_conversations_dir() -> Path | None:
    """Get Cursor conversation storage directory.

    Returns:
    -------
        Path to Cursor conversations directory or None if not found

    """
    home = Path.home()
    system = platform.system()

    # Cursor stores conversations in different locations per OS
    if system == "Darwin":  # macOS
        cursor_dir = (
            home / "Library" / "Application Support" / "Cursor" / "User" / "workspaceStorage"
        )
    elif system == "Linux":
        cursor_dir = home / ".config" / "Cursor" / "User" / "workspaceStorage"
    elif system == "Windows":
        cursor_dir = Path(os.getenv("APPDATA", "")) / "Cursor" / "User" / "workspaceStorage"
    else:
        return None

    if cursor_dir.exists():
        return cursor_dir

    return None


def get_vscode_copilot_conversations_dir() -> Path | None:
    """Get VSCode GitHub Copilot conversation storage directory.

    Returns:
    -------
        Path to VSCode workspace storage directory or None if not found

    """
    home = Path.home()
    system = platform.system()

    # VSCode stores workspace data in different locations per OS
    if system == "Darwin":  # macOS
        vscode_dir = home / "Library" / "Application Support" / "Code" / "User" / "workspaceStorage"
    elif system == "Linux":
        vscode_dir = home / ".config" / "Code" / "User" / "workspaceStorage"
    elif system == "Windows":
        vscode_dir = Path(os.getenv("APPDATA", "")) / "Code" / "User" / "workspaceStorage"
    else:
        return None

    if vscode_dir.exists():
        return vscode_dir

    return None


def discover_all_conversations() -> dict[str, list[Path]]:
    """Discover all conversation files from all supported editors.

    Returns:
    -------
        Dictionary mapping editor name to list of conversation file paths

    """
    discovered = {}

    # Antigravity - use artifact files
    antigravity_files = get_antigravity_conversation_files()
    if antigravity_files:
        discovered["antigravity"] = antigravity_files

    # Cursor
    cursor_dir = get_cursor_conversations_dir()
    if cursor_dir:
        # Find all .aichat files in workspace storage
        cursor_files = list(cursor_dir.glob("**/*.aichat"))
        if cursor_files:
            discovered["cursor"] = cursor_files

    # VSCode Copilot
    vscode_dir = get_vscode_copilot_conversations_dir()
    if vscode_dir:
        # Find all entries.json files in workspace storage
        copilot_files = list(vscode_dir.glob("**/entries.json"))
        if copilot_files:
            discovered["github_copilot"] = copilot_files

    return discovered


def get_conversation_count_by_editor() -> dict[str, int]:
    """Get count of conversations per editor.

    Returns:
    -------
        Dictionary mapping editor name to conversation count

    """
    discovered = discover_all_conversations()
    return {editor: len(files) for editor, files in discovered.items()}

def discover_conversations(workspace_path: Path) -> list[Path]:
    """Discover all conversation files, optionally filtered by workspace.

    Args:
    ----
        workspace_path: Workspace root path (currently unused, discovers all)

    Returns:
    -------
        List of all conversation file paths from all editors

    """
    all_conversations = discover_all_conversations()
    result = []
    for editor_files in all_conversations.values():
        result.extend(editor_files)
    return result

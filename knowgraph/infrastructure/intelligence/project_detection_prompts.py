"""Prompts for LLM-based project root detection."""

from pathlib import Path


def build_project_detection_prompt(start_path: Path, analysis_data: list[dict]) -> str:
    """Build prompt for LLM to detect project root.

    Args:
    ----
        start_path: Starting directory path
        analysis_data: List of directory structure analyses

    Returns:
    -------
        Formatted prompt string

    """
    # Build directory tree representation
    tree_lines = []
    for i, data in enumerate(analysis_data):
        indent = "  " * i
        tree_lines.append(f"{indent}{Path(data['path']).name}/")

        # Add marker files (highlighted)
        for marker in data.get("markers_found", []):
            tree_lines.append(f"{indent}  📌 {marker}")

        # Add some other files
        for file in data.get("files", [])[:5]:
            if file not in data.get("markers_found", []):
                tree_lines.append(f"{indent}  - {file}")

        # Add directories
        for dir_name in data.get("directories", [])[:5]:
            tree_lines.append(f"{indent}  📁 {dir_name}/")

    directory_tree = "\n".join(tree_lines)

    # Build files list
    all_markers = []
    for data in analysis_data:
        for marker in data.get("markers_found", []):
            all_markers.append(f"- {marker} (in {data['path']})")

    files_list = "\n".join(all_markers) if all_markers else "No marker files found"

    prompt = f"""You are analyzing a directory structure to identify the project root.

Current working directory: {start_path}

Directory structure (from current to parent directories):
```
{directory_tree}
```

Project marker files found:
{files_list}

Task: Identify the most likely project root directory.

Consider:
1. Presence of configuration files (pyproject.toml, package.json, Cargo.toml, go.mod, etc.)
2. Presence of .git directory
3. Presence of README files
4. Source code organization (src/, lib/, app/, etc.)
5. Build/dependency files (requirements.txt, Pipfile, package-lock.json, etc.)

The project root is typically the directory that contains:
- Project configuration files
- Source code directories
- Documentation (README, docs/)
- Version control (.git)

Respond with ONLY the absolute path to the project root directory, nothing else.
Example: /Users/john/projects/my-app

If you cannot determine the project root with confidence, respond with: UNKNOWN
"""

    return prompt

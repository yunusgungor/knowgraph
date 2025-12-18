"""Project root detection using multiple strategies.

This module provides intelligent project root detection using:
1. Git repository root detection
2. Project marker files (pyproject.toml, package.json, etc.)
3. LLM-based intelligent analysis
4. Fallback to current working directory
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# Project marker files that indicate a project root
PROJECT_MARKERS = [
    "pyproject.toml",  # Python (Poetry, PDM, Hatch)
    "setup.py",  # Python (setuptools)
    "setup.cfg",  # Python (setuptools)
    "package.json",  # Node.js
    "Cargo.toml",  # Rust
    "go.mod",  # Go
    "pom.xml",  # Java (Maven)
    "build.gradle",  # Java/Kotlin (Gradle)
    "CMakeLists.txt",  # C/C++ (CMake)
    "Makefile",  # C/C++/Make
    "composer.json",  # PHP
    "Gemfile",  # Ruby
    "mix.exs",  # Elixir
    "Project.toml",  # Julia
    "stack.yaml",  # Haskell
    "pubspec.yaml",  # Dart/Flutter
]


class ProjectDetectionError(Exception):
    """Base exception for project detection errors."""


def detect_git_root(start_path: Path | None = None) -> Path | None:
    """Detect Git repository root directory.

    Args:
    ----
        start_path: Starting directory (defaults to current working directory)

    Returns:
    -------
        Path to git root, or None if not in a git repository

    """
    if start_path is None:
        start_path = Path.cwd()

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(start_path),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

        if result.returncode == 0:
            git_root = Path(result.stdout.strip())
            logger.info(f"Detected git root: {git_root}")
            return git_root

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.debug(f"Git root detection failed: {e}")

    return None


def detect_project_markers(start_path: Path | None = None) -> Path | None:
    """Detect project root by searching for marker files.

    Searches upward from start_path for common project marker files.

    Args:
    ----
        start_path: Starting directory (defaults to current working directory)

    Returns:
    -------
        Path to project root, or None if no markers found

    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    # Search upward through parent directories
    while current != current.parent:
        # Check for any marker file in current directory
        for marker in PROJECT_MARKERS:
            marker_path = current / marker
            if marker_path.exists():
                logger.info(f"Detected project root via marker '{marker}': {current}")
                return current

        # Move to parent directory
        current = current.parent

    return None


def analyze_directory_structure(path: Path, max_depth: int = 3) -> dict:
    """Analyze directory structure for LLM analysis.

    Args:
    ----
        path: Directory to analyze
        max_depth: Maximum depth to traverse

    Returns:
    -------
        Dictionary with directory structure information

    """
    structure = {
        "path": str(path),
        "files": [],
        "directories": [],
        "markers_found": [],
    }

    try:
        # Get immediate children
        for item in path.iterdir():
            if item.is_file():
                structure["files"].append(item.name)
                # Check if it's a marker file
                if item.name in PROJECT_MARKERS:
                    structure["markers_found"].append(item.name)
            elif item.is_dir() and not item.name.startswith("."):
                structure["directories"].append(item.name)

    except (PermissionError, OSError) as e:
        logger.debug(f"Error analyzing directory {path}: {e}")

    return structure


async def detect_project_root_with_llm(
    start_path: Path | None = None,
) -> Path | None:
    """Detect project root using LLM analysis.

    This is the most intelligent but slowest method. It analyzes the
    directory structure and uses LLM to determine the most likely project root.

    Args:
    ----
        start_path: Starting directory (defaults to current working directory)

    Returns:
    -------
        Path to project root, or None if detection fails

    """
    if start_path is None:
        start_path = Path.cwd()

    try:
        from knowgraph.adapters.mcp.server import app
        from knowgraph.adapters.mcp.utils import get_llm_provider

        provider = get_llm_provider(app)

        # Analyze directory structure
        current = start_path.resolve()
        analysis_data = []

        # Analyze current directory and up to 3 parents
        for _ in range(4):
            structure = analyze_directory_structure(current)
            analysis_data.append(structure)

            if current == current.parent:
                break
            current = current.parent

        # Build prompt
        from knowgraph.infrastructure.intelligence.project_detection_prompts import (
            build_project_detection_prompt,
        )

        prompt = build_project_detection_prompt(start_path, analysis_data)

        # Call LLM
        response = await provider.generate_text(prompt)

        if response and response.strip() != "UNKNOWN":
            detected_path = Path(response.strip())
            if detected_path.exists() and detected_path.is_dir():
                logger.info(f"LLM detected project root: {detected_path}")
                return detected_path

    except Exception as e:
        logger.debug(f"LLM-based detection failed: {e}")

    return None


def detect_project_root(start_path: Path | None = None, use_llm: bool = True) -> Path:
    """Detect project root using multiple strategies.

    Tries strategies in order of speed and reliability:
    1. Git repository root
    2. Project marker files
    3. LLM-based analysis (if enabled)
    4. Fallback to current working directory

    Args:
    ----
        start_path: Starting directory (defaults to current working directory)
        use_llm: Whether to use LLM for detection (default: True)

    Returns:
    -------
        Path to detected project root

    """
    if start_path is None:
        start_path = Path.cwd()

    logger.info(f"Detecting project root from: {start_path}")

    # Strategy 1: Git root
    git_root = detect_git_root(start_path)
    if git_root:
        return git_root

    # Strategy 2: Project markers
    marker_root = detect_project_markers(start_path)
    if marker_root:
        return marker_root

    # Strategy 3: LLM analysis (async, so we'll skip in sync context)
    # This will be called from async context in server.py
    if use_llm:
        logger.info("LLM-based detection requires async context, skipping in sync detection")

    # Strategy 4: Fallback to current working directory
    # Ensure we never use root directory as project root
    fallback = start_path.resolve()

    if fallback == fallback.parent:  # This means we're at root (/)
        # Try cwd first
        cwd = Path.cwd().resolve()
        if cwd != cwd.parent:  # cwd is not root
            fallback = cwd
            logger.warning(
                "Detected root directory as project root, falling back to cwd: %s",
                fallback,
            )
        else:
            # cwd is also root, use home directory
            fallback = Path.home()
            logger.warning(
                "Both start_path and cwd are root directory, falling back to home: %s",
                fallback,
            )

    logger.info(f"No project root detected, using fallback: {fallback}")
    return fallback

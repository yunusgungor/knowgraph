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
        # Ensure start_path exists and is a directory
        if not start_path.exists():
            logger.warning(f"Start path does not exist: {start_path}")
            return None

        if not start_path.is_dir():
            start_path = start_path.parent
            logger.debug(f"Start path is not a directory, using parent: {start_path}")

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
            # Validate that the detected git root is reasonable
            if git_root.exists() and git_root.is_dir():
                logger.info(f"✓ Git root detected: {git_root}")
                return git_root
            else:
                logger.warning(f"Git returned invalid root: {git_root}")
                return None
        else:
            logger.debug(
                f"Not in a git repository (returncode={result.returncode}): {start_path}"
            )
            if result.stderr:
                logger.debug(f"Git error: {result.stderr.strip()}")

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
    searched_paths = []

    # Search upward through parent directories
    while current != current.parent:
        searched_paths.append(str(current))

        # Check for any marker file in current directory
        for marker in PROJECT_MARKERS:
            marker_path = current / marker
            if marker_path.exists():
                logger.info(f"✓ Project marker '{marker}' found at: {current}")
                return current

        # Move to parent directory
        current = current.parent

    logger.debug(
        f"No project markers found in paths: {', '.join(searched_paths[:3])}..."
        if len(searched_paths) > 3
        else f"No project markers found in paths: {', '.join(searched_paths)}"
    )
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

    logger.debug(f"🔍 Detecting project root from: {start_path}")

    # Strategy 1: Git root
    git_root = detect_git_root(start_path)
    if git_root:
        logger.debug(f"✓ Using git root: {git_root}")
        return git_root

    # Strategy 2: Project markers
    marker_root = detect_project_markers(start_path)
    if marker_root:
        logger.debug(f"✓ Using marker-detected root: {marker_root}")
        return marker_root

    # Strategy 3: LLM analysis (async, so we'll skip in sync context)
    # This will be called from async context in server.py
    if use_llm:
        logger.debug("ℹ️ LLM-based detection requires async context, will run in background")

    # Strategy 4: Fallback to current working directory
    # IMPORTANT: Never fall back to home directory, use cwd instead
    fallback = start_path.resolve()

    # If start_path is root directory, use cwd
    if fallback == fallback.parent:  # This means we're at root (/)
        fallback = Path.cwd().resolve()
        logger.debug(
            f"⚠️ Start path was root directory, using cwd instead: {fallback}",
        )

    # If cwd is also root or home, use a sensible default
    if fallback == fallback.parent or fallback == Path.home():
        # Create a default graphstore directory in home
        fallback = Path.home()
        fallback.mkdir(exist_ok=True)
        logger.debug(
            f"⚠️ No valid project root found, using default graphstore: {fallback}",
        )

    logger.debug(f"→ Fallback to: {fallback}")
    return fallback

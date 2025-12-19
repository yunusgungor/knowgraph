"""Fast file filtering for indexing optimization."""

from pathlib import Path

# Patterns to skip (folders/paths)
SKIP_PATTERNS = {
    "__pycache__",
    ".git",
    ".pytest_cache",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    "htmlcov",
    "coverage",
    ".eggs",
    "*.egg-info",
    ".indexing_cache",
    "graphstore",
}

# Extensions to skip
SKIP_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dylib",
    ".dll",
    ".log",
    ".tmp",
    ".cache",
    ".lock",
    ".swp",
    ".swo",
    ".bak",
    ".orig",
}

# Maximum file size (1MB)
MAX_FILE_SIZE = 1_000_000


def should_skip_file(file_path: Path) -> bool:
    """Fast file filtering to skip unnecessary files.

    Args:
        file_path: Path to check

    Returns:
        True if file should be skipped
    """
    path_str = str(file_path)

    # Skip by path patterns
    for pattern in SKIP_PATTERNS:
        if pattern in path_str:
            return True

    # Skip by extension
    if file_path.suffix in SKIP_EXTENSIONS:
        return True

    # Skip if doesn't exist
    if not file_path.exists():
        return True

    # Skip if not a file
    if not file_path.is_file():
        return True

    try:
        # Skip empty files
        file_size = file_path.stat().st_size
        if file_size == 0:
            return True

        # Skip very large files
        if file_size > MAX_FILE_SIZE:
            return True
    except Exception:
        return True

    return False


def filter_files(files: list[Path]) -> list[Path]:
    """Filter list of files, removing those that should be skipped.

    Args:
        files: List of file paths

    Returns:
        Filtered list of file paths
    """
    return [f for f in files if not should_skip_file(f)]

"""Code file detection and classification for Joern integration.

This module automatically detects code files in repositories and determines
when CPG generation is worthwhile for code analysis.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CodeFile:
    """Represents a detected code file."""

    path: Path
    language: str
    lines_of_code: int
    size_bytes: int


class CodeFileDetector:
    """Detect and classify code files for Joern CPG generation."""

    # Supported languages mapped to file extensions
    SUPPORTED_LANGUAGES = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".c": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".rb": "ruby",
        ".php": "php",
        ".cs": "csharp",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
    }

    # Directories to exclude from scanning
    EXCLUDED_DIRS = {
        "node_modules",
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "env",
        "build",
        "dist",
        "target",
        ".pytest_cache",
        ".tox",
        "coverage",
        ".next",
        ".nuxt",
    }

    # Minimum thresholds for CPG generation
    MIN_FILES = 5
    MIN_TOTAL_LOC = 100

    def detect_code_files(self, path: Path) -> list[CodeFile]:
        """Detect all supported code files in directory tree.

        Args:
            path: Root directory to scan

        Returns:
            List of detected code files
        """
        if not path.exists():
            return []

        code_files = []

        # Single file
        if path.is_file():
            code_file = self._try_classify_file(path)
            if code_file:
                code_files.append(code_file)
            return code_files

        # Directory tree
        for file_path in path.rglob("*"):
            # Skip if in excluded directory
            if any(excluded in file_path.parts for excluded in self.EXCLUDED_DIRS):
                continue

            # Skip non-files
            if not file_path.is_file():
                continue

            # Try to classify
            code_file = self._try_classify_file(file_path)
            if code_file:
                code_files.append(code_file)

        return code_files

    def _try_classify_file(self, path: Path) -> Optional[CodeFile]:
        """Try to classify a file as a supported code file.

        Args:
            path: File path to classify

        Returns:
            CodeFile if supported, None otherwise
        """
        suffix = path.suffix.lower()

        # Check if supported
        language = self.SUPPORTED_LANGUAGES.get(suffix)
        if not language:
            return None

        try:
            # Get file stats
            size_bytes = path.stat().st_size

            # Count lines (for LOC metric)
            with open(path, encoding="utf-8", errors="ignore") as f:
                lines = sum(1 for line in f if line.strip())

            return CodeFile(
                path=path,
                language=language,
                lines_of_code=lines,
                size_bytes=size_bytes
            )
        except Exception:
            # Skip files that can't be read
            return None

    def should_generate_cpg(self, code_files: list[CodeFile]) -> bool:
        """Determine if CPG generation is worthwhile.

        Args:
            code_files: List of detected code files

        Returns:
            True if CPG should be generated
        """
        if not code_files:
            return False

        # Check minimum file count
        if len(code_files) < self.MIN_FILES:
            return False

        # Check minimum total LOC
        total_loc = sum(f.lines_of_code for f in code_files)
        return not total_loc < self.MIN_TOTAL_LOC

    def get_statistics(self, code_files: list[CodeFile]) -> dict:
        """Get statistics about detected code files.

        Args:
            code_files: List of detected code files

        Returns:
            Dictionary with statistics
        """
        if not code_files:
            return {
                "total_files": 0,
                "total_loc": 0,
                "languages": {},
                "total_size_mb": 0
            }

        # Count by language
        language_counts = {}
        language_loc = {}
        for code_file in code_files:
            lang = code_file.language
            language_counts[lang] = language_counts.get(lang, 0) + 1
            language_loc[lang] = language_loc.get(lang, 0) + code_file.lines_of_code

        total_size = sum(f.size_bytes for f in code_files)

        return {
            "total_files": len(code_files),
            "total_loc": sum(f.lines_of_code for f in code_files),
            "languages": {
                lang: {
                    "files": language_counts[lang],
                    "loc": language_loc[lang]
                }
                for lang in language_counts
            },
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }

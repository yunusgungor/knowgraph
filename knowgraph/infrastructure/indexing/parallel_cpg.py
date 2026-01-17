"""Parallel CPG generation for large repositories.

Splits large codebases into chunks and generates CPGs in parallel.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ParallelCPGGenerator:
    """Generate CPGs in parallel for large repositories."""

    def __init__(self, max_workers: int = 4):
        """Initialize parallel CPG generator.

        Args:
            max_workers: Maximum number of parallel workers
        """
        self.max_workers = max_workers

    def split_by_language(self, code_files: list) -> dict:
        """Split code files by programming language.

        Args:
            code_files: List of CodeFile objects

        Returns:
            Dictionary of language -> list of files
        """
        by_language = {}

        for code_file in code_files:
            # Handle both CodeFile objects and Path objects
            if hasattr(code_file, "language"):
                lang = code_file.language
            else:
                lang = "unknown"

            if lang not in by_language:
                by_language[lang] = []

            by_language[lang].append(code_file)

        return by_language

    def should_use_parallel(self, code_files: list) -> bool:
        """Determine if parallel generation is worthwhile.

        Args:
            code_files: List of code files

        Returns:
            True if parallel generation recommended
        """
        # Use parallel for 50+ files or multiple languages
        if len(code_files) >= 50:
            return True

        by_lang = self.split_by_language(code_files)
        if len(by_lang) >= 3:  # 3+ languages
            return True

        return False

    def generate_parallel(
        self,
        code_files: list,
        output_dir: Path,
        timeout: int = 300
    ) -> list[Path]:
        """Generate CPGs in parallel by language.

        Args:
            code_files: List of code files
            output_dir: Directory for output CPGs
            timeout: Timeout per CPG generation

        Returns:
            List of generated CPG paths
        """
        from knowgraph.core.joern import JoernProvider

        if not self.should_use_parallel(code_files):
            logger.info("Parallel generation not needed - using single CPG")
            return []

        by_language = self.split_by_language(code_files)

        logger.info(f"Generating CPGs in parallel for {len(by_language)} languages")

        output_dir.mkdir(parents=True, exist_ok=True)

        cpg_paths = []

        def generate_for_language(lang: str, files: list) -> Optional[Path]:
            """Generate CPG for a specific language."""
            try:
                logger.info(f"Generating CPG for {lang} ({len(files)} files)")

                # Create temp directory with language files
                import tempfile
                with tempfile.TemporaryDirectory() as tmpdir:
                    lang_dir = Path(tmpdir) / lang
                    lang_dir.mkdir()

                    # Copy/symlink files (simplified - just use original paths)
                    provider = JoernProvider()

                    # For now, generate CPG for first file's directory
                    # Full implementation would create proper language-specific dirs
                    if files:
                        first_file = files[0]
                        if hasattr(first_file, "path"):
                            source_dir = first_file.path.parent
                        else:
                            source_dir = first_file.parent

                        cpg_path = provider.generate_cpg(source_dir, timeout=timeout)

                        # Move to output dir
                        final_path = output_dir / f"cpg_{lang}.bin"
                        import shutil
                        shutil.copy2(cpg_path, final_path)

                        logger.info(f"Generated CPG for {lang}: {final_path}")
                        return final_path

                return None

            except Exception as e:
                logger.error(f"Failed to generate CPG for {lang}: {e}")
                return None

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(generate_for_language, lang, files): lang
                for lang, files in by_language.items()
            }

            for future in as_completed(futures):
                lang = futures[future]
                try:
                    cpg_path = future.result()
                    if cpg_path:
                        cpg_paths.append(cpg_path)
                except Exception as e:
                    logger.error(f"Parallel generation failed for {lang}: {e}")

        logger.info(f"Generated {len(cpg_paths)} CPGs in parallel")

        return cpg_paths

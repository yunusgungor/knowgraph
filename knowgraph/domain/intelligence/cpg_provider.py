"""Directory-level CPG provider for the indexing pipeline.

Replaces per-chunk CPG generation with shared per-directory CPGs. Joern-parse
runs once per language group (multi-language repos get one CPG per language),
and per-file entity extraction queries the matching CPG via native Joern DSL.

Generated CPGs are persisted to ``<graph_path>/metadata/cpg.bin`` when the
directory is single-language so the query-time layer and
code_index_integration can reuse them instead of re-generating.
"""

import logging
from pathlib import Path

from knowgraph.core.joern.provider import JoernProvider
from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor
from knowgraph.domain.intelligence.provider import Entity

logger = logging.getLogger(__name__)


# CodeFileDetector.SUPPORTED_LANGUAGES value -> joern-parse --language value.
# Values not listed (e.g. rust) have no Joern frontend and are skipped (AST
# fallback). Joern's --language is case-insensitive.
JOERN_LANGUAGE_ALIASES = {
    "python": "pythonsrc",
    "javascript": "jssrc",
    "typescript": "jssrc",
    "c": "c",
    "cpp": "c",  # c2cpg handles both C and C++
    "java": "javasrc",
    "go": "golang",
    "csharp": "csharpsrc",
    "ruby": "rubysrc",
    "php": "php",
    "kotlin": "kotlin",
    "swift": "swiftsrc",
    "scala": "scala2cpg",
}


class CPGProvider:
    """Manage shared per-language CPGs for a directory and query them per file.

    A single instance lives for the duration of one ``SmartGraphBuilder.build``
    call. The first ``ensure_cpg`` generates (or loads) one CPG per detected
    language; subsequent file lookups reuse the matching language's CPG.
    """

    def __init__(self, graph_path: Path | None = None):
        self.provider = JoernProvider()
        self.graph_path = graph_path
        self._cpg_by_lang: dict[str, Path] = {}
        self._executors: dict[str, JoernQueryExecutor] = {}
        self._file_lang: dict[str, str] = {}  # file basename -> language
        self._primary_cpg: Path | None = None  # single-language: the CPG

    def ensure_cpg(self, directory: Path) -> Path:
        """Generate (or reuse) a CPG for ``directory``.

        One directory-level CPG is generated per Joern-supported language.
        Joern's auto-detection can miss languages in mixed repositories, so
        each language is parsed with its explicit frontend alias. This still
        avoids per-chunk generation while keeping per-file entity extraction
        correct for mixed Python/JS/etc. projects.

        Args:
            directory: Source code directory to index.

        Returns:
            Path to the primary cpg.bin, or an empty Path when no CPG exists.
        """
        if self._primary_cpg is not None:
            return self._primary_cpg

        # Populate _file_lang (cheap: filename scan) so _cpg_for_file can
        # resolve per-file entities against the matching language CPG.
        groups = self._detect_language_groups(directory)
        if not groups:
            # No Joern-supported files detected; nothing to do.
            logger.info("No Joern-supported files detected, skipping directory CPG")
            return Path()

        for lang in sorted(groups):
            alias = JOERN_LANGUAGE_ALIASES[lang]
            try:
                cpg_path = self.provider.generate_cpg(
                    repo_path=directory,
                    language=alias,
                )
            except Exception as e:
                logger.warning(f"CPG generation failed for {lang}: {e}")
                continue

            self._cpg_by_lang[lang] = cpg_path
            self._executors[lang] = self.provider._executor()
            if self._primary_cpg is None:
                self._primary_cpg = cpg_path
            logger.info(f"✅ Directory CPG ({lang}): {cpg_path}")

        if self._primary_cpg is not None and len(self._cpg_by_lang) == 1:
            self._persist(self._primary_cpg, directory)

        return self._primary_cpg or Path()

    def _detect_language_groups(self, directory: Path) -> dict[str, list[Path]]:
        """Group supported code files in ``directory`` by language."""
        from knowgraph.infrastructure.indexing.code_file_detector import CodeFileDetector

        detector = CodeFileDetector()
        code_files = detector.detect_code_files(directory)

        groups: dict[str, list[Path]] = {}
        for cf in code_files:
            lang = cf.language
            if lang not in JOERN_LANGUAGE_ALIASES:
                continue  # no Joern frontend (e.g. rust) -> AST fallback
            groups.setdefault(lang, []).append(cf.path)
            self._file_lang[cf.path.name] = lang

        return groups

    def get_cpg_for_language(self, language: str) -> Path | None:
        """Return the CPG path for a given language, or None."""
        return self._cpg_by_lang.get(language)

    def executor(self, language: str | None = None) -> JoernQueryExecutor:
        """Return a JoernQueryExecutor for the given language (or primary)."""
        if language is not None and language in self._executors:
            return self._executors[language]
        if self._executors:
            # Primary language executor
            return self._executors[next(iter(self._cpg_by_lang))]
        # Fallback: provider's memoized executor (CPG generated outside).
        return self.provider._executor()

    def _cpg_for_file(self, rel_path: str) -> tuple[Path, JoernQueryExecutor] | None:
        """Resolve the CPG + executor for a file by its basename's language."""
        name = Path(rel_path).name
        lang = self._file_lang.get(name)
        if lang and lang in self._cpg_by_lang:
            return self._cpg_by_lang[lang], self._executors[lang]
        if self._primary_cpg is not None and self._cpg_by_lang:
            return self._primary_cpg, self.executor()
        return None

    def extract_entities_for_file(self, rel_path: str) -> list[Entity]:
        """Extract per-file entities from the matching language CPG.

        Runs native Joern DSL queries filtered by the file's basename. Joern
        stores CPG filenames as basenames (e.g. ``a.py``), so we match on the
        basename of ``rel_path``.

        Args:
            rel_path: File path relative to the repo root (e.g. ``src/a.py``).

        Returns:
            List of Entity for the file's methods, calls, and identifiers.
        """
        resolved = self._cpg_for_file(rel_path)
        if resolved is None:
            return []
        cpg_path, execr = resolved
        name = Path(rel_path).name
        entities: list[Entity] = []

        # Single combined native query. JoernQueryExecutor starts a JVM per
        # query, so merging method/call/identifier extraction into ONE query
        # is ~3x cheaper than three separate queries. Results are prefixed:
        # DEF| (method/definition), CALL| (call), REF| (identifier/reference).
        # filename() must match the basename as a regex against the FULL path:
        # joern-parse stores file names like "knowgraph/config.py", so an exact
        # basename match returns nothing (verified: 0 vs 62 results).
        query = (
            f'cpg.method.where(_.filename(".*{name}")).map(m => "DEF|" + m.name).l ++ '
            f'cpg.call.where(_.method.filename(".*{name}")).map(c => "CALL|" + c.name).l ++ '
            f'cpg.identifier.where(_.method.filename(".*{name}")).name.dedup.map(n => "REF|" + n).l'
        )
        try:
            r = execr.execute_query(cpg_path, query, timeout=120)
        except Exception as e:
            logger.warning(f"Entity extraction failed for {rel_path}: {e}")
            return entities

        seen_calls: set[str] = set()
        for item in r.results:
            raw = item.get("raw", "").strip()
            if raw.startswith("DEF|"):
                mname = raw[4:].strip()
                # Skip module/init wrappers and synthetic names (e.g. JS
                # ":program", Scala "<init>", Python "<module>").
                if mname and not mname.startswith("<") and not mname.startswith(":"):
                    entities.append(
                        Entity(name=mname, type="definition", description=f"Method definition: {mname}")
                    )
            elif raw.startswith("CALL|"):
                cname = raw[5:].strip()
                if cname and not cname.startswith("<operator>") and cname not in seen_calls:
                    seen_calls.add(cname)
                    entities.append(Entity(name=cname, type="call", description=f"Call: {cname}"))
            elif raw.startswith("REF|"):
                iname = raw[4:].strip()
                if iname and not iname.startswith("<operator>"):
                    entities.append(
                        Entity(name=iname, type="reference", description=f"Variable reference: {iname}")
                    )

        return entities

    def _persist(self, cpg_path: Path, directory: Path) -> None:
        """Copy the generated CPG into the graph store metadata dir.

        Best-effort: persist only when a graph_path is known and copying
        fails, log a warning (query layer can regenerate).
        """
        if self.graph_path is None:
            return
        try:
            from knowgraph.infrastructure.indexing.cpg_metadata import save_cpg_metadata

            metadata_dir = self.graph_path / "metadata"
            metadata_dir.mkdir(parents=True, exist_ok=True)
            persistent = metadata_dir / "cpg.bin"
            if cpg_path != persistent:
                import shutil

                shutil.copy2(cpg_path, persistent)
            save_cpg_metadata(self.graph_path, persistent, entities_count=0)
            logger.info(f"Persisted directory CPG to {persistent}")
        except Exception as e:
            logger.warning(f"Directory CPG persistence failed (non-fatal): {e}")

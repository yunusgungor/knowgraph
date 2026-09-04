"""Joern integration provider - CPG generation and entity extraction."""

from __future__ import annotations

import logging
import platform
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import networkx as nx

from knowgraph.core.joern.manager import INSTALL_DIR
from knowgraph.core.joern.types import ExportFormat, JoernCPG, JoernEntity

if TYPE_CHECKING:
    from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

logger = logging.getLogger(__name__)

# Map Joern frontend names to their directory/binary names.
# CodeFileDetector language -> Joern frontend executable name.
_JOERN_LANGUAGE_ALIASES = {
    "python": "pythonsrc",
    "javascript": "jssrc",
    "typescript": "jssrc",
    "c": "c",
    "cpp": "c",
    "java": "javasrc",
    "go": "golang",
    "csharp": "csharpsrc",
    "ruby": "rubysrc",
    "php": "php",
    "kotlin": "kotlin",
    "swift": "swiftsrc",
    "scala": "scala2cpg",
}
# Joern language alias -> frontend executable dir/name under frontends/.
_ALIAS_TO_FRONTEND = {
    "pythonsrc": "pysrc2cpg",
    "jssrc": "jssrc2cpg",
    "javasrc": "javasrc2cpg",
    "golang": "gosrc2cpg",
    "csharpsrc": "csharpsrc2cpg",
    "rubysrc": "rubysrc2cpg",
    "c": "c2cpg",
    "php": "php2cpg",
    "kotlin": "kotlin2cpg",
    "swiftsrc": "swiftsrc2cpg",
    "scala2cpg": "scala2cpg",
}


class JoernNotFoundError(Exception):
    """Raised when Joern CLI is not found."""


class JoernProvider:
    """Joern CPG generator and exporter.

    Handles Joern CLI execution, CPG generation, GraphML export,
    and entity extraction for KnowGraph integration.
    """

    def _joern_cmd(self, name: str) -> str:
        """Return the platform-correct Joern executable path.

        On Windows the Joern frontend scripts are ``.bat`` files (e.g.
        ``joern-parse.bat``); invoking the bare name fails with WinError 193
        (not a valid Win32 application). Linux/macOS use the bare script.
        """
        exe = Path(self.joern_path) / name
        if platform.system() == "Windows":
            bat = exe.with_suffix(".bat")
            if bat.exists():
                return str(bat)
        return str(exe)

    def _joern_subprocess(self, cmd: list[str], **kwargs):
        """Run a Joern command cross-platform.

        On Windows, ``.bat`` frontend scripts cannot be launched directly by
        CreateProcess (they are not PE images); they must go through
        ``cmd.exe /c``. ``subprocess.run([...bat...])`` would raise WinError 193,
        so wrap the command list accordingly.
        """
        if platform.system() == "Windows":
            cmd = ["cmd.exe", "/c", *cmd]
            # Avoid spawning a console window and reduce inherited handles —
            # this prevents _winapi.DuplicateHandle OSErrors when many Joern
            # subprocesses run in quick succession (e.g. under pytest capture).
            kwargs.setdefault("creationflags", getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return subprocess.run(cmd, **kwargs)

    def _detect_dominant_language(self, repo_path: Path) -> str | None:
        """Detect the dominant programming language in a directory.

        Returns a language key that maps to a Joern frontend (e.g. 'python'),
        or None if no supported language is found.
        """
        from knowgraph.infrastructure.indexing.code_file_detector import CodeFileDetector

        detector = CodeFileDetector()
        code_files = detector.detect_code_files(repo_path)
        if not code_files:
            return None

        # Count files per language
        lang_counts: dict[str, int] = {}
        for cf in code_files:
            lang_counts[cf.language] = lang_counts.get(cf.language, 0) + 1

        if not lang_counts:
            return None

        # Return the language with the most files, but only if it has a frontend
        dominant = max(lang_counts, key=lang_counts.get)
        alias = _JOERN_LANGUAGE_ALIASES.get(dominant)
        if alias and alias in _ALIAS_TO_FRONTEND:
            return dominant
        return None

    def __init__(self, joern_path: str | None = None):
        """Initialize Joern provider.

        Args:
        ----
            joern_path: Path to Joern CLI (auto-detected if None)

        Raises:
        ------
            JoernNotFoundError: If Joern CLI not found

        """
        self.joern_path = joern_path or self._find_joern()
        if not self.joern_path:
            raise JoernNotFoundError(
                "Joern CLI not found. Run: knowgraph-setup-joern"
            )
        self._executor_cache: JoernQueryExecutor | None = None
        logger.info(f"Joern found at: {self.joern_path}")

    def _executor(self) -> JoernQueryExecutor:
        """Return a memoized JoernQueryExecutor for this provider."""
        from knowgraph.domain.intelligence.joern_query_executor import JoernQueryExecutor

        if self._executor_cache is None:
            self._executor_cache = JoernQueryExecutor(Path(self.joern_path))
        return self._executor_cache

    def _find_joern(self) -> str | None:
        """Auto-detect Joern installation.

        Checks:
        1. ~/.knowgraph/joern/joern-cli (Default Managed Location)
        2. /usr/local/joern/joern-cli
        3. $PATH (finds executable, returns parent)

        Returns
        -------
            Path to Joern CLI directory (not executable) or None

        """
        # Check 1: KnowGraph installation directory (using constant from manager)
        knowgraph_joern = INSTALL_DIR / "joern-cli"

        if knowgraph_joern.exists() and knowgraph_joern.is_dir():
            return str(knowgraph_joern)

        # Check 2: Common install locations
        common_paths = [
            "/usr/local/joern/joern-cli",
            "/opt/joern/joern-cli",
        ]
        for path in common_paths:
            if Path(path).exists() and Path(path).is_dir():
                return path

        # Check 3: $PATH (find executable, return parent directory)
        try:
            result = subprocess.run(
                ["which" if platform.system() != "Windows" else "where", "joern"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                exe_path = Path(result.stdout.strip().split("\n")[0])
                # Return parent directory (joern-cli)
                return str(exe_path.parent)
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            pass

        return None

    def _generate_cpg_via_frontend(
        self,
        repo_path: Path,
        language: str,
        output_file: Path,
        timeout: int | None = None,
    ) -> Path:
        """Generate a CPG by invoking a language-specific Joern frontend directly.

        This is the Windows-safe path: the outer ``joern-parse.bat`` wrapper
        mis-parses some argument combinations, but the frontend binaries under
        ``frontends/<name>/bin`` preserve argument order.
        """
        alias = _JOERN_LANGUAGE_ALIASES.get(language, language)
        frontend_name = _ALIAS_TO_FRONTEND.get(alias)
        if not frontend_name:
            raise JoernNotFoundError(f"No Joern frontend mapped for language: {language}")

        candidate = Path(self.joern_path) / "frontends" / frontend_name / "bin" / f"{frontend_name}.bat"
        if platform.system() != "Windows" or not candidate.exists():
            candidate = Path(self.joern_path) / "frontends" / frontend_name / "bin" / frontend_name
        if not candidate.exists():
            raise JoernNotFoundError(f"Joern frontend not found: {candidate}")

        if timeout is None:
            from knowgraph.config import JOERN_EXPORT_TIMEOUT

            timeout = JOERN_EXPORT_TIMEOUT

        cmd = [str(candidate), str(repo_path), "--output", str(output_file)]
        logger.info(f"Generating CPG via frontend ({frontend_name}): {' '.join(cmd)}")

        result = self._joern_subprocess(
            cmd,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        if result.returncode != 0:
            logger.error(f"{frontend_name} failed: {result.stderr}")
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout or "", result.stderr
            )

        if not output_file.exists():
            raise FileNotFoundError(f"{frontend_name} reported success, but CPG was not written: {output_file}")

        logger.info(f"✅ CPG generated via frontend: {output_file}")
        return output_file

    def generate_cpg(
        self,
        repo_path: Path,
        language: str | None = None,
        timeout: int | None = None,
    ) -> Path:
        """Generate Code Property Graph using Joern.

        Args:
        ----
            repo_path: Path to source code repository
            language: Language hint (auto-detected if None)
            timeout: Timeout in seconds (defaults to config-derived budget)

        Returns:
        -------
            Path to generated cpg.bin file

        Raises:
        ------
            subprocess.CalledProcessError: If joern-parse fails
            subprocess.TimeoutExpired: If timeout exceeded

        """
        output_path = tempfile.mkdtemp(prefix="joern_cpg_")
        output_file = Path(output_path) / "cpg.bin"

# Default to the export budget for generation too; parsing a repo and
        # exporting a CPG are comparable, long-running Joern operations.
        if timeout is None:
            from knowgraph.config import JOERN_EXPORT_TIMEOUT

            timeout = JOERN_EXPORT_TIMEOUT

        # On Windows, the outer `joern-parse.bat` wrapper corrupts argument
        # parsing (`Unknown argument '0' ...`). Work around it by invoking the
        # language-specific frontend directly. When language is None, auto-detect
        # from the source files and use the dominant language's frontend.
        if platform.system() == "Windows":
            if not language:
                language = self._detect_dominant_language(repo_path)
            if language:
                return self._generate_cpg_via_frontend(repo_path, language, output_file, timeout)

        joern_parse = self._joern_cmd("joern-parse")
        cmd = [joern_parse, str(repo_path), "--output", str(output_file)]

        if language:
            cmd.extend(["--language", language])

        logger.info(f"Generating CPG: {' '.join(cmd)}")

        try:
            # stdout -> DEVNULL, stderr -> PIPE: capturing stdout is unnecessary
            # (joern-parse prints nothing useful) and the extra pipe handles make
            # Windows _winapi.DuplicateHandle fail under pytest's capture.
            result = self._joern_subprocess(
                cmd,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )

            if result.returncode != 0:
                logger.error(f"joern-parse failed: {result.stderr}")
                raise subprocess.CalledProcessError(
                    result.returncode,
                    cmd,
                    result.stdout or "",
                    result.stderr,
                )

            logger.info(f"✅ CPG generated: {output_file}")

            # Honor the configured max CPG size (JOERN_MAX_CPG_SIZE_MB): warn
            # when the produced CPG exceeds the limit so oversized graphs are
            # surfaced instead of silently slowing downstream queries.
            try:
                from knowgraph.config import JOERN_MAX_CPG_SIZE_MB

                size_mb = output_file.stat().st_size / (1024 * 1024)
                if size_mb > JOERN_MAX_CPG_SIZE_MB:
                    logger.warning(
                        f"CPG size {size_mb:.1f}MB exceeds configured limit "
                        f"{JOERN_MAX_CPG_SIZE_MB}MB; consider raising "
                        "KNOWGRAPH_JOERN_MAX_CPG_SIZE_MB or splitting the repo."
                    )
            except Exception:
                pass

            return output_file

        except subprocess.TimeoutExpired:
            logger.error(f"CPG generation timed out after {timeout}s")
            raise

    def export_graphml(self, cpg_path: Path, timeout: int | None = None) -> Path:
        """Export CPG to GraphML format.

        Args:
        ----
            cpg_path: Path to cpg.bin file
            timeout: Timeout in seconds (defaults to ``JOERN_EXPORT_TIMEOUT``)

        Returns:
        -------
            Path to exported GraphML file

        Raises:
        ------
            subprocess.CalledProcessError: If joern-export fails
            subprocess.TimeoutExpired: If timeout exceeded
            FileNotFoundError: If export succeeds but file not found

        """
        if timeout is None:
            from knowgraph.config import JOERN_EXPORT_TIMEOUT

            timeout = JOERN_EXPORT_TIMEOUT

        output_dir = cpg_path.parent
        export_dir = output_dir / "graphml_export"  # Separate directory for export

        # Build joern-export command
        # Note: -o expects a DIRECTORY that DOESN'T EXIST YET in Joern v4.x
        joern_export = self._joern_cmd("joern-export")
        cmd = [
            joern_export,
            "--repr", "all",  # "all" works with GraphML (cpg14 doesn't!)
            "--format", "graphml",
            "-o", str(export_dir),  # Must not exist yet!
            str(cpg_path),
        ]

        logger.info(f"Exporting GraphML: {' '.join(cmd)}")

        try:
            result = self._joern_subprocess(
                cmd,
                timeout=timeout,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
            )

            # Check if command succeeded
            if result.returncode != 0:
                logger.warning(f"joern-export returned {result.returncode}: {result.stderr}")
                # Try alternative: maybe output goes to stdout
                if result.stdout:
                    # Write stdout to file (create a generic name for it)
                    stdout_output_file = output_dir / "stdout_export.graphml"
                    stdout_output_file.write_text(result.stdout)
                    logger.info(f"✅ Created GraphML from stdout: {stdout_output_file}")
                    return stdout_output_file

            # Joern might return non-zero but still create files

            # Joern exports GraphML files (may use .xml or .graphml extension)
            # Return the directory itself - parse_graphml_to_cpg will handle it
            graphml_files = []
            if export_dir.exists():
                graphml_files = list(export_dir.glob("**/*.graphml")) + list(export_dir.glob("**/*.xml"))

            if graphml_files:
                logger.info(f"✅ GraphML exported: {len(graphml_files)} files in {export_dir}")
                # Return export directory - caller will parse all files
                return export_dir

            # No GraphML found - log debug info
            logger.error(f"No GraphML files found in {export_dir}")
            if export_dir.exists():
                logger.error(f"Export directory contents: {list(export_dir.iterdir())}")
            logger.error(f"stdout: {result.stdout[:500] if result.stdout else 'empty'}")
            logger.error(f"stderr: {result.stderr[:500] if result.stderr else 'empty'}")

            raise FileNotFoundError(
                f"GraphML export completed but no .graphml files found in {export_dir}"
            )

        except subprocess.TimeoutExpired:
            logger.error(f"GraphML export timed out after {timeout}s")
            raise

    def parse_graphml_to_cpg(self, graphml_path: Path) -> JoernCPG:
        """Parse GraphML file(s) to CPG structure.

        Joern exports multiple GraphML files (per-method) to a directory.
        This method handles both single files and directories.

        Args:
        ----
            graphml_path: Path to GraphML file or directory containing .graphml files

        Returns:
        -------
            JoernCPG object with nodes, edges, metadata

        """
        logger.info(f"Parsing GraphML: {graphml_path}")

        try:
            # Determine if path is file or directory
            if graphml_path.is_dir():
                # Directory: find all .graphml and .xml files (Joern uses both)
                graphml_files = list(graphml_path.glob("**/*.graphml")) + list(graphml_path.glob("**/*.xml"))
                if not graphml_files:
                    logger.warning(f"No GraphML/XML files found in {graphml_path}")
                    # Return empty CPG
                    return JoernCPG(nodes=[], edges=[], metadata={"num_nodes": 0, "num_edges": 0})

                logger.info(f"Found {len(graphml_files)} GraphML files to merge")

                # Merge all GraphML files into single graph
                # Use MultiDiGraph because Joern exports multigraphs (multiple edges between same nodes)
                merged_graph = nx.MultiDiGraph()
                for gml_file in graphml_files:
                    try:
                        subgraph = nx.read_graphml(str(gml_file))
                        # Merge nodes and edges
                        merged_graph = nx.compose(merged_graph, subgraph)
                        logger.debug(f"Merged {len(subgraph.nodes())} nodes from {gml_file.name}")
                    except Exception as e:
                        logger.warning(f"Failed to parse {gml_file.name}: {e}")
                        continue

                graph = merged_graph

            else:
                # Single file
                graph = nx.read_graphml(str(graphml_path))

            # Extract nodes
            nodes = []
            for node_id, node_data in graph.nodes(data=True):
                nodes.append({
                    "id": node_id,
                    **node_data,
                })

            # Extract edges
            edges = []
            for source, target, edge_data in graph.edges(data=True):
                edges.append({
                    "source": source,
                    "target": target,
                    **edge_data,
                })

            # Metadata
            metadata = {
                "num_nodes": len(nodes),
                "num_edges": len(edges),
                "source_file": str(graphml_path),
            }

            logger.info(f"✅ Parsed {len(nodes)} nodes, {len(edges)} edges")
            return JoernCPG(nodes=nodes, edges=edges, metadata=metadata)

        except Exception as e:
            logger.error(f"GraphML parsing failed: {e}")
            raise

    def export_cpg(
        self,
        cpg_path: Path,
        format: ExportFormat = ExportFormat.GRAPHML,
        output_path: Path | None = None,
        timeout: int = 300,
    ) -> Path:
        """Export CPG in various formats.

        Args:
        ----
            cpg_path: Path to CPG binary (.bin file)
            format: Export format (GraphML, GraphSON, Neo4jCSV, DOT)
            output_path: Output directory (auto-generated if None)
            timeout: Export timeout in seconds

        Returns:
        -------
            Path to exported file or directory

        """
        # Determine output directory
        if output_path:
            output_dir = output_path
        else:
            output_dir = cpg_path.parent / f"export_{format.value}"

        # joern-export refuses an output directory that already exists and
        # creates it itself, so only ensure the parent exists.
        output_dir.parent.mkdir(parents=True, exist_ok=True)

        # Build joern-export command
        joern_export = self._joern_cmd("joern-export")

        cmd = [joern_export]
        # `--repr all` is required for graphml/graphson/neo4jcsv on joern 4.x
        # (the default cpg14 repr isn't supported for export); DOT keeps the
        # default repr, which emits one file per method.
        if format != ExportFormat.DOT:
            cmd += ["--repr", "all"]
        cmd += ["--format", format.value, "-o", str(output_dir), str(cpg_path)]

        logger.info(f"Exporting CPG to {format.value}: {' '.join(cmd)}")

        try:
            result = self._joern_subprocess(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.joern_path),
                stdin=subprocess.DEVNULL,
            )

            if result.returncode != 0:
                logger.error(f"Export failed: {result.stderr}")
                raise subprocess.CalledProcessError(
                    result.returncode,
                    cmd,
                    result.stdout,
                    result.stderr,
                )

            # Find exported file(s) — missing files are a real failure, not a
            # silent success.
            exported_files: list[Path] = []

            if format == ExportFormat.GRAPHML:
                exported_files = list(output_dir.glob("*.graphml")) + list(output_dir.glob("*.xml"))
            elif format == ExportFormat.GRAPHSON:
                exported_files = list(output_dir.glob("*.json"))
            elif format == ExportFormat.NEO4JCSV:
                exported_files = list(output_dir.glob("*.csv"))
            elif format == ExportFormat.DOT:
                exported_files = list(output_dir.glob("*.dot"))

            if not exported_files:
                raise FileNotFoundError(
                    f"Export completed but no {format.value} files found in {output_dir}"
                )

            logger.info(f"✅ Exported to {format.value}: {len(exported_files)} files")
            return exported_files[0] if len(exported_files) == 1 else output_dir

        except subprocess.TimeoutExpired:
            logger.error(f"Export timeout after {timeout}s")
            raise
        except Exception as e:
            logger.error(f"Export failed: {e}")
            raise

    def extract_entities_from_cpg(self, cpg: JoernCPG) -> list[JoernEntity]:
        """Extract KnowGraph entities from Joern CPG.

        Converts CPG nodes to KnowGraph-compatible entities.

        Args:
        ----
            cpg: Joern CPG object

        Returns:
        -------
            List of JoernEntity objects

        """
        entities = []

        for node in cpg.nodes:
            # Joern uses 'labelV' for node type (not 'label')
            node_type = node.get("labelV", node.get("label", "")).upper()
            # Try NAME first, then CODE for node name
            node_name = node.get("NAME", node.get("CODE", node.get("FULL_NAME", "")))

            # Skip if no name
            if not node_name:
                continue

            # Map Joern node types to KnowGraph entity types
            if node_type in ["METHOD", "FUNCTION"]:
                entities.append(JoernEntity(
                    name=node_name,
                    type="definition",
                    description=f"Function definition: {node_name}",
                ))
            elif node_type in ["CALL"]:
                entities.append(JoernEntity(
                    name=node_name,
                    type="call",
                    description=f"Function call: {node_name}",
                ))
            elif node_type in ["IDENTIFIER", "LOCAL"]:
                entities.append(JoernEntity(
                    name=node_name,
                    type="reference",
                    description=f"Variable reference: {node_name}",
                ))
            elif node_type in ["IMPORT"]:
                entities.append(JoernEntity(
                    name=node_name,
                    type="import",
                    description=f"Import: {node_name}",
                ))

        logger.info(f"✅ Extracted {len(entities)} entities from CPG")
        return entities

    def run_security_scan(self, cpg_path: Path) -> dict:
        """Run security scan using PolicyEngine."""
        # Delayed import to avoid circular dependency
        from knowgraph.application.security.policy_engine import PolicyEngine
        engine = PolicyEngine()
        violations = engine.validate_policies(cpg_path)

        # Convert to dict format expected by CodeQueryHandler
        return {"violations": [
            {
                "rule_name": v.policy.name,
                "description": v.description,
                "severity": v.severity.name,
                "message": v.description,
                "file_path": str(v.location),
                "line_number": 0
            }
            for v in violations
        ]}

    def find_dead_code(self, cpg_path: Path) -> dict:
        """Find dead code using DominanceAnalyzer."""
        # Delayed import
        from knowgraph.application.analysis.dominance_analyzer import DominanceAnalyzer
        analyzer = DominanceAnalyzer()
        dead_methods = analyzer.find_dead_code(cpg_path)
        # CodeQueryHandler expects simple list of names in 'unreachable_methods'
        return {"unreachable_methods": [m.get("name") for m in dead_methods if isinstance(m, dict)]}

    def analyze_call_graph(self, cpg_path: Path, analysis_type: str = "validate") -> dict:
        """Analyze call graph using CallGraphAnalyzer."""
        # Delayed import
        from knowgraph.application.analysis.call_graph_analyzer import CallGraphAnalyzer
        analyzer = CallGraphAnalyzer()

        if analysis_type == "validate":
            result = analyzer.validate_call_graph(cpg_path)
            # Handle the named tuple result
            return {
                "is_valid": result.is_valid,
                "total_methods": result.total_methods,
                "call_edges": result.call_edges,
                "entry_points": result.entry_points
            }
        elif analysis_type == "recursive":
             recursive_methods = analyzer.find_recursive_calls(cpg_path)
             return {"recursive_methods": recursive_methods}
        return {}

    def find_call_chains(
        self,
        cpg_path: Path,
        from_pattern: str,
        to_pattern: str,
    ) -> list[list[str]]:
        """Find call chains between methods."""
        from knowgraph.application.analysis.call_graph_analyzer import CallGraphAnalyzer
        analyzer = CallGraphAnalyzer()
        return analyzer.find_call_chains(cpg_path, from_pattern, to_pattern)

    def analyze_method_callers(
        self,
        cpg_path: Path,
        method_pattern: str,
    ) -> dict:
        """Analyze who calls a specific method."""
        from knowgraph.application.analysis.call_graph_analyzer import CallGraphAnalyzer
        analyzer = CallGraphAnalyzer()
        return analyzer.analyze_method_callers(cpg_path, method_pattern)

    def analyze_complexity(self, cpg_path: Path, method_pattern: str) -> dict:
        """Calculate cyclomatic complexity for methods."""
        # Calculate complexity: control structures + 1
        query = f"""
        cpg.method.name("{method_pattern}").map{{ m =>
           val complexity = m.controlStructure.size + 1
           s"${{m.name}}:$complexity"
        }}.l
        """
        result = self._executor().execute_query(cpg_path, query)

        complexity_data = []
        for item in result.results:
            raw = item.get("raw", "")
            if ":" in raw:
                name, score = raw.split(":")
                complexity_data.append({"method": name, "score": int(score)})

        return {"complexity": complexity_data}

    def get_ast(self, cpg_path: Path, method_pattern: str) -> str:
        """Get Abstract Syntax Tree (DOT format) for a method."""
        query = f"""
        cpg.method.name("{method_pattern}").dotAst.headOption.getOrElse("AST not found")
        """
        result = self._executor().execute_query(cpg_path, query)

        # Extract the DOT string
        if result.results:
            return result.results[0].get("raw", "AST not found")
        return "AST not found"

    def get_type_hierarchy(self, cpg_path: Path, type_pattern: str) -> dict:
        """Get base types and derived types for a class/structure."""
        # Revised simpler query for robust parsing
        simple_query = f"""
        val target = cpg.typeDecl.name("{type_pattern}").headOption
        target match {{
            case Some(t) =>
                val base = t.inheritsFromTypeFullName.mkString(",")
                val derived = cpg.typeDecl.where(_.inheritsFromTypeFullName(t.fullName)).name.mkString(",")
                s"BASE:$base|DERIVED:$derived"
            case None => "NOT_FOUND"
        }}
        """
        result = self._executor().execute_query(cpg_path, simple_query)
        raw = result.results[0].get("raw", "") if result.results else ""

        if raw == "NOT_FOUND":
            return {"found": False}

        hierarchy = {"found": True, "base": [], "derived": []}
        if "BASE:" in raw and "|DERIVED:" in raw:
            parts = raw.split("|DERIVED:")
            base_part = parts[0].replace("BASE:", "")
            derived_part = parts[1]

            hierarchy["base"] = [x.strip() for x in base_part.split(",") if x.strip()]
            hierarchy["derived"] = [x.strip() for x in derived_part.split(",") if x.strip()]

        return hierarchy

    def get_cfg(self, cpg_path: Path, method_pattern: str) -> str:
        """Get Control Flow Graph (DOT format) for a method."""
        executor = self._executor()

        query = f"""
        cpg.method.name("{method_pattern}").dotCfg.headOption.getOrElse("CFG not found")
        """
        result = executor.execute_query(cpg_path, query)

        if result.results:
            return result.results[0].get("raw", "CFG not found")
        return "CFG not found"

    def get_pdg(self, cpg_path: Path, method_pattern: str) -> str:
        """Get Program Dependence Graph (DOT format) for a method."""
        executor = self._executor()

        query = f"""
        cpg.method.name("{method_pattern}").dotPdg.headOption.getOrElse("PDG not found")
        """
        result = executor.execute_query(cpg_path, query)

        if result.results:
            return result.results[0].get("raw", "PDG not found")
        return "PDG not found"

    def get_cdg(self, cpg_path: Path, method_pattern: str) -> str:
        """Get Control Dependence Graph (DOT format) for a method."""
        executor = self._executor()

        query = f"""
        cpg.method.name("{method_pattern}").dotCdg.headOption.getOrElse("CDG not found")
        """
        result = executor.execute_query(cpg_path, query)

        if result.results:
            return result.results[0].get("raw", "CDG not found")
        return "CDG not found"

    def find_variable_usages(self, cpg_path: Path, var_pattern: str) -> dict:
        """Find where a variable/identifier is used, including filename."""
        executor = self._executor()

        query = f"""
        cpg.identifier.name("{var_pattern}").map{{ i =>
            val method = i.method.name
            val line = i.lineNumber.getOrElse(-1)
            val file = i.method.filename
            s"${{method}}__KG_SEP__${{line}}__KG_SEP__$file"
        }}.dedup.l
        """
        result = executor.execute_query(cpg_path, query)

        usages = []
        for item in result.results:
            raw = item.get("raw", "")
            if "__KG_SEP__" in raw:
                try:
                    parts = raw.split("__KG_SEP__")
                    method = parts[0]
                    line = parts[1]
                    filename = parts[2]
                    usages.append({"method": method, "line": int(line), "filename": filename})
                except Exception:
                     usages.append({"method": "unknown", "line": -1, "filename": "unknown", "raw": raw})
            else:
                 usages.append({"method": "unknown", "line": -1, "filename": "unknown", "raw": raw})

        return {"variable": var_pattern, "usages": usages}

    def perform_slicing(self, cpg_path: Path, var_pattern: str) -> dict:
        """Perform backwards slicing with filename info."""
        executor = self._executor()

        # Slicing logic using REACHABLE BY
        query = f"""
        val target = cpg.identifier.name("{var_pattern}")
        val sources = cpg.call

        target.reachableBy(sources).map{{ c =>
            val method = c.method.name
            val line = c.lineNumber.getOrElse(-1)
            val file = c.method.filename
            val code = c.code.replace("\\"", "'") // Escape quotes
            s"${{method}}__KG_SEP__${{line}}__KG_SEP__${{file}}__KG_SEP__$code"
        }}.dedup.l
        """
        result = executor.execute_query(cpg_path, query)

        slice_lines = []
        for item in result.results:
            raw = item.get("raw", "")
            if "__KG_SEP__" in raw:
                try:
                    parts = raw.split("__KG_SEP__")
                    method = parts[0]
                    line = parts[1]
                    filename = parts[2]
                    code = "__KG_SEP__".join(parts[3:])
                    slice_lines.append({
                        "method": method,
                        "line": int(line),
                        "filename": filename,
                        "code": code
                    })
                except Exception:
                    continue

        return {"variable": var_pattern, "slice": slice_lines}

    def find_literals(self, cpg_path: Path, literal_pattern: str) -> dict:
        """Find hardcoded literals/strings matching a pattern."""
        executor = self._executor()

        # Case-insensitive wildcard search
        query = f"""
        cpg.literal.code("(?i).*{literal_pattern}.*").map{{ l =>
             val code = l.code
             val method = l.method.name.headOption.getOrElse("<unknown>")
             val line = l.lineNumber.getOrElse(-1)
             val file = l.file.name.headOption.getOrElse("<unknown>")
             s"${{method}}__KG_SEP__${{line}}__KG_SEP__${{file}}__KG_SEP__$code"
        }}.dedup.l
        """
        result = executor.execute_query(cpg_path, query)

        literals = []
        for item in result.results:
            raw = item.get("raw", "")
            if "__KG_SEP__" in raw:
                try:
                    parts = raw.split("__KG_SEP__")
                    method = parts[0]
                    line = parts[1]
                    filename = parts[2]
                    code = "__KG_SEP__".join(parts[3:])
                    literals.append({
                        "method": method,
                        "line": int(line),
                        "filename": filename,
                        "code": code
                    })
                except Exception:
                    continue

        return {"pattern": literal_pattern, "literals": literals}

    def find_methods(self, cpg_path: Path, pattern: str) -> dict:
        """Find methods matching a pattern with detailed info."""
        executor = self._executor()

        # Safe string for scala
        safe_pattern = pattern.replace('"', "").replace("'", "")

        # Case-insensitive wildcard search
        query = f"""
        cpg.method.name("(?i).*{safe_pattern}.*").map{{ m =>
            val name = m.name
            val line = m.lineNumber.getOrElse(-1)
            val file = m.filename
            val sig = m.signature
            s"${{name}}__KG_SEP__${{line}}__KG_SEP__${{file}}__KG_SEP__$sig"
        }}.dedup.l
        """
        result = executor.execute_query(cpg_path, query)

        methods = []
        for item in result.results:
            raw = item.get("raw", "") if isinstance(item, dict) else str(item)
            if "__KG_SEP__" in raw:
                try:
                    parts = raw.split("__KG_SEP__")
                    methods.append({
                        "method": parts[0],
                        "line": int(parts[1]),
                        "filename": parts[2],
                        "signature": parts[3]
                    })
                except Exception:
                    continue
        return {"pattern": safe_pattern, "methods": methods}

    def analyze_taint_flow(self, cpg_path: Path, source_pattern: str, sink_pattern: str) -> dict:
        """Trace data flow (taint) from source to sink."""
        executor = self._executor()

        # Robust query using reachableBy
        # Robust query using reachableBy
        # Robust query using reachableBy
        # FIX: Use .contains(...) which is safer and simpler for substring matching than regex
        # FIX: Track flow to BOTH the call arguments AND the call node itself (for builtins/identifiers)

        # Clean pattern for string literal
        # Clean patterns for a Scala string literal: patterns are regex text that
        # may contain backslashes (e.g. re.escape("read(") -> "read\\(") and quotes.
        # Both must be escaped so the embedded Scala string stays valid (an
        # unescaped "\(" raises "invalid escape character" in Scala).
        src_clean = source_pattern.replace("\\", "\\\\").replace('"', '\\"')
        sink_clean = sink_pattern.replace("\\", "\\\\").replace('"', '\\"')

        query = f"""
        def src = cpg.call.filter(c => c.name.contains("{src_clean}") || c.methodFullName.contains("{src_clean}") || c.code.contains("{src_clean}")) ++ cpg.identifier.filter(_.name.contains("{src_clean}"))
        def dst = cpg.call.filter(c => c.name.contains("{sink_clean}") || c.methodFullName.contains("{sink_clean}") || c.code.contains("{sink_clean}")).argument ++ cpg.call.filter(c => c.name.contains("{sink_clean}") || c.methodFullName.contains("{sink_clean}") || c.code.contains("{sink_clean}")) ++ cpg.identifier.filter(_.name.contains("{sink_clean}"))

        dst.reachableByFlows(src).map{{ path =>
            val flow = path.elements.map{{ e =>
                // AstNode has no .method member in Joern 4; it exists only on the
                // concrete node subtypes (Method, Call, Identifier, ...). Resolve
                // the enclosing method via a pattern match so the script compiles.
                // AstNode has no .method member in Joern 4; it exists only on
                // concrete node subtypes (Method, Call, Identifier, ...).
                // Resolve the enclosing method + filename via a pattern match.
                val (method, file) = e match {{
                    case m: Method => (m.name, m.filename)
                    case c: Call => (c.method.name, c.method.filename)
                    case i: Identifier => (i.method.name, i.method.filename)
                    case _ => ("", "")
                }}
                val line = e.lineNumber.getOrElse(-1)
                val code = e.code.replace("\\"", "'")
                s"${{method}}__KG_SEP__${{line}}__KG_SEP__${{file}}__KG_SEP__$code"
            }}.mkString("__KS_FLOW__")
            flow
        }}.dedup.l
        """
        result = executor.execute_query(cpg_path, query)

        flows = []
        for item in result.results:
            raw_flow = item.get("raw", "")
            if "__KS_FLOW__" in raw_flow:
                # Split flow into steps
                steps_raw = raw_flow.split("__KS_FLOW__")
                flow_steps = []
                for step in steps_raw:
                    if "__KG_SEP__" in step:
                        parts = step.split("__KG_SEP__")
                        flow_steps.append({
                            "method": parts[0],
                            "line": int(parts[1]),
                            "filename": parts[2],
                            "code": parts[3]
                        })
                if flow_steps:
                    flows.append(flow_steps)

        return {"source": source_pattern, "sink": sink_pattern, "flows": flows}

    def get_method_params(self, cpg_path: Path, method_pattern: str) -> dict:
        """Get parameters of a method."""
        executor = self._executor()

        query = f"""
        cpg.method.name("{method_pattern}").parameter.map{{ p =>
            val name = p.name
            val type = p.typeFullName
            val index = p.index
            s"${{name}}__KG_SEP__${{type}}__KG_SEP__$index"
        }}.dedup.l
        """
        result = executor.execute_query(cpg_path, query)

        params = []
        for item in result.results:
            raw = item.get("raw", "")
            if "__KG_SEP__" in raw:
                try:
                    parts = raw.split("__KG_SEP__")
                    params.append({
                        "name": parts[0],
                        "type": parts[1],
                        "index": int(parts[2])
                    })
                except Exception:
                    continue
        # Sort by index
        params.sort(key=lambda x: x["index"])
        return {"method": method_pattern, "params": params}

    def get_method_locals(self, cpg_path: Path, method_pattern: str) -> dict:
        """Get local variables defined in a method."""
        executor = self._executor()

        query = f"""
        cpg.method.name("{method_pattern}").local.map{{ l =>
            val name = l.name
            val type = l.typeFullName
            s"${{name}}__KG_SEP__$type"
        }}.dedup.l
        """
        result = executor.execute_query(cpg_path, query)

        locals_ = []
        for item in result.results:
            raw = item.get("raw", "")
            if "__KG_SEP__" in raw:
                 try:
                    parts = raw.split("__KG_SEP__")
                    locals_.append({
                        "name": parts[0],
                        "type": parts[1]
                    })
                 except Exception:
                    continue

        return {"method": method_pattern, "locals": locals_}

    def get_ddg(self, cpg_path: Path, method_pattern: str) -> str:
        """Get Data Dependence Graph (DOT format)."""
        executor = self._executor()

        query = f"""
        cpg.method.name("{method_pattern}").dotDdg.headOption.getOrElse("DDG not found")
        """
        result = executor.execute_query(cpg_path, query)

        if result.results:
            return result.results[0].get("raw", "DDG not found")
        return "DDG not found"

    def find_comments(self, cpg_path: Path, pattern: str) -> dict:
        """Find comments or TODOs matchin pattern."""
        executor = self._executor()

        # Note: 'comment' node type might vary by language/CPG version, but widely supported
        # If unavailable, returns empty
        query = f"""
        cpg.comment.code("(?i).*{pattern}.*").map{{ c =>
            val file = c.file.name.headOption.getOrElse("<unknown>")
            val line = c.lineNumber.getOrElse(-1)
            val content = c.code.replace("\\"", "'")
            s"${{file}}__KG_SEP__${{line}}__KG_SEP__$content"
        }}.dedup.l
        """
        result = executor.execute_query(cpg_path, query)

        comments = []
        for item in result.results:
            raw = item.get("raw", "")
            if "__KG_SEP__" in raw:
                try:
                    parts = raw.split("__KG_SEP__")
                    comments.append({
                        "filename": parts[0],
                        "line": int(parts[1]),
                        "content": parts[2]
                    })
                except Exception:
                    continue

        return {"pattern": pattern, "comments": comments}

    def list_tags(self, cpg_path: Path) -> dict:
        """List all tags in the CPG."""
        executor = self._executor()

        query = "cpg.tag.name.dedup.l"
        result = executor.execute_query(cpg_path, query)

        tags = []
        for item in result.results:
             t = item.get("raw", "").strip()
             if t:
                 tags.append(t)

        return {"tags": sorted(tags)}

    def find_annotations(self, cpg_path: Path, annotation_pattern: str) -> dict:
        """Find methods with specific annotations/decorators."""
        executor = self._executor()

        # Case-insensitive wildcard search
        query = f"""
        cpg.method.filter(_.annotation.name("(?i).*{annotation_pattern}.*")).map{{ m =>
            val name = m.name
            val line = m.lineNumber.getOrElse(-1)
            val file = m.filename
            val annots = m.annotation.name.mkString(", ")
            s"${{name}}__KG_SEP__${{line}}__KG_SEP__${{file}}__KG_SEP__$annots"
        }}.dedup.l
        """
        result = executor.execute_query(cpg_path, query)

        findings = []
        for item in result.results:
            raw = item.get("raw", "")
            if "__KG_SEP__" in raw:
                try:
                    parts = raw.split("__KG_SEP__")
                    findings.append({
                        "method": parts[0],
                        "line": int(parts[1]),
                        "filename": parts[2],
                        "annotations": parts[3]
                    })
                except Exception:
                    continue

        return {"pattern": annotation_pattern, "findings": findings}

    def find_imports(self, cpg_path: Path, import_pattern: str) -> dict:
        """Find imports/dependencies matching a pattern."""
        executor = self._executor()

        # Case-insensitive wildcard search
        query = f"""
        cpg.imports.code("(?i).*{import_pattern}.*").map{{ i =>
            val code = i.code
            val file = i.file.name.headOption.getOrElse("unknown")
            s"${{code}}__KG_SEP__$file"
        }}.dedup.l
        """
        result = executor.execute_query(cpg_path, query)

        imports = []
        for item in result.results:
            raw = item.get("raw", "")
            if "__KG_SEP__" in raw:
                try:
                    parts = raw.split("__KG_SEP__")
                    imports.append({
                        "import": parts[0],
                        "filename": parts[1]
                    })
                except Exception:
                    continue
            else:
                 # Fallback
                 imports.append({"import": raw, "filename": "unknown"})

        return {"pattern": import_pattern, "imports": imports}

    def analyze_structures(self, cpg_path: Path, method_pattern: str) -> dict:
        """Analyze control structures (loops, ifs) in methods."""
        executor = self._executor()

        # Ensure we have a valid pattern, default to all if wildcard passed
        # Joern regex: use (?i) for case insensitive, wrap in .* for partial
        final_pattern = method_pattern if method_pattern == ".*" else f"(?i).*{method_pattern}.*"

        query = f"""
        cpg.method.name("{final_pattern}").map{{ m =>
            val loops = m.controlStructure.filter(x => x.controlStructureType == "FOR" || x.controlStructureType == "WHILE" || x.controlStructureType == "DO").size
            val ifs = m.controlStructure.filter(_.controlStructureType == "IF").size
            val name = m.name
            val line = m.lineNumber.getOrElse(-1)
            val file = m.filename
            s"${{name}}__KG_SEP__${{line}}__KG_SEP__${{file}}__KG_SEP__${{loops}}__KG_SEP__$ifs"
        }}.l
        """
        result = executor.execute_query(cpg_path, query)

        structures = []
        for item in result.results:
            raw = item.get("raw", "")
            if "__KG_SEP__" in raw:
                try:
                    parts = raw.split("__KG_SEP__")
                    structures.append({
                        "method": parts[0],
                        "line": int(parts[1]),
                        "filename": parts[2],
                        "loops": int(parts[3]),
                        "ifs": int(parts[4])
                    })
                except Exception:
                    continue

        return {"pattern": method_pattern, "structures": structures}

    def list_files(self, cpg_path: Path) -> dict:
        """List all source files in the CPG."""
        executor = self._executor()

        query = "cpg.file.name.dedup.l"
        result = executor.execute_query(cpg_path, query)

        files = []
        for item in result.results:
             f = item.get("raw", "").strip()
             if f and f != "<unknown>":
                 files.append(f)

        return {"files": sorted(files)}

    def list_namespaces(self, cpg_path: Path) -> dict:
        """List all namespaces/packages."""
        executor = self._executor()

        query = "cpg.namespace.name.dedup.l"
        result = executor.execute_query(cpg_path, query)

        namespaces = []
        for item in result.results:
             ns = item.get("raw", "").strip()
             if ns and ns != "<global>":
                 namespaces.append(ns)

        return {"namespaces": sorted(namespaces)}

    def list_types(self, cpg_path: Path) -> dict:
        """List all defined types/classes."""
        executor = self._executor()

        query = "cpg.typeDecl.fullName.dedup.l"
        result = executor.execute_query(cpg_path, query)

        types = []
        for item in result.results:
             t = item.get("raw", "").strip()
             if t:
                 types.append(t)

        return {"types": sorted(types)}

    def run_custom_query(self, cpg_path: Path, query: str) -> dict:
        """Execute a raw custom Joern query string."""
        executor = self._executor()

        # Determine if it's a list operation to append .l if missing
        final_query = query.strip()

        result = executor.execute_query(cpg_path, final_query)

        return {
            "query": query,
            "results": [r.get("raw", str(r)) for r in result.results],
            "count": result.node_count
        }

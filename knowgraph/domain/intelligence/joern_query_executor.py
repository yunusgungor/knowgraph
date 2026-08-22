"""Joern Query Executor - Execute native Joern DSL queries.

This module enables KnowGraph to execute native Joern queries directly on CPG binaries,
leveraging Joern's full query language power.
"""

import atexit
import logging
import platform
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from knowgraph.core.joern.process import JoernDaemon

logger = logging.getLogger(__name__)

# Shared persistent Joern REPL across all JoernQueryExecutor instances. All
# analyzers/query paths route through one JVM instead of each spawning its own.
_shared_daemon: "JoernDaemon | None" = None


def _stop_shared_daemon() -> None:
    global _shared_daemon
    if _shared_daemon is not None:
        try:
            _shared_daemon.stop()
        except Exception:
            pass
        _shared_daemon = None


atexit.register(_stop_shared_daemon)


@dataclass
class JoernQueryResult:
    """Result from Joern query execution.

    Attributes
    ----------
        query: Original Joern query string
        results: List of result dictionaries
        execution_time_ms: Query execution time in milliseconds
        node_count: Number of nodes in result
        metadata: Additional metadata (errors, warnings, etc.)

    """

    query: str
    results: list[dict]
    execution_time_ms: float
    node_count: int
    metadata: dict = field(default_factory=dict)

    def __str__(self) -> str:
        """Human-readable summary."""
        return (
            f"JoernQueryResult(\n"
            f"  query: {self.query[:60]}...\n"
            f"  results: {self.node_count} nodes\n"
            f"  time: {self.execution_time_ms:.1f}ms\n"
            f")"
        )


class JoernQueryExecutor:
    """Execute Joern DSL queries on CPG binaries.

    This class provides a bridge to Joern's native query language,
    enabling advanced code analysis beyond what KnowGraph implements.

    Example:
        executor = JoernQueryExecutor()
        result = executor.execute_query(
            cpg_path=Path("cpg.bin"),
            query='cpg.method.name(".*login.*").l'
        )
        print(f"Found {result.node_count} methods")
    """

    def __init__(self, joern_path: Path | None = None, use_daemon: bool | None = None):
        """Initialize executor with Joern installation path.

        Args:
        ----
            joern_path: Path to Joern installation directory
                       (auto-detected if None)
            use_daemon: When True, use a persistent Joern REPL (single JVM)
                       for queries; falls back to one-shot ``--script`` on
                       daemon failure. Defaults to the config flag
                       ``KNOWGRAPH_JOERN_DAEMON``.

        """
        self.joern_path = joern_path or self._find_joern()
        if not self.joern_path:
            raise RuntimeError("Joern not found. Install with: knowgraph-setup-joern")

        if use_daemon is None:
            from knowgraph.config import JOERN_DAEMON_ENABLED

            use_daemon = JOERN_DAEMON_ENABLED
        self.use_daemon = use_daemon
        global _shared_daemon
        self.daemon = None
        if self.use_daemon:
            try:
                if _shared_daemon is None:
                    from knowgraph.core.joern.process import JoernDaemon

                    _shared_daemon = JoernDaemon(self.joern_path)
                self.daemon = _shared_daemon
            except Exception as e:
                logger.warning(f"Joern daemon unavailable, using --script mode: {e}")
                self.daemon = None

        logger.info(f"JoernQueryExecutor initialized: {self.joern_path} (daemon={self.use_daemon})")

    def _find_joern(self) -> Path | None:
        """Auto-detect Joern installation."""
        from knowgraph.config import JOERN_PATH

        # Check configured path first
        if JOERN_PATH:
            joern_cli = Path(JOERN_PATH) / "joern-cli"
            if joern_cli.exists():
                return joern_cli

        # Fallback: check common locations
        common_paths = [
            Path.home() / ".knowgraph" / "joern" / "joern-cli",
            Path("/opt/joern/joern-cli"),
            Path("/usr/local/joern/joern-cli"),
        ]

        for path in common_paths:
            if path.exists():
                return path

        return None

    def execute_query(
        self,
        cpg_path: Path,
        query: str,
        timeout: int | None = None,
    ) -> JoernQueryResult:
        """Execute a Joern query on a CPG.

        Args:
        ----
            cpg_path: Path to CPG binary (.bin file)
            query: Joern query string (e.g., "cpg.method.name.l")
            timeout: Query timeout in seconds (defaults to ``JOERN_TIMEOUT``)

        Returns:
        -------
            JoernQueryResult with parsed results

        Raises:
        ------
            subprocess.TimeoutExpired: If query exceeds timeout
            RuntimeError: If Joern execution fails

        Example:
        -------
            result = executor.execute_query(
                cpg_path=Path("cpg.bin"),
                query='cpg.method.where(_.name("login")).name.l'
            )

        """
        start_time = time.time()

        # Resolve the effective timeout from config when not explicitly given.
        if timeout is None:
            from knowgraph.config import JOERN_TIMEOUT

            timeout = JOERN_TIMEOUT

        # Validate inputs
        if not cpg_path.exists():
            raise FileNotFoundError(f"CPG not found: {cpg_path}")

        # Prefer the persistent daemon (single JVM); fall back to one-shot
        # --script below if the daemon is unavailable or errors.
        if self.daemon is not None:
            try:
                return self._execute_via_daemon(cpg_path, query, timeout, start_time)
            except Exception as e:
                logger.warning(f"Joern daemon query failed, falling back to --script: {e}")

        # Create Joern script
        script_content = self._create_joern_script(cpg_path, query)

        # Write to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".sc",
            delete=False,
            encoding="utf-8"
        ) as script_file:
            script_file.write(script_content)
            script_path = Path(script_file.name)

        try:
            # Execute Joern
            if not self.joern_path:
                 raise RuntimeError("Joern path not configured")

            # Cross-platform: on Windows the frontend is a .bat file that must
            # run through cmd.exe /c (CreateProcess can't launch .bat directly).
            joern_bin = self.joern_path / "joern"
            if platform.system() == "Windows":
                bat = joern_bin.with_suffix(".bat")
                if bat.exists():
                    cmd = ["cmd.exe", "/c", str(bat), "--script", str(script_path)]
                else:
                    cmd = [str(joern_bin), "--script", str(script_path)]
            else:
                cmd = [str(joern_bin), "--script", str(script_path)]

            logger.debug(f"Executing Joern query: {query[:100]}...")

            result = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.joern_path),
            )

            execution_time_ms = (time.time() - start_time) * 1000

            # Parse output
            if result.returncode != 0:
                logger.error(f"Joern query failed: {result.stderr}")
                raise RuntimeError(f"Joern execution failed: {result.stderr}")

            # Extract results from output
            results = self._parse_joern_output(result.stdout)

            return JoernQueryResult(
                query=query,
                results=results,
                execution_time_ms=execution_time_ms,
                node_count=len(results),
                metadata={
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                },
            )

        finally:
            # Clean up temp file
            try:
                script_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete temp script: {e}")

    def execute_dataflow_query(
        self,
        cpg_path: Path,
        source_pattern: str,
        sink_pattern: str,
        max_depth: int = 10,
    ) -> JoernQueryResult:
        """Execute dataflow query using Joern's reachableBy.

        This leverages Joern's optimized dataflow analysis, which is
        more powerful than simple graph traversal.

        Args:
        ----
            cpg_path: Path to CPG binary
            source_pattern: Regex pattern for source methods/calls
            sink_pattern: Regex pattern for sink methods/calls
            max_depth: Maximum path depth (unused, Joern handles this)

        Returns:
        -------
            JoernQueryResult with dataflow paths

        Example:
        -------
            result = executor.execute_dataflow_query(
                cpg_path=Path("cpg.bin"),
                source_pattern=".*gets.*",
                sink_pattern=".*strcpy.*",
            )

        """
        # Construct Joern reachableBy query
        query = f"""
val sources = cpg.call.name("{source_pattern}").l
val sinks = cpg.call.name("{sink_pattern}").l

// Find flows from sources to sinks
val flows = sinks.flatMap {{ sink =>
  sources.flatMap {{ source =>
    sink.reachableBy(source).l
  }}
}}

flows.l
"""

        return self.execute_query(cpg_path, query)

    def _execute_via_daemon(
        self,
        cpg_path: Path,
        query: str,
        timeout: int,
        start_time: float,
    ) -> JoernQueryResult:
        """Run the query on the persistent Joern REPL.

        The daemon returns ``RESULT_ITEM: <value>`` lines (one per result
        item). Reuses ``_parse_joern_item`` for value parsing.
        """
        assert self.daemon is not None
        if not self.daemon.is_running():
            self.daemon.start()

        raw = self.daemon.query(cpg_path, query, timeout=timeout)
        execution_time_ms = (time.time() - start_time) * 1000

        # ``raw`` is the full marker window (REPL echoes + println output +
        # RESULT_ITEM lines). Keep it as stdout so callers that parse
        # ``println``-based stats (e.g. CallGraphAnalyzer) still work.
        results = []
        for line in raw.splitlines():
            line = line.strip()
            if "RESULT_ITEM:" in line:
                item_str = line.split("RESULT_ITEM:", 1)[1].strip()
                results.append(self._parse_joern_item(item_str))

        return JoernQueryResult(
            query=query,
            results=results,
            execution_time_ms=execution_time_ms,
            node_count=len(results),
            metadata={
                "stdout": raw,
                "stderr": "",
                "returncode": 0,
                "transport": "daemon",
            },
        )

    def _create_joern_script(self, cpg_path: Path, query: str) -> str:
        """Create Joern script content.

        Args:
        ----
            cpg_path: Path to CPG binary
            query: Joern query to execute

        Returns:
        -------
            Script content as string

        """
        # Normalize backslashes to forward slashes: Scala string literals treat
        # "\U" etc. in Windows paths (C:\\Users\\...) as invalid escape sequences,
        # which breaks importCpg and yields "No projects loaded".
        cpg_uri = str(cpg_path).replace("\\", "/")
        return f"""
// Load CPG
importCpg("{cpg_uri}")

// Ensure dataflow overlays are present for complete analysis
try {{
  run.ossdataflow
}} catch {{
  case e: Exception => // Ignore if already present or not applicable
}}

// Execute query
val queryResult = {{ {query} }}

// Output results
println("__JOERN_RESULT_START__")

// Convert to string representation
queryResult match {{
  case l: List[_] =>
    l.foreach {{ item =>
      println(s"RESULT_ITEM: $item")
    }}
    println(s"RESULT_COUNT: ${{l.size}}")
  case other =>
    println(s"RESULT_ITEM: $other")
    println("RESULT_COUNT: 1")
}}

println("__JOERN_RESULT_END__")
"""

    def _parse_joern_output(self, output: str) -> list[dict]:
        """Parse Joern output to extract results.

        Args:
        ----
            output: Raw stdout from Joern

        Returns:
        -------
            List of result dictionaries

        """
        results = []

        # Extract content between markers
        if "__JOERN_RESULT_START__" not in output:
            logger.warning("No result markers found in Joern output")
            return results

        try:
            start = output.index("__JOERN_RESULT_START__")
            end = output.index("__JOERN_RESULT_END__")
            result_block = output[start:end]

            # Parse result items
            for line in result_block.split("\n"):
                if line.startswith("RESULT_ITEM:"):
                    item_str = line.replace("RESULT_ITEM:", "").strip()

                    # Try to parse as structured data
                    # Joern outputs like: "Method(name=login, ...)"
                    result_dict = self._parse_joern_item(item_str)
                    results.append(result_dict)

        except (ValueError, IndexError) as e:
            logger.error(f"Failed to parse Joern output: {e}")
            # Fallback: return raw output
            results.append({"raw": output})

        return results

    def _parse_joern_item(self, item_str: str) -> dict:
        """Parse a single Joern result item.

        Args:
        ----
            item_str: String representation of Joern item

        Returns:
        -------
            Dictionary with parsed data

        """
        # Simple parser for Joern output format
        # Example: "Method(name=vulnerable_login, fullName=vulnerable_login)"

        result = {"raw": item_str}

        # Extract type (Method, Call, Identifier, etc.)
        if "(" in item_str:
            type_name = item_str.split("(")[0].strip()
            result["type"] = type_name

            # Extract properties
            props_str = item_str.split("(", 1)[1].rsplit(")", 1)[0]

            # Parse key=value pairs
            for prop in props_str.split(","):
                if "=" in prop:
                    key, value = prop.split("=", 1)
                    result[key.strip()] = value.strip()

        return result

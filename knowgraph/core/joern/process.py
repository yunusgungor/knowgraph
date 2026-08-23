"""Joern daemon mode for persistent process.

Keeps a single Joern REPL (JVM) running so repeated queries avoid JVM startup
and re-`importCpg` for the same CPG. Transport is stdin/stdout on a `joern`
REPL subprocess (verified in a spike: `joern --server` REST mode does NOT
expose the Joern DSL bindings `importCpg`/`cpg`, but the REPL does).

Note: `cmd.exe /c joern.bat` does NOT print a REPL prompt when stdout is a
pipe (jline non-TTY). Synchronization therefore relies on sentinel markers,
not on the prompt.
"""

import logging
import os
import platform
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

START_MARKER = "__JOERN_RESULT_START__"
END_MARKER = "__JOERN_RESULT_END__"
CPG_LOADED_MARKER = "__KG_CPG_LOADED__"


class JoernDaemon:
    """Manage a persistent Joern REPL subprocess (single JVM).

    ``importCpg`` is sent once per distinct CPG; the same CPG's later queries
    skip the (expensive) reload. A background reader thread drains stdout into
    a queue so callers never block indefinitely on ``readline``.
    """

    def __init__(self, joern_path: Path):
        """Initialize Joern daemon manager.

        Args:
            joern_path: Path to joern-cli directory.
        """
        self.joern_path = Path(joern_path)
        self.process: Optional[subprocess.Popen] = None
        self._write_lock = threading.Lock()
        self._lines: queue.Queue = queue.Queue()
        self._reader_stop = threading.Event()
        self._reader: Optional[threading.Thread] = None
        self._loaded_cpgs: set[str] = set()
        # Each REPL query binds a `val __kg` in the session scope; after many
        # queries the accumulated scope slows type-checking (observed ~2x at
        # 500 queries, trending to a hang). Restart periodically to reset it.
        self._query_count = 0
        self._query_reset_threshold = int(
            os.getenv("KNOWGRAPH_JOERN_QUERY_RESET", "300")
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> bool:
        """Start a persistent Joern REPL subprocess.

        Returns:
            True if the subprocess launched. REPL readiness is verified by the
            first CPG load (which waits for the boot/load sentinel).
        """
        if self.is_running():
            return True
        try:
            joern_bat = self.joern_path / "joern.bat" if platform.system() == "Windows" else self.joern_path / "joern"
            cmd = [str(joern_bat)]
            if platform.system() == "Windows":
                cmd = ["cmd.exe", "/c", *cmd]
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                cwd=str(self.joern_path),
            )
        except Exception as e:
            logger.error(f"Failed to start Joern daemon: {e}")
            self.process = None
            return False

        self._reader_stop.clear()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        logger.info("Joern daemon subprocess started")
        return True

    def stop(self) -> bool:
        """Terminate the daemon subprocess."""
        self._reader_stop.set()
        if self.process is not None:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
        self._loaded_cpgs.clear()
        return True

    def restart(self) -> bool:
        """Restart the daemon."""
        self.stop()
        time.sleep(1)
        return self.start()

    def is_running(self) -> bool:
        """Whether the daemon subprocess is alive."""
        return bool(self.process is not None and self.process.poll() is None)

    def is_healthy(self) -> bool:
        """Whether the daemon is running and responsive-ish."""
        return self.is_running()

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------
    def _cpg_fingerprint(self, cpg_path: Path) -> str:
        """Fingerprint of a CPG file: path + size + mtime.

        Re-indexing overwrites ``metadata/cpg.bin`` in place, so a path-only key
        (the old ``_loaded_cpgs`` set) would keep serving the stale in-memory
        CPG after a re-index. Including size+mtime makes an in-place overwrite
        trigger a reload.
        """
        try:
            stat = cpg_path.stat()
            return f"{cpg_path}:{stat.st_size}:{int(stat.st_mtime)}"
        except OSError:
            return str(cpg_path)

    def ensure_cpg_loaded(self, cpg_path: Path, timeout: int | None = None) -> None:
        """Send ``importCpg`` + ``run.ossdataflow`` once per distinct CPG.

        Args:
            cpg_path: Path to cpg.bin.
            timeout: Seconds to wait for the CPG load (covers REPL boot too).

        Raises:
            RuntimeError: If the load sentinel is not seen in time.
        """
        if timeout is None:
            from knowgraph.config import JOERN_DAEMON_BOOT_TIMEOUT

            timeout = JOERN_DAEMON_BOOT_TIMEOUT

        key = self._cpg_fingerprint(cpg_path)
        if key in self._loaded_cpgs:
            return
        cpg_uri = str(cpg_path).replace("\\", "/")
        program = (
            f'importCpg("{cpg_uri}")'
            "\n"
            'println("' + CPG_LOADED_MARKER + '")'
        )
        self._send(program)
        self._wait_for_marker(CPG_LOADED_MARKER, timeout)
        self._send("try { run.ossdataflow } catch { case _: Exception => }")
        # No settle: leftover ossdataflow output is discarded by the next
        # query's marker window (start-marker precedes everything).
        self._loaded_cpgs.add(key)

    def query(self, cpg_path: Path, query: str, timeout: int = 60) -> str:
        """Run a Joern DSL query on the persistent REPL and return raw output.

        Args:
            cpg_path: Path to cpg.bin.
            query: Joern DSL query string.
            timeout: Seconds to wait for the result.

        Returns:
            Raw lines between the start/end markers.

        Raises:
            RuntimeError: If the daemon is not running or the query timed out.
        """
        if not self.is_running():
            raise RuntimeError("JoernDaemon is not running")

        # Periodically restart to reset the growing REPL session scope, which
        # otherwise slows type-checking and eventually hangs (each query binds
        # a `val __kg` in the session). Done BEFORE ensure_cpg_loaded so the
        # fresh REPL re-imports the CPG for this query.
        self._query_count += 1
        if self._query_count >= self._query_reset_threshold:
            self._query_count = 0
            logger.info(
                f"Restarting Joern daemon after {self._query_reset_threshold} queries "
                "(reset accumulated REPL scope)"
            )
            if not self.restart():
                raise RuntimeError("Joern daemon restart failed")

        self.ensure_cpg_loaded(cpg_path)

        # Start the marker window BEFORE evaluating the query so any
        # ``println`` side-effects inside the query body land inside the window
        # (callers parse those from stdout, e.g. CallGraphAnalyzer). Annotate
        # :Any so the match is a runtime type test (a plain `val x = {query}`
        # gives the query's static type, making `case l: List[_]`
        # unreachable-compile-error on non-List results).
        program = (
            f'println("{START_MARKER}")\n'
            f"val __kg: Any = {{ {query} }}\n"
            "__kg match {\n"
            '  case l: List[_] => l.foreach(x => println("RESULT_ITEM: " + x))\n'
            '  case other => println("RESULT_ITEM: " + other)\n'
            "}\n"
            f'println("{END_MARKER}")'
        )
        self._send(program)
        return self._collect_window(START_MARKER, END_MARKER, timeout)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _send(self, *lines: str) -> None:
        """Write lines to the REPL stdin (thread-safe)."""
        if self.process is None or self.process.stdin is None:
            return
        with self._write_lock:
            for ln in lines:
                self.process.stdin.write(ln + "\n")
            self.process.stdin.flush()

    def _read_loop(self) -> None:
        """Drain stdout into the queue until stopped or EOF."""
        if self.process is None or self.process.stdout is None:
            return
        while not self._reader_stop.is_set():
            line = self.process.stdout.readline()
            if not line:
                break
            self._lines.put(line)
        self._reader_stop.set()

    def _wait_for_marker(self, marker: str, timeout: int) -> None:
        """Consume lines until ``marker`` is seen, or raise on timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = self._lines.get(timeout=max(0.5, deadline - time.time()))
            except queue.Empty:
                continue
            if marker in line:
                return
        raise RuntimeError(f"Timed out after {timeout}s waiting for marker {marker}")

    def _collect_window(self, start_marker: str, end_marker: str, timeout: int) -> str:
        """Collect all raw lines for this query's marker window.

        Returns every line between the start and end markers (REPL echoes,
        prompts, ANSI, ``println`` output and ``RESULT_ITEM:`` lines) so both
        ``println``-based results (parsed from stdout) and list-item results
        (parsed from RESULT_ITEM lines) are preserved. Lines before the start
        marker (leftovers) are discarded.
        """
        items: list[str] = []
        started = False
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = self._lines.get(timeout=max(0.5, deadline - time.time()))
            except queue.Empty:
                continue
            if start_marker in line:
                started = True
                continue
            if started and end_marker in line:
                return "\n".join(items)
            if started:
                items.append(line.rstrip("\r\n"))
        raise RuntimeError(f"Timed out after {timeout}s waiting for Joern result")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False

"""Interactive Joern REPL - Direct access to Joern shell.

This module provides integration with Joern's interactive REPL,
enabling exploratory analysis and live query testing.
"""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class JoernREPL:
    """Interactive Joern shell integration.

    Provides direct access to Joern's interactive environment for
    exploratory code analysis and query development.

    Example:
        repl = JoernREPL()

        # Start interactive shell with CPG preloaded
        repl.start(cpg_path=Path("cpg.bin"))

        # Or start empty shell
        repl.start()
    """

    def __init__(self, joern_path: Path | None = None):
        """Initialize REPL.

        Args:
        ----
            joern_path: Path to Joern installation (auto-detected if None)

        """
        self.joern_path = joern_path or self._find_joern()

        if not self.joern_path:
            raise RuntimeError("Joern not found. Install with: knowgraph-setup-joern")

        logger.info(f"JoernREPL initialized: {self.joern_path}")

    def _find_joern(self) -> Path | None:
        """Auto-detect Joern installation."""
        from knowgraph.config import JOERN_PATH

        if JOERN_PATH:
            joern_cli = Path(JOERN_PATH) / "joern-cli"
            if joern_cli.exists():
                return joern_cli

        # Fallback locations
        common_paths = [
            Path.home() / ".knowgraph" / "joern" / "joern-cli",
            Path("/opt/joern/joern-cli"),
            Path("/usr/local/joern/joern-cli"),
        ]

        for path in common_paths:
            if path.exists():
                return path

        return None

    def start(
        self,
        cpg_path: Path | None = None,
        script: str | None = None,
    ) -> int:
        """Start interactive Joern shell.

        Args:
        ----
            cpg_path: Optional CPG to preload
            script: Optional script to execute before entering REPL

        Returns:
        -------
            Exit code from REPL

        Example:
        -------
            repl = JoernREPL()

            # Interactive exploration
            repl.start(cpg_path=Path("cpg.bin"))

            # Will open Joern shell with CPG loaded
            # User can run queries interactively:
            # joern> cpg.method.name.l
            # joern> cpg.call.name("strcpy").l

        """
        if self.joern_path:
             joern_bin = self.joern_path / "joern"
        else:
             raise RuntimeError("Joern path not active")

        cmd = [str(joern_bin)]

        # Build import commands
        import_commands = []

        if cpg_path:
            if not cpg_path.exists():
                logger.error(f"CPG not found: {cpg_path}")
                return 1

            # Preload CPG
            import_commands.append(f'importCpg("{cpg_path}")')
            logger.info(f"Preloading CPG: {cpg_path}")

        if script:
            import_commands.append(script)

        # Create startup script if needed
        if import_commands:
            startup_script = self._create_startup_script(import_commands)
            cmd.extend(["--script", str(startup_script)])

        logger.info("Starting Joern REPL...")
        logger.info("Type 'exit' or Ctrl+D to quit")

        try:
            # Run interactive Joern
            result = subprocess.run(
                cmd,
                cwd=str(self.joern_path),
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )

            return result.returncode

        except KeyboardInterrupt:
            logger.info("\nREPL interrupted by user")
            return 130
        except Exception as e:
            logger.error(f"REPL failed: {e}")
            return 1

    def execute_interactive_script(
        self,
        cpg_path: Path,
        script_path: Path,
    ) -> tuple[str, str]:
        """Execute script in REPL and return output.

        Args:
        ----
            cpg_path: Path to CPG binary
            script_path: Path to Joern script (.sc file)

        Returns:
        -------
            Tuple of (stdout, stderr)

        """
        if not self.joern_path:
             return "", "Joern path not configured"

        joern_bin = self.joern_path / "joern"

        cmd = [
            str(joern_bin),
            "--script", str(script_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.joern_path),
            )

            return result.stdout, result.stderr

        except Exception as e:
            logger.error(f"Script execution failed: {e}")
            return "", str(e)

    def _create_startup_script(self, commands: list[str]) -> Path:
        """Create temporary startup script."""
        import tempfile

        script_content = "\n".join(commands) + "\n"

        # Create temp script
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".sc",
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write(script_content)
            return Path(f.name)

    def get_help(self) -> str:
        """Get Joern REPL help text.

        Returns:
        -------
            Help text with common commands

        """
        return """
Joern Interactive REPL - Common Commands:

Basic Queries:
  cpg.method.name.l                    # List all method names
  cpg.call.l                           # List all calls
  cpg.method.parameter.l               # List all parameters

Filtering:
  cpg.method.name(".*login.*").l       # Methods matching pattern
  cpg.call.name("strcpy").l            # Specific calls

Dataflow:
  cpg.method.parameter.reachableBy(...)  # Dataflow analysis

Graph Operations:
  cpg.method.callOut.l                 # Outgoing calls
  cpg.method.callIn.l                  # Incoming calls
  cpg.method.dominatedBy(...)          # Dominance

Help:
  :help                                # Full help
  :quit or Ctrl+D                      # Exit REPL

For more: https://docs.joern.io/
"""


class ScriptManager:
    """Manage Joern analysis scripts.

    Provides script library management, versioning, and execution
    for reusable analysis patterns.

    Example:
        manager = ScriptManager()

        # Save script
        manager.save_script("find_vulns", script_content)

        # Execute script
        output = manager.execute_script("find_vulns", cpg_path)
    """

    def __init__(self, script_dir: Path | None = None):
        """Initialize script manager.

        Args:
        ----
            script_dir: Directory for script storage

        """
        self.script_dir = script_dir or (Path.home() / ".knowgraph" / "joern_scripts")
        self.script_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ScriptManager: {self.script_dir}")

    def save_script(
        self,
        name: str,
        content: str,
        description: str = "",
    ) -> Path:
        """Save a Joern script.

        Args:
        ----
            name: Script name (without .sc extension)
            content: Script content
            description: Script description

        Returns:
        -------
            Path to saved script

        """
        script_path = self.script_dir / f"{name}.sc"

        # Add header comment
        header = f"""// {name}
// {description}
// Created: {__import__('datetime').datetime.now().isoformat()}

"""

        full_content = header + content

        script_path.write_text(full_content, encoding="utf-8")
        logger.info(f"Script saved: {script_path}")

        return script_path

    def load_script(self, name: str) -> str:
        """Load a script by name.

        Args:
        ----
            name: Script name (without .sc extension)

        Returns:
        -------
            Script content

        """
        script_path = self.script_dir / f"{name}.sc"

        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {name}")

        return script_path.read_text(encoding="utf-8")

    def list_scripts(self) -> list[dict]:
        """List all saved scripts.

        Returns:
        -------
            List of script metadata

        """
        scripts = []

        for script_path in self.script_dir.glob("*.sc"):
            # Extract description from header
            content = script_path.read_text(encoding="utf-8")
            lines = content.split("\n")

            description = ""
            if len(lines) > 1 and lines[1].startswith("//"):
                description = lines[1].replace("//", "").strip()

            scripts.append({
                "name": script_path.stem,
                "path": str(script_path),
                "description": description,
                "size": script_path.stat().st_size,
            })

        return scripts

    def execute_script(
        self,
        name: str,
        cpg_path: Path,
    ) -> tuple[str, str]:
        """Execute a saved script.

        Args:
        ----
            name: Script name
            cpg_path: Path to CPG binary

        Returns:
        -------
            Tuple of (stdout, stderr)

        """
        script_path = self.script_dir / f"{name}.sc"

        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {name}")

        # Use JoernQueryExecutor for execution
        from knowgraph.domain.intelligence.joern_query_executor import (
            JoernQueryExecutor,
        )

        # Read script content
        script_content = script_path.read_text(encoding="utf-8")

        # Extract query (remove comments and imports)
        query_lines = []
        for line in script_content.split("\n"):
            if not line.strip().startswith("//") and line.strip():
                query_lines.append(line)

        query = "\n".join(query_lines)

        # Execute
        executor = JoernQueryExecutor()
        result = executor.execute_query(cpg_path, query)

        # Format output
        stdout = f"Script: {name}\nResults: {result.node_count} items\n"
        stdout += str(result.results)

        stderr = result.metadata.get("stderr", "")

        return stdout, stderr

    def delete_script(self, name: str) -> bool:
        """Delete a script.

        Args:
        ----
            name: Script name

        Returns:
        -------
            True if deleted, False if not found

        """
        script_path = self.script_dir / f"{name}.sc"

        if script_path.exists():
            script_path.unlink()
            logger.info(f"Script deleted: {name}")
            return True

        return False

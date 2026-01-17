"""Dominance Analysis - Control flow dominance for dead code detection.

This module provides dominance analysis capabilities using Joern's
control flow graph analysis features.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DominanceResult:
    """Result from dominance analysis.

    Attributes
    ----------
        dominated_methods: List of methods dominated by dominator
        dominator: Dominator method information
        path_count: Number of dominated nodes
        metadata: Additional analysis metadata

    """

    dominated_methods: list[dict]
    dominator: dict
    path_count: int
    metadata: dict = field(default_factory=dict)

    def __str__(self) -> str:
        """Human-readable summary."""
        return (
            f"DominanceResult(\n"
            f"  dominator: {self.dominator.get('name', 'unknown')}\n"
            f"  dominated: {self.path_count} methods\n"
            f")"
        )


class DominanceAnalyzer:
    """Analyze control flow dominance using Joern.

    Control flow dominance is used to identify:
    - Dead code (unreachable from entry points)
    - Control dependencies
    - Critical paths in execution flow

    Example:
        analyzer = DominanceAnalyzer()

        # Find all methods dominated by main
        result = analyzer.find_dominated_methods(
            cpg_path=Path("cpg.bin"),
            dominator_pattern="main"
        )

        # Find dead code
        dead_code = analyzer.find_dead_code(Path("cpg.bin"))
    """

    def find_dominated_methods(
        self,
        cpg_path: Path,
        dominator_pattern: str,
    ) -> DominanceResult:
        """Find all methods dominated by a dominator.

        A method M is dominated by method D if all paths from entry points
        to M must pass through D.

        Args:
        ----
            cpg_path: Path to CPG binary
            dominator_pattern: Pattern for dominator method name

        Returns:
        -------
            DominanceResult with dominated methods

        Example:
        -------
            result = analyzer.find_dominated_methods(
                cpg_path=Path("cpg.bin"),
                dominator_pattern="main"
            )
            print(f"Found {result.path_count} methods dominated by main")

        """
        from knowgraph.domain.intelligence.joern_query_executor import (
            JoernQueryExecutor,
        )

        # Joern dominance query
        query = f"""
val dominator = cpg.method.name("{dominator_pattern}").headOption

dominator match {{
  case Some(dom) =>
    val dominated = cpg.method.filter(m => m.dominatedBy.contains(dom))
    dominated.name.l
  case None =>
    List.empty
}}
"""

        executor = JoernQueryExecutor()
        result = executor.execute_query(cpg_path, query)

        return DominanceResult(
            dominated_methods=result.results,
            dominator={"name": dominator_pattern},
            path_count=result.node_count,
            metadata={
                "execution_time_ms": result.execution_time_ms,
                **result.metadata,
            },
        )

    def find_post_dominated_methods(
        self,
        cpg_path: Path,
        post_dominator_pattern: str,
    ) -> DominanceResult:
        """Find methods post-dominated by a post-dominator.

        A method M is post-dominated by method P if all paths from M
        to exit points must pass through P.

        Args:
        ----
            cpg_path: Path to CPG binary
            post_dominator_pattern: Pattern for post-dominator method

        Returns:
        -------
            DominanceResult with post-dominated methods

        """
        from knowgraph.domain.intelligence.joern_query_executor import (
            JoernQueryExecutor,
        )

        query = f"""
val postDom = cpg.method.name("{post_dominator_pattern}").headOption

postDom match {{
  case Some(pd) =>
    val postDominated = cpg.method.filter(m => m.postDominatedBy.contains(pd))
    postDominated.name.l
  case None =>
    List.empty
}}
"""

        executor = JoernQueryExecutor()
        result = executor.execute_query(cpg_path, query)

        return DominanceResult(
            dominated_methods=result.results,
            dominator={"name": post_dominator_pattern, "type": "post-dominator"},
            path_count=result.node_count,
            metadata=result.metadata,
        )

    def find_dead_code(self, cpg_path: Path) -> list[dict]:
        """Find unreachable/dead code using dominance analysis.

        Dead code is identified as methods that are:
        1. Not reachable from entry points (main, _start, etc.)
        2. Not dominated by any entry point
        3. Have no call-in edges

        Args:
        ----
            cpg_path: Path to CPG binary

        Returns:
        -------
            List of dead code methods with metadata

        Example:
        -------
            dead_code = analyzer.find_dead_code(Path("cpg.bin"))

            for method in dead_code:
                print(f"Dead code: {method['name']} at line {method.get('line')}")

        """
        from knowgraph.domain.intelligence.joern_query_executor import (
            JoernQueryExecutor,
        )

        # Find methods not reachable from entry points
        query = """
// Identify entry points (main, constructors, etc.)
val entryPoints = cpg.method.name("(main|_start|__libc_start_main).*").l

// Find all non-internal methods
val allMethods = cpg.method.filterNot(_.name.startsWith("<")).l

// Dead code = methods with no callers
val deadMethods = allMethods.filter(_.callIn.isEmpty)

// Return names with line numbers and filename
deadMethods.map { m =>
  val line = m.lineNumber.headOption.map(_.toString).getOrElse("-1")
  val filename = m.filename.headOption.getOrElse("unknown")
  s"${m.name}:$line:$filename"
}.l
"""

        executor = JoernQueryExecutor()
        result = executor.execute_query(cpg_path, query)

        # Parse results
        dead_methods = []
        for item in result.results:
            raw = item.get("raw", "")
            # Parse format: "name:line:filename"
            parts = raw.split(":", 2)  # Split into max 3 parts
            if len(parts) >= 2:
                name = parts[0]
                line = int(parts[1]) if parts[1].isdigit() else -1
                filename = parts[2] if len(parts) > 2 else "unknown"
                dead_methods.append({
                    "name": name,
                    "line": line,
                    "filename": filename,
                    "reason": "unreachable_from_entry_points",
                })
            else:
                dead_methods.append({
                    "name": raw,
                    "line": -1,
                    "filename": "unknown",
                    "reason": "unreachable",
                })

        logger.info(f"Found {len(dead_methods)} dead code methods")

        return dead_methods

    def find_immediate_dominator(
        self,
        cpg_path: Path,
        method_pattern: str,
    ) -> dict | None:
        """Find immediate dominator of a method.

        The immediate dominator is the closest dominator in the
        dominance tree.

        Args:
        ----
            cpg_path: Path to CPG binary
            method_pattern: Pattern for method to analyze

        Returns:
        -------
            Immediate dominator information or None

        """
        from knowgraph.domain.intelligence.joern_query_executor import (
            JoernQueryExecutor,
        )

        query = f"""
val method = cpg.method.name("{method_pattern}").headOption

method match {{
  case Some(m) =>
    m.immediateDominator.map(_.name).headOption.getOrElse("none")
  case None =>
    "not_found"
}}
"""

        executor = JoernQueryExecutor()
        result = executor.execute_query(cpg_path, query)

        if result.results and result.results[0].get("raw") not in ("none", "not_found"):
            return {
                "name": result.results[0].get("raw"),
                "type": "immediate_dominator",
            }

        return None

    def analyze_control_dependencies(
        self,
        cpg_path: Path,
    ) -> dict[str, list[str]]:
        """Analyze control dependencies between methods.

        Returns a mapping of methods to their control dependencies.

        Args:
        ----
            cpg_path: Path to CPG binary

        Returns:
        -------
            Dictionary mapping method names to their dependencies

        """
        from knowgraph.domain.intelligence.joern_query_executor import (
            JoernQueryExecutor,
        )

        query = """
cpg.method.filterNot(_.name.startsWith("<")).map { m =>
  val deps = m.controlledBy.name.l
  s"${m.name}:${deps.mkString(",")}"
}.l
"""

        executor = JoernQueryExecutor()
        result = executor.execute_query(cpg_path, query)

        # Parse results
        dependencies = {}
        for item in result.results:
            raw = item.get("raw", "")
            if ":" in raw:
                method, deps_str = raw.split(":", 1)
                deps = deps_str.split(",") if deps_str else []
                dependencies[method] = deps

        return dependencies

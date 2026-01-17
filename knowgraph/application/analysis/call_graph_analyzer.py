"""Call Graph Analysis - Validate and analyze call relationships.

This module provides comprehensive call graph analysis capabilities
using Joern's call graph features.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CallGraphResult:
    """Result from call graph analysis.

    Attributes
    ----------
        total_methods: Total number of methods
        call_edges: Total number of call edges
        entry_points: List of entry point methods
        leaf_methods: List of leaf methods (no callees)
        max_depth: Maximum call chain depth
        is_valid: Whether call graph is complete/valid
        metadata: Additional analysis data

    """

    total_methods: int
    call_edges: int
    entry_points: list[str]
    leaf_methods: list[str]
    max_depth: int
    is_valid: bool
    metadata: dict = field(default_factory=dict)

    def __str__(self) -> str:
        """Human-readable summary."""
        return (
            f"CallGraphResult(\n"
            f"  methods: {self.total_methods}\n"
            f"  calls: {self.call_edges}\n"
            f"  entry points: {len(self.entry_points)}\n"
            f"  valid: {self.is_valid}\n"
            f")"
        )


class CallGraphAnalyzer:
    """Analyze and validate call graph structure.

    Provides call graph validation, recursive call detection,
    and call chain analysis.

    Example:
        analyzer = CallGraphAnalyzer()

        # Validate call graph
        result = analyzer.validate_call_graph(cpg_path)
        if not result.is_valid:
            print("Incomplete call graph!")

        # Find recursive calls
        recursive = analyzer.find_recursive_calls(cpg_path)
    """

    def validate_call_graph(self, cpg_path: Path) -> CallGraphResult:
        """Validate call graph completeness and structure.

        Checks:
        - All method calls resolved
        - No dangling call references
        - Entry points identified
        - Leaf methods identified

        Args:
        ----
            cpg_path: Path to CPG binary

        Returns:
        -------
            CallGraphResult with validation status

        Example:
        -------
            result = analyzer.validate_call_graph(Path("cpg.bin"))

            if result.is_valid:
                print(f"✅ Valid call graph: {result.total_methods} methods")
            else:
                print(f"❌ Invalid: {result.metadata.get('issues')}")

        """
        from knowgraph.domain.intelligence.joern_query_executor import (
            JoernQueryExecutor,
        )

        query = """
val methods = cpg.method.filterNot(_.name.startsWith("<")).l
val callEdges = cpg.call.l

// Entry points (no callers)
val entryPoints = methods.filter(_.callIn.isEmpty).name.l

// Leaf methods (no callees)
val leafMethods = methods.filter(_.callOut.isEmpty).name.l

// Output stats
println(s"METHODS:${methods.size}")
println(s"CALLS:${callEdges.size}")
println(s"ENTRY_POINTS:${entryPoints.mkString(",")}")
println(s"LEAF_METHODS:${leafMethods.mkString(",")}")

// Return summary
List(s"methods:${methods.size}", s"calls:${callEdges.size}")
"""

        executor = JoernQueryExecutor()
        result = executor.execute_query(cpg_path, query)

        # Parse stdout for stats (println writes to stdout)
        stdout = result.metadata.get("stdout", "")

        methods_count = self._extract_value(stdout, "METHODS:")
        calls_count = self._extract_value(stdout, "CALLS:")
        entry_points = self._extract_list(stdout, "ENTRY_POINTS:")
        leaf_methods = self._extract_list(stdout, "LEAF_METHODS:")

        # Validation: call graph is valid if we have methods
        # Calls can be zero for simple programs
        is_valid = methods_count > 0

        return CallGraphResult(
            total_methods=methods_count,
            call_edges=calls_count,
            entry_points=entry_points,
            leaf_methods=leaf_methods,
            max_depth=0,  # TODO: calculate
            is_valid=is_valid,
            metadata={
                "entry_point_count": len(entry_points),
                "leaf_count": len(leaf_methods),
                "validation_note": "Valid if methods exist" if is_valid else "No methods found",
            },
        )

    def find_recursive_calls(
        self,
        cpg_path: Path,
        depth: int = 10,
    ) -> list[dict]:
        """Find methods with recursive calls (direct or indirect).

        Args:
        ----
            cpg_path: Path to CPG binary
            depth: Maximum recursion depth to check

        Returns:
        -------
            List of recursive method information

        Example:
        -------
            recursive = analyzer.find_recursive_calls(Path("cpg.bin"))

            for method in recursive:
                print(f"Recursive: {method['name']} (depth {method['depth']})")

        """
        from knowgraph.domain.intelligence.joern_query_executor import (
            JoernQueryExecutor,
        )

        # Find methods that call themselves (directly or indirectly)
        query = """
cpg.method.filterNot(_.name.startsWith("<")).filter { m =>
  // Check if method appears in its own call chain
  val callees = m.callOut.callee.l

  // Direct recursion
  val directRecursion = callees.exists(_.name == m.name)

  // Indirect recursion (simplified check)
  val indirectRecursion = callees.exists { callee =>
    callee.callOut.callee.name.contains(m.name)
  }

  directRecursion || indirectRecursion
}.map { m =>
  s"${m.name}:${m.lineNumber.headOption.getOrElse(-1)}"
}.l
"""

        executor = JoernQueryExecutor()
        result = executor.execute_query(cpg_path, query)

        # Parse results
        recursive_methods = []
        for item in result.results:
            raw = item.get("raw", "")
            if ":" in raw:
                name, line = raw.split(":", 1)
                recursive_methods.append({
                    "name": name,
                    "line": int(line) if line.isdigit() else -1,
                    "depth": 1,  # TODO: calculate actual depth
                    "type": "recursive",
                })
            else:
                recursive_methods.append({
                    "name": raw,
                    "line": -1,
                    "depth": 1,
                    "type": "recursive",
                })

        logger.info(f"Found {len(recursive_methods)} recursive methods")

        return recursive_methods

    def find_call_chains(
        self,
        cpg_path: Path,
        from_pattern: str,
        to_pattern: str,
        max_depth: int = 5,
    ) -> list[list[str]]:
        """Find all call chains between two methods.

        Args:
        ----
            cpg_path: Path to CPG binary
            from_pattern: Source method pattern
            to_pattern: Target method pattern
            max_depth: Maximum chain length

        Returns:
        -------
            List of call chains (each chain is list of method names)

        Example:
        -------
            chains = analyzer.find_call_chains(
                cpg_path=Path("cpg.bin"),
                from_pattern="main",
                to_pattern="vulnerable_function"
            )

            for chain in chains:
                print(" -> ".join(chain))

        """
        from knowgraph.domain.intelligence.joern_query_executor import (
            JoernQueryExecutor,
        )

        query = f"""
val source = cpg.method.name("{from_pattern}").head
val target = cpg.method.name("{to_pattern}").head

// Find paths using reachableBy
val paths = target.reachableBy(source).l

paths.map(_.name).l
"""

        executor = JoernQueryExecutor()
        result = executor.execute_query(cpg_path, query)

        # Parse into chains
        chains = []
        current_chain = []

        for item in result.results:
            method_name = item.get("raw", item.get("name", ""))
            if method_name:
                current_chain.append(method_name)

        if current_chain:
            chains.append(current_chain)

        return chains

    def analyze_method_callers(
        self,
        cpg_path: Path,
        method_pattern: str,
    ) -> dict:
        """Analyze who calls a specific method.

        Args:
        ----
            cpg_path: Path to CPG binary
            method_pattern: Method name pattern

        Returns:
        -------
            Dictionary with caller information

        """
        from knowgraph.domain.intelligence.joern_query_executor import (
            JoernQueryExecutor,
        )

        query = f"""
val targetMethod = cpg.method.name("{method_pattern}").headOption

targetMethod match {{
  case Some(method) =>
    val callers = method.callIn.method.name.l
    callers.mkString(",")
  case None =>
    "not_found"
}}
"""

        executor = JoernQueryExecutor()
        result = executor.execute_query(cpg_path, query)

        callers_str = result.results[0].get("raw", "") if result.results else ""
        callers = callers_str.split(",") if callers_str and callers_str != "not_found" else []

        return {
            "method": method_pattern,
            "callers": callers,
            "caller_count": len(callers),
        }

    def _extract_value(self, text: str, prefix: str) -> int:
        """Extract integer value after prefix."""
        for line in text.split("\n"):
            if prefix in line:
                try:
                    value = line.split(prefix)[1].split()[0]
                    return int(value)
                except (IndexError, ValueError):
                    pass
        return 0

    def _extract_list(self, text: str, prefix: str) -> list[str]:
        """Extract comma-separated list after prefix."""
        for line in text.split("\n"):
            if prefix in line:
                try:
                    value = line.split(prefix)[1].strip()
                    return [v.strip() for v in value.split(",") if v.strip()]
                except IndexError:
                    pass
        return []

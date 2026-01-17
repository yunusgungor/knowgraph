"""Joern Query Templates - Predefined queries for common code analysis tasks.

This module provides ready-to-use Joern queries for security analysis,
code quality checks, and dataflow analysis.
"""

from enum import Enum


class JoernQueryTemplate(Enum):
    """Common Joern query patterns for code analysis.

    Each template is a native Joern DSL query that can be executed
    via JoernQueryExecutor.
    """

    # === Security Queries ===

    DANGEROUS_FUNCTIONS = """
cpg.call.name("(strcpy|sprintf|gets|scanf|system|exec|eval)").l
"""

    BUFFER_OVERFLOW_CALLS = """
cpg.call.name("(strcpy|sprintf|strcat|gets)").l
"""

    COMMAND_INJECTION_SINKS = """
cpg.call.name("(system|exec|popen|execv)").l
"""

    SQL_QUERY_CALLS = """
cpg.call.name("(execute|executemany|query|raw|sql)").l
"""

    # === Code Quality ===

    ALL_METHODS = """
cpg.method.name.l
"""

    COMPLEX_METHODS = """
cpg.method.filter(_.controlStructure.size > 10).name.l
"""

    LARGE_METHODS = """
cpg.method.filter(_.lineNumber.isDefined && _.lineNumberEnd.isDefined)
   .filter(m => m.lineNumberEnd.head - m.lineNumber.head > 50)
   .name.l
"""

    DEAD_CODE = """
cpg.method.filter(_.callIn.isEmpty).name.l
"""

    UNUSED_PARAMETERS = """
cpg.method.parameter.filter(_.refsTo.isEmpty).name.l
"""

    # === Dataflow Analysis ===

    TAINT_SOURCES = """
cpg.method.parameter.filter(_.evalType("char.*")).name.l
"""

    USER_INPUT_METHODS = """
cpg.method.name("(.*input.*|.*request.*|.*get.*|.*post.*)").name.l
"""

    # === Vulnerability Patterns ===

    SQL_INJECTION_PATTERN = """
cpg.call.name("(execute|executemany|query|raw)")
   .argument
   .reachableBy(cpg.method.parameter)
   .l
"""

    BUFFER_OVERFLOW_PATTERN = """
cpg.call.name("(strcpy|sprintf)")
   .argument
   .reachableBy(cpg.method.parameter)
   .l
"""

    COMMAND_INJECTION_PATTERN = """
cpg.call.name("(system|exec)")
   .argument
   .reachableBy(cpg.method.parameter)
   .l
"""


def get_vulnerability_query(vuln_type: str) -> str:
    """Get Joern query for specific vulnerability type.

    Args:
    ----
        vuln_type: Vulnerability type (sql_injection, buffer_overflow, etc.)

    Returns:
    -------
        Joern query string

    Example:
    -------
        query = get_vulnerability_query("sql_injection")
        executor.execute_query(cpg_path, query)

    """
    queries = {
        "sql_injection": JoernQueryTemplate.SQL_INJECTION_PATTERN.value,
        "buffer_overflow": JoernQueryTemplate.BUFFER_OVERFLOW_PATTERN.value,
        "command_injection": JoernQueryTemplate.COMMAND_INJECTION_PATTERN.value,
        "dangerous_functions": JoernQueryTemplate.DANGEROUS_FUNCTIONS.value,
    }

    return queries.get(vuln_type, "")


def get_dataflow_query(source_pattern: str, sink_pattern: str) -> str:
    """Create dataflow query using Joern's reachableBy.

    Args:
    ----
        source_pattern: Regex for source methods/calls
        sink_pattern: Regex for sink methods/calls

    Returns:
    -------
        Joern query for dataflow analysis

    Example:
    -------
        query = get_dataflow_query(".*gets.*", ".*strcpy.*")

    """
    return f"""
val sources = cpg.call.name("{source_pattern}").l
val sinks = cpg.call.name("{sink_pattern}").l

sinks.flatMap {{ sink =>
  sources.flatMap {{ source =>
    sink.reachableBy(source).l
  }}
}}.l
"""


def get_method_query(method_pattern: str) -> str:
    """Find methods matching pattern.

    Args:
    ----
        method_pattern: Regex pattern for method names

    Returns:
    -------
        Joern query

    Example:
    -------
        query = get_method_query(".*login.*")

    """
    return f'cpg.method.name("{method_pattern}").name.l'

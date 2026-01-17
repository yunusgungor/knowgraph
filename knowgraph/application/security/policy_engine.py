"""Security Policy Engine - Enforce code security policies using Joern.

This module provides a policy-based security analysis framework
where security rules can be defined and validated against code.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Policy violation severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Policy:
    """Security policy definition.

    Attributes
    ----------
        name: Policy name
        description: Human-readable description
        query: Joern query that returns violations
        severity: Violation severity level
        remediation: Recommended fix
        cwe_id: CWE identifier (optional)

    """

    name: str
    description: str
    query: str
    severity: Severity
    remediation: str
    cwe_id: str | None = None

    def __str__(self) -> str:
        """Human-readable format."""
        cwe = f" ({self.cwe_id})" if self.cwe_id else ""
        return f"{self.name}{cwe}: {self.description}"


@dataclass
class PolicyViolation:
    """Policy violation finding.

    Attributes
    ----------
        policy: The violated policy
        location: Code location (file:line)
        description: Violation description
        severity: Severity level
        code_snippet: Optional code snippet

    """

    policy: Policy
    location: str
    description: str
    severity: Severity
    code_snippet: str | None = None

    def __str__(self) -> str:
        """Human-readable format."""
        return (
            f"{self.severity.value.upper()}: {self.policy.name}\n"
            f"  Location: {self.location}\n"
            f"  {self.description}\n"
            f"  Fix: {self.policy.remediation}"
        )


class PolicyEngine:
    """Enforce security policies on codebase.

    Provides predefined security policies and allows custom policy
    definitions for code quality and security analysis.

    Example:
        engine = PolicyEngine()

        # Validate all policies
        violations = engine.validate_policies(cpg_path)

        for violation in violations:
            print(violation)
    """

    # Predefined security policies
    POLICIES = [
        Policy(
            name="NoBufferOverflow",
            description="No unsafe buffer copy operations",
            query='cpg.call.name("(strcpy|sprintf|gets|strcat)").l',
            severity=Severity.CRITICAL,
            remediation="Use safe alternatives: strncpy, snprintf, fgets, strncat",
            cwe_id="CWE-120",
        ),
        Policy(
            name="NoCommandInjection",
            description="No user input to system commands",
            query="""
cpg.call.name("(system|exec|popen)").argument
   .reachableBy(cpg.method.parameter).l
""",
            severity=Severity.CRITICAL,
            remediation="Validate and sanitize all user input before system calls",
            cwe_id="CWE-78",
        ),
        Policy(
            name="NoSQLInjection",
            description="No user input to SQL queries",
            query="""
cpg.call.name("(execute|executemany|query|raw)").argument
   .reachableBy(cpg.method.parameter).l
""",
            severity=Severity.CRITICAL,
            remediation="Use parameterized queries or prepared statements",
            cwe_id="CWE-89",
        ),
        Policy(
            name="NoHardcodedSecrets",
            description="No hardcoded passwords or API keys",
            query="""
cpg.literal.code.l.filter { code =>
  code.matches(".*(?i)(password|secret|api[_-]?key|token).*=.*")
}
""",
            severity=Severity.HIGH,
            remediation="Use environment variables or secret management systems",
            cwe_id="CWE-798",
        ),
        Policy(
            name="NoWeakCrypto",
            description="No weak cryptographic algorithms",
            query="""
cpg.call.name("(MD5|SHA1|DES|RC4)").l
""",
            severity=Severity.HIGH,
            remediation="Use SHA-256, AES-256, or other modern algorithms",
            cwe_id="CWE-327",
        ),


        Policy(
            name="NoPathTraversal",
            description="Path traversal vulnerability",
            query="""
cpg.call.name("(open|fopen|readFile)").argument
    .reachableBy(cpg.method.parameter).l
""",
            severity=Severity.HIGH,
            remediation="Validate file paths, use absolute paths, check for '..'",
            cwe_id="CWE-22",
        ),
    ]

    def __init__(self, custom_policies: list[Policy] | None = None):
        """Initialize policy engine.

        Args:
        ----
            custom_policies: Additional custom policies

        """
        self.policies = self.POLICIES.copy()
        if custom_policies:
            self.policies.extend(custom_policies)

        logger.info(f"PolicyEngine initialized with {len(self.policies)} policies")

    def validate_policies(
        self,
        cpg_path: Path,
        policies: list[Policy] | None = None,
        severity_filter: Severity | None = None,
    ) -> list[PolicyViolation]:
        """Validate code against security policies.

        Args:
        ----
            cpg_path: Path to CPG binary
            policies: Specific policies to check (uses all if None)
            severity_filter: Only check policies of this severity or higher

        Returns:
        -------
            List of policy violations

        Example:
        -------
            engine = PolicyEngine()

            # Check all CRITICAL policies
            violations = engine.validate_policies(
                cpg_path=Path("cpg.bin"),
                severity_filter=Severity.CRITICAL
            )

        """
        from knowgraph.domain.intelligence.joern_query_executor import (
            JoernQueryExecutor,
        )

        policies_to_check = policies or self.policies

        # Filter by severity if specified
        if severity_filter:
            severity_levels = {
                Severity.CRITICAL: 4,
                Severity.HIGH: 3,
                Severity.MEDIUM: 2,
                Severity.LOW: 1,
                Severity.INFO: 0,
            }
            min_level = severity_levels[severity_filter]
            policies_to_check = [
                p for p in policies_to_check
                if severity_levels[p.severity] >= min_level
            ]

        violations = []
        executor = JoernQueryExecutor()

        logger.info(f"Validating {len(policies_to_check)} policies...")

        for policy in policies_to_check:
            try:
                # Execute policy query
                result = executor.execute_query(cpg_path, policy.query)

                # If query returns results, policy is violated
                if result.node_count > 0:
                    for item in result.results:
                        location = self._extract_location(item)
                        code_snippet = item.get("raw", "")

                        violations.append(
                            PolicyViolation(
                                policy=policy,
                                location=location,
                                description=f"{policy.description} found at {location}",
                                severity=policy.severity,
                                code_snippet=code_snippet if code_snippet != location else None,
                            )
                        )

            except Exception as e:
                logger.warning(f"Policy '{policy.name}' validation failed: {e}")
                continue

        logger.info(f"Found {len(violations)} policy violations")

        return violations

    def validate_single_policy(
        self,
        cpg_path: Path,
        policy_name: str,
    ) -> list[PolicyViolation]:
        """Validate a single policy by name.

        Args:
        ----
            cpg_path: Path to CPG binary
            policy_name: Name of policy to validate

        Returns:
        -------
            List of violations for this policy

        """
        policy = next((p for p in self.policies if p.name == policy_name), None)

        if not policy:
            raise ValueError(f"Policy '{policy_name}' not found")

        return self.validate_policies(cpg_path, policies=[policy])

    def get_policy_summary(self) -> dict:
        """Get summary of all policies.

        Returns:
        -------
            Dictionary with policy statistics

        """
        by_severity = {}
        for policy in self.policies:
            severity = policy.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            "total_policies": len(self.policies),
            "by_severity": by_severity,
            "policies": [
                {
                    "name": p.name,
                    "severity": p.severity.value,
                    "cwe_id": p.cwe_id,
                }
                for p in self.policies
            ],
        }

    def _extract_location(self, item: dict) -> str:
        """Extract code location from query result."""
        # Try to get location info
        name = item.get("name", "")
        line = item.get("line", "")
        raw = item.get("raw", "")

        if name and line:
            return f"{name}:{line}"
        elif name:
            return name
        elif ":" in raw:
            return raw
        else:
            return raw or "unknown"

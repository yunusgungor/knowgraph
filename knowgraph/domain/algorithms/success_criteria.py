"""Success criteria validation for quality monitoring.

Implements validators for:
- SC-008: Edge distribution in active subgraph (70%+ thresholds)
- SC-013: Citation mapping (100% traceability)
- SC-016: Hallucination detection (zero incorrect paths)
"""

import re
from dataclasses import dataclass

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


@dataclass
class EdgeDistributionResult:
    """Result of SC-008 edge distribution validation.

    Attributes
    ----------
        total_edges: Total edges in active subgraph
        semantic_edges: Count of semantic edges
        semantic_percentage: Percentage of semantic edges
        passes_threshold: Whether distribution meets threshold

    """

    total_edges: int
    semantic_edges: int

    @property
    def semantic_percentage(self) -> float:
        """Calculate semantic edge percentage."""
        if self.total_edges == 0:
            return 0.0
        return (self.semantic_edges / self.total_edges) * 100

    def passes_threshold(self, query_type: str, threshold: float = 70.0) -> bool:
        """Check if distribution meets SC-008 threshold.

        With AI-driven indexing, we expect predominantly semantic edges.
        """
        # For now, simplistic check: if we have edges, they should be semantic.
        return self.semantic_percentage >= threshold


def validate_edge_distribution(edges: list[Edge], query_type: str) -> EdgeDistributionResult:
    """Validate SC-008: Edge distribution.

    Args:
    ----
        edges: Edges in active subgraph
        query_type: "how" or "where" query classification (ignored in semantic-only mode)

    Returns:
    -------
        EdgeDistributionResult with percentages

    """
    semantic_count = sum(1 for e in edges if e.type == "semantic")

    return EdgeDistributionResult(
        total_edges=len(edges),
        semantic_edges=semantic_count,
    )


@dataclass
class CitationMappingResult:
    """Result of SC-013 citation validation."""

    total_citations: int
    mapped_citations: int
    unmapped_citations: list[str]

    @property
    def traceability_percentage(self) -> float:
        """Calculate traceability percentage."""
        if self.total_citations == 0:
            return 100.0
        return (self.mapped_citations / self.total_citations) * 100

    def passes_threshold(self) -> bool:
        """Check if 100% traceabilty met."""
        return self.unmapped_citations == []


@dataclass
class HallucinationResult:
    """Result of SC-016 hallucination detection."""

    total_paths: int
    valid_paths: int
    invalid_paths: list[str]

    @property
    def hallucination_count(self) -> int:
        """Count of invalid paths."""
        return len(self.invalid_paths)

    def passes_threshold(self) -> bool:
        """Check if zero hallucinations."""
        return self.hallucination_count == 0


def validate_citation_mapping(answer: str, context_nodes: list[Node]) -> CitationMappingResult:
    """Validate SC-013: 100% citation traceability.

    Extracts file/function references from LLM answer and verifies
    they map to actual source nodes.

    Args:
    ----
        answer: LLM-generated answer text
        context_nodes: Nodes used in context assembly

    Returns:
    -------
        CitationMappingResult with traceability percentage

    """
    # Extract file paths from answer (e.g., "file.py", "src/module.py")
    # Pattern matches common path patterns and code references
    citation_pattern = re.compile(
        r"(?:(?:src/|tests/)?[\w/]+\.(?:py|js|ts|md|java|go|rs))|(?:def\s+\w+)|(?:class\s+\w+)"
    )
    citations = citation_pattern.findall(answer)
    citations = list(set(citations))  # Deduplicate

    # Build set of known paths and identifiers from context nodes
    known_paths = {node.path for node in context_nodes}
    known_identifiers = set()
    for node in context_nodes:
        # Extract function/class names from code nodes
        if node.type == "code":
            func_pattern = re.compile(r"(?:def|class)\s+(\w+)")
            identifiers = func_pattern.findall(node.content)
            known_identifiers.update(identifiers)

    # Map citations to nodes
    mapped = 0
    unmapped = []
    for citation in citations:
        # Check if citation is a file path
        if any(citation in path for path in known_paths) or any(ident in citation for ident in known_identifiers):
            mapped += 1
        else:
            unmapped.append(citation)

    return CitationMappingResult(
        total_citations=len(citations), mapped_citations=mapped, unmapped_citations=unmapped
    )


def detect_hallucinations(answer: str, all_nodes: list[Node]) -> HallucinationResult:
    """Validate SC-016: Zero hallucinated file paths.

    Detects when LLM mentions file paths that don't exist in the graph.

    Args:
    ----
        answer: LLM-generated answer text
        all_nodes: Complete node set from graph

    Returns:
    -------
        HallucinationResult with invalid paths

    """
    # Extract file paths from answer
    path_pattern = re.compile(r"(?:src/|tests/)?[\w/]+\.(?:py|js|ts|md|java|go|rs|cpp|h)")
    mentioned_paths = path_pattern.findall(answer)
    mentioned_paths = list(set(mentioned_paths))

    # Build set of actual file paths
    actual_paths = {node.path for node in all_nodes}

    # Find paths that don't exist
    valid = 0
    invalid = []
    for path in mentioned_paths:
        # Check exact match or substring match
        if path in actual_paths or any(path in actual_path for actual_path in actual_paths):
            valid += 1
        else:
            invalid.append(path)

    return HallucinationResult(
        total_paths=len(mentioned_paths), valid_paths=valid, invalid_paths=invalid
    )


def classify_query_type(query: str) -> str:
    """Classify query as "how" or "where" for SC-008 validation.

    Args:
    ----
        query: Natural language query

    Returns:
    -------
        "how" or "where" classification

    """
    query_lower = query.lower()
    if "how" in query_lower or "implement" in query_lower or "work" in query_lower:
        return "how"
    elif "where" in query_lower or "location" in query_lower or "find" in query_lower:
        return "where"
    return "how"  # Default to "how" for ambiguous queries


def generate_validation_report(
    edge_distribution: EdgeDistributionResult | None,
    citation_mapping: CitationMappingResult | None,
    hallucination: HallucinationResult | None,
    query_type: str = "how",
) -> str:
    """Generate human-readable validation report.

    Args:
    ----
        edge_distribution: SC-008 validation result
        citation_mapping: SC-013 validation result
        hallucination: SC-016 validation result
        query_type: Query classification for SC-008

    Returns:
    -------
        Formatted validation report

    """
    report_lines = ["", "=== Success Criteria Validation Report ===", ""]

    # SC-008: Edge Distribution
    if edge_distribution:
        report_lines.append("SC-008: Edge Distribution")
        report_lines.append(f"  Query Type: {query_type}")
        report_lines.append(f"  Total Edges: {edge_distribution.total_edges}")
        report_lines.append(f"  Semantic: {edge_distribution.semantic_percentage:.1f}%")
        passes = edge_distribution.passes_threshold(query_type)
        report_lines.append(f"  Status: {'✓ PASS' if passes else '✗ FAIL'} (70% threshold)")
        report_lines.append("")

    # SC-013: Citation Mapping
    if citation_mapping:
        report_lines.append("SC-013: Citation Mapping")
        report_lines.append(f"  Total Citations: {citation_mapping.total_citations}")
        report_lines.append(f"  Mapped: {citation_mapping.mapped_citations}")
        report_lines.append(f"  Traceability: {citation_mapping.traceability_percentage:.1f}%")
        if citation_mapping.unmapped_citations:
            report_lines.append(f"  Unmapped: {', '.join(citation_mapping.unmapped_citations[:5])}")
        passes = citation_mapping.passes_threshold()
        report_lines.append(f"  Status: {'✓ PASS' if passes else '✗ FAIL'} (100% required)")
        report_lines.append("")

    # SC-016: Hallucination Detection
    if hallucination:
        report_lines.append("SC-016: Hallucination Detection")
        report_lines.append(f"  Total Paths: {hallucination.total_paths}")
        report_lines.append(f"  Valid: {hallucination.valid_paths}")
        report_lines.append(f"  Hallucinated: {hallucination.hallucination_count}")
        if hallucination.invalid_paths:
            report_lines.append(f"  Invalid: {', '.join(hallucination.invalid_paths[:5])}")
        passes = hallucination.passes_threshold()
        report_lines.append(f"  Status: {'✓ PASS' if passes else '✗ FAIL'} (zero required)")
        report_lines.append("")

    report_lines.append("=" * 43)

    return "\n".join(report_lines)

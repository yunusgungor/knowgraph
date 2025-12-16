from unittest.mock import MagicMock
from uuid import uuid4

from knowgraph.domain.algorithms.success_criteria import (
    classify_query_type,
    detect_hallucinations,
    generate_validation_report,
    validate_citation_mapping,
    validate_edge_distribution,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


def create_mock_node(path="file.py", content="content", type="text"):
    n = MagicMock(spec=Node)
    n.path = path
    n.content = content
    n.type = type
    n.id = uuid4()
    return n


def create_mock_edge(src, tgt, type="semantic"):
    e = MagicMock(spec=Edge)
    e.source = src
    e.target = tgt
    e.type = type
    return e


def test_validate_edge_distribution():
    e1 = create_mock_edge(uuid4(), uuid4(), "semantic")
    e2 = create_mock_edge(uuid4(), uuid4(), "semantic")
    e3 = create_mock_edge(uuid4(), uuid4(), "reference")

    result = validate_edge_distribution([e1, e2, e3], "how")
    assert result.total_edges == 3
    assert result.semantic_edges == 2
    assert abs(result.semantic_percentage - 66.6) < 0.1
    assert result.passes_threshold("how", 60.0) is True
    assert result.passes_threshold("how", 70.0) is False


def test_validate_citation_mapping():
    # Context nodes
    n1 = create_mock_node("src/utils.py", "def helper(): pass", "code")
    n2 = create_mock_node("docs/readme.md", "# Guide", "text")

    # Answer citing file and function
    answer = "Based on src/utils.py and the def helper function..."

    result = validate_citation_mapping(answer, [n1, n2])
    assert result.total_citations == 2  # src/utils.py, def helper
    assert result.mapped_citations == 2
    assert len(result.unmapped_citations) == 0

    # Test unmapped
    answer_bad = "Check missing.py"
    result_bad = validate_citation_mapping(answer_bad, [n1, n2])
    assert result_bad.mapped_citations == 0
    assert "missing.py" in result_bad.unmapped_citations


def test_detect_hallucinations():
    n1 = create_mock_node("src/valid.py")
    all_nodes = [n1]

    answer = "Use src/valid.py and src/ghost.py"

    result = detect_hallucinations(answer, all_nodes)
    assert result.total_paths == 2
    assert result.valid_paths == 1
    assert result.hallucination_count == 1
    assert "src/ghost.py" in result.invalid_paths


def test_classify_query_type():
    assert classify_query_type("How does this work?") == "how"
    assert classify_query_type("Where is the config?") == "where"
    assert classify_query_type("Ambiguous query") == "how"


def test_generate_validation_report():
    # Only smoke test the string generation
    report = generate_validation_report(None, None, None)
    assert "Success Criteria" in report

    # With data
    res_dist = validate_edge_distribution([], "how")
    report = generate_validation_report(res_dist, None, None)
    assert "SC-008" in report
    assert "Edge Distribution" in report

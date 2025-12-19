"""Tests for refactoring utilities."""

from uuid import uuid4

from knowgraph.domain.models.edge import Edge
from knowgraph.shared.refactoring import (
    build_error_response,
    build_graph_stats_response,
    build_llm_prompt,
    build_validation_response,
    extract_query_parameters,
    filter_active_edges,
    flatten_centrality_scores,
    validate_required_argument,
)


class TestFilterActiveEdges:
    """Tests for filter_active_edges function."""

    def test_filter_with_active_nodes(self):
        """Test filtering edges to active subgraph."""
        id1, id2, id3 = uuid4(), uuid4(), uuid4()
        edges = [
            Edge(source=id1, target=id2, type="semantic", score=0.8, created_at=0, metadata={}),
            Edge(source=id2, target=id3, type="semantic", score=0.7, created_at=0, metadata={}),
            Edge(source=id3, target=id1, type="reference", score=0.6, created_at=0, metadata={}),
        ]
        active_node_ids = {id1, id2}

        result = filter_active_edges(edges, active_node_ids)

        assert len(result) == 1
        assert result[0].source == id1
        assert result[0].target == id2

    def test_filter_empty_edges(self):
        """Test filtering with empty edge list."""
        active_node_ids = {uuid4(), uuid4()}

        result = filter_active_edges([], active_node_ids)

        assert result == []

    def test_filter_no_active_nodes(self):
        """Test filtering with no active nodes."""
        edges = [
            Edge(
                source=uuid4(),
                target=uuid4(),
                type="semantic",
                score=0.5,
                created_at=0,
                metadata={},
            )
        ]

        result = filter_active_edges(edges, set())

        assert result == []


class TestFlattenCentralityScores:
    """Tests for flatten_centrality_scores function."""

    def test_flatten_with_degree_metric(self):
        """Test flattening centrality scores with degree metric."""
        id1, id2 = uuid4(), uuid4()
        scores = {
            id1: {"degree": 0.8, "betweenness": 0.5},
            id2: {"degree": 0.6, "betweenness": 0.3},
        }

        result = flatten_centrality_scores(scores, "degree", 0.0)

        assert result[id1] == 0.8
        assert result[id2] == 0.6

    def test_flatten_with_missing_metric(self):
        """Test flattening with missing metric uses default."""
        id1 = uuid4()
        scores = {id1: {"betweenness": 0.5}}

        result = flatten_centrality_scores(scores, "degree", 0.0)

        assert result[id1] == 0.0

    def test_flatten_empty_scores(self):
        """Test flattening empty scores."""
        result = flatten_centrality_scores({}, "degree", 0.0)

        assert result == {}


class TestValidateRequiredArgument:
    """Tests for validate_required_argument function."""

    def test_valid_argument(self):
        """Test validation with valid argument."""
        arguments = {"query": "test query"}

        result = validate_required_argument(arguments, "query")

        assert result is None

    def test_missing_argument(self):
        """Test validation with missing argument."""
        arguments = {}

        result = validate_required_argument(arguments, "query")

        assert result == "Error: query is required."

    def test_empty_argument(self):
        """Test validation with empty argument."""
        arguments = {"query": ""}

        result = validate_required_argument(arguments, "query")

        assert result == "Error: query is required."


class TestBuildErrorResponse:
    """Tests for build_error_response function."""

    def test_build_with_default_prefix(self):
        """Test building error response with default prefix."""
        error = ValueError("Test error")

        result = build_error_response(error)

        assert result == "Error: Test error"

    def test_build_with_custom_prefix(self):
        """Test building error response with custom prefix."""
        error = ValueError("Test error")

        result = build_error_response(error, "Query failed")

        assert result == "Query failed: Test error"


class TestBuildGraphStatsResponse:
    """Tests for build_graph_stats_response function."""

    def test_build_stats_response(self):
        """Test building graph statistics response."""
        from collections import namedtuple

        Manifest = namedtuple(
            "Manifest",
            ["version", "node_count", "edge_count", "semantic_edge_count", "file_hashes"],
        )

        manifest = Manifest(
            version="2.0",
            node_count=100,
            edge_count=150,
            semantic_edge_count=75,
            file_hashes={"file1.md": "hash1", "file2.md": "hash2"},
        )

        result = build_graph_stats_response(manifest)

        assert "Graph Stats (v2.0)" in result
        assert "Nodes: 100" in result
        assert "Edges: 150" in result
        assert "Semantic Edges: 75" in result
        assert "Files Indexed: 2" in result


class TestBuildValidationResponse:
    """Tests for build_validation_response function."""

    def test_build_valid_response(self):
        """Test building validation response for valid graph."""
        from collections import namedtuple

        ValidationResult = namedtuple("ValidationResult", ["valid", "get_error_summary"])

        result_obj = ValidationResult(valid=True, get_error_summary=lambda: "")

        result = build_validation_response(result_obj)

        assert "Graph Validation Status: VALID" in result
        assert "Graph is consistent and ready for queries" in result

    def test_build_invalid_response(self):
        """Test building validation response for invalid graph."""
        from collections import namedtuple

        ValidationResult = namedtuple("ValidationResult", ["valid", "get_error_summary"])

        result_obj = ValidationResult(valid=False, get_error_summary=lambda: "Dangling edges found")

        result = build_validation_response(result_obj)

        assert "Graph Validation Status: INVALID" in result
        assert "Errors:" in result
        assert "Dangling edges found" in result


class TestExtractQueryParameters:
    """Tests for extract_query_parameters function."""

    def test_extract_with_defaults(self):
        """Test extracting parameters with defaults."""
        arguments = {}

        result = extract_query_parameters(arguments)

        assert result["top_k"] == 20
        assert result["max_hops"] == 4
        assert result["with_explanation"] is False
        assert result["expand_query"] is False
        assert result["max_tokens"] == 3000
        assert result["enable_hierarchical_lifting"] is True
        assert result["lift_levels"] == 2
        assert result["system_prompt"] is None

    def test_extract_with_custom_values(self):
        """Test extracting parameters with custom values."""
        arguments = {
            "top_k": 30,
            "max_hops": 6,
            "with_explanation": True,
            "expand_query": True,
            "max_tokens": 5000,
            "enable_hierarchical_lifting": False,
            "lift_levels": 3,
            "system_prompt": "Custom prompt",
        }

        result = extract_query_parameters(arguments)

        assert result["top_k"] == 30
        assert result["max_hops"] == 6
        assert result["with_explanation"] is True
        assert result["expand_query"] is True
        assert result["max_tokens"] == 5000
        assert result["enable_hierarchical_lifting"] is False
        assert result["lift_levels"] == 3
        assert result["system_prompt"] == "Custom prompt"


class TestBuildLLMPrompt:
    """Tests for build_llm_prompt function."""

    def test_build_basic_prompt(self):
        """Test building basic LLM prompt."""
        query = "What is Python?"
        context = "Python is a programming language."

        result = build_llm_prompt(query, context)

        assert "You are a helpful assistant" in result
        assert f"Context:\n{context}" in result
        assert f"Question: {query}" in result
        assert "Answer:" in result

    def test_build_with_custom_system_prompt(self):
        """Test building prompt with custom system prompt."""
        query = "Test query"
        context = "Test context"
        system_prompt = "You are an expert."

        result = build_llm_prompt(query, context, system_prompt)

        assert "You are an expert" in result
        assert "You are a helpful assistant" not in result

    def test_build_with_explanation_data(self):
        """Test building prompt with explanation data."""
        query = "Test query"
        context = "Test context"
        explanation_data = '{"paths": []}'

        result = build_llm_prompt(query, context, None, explanation_data)

        assert "Explanation Data:" in result
        assert explanation_data in result


class TestIntegration:
    """Integration tests for refactoring utilities."""

    def test_end_to_end_query_processing(self):
        """Test end-to-end query parameter processing."""
        arguments = {
            "query": "test",
            "top_k": 15,
            "max_hops": 3,
        }

        # Validate
        error = validate_required_argument(arguments, "query")
        assert error is None

        # Extract parameters
        params = extract_query_parameters(arguments)
        assert params["top_k"] == 15
        assert params["max_hops"] == 3

        # Build prompt
        prompt = build_llm_prompt(arguments["query"], "Context text")
        assert "test" in prompt

    def test_error_handling_workflow(self):
        """Test error handling workflow."""
        error = ValueError("Something went wrong")

        response = build_error_response(error, "Query failed")

        assert "Query failed: Something went wrong" in response

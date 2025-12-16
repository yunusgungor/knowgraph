from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from knowgraph.application.querying.query_engine import QueryEngine, QueryResult


def test_query_engine_run():
    store_path = Path("store")

    # Mocking internal dependencies
    with (
        patch("knowgraph.application.querying.query_engine.QueryRetriever") as mock_retriever_cls,
        patch("knowgraph.application.querying.query_engine.read_all_edges") as mock_read_edges,
        patch("knowgraph.application.querying.query_engine.assemble_context") as mock_assemble,
        patch("knowgraph.application.querying.query_engine.generate_explanation") as mock_gen_exp,
        patch(
            "knowgraph.application.querying.query_engine.compute_centrality_metrics"
        ) as mock_centrality,
    ):

        # Setup mocks
        mock_retriever = mock_retriever_cls.return_value
        # retrieve returns (nodes, seed_nodes)
        n1 = MagicMock()
        n1.id = uuid4()
        mock_retriever.retrieve.return_value = ([n1], [n1.id])
        mock_retriever.retrieve_by_similarity.return_value = [(n1, 1.0)]

        mock_read_edges.return_value = []  # No edges

        mock_centrality.return_value = {n1.id: {"degree": 1.0}}

        mock_assemble.return_value = ("Context", [])

        mock_gen_exp.return_value = MagicMock()

        engine = QueryEngine(store_path)

        # Test query
        result = engine.query("test query", with_explanation=True)

        assert isinstance(result, QueryResult)
        assert result.answer == "Context"
        assert result.explanation is not None
        assert mock_retriever.retrieve.called
        assert mock_centrality.called
        assert mock_assemble.called

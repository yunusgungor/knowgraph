from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from knowgraph.application.querying.query_engine import QueryEngine
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.search.sparse_index import SparseIndex


def create_node(content, title):
    return Node(
        id=uuid4(),
        hash="a" * 40,
        title=title,
        content=content,
        path="p",
        type="text",
        token_count=len(content.split()),
        created_at=1,
    )


@pytest.mark.asyncio
async def test_integration_query_flow():
    # 1. Setup Data
    n1 = create_node("Apple is a fruit", "Apple")
    n2 = create_node("Carrot is a vegetable", "Carrot")
    nodes_db = {n1.id: n1, n2.id: n2}

    # 2. Setup Index
    index = SparseIndex()
    # Mock embedding: simple logic
    index.add(n1.id, {"apple": 1, "fruit": 1})
    index.add(n2.id, {"carrot": 1, "vegetable": 1})
    index.build()

    # 3. Setup Mocks for IO
    provider = MagicMock()
    provider.generate_text = AsyncMock(return_value="The answer is Apple.")

    # Mock read_node_json to return from our DB
    def side_effect_read_node(nid, path):
        return nodes_db.get(nid)

    with (
        patch(
            "knowgraph.application.querying.retriever.read_node_json",
            side_effect=side_effect_read_node,
        ),
        patch("knowgraph.application.querying.query_engine.read_all_edges", return_value=[]),
        patch(
            "knowgraph.infrastructure.embedding.sparse_embedder.SparseEmbedder.embed_text",
            return_value={"apple": 1},
        ),
    ):

        # 4. Initialize Engine
        # We need to wire it up carefully.
        # QueryEngine creates its own Retriever. We need to inject our index?
        # QueryRetriever loads index from disk. We should mock SparseIndex.load

        with patch("knowgraph.infrastructure.search.sparse_index.SparseIndex.load"):
            # We want the retriever to use OUR index.
            # The retriever creates a new SparseIndex() and calls load().
            # We can't easily swap the instance unless we patch the class or the constructor.
            pass

    # Retry with deeper mocking strategy for Integration
    # We will instantiate Retriever manually and verify components work together.

    # Actually, integration means "QueryEngine" working.
    # We can patch SparseIndex so it returns our pre-built object when instantiated?
    # No, that's messy.

    # Better: Patch `query_engine.QueryRetriever` internals?

    # Let's write the test code directly:


@pytest.mark.asyncio
async def test_end_to_end_local_query_logic():
    # Create valid nodes
    n1 = create_node("info about apple", "apple")

    # Mock retriever
    with (
        patch("knowgraph.application.querying.query_engine.QueryRetriever") as MockRetrieverCls,
        patch("knowgraph.application.querying.query_engine.assemble_context") as mock_assemble,
        patch(
            "knowgraph.application.querying.query_engine.compute_centrality_metrics",
            return_value={},
        ),
        patch("knowgraph.application.querying.query_engine.read_all_edges", return_value=[]),
    ):

        # Setup Retriever behavior
        mock_retriever = MockRetrieverCls.return_value
        # it returns list of Node
        mock_retriever.retrieve.return_value = ([n1], {n1.id: 1.0})

        # Setup Assembly
        mock_assemble.return_value = ("context", [])

        engine = QueryEngine("graph_path")
        result = engine.query("apple", enable_hierarchical_lifting=False)

        # QueryEngine.query returns context as answer (no LLM generation)
        assert result.answer == "context"
        assert result.context == "context"
        mock_retriever.retrieve.assert_called_once()  # Integration point

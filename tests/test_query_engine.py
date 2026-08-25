from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from knowgraph.application.querying.query_engine import (
    QueryEngine,
    QueryResult,
    _get_query_cache_key,
)


def test_query_cache_key_distinguishes_grounding():
    """Graph Engineering: a query with grounding on must not reuse a cache entry
    from an evidence-blind run of the same text."""
    base = dict(
        query_text="auth",
        top_k=20,
        max_hops=4,
        max_tokens=3000,
        enable_hierarchical_lifting=True,
        lift_levels=2,
        with_explanation=False,
    )
    off = _get_query_cache_key(**base, enable_grounding=False, enable_temporal_filter=False)
    on = _get_query_cache_key(**base, enable_grounding=True, enable_temporal_filter=False)
    temporal = _get_query_cache_key(**base, enable_grounding=False, enable_temporal_filter=True)
    assert off != on
    assert off != temporal
    assert on != temporal


def test_query_cache_key_distinguishes_dense():
    """Hybrid dense retrieval is a behavioral lever: a dense-fused result must
    not serve (or be served by) a sparse-only cache entry for the same text."""
    base = dict(
        query_text="how does vat work",
        top_k=20,
        max_hops=4,
        max_tokens=3000,
        enable_hierarchical_lifting=True,
        lift_levels=2,
        with_explanation=False,
        enable_grounding=False,
        enable_temporal_filter=False,
    )
    sparse = _get_query_cache_key(**base, enable_dense_retrieval=False)
    dense = _get_query_cache_key(**base, enable_dense_retrieval=True)
    assert sparse != dense
    # Default (omitted) preserves the pre-dense behavior.
    default = _get_query_cache_key(**base)
    assert default == sparse


def test_query_cache_key_distinguishes_dense_weight():
    """The fusion weight is a behavioral lever too: changing it must not serve
    a stale cached result from the old weight."""
    base = dict(
        query_text="how does vat work",
        top_k=20,
        max_hops=4,
        max_tokens=3000,
        enable_hierarchical_lifting=True,
        lift_levels=2,
        with_explanation=False,
        enable_grounding=False,
        enable_temporal_filter=False,
        enable_dense_retrieval=True,
    )
    light = _get_query_cache_key(**base, dense_search_weight=0.3)
    heavy = _get_query_cache_key(**base, dense_search_weight=0.8)
    assert light != heavy


def test_serialize_grounding_facts():
    """Graph Engineering: enable_grounding serializes active-subgraph facts for
    answer-level grounding (grounded_edges + entity_names)."""
    from knowgraph.application.querying.query_engine import _serialize_grounding_facts
    from knowgraph.domain.models.edge import Edge
    from knowgraph.domain.models.node import Node
    from uuid import uuid4

    n1 = Node(id=uuid4(), hash="a" * 40, title="auth.py", content="x", path="auth.py",
              type="code", token_count=5, created_at=1,
              metadata={"entities": [{"name": "authenticate", "type": "definition"}]})
    n2 = Node(id=uuid4(), hash="b" * 40, title="models.py", content="y", path="models.py",
              type="code", token_count=5, created_at=1)
    edge = Edge(source=n1.id, target=n2.id, type="reference", score=0.5, created_at=1, metadata={})

    grounded_edges, entity_names = _serialize_grounding_facts([n1, n2], [edge])

    assert ["auth.py", "reference", "models.py"] in grounded_edges
    assert "authenticate" in entity_names
    assert "auth.py" in entity_names


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


def test_query_context_budget_defaults_to_max_tokens():
    """query()/query_async() default max_tokens to MAX_TOKENS (50000), the
    context-collection cap — NOT LLM_MAX_TOKENS (4096, the model output cap).

    Regression: the small 4096 budget excluded large-file chunks (a single
    20000-char chunk ~4500 tokens), so formula-bearing content never reached
    the LLM context.
    """
    import inspect

    from knowgraph.application.querying.query_engine import QueryEngine
    from knowgraph.config import MAX_TOKENS

    sig = inspect.signature(QueryEngine.query)
    assert sig.parameters["max_tokens"].default == MAX_TOKENS
    sig_async = inspect.signature(QueryEngine.query_async)
    assert sig_async.parameters["max_tokens"].default == MAX_TOKENS


def test_async_assemble_context_receives_edges():
    """_query_async_impl passes edges= to assemble_context so ref-path quality
    differentiates importance ties (determinism)."""
    import asyncio

    from knowgraph.application.querying.query_engine import QueryEngine

    captured = {}

    async def run():
        with (
            patch("knowgraph.application.querying.query_engine.QueryRetriever") as mock_rc,
            patch("knowgraph.application.querying.query_engine.read_all_edges") as mock_re,
            patch("knowgraph.application.querying.query_engine.assemble_context") as mock_ac,
            patch(
                "knowgraph.application.querying.query_engine.compute_centrality_metrics_async",
                new=AsyncMock(),
            ) as mock_cent,
        ):
            mock_r = mock_rc.return_value
            n1 = MagicMock()
            n1.id = uuid4()
            mock_r.retrieve_async = AsyncMock(return_value=([n1], [n1.id]))
            mock_r.retrieve_by_similarity_async = AsyncMock(return_value=[(n1, 1.0)])
            mock_re.return_value = []
            # compute_centrality_metrics_async is awaited in the async path.
            mock_cent.return_value = {n1.id: {"composite": 1.0}}
            mock_ac.return_value = ("Context", [])

            def _capture(nodes, seed_ids, sim, cent, mt, **kw):
                captured["edges"] = kw.get("edges")
                return ("Context", [])

            mock_ac.side_effect = _capture
            engine = QueryEngine(Path("store"))
            # Disable hierarchical lifting to keep the path minimal.
            await engine.query_async(
                "test query", enable_hierarchical_lifting=False, with_explanation=False
            )

    asyncio.run(run())
    assert "edges" in captured, "assemble_context must receive edges= in the async path"

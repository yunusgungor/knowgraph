from unittest.mock import MagicMock, patch
from uuid import uuid4

from knowgraph.application.querying.context_assembly import assemble_context, score_node_importance
from knowgraph.domain.models.node import Node


def create_mock_node(uid, content="content", token_count=10, role="text"):
    n = MagicMock(spec=Node)
    n.id = uid
    n.content = content
    n.title = "Title"
    n.path = "path/to/file"
    n.line_start = 1
    n.line_end = 10
    n.type = role
    n.token_count = token_count
    n.role_weight = 1.0  # Mock default
    return n


def test_score_node_importance():
    n = create_mock_node(uuid4())
    score = score_node_importance(n, True, 0.8, 0.7)
    # Just check it returns float between 0 and 1
    assert 0.0 <= score <= 1.0


def test_score_node_importance_grounded_bonus():
    """Graph Engineering: a grounded node (graph evidence) scores higher than baseline."""
    n = create_mock_node(uuid4())
    baseline = score_node_importance(n, True, 0.8, 0.7, grounded=None)
    grounded = score_node_importance(n, True, 0.8, 0.7, grounded=True)
    assert grounded > baseline


def test_score_node_importance_ungrounded_penalty():
    """Graph Engineering: an ungrounded (isolated) node scores lower than baseline."""
    n = create_mock_node(uuid4())
    baseline = score_node_importance(n, True, 0.8, 0.7, grounded=None)
    ungrounded = score_node_importance(n, True, 0.8, 0.7, grounded=False)
    assert ungrounded < baseline


def test_grounding_removes_isolated_node_under_budget():
    """Graph Engineering: with grounding ON, an isolated (ungrounded) high-similarity
    node is demoted below grounded content and loses the tight context budget;
    with grounding OFF it would have been included."""
    n1 = create_mock_node(uuid4(), content="_seed_node_", token_count=30)
    n2 = create_mock_node(uuid4(), content="_grounded_node_", token_count=30)
    n3 = create_mock_node(uuid4(), content="_isolated_node_", token_count=30)  # isolated, high sim
    nodes = [n1, n2, n3]
    seed_ids = [n1.id]
    # Isolated node scored second-highest on similarity after the seed.
    similarity_scores = {n1.id: 0.9, n2.id: 0.5, n3.id: 0.8}
    centrality_scores = {n.id: {"composite": 0.5} for n in nodes}
    # n3 is isolated (no graph evidence).
    verdicts = {n1.id: True, n2.id: True, n3.id: False}

    with patch("tiktoken.get_encoding") as mock_get_encoding:
        mock_encoding = MagicMock()
        # Each block reports ~30 tokens (content length), so budget 60 fits
        # exactly 2 blocks.
        mock_encoding.encode.side_effect = lambda x: [0] * 30
        mock_get_encoding.return_value = mock_encoding
        _, blocks_off = assemble_context(
            nodes, seed_ids, similarity_scores, centrality_scores, max_tokens=60, grounded_verdicts=None
        )
        _, blocks_on = assemble_context(
            nodes, seed_ids, similarity_scores, centrality_scores, max_tokens=60, grounded_verdicts=verdicts
        )

    contents_off = [b.content for b in blocks_off]
    contents_on = [b.content for b in blocks_on]
    has_isolated_off = any("_isolated_node_" in c for c in contents_off)
    has_isolated_on = any("_isolated_node_" in c for c in contents_on)

    # OFF: n3's high similarity includes it within the 2-block budget.
    assert has_isolated_off, "grounding OFF should include the high-sim isolated node"
    # ON: grounding pushes the isolated node out of the tight budget.
    assert not has_isolated_on, "grounding ON should exclude the isolated node"


def test_assemble_context():
    n1 = create_mock_node(uuid4(), content="Short", token_count=5)
    n2 = create_mock_node(uuid4(), content="Longer content", token_count=15)

    nodes = [n1, n2]
    seed_ids = [n1.id]
    similarity_scores = {n1.id: 0.9, n2.id: 0.5}
    centrality_scores = {n1.id: {"composite": 0.8}, n2.id: {"composite": 0.4}}

    with patch("tiktoken.get_encoding") as mock_get_encoding:
        mock_encoding = MagicMock()
        # Mock encode length
        mock_encoding.encode.side_effect = lambda x: [0] * len(x)
        mock_get_encoding.return_value = mock_encoding

        context, blocks = assemble_context(
            nodes, seed_ids, similarity_scores, centrality_scores, max_tokens=1000
        )

        assert len(blocks) == 2
        assert "Short" in context

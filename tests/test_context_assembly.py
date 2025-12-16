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

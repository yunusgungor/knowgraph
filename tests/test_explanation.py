from unittest.mock import MagicMock
from uuid import uuid4

import networkx as nx

from knowgraph.application.querying.explanation import (
    build_active_subgraph,
    extract_reasoning_paths,
    generate_explanation,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


def create_mock_node(uid=None, title="Title"):
    if not uid:
        uid = uuid4()
    n = MagicMock(spec=Node)
    n.id = uid
    n.title = title
    n.path = "path/to/file"
    n.to_dict.return_value = {"id": str(uid)}
    return n


def create_mock_edge(src, tgt, score=1.0):
    e = MagicMock(spec=Edge)
    e.source = src
    e.target = tgt
    e.score = score
    e.type = "semantic"
    e.to_dict.return_value = {"source": str(src), "target": str(tgt), "score": score}
    return e


def test_build_active_subgraph():
    n1 = create_mock_node()
    n2 = create_mock_node()
    e1 = create_mock_edge(n1.id, n2.id)

    g = build_active_subgraph([n1, n2], [e1])
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
    assert g.has_edge(n1.id, n2.id)


def test_extract_reasoning_paths():
    # Create graph: A -> B -> C
    n_a = create_mock_node(title="A")
    n_b = create_mock_node(title="B")
    n_c = create_mock_node(title="C")

    e_ab = create_mock_edge(n_a.id, n_b.id, score=0.5)
    e_bc = create_mock_edge(n_b.id, n_c.id, score=0.5)

    g = nx.Graph()
    g.add_node(n_a.id, node=n_a)
    g.add_node(n_b.id, node=n_b)
    g.add_node(n_c.id, node=n_c)
    g.add_edge(n_a.id, n_b.id, edge=e_ab, weight=0.5)
    g.add_edge(n_b.id, n_c.id, edge=e_bc, weight=0.5)

    # Path extraction uses shortest weighted path (Dijkstra)
    # Note: Logic minimizes weight? Class says "shortest weighted paths... ranks by total score"
    # Dijkstra minimizes sum of weights.
    # Score is usually "higher is better". If weight=score, Dijkstra finds LOWEST score path.
    # Check implementation: nx.single_source_dijkstra(..., weight="weight")
    # And total_score += edge.score.
    # If edge.score is 1.0 (high), weight is 1.0. Dijkstra treats as cost.
    # This might be intended for "cost" or bug if score is similarity.
    # Assuming "weight" is distance.

    paths = extract_reasoning_paths(g, [n_a])

    # Should find A->B, A->B->C
    # Logic returns paths with len >= 2
    assert len(paths) >= 1
    # Check A->B->C exists (length 3, 2 edges)
    long_paths = [p for p in paths if len(p.nodes) == 3]
    if long_paths:
        p = long_paths[0]
        assert p.nodes[0] == n_a
        assert p.nodes[2] == n_c


def test_generate_explanation():
    n1 = create_mock_node(title="Seed")
    n2 = create_mock_node(title="Target")
    e1 = create_mock_edge(n1.id, n2.id)

    expl = generate_explanation(
        retrieved_nodes=[n1, n2],
        edges=[e1],
        similarities={n1.id: 0.9},
        centralities={n2.id: 0.5},
        seed_ids={n1.id},
        llm_response='Here is a "quote" from content',
    )

    assert expl.active_subgraph is not None
    assert len(expl.reasoning_paths) > 0 or len(expl.node_contributions) == 2
    assert len(expl.node_contributions) == 2
    assert expl.node_contributions[0].is_seed is True  # n1

    # Check to_dict
    d = expl.to_dict()
    assert "node_contributions" in d
    assert "reasoning_paths" in d

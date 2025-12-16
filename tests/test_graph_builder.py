from unittest.mock import MagicMock
from uuid import uuid4

from knowgraph.application.indexing.graph_builder import (
    create_node_from_chunk,
    create_semantic_edges,
    validate_edges,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node
from knowgraph.infrastructure.parsing.chunker import Chunk


def create_mock_chunk(content="content", header="header", chunk_id="1"):
    return Chunk(
        content=content,
        header=header,
        chunk_id=chunk_id,
        line_start=1,
        line_end=10,
        token_count=10,
        header_depth=1,
        header_path="Header",
        has_code=False,
    )


def test_create_node_from_chunk():
    chunk = create_mock_chunk()
    node = create_node_from_chunk(chunk, "src/file.md")
    assert isinstance(node, Node)
    assert node.content == "content"
    assert node.path == "src/file.md"
    assert node.type == "text"  # Default classification


def test_create_node_type_classification():
    chunk = create_mock_chunk()
    chunk.has_code = True
    node = create_node_from_chunk(chunk, "src/code.py")
    assert node.type == "code"

    chunk.has_code = False
    node = create_node_from_chunk(chunk, "README.md")
    assert node.type == "readme"

    node = create_node_from_chunk(chunk, "config.yaml")
    assert node.type == "config"


def test_validate_edges():
    n1_id = uuid4()
    n2_id = uuid4()
    n1 = MagicMock(spec=Node)
    n1.id = n1_id
    n2 = MagicMock(spec=Node)
    n2.id = n2_id

    # Valid edge
    e1 = MagicMock(spec=Edge)
    e1.source = n1_id
    e1.target = n2_id

    # Dangling edge
    e2 = MagicMock(spec=Edge)
    e2.source = n1_id
    e2.target = uuid4()  # Unknown

    # Self loop
    e3 = MagicMock(spec=Edge)
    e3.source = n1_id
    e3.target = n1_id

    valid, warnings = validate_edges([e1, e2, e3], [n1, n2])
    assert len(valid) == 1
    assert valid[0] == e1
    assert len(warnings) == 2


def test_create_semantic_edges():
    n1 = MagicMock(spec=Node)
    n1.id = uuid4()
    n1.metadata = {"entities": [{"name": "A"}, {"name": "B"}]}

    n2 = MagicMock(spec=Node)
    n2.id = uuid4()
    n2.metadata = {"entities": [{"name": "B"}, {"name": "C"}]}

    n3 = MagicMock(spec=Node)
    n3.id = uuid4()
    n3.metadata = {"entities": [{"name": "D"}]}

    edges = create_semantic_edges([n1, n2, n3], threshold=0.1)

    # n1 and n2 share "B". Similarity: 1 / 3 = 0.33 > 0.1. Should match.
    # n1 and n3 share nothing.

    assert len(edges) == 1
    assert edges[0].source == n1.id
    assert edges[0].target == n2.id
    assert edges[0].type == "semantic"

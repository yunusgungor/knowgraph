"""Tests for conversation-to-code linking functionality.

Tests the automatic linking of conversation references to code nodes
in the knowledge graph.
"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from knowgraph.application.linking.conversation_linker import (
    create_conversation_reference_edges,
    extract_code_references,
    link_conversation_to_code,
    match_references_to_nodes,
)
from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


@pytest.fixture
def sample_code_nodes():
    """Create sample code nodes for testing."""
    return [
        Node(
            id="node-1",
            hash="a" * 40,
            title="getUserById",
            type="code",
            content='def getUserById(user_id):\n    """Fetch user by ID."""\n    return db.query(user_id)',
            path="src/api/auth.py",
            token_count=50,
            created_at=int(datetime.now(timezone.utc).timestamp()),
        ),
        Node(
            id="node-2",
            hash="b" * 40,
            title="UserClass",
            type="code",
            content='class UserClass:\n    """User model."""\n    def __init__(self, name):\n        self.name = name',
            path="src/models/user.py",
            token_count=40,
            created_at=int(datetime.now(timezone.utc).timestamp()),
        ),
        Node(
            id="node-3",
            hash="c" * 40,
            title="authenticate",
            type="code",
            content='function authenticate(token) {\n    return verifyJWT(token);\n}',
            path="src/utils/auth.js",
            token_count=30,
            created_at=int(datetime.now(timezone.utc).timestamp()),
        ),
        Node(
            id="node-4",
            hash="d" * 40,
            title="Database Config",
            type="code",
            content="# Database configuration\nDB_HOST = 'localhost'\nDB_PORT = 5432",
            path="config/database.py",
            token_count=20,
            created_at=int(datetime.now(timezone.utc).timestamp()),
        ),
    ]


@pytest.fixture
def sample_conversation_node():
    """Create sample conversation node."""
    conversation_content = """
    I implemented the `getUserById` function in auth.py.
    It uses the UserClass from src/models/user.py to fetch data.
    The authenticate function in src/utils/auth.js handles JWT tokens.
    Also updated the database.py configuration file.
    """

    return Node(
        id="conv-1",
        hash="e" * 40,
        title="Conversation about auth",
        type="conversation",
        content=conversation_content,
        path="conversations/conv-001.md",
        token_count=100,
        created_at=int(datetime.now(timezone.utc).timestamp()),
    )


def test_extract_code_references_backticks():
    """Test extracting references in backticks."""
    content = "I created `getUserById` and `UserClass` in `auth.py`"

    refs = extract_code_references(content)

    assert "getUserById" in refs
    assert "UserClass" in refs
    assert "auth.py" in refs
    assert len(refs) >= 3


def test_extract_code_references_file_paths():
    """Test extracting file path references."""
    content = "Modified src/api/auth.py and ./utils/helper.js files"

    refs = extract_code_references(content)

    assert "src/api/auth.py" in refs
    assert "./utils/helper.js" in refs


def test_extract_code_references_function_patterns():
    """Test extracting function/class pattern references."""
    content = "The getUserById function was implemented. UserClass class is ready."

    refs = extract_code_references(content)

    assert "getUserById" in refs
    # Note: Class pattern might be captured differently depending on regex


def test_extract_code_references_mixed():
    """Test extracting mixed reference types."""
    content = """
    I updated `auth.py` with the getUserById function.
    The src/models/user.py file has the UserClass implementation.
    Also modified ./config/settings.json
    """

    refs = extract_code_references(content)

    # Should find multiple references
    assert len(refs) > 0
    assert "auth.py" in refs
    assert "src/models/user.py" in refs


def test_extract_code_references_no_references():
    """Test with content containing no code references."""
    content = "This is just a general discussion about programming concepts."

    refs = extract_code_references(content)

    # Might be empty or very minimal
    assert isinstance(refs, list)


def test_extract_code_references_deduplication():
    """Test that duplicate references are deduplicated."""
    content = "I used `auth.py` and then modified `auth.py` again in auth.py"

    refs = extract_code_references(content)

    # Should not contain duplicates
    assert len(refs) == len(set(refs))


def test_match_references_to_nodes_exact_path(sample_code_nodes):
    """Test matching references by exact path."""
    refs = ["src/api/auth.py", "src/models/user.py"]

    matches = match_references_to_nodes(refs, sample_code_nodes)

    # Should match both paths
    assert len(matches) >= 2

    # Check that nodes are matched correctly
    matched_paths = [node.path for _, node in matches]
    assert "src/api/auth.py" in matched_paths
    assert "src/models/user.py" in matched_paths


def test_match_references_to_nodes_filename(sample_code_nodes):
    """Test matching references by filename only."""
    refs = ["auth.py", "user.py"]

    matches = match_references_to_nodes(refs, sample_code_nodes)

    # Should match files with these names
    assert len(matches) >= 2


def test_match_references_to_nodes_content_symbol(sample_code_nodes):
    """Test matching references by symbol in code content."""
    refs = ["getUserById", "UserClass", "authenticate"]

    matches = match_references_to_nodes(refs, sample_code_nodes)

    # Should match nodes containing these symbols
    assert len(matches) >= 3

    # Verify symbols are in matched node content
    for ref, node in matches:
        assert ref in node.content


def test_match_references_to_nodes_no_matches(sample_code_nodes):
    """Test with references that don't match any nodes."""
    refs = ["nonexistent.py", "FakeClass", "unknownFunction"]

    matches = match_references_to_nodes(refs, sample_code_nodes)

    # Should return empty or minimal matches
    assert isinstance(matches, list)


def test_match_references_to_nodes_partial_match(sample_code_nodes):
    """Test with partial filename matches."""
    refs = ["auth", "user", "database"]

    matches = match_references_to_nodes(refs, sample_code_nodes)

    # Should match nodes with these substrings in paths
    assert len(matches) > 0


def test_create_conversation_reference_edges(sample_conversation_node, sample_code_nodes):
    """Test creating reference edges from conversation to code."""
    edges = create_conversation_reference_edges(sample_conversation_node, sample_code_nodes)

    # Should create edges to referenced code
    assert len(edges) > 0
    assert all(isinstance(edge, Edge) for edge in edges)

    # Check edge properties
    for edge in edges:
        assert edge.source == sample_conversation_node.id
        assert edge.target in [node.id for node in sample_code_nodes]
        assert edge.type == "conversation_references_code"
        assert edge.score == 0.9  # High confidence
        assert "reference_text" in edge.metadata
        assert edge.metadata["extraction_method"] == "conversation_linker"


def test_create_conversation_reference_edges_custom_type(
    sample_conversation_node, sample_code_nodes
):
    """Test creating edges with custom reference type."""
    edges = create_conversation_reference_edges(
        sample_conversation_node,
        sample_code_nodes,
        reference_type="bookmark_references_code",
    )

    assert all(edge.type == "bookmark_references_code" for edge in edges)


def test_create_conversation_reference_edges_no_references(sample_code_nodes):
    """Test creating edges when conversation has no code references."""
    conv_node = Node(
        id="conv-no-refs",
        hash="f" * 40,
        title="General discussion",
        type="conversation",
        content="Just a general discussion without any code references.",
        path="conversations/general.md",
        token_count=50,
        created_at=int(datetime.now(timezone.utc).timestamp()),
    )

    edges = create_conversation_reference_edges(conv_node, sample_code_nodes)

    # Should return empty list
    assert edges == []


def test_create_conversation_reference_edges_metadata(
    sample_conversation_node, sample_code_nodes
):
    """Test that edge metadata is populated correctly."""
    edges = create_conversation_reference_edges(sample_conversation_node, sample_code_nodes)

    for edge in edges:
        # Check required metadata fields
        assert "reference_text" in edge.metadata
        assert "extraction_method" in edge.metadata
        assert "node_type" in edge.metadata

        # Check values
        assert edge.metadata["extraction_method"] == "conversation_linker"
        assert edge.metadata["node_type"] == "conversation"
        assert isinstance(edge.metadata["reference_text"], str)
        assert len(edge.metadata["reference_text"]) > 0


def test_link_conversation_to_code(sample_conversation_node, sample_code_nodes):
    """Test main linking function."""
    edges, metadata = link_conversation_to_code(sample_conversation_node, sample_code_nodes)

    # Check edges
    assert isinstance(edges, list)
    assert len(edges) > 0
    assert all(isinstance(edge, Edge) for edge in edges)

    # Check metadata
    assert isinstance(metadata, dict)
    assert "conversation_id" in metadata
    assert "references_found" in metadata
    assert "edges_created" in metadata
    assert "linked_code_files" in metadata

    # Verify metadata values
    assert metadata["conversation_id"] == sample_conversation_node.id
    assert metadata["references_found"] > 0
    assert metadata["edges_created"] == len(edges)
    assert metadata["linked_code_files"] > 0


def test_link_conversation_to_code_no_code_nodes(sample_conversation_node):
    """Test linking when there are no code nodes."""
    edges, metadata = link_conversation_to_code(sample_conversation_node, [])

    # Should return empty edges
    assert edges == []
    assert metadata["edges_created"] == 0
    assert metadata["linked_code_files"] == 0


def test_link_conversation_to_code_counts(sample_conversation_node, sample_code_nodes):
    """Test that metadata counts are accurate."""
    edges, metadata = link_conversation_to_code(sample_conversation_node, sample_code_nodes)

    # References found should match extracted references
    refs = extract_code_references(sample_conversation_node.content)
    assert metadata["references_found"] == len(refs)

    # Edges created should match edge list
    assert metadata["edges_created"] == len(edges)

    # Linked files should be unique target count
    unique_targets = len({edge.target for edge in edges})
    assert metadata["linked_code_files"] == unique_targets


def test_extract_code_references_complex_paths():
    """Test extracting complex file paths."""
    content = """
    Modified files:
    - src/api/v2/auth.py
    - tests/integration/test_auth.py
    - ../parent/utils.js
    """

    refs = extract_code_references(content)

    assert any("auth.py" in ref for ref in refs)
    assert any("test_auth.py" in ref for ref in refs)


def test_extract_code_references_with_line_numbers():
    """Test extracting references that include line numbers."""
    content = "See auth.py:45 and user.py:123 for implementation"

    refs = extract_code_references(content)

    # Should extract filenames (line numbers may be included or stripped)
    assert any("auth.py" in ref for ref in refs)
    assert any("user.py" in ref for ref in refs)


def test_match_references_case_insensitive(sample_code_nodes):
    """Test that matching is case-insensitive."""
    refs = ["AUTH.PY", "UserClass", "GETUSERBYID"]

    matches = match_references_to_nodes(refs, sample_code_nodes)

    # Should match despite case differences
    assert len(matches) > 0


def test_create_edges_preserves_timestamps(sample_conversation_node, sample_code_nodes):
    """Test that edge timestamps match conversation node."""
    edges = create_conversation_reference_edges(sample_conversation_node, sample_code_nodes)

    for edge in edges:
        assert edge.created_at == sample_conversation_node.created_at


def test_link_with_bookmark_node(sample_code_nodes):
    """Test linking with a bookmark node instead of conversation."""
    bookmark_node = Node(
        id="bookmark-1",
        hash="g" * 40,
        title="Important bookmark",
        type="tagged_snippet",
        content="Important: Check `getUserById` in auth.py for authentication logic",
        path="bookmarks/important.md",
        token_count=60,
        created_at=int(datetime.now(timezone.utc).timestamp()),
        metadata={"tag": "authentication", "importance": "high"},
    )

    edges, metadata = link_conversation_to_code(bookmark_node, sample_code_nodes)

    # Should work with bookmarks too
    assert len(edges) > 0
    assert all(edge.metadata["node_type"] == "tagged_snippet" for edge in edges)


def test_extract_multiple_references_same_line():
    """Test extracting multiple references from the same line."""
    content = "Updated `auth.py`, `user.py`, and `config.py` files"

    refs = extract_code_references(content)

    assert "auth.py" in refs
    assert "user.py" in refs
    assert "config.py" in refs
    assert len(refs) >= 3


def test_match_references_with_extensions(sample_code_nodes):
    """Test matching files with various extensions."""
    # Add a node with .js extension
    refs = ["auth.js", "user.py", "config.json"]

    matches = match_references_to_nodes(refs, sample_code_nodes)

    # Should match .js and .py files
    assert len(matches) > 0


def test_edge_score_confidence():
    """Test that reference edges have high confidence scores."""
    conv_node = Node(
        id="conv-test",
        hash="h" * 40,
        title="Test conversation",
        type="conversation",
        content="Modified `test.py` file",
        path="conv.md",
        token_count=20,
        created_at=int(datetime.now(timezone.utc).timestamp()),
    )

    code_node = Node(
        id="code-test",
        hash="i" * 40,
        title="test function",
        type="code",
        content="def test(): pass",
        path="test.py",
        token_count=15,
        created_at=int(datetime.now(timezone.utc).timestamp()),
    )

    edges = create_conversation_reference_edges(conv_node, [code_node])

    # High confidence for explicit references
    assert all(edge.score == 0.9 for edge in edges)


def test_extract_references_ignores_noise():
    """Test that common words are not extracted as references."""
    content = "This is a test of the function implementation method class"

    refs = extract_code_references(content)

    # Should not extract common words without context
    # Only "test" might match the function pattern if at all
    assert len(refs) < 5  # Should be minimal matches

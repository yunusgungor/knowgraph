"""Tests for snippet tagging functionality."""


import pytest

from knowgraph.application.tagging.snippet_tagger import (
    TaggedSnippet,
    create_tagged_snippet,
    format_tagged_snippet_markdown,
)


def test_create_tagged_snippet():
    """Test creating a tagged snippet node."""
    tag = "fastapi jwt detayı"
    content = "Here's how to implement JWT authentication in FastAPI..."

    node = create_tagged_snippet(
        tag=tag,
        content=content,
        conversation_id="conv-123",
        user_question="How do I implement JWT auth?",
    )

    assert node.metadata["tag"] == tag
    assert node.metadata["type"] == "tagged_snippet"
    assert node.metadata["conversation_id"] == "conv-123"
    assert node.metadata["role"] == "tagged_snippet"
    assert node.content == content


def test_format_tagged_snippet_markdown():
    """Test formatting tagged snippet as markdown."""
    from datetime import datetime

    snippet = TaggedSnippet(
        tag="test tag",
        content="Test content here",
        conversation_id="conv-456",
        user_question="Test question?",
        timestamp=datetime(2025, 12, 17, 21, 0, 0),
    )

    markdown = format_tagged_snippet_markdown(snippet)

    assert "# Tagged Snippet: test tag" in markdown
    assert "**Tag**: `test tag`" in markdown
    assert "**Timestamp**: 2025-12-17 21:00:00" in markdown
    assert "**Conversation ID**: conv-456" in markdown
    assert "**User Question**: Test question?" in markdown
    assert "Test content here" in markdown


@pytest.mark.skip(reason="Requires OpenAI API key - integration test")
@pytest.mark.asyncio
async def test_index_tagged_snippet(tmp_path):
    """Test indexing a tagged snippet (integration test)."""
    from knowgraph.application.tagging.snippet_tagger import index_tagged_snippet

    tag = "test snippet"
    content = "Important code example:\n\n```python\nprint('hello')\n```"

    node = create_tagged_snippet(
        tag=tag,
        content=content,
    )

    graph_path = tmp_path / "test_graphstore"
    graph_path.mkdir()

    # Index the snippet (requires OpenAI API key)
    await index_tagged_snippet(node, graph_path)

    # Check that manifest was created
    manifest_path = graph_path / "metadata" / "manifest.json"
    assert manifest_path.exists()

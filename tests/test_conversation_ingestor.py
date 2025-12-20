"""Tests for conversation ingestor.

Tests the conversion of conversation files from various AI editors
to markdown format for indexing.
"""

import tempfile
from pathlib import Path

import pytest

from knowgraph.infrastructure.parsing.conversation_ingestor import (
    ConversationIngestorError,
    ingest_conversation,
)
from knowgraph.infrastructure.parsing.conversation_parser import (
    ConversationData,
    Message,
)


@pytest.fixture
def sample_conversation_file(tmp_path):
    """Create a sample conversation JSON file."""
    import json

    conversation_data = {
        "id": "test-conv-123",
        "title": "Test Conversation",
        "created_at": "2024-01-15T10:30:00Z",
        "messages": [
            {
                "id": "msg-1",
                "role": "user",
                "content": "How do I implement authentication?",
                "timestamp": "2024-01-15T10:30:00Z",
            },
            {
                "id": "msg-2",
                "role": "assistant",
                "content": "You can use JWT tokens. Here's an example:\n\n```python\ndef authenticate(token):\n    return verify_jwt(token)\n```",
                "timestamp": "2024-01-15T10:31:00Z",
            },
        ],
    }

    conv_file = tmp_path / "test_conversation.json"
    with open(conv_file, "w", encoding="utf-8") as f:
        json.dump(conversation_data, f)

    return conv_file


@pytest.fixture
def sample_aichat_file(tmp_path):
    """Create a sample .aichat file (Cursor format)."""
    aichat_content = """# Test Chat

**User:**
How do I write a test?

**Assistant:**
Here's how to write a pytest test:

```python
def test_example():
    assert True
```
"""

    aichat_file = tmp_path / "test_chat.aichat"
    with open(aichat_file, "w", encoding="utf-8") as f:
        f.write(aichat_content)

    return aichat_file


@pytest.mark.asyncio
async def test_ingest_conversation_success(sample_conversation_file):
    """Test successful conversation ingestion."""
    markdown_content, output_path = await ingest_conversation(sample_conversation_file)

    # Check markdown content
    assert markdown_content
    assert "Test Conversation" in markdown_content  # Title is in the header
    assert "How do I implement authentication?" in markdown_content
    assert "You can use JWT tokens" in markdown_content
    assert "```python" in markdown_content
    assert "def authenticate" in markdown_content

    # Check output file
    assert output_path.exists()
    assert output_path.suffix == ".md"
    assert "conversation_" in output_path.name


@pytest.mark.asyncio
async def test_ingest_conversation_with_custom_output(sample_conversation_file, tmp_path):
    """Test ingestion with custom output path."""
    custom_output = tmp_path / "custom_output.md"

    markdown_content, output_path = await ingest_conversation(
        sample_conversation_file, custom_output
    )

    # Check output path
    assert output_path == custom_output
    assert custom_output.exists()

    # Verify content
    with open(custom_output, encoding="utf-8") as f:
        content = f.read()

    assert content == markdown_content
    assert "Test Conversation" in content


@pytest.mark.asyncio
async def test_ingest_conversation_creates_parent_dirs(sample_conversation_file, tmp_path):
    """Test that parent directories are created if they don't exist."""
    nested_output = tmp_path / "level1" / "level2" / "output.md"

    markdown_content, output_path = await ingest_conversation(
        sample_conversation_file, nested_output
    )

    assert nested_output.exists()
    assert nested_output.parent.exists()


@pytest.mark.asyncio
async def test_ingest_conversation_nonexistent_file():
    """Test ingestion with nonexistent file."""
    nonexistent = Path("/tmp/nonexistent_conversation.json")

    with pytest.raises(ConversationIngestorError) as exc_info:
        await ingest_conversation(nonexistent)

    assert "Failed to ingest conversation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ingest_conversation_invalid_format(tmp_path):
    """Test ingestion with invalid file format."""
    invalid_file = tmp_path / "invalid.json"
    with open(invalid_file, "w", encoding="utf-8") as f:
        f.write("not valid json {{{")

    with pytest.raises(ConversationIngestorError) as exc_info:
        await ingest_conversation(invalid_file)

    assert "Failed to ingest conversation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ingest_conversation_temp_file_cleanup(sample_conversation_file):
    """Test that temp files are created but not immediately deleted."""
    markdown_content, output_path = await ingest_conversation(sample_conversation_file)

    # Temp file should exist after ingestion
    assert output_path.exists()

    # Should be in system temp directory
    assert str(output_path).startswith(tempfile.gettempdir())


@pytest.mark.asyncio
async def test_ingest_conversation_preserves_code_blocks(sample_conversation_file):
    """Test that code blocks are preserved correctly."""
    markdown_content, _ = await ingest_conversation(sample_conversation_file)

    # Check code block formatting
    assert "```python" in markdown_content
    assert "def authenticate(token):" in markdown_content
    assert "return verify_jwt(token)" in markdown_content
    assert "```" in markdown_content


@pytest.mark.asyncio
async def test_ingest_conversation_empty_messages(tmp_path):
    """Test ingestion with conversation containing no messages."""
    import json

    empty_conv = {
        "id": "empty-123",
        "title": "Empty Conversation",
        "created_at": "2024-01-15T10:30:00Z",
        "messages": [],
    }

    conv_file = tmp_path / "empty.json"
    with open(conv_file, "w", encoding="utf-8") as f:
        json.dump(empty_conv, f)

    # Empty conversations might not parse correctly - expect error
    with pytest.raises(ConversationIngestorError):
        await ingest_conversation(conv_file)


@pytest.mark.asyncio
async def test_ingest_conversation_unicode_content(tmp_path):
    """Test ingestion with Unicode characters."""
    import json

    unicode_conv = {
        "id": "unicode-123",
        "title": "Türkçe Konuşma 🚀",
        "created_at": "2024-01-15T10:30:00Z",
        "messages": [
            {
                "id": "msg-1",
                "role": "user",
                "content": "Merhaba! Türkçe karakter testi: çğıöşü",
                "timestamp": "2024-01-15T10:30:00Z",
            },
        ],
    }

    conv_file = tmp_path / "unicode.json"
    with open(conv_file, "w", encoding="utf-8") as f:
        json.dump(unicode_conv, f, ensure_ascii=False)

    markdown_content, output_path = await ingest_conversation(conv_file)

    # Check Unicode preservation
    assert "Türkçe Konuşma 🚀" in markdown_content
    assert "çğıöşü" in markdown_content

    # Verify file encoding
    with open(output_path, encoding="utf-8") as f:
        content = f.read()
    assert "çğıöşü" in content


@pytest.mark.asyncio
async def test_ingest_conversation_multiple_code_blocks(tmp_path):
    """Test ingestion with multiple code blocks in different languages."""
    import json

    multi_code_conv = {
        "id": "multi-code-123",
        "title": "Multi-Language Code",
        "created_at": "2024-01-15T10:30:00Z",
        "messages": [
            {
                "id": "msg-1",
                "role": "assistant",
                "content": "Here's Python:\n\n```python\nprint('hello')\n```\n\nAnd JavaScript:\n\n```javascript\nconsole.log('world');\n```",
                "timestamp": "2024-01-15T10:30:00Z",
            },
        ],
    }

    conv_file = tmp_path / "multi_code.json"
    with open(conv_file, "w", encoding="utf-8") as f:
        json.dump(multi_code_conv, f)

    markdown_content, _ = await ingest_conversation(conv_file)

    # Check both code blocks
    assert "```python" in markdown_content
    assert "print('hello')" in markdown_content
    assert "```javascript" in markdown_content
    assert "console.log('world')" in markdown_content


@pytest.mark.asyncio
async def test_ingest_conversation_long_content(tmp_path):
    """Test ingestion with very long conversation."""
    import json

    long_message = "This is a very long message. " * 1000

    long_conv = {
        "id": "long-123",
        "title": "Long Conversation",
        "created_at": "2024-01-15T10:30:00Z",
        "messages": [
            {
                "id": "msg-1",
                "role": "user",
                "content": long_message,
                "timestamp": "2024-01-15T10:30:00Z",
            },
        ],
    }

    conv_file = tmp_path / "long.json"
    with open(conv_file, "w", encoding="utf-8") as f:
        json.dump(long_conv, f)

    markdown_content, output_path = await ingest_conversation(conv_file)

    # Should handle long content
    assert len(markdown_content) > 10000
    assert output_path.exists()


@pytest.mark.asyncio
async def test_ingest_conversation_special_characters_in_path(tmp_path):
    """Test ingestion with special characters in output path."""
    import json

    conv_data = {
        "id": "test-123",
        "title": "Test",
        "created_at": "2024-01-15T10:30:00Z",
        "messages": [
            {
                "id": "msg-1",
                "role": "user",
                "content": "Test message",
                "timestamp": "2024-01-15T10:30:00Z",
            }
        ],
    }

    conv_file = tmp_path / "test.json"
    with open(conv_file, "w", encoding="utf-8") as f:
        json.dump(conv_data, f)

    # Path with spaces and special chars
    output_path = tmp_path / "My Conversation (2024-01).md"

    markdown_content, result_path = await ingest_conversation(conv_file, output_path)

    assert result_path.exists()
    assert result_path == output_path

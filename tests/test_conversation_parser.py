"""Tests for conversation parser."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from knowgraph.infrastructure.parsing.conversation_parser import (
    ConversationData,
    Message,
    conversation_to_markdown,
    detect_conversation_format,
    extract_code_blocks,
    parse_conversation,
)


def test_extract_code_blocks():
    """Test code block extraction from markdown."""
    text = """
Some text here.

```python
def hello():
    print("world")
```

More text.

```javascript
console.log("test");
```
"""
    blocks = extract_code_blocks(text)

    assert len(blocks) == 2
    assert blocks[0].language == "python"
    assert "def hello()" in blocks[0].content
    assert blocks[1].language == "javascript"
    assert "console.log" in blocks[1].content


def test_conversation_to_markdown():
    """Test conversation to markdown conversion."""
    conversation = ConversationData(
        id="test-123",
        title="Test Conversation",
        messages=[
            Message(
                role="user",
                content="How do I use FastAPI?",
                timestamp=datetime(2025, 12, 17, 14, 30),
                has_code=False,
            ),
            Message(
                role="assistant",
                content="Here's a basic example:\n\n```python\nfrom fastapi import FastAPI\napp = FastAPI()\n```",
                timestamp=datetime(2025, 12, 17, 14, 31),
                has_code=True,
            ),
        ],
        created_at=datetime(2025, 12, 17, 14, 30),
        updated_at=datetime(2025, 12, 17, 14, 31),
        metadata={"source": "test"},
    )

    markdown = conversation_to_markdown(conversation)

    assert "# Conversation: Test Conversation" in markdown
    assert "test-123" in markdown
    assert "How do I use FastAPI?" in markdown
    assert "```python" in markdown
    assert "from fastapi import FastAPI" in markdown
    assert "👤" in markdown  # user emoji
    assert "🤖" in markdown  # assistant emoji


def test_detect_conversation_format_aichat():
    """Test detection of .aichat format."""
    path = Path("/test/conversation.aichat")
    format_type = detect_conversation_format(path)
    assert format_type == "cursor"


def test_detect_conversation_format_antigravity(tmp_path):
    """Test detection of antigravity format."""
    log_file = tmp_path / ".gemini" / "antigravity" / "brain" / "test.txt"
    log_file.parent.mkdir(parents=True)
    log_file.write_text("test content")

    format_type = detect_conversation_format(log_file)
    assert format_type == "antigravity"


def test_detect_conversation_format_claude(tmp_path):
    """Test detection of Claude format."""
    json_file = tmp_path / "test_conversation.json"
    data = {"chat_messages": [], "uuid": "test-123"}
    json_file.write_text(json.dumps(data))

    format_type = detect_conversation_format(json_file)
    assert format_type == "claude"


def test_parse_conversation_unknown_format(tmp_path):
    """Test parsing unknown format returns None."""
    unknown_file = tmp_path / "unknown.xyz"
    unknown_file.write_text("test")

    result = parse_conversation(unknown_file)
    assert result is None


@pytest.mark.integration
def test_parse_antigravity_log(tmp_path):
    """Test parsing Antigravity log file."""
    log_content = """
<USER_REQUEST>
How do I implement authentication?
</USER_REQUEST>

Some response here.

<USER_REQUEST>
Can you show me an example with FastAPI?

```python
from fastapi import FastAPI
app = FastAPI()
```
</USER_REQUEST>
"""
    log_file = tmp_path / ".gemini" / "antigravity" / "brain" / "conv-123" / "test_log.txt"
    log_file.parent.mkdir(parents=True)
    log_file.write_text(log_content)

    from knowgraph.infrastructure.parsing.conversation_parser import parse_antigravity_log

    conversation = parse_antigravity_log(log_file)

    assert conversation.id == "conv-123"
    assert len(conversation.messages) == 2
    assert conversation.messages[0].role == "user"
    assert "authentication" in conversation.messages[0].content
    assert conversation.messages[1].has_code
    assert len(conversation.messages[1].code_blocks) == 1
    assert conversation.messages[1].code_blocks[0].language == "python"

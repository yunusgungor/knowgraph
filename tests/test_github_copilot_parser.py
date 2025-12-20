"""Tests for GitHub Copilot conversation parser."""

import json

from knowgraph.infrastructure.parsing.conversation_parser import (
    detect_conversation_format,
    parse_github_copilot_chat,
)


def test_detect_github_copilot_exported_json(tmp_path):
    """Test detection of GitHub Copilot exported JSON."""
    json_file = tmp_path / "copilot_chat_export.json"
    data = {
        "sessionId": "session-123",
        "messages": [
            {"role": "user", "content": "How do I use FastAPI?"},
            {"role": "assistant", "content": "Here's how..."},
        ],
    }
    json_file.write_text(json.dumps(data))

    format_type = detect_conversation_format(json_file)
    assert format_type == "github_copilot"


def test_detect_github_copilot_entries_json(tmp_path):
    """Test detection of VSCode workspace storage entries.json."""
    entries_file = tmp_path / "entries.json"
    data = {
        "entries": [
            {"sender": "user", "text": "Test message"},
            {"sender": "copilot", "text": "Response"},
        ]
    }
    entries_file.write_text(json.dumps(data))

    format_type = detect_conversation_format(entries_file)
    assert format_type == "github_copilot"


def test_parse_github_copilot_exported_format(tmp_path):
    """Test parsing GitHub Copilot exported JSON format."""
    json_file = tmp_path / "copilot_export.json"
    data = {
        "id": "chat-456",
        "title": "FastAPI Discussion",
        "sessionId": "session-456",
        "created_at": "2025-12-17T14:30:00",
        "messages": [
            {
                "role": "user",
                "content": "How do I implement authentication in FastAPI?",
                "timestamp": "2025-12-17T14:30:15",
            },
            {
                "role": "assistant",
                "content": "Here's how to implement JWT authentication:\n\n```python\nfrom fastapi import Depends\n```",
                "timestamp": "2025-12-17T14:30:45",
            },
        ],
    }
    json_file.write_text(json.dumps(data))

    conversation = parse_github_copilot_chat(json_file)

    assert conversation.id == "chat-456"
    assert conversation.title == "FastAPI Discussion"
    assert len(conversation.messages) == 2
    assert conversation.messages[0].role == "user"
    assert "authentication" in conversation.messages[0].content
    assert conversation.messages[1].role == "assistant"
    assert conversation.messages[1].has_code
    assert len(conversation.messages[1].code_blocks) == 1
    assert conversation.metadata["source"] == "github_copilot"


def test_parse_github_copilot_entries_format(tmp_path):
    """Test parsing VSCode workspace storage entries.json format."""
    entries_file = tmp_path / "entries.json"
    data = {
        "entries": [
            {
                "sender": "user",
                "value": "Show me an example of async functions",
                "created_at": "2025-12-17T15:00:00",
            },
            {
                "sender": "copilot",
                "value": "Here's an async example:\n\n```python\nasync def fetch_data():\n    pass\n```",
                "created_at": "2025-12-17T15:00:30",
            },
        ]
    }
    entries_file.write_text(json.dumps(data))

    conversation = parse_github_copilot_chat(entries_file)

    assert len(conversation.messages) == 2
    assert conversation.messages[0].role == "user"
    assert "async functions" in conversation.messages[0].content
    assert conversation.messages[1].role == "assistant"
    assert conversation.messages[1].has_code
    assert conversation.metadata["source"] == "github_copilot"


def test_parse_github_copilot_minimal_format(tmp_path):
    """Test parsing minimal GitHub Copilot format."""
    json_file = tmp_path / "minimal_chat.json"
    data = {
        "messages": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
    }
    json_file.write_text(json.dumps(data))

    conversation = parse_github_copilot_chat(json_file)

    assert len(conversation.messages) == 2
    assert conversation.messages[0].content == "Hello"
    assert conversation.messages[1].content == "Hi there!"

"""Conversation parser for AI code editor chat histories.

Supports parsing and converting conversation histories from:
- Antigravity (Gemini) conversation logs
- Cursor .aichat files
- Claude Desktop conversation exports
- GitHub Copilot chat (VSCode)
- VSCode Copilot exported JSON
- Generic JSON conversation format
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

MessageRole = Literal["user", "assistant", "system"]


@dataclass
class CodeBlock:
    """Code snippet extracted from a message."""

    language: str
    content: str
    line_start: int | None = None
    line_end: int | None = None


@dataclass
class Message:
    """Single message in a conversation."""

    role: MessageRole
    content: str
    timestamp: datetime
    has_code: bool = False
    code_blocks: list[CodeBlock] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ConversationData:
    """Complete conversation with metadata."""

    id: str
    title: str
    messages: list[Message]
    created_at: datetime
    updated_at: datetime
    metadata: dict = field(default_factory=dict)


def extract_code_blocks(text: str) -> list[CodeBlock]:
    """Extract code blocks from markdown text.

    Args:
    ----
        text: Markdown text containing code blocks

    Returns:
    -------
        List of extracted code blocks

    """
    code_blocks = []
    # Match ```language\ncode\n```
    pattern = r"```(\w+)?\n(.*?)```"
    matches = re.finditer(pattern, text, re.DOTALL)

    for match in matches:
        language = match.group(1) or "text"
        content = match.group(2).strip()
        code_blocks.append(CodeBlock(language=language, content=content))

    return code_blocks


def parse_antigravity_log(log_path: Path) -> ConversationData:
    """Parse Antigravity conversation log file.

    Antigravity logs are plain text with task boundaries and tool calls.

    Args:
    ----
        log_path: Path to log file

    Returns:
    -------
        Parsed conversation data

    """
    content = log_path.read_text(encoding="utf-8")

    # Extract conversation ID from path
    # Path structure: .../brain/{conversation-id}/logs/file.txt
    # We want the conversation-id part
    parts = log_path.parts
    try:
        brain_idx = parts.index("brain")
        conversation_id = (
            parts[brain_idx + 1] if brain_idx + 1 < len(parts) else log_path.parent.name
        )
    except (ValueError, IndexError):
        conversation_id = log_path.parent.name

    # Extract title from filename
    title = log_path.stem.replace("_", " ").title()

    # Parse messages from log
    messages = []

    # Simple parsing: split by task boundaries or user requests
    # This is a simplified version - can be enhanced
    user_pattern = r"<USER_REQUEST>(.*?)</USER_REQUEST>"
    user_matches = list(re.finditer(user_pattern, content, re.DOTALL))

    if user_matches:
        for match in user_matches:
            user_content = match.group(1).strip()
            has_code = "```" in user_content
            code_blocks = extract_code_blocks(user_content) if has_code else []

            messages.append(
                Message(
                    role="user",
                    content=user_content,
                    timestamp=datetime.now(),  # Log doesn't have timestamps
                    has_code=has_code,
                    code_blocks=code_blocks,
                )
            )
    else:
        # Fallback: Try identifying 'User:' or 'Human:' lines
        # This covers cases where logs are plain text dumps
        fallback_pattern = (
            r"(?:User|Human|Prompt):\s*(.*?)(?=\n(?:User|Human|Prompt|Assistant|Model|System):|$)"
        )
        fallback_matches = list(re.finditer(fallback_pattern, content, re.DOTALL | re.IGNORECASE))

        if not fallback_matches:
            # Last resort: Treat the whole file as one user message if it's not too large
            # but check if it looks like a conversation
            if len(content) > 10 and len(content) < 50000:
                messages.append(
                    Message(
                        role="user",
                        content=content.strip(),
                        timestamp=datetime.now(),
                        has_code="```" in content,
                        code_blocks=extract_code_blocks(content) if "```" in content else [],
                    )
                )

        for match in fallback_matches:
            user_content = match.group(1).strip()
            if not user_content:
                continue

            has_code = "```" in user_content
            code_blocks = extract_code_blocks(user_content) if has_code else []

            messages.append(
                Message(
                    role="user",
                    content=user_content,
                    timestamp=datetime.now(),
                    has_code=has_code,
                    code_blocks=code_blocks,
                )
            )

    # Get file stats for timestamps
    stat = log_path.stat()
    created_at = datetime.fromtimestamp(stat.st_ctime)
    updated_at = datetime.fromtimestamp(stat.st_mtime)

    return ConversationData(
        id=conversation_id,
        title=title,
        messages=messages,
        created_at=created_at,
        updated_at=updated_at,
        metadata={"source": "antigravity", "log_path": str(log_path)},
    )


def parse_cursor_aichat(aichat_path: Path) -> ConversationData:
    """Parse Cursor .aichat file.

    Cursor stores conversations in JSON format.

    Args:
    ----
        aichat_path: Path to .aichat file

    Returns:
    -------
        Parsed conversation data

    """
    data = json.loads(aichat_path.read_text(encoding="utf-8"))

    messages = []
    for msg in data.get("messages", []):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        has_code = "```" in content
        code_blocks = extract_code_blocks(content) if has_code else []

        # Parse timestamp
        timestamp_str = msg.get("timestamp")
        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()

        messages.append(
            Message(
                role=role,  # type: ignore
                content=content,
                timestamp=timestamp,
                has_code=has_code,
                code_blocks=code_blocks,
            )
        )

    conversation_id = data.get("id", aichat_path.stem)
    title = data.get("title", aichat_path.stem)

    return ConversationData(
        id=conversation_id,
        title=title,
        messages=messages,
        created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
        updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
        metadata={"source": "cursor", "file_path": str(aichat_path)},
    )


def parse_claude_conversation(json_path: Path) -> ConversationData:
    """Parse Claude Desktop conversation export.

    Claude exports conversations as JSON.

    Args:
    ----
        json_path: Path to JSON file

    Returns:
    -------
        Parsed conversation data

    """
    data = json.loads(json_path.read_text(encoding="utf-8"))

    messages = []
    for msg in data.get("chat_messages", []):
        role = "assistant" if msg.get("sender") == "assistant" else "user"
        content = msg.get("text", "")
        has_code = "```" in content
        code_blocks = extract_code_blocks(content) if has_code else []

        # Parse timestamp
        timestamp_str = msg.get("created_at")
        timestamp = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.now()

        messages.append(
            Message(
                role=role,  # type: ignore
                content=content,
                timestamp=timestamp,
                has_code=has_code,
                code_blocks=code_blocks,
            )
        )

    conversation_id = data.get("uuid", json_path.stem)
    title = data.get("name", json_path.stem)

    return ConversationData(
        id=conversation_id,
        title=title,
        messages=messages,
        created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
        updated_at=datetime.fromisoformat(data.get("updated_at", datetime.now().isoformat())),
        metadata={"source": "claude", "file_path": str(json_path)},
    )


def parse_github_copilot_chat(json_path: Path) -> ConversationData:
    """Parse GitHub Copilot chat export (VSCode).

    GitHub Copilot exports chat sessions as JSON with a specific structure.

    Args:
    ----
        json_path: Path to exported JSON file

    Returns:
    -------
        Parsed conversation data

    """
    data = json.loads(json_path.read_text(encoding="utf-8"))

    messages = []

    # Handle both exported format and entries.json format
    chat_messages = data.get("messages", data.get("entries", []))

    for msg in chat_messages:
        # Determine role
        role = "user"
        if isinstance(msg, dict):
            if msg.get("role") == "assistant" or msg.get("sender") == "copilot":
                role = "assistant"
            elif msg.get("role") == "user" or msg.get("sender") == "user":
                role = "user"

        # Extract content
        content = ""
        if isinstance(msg, dict):
            content = msg.get("content", msg.get("text", msg.get("value", "")))
        elif isinstance(msg, str):
            content = msg

        has_code = "```" in content
        code_blocks = extract_code_blocks(content) if has_code else []

        # Parse timestamp
        timestamp = datetime.now()
        if isinstance(msg, dict):
            timestamp_str = msg.get("timestamp", msg.get("created_at"))
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                except (ValueError, TypeError):
                    pass

        messages.append(
            Message(
                role=role,  # type: ignore
                content=content,
                timestamp=timestamp,
                has_code=has_code,
                code_blocks=code_blocks,
                metadata={"editor": "github_copilot"},
            )
        )

    conversation_id = data.get("id", data.get("sessionId", json_path.stem))
    title = data.get("title", data.get("name", json_path.stem))

    # Get timestamps
    created_at = datetime.now()
    updated_at = datetime.now()

    if "created_at" in data:
        try:
            created_at = datetime.fromisoformat(data["created_at"])
        except (ValueError, TypeError):
            pass

    if "updated_at" in data:
        try:
            updated_at = datetime.fromisoformat(data["updated_at"])
        except (ValueError, TypeError):
            pass
    elif messages:
        # Use last message timestamp as updated_at
        updated_at = messages[-1].timestamp

    return ConversationData(
        id=conversation_id,
        title=title,
        messages=messages,
        created_at=created_at,
        updated_at=updated_at,
        metadata={"source": "github_copilot", "file_path": str(json_path)},
    )


def conversation_to_markdown(conversation: ConversationData) -> str:
    """Convert conversation to markdown format.

    Args:
    ----
        conversation: Parsed conversation data

    Returns:
    -------
        Markdown formatted conversation

    """
    lines = []

    # Header
    lines.append(f"# Conversation: {conversation.title}")
    lines.append("")
    lines.append(f"**ID**: {conversation.id}")
    lines.append(f"**Created**: {conversation.created_at.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Updated**: {conversation.updated_at.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Messages**: {len(conversation.messages)}")
    lines.append(f"**Source**: {conversation.metadata.get('source', 'unknown')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Messages
    for i, msg in enumerate(conversation.messages, 1):
        # Message header
        role_emoji = "👤" if msg.role == "user" else "🤖" if msg.role == "assistant" else "⚙️"
        time_str = msg.timestamp.strftime("%H:%M:%S")
        lines.append(f"## Message {i} - {role_emoji} {msg.role.title()} ({time_str})")
        lines.append("")

        # Message content
        lines.append(msg.content)
        lines.append("")

        # Code blocks (if not already in content)
        if msg.code_blocks and "```" not in msg.content:
            for block in msg.code_blocks:
                lines.append(f"```{block.language}")
                lines.append(block.content)
                lines.append("```")
                lines.append("")

    return "\n".join(lines)


def detect_conversation_format(file_path: Path) -> str | None:
    """Detect conversation file format.

    Args:
    ----
        file_path: Path to conversation file

    Returns:
    -------
        Format type: "antigravity", "cursor", "claude", "github_copilot", or None

    """
    if (file_path.suffix == ".txt" or file_path.suffix == ".md") and "antigravity" in str(
        file_path
    ):
        return "antigravity"

    if file_path.suffix == ".aichat":
        return "cursor"

    if file_path.suffix == ".json":
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))

            # Claude format
            if "chat_messages" in data or "uuid" in data:
                return "claude"

            # GitHub Copilot format
            if "sessionId" in data or (
                "messages" in data and isinstance(data.get("messages"), list)
            ):
                # Check if it looks like Copilot format
                messages = data.get("messages", [])
                if messages and isinstance(messages[0], dict):
                    if "role" in messages[0] or "sender" in messages[0]:
                        return "github_copilot"

            # VSCode workspace storage entries.json
            if "entries" in data or file_path.name == "entries.json":
                return "github_copilot"

        except (json.JSONDecodeError, OSError):
            pass

    return None


def parse_conversation(file_path: Path) -> ConversationData | None:
    """Parse conversation file (auto-detect format).

    Args:
    ----
        file_path: Path to conversation file

    Returns:
    -------
        Parsed conversation or None if format not recognized

    """
    format_type = detect_conversation_format(file_path)

    if format_type == "antigravity":
        return parse_antigravity_log(file_path)
    if format_type == "cursor":
        return parse_cursor_aichat(file_path)
    if format_type == "claude":
        return parse_claude_conversation(file_path)
    if format_type == "github_copilot":
        return parse_github_copilot_chat(file_path)

    return None

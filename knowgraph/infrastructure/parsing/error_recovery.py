"""Enhanced error handling and recovery for conversation parsing.

Provides robust error handling with:
- Partial parsing (extract what we can)
- Detailed error reporting
- Multiple retry strategies
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from knowgraph.infrastructure.parsing.conversation_parser import (
    ConversationData,
    Message,
    parse_conversation,
)

logger = logging.getLogger(__name__)


@dataclass
class ParsingError:
    """Details about a parsing error."""

    file_path: str
    error_type: str
    error_message: str
    line_number: int | None = None
    partial_data: Any | None = None


@dataclass
class ParsingResult:
    """Result of parsing with error handling."""

    success: bool
    conversation: ConversationData | None = None
    errors: list[ParsingError] | None = None
    warnings: list[str] | None = None


def parse_with_error_recovery(file_path: Path) -> ParsingResult:
    """Parse conversation file with comprehensive error handling.

    Args:
    ----
        file_path: Path to conversation file

    Returns:
    -------
        Parsing result with success status, data, and errors

    """
    errors = []
    warnings = []

    try:
        # Attempt normal parsing
        conversation = parse_conversation(file_path)

        if conversation is None:
            # Try partial parsing
            partial_result = _partial_parse(file_path)
            if partial_result:
                warnings.append("Partial parsing succeeded - some data may be missing")
                return ParsingResult(
                    success=True,
                    conversation=partial_result,
                    errors=None,
                    warnings=warnings,
                )
            else:
                errors.append(
                    ParsingError(
                        file_path=str(file_path),
                        error_type="UnsupportedFormat",
                        error_message="No parser could handle this file format",
                    )
                )
                return ParsingResult(success=False, errors=errors)

        # Validate conversation data
        validation_errors = _validate_conversation(conversation)
        if validation_errors:
            warnings.extend(validation_errors)

        return ParsingResult(
            success=True,
            conversation=conversation,
            errors=None,
            warnings=warnings if warnings else None,
        )

    except Exception as e:
        logger.error(f"Error parsing {file_path}: {e}")

        # Try partial parsing as fallback
        try:
            partial_result = _partial_parse(file_path)
            if partial_result:
                errors.append(
                    ParsingError(
                        file_path=str(file_path),
                        error_type=type(e).__name__,
                        error_message=str(e),
                        partial_data=partial_result,
                    )
                )
                return ParsingResult(
                    success=True,
                    conversation=partial_result,
                    errors=errors,
                    warnings=["Partial parsing used due to errors"],
                )
        except Exception:
            pass

        # Complete failure
        errors.append(
            ParsingError(
                file_path=str(file_path),
                error_type=type(e).__name__,
                error_message=str(e),
            )
        )
        return ParsingResult(success=False, errors=errors)


def _partial_parse(file_path: Path) -> ConversationData | None:
    """Attempt partial parsing - extract what we can.

    Args:
    ----
        file_path: File to parse

    Returns:
    -------
        Partial conversation data or None

    """
    from datetime import datetime

    try:
        # Read raw content
        content = file_path.read_text(encoding="utf-8")

        # Create minimal conversation with raw content as single message
        messages = [
            Message(
                role="assistant",
                content=content[:5000],  # Limit size
                timestamp=datetime.now(),
                has_code="```" in content,
            )
        ]

        return ConversationData(
            id=file_path.stem,
            title=f"Partial: {file_path.name}",
            messages=messages,
            created_at=datetime.fromtimestamp(file_path.stat().st_ctime),
            updated_at=datetime.fromtimestamp(file_path.stat().st_mtime),
            metadata={"partial": True, "source": "error_recovery"},
        )

    except Exception:
        return None


def _validate_conversation(conversation: ConversationData) -> list[str]:
    """Validate conversation data and return warnings.

    Args:
    ----
        conversation: Conversation to validate

    Returns:
    -------
        List of validation warnings

    """
    warnings = []

    if not conversation.messages:
        warnings.append("Conversation has no messages")

    if len(conversation.messages) == 1:
        warnings.append("Conversation has only one message")

    # Check for suspiciously long messages
    for msg in conversation.messages:
        if len(msg.content) > 50000:
            warnings.append(f"Message content exceeds 50k characters (role: {msg.role})")

    return warnings


def generate_error_report(results: list[ParsingResult]) -> dict:
    """Generate comprehensive error report.

    Args:
    ----
        results: List of parsing results

    Returns:
    -------
        Error report dictionary

    """
    total = len(results)
    successful = sum(1 for r in results if r.success)
    failures = total - successful

    all_errors = []
    for result in results:
        if result.errors:
            all_errors.extend(result.errors)

    # Group errors by type
    errors_by_type = {}
    for error in all_errors:
        errors_by_type.setdefault(error.error_type, []).append(error)

    return {
        "total_files": total,
        "successful": successful,
        "failures": failures,
        "success_rate": f"{successful/total*100:.1f}%" if total > 0 else "0%",
        "errors_by_type": {
            error_type: len(errors) for error_type, errors in errors_by_type.items()
        },
        "all_errors": [
            {
                "file": e.file_path,
                "type": e.error_type,
                "message": e.error_message[:100],  # Truncate
            }
            for e in all_errors[:20]  # Limit to first 20
        ],
    }


# Example usage
if __name__ == "__main__":
    # Test error recovery
    result = parse_with_error_recovery(Path("./test_conversation.json"))

    if result.success:
        print(f"✅ Parsed: {result.conversation.title}")
        if result.warnings:
            print(f"⚠️  Warnings: {result.warnings}")
    else:
        print(f"❌ Failed: {result.errors}")

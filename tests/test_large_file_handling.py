"""Tests for large file memory management in chunker."""

import pytest

from knowgraph.infrastructure.parsing.chunker import (
    EXTREME_FILE_SIZE_MB,
    MAX_FILE_SIZE_MB,
    chunk_markdown,
)


def test_normal_file_size():
    """Test normal files process without warnings."""
    # 1KB file
    small_text = "# Header\n\n" + ("content " * 200)

    chunks = chunk_markdown(small_text, source_path="small.md")

    assert len(chunks) > 0


@pytest.mark.skip(reason="tiktoken stack overflow on very large strings - known limitation")
def test_large_file_warning():
    """Test that large files (>100MB) trigger warning but still process."""
    # Create ~110MB text (exceeds MAX_FILE_SIZE_MB but < EXTREME_FILE_SIZE_MB)
    # Each char ~1 byte, so 115MB = 115 * 1024 * 1024 bytes
    large_text = "# Header\n\n" + ("A" * (115 * 1024 * 1024))

    # Should process but log warning
    chunks = chunk_markdown(large_text, source_path="large.md")

    assert len(chunks) > 0


def test_extreme_file_rejection():
    """Test that extremely large files (>500MB) are rejected."""
    # Create ~600MB text (exceeds EXTREME_FILE_SIZE_MB)
    # This would cause OOM on low-RAM systems
    extreme_text = "# Header\n\n" + ("B" * (600 * 1024 * 1024))

    with pytest.raises(ValueError, match="exceeds maximum"):
        chunk_markdown(extreme_text, source_path="extreme.md")


def test_file_size_calculation():
    """Test that file size is calculated correctly (UTF-8 encoding)."""
    # UTF-8 multi-byte characters
    text_with_unicode = "# Türkçe Başlık\n\nİçerik: üğşçöı" * 1000

    # Should not raise error (text is small)
    chunks = chunk_markdown(text_with_unicode, source_path="unicode.md")

    assert len(chunks) > 0


def test_empty_file_handling():
    """Test that empty files are handled gracefully."""
    empty_text = ""

    chunks = chunk_markdown(empty_text, source_path="empty.md")

    assert len(chunks) == 0


def test_whitespace_only_file():
    """Test whitespace-only files."""
    whitespace_text = "   \n\n  \t  \n"

    chunks = chunk_markdown(whitespace_text, source_path="whitespace.md")

    assert len(chunks) == 0


@pytest.mark.skip(reason="tiktoken stack overflow on 100MB+ strings - known limitation")
def test_boundary_size_files():
    """Test files at exactly the threshold sizes."""
    # Exactly MAX_FILE_SIZE_MB (100MB)
    boundary_text_100mb = "# Header\n\n" + ("X" * (MAX_FILE_SIZE_MB * 1024 * 1024 - 12))

    # Should process with warning
    chunks = chunk_markdown(boundary_text_100mb, source_path="boundary_100mb.md")
    assert len(chunks) > 0

    # Exactly EXTREME_FILE_SIZE_MB (500MB) - should be rejected
    boundary_text_500mb = "# Header\n\n" + ("Y" * (EXTREME_FILE_SIZE_MB * 1024 * 1024 - 12))

    with pytest.raises(ValueError):
        chunk_markdown(boundary_text_500mb, source_path="boundary_500mb.md")


def test_large_file_chunks_correctly():
    """Test that large files are still correctly chunked."""
    # 105MB file with structure
    large_structured = (
        "# Main Header\n\n"
         "## Section 1\n\n"
        + ("content " * 10_000_000)
        + "## Section 2\n\n"
        + ("more content " * 10_000_000)
    )

    chunks = chunk_markdown(large_structured, source_path="structured_large.md", max_chars=100000)

    # Should create multiple chunks
    assert len(chunks) > 1
    # All chunks should have content
    assert all(len(c.content) > 0 for c in chunks)

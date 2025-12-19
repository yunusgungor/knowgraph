from unittest.mock import patch

import pytest

from knowgraph.infrastructure.parsing.chunker import chunk_markdown


def test_chunk_markdown_empty():
    """Test chunking empty or whitespace strings."""
    assert chunk_markdown("") == []
    assert chunk_markdown("   ") == []


def test_chunk_markdown_invalid_args():
    """Test invalid arguments raise errors."""
    with pytest.raises(ValueError):
        chunk_markdown("test", max_chars=0)
    with pytest.raises(ValueError):
        chunk_markdown("test", max_chars=-1)


def test_chunk_markdown_basic():
    """Test basic markdown chunking without splitting."""
    md = "# Header 1\n\nContent 1\n\n## Header 2\n\nContent 2"
    # Mock MIN_CHUNK_SIZE to avoid merging
    with patch("knowgraph.infrastructure.parsing.chunker.MIN_CHUNK_SIZE", 0):
        chunks = chunk_markdown(md, max_chars=1000)

    assert len(chunks) == 2
    assert chunks[0].header == "Header 1"
    assert "Content 1" in chunks[0].content
    assert chunks[1].header == "Header 2"
    assert "Content 2" in chunks[1].content


def test_chunk_markdown_large_section_split():
    """Test splitting of large sections."""
    # Create a section larger than max_chars
    large_content = "A" * 200 + "\n\n" + "B" * 200
    md = f"# Large Section\n\n{large_content}"

    # max_chars small enough to force split
    # Mock MIN_CHUNK_SIZE to avoid merging header-only chunks
    with patch("knowgraph.infrastructure.parsing.chunker.MIN_CHUNK_SIZE", 0):
        chunks = chunk_markdown(md, max_chars=150)

        print(f"\nDEBUG: Chunks count: {len(chunks)}")
        for i, c in enumerate(chunks):
            print(f"Chunk {i}: {c.header}")

        # The logic splits more granularly now (7 chunks)
        # 1. Header only
        # 2. Header + Parts of A
        # 3. Header + Parts of B
        assert len(chunks) == 7
        assert chunks[0].header == "Large Section (part 1)"
        assert "# Large Section" in chunks[0].content


def test_chunk_markdown_merge_small():
    """Test merging of small chunks."""
    # Create tiny sections
    md = "# H1\n\nA\n\n# H2\n\nB\n\n# H3\n\nC"

    # Use real chunker but mock internal merge constant if possible, or just rely on MIN_CHUNK_SIZE
    # MIN_CHUNK_SIZE is imported, let's assume it's small or we pass large inputs contextually
    # But wait, logic merges chunks < MIN_CHUNK_SIZE. If MIN_CHUNK_SIZE is e.g. 100, these tiny chunks will merge.

    chunks = chunk_markdown(md)
    # "A", "B", "C" are very small. They should be merged into one or two chunks depending on logic.
    # Logic: H1(A) -> pending. H2(B) -> merge with pending (H1+H2). H3(C) -> merge.

    # Assuming strict merging behavior:
    assert len(chunks) < 3
    combined_content = "".join([c.content for c in chunks])
    assert "H1" in combined_content
    assert "H2" in combined_content
    assert "H3" in combined_content


@patch("knowgraph.infrastructure.parsing.chunker.tiktoken", None)
def test_chunk_markdown_no_tiktoken():
    """Test fallback when tokenizer is not available."""
    md = "# Header\n\nContent"
    chunks = chunk_markdown(md)
    assert len(chunks) == 1
    # Fallback uses split() for token counting
    assert chunks[0].token_count > 0


def test_chunk_markdown_with_tiktoken():
    """Test usage of tiktoken if available."""
    # This assumes tiktoken is installed in environment, which it is per requirements
    md = "# Header\n\nContent"
    chunks = chunk_markdown(md)
    assert len(chunks) == 1
    # Real tokenizer count check (rough)
    assert chunks[0].token_count > 0

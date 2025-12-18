"""Hierarchical chunking with header-based boundaries.

Implements smart chunking that respects markdown structure and token limits.
"""

import logging
from dataclasses import dataclass
from typing import Any

try:
    import tiktoken
except ImportError:
    tiktoken = None  # type: ignore

from knowgraph.config import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_OPENAI_MODEL,
    MIN_CHUNK_SIZE,
)
from knowgraph.infrastructure.parsing.markdown_parser import MarkdownSection, parse_markdown

logger = logging.getLogger(__name__)

# Memory protection thresholds
MAX_FILE_SIZE_MB = 100  # Maximum file size before warning
EXTREME_FILE_SIZE_MB = 500  # Extreme size - reject processing


@dataclass
class Chunk:
    """A chunk of content with metadata.

    Attributes
    ----------
        content: Chunk text
        header: Section header
        header_depth: Header level (1-4)
        header_path: Breadcrumb path
        line_start: Starting line number
        line_end: Ending line number
        token_count: Approximate token count
        has_code: Whether chunk contains code
        chunk_id: Optional identifier

    """

    content: str
    header: str
    header_depth: int
    header_path: str
    line_start: int
    line_end: int
    token_count: int
    has_code: bool
    source_path: str = ""
    chunk_id: str | None = None


def chunk_markdown(
    markdown_text: str,
    source_path: str = "",
    max_chars: int = DEFAULT_CHUNK_SIZE,
    overlap_tokens: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    r"""Chunk markdown into token-aware sections.

    Splits on H1-H4 headers first, then further splits if sections exceed
    max_chars. Preserves hierarchy and adds breadcrumb context.

    Args:
    ----
        markdown_text: Raw markdown content
        source_path: Source file path
        max_chars: Maximum characters per chunk
        overlap_tokens: Token overlap for context continuity

    Returns:
    -------
        List of chunks with metadata

    Example:
    -------
        >>> md = "# Title\\n\\n" + ("A" * 5000)
        >>> chunks = chunk_markdown(md, max_chars=4096)
        >>> len(chunks) >= 2  # Split due to size
        True

    Raises:
    ------
        ValueError: If markdown_text is None or max_chars is invalid

    """
    # Handle edge cases
    if max_chars <= 0:
        raise ValueError(f"max_chars must be positive, got {max_chars}")

    if not markdown_text or markdown_text.isspace():
        # Return empty list for empty/whitespace content
        return []

    # Memory protection: Check file size
    file_size_bytes = len(markdown_text.encode("utf-8"))
    file_size_mb = file_size_bytes / (1024 * 1024)

    if file_size_mb > EXTREME_FILE_SIZE_MB:
        logger.error(
            f"File too large ({file_size_mb:.1f}MB > {EXTREME_FILE_SIZE_MB}MB limit) at "
            f"{source_path}. Skipping to prevent memory issues."
        )
        raise ValueError(
            f"File size {file_size_mb:.1f}MB exceeds maximum {EXTREME_FILE_SIZE_MB}MB. "
            "Consider splitting the file or reducing content."
        )

    if file_size_mb > MAX_FILE_SIZE_MB:
        logger.warning(
            f"Large file detected ({file_size_mb:.1f}MB) at {source_path}. "
            "Processing may be slow. Consider splitting for better performance."
        )

    # Parse into sections first
    sections = parse_markdown(markdown_text, source_path)

    if not sections:
        return []

    chunks = []
    chunks = []
    if tiktoken:
        try:
            tokenizer = tiktoken.encoding_for_model(DEFAULT_OPENAI_MODEL)
        except KeyError:
            tokenizer = tiktoken.get_encoding("o200k_base")  # Fallback for newer models
    else:
        tokenizer = None

    for section in sections:
        # Build full section text with header
        section_text = f"{'#' * section.level} {section.header}\n\n{section.content}"

        # Check if section needs splitting
        if len(section_text) <= max_chars:
            # Section fits in one chunk
            if tokenizer:
                tokens = len(tokenizer.encode(section_text))
            else:
                tokens = len(section_text.split())  # Rough fallback
            chunks.append(
                Chunk(
                    content=section_text,
                    header=section.header,
                    header_depth=section.level,
                    header_path=section.header_path,
                    line_start=section.line_start,
                    line_end=section.line_end,
                    token_count=tokens,
                    has_code=section.has_code,
                    source_path=source_path,
                )
            )
        else:
            # Split section into smaller chunks
            sub_chunks = _split_large_section(
                section, max_chars, overlap_tokens, tokenizer, source_path
            )
            chunks.extend(sub_chunks)

    # Merge tiny chunks
    chunks = _merge_small_chunks(chunks, MIN_CHUNK_SIZE)

    return chunks


def _split_large_section(
    section: MarkdownSection,
    max_chars: int,
    overlap_tokens: int,  # noqa: ARG001
    tokenizer: Any,
    source_path: str = "",
) -> list[Chunk]:
    """Split a large section into smaller chunks.

    Args:
    ----
        section: Section to split
        max_chars: Maximum characters per chunk
        overlap_tokens: Overlap size
        tokenizer: Tokenizer for token counting

    Returns:
    -------
        List of sub-chunks

    """
    # Split on paragraph boundaries (double newline)
    paragraphs = section.content.split("\n\n")
    chunks = []

    current_chunk_parts = []
    current_size = 0
    chunk_index = 0

    # Add header to first chunk
    header_text = f"{'#' * section.level} {section.header}\n\n"
    current_chunk_parts.append(header_text)
    current_size = len(header_text)

    for para in paragraphs:
        para_size = len(para) + 2  # +2 for \n\n

        # Handle oversized paragraphs (e.g. minified code)
        if para_size > max_chars:
            # 1. Flush current pending parts
            if current_chunk_parts:
                chunk_content = "".join(current_chunk_parts).strip()
                if tokenizer:
                    tokens = len(tokenizer.encode(chunk_content))
                else:
                    # Fallback: estimate tokens (approx 3.5 chars per token for code)
                    tokens = int(len(chunk_content) / 3.5)

                chunks.append(
                    Chunk(
                        content=chunk_content,
                        header=f"{section.header} (part {chunk_index + 1})",
                        header_depth=section.level,
                        header_path=section.header_path,
                        line_start=section.line_start,
                        line_end=section.line_end,
                        token_count=tokens,
                        has_code=section.has_code,
                        source_path=source_path,
                        chunk_id=f"{section.header}_{chunk_index}",
                    )
                )
                chunk_index += 1
                current_chunk_parts = []
                current_size = 0

            # 2. Hard split the large paragraph
            # We must split this specific paragraph into multiple chunks
            start = 0
            raw_para_len = len(para)
            while start < raw_para_len:
                # Calculate slice end, ensuring we don't exceed max_chars
                # Leave room for header context if needed, though here we just slice raw
                slice_len = max_chars - len(header_text)
                if slice_len <= 0:
                    slice_len = max_chars  # Fallback if header is huge (unlikely)

                piece = para[start : start + slice_len]

                # Create a chunk for this piece immediately
                # Always prefix with header to maintain context
                full_piece_content = (header_text + piece).strip()

                if tokenizer:
                    tokens = len(tokenizer.encode(full_piece_content))
                else:
                    # Fallback: estimate tokens (approx 3.5 chars per token for code)
                    tokens = int(len(full_piece_content) / 3.5)

                chunks.append(
                    Chunk(
                        content=full_piece_content,
                        header=f"{section.header} (part {chunk_index + 1})",
                        header_depth=section.level,
                        header_path=section.header_path,
                        line_start=section.line_start,
                        line_end=section.line_end,
                        token_count=tokens,
                        has_code=section.has_code,
                        source_path=source_path,
                        chunk_id=f"{section.header}_{chunk_index}",
                    )
                )
                chunk_index += 1
                start += slice_len

            # Reset current context for next paragraphs
            current_chunk_parts = [header_text]
            current_size = len(header_text)
            continue

        if current_size + para_size > max_chars and current_chunk_parts:
            # Save current chunk
            chunk_content = "".join(current_chunk_parts).strip()
            if tokenizer:
                tokens = len(tokenizer.encode(chunk_content))
            else:
                # Fallback: estimate tokens (approx 3.5 chars per token for code)
                tokens = int(len(chunk_content) / 3.5)

            chunks.append(
                Chunk(
                    content=chunk_content,
                    header=f"{section.header} (part {chunk_index + 1})",
                    header_depth=section.level,
                    header_path=section.header_path,
                    line_start=section.line_start,
                    line_end=section.line_end,
                    token_count=tokens,
                    has_code=section.has_code,
                    source_path=source_path,
                    chunk_id=f"{section.header}_{chunk_index}",
                )
            )

            # Start new chunk with header context
            current_chunk_parts = [header_text]
            current_size = len(header_text)
            chunk_index += 1

        current_chunk_parts.append(para + "\n\n")
        current_size += para_size

    # Save remaining chunk
    if current_chunk_parts:
        chunk_content = "".join(current_chunk_parts).strip()
        if tokenizer:
            tokens = len(tokenizer.encode(chunk_content))
        else:
            # Fallback: estimate tokens (approx 3.5 chars per token for code)
            tokens = int(len(chunk_content) / 3.5)

        chunks.append(
            Chunk(
                content=chunk_content,
                header=(
                    f"{section.header} (part {chunk_index + 1})"
                    if chunk_index > 0
                    else section.header
                ),
                header_depth=section.level,
                header_path=section.header_path,
                line_start=section.line_start,
                line_end=section.line_end,
                token_count=tokens,
                has_code=section.has_code,
                source_path=source_path,
                chunk_id=f"{section.header}_{chunk_index}" if chunk_index > 0 else None,
            )
        )

    return chunks


def _merge_small_chunks(chunks: list[Chunk], min_size: int) -> list[Chunk]:
    """Merge chunks smaller than min_size into adjacent chunks.

    Args:
    ----
        chunks: List of chunks
        min_size: Minimum chunk size in characters

    Returns:
    -------
        List of chunks with small ones merged

    """
    if not chunks:
        return []

    merged = []
    pending = None

    for chunk in chunks:
        if len(chunk.content) < min_size:
            # Too small, merge with next
            pending = _combine_chunks(pending, chunk) if pending else chunk
        else:
            if pending:
                # Merge pending with current
                merged.append(_combine_chunks(pending, chunk))
                pending = None
            else:
                merged.append(chunk)

    # Add any remaining pending
    if pending:
        if merged:
            # Merge with last chunk
            merged[-1] = _combine_chunks(merged[-1], pending)
        else:
            merged.append(pending)

    return merged


def _combine_chunks(chunk1: Chunk, chunk2: Chunk) -> Chunk:
    """Combine two chunks into one.

    Args:
    ----
        chunk1: First chunk
        chunk2: Second chunk

    Returns:
    -------
        Combined chunk

    """
    combined_content = f"{chunk1.content}\n\n{chunk2.content}"

    if tiktoken:
        try:
            tokenizer = tiktoken.encoding_for_model(DEFAULT_OPENAI_MODEL)
        except KeyError:
            tokenizer = tiktoken.get_encoding("o200k_base")
        combined_tokens = len(tokenizer.encode(combined_content))
    else:
        combined_tokens = len(combined_content.split())

    return Chunk(
        content=combined_content,
        header=chunk1.header,  # Keep first header
        header_depth=chunk1.header_depth,
        header_path=chunk1.header_path,
        line_start=chunk1.line_start,
        line_end=chunk2.line_end,
        token_count=combined_tokens,
        has_code=chunk1.has_code or chunk2.has_code,
        source_path=chunk1.source_path,
        chunk_id=chunk1.chunk_id,
    )

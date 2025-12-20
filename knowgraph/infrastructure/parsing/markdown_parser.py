"""Markdown parser for Gittodoc format.

Parses markdown files with hierarchical headers and code blocks, preserving
structure for graph construction.
"""

import re
from dataclasses import dataclass
from typing import cast

from knowgraph.shared.memory_profiler import memory_guard
from knowgraph.shared.tracing import trace_operation


@dataclass
class MarkdownSection:
    """A section of markdown content.

    Attributes
    ----------
        header: Header text (without #)
        level: Header level (1-4 for H1-H4)
        content: Section content (excluding header)
        line_start: Starting line number
        line_end: Ending line number
        header_path: Breadcrumb path (e.g., "H1 > H2 > H3")
        has_code: Whether section contains code blocks

    """

    header: str
    level: int
    content: str
    line_start: int
    line_end: int
    header_path: str
    has_code: bool = False


def parse_markdown(
    markdown_text: str, source_path: str = ""  # noqa: ARG001
) -> list[MarkdownSection]:
    r"""Parse markdown into hierarchical sections.

    Splits on H1-H4 headers, preserving hierarchy and building breadcrumb paths.
    Detects code blocks for node type classification.

    Args:
    ----
        markdown_text: Raw markdown content
        source_path: Source file path for error messages

    Returns:
    -------
        List of markdown sections with hierarchy

    Example:
    -------
        >>> md = "# Title\\n\\nIntro\\n\\n## Section\\n\\nContent"
        >>> sections = parse_markdown(md)
        >>> len(sections)
        2
        >>> sections[0].header
        'Title'
        >>> sections[1].header_path
        'Title > Section'

    Raises:
    ------
        ValueError: If markdown_text is None or contains invalid UTF-8

    """
    with memory_guard(
        operation_name=f"parse_md[{source_path if source_path else 'text'}]",
        warning_threshold_mb=50,
        critical_threshold_mb=150,
    ):
        with trace_operation(
            "markdown_parser.parse_markdown",
            source_path=source_path,
            text_length=len(markdown_text) if markdown_text else 0,
        ):
            # Handle edge cases
            if not markdown_text or markdown_text.isspace():
                # Return empty list for empty/whitespace-only files
                return []

            lines = markdown_text.split("\n")
            sections = []
            header_stack: list[tuple[int, str]] = []  # Stack of (level, header)

            # Regex for headers (H1-H4)
            header_pattern = re.compile(r"^(#{1,4})\s+(.+?)$")

            current_section: dict[str, object] | None = None

            for line_num, line in enumerate(lines, 1):
                match = header_pattern.match(line)

                if match:
                    # Save previous section
                    if current_section:
                        sections.append(_finalize_section(current_section, line_num - 1))

                    # Parse header
                    level = len(match.group(1))
                    header_text = match.group(2).strip()

                    # Update header stack (pop until we find parent level)
                    while header_stack and header_stack[-1][0] >= level:
                        header_stack.pop()
                    header_stack.append((level, header_text))

                    # Build header path
                    header_path = " > ".join(h[1] for h in header_stack)

                    # Start new section
                    current_section = {
                        "header": header_text,
                        "level": level,
                        "content_lines": [],
                        "line_start": line_num,
                        "header_path": header_path,
                        "has_code": False,
                    }
                else:
                    # Add line to current section
                    if current_section:
                        content_lines = current_section["content_lines"]
                        if isinstance(content_lines, list):
                            content_lines.append(line)
                        # Check for code blocks
                        if line.strip().startswith("```"):
                            current_section["has_code"] = True

            # Save last section
            if current_section:
                sections.append(_finalize_section(current_section, len(lines)))

            return sections


def _finalize_section(section_data: dict[str, object], line_end: int) -> MarkdownSection:
    """Convert section data dictionary to MarkdownSection object.

    Args:
    ----
        section_data: Dictionary with section fields
        line_end: Ending line number

    Returns:
    -------
        MarkdownSection object

    """
    content = "\n".join(section_data["content_lines"]).strip()  # type: ignore[arg-type]

    return MarkdownSection(
        header=cast(str, section_data["header"]),
        level=cast(int, section_data["level"]),
        content=content,
        line_start=cast(int, section_data["line_start"]),
        line_end=line_end,
        header_path=cast(str, section_data["header_path"]),
        has_code=cast(bool, section_data["has_code"]),
    )


def extract_code_blocks(markdown_text: str) -> list[tuple[str, str]]:
    r"""Extract code blocks with their language identifiers.

    Args:
    ----
        markdown_text: Markdown content

    Returns:
    -------
        List of (language, code) tuples

    Example:
    -------
        >>> md = "```python\\nprint('hello')\\n```"
        >>> blocks = extract_code_blocks(md)
        >>> blocks[0]
        ('python', "print('hello')")

    """
    # Regex for fenced code blocks
    pattern = re.compile(r"```(\w+)?\n(.*?)\n```", re.DOTALL)
    matches = pattern.findall(markdown_text)

    return [(lang or "text", code.strip()) for lang, code in matches]


def classify_section_type(section: MarkdownSection, file_path: str) -> str:
    """Classify section as code, text, readme, or config.

    Args:
    ----
        section: Markdown section
        file_path: Source file path

    Returns:
    -------
        Node type: "code", "text", "readme", or "config"

    """
    file_lower = file_path.lower()

    # Check file path patterns
    if "readme" in file_lower:
        return "readme"
    if any(
        pattern in file_lower for pattern in ["config", ".yaml", ".yml", ".json", ".toml", ".ini"]
    ):
        return "config"

    # Check content
    if section.has_code:
        return "code"

    return "text"

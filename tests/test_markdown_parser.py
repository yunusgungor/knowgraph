from knowgraph.infrastructure.parsing.markdown_parser import (
    MarkdownSection,
    classify_section_type,
    extract_code_blocks,
    parse_markdown,
)


def test_parse_markdown_hierarchical():
    """Test parsing of hierarchical markdown."""
    md = "# Header 1\n\nContent 1\n\n## Header 2\n\nContent 2"
    sections = parse_markdown(md)

    assert len(sections) == 2
    assert sections[0].header == "Header 1"
    assert sections[0].level == 1
    assert "Content 1" in sections[0].content

    assert sections[1].header == "Header 2"
    assert sections[1].level == 2
    assert "Content 2" in sections[1].content
    assert sections[1].header_path == "Header 1 > Header 2"


def test_parse_markdown_flat():
    """Test parsing of flat structure."""
    md = "# Header A\n\nText A\n# Header B\n\nText B"
    sections = parse_markdown(md)

    assert len(sections) == 2
    assert sections[0].level == 1
    assert sections[1].level == 1
    assert sections[0].header == "Header A"
    assert sections[1].header == "Header B"


def test_extract_code_blocks():
    """Test code block extraction."""
    md = "```python\nprint('hello')\n```\n\nText\n\n```json\n{}\n```"
    blocks = extract_code_blocks(md)

    assert len(blocks) == 2
    assert blocks[0] == ("python", "print('hello')")
    assert blocks[1] == ("json", "{}")


def test_classify_section_type():
    """Test section classification."""
    s1 = MarkdownSection("H1", 1, "text", 1, 2, "H1", False)
    assert classify_section_type(s1, "doc.md") == "text"

    s2 = MarkdownSection("H1", 1, "code", 1, 2, "H1", True)
    assert classify_section_type(s2, "doc.md") == "code"

    s3 = MarkdownSection("H1", 1, "text", 1, 2, "H1", False)
    assert classify_section_type(s3, "README.md") == "readme"

    s4 = MarkdownSection("H1", 1, "text", 1, 2, "H1", False)
    assert classify_section_type(s4, "config.yaml") == "config"

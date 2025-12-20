"""Conversation-to-code reference linking.

Links conversation snippets and bookmarks to code files they reference,
enabling "show related conversations" in query results.
"""

import re
from pathlib import Path

from knowgraph.domain.models.edge import Edge
from knowgraph.domain.models.node import Node


def extract_code_references(conversation_content: str) -> list[str]:
    """Extract code references from conversation content.

    Looks for:
    - Function names (camelCase, snake_case)
    - File paths (relative, absolute)
    - Class names
    - Code symbols in backticks

    Args:
    ----
        conversation_content: Conversation text

    Returns:
    -------
        List of code references

    """
    references = []

    # 1. Extract backtick-wrapped code symbols
    # `getUserById`, `auth.py`, `UserClass`
    backtick_pattern = r"`([a-zA-Z_][a-zA-Z0-9_\.\/]*)`"
    backtick_matches = re.findall(backtick_pattern, conversation_content)
    references.extend(backtick_matches)

    # 2. Extract file paths (with optional line numbers)
    # src/auth.py, ./utils/helper.js, auth.py:45, user.py:123
    file_pattern = r"(?:^|[\s(])((?:\.?\.?/)?[a-zA-Z0-9_\-\/]+\.[a-zA-Z]{1,4})(?::\d+)?(?:[\s),]|$)"
    file_matches = re.findall(file_pattern, conversation_content)
    references.extend(file_matches)

    # 3. Extract common function/class patterns
    # "the getUserById function", "UserClass implementation"
    func_pattern = r"\b([a-z][a-zA-Z0-9_]{2,})\s+(?:function|method|class|implementation)\b"
    func_matches = re.findall(func_pattern, conversation_content, re.IGNORECASE)
    references.extend(func_matches)

    # Deduplicate and clean
    unique_refs = []
    seen = set()
    for ref in references:
        ref_clean = ref.strip()
        if ref_clean and ref_clean not in seen:
            seen.add(ref_clean)
            unique_refs.append(ref_clean)

    return unique_refs


def match_references_to_nodes(
    references: list[str],
    all_nodes: list[Node],
) -> list[tuple[str, Node]]:
    """Match extracted references to actual nodes in graph.

    Args:
    ----
        references: List of code references from conversation
        all_nodes: All nodes in graph

    Returns:
    -------
        List of (reference, matched_node) tuples

    """
    matches = []

    for ref in references:
        ref_lower = ref.lower()

        for node in all_nodes:
            # Match by exact path
            if node.path and ref_lower in node.path.lower():
                matches.append((ref, node))
                continue

            # Match by filename
            if node.path:
                filename = Path(node.path).name.lower()
                if ref_lower == filename or ref_lower in filename:
                    matches.append((ref, node))
                    continue

            # Match by content (function/class name in code)
            if node.content and ref in node.content:
                # Verify it's likely a symbol (not just substring)
                # Use word boundaries
                pattern = r"\b" + re.escape(ref) + r"\b"
                if re.search(pattern, node.content):
                    matches.append((ref, node))
                    continue

    return matches


def create_conversation_reference_edges(
    conversation_node: Node,
    code_nodes: list[Node],
    reference_type: str = "conversation_references_code",
) -> list[Edge]:
    """Create reference edges from conversation to code.

    Args:
    ----
        conversation_node: Conversation or bookmark node
        code_nodes: Code nodes referenced in conversation
        reference_type: Edge type (default: conversation_references_code)

    Returns:
    -------
        List of edges

    """
    edges = []

    # Extract references from conversation
    references = extract_code_references(conversation_node.content)

    if not references:
        return edges

    # Match references to code nodes
    matches = match_references_to_nodes(references, code_nodes)

    # Create edges for each match
    for ref_text, code_node in matches:
        edge = Edge(
            source=conversation_node.id,
            target=code_node.id,
            type=reference_type,
            score=0.9,  # High confidence for explicit references
            created_at=conversation_node.created_at,
            metadata={
                "reference_text": ref_text,
                "extraction_method": "conversation_linker",
                "node_type": conversation_node.type,
            },
        )
        edges.append(edge)

    return edges


def link_conversation_to_code(
    conversation_node: Node,
    all_code_nodes: list[Node],
) -> tuple[list[Edge], dict]:
    """Main entry point for conversation-code linking.

    Args:
    ----
        conversation_node: Conversation or bookmark node to link
        all_code_nodes: All code nodes in graph

    Returns:
    -------
        Tuple of (edges, metadata_dict)

    """
    # Create edges
    edges = create_conversation_reference_edges(conversation_node, all_code_nodes)

    # Build metadata for reporting
    metadata = {
        "conversation_id": conversation_node.id,
        "references_found": len(extract_code_references(conversation_node.content)),
        "edges_created": len(edges),
        "linked_code_files": len({edge.target for edge in edges}),
    }

    return edges, metadata


# Example usage
if __name__ == "__main__":
    # Test reference extraction
    sample_conversation = """
    I implemented the `getUserById` function in auth.py.
    It uses the UserClass from src/models/user.py to fetch data.
    The authentication function handles JWT tokens.
    """

    refs = extract_code_references(sample_conversation)
    print(f"Extracted references: {refs}")
    # Expected: ['getUserById', 'auth.py', 'UserClass', 'src/models/user.py', 'authentication']

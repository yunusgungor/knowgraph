"""Type definitions and protocols for KnowGraph system."""

from typing import Literal, TypeAlias

# Node types
NodeType: TypeAlias = Literal[
    "code", "text", "config", "documentation", "conversation", "tagged_snippet",
    "readme",     # graph_builder produces this type; was missing from the literal
    "entity_node",  # cpg_converter produces this type; was missing from the literal
]

# Edge types
EdgeType: TypeAlias = Literal[
    "semantic",       # Existing: AI entity overlap (shared concepts)
    "reference",      # Existing: Symbol definition-use relationships
    "hierarchy",      # Existing: Parent-child relationships
    "call",           # NEW (Joern): Function call edges (CALL)
    "data_flow",      # NEW (Joern): Variable reaching definitions (REACHING_DEF)
    "control_flow",   # NEW (Joern): Execution path (CFG)
    "ast",            # NEW (Joern): Syntax hierarchy (AST)
    "conversation_references_code",  # Conversation -> code file it references (conversation_linker — existed at runtime, was missing from this literal)
    "supersedes",     # Temporal (Graph Engineering): later claim invalidates an earlier one (same entity/attribute)
    "contradicts",    # Temporal (Graph Engineering): same entity/attribute, different value, no single truth
    "grounded",       # Graph Engineering: SC-quote + P3 verified relation between resolved nodes
]


# LLM providers
LLMProvider: TypeAlias = Literal["openai", "ollama"]

# Query intents
QueryIntent: TypeAlias = Literal["auto", "location", "explanation", "implementation"]

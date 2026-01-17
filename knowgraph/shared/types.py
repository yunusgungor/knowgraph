"""Type definitions and protocols for KnowGraph system."""

from typing import Literal, TypeAlias

# Node types
NodeType: TypeAlias = Literal[
    "code", "text", "config", "documentation", "conversation", "tagged_snippet"
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
]


# LLM providers
LLMProvider: TypeAlias = Literal["openai", "ollama"]

# Query intents
QueryIntent: TypeAlias = Literal["auto", "location", "explanation", "implementation"]

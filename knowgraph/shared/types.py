"""Type definitions and protocols for KnowGraph system."""

from typing import Literal, TypeAlias

# Node types
NodeType: TypeAlias = Literal[
    "code", "text", "config", "documentation", "conversation", "tagged_snippet"
]

# Edge types
EdgeType: TypeAlias = Literal["semantic", "reference"]


# LLM providers
LLMProvider: TypeAlias = Literal["openai", "ollama"]

# Query intents
QueryIntent: TypeAlias = Literal["auto", "location", "explanation", "implementation"]

"""Type definitions and protocols for KnowGraph system."""

from typing import Literal, Protocol, TypeAlias

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


class LLMProtocol(Protocol):
    """Protocol for LLM provider implementations."""

    def generate(self: "LLMProtocol", prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate text from prompt.

        Args:
        ----
            prompt: Input prompt
            max_tokens: Maximum response length
            temperature: Sampling temperature

        Returns:
        -------
            Generated text

        """
        ...

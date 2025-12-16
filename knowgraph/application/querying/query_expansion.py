"""Query expansion using LLM to bridge semantic gap in static retrieval.

Generates synonymous technical terms and domain-specific keywords to improve
recall when using sparse/lexical search.
"""

from typing import Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

from knowgraph.config import (
    DEFAULT_LLM_PROVIDER,
    DEFAULT_OPENAI_MODEL,
    LLM_TEMPERATURE,
    MAX_EXPANSION_TERMS,
)


class QueryExpander:
    """Expands natural language queries into technical keywords using LLM."""

    def __init__(
        self,
        provider: str = DEFAULT_LLM_PROVIDER,
        model: str = DEFAULT_OPENAI_MODEL,
        intelligence_provider: Any = None,
    ):
        """Initialize query expander.

        Args:
            provider: LLM provider ("openai" or "ollama")
            model: Model identifier
            intelligence_provider: Optional IntelligenceProvider instance for generic support

        """
        self.provider = provider
        self.model = model
        self.intelligence_provider = intelligence_provider

        # Initialize client if OpenAI (mock/placeholder for now if dependencies missing)
        self.client: Any = None
        if provider == "openai" and OpenAI and not intelligence_provider:
            # Assumes OPENAI_API_KEY is in env
            self.client = OpenAI()

    async def expand_query_async(self, query: str) -> list[str]:
        """Generate expansion terms for a query (async version).

        Args:
            query: Original user query

        Returns:
            List of expansion terms (e.g. synonyms, related concepts)

        """
        if not query.strip():
            return []

        try:
            if self.intelligence_provider:
                return await self._expand_with_provider(query)
            elif self.provider == "openai" and self.client:
                return self._expand_openai(query)
            elif self.provider == "mock":
                # For testing without API keys
                return self._expand_mock(query)
            # Add Ollama support here if needed

            return []

        except Exception as e:
            # If expansion fails, fail gracefully and return empty list
            # so the system falls back to original query
            print(f"Query expansion failed: {e}")
            return []

    def expand_query(self, query: str) -> list[str]:
        """Generate expansion terms for a query (sync version for backward compatibility).

        Args:
            query: Original user query

        Returns:
            List of expansion terms (e.g. synonyms, related concepts)

        """
        if not query.strip():
            return []

        try:
            # Sync version only supports OpenAI client and mock
            if self.provider == "openai" and self.client:
                return self._expand_openai(query)
            elif self.provider == "mock":
                return self._expand_mock(query)

            return []

        except Exception as e:
            print(f"Query expansion failed: {e}")
            return []

    async def _expand_with_provider(self, query: str) -> list[str]:
        """Use IntelligenceProvider to expand query."""
        prompt = (
            f"You are a senior software engineer. The user is querying a codebase. "
            f"Generate {MAX_EXPANSION_TERMS} specific technical keywords, class names, "
            f"file patterns, or synonyms that are semantically relevant to this query. "
            f"Return ONLY a comma-separated list of terms. Do not add numbering or explanations.\n\n"
            f"Query: {query}\n"
            f"Terms:"
        )

        response = await self.intelligence_provider.generate_text(prompt)
        content = response.strip()
        terms = [t.strip() for t in content.split(",")]
        return terms[:MAX_EXPANSION_TERMS]

    def _expand_openai(self, query: str) -> list[str]:
        """Use OpenAI to expand query."""
        prompt = (
            f"You are a senior software engineer. The user is querying a codebase. "
            f"Generate {MAX_EXPANSION_TERMS} specific technical keywords, class names, "
            f"file patterns, or synonyms that are semantically relevant to this query. "
            f"Return ONLY a comma-separated list of terms. Do not add numbering or explanations.\n\n"
            f"Query: {query}\n"
            f"Terms:"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=LLM_TEMPERATURE,
            max_tokens=100,
        )

        content = response.choices[0].message.content.strip()
        terms = [t.strip() for t in content.split(",")]
        return terms[:MAX_EXPANSION_TERMS]

    def _expand_mock(self, query: str) -> list[str]:
        """Mock expansion for testing."""
        # Simple rule-based mock for verification script
        qt = query.lower()
        if "login" in qt or "signin" in qt:
            return ["authentication", "auth", "credentials", "jwt", "session", "login"]
        if "payment" in qt:
            return ["stripe", "credit_card", "transaction", "checkout"]
        return []

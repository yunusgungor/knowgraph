"""Sparse embedding generator for lightweight retrieval.

Implements tokenization and term frequency calculation for BM25/TF-IDF
based retrieval, avoiding heavy neural models.
"""

import re
from collections import Counter
from functools import lru_cache

from knowgraph.shared.exceptions import EmbeddingError


class SparseEmbedder:
    """Sparse embedding generator (Tokenization + Term Frequency).

    Does not produce dense vectors. Instead, produces sparse representations
    (Bag of Words / Term Frequency dictionaries) for Inverted Indexing.
    """

    def __init__(self) -> None:
        """Initialize sparse embedder."""
        # Simple regex for tokenization: alphanumeric sequences
        self.token_pattern = re.compile(r"(?u)\b\w\w+\b")
        # Standard English stop words (minimal set)
        self.stop_words = {
            "i",
            "me",
            "my",
            "myself",
            "we",
            "our",
            "ours",
            "ourselves",
            "you",
            "your",
            "yours",
            "yourself",
            "yourselves",
            "he",
            "him",
            "his",
            "himself",
            "she",
            "her",
            "hers",
            "herself",
            "it",
            "its",
            "itself",
            "they",
            "them",
            "their",
            "theirs",
            "themselves",
            "what",
            "which",
            "who",
            "whom",
            "this",
            "that",
            "these",
            "those",
            "am",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "having",
            "do",
            "does",
            "did",
            "doing",
            "a",
            "an",
            "the",
            "and",
            "but",
            "if",
            "or",
            "because",
            "as",
            "until",
            "while",
            "of",
            "at",
            "by",
            "for",
            "with",
            "about",
            "against",
            "between",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "to",
            "from",
            "up",
            "down",
            "in",
            "out",
            "on",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "any",
            "both",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "s",
            "t",
            "can",
            "will",
            "just",
            "don",
            "should",
            "now",
        }

    def embed_text(self, text: str) -> dict[str, int]:
        """Generate sparse embedding (Term Frequency dict) for text.

        Args:
            text: Input text

        Returns:
            Dictionary of {term: frequency}

        """
        try:
            # Use cached version
            return self._embed_text_cached(text, frozenset(self.stop_words))
        except Exception as error:
            raise EmbeddingError(
                "Failed to generate sparse text embedding",
                {"error": str(error), "text_length": len(text)},
            ) from error

    @staticmethod
    # Note: Cache size configured via settings, but lru_cache decorator needs compile-time constant
    # Using default of 1000, override via KNOWGRAPH_PERF_CACHE_SIZE in production
    @lru_cache(maxsize=1000)
    def _embed_text_cached(text: str, stop_words: frozenset[str]) -> dict[str, int]:
        """Cached text embedding computation."""
        token_pattern = re.compile(r"(?u)\b\w\w+\b")
        text = text.lower()
        tokens = token_pattern.findall(text)
        filtered = [t for t in tokens if t not in stop_words]
        return dict(Counter(filtered))

    def embed_code(self, code: str) -> dict[str, int]:
        """Generate sparse embedding for code (CODE-AWARE TOKENIZATION).

        Specialized for code:
        - Splits camelCase: getUserById → ['get', 'user', 'by', 'id', 'getUserById']
        - Splits snake_case: user_profile → ['user', 'profile', 'user_profile']
        - Preserves keywords and operators
        """
        try:
            # Use cached version
            return self._embed_code_cached(code, frozenset(self.stop_words))
        except Exception as error:
            raise EmbeddingError(
                "Failed to generate sparse code embedding",
                {"error": str(error), "code_length": len(code)},
            ) from error

    @staticmethod
    # Cache size: 1000 (configurable via KNOWGRAPH_PERF_CACHE_SIZE)
    @lru_cache(maxsize=1000)
    def _embed_code_cached(code: str, stop_words: frozenset[str]) -> dict[str, int]:
        """Cached code embedding computation."""
        token_pattern = re.compile(r"(?u)\b\w\w+\b")
        code_keywords = {
            "def",
            "class",
            "import",
            "from",
            "return",
            "if",
            "else",
            "elif",
            "for",
            "while",
            "try",
            "except",
            "finally",
            "with",
            "as",
            "async",
            "await",
            "yield",
            "lambda",
            "pass",
            "break",
            "continue",
            "raise",
            "assert",
            "global",
            "nonlocal",
            "del",
            "in",
            "is",
            "not",
            "and",
            "or",
            "true",
            "false",
            "none",
            "self",
            "super",
            "init",
            "main",
            "function",
            "var",
            "let",
            "const",
            "new",
            "this",
            "null",
            "undefined",
            "public",
            "private",
            "protected",
            "static",
            "void",
            "int",
            "string",
            "bool",
            "float",
            "double",
            "char",
            "interface",
            "extends",
            "implements",
        }

        raw_tokens_original = token_pattern.findall(code)
        expanded_tokens = []

        for token_original in raw_tokens_original:
            token_lower = token_original.lower()

            # Skip stop words but NOT code keywords
            if token_lower in stop_words and token_lower not in code_keywords:
                continue

            # Always include the lowercased token
            expanded_tokens.append(token_lower)

            # Split camelCase (but skip all-uppercase tokens like TTL, API, HTTP)
            # This prevents acronyms from being split into individual letters
            camel_parts = re.findall(r"[a-z]+|[A-Z][a-z]*", token_original)
            if len(camel_parts) > 1 and not token_original.isupper():
                expanded_tokens.extend([p.lower() for p in camel_parts])

            # Split snake_case
            if "_" in token_lower:
                snake_parts = token_lower.split("_")
                expanded_tokens.extend([p for p in snake_parts if p and p not in stop_words])

        # Deduplicate
        seen = set()
        unique_tokens = []
        for t in expanded_tokens:
            if t and t not in seen:
                seen.add(t)
                unique_tokens.append(t)

        return dict(Counter(unique_tokens))

    def _tokenize(self, text: str) -> list[str]:
        """Normalize and tokenize text."""
        text = text.lower()
        tokens = self.token_pattern.findall(text)
        return [t for t in tokens if t not in self.stop_words]

    def _tokenize_code(self, code: str) -> list[str]:
        """Code-aware tokenization with camelCase/snake_case splitting.

        Returns both split tokens AND original identifiers for maximum recall.
        Example: 'getUserById' → ['get', 'user', 'by', 'id', 'getuserbyid']
        """
        # First, extract all identifiers BEFORE lowercasing (for camelCase detection)
        raw_tokens_original = self.token_pattern.findall(code)
        # First, extract all identifiers BEFORE lowercasing (for camelCase detection)
        raw_tokens_original = self.token_pattern.findall(code)
        # First, extract all identifiers BEFORE lowercasing (for camelCase detection)
        expanded_tokens = []

        for token_original in raw_tokens_original:
            token_lower = token_original.lower()

            # Skip stop words but NOT code keywords
            if token_lower in self.stop_words and not self._is_code_keyword(token_lower):
                continue

            # Always include the lowercased token
            expanded_tokens.append(token_lower)

            # Split camelCase: getUserById → ['get', 'user', 'by', 'id']
            # Use ORIGINAL case for detection, then lowercase the parts
            camel_parts = re.findall(r"[a-z]+|[A-Z][a-z]*", token_original)
            if len(camel_parts) > 1:
                expanded_tokens.extend([p.lower() for p in camel_parts])

            # Split snake_case: user_profile → ['user', 'profile']
            if "_" in token_lower:
                snake_parts = token_lower.split("_")
                expanded_tokens.extend([p for p in snake_parts if p and p not in self.stop_words])
            if "_" in token_lower:
                snake_parts = token_lower.split("_")
                expanded_tokens.extend([p for p in snake_parts if p and p not in self.stop_words])

        # Deduplicate while preserving some order
        seen = set()
        unique_tokens = []
        for t in expanded_tokens:
            if t and t not in seen:
                seen.add(t)
                unique_tokens.append(t)

        return unique_tokens

    def _is_code_keyword(self, token: str) -> bool:
        """Check if token is a programming keyword (should NOT be filtered)."""
        code_keywords = {
            "def",
            "class",
            "import",
            "from",
            "return",
            "if",
            "else",
            "elif",
            "for",
            "while",
            "try",
            "except",
            "finally",
            "with",
            "as",
            "async",
            "await",
            "yield",
            "lambda",
            "pass",
            "break",
            "continue",
            "raise",
            "assert",
            "global",
            "nonlocal",
            "del",
            "in",
            "is",
            "not",
            "and",
            "or",
            "true",
            "false",
            "none",
            "self",
            "super",
            "init",
            "main",
            "function",
            "var",
            "let",
            "const",
            "new",
            "this",
            "null",
            "undefined",
            "public",
            "private",
            "protected",
            "static",
            "void",
            "int",
            "string",
            "bool",
            "float",
            "double",
            "char",
            "interface",
            "extends",
            "implements",
        }
        return token in code_keywords

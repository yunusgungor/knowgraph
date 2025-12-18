"""Sparse embedding generator for lightweight retrieval.

Implements tokenization and term frequency calculation for BM25/TF-IDF
based retrieval, avoiding heavy neural models.
"""

import re
from collections import Counter

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
            tokens = self._tokenize(text)
            return dict(Counter(tokens))
        except Exception as error:
            raise EmbeddingError(
                "Failed to generate sparse text embedding",
                {"error": str(error), "text_length": len(text)},
            ) from error

    def embed_code(self, code: str) -> dict[str, int]:
        """Generate sparse embedding for code (CODE-AWARE TOKENIZATION).

        Specialized for code:
        - Splits camelCase: getUserById → ['get', 'user', 'by', 'id', 'getUserById']
        - Splits snake_case: user_profile → ['user', 'profile', 'user_profile']
        - Preserves keywords and operators
        """
        try:
            tokens = self._tokenize_code(code)
            return dict(Counter(tokens))
        except Exception as error:
            raise EmbeddingError(
                "Failed to generate sparse code embedding",
                {"error": str(error), "code_length": len(code)},
            ) from error

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
        code_lower = code.lower()

        # First, extract all identifiers (alphanumeric sequences)
        raw_tokens = self.token_pattern.findall(code_lower)

        expanded_tokens = []

        for token in raw_tokens:
            # Skip stop words but NOT code keywords
            if token in self.stop_words and not self._is_code_keyword(token):
                continue

            # Always include the original token
            expanded_tokens.append(token)

            # Split camelCase: getUserById → ['get', 'user', 'by', 'id']
            camel_parts = re.findall(r"[a-z]+|[A-Z][a-z]*", token)
            if len(camel_parts) > 1:
                expanded_tokens.extend(camel_parts)

            # Split snake_case: user_profile → ['user', 'profile']
            if "_" in token:
                snake_parts = token.split("_")
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

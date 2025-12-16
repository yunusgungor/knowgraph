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
        """Generate sparse embedding for code.

        For code, we might want to keep camelCase or snake_case parts.
        For now, treating same as text but could be specialized.
        """
        try:
            # For code, often splitting by non-alphanumeric is good
            # to catch "my_var" as "my", "var", "my_var" etc.
            # Here we stick to simple tokenization for consistency.
            tokens = self._tokenize(code)
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

"""Inverted Index implementation for sparse retrieval (BM25).

Replaces FAISS vector store with a pure-python dictionary-based inverted index.
Ideal for static, low-resource environments.

Supports both sync and async search for optimal performance.
"""

import asyncio
import json
import math
from collections import defaultdict
from pathlib import Path
from uuid import UUID


class SparseIndex:
    """Inverted Index with BM25 scoring.

    Attributes:
        index: Dict mapping terms to list of (doc_id, term_freq)
        doc_lengths: Dict mapping doc_id to document length (number of tokens)
        avg_doc_length: Average document length in corpus
        n_docs: Total number of documents

    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """Initialize sparse index.

        Args:
            k1: BM25 k1 parameter (term frequency saturation)
            b: BM25 b parameter (length normalization)

        """
        self.k1 = k1
        self.b = b

        # Inverted index: term -> [(doc_id, freq), ...]
        self.index: dict[str, list[tuple[str, int]]] = defaultdict(list)

        # Document statistics
        self.doc_lengths: dict[str, int] = {}
        self.doc_embeddings: dict[str, dict[str, int]] = {}  # Cache of sparse embeddings
        self.n_docs = 0
        self.avg_doc_length = 0.0

    def add(self, node_id: str | UUID, sparse_vector: dict[str, int]) -> None:
        """Add a document to the index.

        Args:
            node_id: Unique identifier for the document
            sparse_vector: Term frequency dictionary {term: freq}

        """
        doc_id = str(node_id)
        doc_len = sum(sparse_vector.values())

        # Update doc stats
        self.doc_lengths[doc_id] = doc_len
        self.doc_embeddings[doc_id] = sparse_vector
        self.n_docs += 1

        # Add to inverted index
        for term, freq in sparse_vector.items():
            self.index[term].append((doc_id, freq))

    def build(self) -> None:
        """Finalize index construction (calculate averages)."""
        if self.n_docs > 0:
            self.avg_doc_length = sum(self.doc_lengths.values()) / self.n_docs

    def search(self, query_vector: dict[str, int], top_k: int = 10) -> list[tuple[str, float]]:
        """Search the index using BM25.

        Args:
            query_vector: Query sparse vector {term: freq}
            top_k: Number of results to return

        Returns:
            List of (doc_id, core) tuples sorted by score descending

        """
        scores: dict[str, float] = defaultdict(float)

        for term, q_freq in query_vector.items():
            if term not in self.index:
                continue

            # Calculate IDF
            # idf = log((N - n + 0.5) / (n + 0.5) + 1)
            n_t = len(self.index[term])
            idf = math.log((self.n_docs - n_t + 0.5) / (n_t + 0.5) + 1)

            # Calculate score contribution for this term for all docs containing it
            for doc_id, t_freq in self.index[term]:
                doc_len = self.doc_lengths[doc_id]

                # BM25 term weight
                numerator = t_freq * (self.k1 + 1)
                denominator = t_freq + self.k1 * (
                    1 - self.b + self.b * (doc_len / (self.avg_doc_length or 1))
                )

                score = idf * (numerator / denominator)
                scores[doc_id] += score

        # Sort and return top_k
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_k]

    async def search_async(
        self, query_vector: dict[str, int], top_k: int = 10
    ) -> list[tuple[str, float]]:
        """Search the index using BM25 asynchronously with parallel term processing.

        This async version processes query terms concurrently for better performance
        on multi-core systems, especially for queries with many terms.

        Args:
            query_vector: Query sparse vector {term: freq}
            top_k: Number of results to return

        Returns:
            List of (doc_id, score) tuples sorted by score descending

        """
        scores: dict[str, float] = defaultdict(float)

        # Process terms in parallel batches for better performance
        async def score_term(term: str, q_freq: int) -> dict[str, float]:
            """Score documents for a single query term."""
            term_scores: dict[str, float] = {}

            if term not in self.index:
                return term_scores

            # Calculate IDF
            n_t = len(self.index[term])
            idf = math.log((self.n_docs - n_t + 0.5) / (n_t + 0.5) + 1)

            # Calculate score contribution for this term
            for doc_id, t_freq in self.index[term]:
                doc_len = self.doc_lengths[doc_id]

                # BM25 term weight
                numerator = t_freq * (self.k1 + 1)
                denominator = t_freq + self.k1 * (
                    1 - self.b + self.b * (doc_len / (self.avg_doc_length or 1))
                )

                score = idf * (numerator / denominator)
                term_scores[doc_id] = score

            # Yield control to event loop
            await asyncio.sleep(0)
            return term_scores

        # Process all terms concurrently
        tasks = [score_term(term, q_freq) for term, q_freq in query_vector.items()]
        term_score_dicts = await asyncio.gather(*tasks)

        # Aggregate scores from all terms
        for term_scores in term_score_dicts:
            for doc_id, score in term_scores.items():
                scores[doc_id] += score

        # Sort and return top_k
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_k]

    def save(self, directory: str | Path) -> None:
        """Save index to disk."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)

        data = {
            "index": self.index,
            "doc_lengths": self.doc_lengths,
            "n_docs": self.n_docs,
            "avg_doc_length": self.avg_doc_length,
            # We don't necessarily need to save doc_embeddings if we just want search
            # "doc_embeddings": self.doc_embeddings
        }

        with open(directory / "sparse_index.json", "w") as f:
            json.dump(data, f)

    def load(self, directory: str | Path) -> None:
        """Load index from disk."""
        directory = Path(directory)
        path = directory / "sparse_index.json"

        if not path.exists():
            return

        with open(path) as f:
            data = json.load(f)

        self.index = data["index"]
        self.doc_lengths = data["doc_lengths"]
        self.n_docs = data["n_docs"]
        self.avg_doc_length = data["avg_doc_length"]

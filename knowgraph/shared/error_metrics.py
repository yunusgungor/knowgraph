"""Error metrics collection for indexing operations."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class IndexingMetrics:
    """Metrics for tracking indexing performance and errors."""

    # Counters
    total_chunks: int = 0
    successful_chunks: int = 0
    ast_successes: int = 0
    ast_failures: int = 0
    llm_successes: int = 0
    llm_failures: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    # Timing
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None

    # Errors
    error_details: list[dict[str, Any]] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_chunks == 0:
            return 0.0
        return self.successful_chunks / self.total_chunks

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_cache_attempts = self.cache_hits + self.cache_misses
        if total_cache_attempts == 0:
            return 0.0
        return self.cache_hits / total_cache_attempts

    @property
    def duration_seconds(self) -> float:
        """Calculate duration in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self.cache_hits += 1
        self.successful_chunks += 1

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self.cache_misses += 1

    def record_ast_success(self) -> None:
        """Record successful AST parsing."""
        self.ast_successes += 1
        self.successful_chunks += 1

    def record_ast_failure(self, error: str, chunk_info: str = "") -> None:
        """Record AST parsing failure."""
        self.ast_failures += 1
        self.error_details.append(
            {
                "type": "ast_failure",
                "error": error,
                "chunk": chunk_info,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def record_llm_success(self) -> None:
        """Record successful LLM extraction."""
        self.llm_successes += 1
        self.successful_chunks += 1

    def record_llm_failure(self, error: str, chunk_info: str = "") -> None:
        """Record LLM extraction failure."""
        self.llm_failures += 1
        self.error_details.append(
            {
                "type": "llm_failure",
                "error": error,
                "chunk": chunk_info,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def finalize(self) -> None:
        """Mark metrics collection as complete."""
        self.end_time = datetime.now()

    def get_summary(self) -> str:
        """Get human-readable summary.

        Returns:
            Formatted summary string.
        """
        duration = self.duration_seconds
        chunks_per_sec = self.total_chunks / duration if duration > 0 else 0

        summary = f"""
Indexing Metrics Summary
========================
Total Chunks: {self.total_chunks}
Successful: {self.successful_chunks} ({self.success_rate:.1%})
Duration: {duration:.1f}s ({chunks_per_sec:.1f} chunks/sec)

Cache Performance:
  Hits: {self.cache_hits}
  Misses: {self.cache_misses}
  Hit Rate: {self.cache_hit_rate:.1%}

Entity Extraction:
  AST: {self.ast_successes} successes, {self.ast_failures} failures
  LLM: {self.llm_successes} successes, {self.llm_failures} failures

Errors: {len(self.error_details)} total
"""
        if self.error_details:
            summary += "\nRecent Errors:\n"
            for error in self.error_details[-5:]:  # Show last 5
                summary += f"  - [{error['type']}] {error['error'][:80]}\n"

        return summary.strip()

    # get_dict removed as it was unused serialization helper

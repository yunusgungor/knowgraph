"""Configuration constants for KnowGraph system.

All magic numbers and configuration values are centralized here following
Clean Code principles.

NEW: Added Pydantic-based settings for runtime configuration (Phase 2).
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# =============================================================================
# Pydantic Settings (Environment-Aware Configuration)
# =============================================================================


class PerformanceSettings(BaseSettings):
    """Performance tuning settings.

    Controls concurrency, caching, and batch processing behavior.
    """

    max_workers: int = Field(
        10,
        ge=1,
        le=50,
        description="Maximum concurrent workers for parallel processing",
    )
    cache_size: int = Field(
        1000,
        ge=100,
        le=10000,
        description="LRU cache size for embeddings and tokenization",
    )
    batch_size: int = Field(
        10,
        ge=1,
        le=100,
        description="Batch size for processing operations",
    )

    model_config = SettingsConfigDict(
        env_prefix="KNOWGRAPH_PERF_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class MemorySettings(BaseSettings):
    """Memory management settings.

    Controls memory profiling thresholds and garbage collection.
    """

    warning_threshold_mb: int = Field(
        500,
        ge=100,
        description="Memory usage warning threshold in MB",
    )
    critical_threshold_mb: int = Field(
        1000,
        ge=500,
        description="Memory usage critical threshold in MB",
    )
    auto_gc: bool = Field(
        True,
        description="Enable automatic garbage collection on high memory",
    )

    model_config = SettingsConfigDict(
        env_prefix="KNOWGRAPH_MEMORY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class QuerySettings(BaseSettings):
    """Query execution settings.

    Controls query behavior, results, and graph traversal.
    """

    top_k: int = Field(
        20,
        ge=1,
        le=100,
        description="Number of top results to return",
    )
    max_hops: int = Field(
        4,
        ge=1,
        le=10,
        description="Maximum graph traversal depth",
    )
    enable_query_expansion: bool = Field(
        True,
        description="Enable LLM-powered query expansion",
    )
    timeout_seconds: float = Field(
        30.0,
        ge=1.0,
        le=300.0,
        description="Query execution timeout in seconds",
    )

    model_config = SettingsConfigDict(
        env_prefix="KNOWGRAPH_QUERY_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class KnowGraphSettings(BaseSettings):
    """Main KnowGraph application settings.

    Aggregates all configuration groups and provides general settings.
    Automatically loads from .env file if present.
    """

    # Sub-configuration groups
    performance: PerformanceSettings = Field(
        default_factory=PerformanceSettings,
        description="Performance-related settings",
    )
    memory: MemorySettings = Field(
        default_factory=MemorySettings,
        description="Memory management settings",
    )
    query: QuerySettings = Field(
        default_factory=QuerySettings,
        description="Query execution settings",
    )

    # General application settings
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        "INFO",
        description="Logging level",
    )
    graph_store_path: Path = Field(
        Path("./graphstore"),
        description="Path to graph storage directory",
    )

    model_config = SettingsConfigDict(
        env_prefix="KNOWGRAPH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> KnowGraphSettings:
    """Get cached settings singleton.

    Settings are loaded once and cached for the application lifetime.
    """
    return KnowGraphSettings()  # type: ignore[call-arg]


# =============================================================================
# Legacy Constants (Maintained for Backward Compatibility)
# =============================================================================

# Chunking Configuration
DEFAULT_CHUNK_SIZE = 20000
DEFAULT_CHUNK_OVERLAP = 100
MIN_CHUNK_SIZE = 150

# Retrieval Configuration
TOP_K = 20
ENABLE_QUERY_EXPANSION = True


def get_optimal_workers() -> int:
    """Get optimal worker count based on available system resources."""
    try:
        from knowgraph.shared.resource_detector import ResourceDetector

        # Reduced max workers to avoid rate limits (30 -> 5)
        return ResourceDetector.recommend_workers(max_workers=5)
    except Exception:
        return 5


# Maximum concurrent API requests (reduced to avoid rate limits)
MAX_CONCURRENT_REQUESTS = int(os.getenv("KNOWGRAPH_WORKERS", get_optimal_workers()))

# Batch size for LLM entity extraction (balanced for rate limits)
# Auto-tuned to available RAM (smaller on low-memory hosts), override via
# KNOWGRAPH_BATCH_SIZE.
def _get_optimal_batch_size() -> int:
    try:
        from knowgraph.shared.resource_detector import ResourceDetector

        return ResourceDetector.recommend_batch_size(default=15)
    except Exception:
        return 10


BATCH_SIZE = int(os.getenv("KNOWGRAPH_BATCH_SIZE", _get_optimal_batch_size()))

# Async Configuration
MAX_CONCURRENT_QUERIES = 15
QUERY_TIMEOUT_SECONDS = 30.0

# Centrality Optimization Configuration
CENTRALITY_APPROXIMATE_THRESHOLD = 75
CENTRALITY_MULTIPROCESSING_ENABLED = True
CENTRALITY_MULTIPROCESSING_THRESHOLD = 500

# Approximate Centrality Settings
BETWEENNESS_SAMPLE_SIZE_FACTOR = 0.4
BETWEENNESS_MIN_SAMPLES = 15
EIGENVECTOR_MAX_ITER_APPROXIMATE = 50
EIGENVECTOR_MAX_ITER_EXACT = 100

# LLM Configuration
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_OPENAI_MODEL = os.getenv("KNOWGRAPH_LLM_MODEL", "gpt-4o-mini")
KNOWGRAPH_LLM_MODEL = DEFAULT_OPENAI_MODEL
LLM_TEMPERATURE = 0.0
MAX_EXPANSION_TERMS = 5
LLM_RETRY_COUNT = int(os.getenv("KNOWGRAPH_LLM_RETRY_COUNT", "5"))
LLM_RETRY_BASE_DELAY = float(os.getenv("KNOWGRAPH_LLM_RETRY_DELAY", "1.0"))
# Max tokens the LLM may GENERATE per completion (output cap). Keeps costs
# bounded and avoids runaway responses. Override via KNOWGRAPH_LLM_MAX_TOKENS.
LLM_MAX_TOKENS = int(os.getenv("KNOWGRAPH_LLM_MAX_TOKENS", "4096"))
# Approx. max INPUT tokens per completion (model context minus output cap).
# gpt-4o-mini has a 128k context; a conservative default protects smaller models.
LLM_MAX_INPUT_TOKENS = int(os.getenv("KNOWGRAPH_LLM_MAX_INPUT_TOKENS", "32000"))

# Graph Traversal Configuration
MAX_HOPS = 4

# Context Assembly Configuration
# Maximum number of tokens collected into the RAG context (a large budget —
# the graph context is broad). Distinct from LLM_MAX_TOKENS, which bounds the
# LLM's generated output. CLI/engine/MCP default the LLM output to
# LLM_MAX_TOKENS; this constant is only the context-collection cap.
MAX_TOKENS = 50000

# Node Activation Scoring Weights
ALPHA = 0.6
BETA = 0.3
GAMMA = 0.1

# Centrality Composite Scoring Weights
CENTRALITY_BETWEENNESS_WEIGHT = 0.5
CENTRALITY_DEGREE_WEIGHT = 0.2
CENTRALITY_CLOSENESS_WEIGHT = 0.2
CENTRALITY_EIGENVECTOR_WEIGHT = 0.1

# Storage Configuration
DEFAULT_GRAPH_STORE_PATH = "./graphstore"
EDGES_FILENAME = "edges.jsonl"

# Node Role Weights
ROLE_WEIGHTS = {
    "code": 0.9,
    "conversation": 0.85,
    "tagged_snippet": 0.85,
    "config": 0.8,
    "readme": 0.7,
    "text": 0.6,
}

# Token Penalty Configuration
MAX_TOKEN_COUNT_FOR_PENALTY = 1000
TOKEN_PENALTY_FACTOR = 0.1

# Hashing Configuration
FILE_READ_CHUNK_SIZE = 8192

# Validation Limits
MAX_NODE_TOKEN_COUNT = 50000
MAX_QUERY_PREVIEW_LENGTH = 100

# Milliseconds to Seconds Conversion
MS_TO_SECONDS = 1000

# Seed Node Bonus
SEED_NODE_BONUS = 1.0

# Default Score Values
DEFAULT_SIMILARITY_SCORE = 0.0
DEFAULT_CENTRALITY_SCORE = 0.0
DEFAULT_ROLE_WEIGHT = 0.5

# =============================================================================
# Joern Integration Configuration (v0.8.0+)
# =============================================================================

# Joern Enabled/Disabled (DEFAULT: ENABLED)
JOERN_ENABLED = os.getenv("KNOWGRAPH_JOERN_ENABLED", "true").lower() == "true"

# Joern Path (auto-detected if None)
JOERN_PATH = os.getenv("KNOWGRAPH_JOERN_PATH")  # None = auto-detect

# Joern Timeout Configuration
JOERN_TIMEOUT = int(os.getenv("KNOWGRAPH_JOERN_TIMEOUT", "120"))  # Reduced to 2 minutes

# Persistent Joern daemon (single JVM). When enabled, JoernQueryExecutor runs
# queries on a long-lived REPL instead of starting a fresh JVM per query.
# Disable for one-shot environments (e.g. tests) where daemon lifecycle is
# undesirable. DAEMON_START_TIMEOUT covers the initial JVM + REPL boot.
JOERN_DAEMON_ENABLED = os.getenv("KNOWGRAPH_JOERN_DAEMON", "true").lower() == "true"
JOERN_DAEMON_BOOT_TIMEOUT = int(os.getenv("KNOWGRAPH_JOERN_DAEMON_BOOT_TIMEOUT", "120"))

# CPG Integration Settings (v0.8.0+)
# Enable creation of separate nodes from CPG entities. Joern runs on every
# code file, so its CPG nodes are folded into the graph by default to
# maximize indexing/extraction quality. Set KNOWGRAPH_CPG_NODES_ENABLED=false
# to keep the graph smaller (metadata-only extraction).
CPG_NODES_ENABLED = os.getenv("KNOWGRAPH_CPG_NODES_ENABLED", "true").lower() == "true"

# CPG node types to create KnowGraph nodes for
CPG_NODE_TYPES = os.getenv(
    "KNOWGRAPH_CPG_NODE_TYPES",
    "METHOD,CALL,TYPE_DECL,IDENTIFIER,LOCAL"
).split(",")

# Intelligence Provider Settings
JOERN_EXPORT_TIMEOUT = int(os.getenv("KNOWGRAPH_JOERN_EXPORT_TIMEOUT", "300"))  # 5 minutes

# Joern is used for every code file (no size/language thresholds):
# Joern is the primary extractor across the whole pipeline.
JOERN_MAX_CPG_SIZE_MB = 500


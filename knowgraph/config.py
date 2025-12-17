"""Configuration constants for KnowGraph system.

All magic numbers and configuration values are centralized here following
Clean Code principles.
"""

import os

# Chunking Configuration
DEFAULT_CHUNK_SIZE = 24000  # Maximum characters per chunk (Optimization for large files)
DEFAULT_CHUNK_OVERLAP = 50  # Token overlap between chunks
MIN_CHUNK_SIZE = 100  # Minimum chunk size to avoid noise

# Retrieval Configuration
TOP_K = 20  # Number of seed nodes from vector search
MAX_NODES = 200  # Maximum nodes in active subgraph
ENABLE_QUERY_EXPANSION = True  # Enable LLM-based query expansion
MAX_CONCURRENT_REQUESTS = 20  # Maximum concurrent API requests
BATCH_SIZE = 10  # Number of chunks to process in a single LLM call

# Async Configuration
MAX_CONCURRENT_QUERIES = 10  # Maximum concurrent queries in async mode
MAX_CONCURRENT_NODE_LOADS = 50  # Maximum concurrent node file loads
QUERY_TIMEOUT_SECONDS = 30.0  # Default timeout for async queries
BATCH_QUERY_CHUNK_SIZE = 5  # Number of queries to process concurrently in batch


# LLM Configuration
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_OPENAI_MODEL = os.getenv("KNOWGRAPH_LLM_MODEL", "gpt-4o-mini")
KNOWGRAPH_LLM_MODEL = DEFAULT_OPENAI_MODEL
LLM_TEMPERATURE = 0.0
MAX_EXPANSION_TERMS = 5  # Number of expansion terms

# Graph Traversal Configuration
MAX_HOPS = 4  # Maximum graph traversal depth
MIN_HOPS = 1  # Minimum traversal depth
MAX_HOPS_LIMIT = 6  # Hard limit for traversal

# Context Assembly Configuration
MAX_TOKENS = 50000  # Maximum tokens for LLM context (increased for large files)
TOKEN_BUDGET_UTILIZATION = 0.90  # Target 90% token budget usage

# Node Activation Scoring Weights (sum = 1.0)
ALPHA = 0.6  # Weight for similarity score
BETA = 0.3  # Weight for centrality score
GAMMA = 0.1  # Weight for seed node indicator

# Centrality Composite Scoring Weights (sum = 1.0)
CENTRALITY_BETWEENNESS_WEIGHT = 0.5
CENTRALITY_DEGREE_WEIGHT = 0.2
CENTRALITY_CLOSENESS_WEIGHT = 0.2
CENTRALITY_EIGENVECTOR_WEIGHT = 0.1


# Storage Configuration
DEFAULT_GRAPH_STORE_PATH = "./graphstore"
NODES_DIR = "nodes"
EDGES_DIR = "edges"
METADATA_DIR = "metadata"
EDGES_FILENAME = "edges.jsonl"
NODES_FILENAME = "nodes.jsonl"
MANIFEST_FILENAME = "manifest.json"


# Node Role Weights (for importance scoring)
ROLE_WEIGHTS = {
    "code": 0.9,
    "config": 0.8,
    "readme": 0.7,
    "text": 0.6,
}

# Performance Configuration

GRAPH_TRAVERSAL_TIMEOUT_MS = 2000  # Target traversal + centrality latency
INCREMENTAL_UPDATE_TIMEOUT_S = 60  # Target for 10 file changes

# Token Penalty Configuration
MAX_TOKEN_COUNT_FOR_PENALTY = 1000  # Token count threshold for scoring penalty
TOKEN_PENALTY_FACTOR = 0.1  # Penalty factor for large chunks

# Hashing Configuration
FILE_READ_CHUNK_SIZE = 8192  # Bytes to read at a time for hashing

# Validation Limits
MAX_NODE_TOKEN_COUNT = 50000  # Maximum tokens per node
MAX_QUERY_PREVIEW_LENGTH = 100  # Characters to show in error messages

# Sampling Configuration
MAX_SIMILARITY_SAMPLE_PAIRS = 1000  # Max pairs for adaptive threshold calculation

# Milliseconds to Seconds Conversion
MS_TO_SECONDS = 1000  # Conversion factor for timing display

# Seed Node Bonus
SEED_NODE_BONUS = 1.0  # Importance bonus for seed nodes in scoring

# Default Score Values
DEFAULT_SIMILARITY_SCORE = 0.0  # Default if similarity not found
DEFAULT_CENTRALITY_SCORE = 0.0  # Default if centrality not calculated
DEFAULT_ROLE_WEIGHT = 0.5  # Default weight for unknown node types

# Cache Configuration
DEFAULT_CACHE_DIR = "/workspace/.cache"
MODELS_CACHE_DIR = "/workspace/.cache/models"
HF_HOME_DIR = "/workspace/.cache/huggingface"
TRANSFORMERS_CACHE_DIR = "/workspace/.cache/huggingface/transformers"
HF_DATASETS_CACHE_DIR = "/workspace/.cache/huggingface/datasets"

# Logging Configuration
LOG_LEVEL = "INFO"
VERBOSE_LOG_LEVEL = "DEBUG"

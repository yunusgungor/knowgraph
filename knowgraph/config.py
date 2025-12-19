"""Configuration constants for KnowGraph system.

All magic numbers and configuration values are centralized here following
Clean Code principles.
"""

import os


# Validated as unused during Deep Code Clean Phase 6

# Chunking Configuration
DEFAULT_CHUNK_SIZE = (
    20000  # Maximum characters per chunk (Optimized from 24000 for better memory usage)
)
DEFAULT_CHUNK_OVERLAP = 100  # Token overlap between chunks (increased for better context)
MIN_CHUNK_SIZE = 150  # Minimum chunk size to avoid noise (increased from 100)

# Retrieval Configuration
TOP_K = 20  # Number of seed nodes from vector search
ENABLE_QUERY_EXPANSION = True  # Enable LLM-based query expansion


def get_optimal_workers() -> int:
    """Get optimal worker count based on available system resources.

    Returns:
        Optimal number of concurrent workers.
    """
    try:
        from knowgraph.shared.resource_detector import ResourceDetector

        return ResourceDetector.recommend_workers(max_workers=30)
    except Exception:
        return 30  # Fallback to default


# Maximum concurrent API requests (can be overridden by environment or auto-detection)
MAX_CONCURRENT_REQUESTS = int(os.getenv("KNOWGRAPH_WORKERS", get_optimal_workers()))

BATCH_SIZE = 15  # Number of chunks to process in a single LLM call (increased from 10)

# Async Configuration
MAX_CONCURRENT_QUERIES = 15  # Maximum concurrent queries in async mode (increased from 10)
QUERY_TIMEOUT_SECONDS = 30.0  # Default timeout for async queries


# Centrality Optimization Configuration
CENTRALITY_APPROXIMATE_THRESHOLD = 75  # Use approximate algorithms for graphs >75 nodes (optimized)
CENTRALITY_MULTIPROCESSING_ENABLED = True  # Multiprocessing enabled for large graphs
CENTRALITY_MULTIPROCESSING_THRESHOLD = (
    500  # Use multiprocessing for graphs >500 nodes (reduced from 1000)
)

# Approximate Centrality Settings
BETWEENNESS_SAMPLE_SIZE_FACTOR = (
    0.4  # Sample size = 0.4*sqrt(n) for approximate betweenness (optimized)
)
BETWEENNESS_MIN_SAMPLES = 15  # Minimum samples for approximate betweenness (increased for accuracy)
EIGENVECTOR_MAX_ITER_APPROXIMATE = 50  # Max iterations for approximate eigenvector
EIGENVECTOR_MAX_ITER_EXACT = 100  # Max iterations for exact eigenvector


# LLM Configuration
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_OPENAI_MODEL = os.getenv("KNOWGRAPH_LLM_MODEL", "gpt-5-nano")
KNOWGRAPH_LLM_MODEL = DEFAULT_OPENAI_MODEL
LLM_TEMPERATURE = 0.0
MAX_EXPANSION_TERMS = 5  # Number of expansion terms
LLM_RETRY_COUNT = int(
    os.getenv("KNOWGRAPH_LLM_RETRY_COUNT", "5")
)  # Number of retry attempts for API calls
LLM_RETRY_BASE_DELAY = float(
    os.getenv("KNOWGRAPH_LLM_RETRY_DELAY", "1.0")
)  # Base delay for exponential backoff (seconds)

# Graph Traversal Configuration
MAX_HOPS = 4  # Maximum graph traversal depth


# Context Assembly Configuration
MAX_TOKENS = 50000  # Maximum tokens for LLM context (increased for large files)


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
EDGES_FILENAME = "edges.jsonl"


# Node Role Weights (for importance scoring)
ROLE_WEIGHTS = {
    "code": 0.9,
    "conversation": 0.85,  # High priority - contains context and examples
    "tagged_snippet": 0.85,  # Same as conversation - user-tagged important content
    "config": 0.8,
    "readme": 0.7,
    "text": 0.6,
}


# Token Penalty Configuration
MAX_TOKEN_COUNT_FOR_PENALTY = 1000  # Token count threshold for scoring penalty
TOKEN_PENALTY_FACTOR = 0.1  # Penalty factor for large chunks

# Hashing Configuration
FILE_READ_CHUNK_SIZE = 8192  # Bytes to read at a time for hashing


# Validation Limits
MAX_NODE_TOKEN_COUNT = 50000  # Maximum tokens per node
MAX_QUERY_PREVIEW_LENGTH = 100  # Characters to show in error messages


# Milliseconds to Seconds Conversion
MS_TO_SECONDS = 1000  # Conversion factor for timing display

# Seed Node Bonus
SEED_NODE_BONUS = 1.0  # Importance bonus for seed nodes in scoring

# Default Score Values
DEFAULT_SIMILARITY_SCORE = 0.0  # Default if similarity not found
DEFAULT_CENTRALITY_SCORE = 0.0  # Default if centrality not calculated
DEFAULT_ROLE_WEIGHT = 0.5  # Default weight for unknown node types

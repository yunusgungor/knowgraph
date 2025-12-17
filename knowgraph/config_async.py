# KnowGraph Async Configuration

# Async Query Configuration
MAX_CONCURRENT_QUERIES = 10  # Maximum concurrent queries in async mode
MAX_CONCURRENT_NODE_LOADS = 50  # Maximum concurrent node file loads
QUERY_TIMEOUT_SECONDS = 30.0  # Default timeout for async queries
BATCH_QUERY_CHUNK_SIZE = 5  # Number of queries to process concurrently in batch

# Centrality Optimization Configuration
CENTRALITY_CACHE_SIZE = 256  # Maximum number of cached subgraphs
CENTRALITY_APPROXIMATE_THRESHOLD = 100  # Use approximate algorithms for graphs >100 nodes
CENTRALITY_MULTIPROCESSING_ENABLED = False  # Multiprocessing disabled by default (overhead)
CENTRALITY_MULTIPROCESSING_THRESHOLD = 1000  # Only use multiprocessing for graphs >1000 nodes

# Approximate Centrality Settings
BETWEENNESS_SAMPLE_SIZE_FACTOR = 0.5  # Sample size = sqrt(n) for approximate betweenness
BETWEENNESS_MIN_SAMPLES = 10  # Minimum samples for approximate betweenness
EIGENVECTOR_MAX_ITER_APPROXIMATE = 50  # Max iterations for approximate eigenvector
EIGENVECTOR_MAX_ITER_EXACT = 100  # Max iterations for exact eigenvector

# Performance Tuning
ENABLE_CENTRALITY_CACHING = True  # Enable centrality caching (22x speedup)
ENABLE_APPROXIMATE_CENTRALITY = True  # Enable approximate centrality for large graphs

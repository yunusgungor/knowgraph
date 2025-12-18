# KnowGraph Async Configuration

# Async Query Configuration
MAX_CONCURRENT_QUERIES = 10  # Maximum concurrent queries in async mode
MAX_CONCURRENT_NODE_LOADS = 50  # Maximum concurrent node file loads
QUERY_TIMEOUT_SECONDS = 30.0  # Default timeout for async queries
BATCH_QUERY_CHUNK_SIZE = 5  # Number of queries to process concurrently in batch

# Centrality Optimization Configuration
CENTRALITY_CACHE_SIZE = 512  # Maximum number of cached subgraphs (increased from 256)
CENTRALITY_APPROXIMATE_THRESHOLD = 75  # Use approximate algorithms for graphs >75 nodes (optimized)
CENTRALITY_MULTIPROCESSING_ENABLED = True  # Multiprocessing enabled for large graphs
CENTRALITY_MULTIPROCESSING_THRESHOLD = 500  # Use multiprocessing for graphs >500 nodes (reduced from 1000)

# Approximate Centrality Settings
BETWEENNESS_SAMPLE_SIZE_FACTOR = 0.4  # Sample size = 0.4*sqrt(n) for approximate betweenness (optimized)
BETWEENNESS_MIN_SAMPLES = 15  # Minimum samples for approximate betweenness (increased for accuracy)
EIGENVECTOR_MAX_ITER_APPROXIMATE = 50  # Max iterations for approximate eigenvector
EIGENVECTOR_MAX_ITER_EXACT = 100  # Max iterations for exact eigenvector

# Performance Tuning
ENABLE_CENTRALITY_CACHING = True  # Enable centrality caching (22x speedup)
ENABLE_APPROXIMATE_CENTRALITY = True  # Enable approximate centrality for large graphs

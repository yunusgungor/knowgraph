"""Global resilience patterns shared across MCP handlers."""

import logging

from knowgraph.shared.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from knowgraph.shared.rate_limiter import (
    RateLimiter as SharedRateLimiter,
)

# Initialize logger
logger = logging.getLogger(__name__)

# Global resilience patterns - shared across all handlers
_global_circuit_breaker = CircuitBreaker(
    name="mcp_handlers",
    config=CircuitBreakerConfig(
        failure_threshold=5,
        timeout=60.0,  # Use 'timeout' not 'recovery_timeout'
        success_threshold=3,  # Use 'success_threshold' not 'half_open_max_calls'
    ),
)

_global_rate_limiter = SharedRateLimiter(
    rate=10,  # 10 requests
    period=1.0,  # per second
    algorithm="token_bucket",
    burst_size=20,
)
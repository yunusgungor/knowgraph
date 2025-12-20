"""Tests for circuit breaker pattern."""

import asyncio

import pytest

from knowgraph.shared.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    clear_circuit_breakers,
    get_circuit_breaker,
)


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout == 60.0
        assert config.window_size == 10
        assert config.expected_exceptions == (Exception,)

    def test_custom_config(self):
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=1,
            timeout=30.0,
            window_size=5,
            expected_exceptions=(ValueError, TypeError),
        )

        assert config.failure_threshold == 3
        assert config.success_threshold == 1
        assert config.timeout == 30.0
        assert config.window_size == 5
        assert config.expected_exceptions == (ValueError, TypeError)


class TestCircuitBreakerStates:
    """Tests for circuit breaker state properties."""

    def test_initial_state_closed(self):
        """Test circuit breaker starts in closed state."""
        breaker = CircuitBreaker("test")

        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open
        assert not breaker.is_half_open

    def test_state_properties(self):
        """Test state property checks."""
        breaker = CircuitBreaker("test")

        # Closed
        assert breaker.is_closed

        # Open
        breaker._state = CircuitState.OPEN
        assert breaker.is_open
        assert not breaker.is_closed

        # Half-open
        breaker._state = CircuitState.HALF_OPEN
        assert breaker.is_half_open
        assert not breaker.is_open


class TestCircuitBreakerAsync:
    """Tests for async circuit breaker operations."""

    @pytest.mark.asyncio
    async def test_successful_call(self):
        """Test successful function call."""
        breaker = CircuitBreaker("test")

        async def success_func():
            return "success"

        result = await breaker.call(success_func)

        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        stats = breaker.get_stats()
        assert stats.total_calls == 1
        assert stats.total_successes == 1
        assert stats.total_failures == 0

    @pytest.mark.asyncio
    async def test_failed_call_stays_closed(self):
        """Test single failure doesn't open circuit."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        assert breaker.state == CircuitState.CLOSED
        stats = breaker.get_stats()
        assert stats.total_failures == 1
        assert stats.failure_count == 1

    @pytest.mark.asyncio
    async def test_multiple_failures_open_circuit(self):
        """Test multiple failures open the circuit."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("Test error")

        # Fail 3 times to open circuit
        for _ in range(3):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN
        stats = breaker.get_stats()
        assert stats.total_failures == 3

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self):
        """Test open circuit rejects calls immediately."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

        # Next call should be rejected
        async def success_func():
            return "success"

        with pytest.raises(CircuitBreakerError) as exc_info:
            await breaker.call(success_func)

        assert "is open" in str(exc_info.value)
        stats = breaker.get_stats()
        assert stats.total_rejections == 1

    @pytest.mark.asyncio
    async def test_half_open_transition(self):
        """Test transition from open to half-open after timeout."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=0.1)
        breaker = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Next call should transition to half-open
        async def success_func():
            return "success"

        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self):
        """Test successful calls in half-open close circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout=0.1,
        )
        breaker = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("Test error")

        async def success_func():
            return "success"

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

        # Wait and transition to half-open
        await asyncio.sleep(0.15)

        # Two successes should close circuit
        await breaker.call(success_func)
        assert breaker.state == CircuitState.HALF_OPEN

        await breaker.call(success_func)
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self):
        """Test failure in half-open reopens circuit."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=0.1)
        breaker = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        # Wait and transition to half-open
        await asyncio.sleep(0.15)

        # Failure should reopen circuit
        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_reset_circuit(self):
        """Test manual circuit reset."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

        # Reset manually
        await breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        stats = breaker.get_stats()
        assert stats.failure_count == 0


class TestCircuitBreakerSync:
    """Tests for synchronous circuit breaker operations."""

    def test_sync_successful_call(self):
        """Test synchronous successful call."""
        breaker = CircuitBreaker("test")

        def success_func():
            return "success"

        result = breaker.call_sync(success_func)

        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    def test_sync_failed_call(self):
        """Test synchronous failed call."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)

        def fail_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            breaker.call_sync(fail_func)

        assert breaker.state == CircuitState.CLOSED

    def test_sync_open_circuit(self):
        """Test synchronous calls with open circuit."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)

        def fail_func():
            raise ValueError("Test error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                breaker.call_sync(fail_func)

        assert breaker.state == CircuitState.OPEN

        # Next call should be rejected
        def success_func():
            return "success"

        with pytest.raises(CircuitBreakerError):
            breaker.call_sync(success_func)


class TestCircuitBreakerStats:
    """Tests for circuit breaker statistics."""

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Test statistics are properly tracked."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        async def success_func():
            return "success"

        async def fail_func():
            raise ValueError("Test error")

        # Perform operations
        await breaker.call(success_func)

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        await breaker.call(success_func)

        stats = breaker.get_stats()
        assert stats.total_calls == 3
        assert stats.total_successes == 2
        assert stats.total_failures == 1
        assert stats.failure_count == 1

    @pytest.mark.asyncio
    async def test_rejection_stats(self):
        """Test rejection statistics."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test", config)

        async def fail_func():
            raise ValueError("Test error")

        # Open circuit
        for _ in range(2):
            with pytest.raises(ValueError):
                await breaker.call(fail_func)

        # Try to call while open
        async def success_func():
            return "success"

        for _ in range(3):
            with pytest.raises(CircuitBreakerError):
                await breaker.call(success_func)

        stats = breaker.get_stats()
        assert stats.total_rejections == 3


class TestCircuitBreakerRegistry:
    """Tests for circuit breaker registry."""

    def test_get_circuit_breaker(self):
        """Test getting circuit breaker from registry."""
        clear_circuit_breakers()

        breaker1 = get_circuit_breaker("api1")
        breaker2 = get_circuit_breaker("api1")

        assert breaker1 is breaker2
        assert breaker1.name == "api1"

    def test_multiple_circuit_breakers(self):
        """Test multiple circuit breakers in registry."""
        clear_circuit_breakers()

        breaker1 = get_circuit_breaker("api1")
        breaker2 = get_circuit_breaker("api2")

        assert breaker1 is not breaker2
        assert breaker1.name == "api1"
        assert breaker2.name == "api2"

    def test_clear_registry(self):
        """Test clearing circuit breaker registry."""
        get_circuit_breaker("api1")
        get_circuit_breaker("api2")

        clear_circuit_breakers()

        breaker3 = get_circuit_breaker("api1")
        assert breaker3.name == "api1"


class TestCircuitBreakerEdgeCases:
    """Tests for edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_with_arguments(self):
        """Test circuit breaker with function arguments."""
        breaker = CircuitBreaker("test")

        async def add_func(a: int, b: int) -> int:
            return a + b

        result = await breaker.call(add_func, 2, 3)

        assert result == 5

    @pytest.mark.asyncio
    async def test_with_kwargs(self):
        """Test circuit breaker with keyword arguments."""
        breaker = CircuitBreaker("test")

        async def greet_func(name: str, greeting: str = "Hello") -> str:
            return f"{greeting}, {name}!"

        result = await breaker.call(greet_func, name="World", greeting="Hi")

        assert result == "Hi, World!"

    @pytest.mark.asyncio
    async def test_sliding_window(self):
        """Test sliding window for failure tracking."""
        config = CircuitBreakerConfig(failure_threshold=3, window_size=5)
        breaker = CircuitBreaker("test", config)

        async def success_func():
            return "success"

        async def fail_func():
            raise ValueError("Test error")

        # Fill window with successes and failures
        await breaker.call(success_func)
        await breaker.call(success_func)

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        await breaker.call(success_func)

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        # Should still be closed (only 2 failures in window)
        assert breaker.state == CircuitState.CLOSED

    def test_repr(self):
        """Test string representation."""
        breaker = CircuitBreaker("test-api")

        repr_str = repr(breaker)

        assert "test-api" in repr_str
        assert "closed" in repr_str


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test complete circuit breaker lifecycle."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout=0.1,
        )
        breaker = CircuitBreaker("api", config)

        async def api_call(should_fail: bool = False):
            if should_fail:
                raise ValueError("API Error")
            return "success"

        # Start closed
        assert breaker.state == CircuitState.CLOSED

        # Successful calls
        await breaker.call(api_call, should_fail=False)
        await breaker.call(api_call, should_fail=False)
        assert breaker.state == CircuitState.CLOSED

        # Failures open circuit
        with pytest.raises(ValueError):
            await breaker.call(api_call, should_fail=True)
        with pytest.raises(ValueError):
            await breaker.call(api_call, should_fail=True)
        assert breaker.state == CircuitState.OPEN

        # Rejected while open
        with pytest.raises(CircuitBreakerError):
            await breaker.call(api_call, should_fail=False)

        # Wait for timeout
        await asyncio.sleep(0.15)

        # Transition to half-open and test recovery
        await breaker.call(api_call, should_fail=False)
        assert breaker.state == CircuitState.HALF_OPEN

        # Close circuit with success threshold
        await breaker.call(api_call, should_fail=False)
        assert breaker.state == CircuitState.CLOSED

        # Verify stats
        stats = breaker.get_stats()
        assert stats.total_calls == 7  # 2 + 2 + 1 + 2
        assert stats.total_successes == 4  # 2 initial + 2 half-open
        assert stats.total_failures == 2
        assert stats.total_rejections == 1

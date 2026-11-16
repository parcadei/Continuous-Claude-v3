"""Tests for CircuitBreaker pattern."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time


class TestCircuitBreakerClosed:
    """Test circuit stays closed on success."""

    @pytest.mark.asyncio
    async def test_circuit_stays_closed_on_success(self):
        """Circuit remains CLOSED when primary agent succeeds."""
        from scripts.agentica_patterns.patterns import CircuitBreaker, CircuitState

        # Create mock agents
        primary_agent = AsyncMock()
        primary_agent.call.return_value = "success result"

        fallback_agent = AsyncMock()

        with patch("scripts.agentica_patterns.patterns.circuit_breaker.spawn") as mock_spawn:
            # spawn returns primary first, then fallback
            mock_spawn.side_effect = [primary_agent, fallback_agent]

            cb = CircuitBreaker(
                primary_premise="You implement features.",
                fallback_premise="You implement simpler versions.",
                max_failures=3,
                reset_timeout=60
            )

            result = await cb.execute("Do something")

            assert result == "success result"
            assert cb.state == CircuitState.CLOSED
            assert cb.failure_count == 0
            primary_agent.call.assert_called_once()
            fallback_agent.call.assert_not_called()


class TestCircuitBreakerOpens:
    """Test circuit opens after max_failures."""

    @pytest.mark.asyncio
    async def test_circuit_opens_after_max_failures(self):
        """Circuit transitions to OPEN after max consecutive failures."""
        from scripts.agentica_patterns.patterns import CircuitBreaker, CircuitState

        primary_agent = AsyncMock()
        primary_agent.call.side_effect = Exception("primary failed")

        fallback_agent = AsyncMock()
        fallback_agent.call.return_value = "fallback result"

        with patch("scripts.agentica_patterns.patterns.circuit_breaker.spawn") as mock_spawn:
            mock_spawn.side_effect = [primary_agent, fallback_agent]

            cb = CircuitBreaker(
                primary_premise="You implement features.",
                fallback_premise="You implement simpler versions.",
                max_failures=3,
                reset_timeout=60
            )

            # First 3 failures should open the circuit
            for i in range(3):
                result = await cb.execute("Do something")
                # After max_failures, fallback should be used
                if i < 2:
                    assert cb.state == CircuitState.CLOSED
                else:
                    assert cb.state == CircuitState.OPEN

            assert cb.failure_count == 3


class TestCircuitBreakerFallback:
    """Test fallback is called when circuit is open."""

    @pytest.mark.asyncio
    async def test_fallback_called_when_open(self):
        """When circuit is OPEN, fallback agent is used."""
        from scripts.agentica_patterns.patterns import CircuitBreaker, CircuitState

        primary_agent = AsyncMock()
        primary_agent.call.side_effect = Exception("primary failed")

        fallback_agent = AsyncMock()
        fallback_agent.call.return_value = "fallback result"

        with patch("scripts.agentica_patterns.patterns.circuit_breaker.spawn") as mock_spawn:
            mock_spawn.side_effect = [primary_agent, fallback_agent]

            cb = CircuitBreaker(
                primary_premise="You implement features.",
                fallback_premise="You implement simpler versions.",
                max_failures=2,  # Lower threshold for faster test
                reset_timeout=60
            )

            # Trigger failures to open circuit
            for _ in range(2):
                await cb.execute("Do something")

            assert cb.state == CircuitState.OPEN

            # Now execute again - should use fallback
            primary_agent.call.reset_mock()
            result = await cb.execute("Do something else")

            assert result == "fallback result"
            fallback_agent.call.assert_called()


class TestCircuitBreakerReset:
    """Test circuit resets after timeout."""

    @pytest.mark.asyncio
    async def test_circuit_resets_after_timeout(self):
        """Circuit transitions to HALF_OPEN after reset_timeout."""
        from scripts.agentica_patterns.patterns import CircuitBreaker, CircuitState

        primary_agent = AsyncMock()
        primary_agent.call.side_effect = [
            Exception("fail 1"),
            Exception("fail 2"),
            "success after reset"  # Will succeed on half-open test
        ]

        fallback_agent = AsyncMock()
        fallback_agent.call.return_value = "fallback result"

        with patch("scripts.agentica_patterns.patterns.circuit_breaker.spawn") as mock_spawn:
            mock_spawn.side_effect = [primary_agent, fallback_agent]

            cb = CircuitBreaker(
                primary_premise="You implement features.",
                fallback_premise="You implement simpler versions.",
                max_failures=2,
                reset_timeout=0.1  # Short timeout for testing
            )

            # Trigger failures to open circuit
            for _ in range(2):
                await cb.execute("Do something")

            assert cb.state == CircuitState.OPEN

            # Wait for timeout
            await asyncio.sleep(0.15)

            # Next call should try primary in HALF_OPEN state
            result = await cb.execute("Do something")

            # If primary succeeds, circuit should close
            assert result == "success after reset"
            assert cb.state == CircuitState.CLOSED
            assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self):
        """If primary fails in HALF_OPEN state, circuit reopens."""
        from scripts.agentica_patterns.patterns import CircuitBreaker, CircuitState

        primary_agent = AsyncMock()
        primary_agent.call.side_effect = Exception("always fails")

        fallback_agent = AsyncMock()
        fallback_agent.call.return_value = "fallback result"

        with patch("scripts.agentica_patterns.patterns.circuit_breaker.spawn") as mock_spawn:
            mock_spawn.side_effect = [primary_agent, fallback_agent]

            cb = CircuitBreaker(
                primary_premise="You implement features.",
                fallback_premise="You implement simpler versions.",
                max_failures=2,
                reset_timeout=0.1
            )

            # Trigger failures to open circuit
            for _ in range(2):
                await cb.execute("Do something")

            assert cb.state == CircuitState.OPEN

            # Wait for timeout
            await asyncio.sleep(0.15)

            # Next call tries primary in HALF_OPEN, it fails
            result = await cb.execute("Do something")

            # Should use fallback and reopen circuit
            assert result == "fallback result"
            assert cb.state == CircuitState.OPEN

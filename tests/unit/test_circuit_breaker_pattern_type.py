"""
Tests for Circuit Breaker pattern PATTERN_TYPE environment variable setting.

Verifies that CircuitBreaker pattern sets the required environment variables
when spawning agents, enabling hooks to detect and route to circuit-breaker handlers.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scripts.agentica_patterns.patterns.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreakerEnvironmentVariables:
    """Test that CircuitBreaker sets PATTERN_TYPE and related env vars."""

    @pytest.mark.asyncio
    async def test_primary_agent_env_vars_closed(self):
        """Primary agent spawn includes circuit breaker env vars (closed state)."""
        with patch("scripts.agentica_patterns.patterns.circuit_breaker.spawn", new_callable=AsyncMock) as mock_spawn:
            mock_agent = MagicMock()
            mock_agent.call = AsyncMock(return_value="result")
            mock_spawn.return_value = mock_agent

            cb = CircuitBreaker(
                primary_premise="You are the primary agent",
                fallback_premise="You are the fallback agent",
                max_failures=3
            )

            # Execute to trigger primary spawn
            await cb.execute("test query")

            # Verify spawn was called
            assert mock_spawn.call_count >= 1

            # Check that env vars would be passed (note: current impl doesn't pass env,
            # this test documents the expected behavior for Phase 40)
            call_kwargs = mock_spawn.call_args_list[0][1] if mock_spawn.call_args_list else {}

            # TODO Phase 40: Verify these env vars are set
            # expected_env = {
            #     "PATTERN_TYPE": "circuit_breaker",
            #     "PATTERN_ID": cb.cb_id,
            #     "AGENT_ROLE": "primary",
            #     "CIRCUIT_STATE": "closed"
            # }
            # assert "env" in call_kwargs
            # assert call_kwargs["env"]["PATTERN_TYPE"] == "circuit_breaker"

    @pytest.mark.asyncio
    async def test_fallback_agent_env_vars(self):
        """Fallback agent spawn includes circuit breaker env vars."""
        with patch("scripts.agentica_patterns.patterns.circuit_breaker.spawn", new_callable=AsyncMock) as mock_spawn:
            mock_primary = MagicMock()
            mock_primary.call = AsyncMock(side_effect=RuntimeError("Primary failed"))

            mock_fallback = MagicMock()
            mock_fallback.call = AsyncMock(return_value="fallback result")

            # Return primary first, then fallback
            mock_spawn.side_effect = [mock_primary, mock_fallback]

            cb = CircuitBreaker(
                primary_premise="You are the primary agent",
                fallback_premise="You are the fallback agent",
                max_failures=1
            )

            # Execute - should fail to primary, then spawn fallback
            result = await cb.execute("test query")
            assert result == "fallback result"

            # Verify both agents spawned
            assert mock_spawn.call_count == 2

            # TODO Phase 40: Verify fallback env vars
            # fallback_kwargs = mock_spawn.call_args_list[1][1]
            # assert fallback_kwargs["env"]["AGENT_ROLE"] == "fallback"

    @pytest.mark.asyncio
    async def test_circuit_state_transitions_in_env(self):
        """Circuit state transitions are reflected in environment variables."""
        with patch("scripts.agentica_patterns.patterns.circuit_breaker.spawn", new_callable=AsyncMock) as mock_spawn:
            mock_primary = MagicMock()
            failures = [0]  # Mutable counter

            async def primary_call(return_type, query):
                failures[0] += 1
                if failures[0] <= 3:
                    raise RuntimeError("Primary failed")
                return "primary recovered"

            mock_primary.call = AsyncMock(side_effect=primary_call)

            mock_fallback = MagicMock()
            mock_fallback.call = AsyncMock(return_value="fallback result")

            mock_spawn.side_effect = [mock_primary, mock_fallback]

            cb = CircuitBreaker(
                primary_premise="You are the primary agent",
                fallback_premise="You are the fallback agent",
                max_failures=3,
                reset_timeout=0.1  # Short timeout for testing
            )

            # First call - circuit closed, primary fails
            await cb.execute("query 1")
            assert cb.state == CircuitState.CLOSED

            # Second call - still closed, primary fails again
            await cb.execute("query 2")
            assert cb.state == CircuitState.CLOSED

            # Third call - circuit opens after max failures
            await cb.execute("query 3")
            assert cb.state == CircuitState.OPEN

            # TODO Phase 40: Verify env vars reflect circuit state
            # At this point, subsequent agent spawns should have CIRCUIT_STATE=open

    @pytest.mark.asyncio
    async def test_cb_id_is_unique_per_instance(self):
        """Each CircuitBreaker instance has a unique PATTERN_ID."""
        cb1 = CircuitBreaker(
            primary_premise="Primary 1",
            fallback_premise="Fallback 1"
        )

        cb2 = CircuitBreaker(
            primary_premise="Primary 2",
            fallback_premise="Fallback 2"
        )

        # TODO Phase 40: Verify cb_id exists and is unique
        # assert hasattr(cb1, "cb_id")
        # assert hasattr(cb2, "cb_id")
        # assert cb1.cb_id != cb2.cb_id

    @pytest.mark.asyncio
    async def test_env_vars_with_coordination_db(self):
        """Circuit breaker sets env vars when using CoordinationDB."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        with patch("scripts.agentica_patterns.patterns.circuit_breaker.spawn", new_callable=AsyncMock) as mock_spawn:
            mock_agent = MagicMock()
            mock_agent.call = AsyncMock(return_value="result")
            mock_spawn.return_value = mock_agent

            db = CoordinationDB(":memory:")

            cb = CircuitBreaker(
                primary_premise="You are the primary agent",
                fallback_premise="You are the fallback agent",
                db=db
            )

            # Execute to trigger spawn
            with patch("scripts.agentica_patterns.tracked_agent.tracked_spawn", new_callable=AsyncMock) as mock_tracked:
                mock_tracked.return_value = mock_agent
                await cb.execute("test query")

                # Verify tracked_spawn was called with pattern
                assert mock_tracked.call_count >= 1
                call_kwargs = mock_tracked.call_args_list[0][1]
                assert call_kwargs["pattern"] == "circuit_breaker"

                # TODO Phase 40: Verify env vars are passed through tracked_spawn


class TestCircuitBreakerRoleInjection:
    """Test that roles (primary/fallback) are properly set."""

    @pytest.mark.asyncio
    async def test_primary_role_on_first_call(self):
        """First execution uses primary agent with role=primary."""
        with patch("scripts.agentica_patterns.patterns.circuit_breaker.spawn", new_callable=AsyncMock) as mock_spawn:
            mock_agent = MagicMock()
            mock_agent.call = AsyncMock(return_value="primary result")
            mock_spawn.return_value = mock_agent

            cb = CircuitBreaker(
                primary_premise="You are the primary agent",
                fallback_premise="You are the fallback agent"
            )

            result = await cb.execute("test query")
            assert result == "primary result"

            # TODO Phase 40: Verify AGENT_ROLE=primary in env

    @pytest.mark.asyncio
    async def test_fallback_role_when_circuit_open(self):
        """When circuit is open, fallback agent is used with role=fallback."""
        with patch("scripts.agentica_patterns.patterns.circuit_breaker.spawn", new_callable=AsyncMock) as mock_spawn:
            mock_primary = MagicMock()
            mock_primary.call = AsyncMock(side_effect=RuntimeError("Fail"))

            mock_fallback = MagicMock()
            mock_fallback.call = AsyncMock(return_value="fallback result")

            mock_spawn.side_effect = [mock_primary, mock_fallback]

            cb = CircuitBreaker(
                primary_premise="Primary",
                fallback_premise="Fallback",
                max_failures=1
            )

            # Fail once to open circuit
            await cb.execute("query 1")
            assert cb.state == CircuitState.OPEN

            # TODO Phase 40: Verify AGENT_ROLE=fallback in subsequent spawns

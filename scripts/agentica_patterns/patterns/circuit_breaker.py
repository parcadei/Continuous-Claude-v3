"""
CircuitBreaker Pattern for Agentica.

Failure detection with fallback routing. Wraps agent execution with failure detection
and routes to fallback agent after consecutive failures.
"""

import asyncio
import os
import time
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

# Import spawn from agentica if available, otherwise use a stub for testing
try:
    from agentica import spawn
except ImportError:
    # Stub for testing - tests will mock this
    async def spawn(**kwargs):  # type: ignore
        """Stub spawn function for testing."""
        raise NotImplementedError("agentica not installed - use mocking in tests")


if TYPE_CHECKING:
    from scripts.agentica_patterns.coordination import CoordinationDB


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, using primary
    OPEN = "open"          # Failure threshold reached, using fallback
    HALF_OPEN = "half_open"  # Testing if primary has recovered


class CircuitBreaker:
    """
    CircuitBreaker pattern: Failure detection with fallback routing.

    Wraps agent execution with failure detection. After N consecutive
    failures, the circuit "opens" and routes to a fallback agent. After
    a timeout, the circuit enters "half-open" state and tests the primary
    agent again.

    States:
    - CLOSED: Normal operation, primary agent is used
    - OPEN: Primary has failed too many times, fallback is used
    - HALF_OPEN: Testing primary after timeout, one failure reopens

    Example:
        cb = CircuitBreaker(
            primary_premise="You implement features.",
            fallback_premise="You implement simpler versions.",
            max_failures=3,
            reset_timeout=60
        )
        result = await cb.execute("Implement OAuth flow")
    """

    def __init__(
        self,
        primary_premise: str,
        fallback_premise: str,
        max_failures: int = 3,
        reset_timeout: float = 60,
        primary_model: str | None = None,
        fallback_model: str | None = None,
        primary_scope: dict[str, Any] | None = None,
        fallback_scope: dict[str, Any] | None = None,
        return_type: type = str,
        db: Optional["CoordinationDB"] = None
    ):
        """
        Initialize CircuitBreaker.

        Args:
            primary_premise: Premise for primary agent
            fallback_premise: Premise for fallback agent
            max_failures: Consecutive failures before opening circuit
            reset_timeout: Seconds before trying primary again
            primary_model: Model for primary agent
            fallback_model: Model for fallback agent
            primary_scope: Tools for primary agent
            fallback_scope: Tools for fallback agent
            return_type: Expected return type for agent calls
            db: Optional coordination database for tracking agents
        """
        self.primary_premise = primary_premise
        self.fallback_premise = fallback_premise
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.primary_scope = primary_scope or {}
        self.fallback_scope = fallback_scope or {}
        self.return_type = return_type
        self.db = db

        # Circuit state
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None

        # Lock for thread-safe state mutations
        self._state_lock = asyncio.Lock()

        # Unique circuit breaker ID for hook correlation
        self.cb_id = str(uuid4())

        # Agents spawned lazily
        self.primary_agent = None
        self.fallback_agent = None

    async def _ensure_primary(self):
        """Lazy spawn primary agent with circuit breaker env vars."""
        if self.primary_agent is None:
            spawn_kwargs = {"premise": self.primary_premise}
            if self.primary_scope:
                spawn_kwargs["scope"] = self.primary_scope
            if self.primary_model:
                spawn_kwargs["model"] = self.primary_model

            # Set environment variables for hook detection
            env_vars = {
                "PATTERN_TYPE": "circuit_breaker",
                "PATTERN_ID": self.cb_id,
                "CB_ID": self.cb_id,
                "AGENT_ROLE": "primary",
                "CIRCUIT_STATE": self.state.value
            }

            # Merge with existing environment
            spawn_env = os.environ.copy()
            spawn_env.update(env_vars)

            if self.db:
                from scripts.agentica_patterns.tracked_agent import tracked_spawn
                self.primary_agent = await tracked_spawn(
                    db=self.db, pattern="circuit_breaker", env=spawn_env, **spawn_kwargs
                )
            else:
                self.primary_agent = await spawn(env=spawn_env, **spawn_kwargs)

    async def _ensure_fallback(self):
        """Lazy spawn fallback agent with circuit breaker env vars."""
        if self.fallback_agent is None:
            spawn_kwargs = {"premise": self.fallback_premise}
            if self.fallback_scope:
                spawn_kwargs["scope"] = self.fallback_scope
            if self.fallback_model:
                spawn_kwargs["model"] = self.fallback_model

            # Set environment variables for hook detection
            env_vars = {
                "PATTERN_TYPE": "circuit_breaker",
                "PATTERN_ID": self.cb_id,
                "CB_ID": self.cb_id,
                "AGENT_ROLE": "fallback",
                "CIRCUIT_STATE": self.state.value
            }

            # Merge with existing environment
            spawn_env = os.environ.copy()
            spawn_env.update(env_vars)

            if self.db:
                from scripts.agentica_patterns.tracked_agent import tracked_spawn
                self.fallback_agent = await tracked_spawn(
                    db=self.db, pattern="circuit_breaker", env=spawn_env, **spawn_kwargs
                )
            else:
                self.fallback_agent = await spawn(env=spawn_env, **spawn_kwargs)

    def _should_try_primary(self) -> bool:
        """Check if we should attempt primary agent."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self.last_failure_time is not None:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.reset_timeout:
                    self.state = CircuitState.HALF_OPEN
                    return True
            return False

        # HALF_OPEN: try primary
        return True

    async def _record_success(self):
        """Record successful primary execution."""
        async with self._state_lock:
            self.failure_count = 0
            self.state = CircuitState.CLOSED
            self.last_failure_time = None

    async def _record_failure(self):
        """Record failed primary execution."""
        async with self._state_lock:
            # Cap failure_count at max_failures to maintain consistent state
            if self.failure_count < self.max_failures:
                self.failure_count += 1
            self.last_failure_time = time.time()

            # Open circuit if max failures reached OR if we're testing (half-open)
            if (
                self.failure_count >= self.max_failures
                or self.state == CircuitState.HALF_OPEN
            ):
                self.state = CircuitState.OPEN

    async def execute(self, query: str) -> Any:
        """
        Execute query with circuit breaker protection.

        Args:
            query: Query/task for the agent

        Returns:
            Result from primary or fallback agent
        """
        await self._ensure_primary()
        await self._ensure_fallback()

        if self._should_try_primary():
            try:
                result = await self.primary_agent.call(self.return_type, query)
                await self._record_success()
                return result
            except Exception:
                await self._record_failure()
                # Always use fallback on failure (graceful degradation)
                return await self.fallback_agent.call(self.return_type, query)

        # Circuit is OPEN, use fallback
        return await self.fallback_agent.call(self.return_type, query)

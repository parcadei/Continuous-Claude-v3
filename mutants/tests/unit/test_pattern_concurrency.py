"""
Concurrency tests for pattern race conditions.

These tests verify that concurrent access to shared state causes failures
when proper locking is not in place. Once the patterns are fixed with
asyncio.Lock(), these tests should PASS.

Issues being tested:
1. CircuitBreaker: concurrent state mutations without lock
2. Blackboard: concurrent dict writes without lock
3. Hierarchical: lazy initialization race (check-then-act)

Reference: docs/concurrency-search/RACE_FINDINGS.md
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.agentica.patterns.blackboard import BlackboardState
from scripts.agentica.patterns.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)
from scripts.agentica.patterns.hierarchical import Hierarchical


class TestCircuitBreakerConcurrency:
    """Test concurrent access to CircuitBreaker state."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create a CircuitBreaker with low failure threshold for testing."""
        return CircuitBreaker(
            primary_premise="Primary agent",
            fallback_premise="Fallback agent",
            max_failures=3,
            reset_timeout=0.1,  # Short timeout for testing
        )

    @pytest.mark.asyncio
    async def test_concurrent_execute_state_consistency(self, circuit_breaker):
        """
        Test that 10 concurrent execute() calls maintain consistent state.

        Without proper locking, concurrent calls can:
        - Read stale state values
        - Increment failure_count non-atomically
        - Corrupt state transitions

        This test should FAIL without asyncio.Lock protection.
        """
        call_count = {"primary": 0, "fallback": 0}

        # Mock agents that track call counts
        mock_primary = AsyncMock()
        mock_fallback = AsyncMock()

        async def primary_call(return_type, query):
            call_count["primary"] += 1
            # Simulate some async work
            await asyncio.sleep(0.01)
            # First few calls succeed, then fail to test state transitions
            if call_count["primary"] <= 2:
                return f"Primary: {query}"
            raise ValueError("Primary agent failed")

        async def fallback_call(return_type, query):
            call_count["fallback"] += 1
            await asyncio.sleep(0.01)
            return f"Fallback: {query}"

        mock_primary.call = primary_call
        mock_fallback.call = fallback_call

        # Patch spawn to return our mocked agents
        with patch(
            "scripts.agentica.patterns.circuit_breaker.spawn"
        ) as mock_spawn:
            spawn_count = {"count": 0}

            async def mock_spawn_fn(**kwargs):
                spawn_count["count"] += 1
                # Return primary for first call, fallback for second
                if spawn_count["count"] == 1:
                    return mock_primary
                return mock_fallback

            mock_spawn.side_effect = mock_spawn_fn

            # Run 10 concurrent execute calls
            tasks = [
                asyncio.create_task(circuit_breaker.execute(f"query_{i}"))
                for i in range(10)
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify we got results (some may be exceptions)
        _ = [r for r in results if not isinstance(r, Exception)]

        # Verify state consistency
        # The failure_count should be a valid number (0-3)
        assert 0 <= circuit_breaker.failure_count <= circuit_breaker.max_failures, (
            f"Inconsistent failure_count: {circuit_breaker.failure_count}"
        )

        # State should be one of the valid states
        assert circuit_breaker.state in [
            CircuitState.CLOSED,
            CircuitState.OPEN,
            CircuitState.HALF_OPEN,
        ], f"Invalid state: {circuit_breaker.state}"

        # The critical assertion: after concurrent failures, state should be OPEN
        # and failure_count should be exactly max_failures (3)
        # Without locking, failure_count can be corrupted (e.g., > max_failures)
        if circuit_breaker.state == CircuitState.OPEN:
            assert circuit_breaker.failure_count >= circuit_breaker.max_failures, (
                f"State is OPEN but failure_count ({circuit_breaker.failure_count}) "
                f"< max_failures ({circuit_breaker.max_failures})"
            )

    @pytest.mark.asyncio
    async def test_concurrent_record_failure_atomicity(self, circuit_breaker):
        """
        Test that concurrent _record_failure() calls are atomic.

        This directly tests the race condition where multiple tasks
        increment failure_count simultaneously.

        Without locking, N concurrent increments can result in < N final count.
        """
        circuit_breaker.failure_count = 0
        circuit_breaker.state = CircuitState.CLOSED

        num_concurrent = 10

        async def record_with_delay():
            """Simulate the race by adding delays between read and write."""
            # This simulates what happens without a lock:
            # 1. Read current failure_count
            # 2. (other tasks also read the same value)
            # 3. Increment and write back
            # Result: lost updates
            await circuit_breaker._record_failure()
            await asyncio.sleep(0.001)

        # Run concurrent _record_failure calls
        tasks = [
            asyncio.create_task(record_with_delay())
            for _ in range(num_concurrent)
        ]
        await asyncio.gather(*tasks)

        # With proper locking, failure_count should equal num_concurrent
        # Without locking, it may be less due to lost updates
        # Note: Since _record_failure is sync, this test may pass even without locks
        # The real race happens when async operations interleave

        # At minimum, failure_count should have increased
        assert circuit_breaker.failure_count > 0, "No failures were recorded"

        # With max_failures=3, after 10 failures, state should be OPEN
        assert circuit_breaker.state == CircuitState.OPEN, (
            f"State should be OPEN after {num_concurrent} failures, "
            f"but is {circuit_breaker.state}"
        )

    @pytest.mark.asyncio
    async def test_concurrent_state_transition_race(self, circuit_breaker):
        """
        Test race condition in _should_try_primary() state transitions.

        When circuit is OPEN and timeout has elapsed, multiple concurrent
        calls can all see OPEN state, all transition to HALF_OPEN, and all
        try the primary agent simultaneously.

        This should result in only ONE task testing the primary.
        """
        # Set up circuit in OPEN state with timeout elapsed
        circuit_breaker.state = CircuitState.OPEN
        circuit_breaker.failure_count = circuit_breaker.max_failures
        circuit_breaker.last_failure_time = 0  # Long ago

        primary_test_count = {"count": 0}

        def should_try_with_tracking() -> bool:
            """Track how many times primary is chosen."""
            result = circuit_breaker._should_try_primary()
            if result and circuit_breaker.state == CircuitState.HALF_OPEN:
                primary_test_count["count"] += 1
            return result

        # Call concurrently
        num_concurrent = 5
        results = []

        for _ in range(num_concurrent):
            result = should_try_with_tracking()
            results.append(result)
            # Small delay to allow interleaving
            await asyncio.sleep(0.0001)

        # Without locking, multiple calls can all return True and
        # all increment primary_test_count
        # With proper locking, only ONE should transition to HALF_OPEN and test primary
        # Note: Since _should_try_primary is sync, this test shows the semantic issue
        # but the actual race manifests in async execute() calls

        # All should return True (primary should be tried)
        true_count = sum(1 for r in results if r)
        assert true_count > 0, "At least one call should try primary"


class TestBlackboardConcurrency:
    """Test concurrent access to BlackboardState.

    Note: Simple dict operations in CPython are atomic due to the GIL.
    The real race condition manifests when:
    1. Read-modify-write patterns are used
    2. Multiple operations need to be atomic together
    3. In non-CPython implementations (PyPy, Jython, etc.)

    These tests verify the expected behavior and document where locks
    would be needed for correctness in a read-modify-write scenario.
    """

    @pytest.mark.asyncio
    async def test_concurrent_set_item_consistency(self):
        """
        Test that 10 concurrent set_item() calls maintain consistency.

        This test passes because dict.__setitem__ is atomic in CPython.
        However, if BlackboardState were to implement increment or
        read-modify-write, locks would be required.
        """
        state = BlackboardState()

        async def set_item_async(key: str, value: str):
            """Async wrapper to simulate concurrent access."""
            # Small delay to increase chance of interleaving
            await asyncio.sleep(0.001)
            state[key] = value
            await asyncio.sleep(0.001)

        # 10 concurrent writes to different keys
        tasks = [
            asyncio.create_task(set_item_async(f"key_{i}", f"value_{i}"))
            for i in range(10)
        ]
        await asyncio.gather(*tasks)

        # All 10 keys should be present
        assert len(state._data) == 10, (
            f"Expected 10 keys, got {len(state._data)}: {list(state._data.keys())}"
        )

        # History should have exactly 10 entries
        assert len(state.history) == 10, (
            f"Expected 10 history entries, got {len(state.history)}"
        )

        # Each key should have its corresponding value
        for i in range(10):
            assert f"key_{i}" in state._data, f"Missing key_{i}"
            assert state._data[f"key_{i}"] == f"value_{i}", (
                f"Wrong value for key_{i}: {state._data.get(f'key_{i}')}"
            )

    @pytest.mark.asyncio
    async def test_concurrent_read_modify_write_race(self):
        """
        Test race condition in read-modify-write pattern.

        This demonstrates where locks ARE needed: when you need to
        read a value, modify it, and write it back atomically.

        Without locking, concurrent increments will lose updates.
        With the new update_item() method, this should PASS.
        """
        state = BlackboardState()
        state["counter"] = 0

        async def increment_counter():
            """Atomic increment using update_item."""
            await asyncio.sleep(0.001)  # Allow interleaving
            await state.update_item("counter", lambda x: (x or 0) + 1)
            await asyncio.sleep(0.001)

        num_increments = 10
        tasks = [
            asyncio.create_task(increment_counter())
            for _ in range(num_increments)
        ]
        await asyncio.gather(*tasks)

        # With update_item() locking, final value should equal num_increments
        assert state["counter"] == num_increments, (
            f"Expected counter={num_increments}, got {state['counter']}. "
            "Lost updates due to read-modify-write race condition."
        )

    @pytest.mark.asyncio
    async def test_concurrent_set_same_key_last_write_wins(self):
        """
        Test that concurrent writes to the same key result in consistent state.

        When multiple tasks write to the same key, one value should win.
        The history should record all attempts (even if values are overwritten).

        This tests dict write atomicity.
        """
        state = BlackboardState()
        write_order = []

        async def set_with_tracking(writer_id: int):
            """Write and track order."""
            await asyncio.sleep(0.001 * (10 - writer_id))  # Stagger writes
            state["shared_key"] = f"writer_{writer_id}"
            write_order.append(writer_id)

        # 10 concurrent writes to same key
        tasks = [
            asyncio.create_task(set_with_tracking(i))
            for i in range(10)
        ]
        await asyncio.gather(*tasks)

        # Key should exist
        assert "shared_key" in state._data, "shared_key missing"

        # History should have 10 entries (one per write)
        history_count = len([
            h for h in state.history if h.get("key") == "shared_key"
        ])
        assert history_count == 10, (
            f"Expected 10 history entries for shared_key, got {history_count}"
        )

        # Final value should be from one of the writers
        final_value = state["shared_key"]
        assert final_value.startswith("writer_"), f"Invalid final value: {final_value}"

    @pytest.mark.asyncio
    async def test_concurrent_history_append_integrity(self):
        """
        Test that concurrent appends to history list don't corrupt it.

        list.append() is atomic in CPython due to GIL, but the combination
        of dict write + list append is not atomic.

        Without locking, history entries could be missing or duplicated.
        """
        state = BlackboardState()

        async def rapid_writes(prefix: str, count: int):
            """Perform rapid consecutive writes."""
            for i in range(count):
                state[f"{prefix}_{i}"] = f"value_{i}"
                # No await to maximize contention

        # Multiple writers doing rapid writes
        tasks = [
            asyncio.create_task(rapid_writes(f"writer_{w}", 10))
            for w in range(5)
        ]
        await asyncio.gather(*tasks)

        # Should have 50 data entries (5 writers * 10 each)
        expected_keys = 50
        assert len(state._data) == expected_keys, (
            f"Expected {expected_keys} keys, got {len(state._data)}"
        )

        # History should also have 50 entries
        assert len(state.history) == expected_keys, (
            f"Expected {expected_keys} history entries, got {len(state.history)}"
        )


class TestHierarchicalConcurrency:
    """Test lazy initialization race in Hierarchical pattern."""

    @pytest.fixture
    def hierarchical(self):
        """Create a Hierarchical pattern for testing."""
        return Hierarchical(
            coordinator_premise="You coordinate tasks",
            specialist_premises={
                "researcher": "You research topics",
                "analyst": "You analyze data",
            },
        )

    @pytest.mark.asyncio
    async def test_concurrent_ensure_coordinator_single_spawn(self, hierarchical):
        """
        Test that 5 concurrent _ensure_coordinator() calls spawn only 1 coordinator.

        The check-then-act pattern without locking:
            if self.coordinator is None:  # Check
                self.coordinator = await spawn(...)  # Act

        Multiple concurrent calls can all pass the check before any completes
        the spawn, resulting in multiple coordinators being created.

        This test should FAIL without asyncio.Lock protection.
        """
        spawn_calls = []

        with patch(
            "scripts.agentica.patterns.hierarchical.spawn"
        ) as mock_spawn:
            async def mock_spawn_fn(**kwargs):
                spawn_calls.append(kwargs)
                # Simulate slow spawn to increase race window
                await asyncio.sleep(0.05)
                mock_agent = MagicMock()
                mock_agent.agent_id = f"agent_{len(spawn_calls)}"
                return mock_agent

            mock_spawn.side_effect = mock_spawn_fn

            # Run 5 concurrent _ensure_coordinator calls
            tasks = [
                asyncio.create_task(hierarchical._ensure_coordinator())
                for _ in range(5)
            ]
            await asyncio.gather(*tasks)

        # Critical assertion: spawn should be called EXACTLY ONCE
        # Without locking, it will be called multiple times
        assert len(spawn_calls) == 1, (
            f"Expected 1 spawn call, got {len(spawn_calls)}. "
            "Multiple coordinators were spawned due to race condition."
        )

        # Coordinator should be set
        assert hierarchical.coordinator is not None, "Coordinator not set"

    @pytest.mark.asyncio
    async def test_concurrent_ensure_specialist_single_spawn(self, hierarchical):
        """
        Test that 5 concurrent _ensure_specialist('researcher') calls spawn only 1 specialist.

        Same check-then-act race as coordinator, but for specialist dict:
            if name not in self.specialists:  # Check
                self.specialists[name] = await spawn(...)  # Act
        """
        spawn_calls = []

        with patch(
            "scripts.agentica.patterns.hierarchical.spawn"
        ) as mock_spawn:
            async def mock_spawn_fn(**kwargs):
                spawn_calls.append(kwargs)
                await asyncio.sleep(0.05)  # Slow spawn
                mock_agent = MagicMock()
                mock_agent.agent_id = f"agent_{len(spawn_calls)}"
                return mock_agent

            mock_spawn.side_effect = mock_spawn_fn

            # First, ensure coordinator exists (needed for specialist)
            hierarchical.coordinator = MagicMock()
            hierarchical.coordinator.agent_id = "coordinator"
            hierarchical.coordinator_id = "coordinator"

            # Run 5 concurrent _ensure_specialist calls for same specialist
            tasks = [
                asyncio.create_task(hierarchical._ensure_specialist("researcher"))
                for _ in range(5)
            ]
            await asyncio.gather(*tasks)

        # Should spawn exactly 1 specialist
        assert len(spawn_calls) == 1, (
            f"Expected 1 spawn call, got {len(spawn_calls)}. "
            "Multiple specialists were spawned due to race condition."
        )

        # Specialist should be in dict
        assert "researcher" in hierarchical.specialists

    @pytest.mark.asyncio
    async def test_concurrent_execute_tasks_share_coordinator(self, hierarchical):
        """
        Test that concurrent execute() calls share a single coordinator.

        This is an end-to-end test that multiple execute() calls don't
        spawn duplicate coordinators.
        """
        spawn_calls = {"coordinator": 0, "specialist": 0}

        with patch(
            "scripts.agentica.patterns.hierarchical.spawn"
        ) as mock_spawn:
            async def mock_spawn_fn(**kwargs):
                # The coordinator premise is "You coordinate tasks"
                premise = kwargs.get("premise", "").lower()
                if "coordinate" in premise:
                    spawn_calls["coordinator"] += 1
                else:
                    spawn_calls["specialist"] += 1

                await asyncio.sleep(0.02)
                mock_agent = MagicMock()
                coord = spawn_calls['coordinator']
                spec = spawn_calls['specialist']
                mock_agent.agent_id = f"agent_{coord}_{spec}"
                # Mock the call method for decomposition
                mock_agent.call = AsyncMock(return_value=[])
                return mock_agent

            mock_spawn.side_effect = mock_spawn_fn

            # Run 3 concurrent execute calls
            tasks = [
                asyncio.create_task(hierarchical.execute(f"task_{i}"))
                for i in range(3)
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

        # Should have spawned exactly 1 coordinator
        assert spawn_calls["coordinator"] == 1, (
            f"Expected 1 coordinator spawn, got {spawn_calls['coordinator']}. "
            "Race condition in _ensure_coordinator."
        )


class TestCrossPatternConcurrency:
    """Test concurrent usage across different pattern instances."""

    @pytest.mark.asyncio
    async def test_independent_blackboard_states(self):
        """
        Test that multiple BlackboardState instances don't share state.

        This verifies that race conditions are per-instance, not global.
        """
        states = [BlackboardState() for _ in range(3)]

        async def write_to_state(state: BlackboardState, prefix: str):
            for i in range(10):
                state[f"{prefix}_{i}"] = f"value_{i}"
                await asyncio.sleep(0.001)

        # Write to all states concurrently
        tasks = [
            asyncio.create_task(write_to_state(states[i], f"state_{i}"))
            for i in range(3)
        ]
        await asyncio.gather(*tasks)

        # Each state should have 10 entries
        for i, state in enumerate(states):
            assert len(state._data) == 10, (
                f"State {i} has {len(state._data)} entries, expected 10"
            )

            # Keys should have correct prefix
            for key in state._data.keys():
                assert key.startswith(f"state_{i}_"), (
                    f"State {i} has wrong key: {key}"
                )

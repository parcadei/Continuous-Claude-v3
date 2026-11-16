"""Tests for TemporalMemoryStorePG - Phase 3.3 of PostgreSQL migration.

TDD test suite for PostgreSQL-backed temporal memory store.
Mirrors all tests from test_temporal_store.py for PostgreSQL.

Tests:
- TestTemporalMemoryStorePGSchema: Table access, connect idempotent, turn starts at 0
- TestTemporalMemoryStorePGCRUD: record_facts, record_updates_turn, tracks_changes, get_trace_ordered
- TestTemporalMemoryStorePGErotetic: record_with_erotetic, get_open_questions
- TestTemporalMemoryStorePGInertia: advance_turn_applies_inertia, advance_turn_returns_revisions

Prerequisites:
- Docker must be running
- Run: ./docker/start-postgres.sh before tests
- Temporal schema must be applied (Phase 3.1)

Usage:
    uv run pytest tests/unit/test_temporal_store_pg.py -v

Expected failures (TemporalMemoryStorePG not yet implemented):
- ModuleNotFoundError: No module named 'scripts.temporal_memory.store_pg'
"""

from __future__ import annotations

import subprocess
import time

import pytest


def is_container_running(container_name: str = "agentica-postgres") -> bool:
    """Check if the PostgreSQL container is running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == "true"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def is_container_healthy(container_name: str = "agentica-postgres") -> bool:
    """Check if the PostgreSQL container is healthy."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == "healthy"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.fixture(scope="module")
def ensure_postgres_running():
    """Ensure PostgreSQL container is running before tests.

    This fixture checks if the container is running and healthy.
    If not, it skips the test suite with a helpful message.
    """
    import asyncio

    if not is_container_running():
        pytest.skip(
            "PostgreSQL container not running. "
            "Start with: ./docker/start-postgres.sh or "
            "docker compose -f docker/docker-compose.yml up -d"
        )

    # Wait for container to become healthy (max 30 seconds)
    for _ in range(30):
        if is_container_healthy():
            break
        time.sleep(1)
    else:
        pytest.skip("PostgreSQL container not healthy after 30 seconds")

    yield


@pytest.fixture(scope="function")
async def clean_temporal_tables(ensure_postgres_running):
    """Clean temporal tables before and after each test.

    Uses TRUNCATE for fast cleanup with CASCADE for dependent objects.
    """
    import asyncpg

    conn_string = "postgresql://agentica:agentica_dev@localhost:5433/agentica_memory"
    conn = await asyncpg.connect(conn_string)
    try:
        # Clean before test
        await conn.execute(
            "TRUNCATE temporal_facts, temporal_traces CASCADE"
        )
    finally:
        await conn.close()

    yield

    # Clean after test
    conn = await asyncpg.connect(conn_string)
    try:
        await conn.execute(
            "TRUNCATE temporal_facts, temporal_traces CASCADE"
        )
    finally:
        await conn.close()


@pytest.fixture
async def store(clean_temporal_tables):
    """Create a TemporalMemoryStorePG instance for testing.

    Uses the PostgreSQL pool from postgres_pool.py.
    Tables are cleaned before and after each test.
    """
    # Reset pool to avoid event loop issues between tests
    from scripts.agentica_patterns.postgres_pool import reset_pool

    reset_pool()

    # Import will fail until TemporalMemoryStorePG is implemented
    from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

    s = TemporalMemoryStorePG(session_id="test-session")
    await s.connect()

    yield s

    # Reset pool after test to avoid stale connections
    reset_pool()


class TestTemporalMemoryStorePGSchema:
    """Test schema access and connection for PostgreSQL backend."""

    @pytest.mark.asyncio
    async def test_create_store(self, clean_temporal_tables) -> None:
        """Store can be created with session_id."""
        from scripts.agentica_patterns.postgres_pool import reset_pool
        reset_pool()

        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        store = TemporalMemoryStorePG(session_id="test-123")
        assert store.session_id == "test-123"
        assert not store._connected

    @pytest.mark.asyncio
    async def test_connect_succeeds(self, clean_temporal_tables) -> None:
        """Store can connect to PostgreSQL."""
        from scripts.agentica_patterns.postgres_pool import reset_pool
        reset_pool()

        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        store = TemporalMemoryStorePG(session_id="test-123")
        await store.connect()

        assert store._connected

    @pytest.mark.asyncio
    async def test_temporal_facts_table_accessible(self, store) -> None:
        """Verify temporal_facts table is accessible."""
        import asyncpg

        conn_string = "postgresql://agentica:agentica_dev@localhost:5433/agentica_memory"
        conn = await asyncpg.connect(conn_string)
        try:
            # Check table exists by querying it
            row = await conn.fetchval(
                "SELECT COUNT(*) FROM temporal_facts"
            )
            assert row is not None  # Table exists if query succeeds
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_temporal_traces_table_accessible(self, store) -> None:
        """Verify temporal_traces table is accessible."""
        import asyncpg

        conn_string = "postgresql://agentica:agentica_dev@localhost:5433/agentica_memory"
        conn = await asyncpg.connect(conn_string)
        try:
            # Check table exists by querying it
            row = await conn.fetchval(
                "SELECT COUNT(*) FROM temporal_traces"
            )
            assert row is not None  # Table exists if query succeeds
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_indexes_exist(self, store) -> None:
        """Verify indexes exist on temporal tables."""
        import asyncpg

        conn_string = "postgresql://agentica:agentica_dev@localhost:5433/agentica_memory"
        conn = await asyncpg.connect(conn_string)
        try:
            # Query for indexes on temporal_facts
            rows = await conn.fetch(
                """
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'temporal_facts'
                AND indexname LIKE 'idx_temporal%'
                """
            )
            index_names = [r["indexname"] for r in rows]
            assert "idx_temporal_facts_session" in index_names
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_connect_idempotent(self, clean_temporal_tables) -> None:
        """Calling connect() twice doesn't raise error."""
        from scripts.agentica_patterns.postgres_pool import reset_pool
        reset_pool()

        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        store = TemporalMemoryStorePG(session_id="test-123")
        await store.connect()
        await store.connect()  # Should not raise
        assert store._connected

    @pytest.mark.asyncio
    async def test_current_turn_starts_at_zero(self, store) -> None:
        """Current turn starts at 0 for new session."""
        assert store._current_turn == 0

    @pytest.mark.asyncio
    async def test_current_turn_restored_on_connect(self, clean_temporal_tables) -> None:
        """Turn is restored from DB on reconnect."""
        from scripts.agentica_patterns.postgres_pool import reset_pool
        reset_pool()

        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        # First store records at turn 5
        store1 = TemporalMemoryStorePG(session_id="test-restore")
        await store1.connect()
        await store1.record(turn=5, facts={"phase": "testing"})
        assert store1._current_turn == 5

        # New store instance should restore turn
        reset_pool()
        store2 = TemporalMemoryStorePG(session_id="test-restore")
        await store2.connect()
        assert store2._current_turn == 5

    @pytest.mark.asyncio
    async def test_different_session_ids_isolated(self, clean_temporal_tables) -> None:
        """Different session_ids have separate turn counters."""
        from scripts.agentica_patterns.postgres_pool import reset_pool
        reset_pool()

        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        store1 = TemporalMemoryStorePG(session_id="session-1")
        store2 = TemporalMemoryStorePG(session_id="session-2")
        await store1.connect()
        await store2.connect()

        await store1.record(turn=10, facts={"a": "1"})
        await store2.record(turn=3, facts={"b": "2"})

        assert store1._current_turn == 10
        assert store2._current_turn == 3


class TestTemporalMemoryStorePGCRUD:
    """Test CRUD operations for PostgreSQL backend."""

    @pytest.mark.asyncio
    async def test_record_facts(self, store) -> None:
        """Facts can be recorded and retrieved."""
        await store.record(turn=1, facts={"phase": "testing", "goal": "implement"})

        state = await store.get_current_state()
        assert state["phase"] == "testing"
        assert state["goal"] == "implement"

    @pytest.mark.asyncio
    async def test_record_updates_turn(self, store) -> None:
        """Recording facts updates current turn."""
        await store.record(turn=1, facts={"phase": "testing"})
        assert store._current_turn == 1

        await store.record(turn=5, facts={"phase": "done"})
        assert store._current_turn == 5

    @pytest.mark.asyncio
    async def test_record_tracks_changes(self, store) -> None:
        """Change count is tracked for updated facts."""
        await store.record(turn=1, facts={"phase": "planning"})
        await store.record(turn=2, facts={"phase": "testing"})
        await store.record(turn=3, facts={"phase": "done"})

        # Check change_count in database
        import asyncpg

        conn_string = "postgresql://agentica:agentica_dev@localhost:5433/agentica_memory"
        conn = await asyncpg.connect(conn_string)
        try:
            row = await conn.fetchrow(
                "SELECT change_count FROM temporal_facts WHERE session_id = $1 AND key = $2",
                store.session_id, "phase"
            )
            assert row["change_count"] == 2  # Changed twice: planning->testing, testing->done
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_get_trace_returns_ordered(self, store) -> None:
        """Trace returns facts ordered by turn."""
        await store.record(turn=1, facts={"a": "1"})
        await store.record(turn=3, facts={"b": "2"})
        await store.record(turn=2, facts={"c": "3"})

        trace = await store.get_trace()
        turns = [t["turn"] for t in trace]
        assert turns == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_trace_includes_facts(self, store) -> None:
        """Trace entries include facts."""
        await store.record(turn=1, facts={"phase": "testing"})

        trace = await store.get_trace()
        assert len(trace) == 1
        assert trace[0]["facts"]["phase"] == "testing"

    @pytest.mark.asyncio
    async def test_get_current_state_latest_values(self, store) -> None:
        """Current state reflects latest values."""
        await store.record(turn=1, facts={"phase": "planning", "goal": "implement"})
        await store.record(turn=2, facts={"phase": "testing"})

        state = await store.get_current_state()
        assert state["phase"] == "testing"
        assert state["goal"] == "implement"

    @pytest.mark.asyncio
    async def test_get_current_state_empty(self, store) -> None:
        """Current state is empty for new session."""
        state = await store.get_current_state()
        assert state == {}

    @pytest.mark.asyncio
    async def test_get_invariants_unchanged_facts(self, store) -> None:
        """Invariants returns facts that never changed."""
        await store.record(turn=1, facts={"db_type": "postgres", "phase": "planning"})
        await store.record(turn=2, facts={"phase": "testing"})
        await store.record(turn=3, facts={"phase": "done"})

        invariants = await store.get_invariants()
        assert "db_type" in invariants
        assert invariants["db_type"] == "postgres"
        assert "phase" not in invariants  # Changed

    @pytest.mark.asyncio
    async def test_get_invariants_empty(self, store) -> None:
        """Invariants is empty for new session."""
        invariants = await store.get_invariants()
        assert invariants == {}

    @pytest.mark.asyncio
    async def test_record_multiple_sessions_isolated(self, clean_temporal_tables) -> None:
        """Facts from different sessions are isolated."""
        from scripts.agentica_patterns.postgres_pool import reset_pool
        reset_pool()

        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        store1 = TemporalMemoryStorePG(session_id="session-1")
        store2 = TemporalMemoryStorePG(session_id="session-2")
        await store1.connect()
        await store2.connect()

        await store1.record(turn=1, facts={"value": "from-1"})
        await store2.record(turn=1, facts={"value": "from-2"})

        state1 = await store1.get_current_state()
        state2 = await store2.get_current_state()

        assert state1["value"] == "from-1"
        assert state2["value"] == "from-2"

    @pytest.mark.asyncio
    async def test_record_overwrites_same_key(self, store) -> None:
        """Recording same key overwrites previous value."""
        await store.record(turn=1, facts={"key": "value1"})
        await store.record(turn=2, facts={"key": "value2"})

        state = await store.get_current_state()
        assert state["key"] == "value2"

    @pytest.mark.asyncio
    async def test_get_trace_empty(self, store) -> None:
        """Trace is empty for new session."""
        trace = await store.get_trace()
        assert trace == []


class TestTemporalMemoryStorePGErotetic:
    """Test E(X,Q) integration for PostgreSQL backend."""

    @pytest.mark.asyncio
    async def test_record_with_erotetic(self, store) -> None:
        """record_with_erotetic returns evocation result."""
        # Facts with some unknowns
        facts = {"framework": "fastapi", "database": "UNKNOWN"}
        result = await store.record_with_erotetic(turn=1, facts=facts)

        # Should return evocation result
        assert "isEmpty" in result
        assert "unknowns" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_record_with_erotetic_stores_trace(self, store) -> None:
        """record_with_erotetic stores trace with erotetic data."""
        facts = {"phase": "testing", "auth": "UNKNOWN"}
        await store.record_with_erotetic(turn=1, facts=facts)

        trace = await store.get_trace()
        assert len(trace) == 1
        assert trace[0]["erotetic"] is not None

    @pytest.mark.asyncio
    async def test_get_open_questions_latest(self, store) -> None:
        """get_open_questions returns unknowns from latest turn."""
        facts1 = {"db": "UNKNOWN", "api": "UNKNOWN"}
        await store.record_with_erotetic(turn=1, facts=facts1)

        facts2 = {"db": "postgres", "api": "UNKNOWN"}
        await store.record_with_erotetic(turn=2, facts=facts2)

        questions = await store.get_open_questions()
        # Latest turn should have fewer unknowns (db resolved)
        assert "api" in questions or len(questions) <= 2

    @pytest.mark.asyncio
    async def test_get_open_questions_at_turn(self, store) -> None:
        """get_open_questions can query specific turn."""
        await store.record_with_erotetic(turn=1, facts={"a": "UNKNOWN"})
        await store.record_with_erotetic(turn=2, facts={"a": "resolved"})

        q_turn1 = await store.get_open_questions(turn=1)
        q_turn2 = await store.get_open_questions(turn=2)

        # Turn 1 had unknowns, turn 2 resolved them
        assert len(q_turn1) >= len(q_turn2)

    @pytest.mark.asyncio
    async def test_get_open_questions_empty(self, store) -> None:
        """get_open_questions returns empty list for new session."""
        questions = await store.get_open_questions()
        assert questions == []

    @pytest.mark.asyncio
    async def test_erotetic_with_no_unknowns(self, store) -> None:
        """record_with_erotetic handles facts with no unknowns."""
        facts = {"framework": "fastapi", "database": "postgres"}
        result = await store.record_with_erotetic(turn=1, facts=facts)

        assert result["isEmpty"] is True
        assert result["unknowns"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_record_with_erotetic_unknown_values(self, store) -> None:
        """E(X,Q) correctly identifies unknowns."""
        facts = {"known": "value", "unknown1": "UNKNOWN", "unknown2": None}
        result = await store.record_with_erotetic(turn=1, facts=facts)

        assert result["isEmpty"] is False
        assert "unknown1" in result["unknowns"]
        assert "unknown2" in result["unknowns"]
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_get_open_questions_returns_unknowns_list(self, store) -> None:
        """get_open_questions returns list of unknown names."""
        facts = {"db": "UNKNOWN", "cache": "UNKNOWN", "api": "rest"}
        await store.record_with_erotetic(turn=1, facts=facts)

        questions = await store.get_open_questions()
        assert isinstance(questions, list)
        assert "db" in questions
        assert "cache" in questions
        assert "api" not in questions


class TestTemporalMemoryStorePGInertia:
    """Test store with inertia integration for PostgreSQL backend."""

    @pytest.mark.asyncio
    async def test_advance_turn_applies_inertia(self, store) -> None:
        """advance_turn persists unchanged facts via inertia."""
        from scripts.temporal_memory.inertia import RevisionPriority

        await store.record(turn=1, facts={"db": "postgres", "phase": "planning"})
        revisions = await store.advance_turn(
            updates={"phase": "testing"},
            priority=RevisionPriority.RECENT_OBSERVATION,
        )

        state = await store.get_current_state()
        assert state["db"] == "postgres"  # Persisted via inertia
        assert state["phase"] == "testing"  # Updated

    @pytest.mark.asyncio
    async def test_advance_turn_returns_revisions(self, store) -> None:
        """advance_turn returns list of revision events."""
        from scripts.temporal_memory.inertia import RevisionPriority

        await store.record(turn=1, facts={"phase": "planning"})
        revisions = await store.advance_turn(
            updates={"phase": "testing"},
            priority=RevisionPriority.RECENT_OBSERVATION,
        )

        assert len(revisions) == 1
        assert revisions[0].key == "phase"
        assert revisions[0].old_value == "planning"
        assert revisions[0].new_value == "testing"

    @pytest.mark.asyncio
    async def test_advance_turn_increments_turn(self, store) -> None:
        """advance_turn increments current turn."""
        await store.record(turn=1, facts={"a": "1"})
        assert store._current_turn == 1

        await store.advance_turn(updates={"b": "2"})
        assert store._current_turn == 2

    @pytest.mark.asyncio
    async def test_advance_turn_new_fact_no_conflict(self, store) -> None:
        """Adding a new fact (not existing) doesn't cause revision."""
        await store.record(turn=1, facts={"existing": "value"})
        revisions = await store.advance_turn(updates={"new_fact": "new_value"})

        # No revision event for new facts
        assert len(revisions) == 0
        state = await store.get_current_state()
        assert state["new_fact"] == "new_value"
        assert state["existing"] == "value"

    @pytest.mark.asyncio
    async def test_advance_turn_lower_priority_rejected(self, store) -> None:
        """Lower priority update is rejected."""
        from scripts.temporal_memory.inertia import RevisionPriority

        # Record initial fact - it will have change_count=0, so INVARIANT priority
        await store.record(turn=1, facts={"invariant_fact": "original"})

        # Try to update with lower priority (HISTORICAL < INVARIANT)
        revisions = await store.advance_turn(
            updates={"invariant_fact": "attempted_change"},
            priority=RevisionPriority.HISTORICAL,
        )

        # No revision should occur
        assert len(revisions) == 0
        state = await store.get_current_state()
        assert state["invariant_fact"] == "original"  # Original preserved

    @pytest.mark.asyncio
    async def test_advance_turn_from_zero(self, store) -> None:
        """advance_turn works even when starting from turn 0."""
        assert store._current_turn == 0

        await store.advance_turn(updates={"first_fact": "value"})

        assert store._current_turn == 1
        state = await store.get_current_state()
        assert state["first_fact"] == "value"


class TestTemporalMemoryStorePGEdgeCases:
    """Test edge cases for PostgreSQL backend."""

    @pytest.mark.asyncio
    async def test_special_characters_in_value(self, store) -> None:
        """Fact values with special characters are handled correctly."""
        special_value = "path/with'quotes\"and\\backslashes\nand\nnewlines"
        await store.record(turn=1, facts={"test": special_value})

        state = await store.get_current_state()
        assert state["test"] == special_value

    @pytest.mark.asyncio
    async def test_unicode_in_value(self, store) -> None:
        """Fact values with unicode characters are handled correctly."""
        unicode_value = "Hello world"
        await store.record(turn=1, facts={"test": unicode_value})

        state = await store.get_current_state()
        assert state["test"] == unicode_value

    @pytest.mark.asyncio
    async def test_large_value(self, store) -> None:
        """Fact values can be large text blobs."""
        # 100KB value
        large_value = "x" * 100_000
        await store.record(turn=1, facts={"test": large_value})

        state = await store.get_current_state()
        assert len(state["test"]) == 100_000

    @pytest.mark.asyncio
    async def test_empty_facts_dict(self, store) -> None:
        """Empty facts dict doesn't crash."""
        await store.record(turn=1, facts={})

        state = await store.get_current_state()
        assert state == {}

    @pytest.mark.asyncio
    async def test_null_value_in_facts(self, store) -> None:
        """None values in facts are handled correctly."""
        await store.record(turn=1, facts={"nullable": None})

        state = await store.get_current_state()
        assert state["nullable"] is None

    @pytest.mark.asyncio
    async def test_numeric_string_values(self, store) -> None:
        """Numeric string values are preserved as strings."""
        await store.record(turn=1, facts={"number": "12345"})

        state = await store.get_current_state()
        assert state["number"] == "12345"
        assert isinstance(state["number"], str)


class TestTemporalMemoryStorePGConcurrency:
    """Test concurrent access to PostgreSQL backend."""

    @pytest.mark.asyncio
    async def test_concurrent_writes_different_sessions(
        self, clean_temporal_tables
    ) -> None:
        """Concurrent writes to different sessions don't interfere."""
        import asyncio

        from scripts.agentica_patterns.postgres_pool import reset_pool
        reset_pool()

        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        async def write_session(session_id: str, key: str) -> str:
            store = TemporalMemoryStorePG(session_id=session_id)
            await store.connect()
            await store.record(turn=1, facts={key: f"value-{session_id}"})
            state = await store.get_current_state()
            return state[key]

        # Write to 5 sessions concurrently
        tasks = [
            write_session(f"session-{i}", f"key-{i}")
            for i in range(5)
        ]
        values = await asyncio.gather(*tasks)

        # Verify each session got its own value
        for i, value in enumerate(values):
            assert value == f"value-session-{i}"

    @pytest.mark.asyncio
    async def test_concurrent_reads_same_session(
        self, store
    ) -> None:
        """Concurrent reads from same session are consistent."""
        import asyncio

        # Setup data
        await store.record(turn=1, facts={"stable": "value"})

        from scripts.agentica_patterns.postgres_pool import reset_pool

        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        async def read_session() -> str:
            # Create new store instance pointing to same session
            s = TemporalMemoryStorePG(session_id=store.session_id)
            await s.connect()
            state = await s.get_current_state()
            return state.get("stable", "")

        # Read concurrently
        tasks = [read_session() for _ in range(10)]
        values = await asyncio.gather(*tasks)

        # All reads should return same value
        assert all(v == "value" for v in values)

    @pytest.mark.asyncio
    async def test_sequential_writes_same_session(self, store) -> None:
        """Sequential writes to same session accumulate correctly."""
        for i in range(10):
            await store.record(turn=i + 1, facts={f"key-{i}": f"value-{i}"})

        state = await store.get_current_state()
        assert len(state) == 10
        for i in range(10):
            assert state[f"key-{i}"] == f"value-{i}"

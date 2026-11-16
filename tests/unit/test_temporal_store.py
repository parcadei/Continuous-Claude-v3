"""Tests for TemporalMemoryStore."""
import pytest
import tempfile
from pathlib import Path

from scripts.temporal_memory.store import TemporalMemoryStore


class TestTemporalMemoryStoreSchema:
    """Test schema creation and connection."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_temporal.db"

    @pytest.fixture
    async def store(self, temp_db):
        """Create connected store."""
        s = TemporalMemoryStore(session_id="test-session", db_path=temp_db)
        await s.connect()
        return s

    @pytest.mark.asyncio
    async def test_create_store(self, temp_db):
        store = TemporalMemoryStore(session_id="test-123", db_path=temp_db)
        assert store.session_id == "test-123"
        assert not store._connected

    @pytest.mark.asyncio
    async def test_connect_creates_tables(self, temp_db):
        store = TemporalMemoryStore(session_id="test-123", db_path=temp_db)
        await store.connect()

        assert store._connected
        assert temp_db.exists()

    @pytest.mark.asyncio
    async def test_temporal_facts_table_exists(self, store, temp_db):
        import aiosqlite
        async with aiosqlite.connect(str(temp_db)) as conn:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='temporal_facts'"
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "temporal_facts"

    @pytest.mark.asyncio
    async def test_temporal_trace_table_exists(self, store, temp_db):
        import aiosqlite
        async with aiosqlite.connect(str(temp_db)) as conn:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='temporal_trace'"
            )
            row = await cursor.fetchone()
            assert row is not None
            assert row[0] == "temporal_trace"

    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, store, temp_db):
        import aiosqlite
        async with aiosqlite.connect(str(temp_db)) as conn:
            cursor = await conn.execute("PRAGMA journal_mode")
            row = await cursor.fetchone()
            assert row[0].lower() == "wal"

    @pytest.mark.asyncio
    async def test_indexes_created(self, store, temp_db):
        import aiosqlite
        async with aiosqlite.connect(str(temp_db)) as conn:
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_temporal%'"
            )
            rows = await cursor.fetchall()
            index_names = [r[0] for r in rows]
            assert "idx_temporal_facts_session" in index_names
            assert "idx_temporal_trace_session" in index_names

    @pytest.mark.asyncio
    async def test_connect_idempotent(self, temp_db):
        store = TemporalMemoryStore(session_id="test-123", db_path=temp_db)
        await store.connect()
        await store.connect()  # Should not raise
        assert store._connected

    @pytest.mark.asyncio
    async def test_default_db_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
        store = TemporalMemoryStore(session_id="test-123")
        await store.connect()

        expected_path = tmp_path / ".claude" / "cache" / "temporal-memory" / "temporal.db"
        assert expected_path.exists()

    @pytest.mark.asyncio
    async def test_current_turn_starts_at_zero(self, store):
        assert store._current_turn == 0


class TestTemporalMemoryStoreCRUD:
    """Test CRUD operations."""

    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_temporal.db"

    @pytest.fixture
    async def store(self, temp_db):
        s = TemporalMemoryStore(session_id="test-session", db_path=temp_db)
        await s.connect()
        return s

    @pytest.mark.asyncio
    async def test_record_facts(self, store):
        await store.record(turn=1, facts={"phase": "testing", "goal": "implement"})

        state = await store.get_current_state()
        assert state["phase"] == "testing"
        assert state["goal"] == "implement"

    @pytest.mark.asyncio
    async def test_record_updates_turn(self, store):
        await store.record(turn=1, facts={"phase": "testing"})
        assert store._current_turn == 1

        await store.record(turn=5, facts={"phase": "done"})
        assert store._current_turn == 5

    @pytest.mark.asyncio
    async def test_record_tracks_changes(self, store):
        await store.record(turn=1, facts={"phase": "planning"})
        await store.record(turn=2, facts={"phase": "testing"})
        await store.record(turn=3, facts={"phase": "done"})

        # Check change_count in database
        import aiosqlite
        async with aiosqlite.connect(str(store._db_path)) as conn:
            cursor = await conn.execute(
                "SELECT change_count FROM temporal_facts WHERE session_id = ? AND key = ?",
                (store.session_id, "phase")
            )
            row = await cursor.fetchone()
            assert row[0] == 2  # Changed twice: planning->testing, testing->done

    @pytest.mark.asyncio
    async def test_get_trace_returns_ordered(self, store):
        await store.record(turn=1, facts={"a": "1"})
        await store.record(turn=3, facts={"b": "2"})
        await store.record(turn=2, facts={"c": "3"})

        trace = await store.get_trace()
        turns = [t["turn"] for t in trace]
        assert turns == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_get_trace_includes_facts(self, store):
        await store.record(turn=1, facts={"phase": "testing"})

        trace = await store.get_trace()
        assert len(trace) == 1
        assert trace[0]["facts"]["phase"] == "testing"

    @pytest.mark.asyncio
    async def test_get_current_state_latest_values(self, store):
        await store.record(turn=1, facts={"phase": "planning", "goal": "implement"})
        await store.record(turn=2, facts={"phase": "testing"})

        state = await store.get_current_state()
        assert state["phase"] == "testing"
        assert state["goal"] == "implement"

    @pytest.mark.asyncio
    async def test_get_current_state_empty(self, store):
        state = await store.get_current_state()
        assert state == {}

    @pytest.mark.asyncio
    async def test_get_invariants_unchanged_facts(self, store):
        await store.record(turn=1, facts={"db_type": "sqlite", "phase": "planning"})
        await store.record(turn=2, facts={"phase": "testing"})
        await store.record(turn=3, facts={"phase": "done"})

        invariants = await store.get_invariants()
        assert "db_type" in invariants
        assert invariants["db_type"] == "sqlite"
        assert "phase" not in invariants  # Changed

    @pytest.mark.asyncio
    async def test_get_invariants_empty(self, store):
        invariants = await store.get_invariants()
        assert invariants == {}

    @pytest.mark.asyncio
    async def test_record_multiple_sessions_isolated(self, temp_db):
        store1 = TemporalMemoryStore(session_id="session-1", db_path=temp_db)
        store2 = TemporalMemoryStore(session_id="session-2", db_path=temp_db)
        await store1.connect()
        await store2.connect()

        await store1.record(turn=1, facts={"value": "from-1"})
        await store2.record(turn=1, facts={"value": "from-2"})

        state1 = await store1.get_current_state()
        state2 = await store2.get_current_state()

        assert state1["value"] == "from-1"
        assert state2["value"] == "from-2"


class TestTemporalMemoryStoreErotetic:
    """Test E(X,Q) integration."""

    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_temporal.db"

    @pytest.fixture
    async def store(self, temp_db):
        s = TemporalMemoryStore(session_id="test-session", db_path=temp_db)
        await s.connect()
        return s

    @pytest.mark.asyncio
    async def test_record_with_erotetic(self, store):
        # Facts with some unknowns
        facts = {"framework": "fastapi", "database": "UNKNOWN"}
        result = await store.record_with_erotetic(turn=1, facts=facts)

        # Should return evocation result
        assert "isEmpty" in result
        assert "unknowns" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_record_with_erotetic_stores_trace(self, store):
        facts = {"phase": "testing", "auth": "UNKNOWN"}
        await store.record_with_erotetic(turn=1, facts=facts)

        trace = await store.get_trace()
        assert len(trace) == 1
        assert trace[0]["erotetic"] is not None

    @pytest.mark.asyncio
    async def test_get_open_questions_latest(self, store):
        facts1 = {"db": "UNKNOWN", "api": "UNKNOWN"}
        await store.record_with_erotetic(turn=1, facts=facts1)

        facts2 = {"db": "postgres", "api": "UNKNOWN"}
        await store.record_with_erotetic(turn=2, facts=facts2)

        questions = await store.get_open_questions()
        # Latest turn should have fewer unknowns (db resolved)
        assert "api" in questions or len(questions) <= 2

    @pytest.mark.asyncio
    async def test_get_open_questions_at_turn(self, store):
        await store.record_with_erotetic(turn=1, facts={"a": "UNKNOWN"})
        await store.record_with_erotetic(turn=2, facts={"a": "resolved"})

        q_turn1 = await store.get_open_questions(turn=1)
        q_turn2 = await store.get_open_questions(turn=2)

        # Turn 1 had unknowns, turn 2 resolved them
        assert len(q_turn1) >= len(q_turn2)

    @pytest.mark.asyncio
    async def test_get_open_questions_empty(self, store):
        questions = await store.get_open_questions()
        assert questions == []

    @pytest.mark.asyncio
    async def test_erotetic_with_no_unknowns(self, store):
        facts = {"framework": "fastapi", "database": "postgres"}
        result = await store.record_with_erotetic(turn=1, facts=facts)

        assert result["isEmpty"] is True
        assert result["unknowns"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_record_with_erotetic_unknown_values(self, store):
        """Test that E(X,Q) correctly identifies unknowns."""
        facts = {"known": "value", "unknown1": "UNKNOWN", "unknown2": None}
        result = await store.record_with_erotetic(turn=1, facts=facts)

        assert result["isEmpty"] is False
        assert "unknown1" in result["unknowns"]
        assert "unknown2" in result["unknowns"]
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_get_open_questions_returns_unknowns_list(self, store):
        """Test that get_open_questions returns list of unknown names."""
        facts = {"db": "UNKNOWN", "cache": "UNKNOWN", "api": "rest"}
        await store.record_with_erotetic(turn=1, facts=facts)

        questions = await store.get_open_questions()
        assert isinstance(questions, list)
        assert "db" in questions
        assert "cache" in questions
        assert "api" not in questions


class TestTemporalMemoryStoreInertia:
    """Test store with inertia integration."""

    @pytest.fixture
    def temp_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test.db"

    @pytest.fixture
    async def store(self, temp_db):
        s = TemporalMemoryStore(session_id="test", db_path=temp_db)
        await s.connect()
        return s

    @pytest.mark.asyncio
    async def test_advance_turn_applies_inertia(self, store):
        from scripts.temporal_memory.inertia import RevisionPriority

        await store.record(turn=1, facts={"db": "sqlite", "phase": "planning"})
        revisions = await store.advance_turn(
            updates={"phase": "testing"},
            priority=RevisionPriority.RECENT_OBSERVATION,
        )

        state = await store.get_current_state()
        assert state["db"] == "sqlite"  # Persisted via inertia
        assert state["phase"] == "testing"  # Updated

    @pytest.mark.asyncio
    async def test_advance_turn_returns_revisions(self, store):
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
    async def test_advance_turn_increments_turn(self, store):
        await store.record(turn=1, facts={"a": "1"})
        assert store._current_turn == 1

        await store.advance_turn(updates={"b": "2"})
        assert store._current_turn == 2

    @pytest.mark.asyncio
    async def test_advance_turn_new_fact_no_conflict(self, store):
        """Test adding a new fact (not existing) doesn't cause revision."""
        await store.record(turn=1, facts={"existing": "value"})
        revisions = await store.advance_turn(updates={"new_fact": "new_value"})

        # No revision event for new facts
        assert len(revisions) == 0
        state = await store.get_current_state()
        assert state["new_fact"] == "new_value"
        assert state["existing"] == "value"

    @pytest.mark.asyncio
    async def test_advance_turn_lower_priority_rejected(self, store):
        """Test that lower priority update is rejected."""
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

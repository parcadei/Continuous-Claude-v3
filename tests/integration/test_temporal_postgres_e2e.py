"""End-to-end integration tests for temporal memory PostgreSQL backend.

Phase 4 of PostgreSQL migration - E2E Integration Testing.

Tests the full workflow of temporal memory with PostgreSQL including:
- Multi-agent concurrent writes
- Fact persistence across sessions
- Semantic search across agent contexts
- Backend switching (SQLite <-> PostgreSQL)
- Full lifecycle (Write -> Read -> Update -> Search -> Summarize)
- Regression: All existing tests pass with Postgres backend

Prerequisites:
- PostgreSQL container must be running
- Run: ./docker/start-postgres.sh before tests
- pgvector extension must be installed

Usage:
    # Run E2E tests
    uv run pytest tests/integration/test_temporal_postgres_e2e.py -v

    # Run all temporal tests with Postgres backend
    TEMPORAL_BACKEND=postgres uv run pytest -k temporal -v --ignore=tests/integration/test_temporal_postgres_e2e.py
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest


def is_postgres_available() -> bool:
    """Check if PostgreSQL container is running and healthy."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", "agentica-postgres"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == "healthy"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


# Module-level skip if PostgreSQL is not available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not is_postgres_available(),
        reason="PostgreSQL container not available. Start with: ./docker/start-postgres.sh",
    ),
]


@pytest.fixture(scope="module")
async def clean_temporal_tables():
    """Clean temporal tables before and after test module.

    This fixture ensures a clean slate for each test run.
    """
    from scripts.agentica_patterns.postgres_pool import (
        close_pool,
        get_connection,
        reset_pool,
    )

    # Clean before tests
    try:
        async with get_connection() as conn:
            await conn.execute("TRUNCATE temporal_facts, temporal_traces CASCADE")
    except Exception:
        # Tables might not exist yet
        pass

    yield

    # Clean after tests
    try:
        async with get_connection() as conn:
            await conn.execute("TRUNCATE temporal_facts, temporal_traces CASCADE")
    except Exception:
        pass

    # Close pool to clean up connections
    await close_pool()
    reset_pool()


@pytest.fixture
async def clean_session():
    """Clean temporal tables before each test.

    Returns a unique session_id prefix for test isolation.
    """
    from scripts.agentica_patterns.postgres_pool import get_connection, reset_pool

    # Reset pool to avoid event loop issues
    reset_pool()

    # Clean tables
    try:
        async with get_connection() as conn:
            await conn.execute("TRUNCATE temporal_facts, temporal_traces CASCADE")
    except Exception:
        pass

    # Return unique prefix for this test
    return f"test-{uuid.uuid4().hex[:8]}"


class TestMultiAgentConcurrentWrites:
    """Test concurrent writes from multiple agents to PostgreSQL backend."""

    @pytest.mark.asyncio
    async def test_five_concurrent_agents_no_conflicts(self, clean_session):
        """Spawn 5 concurrent asyncio tasks writing to same PostgreSQL backend.

        Verifies:
        - All writes succeed without conflicts
        - No data loss
        - Each task writes to a different session_id
        """
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_prefix = clean_session
        num_agents = 5
        turns_per_agent = 10

        async def agent_work(agent_id: int) -> dict[str, Any]:
            """Simulate an agent writing facts across multiple turns."""
            session_id = f"{session_prefix}-agent-{agent_id}"
            store = TemporalMemoryStorePG(session_id=session_id)
            await store.connect()

            for turn in range(1, turns_per_agent + 1):
                await store.record(
                    turn=turn,
                    facts={
                        "agent_id": str(agent_id),
                        "turn": str(turn),
                        "phase": f"phase-{turn % 3}",
                        "data": f"agent-{agent_id}-turn-{turn}",
                    },
                )

            # Return final state
            state = await store.get_current_state()
            trace = await store.get_trace()
            return {
                "session_id": session_id,
                "state": state,
                "turn_count": len(trace),
            }

        # Run all agents concurrently
        results = await asyncio.gather(*[agent_work(i) for i in range(num_agents)])

        # Verify all agents completed successfully
        assert len(results) == num_agents

        for i, result in enumerate(results):
            assert result["turn_count"] == turns_per_agent, (
                f"Agent {i} missing turns: expected {turns_per_agent}, got {result['turn_count']}"
            )
            assert result["state"]["agent_id"] == str(i)
            assert result["state"]["turn"] == str(turns_per_agent)

    @pytest.mark.asyncio
    async def test_concurrent_writes_different_facts(self, clean_session):
        """Multiple agents write different facts concurrently.

        Verifies that concurrent writes to different keys don't interfere.
        """
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_prefix = clean_session
        num_agents = 3

        async def agent_write_unique_facts(agent_id: int) -> dict[str, Any]:
            """Each agent writes facts with unique keys."""
            session_id = f"{session_prefix}-unique-{agent_id}"
            store = TemporalMemoryStorePG(session_id=session_id)
            await store.connect()

            # Each agent writes unique keys
            facts = {
                f"key_{agent_id}_1": f"value_{agent_id}_1",
                f"key_{agent_id}_2": f"value_{agent_id}_2",
                f"key_{agent_id}_3": f"value_{agent_id}_3",
            }
            await store.record(turn=1, facts=facts)

            return {
                "session_id": session_id,
                "state": await store.get_current_state(),
            }

        results = await asyncio.gather(*[agent_write_unique_facts(i) for i in range(num_agents)])

        # Verify each agent's facts are intact
        for i, result in enumerate(results):
            state = result["state"]
            assert state.get(f"key_{i}_1") == f"value_{i}_1"
            assert state.get(f"key_{i}_2") == f"value_{i}_2"
            assert state.get(f"key_{i}_3") == f"value_{i}_3"


class TestFactPersistenceAcrossSessions:
    """Test that facts persist across store instances."""

    @pytest.mark.asyncio
    async def test_facts_persist_after_reconnect(self, clean_session):
        """Write facts in one instance, verify they persist in new instance."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-persist"

        # First instance - write facts
        store1 = TemporalMemoryStorePG(session_id=session_id)
        await store1.connect()
        await store1.record(turn=1, facts={"db": "postgres", "phase": "init"})
        await store1.record(turn=2, facts={"db": "postgres", "phase": "running"})

        # Second instance - should see persisted data
        store2 = TemporalMemoryStorePG(session_id=session_id)
        await store2.connect()

        # Verify facts persisted
        state = await store2.get_current_state()
        assert state["db"] == "postgres"
        assert state["phase"] == "running"

        # Verify turn restored
        assert store2._current_turn == 2

    @pytest.mark.asyncio
    async def test_turn_continuity_after_reconnect(self, clean_session):
        """Verify turn counter continues correctly after reconnect."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-turn-continuity"

        # First instance - write up to turn 5
        store1 = TemporalMemoryStorePG(session_id=session_id)
        await store1.connect()
        for turn in range(1, 6):
            await store1.record(turn=turn, facts={"count": str(turn)})

        # Second instance - should continue from turn 5
        store2 = TemporalMemoryStorePG(session_id=session_id)
        await store2.connect()

        assert store2._current_turn == 5

        # Continue recording
        await store2.record(turn=6, facts={"count": "6"})
        assert store2._current_turn == 6

        # Verify trace has all 6 turns
        trace = await store2.get_trace()
        assert len(trace) == 6

    @pytest.mark.asyncio
    async def test_invariants_persist_across_sessions(self, clean_session):
        """Invariants should be correctly identified after reconnect."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-invariants"

        # First instance - establish invariants
        store1 = TemporalMemoryStorePG(session_id=session_id)
        await store1.connect()
        await store1.record(turn=1, facts={"db_type": "postgres", "phase": "init"})
        await store1.record(turn=2, facts={"phase": "running"})  # phase changes

        # Second instance - check invariants
        store2 = TemporalMemoryStorePG(session_id=session_id)
        await store2.connect()

        invariants = await store2.get_invariants()
        assert "db_type" in invariants  # Never changed
        assert "phase" not in invariants  # Changed


class TestSemanticSearchAcrossAgentContexts:
    """Test vector similarity search with session isolation."""

    @pytest.mark.asyncio
    async def test_search_similar_returns_ranked_results(self, clean_session):
        """Search returns results ranked by similarity."""
        from scripts.agentica_patterns.postgres_pool import get_connection
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-search"
        store = TemporalMemoryStorePG(session_id=session_id)
        await store.connect()

        # Record some facts
        await store.record(turn=1, facts={"topic": "database"})
        await store.record(turn=2, facts={"topic2": "postgresql"})
        await store.record(turn=3, facts={"topic3": "vectors"})

        # Manually add embeddings to the facts (simulating embedding generation)
        # Using simple patterns: similar embeddings for similar concepts
        embeddings = {
            "topic": [1.0, 0.0, 0.0, 0.0] + [0.0] * 4092,  # 4096 dim
            "topic2": [0.9, 0.1, 0.0, 0.0] + [0.0] * 4092,  # Similar to topic
            "topic3": [0.0, 0.0, 1.0, 0.0] + [0.0] * 4092,  # Different
        }

        async with get_connection() as conn:
            for key, emb in embeddings.items():
                await conn.execute(
                    """
                    UPDATE temporal_facts
                    SET embedding = $1::vector
                    WHERE session_id = $2 AND key = $3
                    """,
                    emb,
                    session_id,
                    key,
                )

        # Search for something similar to "database" embedding
        query_embedding = [1.0, 0.0, 0.0, 0.0]  # Will be padded
        results = await store.search_similar(query_embedding, limit=10)

        assert len(results) == 3
        # First result should be "topic" (exact match)
        assert results[0]["key"] == "topic"
        # Second should be "topic2" (similar)
        assert results[1]["key"] == "topic2"
        # Third should be "topic3" (different)
        assert results[2]["key"] == "topic3"

        # Verify similarity scores are ordered
        assert results[0]["similarity"] >= results[1]["similarity"]
        assert results[1]["similarity"] >= results[2]["similarity"]

    @pytest.mark.asyncio
    async def test_search_respects_session_isolation(self, clean_session):
        """Search should not return facts from other sessions."""
        from scripts.agentica_patterns.postgres_pool import get_connection
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session1_id = f"{clean_session}-session1"
        session2_id = f"{clean_session}-session2"

        # Create two stores with different sessions
        store1 = TemporalMemoryStorePG(session_id=session1_id)
        store2 = TemporalMemoryStorePG(session_id=session2_id)
        await store1.connect()
        await store2.connect()

        # Record facts in both sessions
        await store1.record(turn=1, facts={"secret": "session1-secret"})
        await store2.record(turn=1, facts={"secret": "session2-secret"})

        # Add embeddings
        embedding = [1.0] * 128  # Will be padded to 4096
        padded = embedding + [0.0] * (4096 - 128)

        async with get_connection() as conn:
            await conn.execute(
                """
                UPDATE temporal_facts
                SET embedding = $1::vector
                WHERE session_id = $2 AND key = $3
                """,
                padded,
                session1_id,
                "secret",
            )
            await conn.execute(
                """
                UPDATE temporal_facts
                SET embedding = $1::vector
                WHERE session_id = $2 AND key = $3
                """,
                padded,
                session2_id,
                "secret",
            )

        # Search from store1 - should only find session1 facts
        results1 = await store1.search_similar([1.0] * 128, limit=10)
        assert len(results1) == 1
        assert results1[0]["value"] == "session1-secret"

        # Search from store2 - should only find session2 facts
        results2 = await store2.search_similar([1.0] * 128, limit=10)
        assert len(results2) == 1
        assert results2[0]["value"] == "session2-secret"

    @pytest.mark.asyncio
    async def test_search_graceful_without_embeddings(self, clean_session):
        """Search should return empty if no facts have embeddings."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-no-embeddings"
        store = TemporalMemoryStorePG(session_id=session_id)
        await store.connect()

        # Record facts without embeddings
        await store.record(turn=1, facts={"fact1": "value1", "fact2": "value2"})

        # Search should return empty (no embeddings)
        results = await store.search_similar([1.0] * 128, limit=10)
        assert results == []


class TestBackendSwitching:
    """Test switching between SQLite and PostgreSQL backends."""

    @pytest.mark.asyncio
    async def test_backend_switching_data_isolation(self, clean_session):
        """Data written to SQLite should not appear in PostgreSQL and vice versa."""
        from scripts.temporal_memory.factory import create_temporal_store

        session_id = f"{clean_session}-switch"

        with TemporaryDirectory() as tmpdir:
            sqlite_path = Path(tmpdir) / "temporal.db"

            # Write to SQLite
            store_sqlite = await create_temporal_store(
                backend="sqlite",
                session_id=session_id,
                db_path=sqlite_path,
            )
            await store_sqlite.record(turn=1, facts={"backend": "sqlite", "data": "sqlite-data"})

            # Write to PostgreSQL (different data)
            store_pg = await create_temporal_store(
                backend="postgres",
                session_id=session_id,
            )
            await store_pg.record(turn=1, facts={"backend": "postgres", "data": "pg-data"})

            # Verify SQLite has its own data
            state_sqlite = await store_sqlite.get_current_state()
            assert state_sqlite["backend"] == "sqlite"
            assert state_sqlite["data"] == "sqlite-data"

            # Verify PostgreSQL has its own data
            state_pg = await store_pg.get_current_state()
            assert state_pg["backend"] == "postgres"
            assert state_pg["data"] == "pg-data"

    @pytest.mark.asyncio
    async def test_env_var_backend_selection(self, clean_session, monkeypatch):
        """Test TEMPORAL_BACKEND environment variable controls backend selection."""
        from scripts.temporal_memory.factory import get_temporal_backend

        # Default is sqlite
        monkeypatch.delenv("TEMPORAL_BACKEND", raising=False)
        assert get_temporal_backend() == "sqlite"

        # Set to postgres
        monkeypatch.setenv("TEMPORAL_BACKEND", "postgres")
        assert get_temporal_backend() == "postgres"

        # Invalid value falls back to sqlite
        monkeypatch.setenv("TEMPORAL_BACKEND", "invalid")
        assert get_temporal_backend() == "sqlite"


class TestFullLifecycle:
    """Test complete lifecycle: Write -> Read -> Update -> Search -> Summarize."""

    @pytest.mark.asyncio
    async def test_full_crud_lifecycle(self, clean_session):
        """Test complete CRUD operations lifecycle."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-lifecycle"
        store = TemporalMemoryStorePG(session_id=session_id)
        await store.connect()

        # 1. CREATE - Write initial facts
        await store.record(turn=1, facts={"phase": "init", "db": "postgres", "goal": "pending"})

        # 2. READ - Verify initial state
        state = await store.get_current_state()
        assert state["phase"] == "init"
        assert state["db"] == "postgres"
        assert state["goal"] == "pending"

        # 3. UPDATE - Modify facts
        await store.record(turn=2, facts={"phase": "running", "db": "postgres", "goal": "in_progress"})

        # 4. READ after update
        state = await store.get_current_state()
        assert state["phase"] == "running"
        assert state["goal"] == "in_progress"

        # 5. Get trace (full history)
        trace = await store.get_trace()
        assert len(trace) == 2
        assert trace[0]["turn"] == 1
        assert trace[1]["turn"] == 2

        # 6. Get invariants (facts that never changed)
        invariants = await store.get_invariants()
        assert "db" in invariants  # db never changed
        assert "phase" not in invariants  # phase changed
        assert "goal" not in invariants  # goal changed

    @pytest.mark.asyncio
    async def test_lifecycle_with_erotetic(self, clean_session):
        """Test lifecycle including erotetic (open question) tracking."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-erotetic"
        store = TemporalMemoryStorePG(session_id=session_id)
        await store.connect()

        # Record with unknowns
        result1 = await store.record_with_erotetic(
            turn=1,
            facts={"db": "UNKNOWN", "framework": "agentica", "auth": "UNKNOWN"},
        )
        assert len(result1["unknowns"]) == 2
        assert "db" in result1["unknowns"]
        assert "auth" in result1["unknowns"]

        # Resolve one unknown
        result2 = await store.record_with_erotetic(
            turn=2,
            facts={"db": "postgres", "framework": "agentica", "auth": "UNKNOWN"},
        )
        assert "db" not in result2["unknowns"]
        assert "auth" in result2["unknowns"]

        # Query open questions
        questions = await store.get_open_questions()
        assert "auth" in questions
        assert "db" not in questions

    @pytest.mark.asyncio
    async def test_lifecycle_with_inertia(self, clean_session):
        """Test lifecycle with inertia rule (advance_turn)."""
        from scripts.temporal_memory.inertia import RevisionPriority
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-inertia"
        store = TemporalMemoryStorePG(session_id=session_id)
        await store.connect()

        # Initial state
        await store.record(turn=1, facts={"db": "postgres", "phase": "init", "counter": "0"})

        # Advance turn with partial update (inertia preserves unchanged facts)
        revisions = await store.advance_turn(
            updates={"phase": "running", "counter": "1"},
            priority=RevisionPriority.RECENT_OBSERVATION,
        )

        # Check revisions generated
        assert len(revisions) == 2  # phase and counter changed

        # Verify inertia: db persisted without being in updates
        state = await store.get_current_state()
        assert state["db"] == "postgres"  # Persisted via inertia
        assert state["phase"] == "running"  # Updated
        assert state["counter"] == "1"  # Updated

    @pytest.mark.asyncio
    async def test_full_workflow_with_summarizer(self, clean_session):
        """Test full workflow including summarization."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG
        from scripts.temporal_memory.summarizer import TemporalSummarizer

        session_id = f"{clean_session}-summarizer"
        store = TemporalMemoryStorePG(session_id=session_id)
        await store.connect()

        # Record multiple turns with transitions
        await store.record(turn=1, facts={"phase": "planning", "db": "postgres"})
        await store.record(turn=2, facts={"phase": "coding", "db": "postgres"})
        await store.record(turn=3, facts={"phase": "testing", "db": "postgres"})
        await store.record(turn=4, facts={"phase": "done", "db": "postgres", "goal_tests": "achieved"})

        # Summarize
        summarizer = TemporalSummarizer()
        summary = await summarizer.summarize(store, budget_tokens=2000)

        # Verify summary contents
        assert summary["turn_count"] == 4
        assert summary["current_state"]["phase"] == "done"
        assert summary["current_state"]["db"] == "postgres"

        # Should have transitions (phase changed 3 times)
        assert len(summary["transitions"]) >= 3

        # db should be invariant (never changed)
        db_invariants = [inv for inv in summary["invariants"] if "db" in inv]
        assert len(db_invariants) >= 1


class TestRegressionExistingTests:
    """Verify existing temporal tests pass with PostgreSQL backend.

    These tests verify that the PostgreSQL backend is compatible with
    the same operations tested in the SQLite-based test suite.
    """

    @pytest.mark.asyncio
    async def test_session_isolation_regression(self, clean_session):
        """Sessions should be isolated - regression test."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session1_id = f"{clean_session}-iso1"
        session2_id = f"{clean_session}-iso2"

        store1 = TemporalMemoryStorePG(session_id=session1_id)
        store2 = TemporalMemoryStorePG(session_id=session2_id)
        await store1.connect()
        await store2.connect()

        # Write to both
        await store1.record(turn=1, facts={"data": "session1"})
        await store2.record(turn=1, facts={"data": "session2"})

        # Verify isolation
        state1 = await store1.get_current_state()
        state2 = await store2.get_current_state()
        assert state1["data"] == "session1"
        assert state2["data"] == "session2"

    @pytest.mark.asyncio
    async def test_change_count_tracking_regression(self, clean_session):
        """Change count should be tracked correctly - regression test."""
        from scripts.agentica_patterns.postgres_pool import get_connection
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-change"
        store = TemporalMemoryStorePG(session_id=session_id)
        await store.connect()

        # Initial record
        await store.record(turn=1, facts={"phase": "init"})

        # Verify initial change_count is 0
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT change_count FROM temporal_facts
                WHERE session_id = $1 AND key = $2
                """,
                session_id,
                "phase",
            )
            assert row["change_count"] == 0

        # Update the fact
        await store.record(turn=2, facts={"phase": "running"})

        # Verify change_count incremented
        async with get_connection() as conn:
            row = await conn.fetchrow(
                """
                SELECT change_count FROM temporal_facts
                WHERE session_id = $1 AND key = $2
                """,
                session_id,
                "phase",
            )
            assert row["change_count"] == 1

    @pytest.mark.asyncio
    async def test_trace_ordering_regression(self, clean_session):
        """Trace should be ordered by turn - regression test."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-trace"
        store = TemporalMemoryStorePG(session_id=session_id)
        await store.connect()

        # Write out of order (shouldn't happen normally, but test ordering)
        await store.record(turn=3, facts={"order": "third"})
        await store.record(turn=1, facts={"order": "first"})
        await store.record(turn=2, facts={"order": "second"})

        trace = await store.get_trace()
        assert len(trace) == 3
        assert trace[0]["turn"] == 1
        assert trace[1]["turn"] == 2
        assert trace[2]["turn"] == 3

    @pytest.mark.asyncio
    async def test_special_characters_regression(self, clean_session):
        """Special characters should be handled correctly - regression test."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-special"
        store = TemporalMemoryStorePG(session_id=session_id)
        await store.connect()

        special_value = "value with 'quotes' and \"double\" and\nnewlines and unicode"
        await store.record(turn=1, facts={"special": special_value})

        state = await store.get_current_state()
        assert state["special"] == special_value

    @pytest.mark.asyncio
    async def test_empty_facts_regression(self, clean_session):
        """Empty facts should be handled - regression test."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-empty"
        store = TemporalMemoryStorePG(session_id=session_id)
        await store.connect()

        # Record empty facts
        await store.record(turn=1, facts={})

        trace = await store.get_trace()
        assert len(trace) == 1
        assert trace[0]["facts"] == {}

    @pytest.mark.asyncio
    async def test_concurrent_read_write_regression(self, clean_session):
        """Concurrent read/write operations should not conflict - regression test."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_id = f"{clean_session}-concurrent"
        store = TemporalMemoryStorePG(session_id=session_id)
        await store.connect()

        # Initial data
        await store.record(turn=1, facts={"counter": "0"})

        async def read_task():
            for _ in range(5):
                await store.get_current_state()
                await asyncio.sleep(0.01)

        async def write_task():
            for i in range(5):
                await store.record(turn=i + 2, facts={"counter": str(i + 1)})
                await asyncio.sleep(0.01)

        # Run concurrently
        await asyncio.gather(read_task(), write_task())

        # Verify final state
        state = await store.get_current_state()
        assert state["counter"] == "5"


class TestConnectionPooling:
    """Test connection pool behavior under load."""

    @pytest.mark.asyncio
    async def test_pool_handles_many_connections(self, clean_session):
        """Pool should handle many concurrent store operations."""
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

        session_prefix = clean_session
        num_stores = 10

        async def create_and_use_store(i: int) -> str:
            session_id = f"{session_prefix}-pool-{i}"
            store = TemporalMemoryStorePG(session_id=session_id)
            await store.connect()
            await store.record(turn=1, facts={"store_id": str(i)})
            state = await store.get_current_state()
            return state["store_id"]

        results = await asyncio.gather(*[create_and_use_store(i) for i in range(num_stores)])
        assert results == [str(i) for i in range(num_stores)]

    @pytest.mark.asyncio
    async def test_health_check(self, clean_session):
        """Health check should pass when PostgreSQL is available."""
        from scripts.agentica_patterns.postgres_pool import health_check

        is_healthy, error = await health_check()
        assert is_healthy is True
        assert error is None

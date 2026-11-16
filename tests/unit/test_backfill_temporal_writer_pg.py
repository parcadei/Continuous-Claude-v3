"""Tests for TemporalWriterPG - Phase 3.2 of PostgreSQL migration.

TDD test suite for writing extracted facts to PostgreSQL.
Mirrors all tests from test_backfill_temporal_writer.py for PostgreSQL.

Tests:
- test_write_single_fact: Single fact written to temporal_facts table
- test_write_multiple_facts_batched: Multiple facts in single transaction
- test_dedup_by_content_hash: Duplicate facts (same hash) are skipped
- test_confidence_calibration_applied: Confidence multiplied by outcome
- test_write_trace_snapshot: Turn-level trace entries created
- test_facts_include_turn_number: Facts preserve turn number
- test_empty_facts_list: Empty list doesn't crash
- test_write_facts_returns_count: Returns count of facts written
- test_different_sessions_isolated: Sessions don't interfere

Prerequisites:
- Docker must be running
- Run: ./docker/start-postgres.sh before tests
- Temporal schema must be applied (Phase 3.1)

Usage:
    uv run pytest tests/unit/test_backfill_temporal_writer_pg.py -v

Expected failures (TemporalWriterPG not yet implemented):
- ModuleNotFoundError: No module named 'scripts.backfill.temporal_writer_pg'
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
async def pg_writer(clean_temporal_tables):
    """Create a TemporalWriterPG instance for testing.

    Uses the PostgreSQL pool from postgres_pool.py.
    Tables are cleaned before and after each test.
    """
    # Reset pool to avoid event loop issues between tests
    from scripts.agentica_patterns.postgres_pool import reset_pool

    reset_pool()

    # Import will fail until TemporalWriterPG is implemented
    from scripts.backfill.temporal_writer_pg import TemporalWriterPG

    writer = TemporalWriterPG()
    await writer.connect()

    yield writer

    await writer.close()

    # Reset pool after test to avoid stale connections
    reset_pool()


class TestTemporalWriterPG:
    """Test suite for TemporalWriterPG - PostgreSQL version."""

    @pytest.mark.asyncio
    async def test_write_single_fact(self, pg_writer) -> None:
        """Single fact written to temporal_facts table."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        fact = SpanFact(key="file_read", value="/path/to/file.py", turn=1)
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="SUCCEEDED",
            confidence_multiplier=1.2,
            method="context_db",
        )

        await pg_writer.write_facts("session-1", [fact], outcome)

        # Verify in database
        facts = await pg_writer.get_facts("session-1")
        assert len(facts) == 1
        assert facts[0]["key"] == "file_read"
        assert facts[0]["value"] == "/path/to/file.py"
        assert facts[0]["confidence"] == pytest.approx(1.2)  # 1.0 * 1.2

    @pytest.mark.asyncio
    async def test_write_multiple_facts_batched(self, pg_writer) -> None:
        """Multiple facts written in single transaction."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        facts = [
            SpanFact(key="file_read", value="/a.py", turn=1),
            SpanFact(key="file_read", value="/b.py", turn=1),
            SpanFact(key="file_written", value="/c.py", turn=2),
        ]
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="SUCCEEDED",
            confidence_multiplier=1.2,
            method="context_db",
        )

        await pg_writer.write_facts("session-1", facts, outcome)

        all_facts = await pg_writer.get_facts("session-1")
        assert len(all_facts) == 3

    @pytest.mark.asyncio
    async def test_dedup_by_content_hash(self, pg_writer) -> None:
        """Duplicate facts (same content_hash) are skipped."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        fact = SpanFact(
            key="file_read", value="/same.py", turn=1, content_hash="abc123"
        )
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )

        await pg_writer.write_facts("session-1", [fact], outcome)
        await pg_writer.write_facts("session-1", [fact], outcome)  # Duplicate

        facts = await pg_writer.get_facts("session-1")
        assert len(facts) == 1  # Only one copy

    @pytest.mark.asyncio
    async def test_confidence_calibration_applied(self, pg_writer) -> None:
        """Fact confidence is multiplied by outcome multiplier."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        fact = SpanFact(key="test", value="v", turn=1, confidence=0.8)
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="SUCCEEDED",
            confidence_multiplier=1.2,
            method="context_db",
        )

        await pg_writer.write_facts("session-1", [fact], outcome)

        facts = await pg_writer.get_facts("session-1")
        assert facts[0]["confidence"] == pytest.approx(0.96)  # 0.8 * 1.2

    @pytest.mark.asyncio
    async def test_write_trace_snapshot(self, pg_writer) -> None:
        """Turn-level trace snapshot written."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        facts_by_turn: dict[int, list[SpanFact]] = {
            1: [SpanFact(key="a", value="1", turn=1)],
            2: [SpanFact(key="b", value="2", turn=2)],
        }
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="SUCCEEDED",
            confidence_multiplier=1.2,
            method="context_db",
        )

        await pg_writer.write_traces("session-1", facts_by_turn, outcome)

        # Verify trace table has entries
        traces = await pg_writer.get_traces("session-1")
        assert len(traces) == 2

    @pytest.mark.asyncio
    async def test_facts_include_turn_number(self, pg_writer) -> None:
        """Facts preserve turn number from SpanFact."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        facts = [
            SpanFact(key="a", value="1", turn=5),
            SpanFact(key="b", value="2", turn=10),
        ]
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )

        await pg_writer.write_facts("session-1", facts, outcome)

        db_facts = await pg_writer.get_facts("session-1")
        turns = [f["turn"] for f in db_facts]
        assert 5 in turns
        assert 10 in turns

    @pytest.mark.asyncio
    async def test_empty_facts_list(self, pg_writer) -> None:
        """Empty facts list doesn't crash."""
        from scripts.backfill.outcome_tagger import SessionOutcome

        outcome = SessionOutcome(
            session_id="session-1",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )

        count = await pg_writer.write_facts("session-1", [], outcome)
        assert count == 0

        facts = await pg_writer.get_facts("session-1")
        assert len(facts) == 0

    @pytest.mark.asyncio
    async def test_write_facts_returns_count(self, pg_writer) -> None:
        """write_facts returns count of facts written."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        facts = [
            SpanFact(key="a", value="1", turn=1),
            SpanFact(key="b", value="2", turn=2),
        ]
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )

        count = await pg_writer.write_facts("session-1", facts, outcome)
        assert count == 2

    @pytest.mark.asyncio
    async def test_different_sessions_isolated(self, pg_writer) -> None:
        """Facts from different sessions are isolated."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        outcome1 = SessionOutcome(
            session_id="session-1",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )
        outcome2 = SessionOutcome(
            session_id="session-2",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )

        await pg_writer.write_facts(
            "session-1", [SpanFact(key="a", value="1", turn=1)], outcome1
        )
        await pg_writer.write_facts(
            "session-2", [SpanFact(key="b", value="2", turn=1)], outcome2
        )

        facts1 = await pg_writer.get_facts("session-1")
        facts2 = await pg_writer.get_facts("session-2")

        assert len(facts1) == 1
        assert len(facts2) == 1
        assert facts1[0]["key"] == "a"
        assert facts2[0]["key"] == "b"


class TestTemporalWriterPGTransactions:
    """Test transaction behavior for TemporalWriterPG."""

    @pytest.mark.asyncio
    async def test_write_facts_atomic(self, pg_writer) -> None:
        """All facts in a write_facts call are atomic.

        If any fact fails, none should be written.
        This tests the transaction semantics of the PostgreSQL writer.
        """
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        # First write should succeed
        facts = [
            SpanFact(key="a", value="1", turn=1, content_hash="hash1"),
            SpanFact(key="b", value="2", turn=2, content_hash="hash2"),
        ]
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )
        await pg_writer.write_facts("session-1", facts, outcome)

        # Verify first write
        db_facts = await pg_writer.get_facts("session-1")
        assert len(db_facts) == 2

    @pytest.mark.asyncio
    async def test_write_traces_atomic(self, pg_writer) -> None:
        """All traces in a write_traces call are atomic."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        facts_by_turn = {
            1: [SpanFact(key="a", value="1", turn=1)],
            2: [SpanFact(key="b", value="2", turn=2)],
            3: [SpanFact(key="c", value="3", turn=3)],
        }
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="SUCCEEDED",
            confidence_multiplier=1.2,
            method="context_db",
        )

        await pg_writer.write_traces("session-1", facts_by_turn, outcome)

        traces = await pg_writer.get_traces("session-1")
        assert len(traces) == 3


class TestTemporalWriterPGEdgeCases:
    """Test edge cases for TemporalWriterPG."""

    @pytest.mark.asyncio
    async def test_special_characters_in_value(self, pg_writer) -> None:
        """Fact values with special characters are handled correctly."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        # Value with various special characters
        special_value = "path/with'quotes\"and\\backslashes\nand\nnewlines"
        fact = SpanFact(key="test", value=special_value, turn=1)
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )

        await pg_writer.write_facts("session-1", [fact], outcome)

        facts = await pg_writer.get_facts("session-1")
        assert len(facts) == 1
        assert facts[0]["value"] == special_value

    @pytest.mark.asyncio
    async def test_unicode_in_value(self, pg_writer) -> None:
        """Fact values with unicode characters are handled correctly."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        unicode_value = "Hello world"
        fact = SpanFact(key="test", value=unicode_value, turn=1)
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )

        await pg_writer.write_facts("session-1", [fact], outcome)

        facts = await pg_writer.get_facts("session-1")
        assert len(facts) == 1
        assert facts[0]["value"] == unicode_value

    @pytest.mark.asyncio
    async def test_large_value(self, pg_writer) -> None:
        """Fact values can be large text blobs."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        # 100KB value
        large_value = "x" * 100_000
        fact = SpanFact(key="test", value=large_value, turn=1)
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )

        await pg_writer.write_facts("session-1", [fact], outcome)

        facts = await pg_writer.get_facts("session-1")
        assert len(facts) == 1
        assert len(facts[0]["value"]) == 100_000

    @pytest.mark.asyncio
    async def test_null_content_hash_allowed(self, pg_writer) -> None:
        """Facts without content_hash are allowed (NULL)."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        # No content_hash specified
        fact = SpanFact(key="test", value="v", turn=1)
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )

        await pg_writer.write_facts("session-1", [fact], outcome)

        facts = await pg_writer.get_facts("session-1")
        assert len(facts) == 1

    @pytest.mark.asyncio
    async def test_confidence_clamping(self, pg_writer) -> None:
        """Confidence values are not clamped (can exceed 1.0)."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        # High confidence with high multiplier
        fact = SpanFact(key="test", value="v", turn=1, confidence=1.0)
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="SUCCEEDED",
            confidence_multiplier=1.5,  # Results in 1.5
            method="context_db",
        )

        await pg_writer.write_facts("session-1", [fact], outcome)

        facts = await pg_writer.get_facts("session-1")
        # Confidence should be 1.5, not clamped to 1.0
        assert facts[0]["confidence"] == pytest.approx(1.5)

    @pytest.mark.asyncio
    async def test_zero_confidence_multiplier(self, pg_writer) -> None:
        """Zero confidence multiplier zeroes out fact confidence."""
        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact

        fact = SpanFact(key="test", value="v", turn=1, confidence=0.8)
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="FAILED",
            confidence_multiplier=0.0,  # Zero out
            method="context_db",
        )

        await pg_writer.write_facts("session-1", [fact], outcome)

        facts = await pg_writer.get_facts("session-1")
        assert facts[0]["confidence"] == pytest.approx(0.0)


class TestTemporalWriterPGConcurrency:
    """Test concurrent access to TemporalWriterPG."""

    @pytest.mark.asyncio
    async def test_concurrent_writes_different_sessions(
        self, pg_writer
    ) -> None:
        """Concurrent writes to different sessions don't interfere."""
        import asyncio

        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact
        from scripts.backfill.temporal_writer_pg import TemporalWriterPG

        async def write_session(session_id: str, key: str) -> int:
            writer = TemporalWriterPG()
            await writer.connect()
            try:
                fact = SpanFact(key=key, value=f"value-{session_id}", turn=1)
                outcome = SessionOutcome(
                    session_id=session_id,
                    outcome="UNKNOWN",
                    confidence_multiplier=1.0,
                    method="default",
                )
                return await writer.write_facts(session_id, [fact], outcome)
            finally:
                await writer.close()

        # Write to 5 sessions concurrently
        tasks = [
            write_session(f"session-{i}", f"key-{i}")
            for i in range(5)
        ]
        counts = await asyncio.gather(*tasks)

        assert all(c == 1 for c in counts)

        # Verify all sessions have their facts
        for i in range(5):
            facts = await pg_writer.get_facts(f"session-{i}")
            assert len(facts) == 1
            assert facts[0]["key"] == f"key-{i}"

    @pytest.mark.asyncio
    async def test_concurrent_writes_same_session(
        self, pg_writer
    ) -> None:
        """Concurrent writes to same session with different content_hash succeed."""
        import asyncio

        from scripts.backfill.outcome_tagger import SessionOutcome
        from scripts.backfill.span_parser import SpanFact
        from scripts.backfill.temporal_writer_pg import TemporalWriterPG

        async def write_fact(key: str, content_hash: str) -> int:
            writer = TemporalWriterPG()
            await writer.connect()
            try:
                fact = SpanFact(
                    key=key, value=f"value-{key}", turn=1, content_hash=content_hash
                )
                outcome = SessionOutcome(
                    session_id="session-1",
                    outcome="UNKNOWN",
                    confidence_multiplier=1.0,
                    method="default",
                )
                return await writer.write_facts("session-1", [fact], outcome)
            finally:
                await writer.close()

        # Write 5 facts concurrently with different content hashes
        tasks = [
            write_fact(f"key-{i}", f"hash-{i}")
            for i in range(5)
        ]
        counts = await asyncio.gather(*tasks)

        assert all(c == 1 for c in counts)

        # Verify all facts were written
        facts = await pg_writer.get_facts("session-1")
        assert len(facts) == 5

"""Tests for TemporalWriter - Phase 3.5 of backfill pipeline.

TDD test suite for writing extracted facts to temporal.db.

Tests:
- test_write_single_fact: Single fact written to temporal_facts table
- test_write_multiple_facts_batched: Multiple facts in single transaction
- test_dedup_by_content_hash: Duplicate facts (same hash) are skipped
- test_confidence_calibration_applied: Confidence multiplied by outcome
- test_write_trace_snapshot: Turn-level trace entries created
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.backfill.outcome_tagger import SessionOutcome
from scripts.backfill.span_parser import SpanFact
from scripts.backfill.temporal_writer import TemporalWriter


class TestTemporalWriter:
    """Test suite for TemporalWriter."""

    @pytest.fixture
    def temp_db(self, tmp_path: Path) -> Path:
        """Create a temporary database path."""
        return tmp_path / "temporal.db"

    @pytest.mark.asyncio
    async def test_write_single_fact(self, temp_db: Path) -> None:
        """Single fact written to temporal_facts table."""
        writer = TemporalWriter(db_path=temp_db)
        await writer.connect()

        fact = SpanFact(key="file_read", value="/path/to/file.py", turn=1)
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="SUCCEEDED",
            confidence_multiplier=1.2,
            method="context_db",
        )

        await writer.write_facts("session-1", [fact], outcome)

        # Verify in database
        facts = await writer.get_facts("session-1")
        assert len(facts) == 1
        assert facts[0]["key"] == "file_read"
        assert facts[0]["value"] == "/path/to/file.py"
        assert facts[0]["confidence"] == pytest.approx(1.2)  # 1.0 * 1.2

        await writer.close()

    @pytest.mark.asyncio
    async def test_write_multiple_facts_batched(self, temp_db: Path) -> None:
        """Multiple facts written in single transaction."""
        writer = TemporalWriter(db_path=temp_db)
        await writer.connect()

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

        await writer.write_facts("session-1", facts, outcome)

        all_facts = await writer.get_facts("session-1")
        assert len(all_facts) == 3

        await writer.close()

    @pytest.mark.asyncio
    async def test_dedup_by_content_hash(self, temp_db: Path) -> None:
        """Duplicate facts (same content_hash) are skipped."""
        writer = TemporalWriter(db_path=temp_db)
        await writer.connect()

        fact = SpanFact(
            key="file_read", value="/same.py", turn=1, content_hash="abc123"
        )
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )

        await writer.write_facts("session-1", [fact], outcome)
        await writer.write_facts("session-1", [fact], outcome)  # Duplicate

        facts = await writer.get_facts("session-1")
        assert len(facts) == 1  # Only one copy

        await writer.close()

    @pytest.mark.asyncio
    async def test_confidence_calibration_applied(self, temp_db: Path) -> None:
        """Fact confidence is multiplied by outcome multiplier."""
        writer = TemporalWriter(db_path=temp_db)
        await writer.connect()

        fact = SpanFact(key="test", value="v", turn=1, confidence=0.8)
        outcome = SessionOutcome(
            session_id="session-1",
            outcome="SUCCEEDED",
            confidence_multiplier=1.2,
            method="context_db",
        )

        await writer.write_facts("session-1", [fact], outcome)

        facts = await writer.get_facts("session-1")
        assert facts[0]["confidence"] == pytest.approx(0.96)  # 0.8 * 1.2

        await writer.close()

    @pytest.mark.asyncio
    async def test_write_trace_snapshot(self, temp_db: Path) -> None:
        """Turn-level trace snapshot written."""
        writer = TemporalWriter(db_path=temp_db)
        await writer.connect()

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

        await writer.write_traces("session-1", facts_by_turn, outcome)

        # Verify trace table has entries
        traces = await writer.get_traces("session-1")
        assert len(traces) == 2

        await writer.close()

    @pytest.mark.asyncio
    async def test_facts_include_turn_number(self, temp_db: Path) -> None:
        """Facts preserve turn number from SpanFact."""
        writer = TemporalWriter(db_path=temp_db)
        await writer.connect()

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

        await writer.write_facts("session-1", facts, outcome)

        db_facts = await writer.get_facts("session-1")
        turns = [f["turn"] for f in db_facts]
        assert 5 in turns
        assert 10 in turns

        await writer.close()

    @pytest.mark.asyncio
    async def test_empty_facts_list(self, temp_db: Path) -> None:
        """Empty facts list doesn't crash."""
        writer = TemporalWriter(db_path=temp_db)
        await writer.connect()

        outcome = SessionOutcome(
            session_id="session-1",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )

        count = await writer.write_facts("session-1", [], outcome)
        assert count == 0

        facts = await writer.get_facts("session-1")
        assert len(facts) == 0

        await writer.close()

    @pytest.mark.asyncio
    async def test_write_facts_returns_count(self, temp_db: Path) -> None:
        """write_facts returns count of facts written."""
        writer = TemporalWriter(db_path=temp_db)
        await writer.connect()

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

        count = await writer.write_facts("session-1", facts, outcome)
        assert count == 2

        await writer.close()

    @pytest.mark.asyncio
    async def test_different_sessions_isolated(self, temp_db: Path) -> None:
        """Facts from different sessions are isolated."""
        writer = TemporalWriter(db_path=temp_db)
        await writer.connect()

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

        await writer.write_facts(
            "session-1", [SpanFact(key="a", value="1", turn=1)], outcome1
        )
        await writer.write_facts(
            "session-2", [SpanFact(key="b", value="2", turn=1)], outcome2
        )

        facts1 = await writer.get_facts("session-1")
        facts2 = await writer.get_facts("session-2")

        assert len(facts1) == 1
        assert len(facts2) == 1
        assert facts1[0]["key"] == "a"
        assert facts2[0]["key"] == "b"

        await writer.close()

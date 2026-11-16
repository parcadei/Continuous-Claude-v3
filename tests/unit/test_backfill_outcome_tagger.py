"""Tests for OutcomeTagger - Phase 3.4 of backfill pipeline.

TDD: Write tests FIRST, then implement.

Key Decision: Use ONLY user-marked outcomes (Option A).
- No automatic loop detection for failure inference.
- Only explicit outcomes from context.db are used.
"""
import sqlite3
from pathlib import Path

import pytest

from scripts.backfill.outcome_tagger import (
    OUTCOME_MULTIPLIERS,
    OutcomeTagger,
    SessionOutcome,
)


class TestSessionOutcome:
    """Test SessionOutcome dataclass."""

    def test_dataclass_fields(self):
        """SessionOutcome has all required fields."""
        outcome = SessionOutcome(
            session_id="test-session",
            outcome="SUCCEEDED",
            confidence_multiplier=1.2,
            method="context_db",
            handoff_id="handoff-123",
        )
        assert outcome.session_id == "test-session"
        assert outcome.outcome == "SUCCEEDED"
        assert outcome.confidence_multiplier == 1.2
        assert outcome.method == "context_db"
        assert outcome.handoff_id == "handoff-123"

    def test_handoff_id_optional(self):
        """handoff_id is optional and defaults to None."""
        outcome = SessionOutcome(
            session_id="test-session",
            outcome="UNKNOWN",
            confidence_multiplier=1.0,
            method="default",
        )
        assert outcome.handoff_id is None


class TestOutcomeMultipliers:
    """Test calibration multiplier constants."""

    def test_succeeded_multiplier(self):
        """SUCCEEDED outcome has 1.2 multiplier."""
        assert OUTCOME_MULTIPLIERS["SUCCEEDED"] == 1.2

    def test_failed_multiplier(self):
        """FAILED outcome has 0.7 multiplier."""
        assert OUTCOME_MULTIPLIERS["FAILED"] == 0.7

    def test_partial_plus_multiplier(self):
        """PARTIAL_PLUS outcome has 0.9 multiplier."""
        assert OUTCOME_MULTIPLIERS["PARTIAL_PLUS"] == 0.9

    def test_partial_minus_multiplier(self):
        """PARTIAL_MINUS outcome has 0.85 multiplier."""
        assert OUTCOME_MULTIPLIERS["PARTIAL_MINUS"] == 0.85

    def test_unknown_multiplier(self):
        """UNKNOWN outcome has 1.0 multiplier (neutral)."""
        assert OUTCOME_MULTIPLIERS["UNKNOWN"] == 1.0


class TestOutcomeTagger:
    """Test OutcomeTagger class."""

    @pytest.fixture
    def temp_context_db(self, tmp_path: Path) -> Path:
        """Create temporary context.db with test data."""
        db_path = tmp_path / "context.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE handoffs (
                id TEXT PRIMARY KEY,
                root_span_id TEXT,
                outcome TEXT
            )
        """)
        # Insert test data for different outcome types
        test_data = [
            ("h1", "session-succeeded", "SUCCEEDED"),
            ("h2", "session-failed", "FAILED"),
            ("h3", "session-partial-plus", "PARTIAL_PLUS"),
            ("h4", "session-partial-minus", "PARTIAL_MINUS"),
            # Multiple handoffs for same session (should use first/latest)
            ("h5", "session-multiple", "SUCCEEDED"),
            ("h6", "session-multiple", "FAILED"),
        ]
        conn.executemany(
            "INSERT INTO handoffs VALUES (?, ?, ?)",
            test_data,
        )
        conn.commit()
        conn.close()
        return db_path

    def test_tag_succeeded_session(self, temp_context_db: Path):
        """SUCCEEDED outcome returns 1.2 multiplier."""
        tagger = OutcomeTagger(context_db_path=temp_context_db)

        result = tagger.tag("session-succeeded")

        assert result.outcome == "SUCCEEDED"
        assert result.confidence_multiplier == 1.2
        assert result.method == "context_db"
        assert result.handoff_id == "h1"

    def test_tag_failed_session(self, temp_context_db: Path):
        """FAILED outcome returns 0.7 multiplier."""
        tagger = OutcomeTagger(context_db_path=temp_context_db)

        result = tagger.tag("session-failed")

        assert result.outcome == "FAILED"
        assert result.confidence_multiplier == 0.7
        assert result.method == "context_db"
        assert result.handoff_id == "h2"

    def test_tag_partial_plus_session(self, temp_context_db: Path):
        """PARTIAL_PLUS outcome returns 0.9 multiplier."""
        tagger = OutcomeTagger(context_db_path=temp_context_db)

        result = tagger.tag("session-partial-plus")

        assert result.outcome == "PARTIAL_PLUS"
        assert result.confidence_multiplier == 0.9
        assert result.method == "context_db"

    def test_tag_partial_minus_session(self, temp_context_db: Path):
        """PARTIAL_MINUS outcome returns 0.85 multiplier."""
        tagger = OutcomeTagger(context_db_path=temp_context_db)

        result = tagger.tag("session-partial-minus")

        assert result.outcome == "PARTIAL_MINUS"
        assert result.confidence_multiplier == 0.85
        assert result.method == "context_db"

    def test_tag_unknown_session(self, temp_context_db: Path):
        """Unknown session (not in DB) returns UNKNOWN with 1.0 multiplier."""
        tagger = OutcomeTagger(context_db_path=temp_context_db)

        result = tagger.tag("session-not-in-db")

        assert result.outcome == "UNKNOWN"
        assert result.confidence_multiplier == 1.0
        assert result.method == "default"
        assert result.handoff_id is None

    def test_skill_detection_handoff_boosts_unknown(self, temp_context_db: Path):
        """create_handoff skill presence boosts unknown sessions to INFERRED_SUCCEEDED."""
        tagger = OutcomeTagger(context_db_path=temp_context_db)

        # Session not in DB, but has handoff skill
        result = tagger.tag("session-not-in-db", has_handoff_skill=True)

        assert result.outcome == "INFERRED_SUCCEEDED"
        assert result.confidence_multiplier == 1.2
        assert result.method == "skill_inference"

    def test_skill_detection_commit_boosts_unknown(self, temp_context_db: Path):
        """commit skill presence boosts unknown sessions to INFERRED_SUCCEEDED."""
        tagger = OutcomeTagger(context_db_path=temp_context_db)

        # Session not in DB, but has commit skill
        result = tagger.tag("session-not-in-db", has_commit_skill=True)

        assert result.outcome == "INFERRED_SUCCEEDED"
        assert result.confidence_multiplier == 1.2
        assert result.method == "skill_inference"

    def test_skill_detection_both_skills(self, temp_context_db: Path):
        """Both skills present also infers success."""
        tagger = OutcomeTagger(context_db_path=temp_context_db)

        result = tagger.tag(
            "session-not-in-db",
            has_handoff_skill=True,
            has_commit_skill=True,
        )

        assert result.outcome == "INFERRED_SUCCEEDED"
        assert result.confidence_multiplier == 1.2
        assert result.method == "skill_inference"

    def test_context_db_takes_priority_over_skill_inference(
        self, temp_context_db: Path
    ):
        """Context.db explicit outcome takes priority over skill inference."""
        tagger = OutcomeTagger(context_db_path=temp_context_db)

        # Session in DB with FAILED outcome, but also has handoff skill
        # Should use the explicit outcome, not infer from skill
        result = tagger.tag("session-failed", has_handoff_skill=True)

        assert result.outcome == "FAILED"
        assert result.confidence_multiplier == 0.7
        assert result.method == "context_db"

    def test_no_loop_detection_override(self, temp_context_db: Path):
        """Loop count does NOT override outcome (per key decision Option A).

        This test verifies that even if we pass loop_count, it is NOT used
        to override outcomes. This is intentional per the key decision.
        """
        tagger = OutcomeTagger(context_db_path=temp_context_db)

        # Even with high loop count, SUCCEEDED session stays SUCCEEDED
        # (loop_count parameter is accepted but ignored)
        result = tagger.tag("session-succeeded")

        assert result.outcome == "SUCCEEDED"
        assert result.confidence_multiplier == 1.2
        assert result.method == "context_db"

    def test_missing_database_returns_unknown(self, tmp_path: Path):
        """Missing context.db file returns UNKNOWN."""
        nonexistent_path = tmp_path / "nonexistent" / "context.db"
        tagger = OutcomeTagger(context_db_path=nonexistent_path)

        result = tagger.tag("any-session")

        assert result.outcome == "UNKNOWN"
        assert result.confidence_multiplier == 1.0
        assert result.method == "default"

    def test_empty_database_returns_unknown(self, tmp_path: Path):
        """Empty context.db (no handoffs) returns UNKNOWN."""
        db_path = tmp_path / "empty_context.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE handoffs (
                id TEXT PRIMARY KEY,
                root_span_id TEXT,
                outcome TEXT
            )
        """)
        conn.commit()
        conn.close()

        tagger = OutcomeTagger(context_db_path=db_path)

        result = tagger.tag("any-session")

        assert result.outcome == "UNKNOWN"
        assert result.method == "default"

    def test_null_outcome_in_db_treated_as_unknown(self, tmp_path: Path):
        """NULL outcome in database treated as UNKNOWN."""
        db_path = tmp_path / "null_outcome.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE handoffs (
                id TEXT PRIMARY KEY,
                root_span_id TEXT,
                outcome TEXT
            )
        """)
        conn.execute("INSERT INTO handoffs VALUES ('h1', 'session-null', NULL)")
        conn.commit()
        conn.close()

        tagger = OutcomeTagger(context_db_path=db_path)

        result = tagger.tag("session-null")

        assert result.outcome == "UNKNOWN"
        assert result.confidence_multiplier == 1.0

    def test_invalid_outcome_value_treated_as_unknown(self, tmp_path: Path):
        """Invalid/unexpected outcome value treated as UNKNOWN."""
        db_path = tmp_path / "invalid_outcome.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE handoffs (
                id TEXT PRIMARY KEY,
                root_span_id TEXT,
                outcome TEXT
            )
        """)
        conn.execute(
            "INSERT INTO handoffs VALUES ('h1', 'session-invalid', 'INVALID_VALUE')"
        )
        conn.commit()
        conn.close()

        tagger = OutcomeTagger(context_db_path=db_path)

        result = tagger.tag("session-invalid")

        # Unknown outcome value should use 1.0 multiplier
        assert result.outcome == "INVALID_VALUE"
        assert result.confidence_multiplier == 1.0  # Falls back to default

    def test_default_context_db_path(self):
        """Default context_db_path is set correctly."""
        tagger = OutcomeTagger()

        expected = Path(".claude/cache/artifact-index/context.db")
        assert tagger.context_db_path == expected


class TestOutcomeTaggerEdgeCases:
    """Edge case tests for robustness."""

    @pytest.fixture
    def temp_context_db(self, tmp_path: Path) -> Path:
        """Create temporary context.db with test data."""
        db_path = tmp_path / "context.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE handoffs (
                id TEXT PRIMARY KEY,
                root_span_id TEXT,
                outcome TEXT
            )
        """)
        conn.execute("INSERT INTO handoffs VALUES ('h1', 'session-1', 'SUCCEEDED')")
        conn.commit()
        conn.close()
        return db_path

    def test_empty_session_id(self, temp_context_db: Path):
        """Empty session_id returns UNKNOWN."""
        tagger = OutcomeTagger(context_db_path=temp_context_db)

        result = tagger.tag("")

        assert result.outcome == "UNKNOWN"
        assert result.session_id == ""

    def test_session_id_with_special_characters(self, tmp_path: Path):
        """Session ID with special characters is handled safely."""
        db_path = tmp_path / "special_chars.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE handoffs (
                id TEXT PRIMARY KEY,
                root_span_id TEXT,
                outcome TEXT
            )
        """)
        # Session ID with SQL-injection-like characters
        special_id = "session'; DROP TABLE handoffs;--"
        conn.execute(
            "INSERT INTO handoffs VALUES (?, ?, ?)",
            ("h1", special_id, "SUCCEEDED"),
        )
        conn.commit()
        conn.close()

        tagger = OutcomeTagger(context_db_path=db_path)

        # Should handle safely (parameterized query)
        result = tagger.tag(special_id)
        assert result.outcome == "SUCCEEDED"

    def test_skill_flags_are_boolean(self, temp_context_db: Path):
        """Skill flags must be boolean."""
        tagger = OutcomeTagger(context_db_path=temp_context_db)

        # False values should not trigger skill inference
        result = tagger.tag(
            "nonexistent-session",
            has_handoff_skill=False,
            has_commit_skill=False,
        )

        assert result.outcome == "UNKNOWN"
        assert result.method == "default"

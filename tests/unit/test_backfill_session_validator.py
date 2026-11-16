"""Tests for backfill session validation.

TDD: Write tests first, then implementation.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiosqlite


class TestSessionValidator:
    """Test session validation for backfill pipeline."""

    @pytest.mark.asyncio
    async def test_valid_session_passes(self):
        """Session with spans and no errors passes validation."""
        from scripts.backfill.session_validator import SessionValidator, ValidationResult

        # Mock Braintrust API to return valid session data
        mock_stats = {
            "span_count": 50,
            "tool_count": 20,
            "llm_count": 15,
        }

        validator = SessionValidator()

        with patch.object(validator, "_query_braintrust_stats", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_stats
            with patch.object(validator, "_check_already_processed", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = False

                result = await validator.validate("root-span-123", min_spans=5)

        assert result.is_valid
        assert result.span_count >= 5
        assert result.error is None
        assert result.session_id == "root-span-123"

    @pytest.mark.asyncio
    async def test_empty_session_fails(self):
        """Session with 0 spans fails validation."""
        from scripts.backfill.session_validator import SessionValidator, ValidationResult

        # Mock Braintrust API to return empty session
        mock_stats = {
            "span_count": 0,
            "tool_count": 0,
            "llm_count": 0,
        }

        validator = SessionValidator()

        with patch.object(validator, "_query_braintrust_stats", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_stats
            with patch.object(validator, "_check_already_processed", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = False

                result = await validator.validate("empty-session-id", min_spans=5)

        assert not result.is_valid
        assert result.error == "insufficient_spans"
        assert result.span_count == 0

    @pytest.mark.asyncio
    async def test_partial_session_flags(self):
        """Session with spans but missing tool spans flags partial."""
        from scripts.backfill.session_validator import SessionValidator, ValidationResult

        # Mock session with spans but no tool spans
        mock_stats = {
            "span_count": 10,
            "tool_count": 0,  # No tool spans
            "llm_count": 5,
        }

        validator = SessionValidator()

        with patch.object(validator, "_query_braintrust_stats", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_stats
            with patch.object(validator, "_check_already_processed", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = False

                result = await validator.validate("partial-session", min_spans=1)

        assert result.is_valid  # Still valid, just flagged
        assert result.has_tool_spans is False
        assert "no_tool_spans" in result.warnings

    @pytest.mark.asyncio
    async def test_already_processed_skips(self, tmp_path):
        """Session already in temporal.db is skipped."""
        from scripts.backfill.session_validator import SessionValidator, ValidationResult

        # Create a temp database with processed sessions table
        db_path = tmp_path / "temporal.db"
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS processed_sessions (
                    session_id TEXT PRIMARY KEY,
                    processed_at TEXT
                )
            """)
            await db.execute(
                "INSERT INTO processed_sessions (session_id, processed_at) VALUES (?, datetime('now'))",
                ("already-done-session",)
            )
            await db.commit()

        validator = SessionValidator(temporal_db_path=str(db_path))

        result = await validator.validate("already-done-session", min_spans=1)

        assert not result.is_valid
        assert result.error == "already_processed"

    @pytest.mark.asyncio
    async def test_braintrust_api_error_handled(self):
        """API errors are caught and reported."""
        from scripts.backfill.session_validator import SessionValidator, ValidationResult

        validator = SessionValidator()

        with patch.object(validator, "_query_braintrust_stats", new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = Exception("Connection timeout")
            with patch.object(validator, "_check_already_processed", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = False

                result = await validator.validate("invalid-format-id", min_spans=1)

        assert not result.is_valid
        assert "api_error" in result.error

    @pytest.mark.asyncio
    async def test_mark_processed_creates_entry(self, tmp_path):
        """_mark_processed creates entry in database."""
        from scripts.backfill.session_validator import SessionValidator

        db_path = tmp_path / "temporal.db"

        validator = SessionValidator(temporal_db_path=str(db_path))

        # Mark a session as processed
        await validator._mark_processed("new-session-123")

        # Verify it was recorded
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT session_id FROM processed_sessions WHERE session_id = ?",
                ("new-session-123",)
            )
            row = await cursor.fetchone()

        assert row is not None
        assert row[0] == "new-session-123"

    @pytest.mark.asyncio
    async def test_session_below_min_spans_fails(self):
        """Session with spans below minimum threshold fails."""
        from scripts.backfill.session_validator import SessionValidator

        mock_stats = {
            "span_count": 3,  # Below min_spans=5
            "tool_count": 2,
            "llm_count": 1,
        }

        validator = SessionValidator()

        with patch.object(validator, "_query_braintrust_stats", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_stats
            with patch.object(validator, "_check_already_processed", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = False

                result = await validator.validate("small-session", min_spans=5)

        assert not result.is_valid
        assert result.error == "insufficient_spans"
        assert result.span_count == 3

    @pytest.mark.asyncio
    async def test_session_with_no_llm_spans_warns(self):
        """Session with no LLM spans adds warning but still valid."""
        from scripts.backfill.session_validator import SessionValidator

        mock_stats = {
            "span_count": 10,
            "tool_count": 8,
            "llm_count": 0,  # No LLM spans
        }

        validator = SessionValidator()

        with patch.object(validator, "_query_braintrust_stats", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_stats
            with patch.object(validator, "_check_already_processed", new_callable=AsyncMock) as mock_check:
                mock_check.return_value = False

                result = await validator.validate("no-llm-session", min_spans=5)

        assert result.is_valid
        assert result.has_llm_spans is False
        assert "no_llm_spans" in result.warnings

    @pytest.mark.asyncio
    async def test_validation_result_dataclass_fields(self):
        """ValidationResult has all required fields."""
        from scripts.backfill.session_validator import ValidationResult

        result = ValidationResult(
            is_valid=True,
            session_id="test-session",
            span_count=50,
            has_tool_spans=True,
            has_llm_spans=True,
            warnings=["some_warning"],
            error=None
        )

        assert result.is_valid is True
        assert result.session_id == "test-session"
        assert result.span_count == 50
        assert result.has_tool_spans is True
        assert result.has_llm_spans is True
        assert result.warnings == ["some_warning"]
        assert result.error is None

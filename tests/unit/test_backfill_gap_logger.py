"""Unit tests for gap logger - Phase 3.6.

Tests gap tracking for skipped sessions during backfill processing.
"""
import json
import pytest
from pathlib import Path

from scripts.backfill.gap_logger import GapLogger, GapReason


class TestGapLogger:
    """Tests for GapLogger class."""

    @pytest.fixture
    def temp_log(self, tmp_path: Path) -> Path:
        """Create temporary log path."""
        return tmp_path / "gaps.jsonl"

    def test_log_validation_failure(self, temp_log: Path) -> None:
        """Validation failures logged with reason."""
        logger = GapLogger(log_path=temp_log)

        logger.log_gap("session-1", GapReason.INSUFFICIENT_SPANS, span_count=2)

        entries = logger.read_gaps()
        assert len(entries) == 1
        assert entries[0]["session_id"] == "session-1"
        assert entries[0]["reason"] == "insufficient_spans"
        assert entries[0]["details"]["span_count"] == 2

    def test_log_already_processed(self, temp_log: Path) -> None:
        """Already processed sessions logged."""
        logger = GapLogger(log_path=temp_log)

        logger.log_gap("session-2", GapReason.ALREADY_PROCESSED)

        entries = logger.read_gaps()
        assert len(entries) == 1
        assert entries[0]["session_id"] == "session-2"
        assert entries[0]["reason"] == "already_processed"

    def test_log_api_error(self, temp_log: Path) -> None:
        """API errors logged with message."""
        logger = GapLogger(log_path=temp_log)

        logger.log_gap("session-3", GapReason.API_ERROR, error_message="Connection timeout")

        entries = logger.read_gaps()
        assert len(entries) == 1
        assert entries[0]["session_id"] == "session-3"
        assert entries[0]["reason"] == "api_error"
        assert entries[0]["details"]["error_message"] == "Connection timeout"

    def test_multiple_gaps_appended(self, temp_log: Path) -> None:
        """Multiple gaps appended to same file."""
        logger = GapLogger(log_path=temp_log)

        logger.log_gap("s1", GapReason.INSUFFICIENT_SPANS)
        logger.log_gap("s2", GapReason.NO_TOOL_SPANS)

        entries = logger.read_gaps()
        assert len(entries) == 2
        assert entries[0]["session_id"] == "s1"
        assert entries[0]["reason"] == "insufficient_spans"
        assert entries[1]["session_id"] == "s2"
        assert entries[1]["reason"] == "no_tool_spans"

    def test_summary_statistics(self, temp_log: Path) -> None:
        """Summary stats computed correctly."""
        logger = GapLogger(log_path=temp_log)

        logger.log_gap("s1", GapReason.INSUFFICIENT_SPANS)
        logger.log_gap("s2", GapReason.INSUFFICIENT_SPANS)
        logger.log_gap("s3", GapReason.API_ERROR)

        summary = logger.get_summary()
        assert summary["total"] == 3
        assert summary["by_reason"]["insufficient_spans"] == 2
        assert summary["by_reason"]["api_error"] == 1

    def test_log_no_tool_spans(self, temp_log: Path) -> None:
        """No tool spans reason logged correctly."""
        logger = GapLogger(log_path=temp_log)

        logger.log_gap("session-4", GapReason.NO_TOOL_SPANS, has_llm_spans=True)

        entries = logger.read_gaps()
        assert len(entries) == 1
        assert entries[0]["reason"] == "no_tool_spans"
        assert entries[0]["details"]["has_llm_spans"] is True

    def test_log_parse_error(self, temp_log: Path) -> None:
        """Parse errors logged with error details."""
        logger = GapLogger(log_path=temp_log)

        logger.log_gap("session-5", GapReason.PARSE_ERROR, error_type="JSONDecodeError")

        entries = logger.read_gaps()
        assert len(entries) == 1
        assert entries[0]["reason"] == "parse_error"
        assert entries[0]["details"]["error_type"] == "JSONDecodeError"

    def test_log_timeout(self, temp_log: Path) -> None:
        """Timeout logged with duration."""
        logger = GapLogger(log_path=temp_log)

        logger.log_gap("session-6", GapReason.TIMEOUT, duration_seconds=30.5)

        entries = logger.read_gaps()
        assert len(entries) == 1
        assert entries[0]["reason"] == "timeout"
        assert entries[0]["details"]["duration_seconds"] == 30.5

    def test_read_gaps_empty_file(self, temp_log: Path) -> None:
        """Reading gaps from non-existent file returns empty list."""
        logger = GapLogger(log_path=temp_log)

        entries = logger.read_gaps()
        assert entries == []

    def test_get_summary_empty_log(self, temp_log: Path) -> None:
        """Summary on empty log returns zero counts."""
        logger = GapLogger(log_path=temp_log)

        summary = logger.get_summary()
        assert summary["total"] == 0
        assert summary["by_reason"] == {}

    def test_log_entry_has_timestamp(self, temp_log: Path) -> None:
        """Each log entry includes timestamp."""
        logger = GapLogger(log_path=temp_log)

        logger.log_gap("session-7", GapReason.INSUFFICIENT_SPANS)

        entries = logger.read_gaps()
        assert len(entries) == 1
        assert "timestamp" in entries[0]
        # Timestamp should be ISO format
        assert "T" in entries[0]["timestamp"]

    def test_log_creates_parent_directory(self, tmp_path: Path) -> None:
        """Log file creation creates parent directories if needed."""
        nested_path = tmp_path / "deep" / "nested" / "gaps.jsonl"
        logger = GapLogger(log_path=nested_path)

        logger.log_gap("session-8", GapReason.API_ERROR)

        assert nested_path.exists()
        entries = logger.read_gaps()
        assert len(entries) == 1

    def test_summary_all_reason_types(self, temp_log: Path) -> None:
        """Summary handles all reason types."""
        logger = GapLogger(log_path=temp_log)

        # Log one of each reason type
        for reason in GapReason:
            logger.log_gap(f"session-{reason.value}", reason)

        summary = logger.get_summary()
        assert summary["total"] == len(GapReason)
        # Each reason should appear exactly once
        for reason in GapReason:
            assert summary["by_reason"][reason.value] == 1

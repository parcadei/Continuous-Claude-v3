"""Tests for Phase 3.8: Calibration Analyzer.

TDD tests for the CalibrationAnalyzer that correlates facts to session outcomes
to generate calibration tables for confidence scoring.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts.backfill.calibration import CalibrationAnalyzer


class TestCalibrationAnalyzer:
    """Test suite for CalibrationAnalyzer."""

    @pytest.fixture
    def temp_temporal_db(self, tmp_path: Path) -> Path:
        """Create temp temporal.db with test data."""
        db_path = tmp_path / "temporal.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE temporal_facts (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                key TEXT,
                value TEXT,
                confidence REAL
            )
        """)
        # Session 1 - succeeded (will be linked via context.db)
        conn.execute(
            "INSERT INTO temporal_facts VALUES ('f1', 's1', 'file_written', 'a.py', 1.2)"
        )
        conn.execute(
            "INSERT INTO temporal_facts VALUES ('f2', 's1', 'test_passed', 'true', 1.2)"
        )
        # Session 2 - failed (will be linked via context.db)
        conn.execute(
            "INSERT INTO temporal_facts VALUES ('f3', 's2', 'loop_count', '400', 0.7)"
        )
        conn.execute(
            "INSERT INTO temporal_facts VALUES ('f4', 's2', 'error_occurred', 'true', 0.7)"
        )
        # Session 3 - succeeded (mixed facts)
        conn.execute(
            "INSERT INTO temporal_facts VALUES ('f5', 's3', 'file_written', 'b.py', 1.2)"
        )
        conn.execute(
            "INSERT INTO temporal_facts VALUES ('f6', 's3', 'test_passed', 'true', 1.2)"
        )
        conn.commit()
        conn.close()
        return db_path

    @pytest.fixture
    def temp_context_db(self, tmp_path: Path) -> Path:
        """Create temp context.db with outcomes (handoffs table)."""
        db_path = tmp_path / "context.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE handoffs (id TEXT, root_span_id TEXT, outcome TEXT)"
        )
        conn.execute("INSERT INTO handoffs VALUES ('h1', 's1', 'SUCCEEDED')")
        conn.execute("INSERT INTO handoffs VALUES ('h2', 's2', 'FAILED')")
        conn.execute("INSERT INTO handoffs VALUES ('h3', 's3', 'SUCCEEDED')")
        conn.commit()
        conn.close()
        return db_path

    def test_success_fact_correlation(
        self, temp_temporal_db: Path, temp_context_db: Path
    ) -> None:
        """Facts from succeeded sessions tracked in success_patterns."""
        analyzer = CalibrationAnalyzer(
            temporal_db=temp_temporal_db,
            context_db=temp_context_db,
        )

        report = analyzer.analyze()

        assert report["sessions_analyzed"] >= 2
        assert "file_written" in report["success_patterns"]
        assert report["success_patterns"]["file_written"] >= 1
        assert "test_passed" in report["success_patterns"]

    def test_failure_fact_correlation(
        self, temp_temporal_db: Path, temp_context_db: Path
    ) -> None:
        """Facts from failed sessions tracked in failure_patterns."""
        analyzer = CalibrationAnalyzer(
            temporal_db=temp_temporal_db,
            context_db=temp_context_db,
        )

        report = analyzer.analyze()

        assert "loop_count" in report["failure_patterns"]
        assert report["failure_patterns"]["loop_count"] >= 1
        assert "error_occurred" in report["failure_patterns"]

    def test_generate_calibration_table(
        self, temp_temporal_db: Path, temp_context_db: Path
    ) -> None:
        """Generate calibration table with success_rate and recommended_multiplier."""
        analyzer = CalibrationAnalyzer(
            temporal_db=temp_temporal_db,
            context_db=temp_context_db,
        )

        table = analyzer.get_calibration_table()

        # Facts appearing in SUCCEEDED sessions get boost
        assert "file_written" in table
        assert table["file_written"]["success_rate"] > 0.5
        assert table["file_written"]["count"] >= 1
        assert "recommended_multiplier" in table["file_written"]
        assert table["file_written"]["recommended_multiplier"] >= 1.0

        # Facts appearing only in FAILED sessions get penalty
        assert "loop_count" in table
        assert table["loop_count"]["success_rate"] < 0.5
        assert table["loop_count"]["recommended_multiplier"] < 1.0

    def test_handle_empty_temporal_db(self, tmp_path: Path) -> None:
        """Empty temporal.db returns empty report without error."""
        temporal_db = tmp_path / "empty_temporal.db"
        context_db = tmp_path / "empty_context.db"

        # Create empty databases with correct schema
        conn = sqlite3.connect(temporal_db)
        conn.execute("""
            CREATE TABLE temporal_facts (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                key TEXT,
                value TEXT,
                confidence REAL
            )
        """)
        conn.commit()
        conn.close()

        conn = sqlite3.connect(context_db)
        conn.execute(
            "CREATE TABLE handoffs (id TEXT, root_span_id TEXT, outcome TEXT)"
        )
        conn.commit()
        conn.close()

        analyzer = CalibrationAnalyzer(
            temporal_db=temporal_db,
            context_db=context_db,
        )

        report = analyzer.analyze()

        assert report["sessions_analyzed"] == 0
        assert report["success_patterns"] == {}
        assert report["failure_patterns"] == {}

    def test_handle_empty_context_db(
        self, temp_temporal_db: Path, tmp_path: Path
    ) -> None:
        """Empty context.db treats all sessions as UNKNOWN outcome."""
        context_db = tmp_path / "empty_context.db"
        conn = sqlite3.connect(context_db)
        conn.execute(
            "CREATE TABLE handoffs (id TEXT, root_span_id TEXT, outcome TEXT)"
        )
        conn.commit()
        conn.close()

        analyzer = CalibrationAnalyzer(
            temporal_db=temp_temporal_db,
            context_db=context_db,
        )

        report = analyzer.analyze()

        # Sessions exist but have no known outcome
        assert report["sessions_analyzed"] >= 0
        # No facts should be in success or failure patterns (all UNKNOWN)
        assert report["success_patterns"] == {}
        assert report["failure_patterns"] == {}

    def test_overall_stats_included(
        self, temp_temporal_db: Path, temp_context_db: Path
    ) -> None:
        """Report includes overall statistics."""
        analyzer = CalibrationAnalyzer(
            temporal_db=temp_temporal_db,
            context_db=temp_context_db,
        )

        report = analyzer.analyze()

        assert "overall_stats" in report
        assert "total_facts" in report["overall_stats"]
        assert "succeeded_sessions" in report["overall_stats"]
        assert "failed_sessions" in report["overall_stats"]

    def test_calibration_table_count_accuracy(
        self, temp_temporal_db: Path, temp_context_db: Path
    ) -> None:
        """Calibration table count reflects actual occurrences."""
        analyzer = CalibrationAnalyzer(
            temporal_db=temp_temporal_db,
            context_db=temp_context_db,
        )

        table = analyzer.get_calibration_table()

        # file_written appears in 2 sessions (s1 and s3)
        assert table["file_written"]["count"] == 2
        # loop_count appears in 1 session (s2)
        assert table["loop_count"]["count"] == 1

    def test_multiplier_calculation(
        self, temp_temporal_db: Path, temp_context_db: Path
    ) -> None:
        """Recommended multiplier is derived from success rate."""
        analyzer = CalibrationAnalyzer(
            temporal_db=temp_temporal_db,
            context_db=temp_context_db,
        )

        table = analyzer.get_calibration_table()

        # file_written: 2 succeeded, 0 failed -> 100% success -> multiplier ~1.2
        assert table["file_written"]["success_rate"] == 1.0
        assert table["file_written"]["recommended_multiplier"] >= 1.1

        # loop_count: 0 succeeded, 1 failed -> 0% success -> multiplier ~0.7
        assert table["loop_count"]["success_rate"] == 0.0
        assert table["loop_count"]["recommended_multiplier"] <= 0.8

    def test_missing_database_files(self, tmp_path: Path) -> None:
        """Missing database files handled gracefully."""
        analyzer = CalibrationAnalyzer(
            temporal_db=tmp_path / "nonexistent.db",
            context_db=tmp_path / "also_nonexistent.db",
        )

        # Should not raise, but return empty report
        report = analyzer.analyze()
        assert report["sessions_analyzed"] == 0
        assert report["success_patterns"] == {}
        assert report["failure_patterns"] == {}

        table = analyzer.get_calibration_table()
        assert table == {}

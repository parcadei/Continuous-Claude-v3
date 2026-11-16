"""Calibration analysis for temporal memory.

Phase 3.8 of backfill pipeline.

Correlates facts to session outcomes to determine calibration multipliers.
Analyzes which fact patterns correlate with successful vs failed sessions
to recommend confidence adjustments for future fact scoring.

Usage:
    analyzer = CalibrationAnalyzer(
        temporal_db=Path("temporal.db"),
        context_db=Path("context.db"),
    )
    report = analyzer.analyze()
    table = analyzer.get_calibration_table()
"""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

# Multiplier boundaries based on research in plan.md
MIN_MULTIPLIER = 0.7
MAX_MULTIPLIER = 1.2
NEUTRAL_MULTIPLIER = 1.0


class CalibrationAnalyzer:
    """Analyze fact-outcome correlations for confidence calibration.

    Reads from temporal.db (facts) and context.db (handoff outcomes) to
    determine which fact patterns correlate with success/failure, and
    generate recommended confidence multipliers.
    """

    def __init__(
        self,
        temporal_db: Path | None = None,
        context_db: Path | None = None,
    ):
        """Initialize CalibrationAnalyzer.

        Args:
            temporal_db: Path to temporal.db with temporal_facts table.
                Defaults to .claude/cache/temporal-memory/temporal.db
            context_db: Path to context.db with handoffs table.
                Defaults to .claude/cache/artifact-index/context.db
        """
        self.temporal_db = temporal_db or Path(
            ".claude/cache/temporal-memory/temporal.db"
        )
        self.context_db = context_db or Path(
            ".claude/cache/artifact-index/context.db"
        )

    def analyze(self) -> dict[str, Any]:
        """Analyze correlations between facts and outcomes.

        Returns:
            Report dictionary with:
            - sessions_analyzed: Number of unique sessions processed
            - success_patterns: {fact_key: count} for SUCCEEDED sessions
            - failure_patterns: {fact_key: count} for FAILED sessions
            - overall_stats: Summary statistics
        """
        # Handle missing databases gracefully
        if not self.temporal_db.exists() or not self.context_db.exists():
            return self._empty_report()

        try:
            # Get session outcomes from context.db
            session_outcomes = self._get_session_outcomes()
            if not session_outcomes:
                return self._empty_report()

            # Get facts grouped by session
            session_facts = self._get_session_facts()
            if not session_facts:
                return self._empty_report()

            # Correlate facts to outcomes
            success_patterns: dict[str, int] = defaultdict(int)
            failure_patterns: dict[str, int] = defaultdict(int)

            analyzed_sessions = 0
            succeeded_count = 0
            failed_count = 0
            total_facts = 0

            for session_id, facts in session_facts.items():
                outcome = session_outcomes.get(session_id)
                if outcome is None:
                    # Unknown outcome, skip
                    continue

                analyzed_sessions += 1
                total_facts += len(facts)

                if outcome == "SUCCEEDED":
                    succeeded_count += 1
                    for fact_key in facts:
                        success_patterns[fact_key] += 1
                elif outcome == "FAILED":
                    failed_count += 1
                    for fact_key in facts:
                        failure_patterns[fact_key] += 1
                # PARTIAL outcomes are skipped for clear success/failure correlation

            return {
                "sessions_analyzed": analyzed_sessions,
                "success_patterns": dict(success_patterns),
                "failure_patterns": dict(failure_patterns),
                "overall_stats": {
                    "total_facts": total_facts,
                    "succeeded_sessions": succeeded_count,
                    "failed_sessions": failed_count,
                    "unique_fact_keys": len(
                        set(success_patterns.keys()) | set(failure_patterns.keys())
                    ),
                },
            }

        except sqlite3.Error:
            return self._empty_report()

    def get_calibration_table(self) -> dict[str, dict[str, Any]]:
        """Generate calibration table for fact types.

        Returns:
            Dictionary mapping fact_key to calibration info:
            {
                "fact_key": {
                    "success_rate": float (0.0 to 1.0),
                    "count": int (total occurrences),
                    "recommended_multiplier": float (0.7 to 1.2)
                }
            }
        """
        # Handle missing databases gracefully
        if not self.temporal_db.exists() or not self.context_db.exists():
            return {}

        try:
            # Get session outcomes from context.db
            session_outcomes = self._get_session_outcomes()
            if not session_outcomes:
                return {}

            # Get facts grouped by session with unique keys per session
            session_facts = self._get_session_facts()
            if not session_facts:
                return {}

            # Track success/failure counts per fact key
            fact_success_count: dict[str, int] = defaultdict(int)
            fact_failure_count: dict[str, int] = defaultdict(int)

            for session_id, fact_keys in session_facts.items():
                outcome = session_outcomes.get(session_id)
                if outcome is None:
                    continue

                # Get unique fact keys in this session
                unique_keys = set(fact_keys)

                if outcome == "SUCCEEDED":
                    for key in unique_keys:
                        fact_success_count[key] += 1
                elif outcome == "FAILED":
                    for key in unique_keys:
                        fact_failure_count[key] += 1

            # Build calibration table
            all_keys = set(fact_success_count.keys()) | set(fact_failure_count.keys())
            table: dict[str, dict[str, Any]] = {}

            for key in all_keys:
                success_count = fact_success_count.get(key, 0)
                failure_count = fact_failure_count.get(key, 0)
                total_count = success_count + failure_count

                if total_count == 0:
                    continue

                success_rate = success_count / total_count

                # Calculate recommended multiplier
                # Linear interpolation between MIN_MULTIPLIER (0% success) and MAX_MULTIPLIER (100%)
                multiplier = MIN_MULTIPLIER + (MAX_MULTIPLIER - MIN_MULTIPLIER) * success_rate

                table[key] = {
                    "success_rate": success_rate,
                    "count": total_count,
                    "recommended_multiplier": round(multiplier, 2),
                }

            return table

        except sqlite3.Error:
            return {}

    def _get_session_outcomes(self) -> dict[str, str]:
        """Query context.db for session outcomes.

        Returns:
            Dictionary mapping root_span_id to outcome string
        """
        conn = sqlite3.connect(self.context_db)
        try:
            cursor = conn.execute(
                "SELECT root_span_id, outcome FROM handoffs WHERE outcome IS NOT NULL"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            conn.close()

    def _get_session_facts(self) -> dict[str, list[str]]:
        """Query temporal.db for facts grouped by session.

        Returns:
            Dictionary mapping session_id to list of fact keys
        """
        conn = sqlite3.connect(self.temporal_db)
        try:
            cursor = conn.execute("SELECT session_id, key FROM temporal_facts")

            session_facts: dict[str, list[str]] = defaultdict(list)
            for row in cursor.fetchall():
                session_id, fact_key = row
                session_facts[session_id].append(fact_key)

            return dict(session_facts)
        finally:
            conn.close()

    def _empty_report(self) -> dict[str, Any]:
        """Return empty report structure."""
        return {
            "sessions_analyzed": 0,
            "success_patterns": {},
            "failure_patterns": {},
            "overall_stats": {
                "total_facts": 0,
                "succeeded_sessions": 0,
                "failed_sessions": 0,
                "unique_fact_keys": 0,
            },
        }

"""Tag sessions with outcomes from context.db.

Links Braintrust sessions to handoff outcomes and applies calibration.

Phase 3.4 of backfill pipeline.

Key Decision: Use ONLY user-marked outcomes (Option A).
- No automatic loop detection for failure inference.
- Only explicit outcomes from context.db are used.
- Skill inference is used as a secondary signal for UNKNOWN sessions.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SessionOutcome:
    """Outcome tagging result."""

    session_id: str
    outcome: str  # SUCCEEDED, FAILED, PARTIAL_PLUS, PARTIAL_MINUS, UNKNOWN, INFERRED_*
    confidence_multiplier: float
    method: str  # context_db, skill_inference, default
    handoff_id: str | None = None


# Calibration multipliers from research
# These weights adjust fact confidence based on session outcome
OUTCOME_MULTIPLIERS: dict[str, float] = {
    "SUCCEEDED": 1.2,  # High confidence - task completed successfully
    "INFERRED_SUCCEEDED": 1.2,  # Inferred success via skill detection
    "FAILED": 0.7,  # Lower confidence - task failed
    "INFERRED_FAILED": 0.7,  # Inferred failure (not used per Option A)
    "PARTIAL_PLUS": 0.9,  # Mixed result, mostly positive
    "PARTIAL_MINUS": 0.85,  # Mixed result, mostly negative
    "UNKNOWN": 1.0,  # Neutral - no outcome information
}


class OutcomeTagger:
    """Tag sessions with outcomes for calibration.

    Queries context.db to find outcome labels for sessions, then
    applies calibration multipliers based on the outcome.

    Priority order:
    1. Context.db handoff outcome (explicit user-marked)
    2. Skill inference (create_handoff, commit presence)
    3. Default to UNKNOWN

    Note: Loop detection is intentionally NOT implemented per Option A decision.
    We only use explicit user-marked outcomes, not automatic inference.
    """

    def __init__(self, context_db_path: Path | None = None):
        """Initialize OutcomeTagger.

        Args:
            context_db_path: Path to context.db. Defaults to
                .claude/cache/artifact-index/context.db
        """
        self.context_db_path = context_db_path or Path(
            ".claude/cache/artifact-index/context.db"
        )

    def tag(
        self,
        session_id: str,
        has_handoff_skill: bool = False,
        has_commit_skill: bool = False,
    ) -> SessionOutcome:
        """Tag session with outcome.

        Args:
            session_id: Root span ID of the session
            has_handoff_skill: True if create_handoff skill was activated
            has_commit_skill: True if commit skill was activated

        Returns:
            SessionOutcome with outcome label and confidence multiplier

        Priority:
        1. Context.db handoff outcome (explicit, takes priority)
        2. Skill inference (create_handoff or commit = success)
        3. Default to UNKNOWN
        """
        # Step 1: Try to get explicit outcome from context.db
        db_result = self._query_context_db(session_id)
        if db_result is not None:
            handoff_id, outcome = db_result
            if outcome is not None:
                # Use explicit outcome from database
                multiplier = OUTCOME_MULTIPLIERS.get(outcome, 1.0)
                return SessionOutcome(
                    session_id=session_id,
                    outcome=outcome,
                    confidence_multiplier=multiplier,
                    method="context_db",
                    handoff_id=handoff_id,
                )

        # Step 2: Try skill inference for UNKNOWN sessions
        if has_handoff_skill or has_commit_skill:
            return SessionOutcome(
                session_id=session_id,
                outcome="INFERRED_SUCCEEDED",
                confidence_multiplier=OUTCOME_MULTIPLIERS["INFERRED_SUCCEEDED"],
                method="skill_inference",
                handoff_id=None,
            )

        # Step 3: Default to UNKNOWN
        return SessionOutcome(
            session_id=session_id,
            outcome="UNKNOWN",
            confidence_multiplier=OUTCOME_MULTIPLIERS["UNKNOWN"],
            method="default",
            handoff_id=None,
        )

    def _query_context_db(self, session_id: str) -> tuple[str, str | None] | None:
        """Query context.db for outcome by root_span_id.

        Args:
            session_id: Root span ID to look up

        Returns:
            Tuple of (handoff_id, outcome) if found, None if not found
            or database doesn't exist.
        """
        # Check if database exists
        if not self.context_db_path.exists():
            return None

        try:
            conn = sqlite3.connect(self.context_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Query for handoff with matching root_span_id
            # Uses parameterized query to prevent SQL injection
            cursor.execute(
                """
                SELECT id, outcome
                FROM handoffs
                WHERE root_span_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (session_id,),
            )

            row = cursor.fetchone()
            conn.close()

            if row is None:
                return None

            return (row["id"], row["outcome"])

        except sqlite3.Error:
            # Database error - return None (treat as UNKNOWN)
            return None

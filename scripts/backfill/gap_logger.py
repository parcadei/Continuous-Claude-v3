"""Log skipped sessions for debugging.

Uses JSONL format for easy streaming and analysis.

JSONL Entry Format:
```json
{"session_id": "xxx", "reason": "insufficient_spans", "details": {"span_count": 2}, "timestamp": "2025-01-01T00:00:00Z"}
```
"""
import json
from collections import Counter
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class GapReason(Enum):
    """Reasons a session was skipped during backfill."""
    INSUFFICIENT_SPANS = "insufficient_spans"
    NO_TOOL_SPANS = "no_tool_spans"
    ALREADY_PROCESSED = "already_processed"
    API_ERROR = "api_error"
    PARSE_ERROR = "parse_error"
    TIMEOUT = "timeout"


class GapLogger:
    """Log gaps in backfill processing.

    Tracks sessions that were skipped during backfill along with
    the reason for skipping. Uses JSONL format for streaming and
    easy analysis.

    Example:
        logger = GapLogger()
        logger.log_gap("session-123", GapReason.INSUFFICIENT_SPANS, span_count=2)

        # Later, analyze gaps
        summary = logger.get_summary()
        print(f"Total skipped: {summary['total']}")
    """

    def __init__(self, log_path: Optional[Path] = None):
        """Initialize gap logger.

        Args:
            log_path: Path to JSONL log file. Defaults to
                      .claude/cache/backfill-gaps.jsonl
        """
        self.log_path = log_path or Path(".claude/cache/backfill-gaps.jsonl")

    def log_gap(self, session_id: str, reason: GapReason, **details: Any) -> None:
        """Log a skipped session.

        Args:
            session_id: The Braintrust session/root_span_id that was skipped
            reason: Why the session was skipped
            **details: Additional context (e.g., span_count=2, error_message="...")
        """
        entry = {
            "session_id": session_id,
            "reason": reason.value,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Create parent directories if needed
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to JSONL file
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def read_gaps(self) -> list[dict[str, Any]]:
        """Read all logged gaps.

        Returns:
            List of gap entries, each containing session_id, reason,
            details, and timestamp.
        """
        if not self.log_path.exists():
            return []

        entries = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def get_summary(self) -> dict[str, Any]:
        """Get summary statistics.

        Returns:
            Dictionary with:
            - total: Total number of skipped sessions
            - by_reason: Count per reason type
        """
        entries = self.read_gaps()

        if not entries:
            return {"total": 0, "by_reason": {}}

        reason_counts = Counter(entry["reason"] for entry in entries)

        return {
            "total": len(entries),
            "by_reason": dict(reason_counts),
        }

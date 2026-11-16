"""Checkpoint/resume support for backfill pipeline.

Enables resuming interrupted backfills without reprocessing.

Features:
- Atomic writes using temp file + rename pattern
- Tracks processed and pending session IDs
- Timestamps for debugging/monitoring
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, cast


class CheckpointManager:
    """Manage backfill checkpoint state.

    Checkpoint JSON format:
    {
        "processed": ["session-1", "session-2"],
        "pending": ["session-3", "session-4"],
        "updated_at": "2025-01-01T00:00:00Z"
    }
    """

    def __init__(self, checkpoint_path: Optional[Path] = None) -> None:
        """Initialize checkpoint manager.

        Args:
            checkpoint_path: Path to checkpoint file. Defaults to
                .claude/cache/backfill-checkpoint.json
        """
        self.checkpoint_path = checkpoint_path or Path(
            ".claude/cache/backfill-checkpoint.json"
        )

    def save(self, processed: list[str], pending: list[str]) -> None:
        """Save checkpoint state atomically.

        Uses write-to-temp + atomic rename pattern to prevent corruption
        if interrupted during write.

        Args:
            processed: List of processed session IDs
            pending: List of pending session IDs
        """
        state = {
            "processed": processed,
            "pending": pending,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Ensure parent directory exists
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file first, then atomic rename
        # Use same directory to ensure same filesystem for atomic rename
        fd, temp_path = tempfile.mkstemp(
            suffix=".tmp",
            dir=self.checkpoint_path.parent,
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(state, f, indent=2)
            # Atomic rename (on POSIX systems)
            os.replace(temp_path, self.checkpoint_path)
        except Exception:
            # Clean up temp file on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def load(self) -> dict[str, Any]:
        """Load checkpoint state.

        Returns:
            Dict with 'processed', 'pending', and 'updated_at' keys.
            Returns empty defaults if checkpoint doesn't exist.
        """
        if not self.checkpoint_path.exists():
            return {
                "processed": [],
                "pending": [],
            }

        with open(self.checkpoint_path) as f:
            data: dict[str, Any] = json.load(f)
            return data

    def mark_processed(self, session_id: str) -> None:
        """Mark a session as processed.

        Moves session from pending to processed list and saves checkpoint.
        If session is not in pending, still adds to processed (idempotent).

        Args:
            session_id: Session ID to mark as processed
        """
        state = self.load()

        # Remove from pending if present
        pending = [s for s in state.get("pending", []) if s != session_id]

        # Add to processed if not already there
        processed = state.get("processed", [])
        if session_id not in processed:
            processed = processed + [session_id]

        self.save(processed=processed, pending=pending)

    def get_pending(self) -> list[str]:
        """Get list of pending sessions.

        Returns:
            List of session IDs that haven't been processed yet.
        """
        state = self.load()
        pending: list[str] = state.get("pending", [])
        return pending

    def clear(self) -> None:
        """Clear checkpoint (fresh start).

        Removes the checkpoint file if it exists.
        Safe to call even if file doesn't exist.
        """
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()

"""Tests for backfill checkpoint/resume support.

Phase 3.7: Enables resuming interrupted backfills without reprocessing.
"""
import pytest
from pathlib import Path
from scripts.backfill.checkpoint import CheckpointManager


class TestCheckpointManager:
    """Test checkpoint manager functionality."""

    @pytest.fixture
    def temp_checkpoint(self, tmp_path: Path) -> Path:
        """Create temporary checkpoint file path."""
        return tmp_path / "checkpoint.json"

    def test_save_progress(self, temp_checkpoint: Path) -> None:
        """Progress saved to checkpoint file."""
        manager = CheckpointManager(checkpoint_path=temp_checkpoint)

        manager.save(processed=["s1", "s2"], pending=["s3", "s4"])

        state = manager.load()
        assert set(state["processed"]) == {"s1", "s2"}
        assert set(state["pending"]) == {"s3", "s4"}

    def test_load_empty_returns_defaults(self, temp_checkpoint: Path) -> None:
        """Missing checkpoint returns empty defaults."""
        manager = CheckpointManager(checkpoint_path=temp_checkpoint)

        state = manager.load()

        assert state["processed"] == []
        assert state["pending"] == []

    def test_mark_processed(self, temp_checkpoint: Path) -> None:
        """Marking processed updates checkpoint."""
        manager = CheckpointManager(checkpoint_path=temp_checkpoint)
        manager.save(processed=["s1"], pending=["s2", "s3"])

        manager.mark_processed("s2")

        state = manager.load()
        assert "s2" in state["processed"]
        assert "s2" not in state["pending"]

    def test_get_pending_returns_remaining(self, temp_checkpoint: Path) -> None:
        """Get pending returns unprocessed sessions."""
        manager = CheckpointManager(checkpoint_path=temp_checkpoint)
        manager.save(processed=["s1", "s2"], pending=["s3", "s4", "s5"])

        pending = manager.get_pending()

        assert pending == ["s3", "s4", "s5"]

    def test_clear_checkpoint(self, temp_checkpoint: Path) -> None:
        """Clear removes checkpoint file."""
        manager = CheckpointManager(checkpoint_path=temp_checkpoint)
        manager.save(processed=["s1"], pending=["s2"])

        manager.clear()

        assert not temp_checkpoint.exists()

    def test_atomic_update(self, temp_checkpoint: Path) -> None:
        """Update is atomic (write temp, rename)."""
        manager = CheckpointManager(checkpoint_path=temp_checkpoint)

        # Save should be atomic
        manager.save(processed=["s1"], pending=["s2"])

        # Verify no temp files left
        temp_files = list(temp_checkpoint.parent.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_updated_at_timestamp(self, temp_checkpoint: Path) -> None:
        """Checkpoint includes updated_at timestamp."""
        manager = CheckpointManager(checkpoint_path=temp_checkpoint)

        manager.save(processed=["s1"], pending=["s2"])

        state = manager.load()
        assert "updated_at" in state
        # Should be ISO format
        assert "T" in state["updated_at"]

    def test_mark_processed_preserves_order(self, temp_checkpoint: Path) -> None:
        """Mark processed preserves pending order."""
        manager = CheckpointManager(checkpoint_path=temp_checkpoint)
        manager.save(processed=[], pending=["s1", "s2", "s3", "s4"])

        manager.mark_processed("s2")

        pending = manager.get_pending()
        assert pending == ["s1", "s3", "s4"]

    def test_mark_processed_nonexistent_session(self, temp_checkpoint: Path) -> None:
        """Marking nonexistent session doesn't crash."""
        manager = CheckpointManager(checkpoint_path=temp_checkpoint)
        manager.save(processed=["s1"], pending=["s2"])

        # Should not raise
        manager.mark_processed("nonexistent")

        state = manager.load()
        # nonexistent still added to processed (idempotent for external tracking)
        assert "nonexistent" in state["processed"]
        # Pending unchanged
        assert state["pending"] == ["s2"]

    def test_clear_nonexistent_file(self, temp_checkpoint: Path) -> None:
        """Clear on nonexistent file doesn't crash."""
        manager = CheckpointManager(checkpoint_path=temp_checkpoint)

        # Should not raise
        manager.clear()

        assert not temp_checkpoint.exists()

    def test_get_pending_empty_state(self, temp_checkpoint: Path) -> None:
        """Get pending on empty state returns empty list."""
        manager = CheckpointManager(checkpoint_path=temp_checkpoint)

        pending = manager.get_pending()

        assert pending == []

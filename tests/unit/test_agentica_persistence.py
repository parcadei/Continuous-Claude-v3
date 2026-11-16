"""Tests for Agentica state persistence."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch
import tempfile
import os


class TestStatePersistence:
    """Test state save/load functionality."""

    def test_save_state_creates_file(self, tmp_path):
        """save_state should create JSON file."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            from scripts.agentica_patterns.server.persistence import save_state

            state = {"findings": ["test finding"], "query_count": 1}
            save_state("research", state)

            expected_path = tmp_path / ".claude" / "cache" / "agentica-state" / "research.json"
            assert expected_path.exists()

            with open(expected_path) as f:
                saved = json.load(f)
            assert saved["state"]["findings"] == ["test finding"]

    def test_load_state_returns_none_if_missing(self, tmp_path):
        """load_state should return None if no file."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            from scripts.agentica_patterns.server.persistence import load_state

            state = load_state("nonexistent")
            assert state is None

    def test_load_state_returns_saved_state(self, tmp_path):
        """load_state should return previously saved state."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            from scripts.agentica_patterns.server.persistence import save_state, load_state

            original = {"findings": ["a", "b"], "sources": {"url1": "title1"}}
            save_state("research", original)

            loaded = load_state("research")
            assert loaded["findings"] == ["a", "b"]
            assert loaded["sources"] == {"url1": "title1"}

    def test_state_includes_metadata(self, tmp_path):
        """Saved state should include timestamp and metadata."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            from scripts.agentica_patterns.server.persistence import save_state

            save_state("research", {"test": 1})

            path = tmp_path / ".claude" / "cache" / "agentica-state" / "research.json"
            with open(path) as f:
                saved = json.load(f)

            assert "timestamp" in saved
            assert "agent_type" in saved
            assert saved["agent_type"] == "research"


class TestStateSize:
    """Test state size monitoring."""

    def test_get_state_size_returns_bytes(self, tmp_path):
        """get_state_size should return size in bytes."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            from scripts.agentica_patterns.server.persistence import save_state, get_state_size

            save_state("research", {"test": "x" * 1000})
            size = get_state_size("research")

            assert size > 1000
            assert isinstance(size, int)

    def test_get_state_size_zero_if_missing(self, tmp_path):
        """get_state_size should return 0 if no file."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            from scripts.agentica_patterns.server.persistence import get_state_size

            size = get_state_size("nonexistent")
            assert size == 0


class TestMemoryManagement:
    """Test state flushing when too large."""

    def test_should_flush_returns_false_under_threshold(self, tmp_path):
        """should_flush should return False for small states."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            from scripts.agentica_patterns.server.persistence import save_state, should_flush

            save_state("research", {"small": "state"})
            assert should_flush("research") is False

    def test_should_flush_returns_true_over_threshold(self, tmp_path):
        """should_flush should return True for large states."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            from scripts.agentica_patterns.server.persistence import save_state, should_flush

            # Create state over 1MB
            large_data = {"data": "x" * (1024 * 1024 + 1000)}
            save_state("research", large_data)

            assert should_flush("research") is True

    def test_flush_state_preserves_summary(self, tmp_path):
        """flush_state should preserve summary but clear detailed data."""
        with patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(tmp_path)}):
            from scripts.agentica_patterns.server.persistence import save_state, flush_state, load_state

            state = {
                "findings": ["a", "b", "c"],
                "detailed_results": "x" * 10000,
                "query_history": ["q1", "q2", "q3"],
                "sources": {"url1": "title1"},
            }
            save_state("research", state)

            flush_state("research")

            flushed = load_state("research")
            # Summary fields preserved
            assert "findings_count" in flushed or len(flushed.get("findings", [])) <= 5
            # Detailed data reduced
            assert len(json.dumps(flushed)) < len(json.dumps(state))

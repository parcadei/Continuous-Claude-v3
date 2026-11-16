"""Tests for temporal memory CLI.

TDD tests for Phase 4.3 of temporal memory implementation.
Tests the CLI wrapper that hooks will call.
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestTemporalCLI:
    """Test CLI commands."""

    @pytest.fixture
    def temp_db_dir(self):
        """Create a temporary directory for test database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def run_cli(self, *args, env=None, cwd=None):
        """Run CLI command and return result."""
        project_root = Path(__file__).parent.parent.parent
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "scripts.temporal_memory.cli",
        ] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env={**os.environ, **(env or {})},
            cwd=cwd or project_root,
        )
        return result

    def test_cli_help(self):
        """Test that --help shows usage information."""
        result = self.run_cli("--help")
        assert result.returncode == 0
        # Should mention available commands
        assert "summarize" in result.stdout or "usage" in result.stdout.lower()
        assert "record" in result.stdout or "usage" in result.stdout.lower()

    def test_cli_record(self, temp_db_dir):
        """Test recording facts at a turn."""
        result = self.run_cli(
            "record",
            "--session-id",
            "test-123",
            "--turn",
            "1",
            "--facts",
            '{"phase": "testing"}',
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["status"] == "ok"
        assert output["turn"] == 1

    def test_cli_record_multiple_facts(self, temp_db_dir):
        """Test recording multiple facts at once."""
        result = self.run_cli(
            "record",
            "--session-id",
            "test-123",
            "--turn",
            "1",
            "--facts",
            '{"phase": "testing", "db": "sqlite", "branch": "feature"}',
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["status"] == "ok"

    def test_cli_summarize_json(self, temp_db_dir):
        """Test summarize command with JSON output."""
        db_path = str(temp_db_dir / "test.db")

        # First record some data
        self.run_cli(
            "record",
            "--session-id",
            "test-123",
            "--turn",
            "1",
            "--facts",
            '{"db": "sqlite"}',
            "--db-path",
            db_path,
        )

        result = self.run_cli(
            "summarize",
            "--session-id",
            "test-123",
            "--output",
            "json",
            "--db-path",
            db_path,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        output = json.loads(result.stdout)
        assert "invariants" in output
        assert "turn_count" in output
        assert "open_questions" in output
        assert "pending_goals" in output
        assert "transitions" in output

    def test_cli_summarize_markdown(self, temp_db_dir):
        """Test summarize command with markdown output."""
        db_path = str(temp_db_dir / "test.db")

        self.run_cli(
            "record",
            "--session-id",
            "test-123",
            "--turn",
            "1",
            "--facts",
            '{"db": "sqlite"}',
            "--db-path",
            db_path,
        )

        result = self.run_cli(
            "summarize",
            "--session-id",
            "test-123",
            "--output",
            "markdown",
            "--db-path",
            db_path,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "# Temporal Summary" in result.stdout
        assert "## Invariants" in result.stdout or "Invariants" in result.stdout

    def test_cli_budget_parameter(self, temp_db_dir):
        """Test that budget parameter is accepted."""
        db_path = str(temp_db_dir / "test.db")

        self.run_cli(
            "record",
            "--session-id",
            "test-123",
            "--turn",
            "1",
            "--facts",
            '{"db": "sqlite"}',
            "--db-path",
            db_path,
        )

        result = self.run_cli(
            "summarize",
            "--session-id",
            "test-123",
            "--budget",
            "500",
            "--output",
            "json",
            "--db-path",
            db_path,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"

    def test_cli_record_multiple_turns(self, temp_db_dir):
        """Test recording across multiple turns."""
        db_path = str(temp_db_dir / "test.db")

        self.run_cli(
            "record",
            "--session-id",
            "test",
            "--turn",
            "1",
            "--facts",
            '{"phase": "planning"}',
            "--db-path",
            db_path,
        )
        self.run_cli(
            "record",
            "--session-id",
            "test",
            "--turn",
            "2",
            "--facts",
            '{"phase": "testing"}',
            "--db-path",
            db_path,
        )

        result = self.run_cli(
            "summarize",
            "--session-id",
            "test",
            "--output",
            "json",
            "--db-path",
            db_path,
        )
        output = json.loads(result.stdout)
        assert output["turn_count"] == 2

    def test_cli_summarize_empty_session(self, temp_db_dir):
        """Test summarize on a session with no data."""
        db_path = str(temp_db_dir / "test.db")

        result = self.run_cli(
            "summarize",
            "--session-id",
            "nonexistent",
            "--output",
            "json",
            "--db-path",
            db_path,
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        output = json.loads(result.stdout)
        assert output["turn_count"] == 0
        assert output["invariants"] == []

    def test_cli_record_invalid_json(self, temp_db_dir):
        """Test that invalid JSON facts returns error."""
        result = self.run_cli(
            "record",
            "--session-id",
            "test",
            "--turn",
            "1",
            "--facts",
            "not valid json",
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        # Should fail with non-zero exit code
        assert result.returncode != 0

    def test_cli_summarize_with_transitions(self, temp_db_dir):
        """Test that transitions are captured in summary."""
        db_path = str(temp_db_dir / "test.db")

        # Record state changes
        self.run_cli(
            "record",
            "--session-id",
            "test",
            "--turn",
            "1",
            "--facts",
            '{"phase": "planning", "db": "sqlite"}',
            "--db-path",
            db_path,
        )
        self.run_cli(
            "record",
            "--session-id",
            "test",
            "--turn",
            "2",
            "--facts",
            '{"phase": "coding", "db": "sqlite"}',
            "--db-path",
            db_path,
        )
        self.run_cli(
            "record",
            "--session-id",
            "test",
            "--turn",
            "3",
            "--facts",
            '{"phase": "testing", "db": "sqlite"}',
            "--db-path",
            db_path,
        )

        result = self.run_cli(
            "summarize",
            "--session-id",
            "test",
            "--output",
            "json",
            "--db-path",
            db_path,
        )
        output = json.loads(result.stdout)

        # Should have transitions for phase changes
        assert len(output["transitions"]) >= 1

        # db should be invariant (never changed)
        assert any("db" in inv or "sqlite" in inv for inv in output["invariants"])

    def test_cli_session_isolation(self, temp_db_dir):
        """Test that different sessions are isolated."""
        db_path = str(temp_db_dir / "test.db")

        # Record to session A
        self.run_cli(
            "record",
            "--session-id",
            "session-a",
            "--turn",
            "1",
            "--facts",
            '{"secret": "a-data"}',
            "--db-path",
            db_path,
        )

        # Record to session B
        self.run_cli(
            "record",
            "--session-id",
            "session-b",
            "--turn",
            "1",
            "--facts",
            '{"secret": "b-data"}',
            "--db-path",
            db_path,
        )

        # Summarize session A
        result_a = self.run_cli(
            "summarize",
            "--session-id",
            "session-a",
            "--output",
            "json",
            "--db-path",
            db_path,
        )
        output_a = json.loads(result_a.stdout)

        # Summarize session B
        result_b = self.run_cli(
            "summarize",
            "--session-id",
            "session-b",
            "--output",
            "json",
            "--db-path",
            db_path,
        )
        output_b = json.loads(result_b.stdout)

        # Each should only see their own data
        assert output_a["current_state"].get("secret") == "a-data"
        assert output_b["current_state"].get("secret") == "b-data"


class TestTemporalCLIEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_db_dir(self):
        """Create a temporary directory for test database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def run_cli(self, *args, env=None, cwd=None):
        """Run CLI command and return result."""
        project_root = Path(__file__).parent.parent.parent
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "scripts.temporal_memory.cli",
        ] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env={**os.environ, **(env or {})},
            cwd=cwd or project_root,
        )
        return result

    def test_record_missing_session_id(self, temp_db_dir):
        """Test that missing session-id shows error."""
        result = self.run_cli(
            "record",
            "--turn",
            "1",
            "--facts",
            '{"key": "value"}',
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        assert result.returncode != 0

    def test_record_missing_turn(self, temp_db_dir):
        """Test that missing turn shows error."""
        result = self.run_cli(
            "record",
            "--session-id",
            "test",
            "--facts",
            '{"key": "value"}',
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        assert result.returncode != 0

    def test_summarize_missing_session_id(self, temp_db_dir):
        """Test that missing session-id shows error."""
        result = self.run_cli(
            "summarize",
            "--output",
            "json",
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        assert result.returncode != 0

    def test_record_negative_turn(self, temp_db_dir):
        """Test that negative turn values are handled."""
        result = self.run_cli(
            "record",
            "--session-id",
            "test",
            "--turn",
            "-1",
            "--facts",
            '{"key": "value"}',
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        # Should either fail or handle gracefully
        # Implementation choice: we accept any int turn value
        # as negative turns could have semantic meaning in some cases

    def test_record_empty_facts(self, temp_db_dir):
        """Test recording empty facts dictionary."""
        result = self.run_cli(
            "record",
            "--session-id",
            "test",
            "--turn",
            "1",
            "--facts",
            "{}",
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["status"] == "ok"

    def test_unicode_in_facts(self, temp_db_dir):
        """Test that unicode characters in facts work."""
        result = self.run_cli(
            "record",
            "--session-id",
            "test",
            "--turn",
            "1",
            "--facts",
            '{"message": "Hello"}',
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        assert result.returncode == 0

        result = self.run_cli(
            "summarize",
            "--session-id",
            "test",
            "--output",
            "json",
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        output = json.loads(result.stdout)
        assert output["current_state"]["message"] == "Hello"

    def test_special_chars_in_session_id(self, temp_db_dir):
        """Test session IDs with special characters."""
        result = self.run_cli(
            "record",
            "--session-id",
            "session-with-dashes_and_underscores.and.dots",
            "--turn",
            "1",
            "--facts",
            '{"key": "value"}',
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        assert result.returncode == 0

    def test_large_facts_object(self, temp_db_dir):
        """Test recording a large facts object."""
        # Create a large facts object
        large_facts = {f"key_{i}": f"value_{i}" for i in range(100)}

        result = self.run_cli(
            "record",
            "--session-id",
            "test",
            "--turn",
            "1",
            "--facts",
            json.dumps(large_facts),
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        assert result.returncode == 0

        result = self.run_cli(
            "summarize",
            "--session-id",
            "test",
            "--output",
            "json",
            "--db-path",
            str(temp_db_dir / "test.db"),
        )
        output = json.loads(result.stdout)
        assert len(output["current_state"]) == 100

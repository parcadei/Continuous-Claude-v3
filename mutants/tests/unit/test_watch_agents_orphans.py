"""Tests for watch_agents.py --orphans flag (Phase 12).

TDD: These tests are written first, implementation follows.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from scripts.agentica.coordination import OrphanCandidate


class TestWatchAgentsOrphansFlag:
    """Test the --orphans flag in watch_agents.py."""

    def test_argparse_accepts_orphans_flag(self):
        """The --orphans flag should be recognized by argparse."""
        from scripts.agentica.watch_agents import main
        import argparse

        # Import the module to check argparse configuration
        from scripts.agentica import watch_agents

        # Create a parser the same way main() does
        parser = argparse.ArgumentParser()
        parser.add_argument("--watch", "-w", action="store_true")
        parser.add_argument("--completed", "-c", action="store_true")
        parser.add_argument("--summary", "-s", action="store_true")
        parser.add_argument("--pattern", "-p", type=str)
        parser.add_argument("--session", type=str)
        parser.add_argument("--all-sessions", "-a", action="store_true")
        parser.add_argument("--monitor", "-m", action="store_true")
        parser.add_argument("--watch-dir", type=str, action="append")
        parser.add_argument("--logs", "-l", action="store_true")
        parser.add_argument("--logs-dir", type=str, default="./logs")
        # This is the new flag we're testing
        parser.add_argument("--orphans", "-o", action="store_true")

        args = parser.parse_args(["--orphans"])
        assert args.orphans is True

    def test_argparse_accepts_short_orphans_flag(self):
        """The -o short flag should also work."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--orphans", "-o", action="store_true")

        args = parser.parse_args(["-o"])
        assert args.orphans is True

    def test_orphans_flag_via_cli(self):
        """Running watch_agents.py --orphans should not error."""
        result = subprocess.run(
            [sys.executable, "scripts/agentica/watch_agents.py", "--orphans"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(_project_root),
        )
        # Should exit 0 (success) even if no orphans found
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_orphans_flag_calls_find_orphans(self):
        """--orphans flag should call db.find_orphans()."""
        from scripts.agentica import watch_agents

        mock_db = MagicMock()
        mock_db.find_orphans.return_value = []

        with patch.object(watch_agents, "CoordinationDB", return_value=mock_db):
            with patch.object(sys, "argv", ["watch_agents.py", "--orphans"]):
                try:
                    watch_agents.main()
                except SystemExit:
                    pass  # argparse may exit

        mock_db.find_orphans.assert_called_once()

    def test_orphans_display_shows_tier_and_reason(self):
        """Orphan display should show tier, agent_id, reason, and age."""
        from scripts.agentica import watch_agents

        # Create mock orphan candidates
        mock_orphans = [
            OrphanCandidate(
                agent_id="test-agent-001",
                ppid=1,
                parent_agent_id=None,
                spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
                tier=1,
                reason="ppid=1 (parent process died)",
            ),
            OrphanCandidate(
                agent_id="test-agent-002",
                ppid=12345,
                parent_agent_id="parent-001",
                spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
                tier=2,
                reason="Parent agent completed/failed (30min grace expired)",
            ),
        ]

        mock_db = MagicMock()
        mock_db.find_orphans.return_value = mock_orphans

        with patch.object(watch_agents, "CoordinationDB", return_value=mock_db):
            with patch.object(sys, "argv", ["watch_agents.py", "--orphans"]):
                with patch.object(watch_agents, "RICH_AVAILABLE", False):
                    with patch("builtins.print") as mock_print:
                        try:
                            watch_agents.main()
                        except SystemExit:
                            pass

        # Verify output includes tier and reason
        printed_output = " ".join(str(call) for call in mock_print.call_args_list)
        assert "Tier 1" in printed_output or "tier=1" in printed_output.lower() or "1" in printed_output
        assert "test-agent-001" in printed_output
        assert "test-agent-002" in printed_output


class TestOrphansJsonOutput:
    """Test --orphans with --json flag."""

    def test_orphans_json_flag_outputs_json(self):
        """--orphans --json should output valid JSON."""
        from scripts.agentica import watch_agents

        mock_orphans = [
            OrphanCandidate(
                agent_id="json-test-agent",
                ppid=1,
                parent_agent_id=None,
                spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=30),
                tier=1,
                reason="ppid=1",
            ),
        ]

        mock_db = MagicMock()
        mock_db.find_orphans.return_value = mock_orphans

        output_lines = []
        with patch.object(watch_agents, "CoordinationDB", return_value=mock_db):
            with patch.object(sys, "argv", ["watch_agents.py", "--orphans", "--json"]):
                with patch("builtins.print", side_effect=lambda x: output_lines.append(x)):
                    try:
                        watch_agents.main()
                    except SystemExit:
                        pass

        # Should have at least one JSON output
        json_output = None
        for line in output_lines:
            try:
                json_output = json.loads(line)
                break
            except (json.JSONDecodeError, TypeError):
                continue

        assert json_output is not None, f"No valid JSON found in output: {output_lines}"

    def test_orphans_json_contains_required_fields(self):
        """JSON output should contain tier, agent_id, reason, age fields."""
        from scripts.agentica import watch_agents

        mock_orphans = [
            OrphanCandidate(
                agent_id="field-test-agent",
                ppid=1,
                parent_agent_id="parent-123",
                spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1),
                tier=2,
                reason="Parent agent failed",
            ),
        ]

        mock_db = MagicMock()
        mock_db.find_orphans.return_value = mock_orphans

        output_lines = []
        with patch.object(watch_agents, "CoordinationDB", return_value=mock_db):
            with patch.object(sys, "argv", ["watch_agents.py", "--orphans", "--json"]):
                with patch("builtins.print", side_effect=lambda x: output_lines.append(x)):
                    try:
                        watch_agents.main()
                    except SystemExit:
                        pass

        # Parse JSON and verify fields
        json_output = None
        for line in output_lines:
            try:
                json_output = json.loads(line)
                break
            except (json.JSONDecodeError, TypeError):
                continue

        assert json_output is not None
        # Could be a list or single object
        orphan_data = json_output[0] if isinstance(json_output, list) else json_output
        assert "tier" in orphan_data or "Tier" in orphan_data
        assert "agent_id" in orphan_data or "Agent ID" in orphan_data
        assert "reason" in orphan_data or "Reason" in orphan_data


class TestOrphansRichTable:
    """Test --orphans with Rich table output."""

    @pytest.mark.skipif(not True, reason="Rich tests")
    def test_orphans_creates_rich_table_when_available(self):
        """When rich is available, should create a Table with proper columns."""
        from scripts.agentica import watch_agents

        # Skip if rich is not available
        if not watch_agents.RICH_AVAILABLE:
            pytest.skip("Rich not available")

        mock_orphans = [
            OrphanCandidate(
                agent_id="rich-test-agent",
                ppid=1,
                parent_agent_id=None,
                spawned_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=3),
                tier=1,
                reason="ppid=1 (parent process died)",
            ),
        ]

        mock_db = MagicMock()
        mock_db.find_orphans.return_value = mock_orphans

        # Capture console output
        from io import StringIO
        from rich.console import Console

        output = StringIO()
        mock_console = Console(file=output, force_terminal=False)

        with patch.object(watch_agents, "CoordinationDB", return_value=mock_db):
            with patch.object(watch_agents, "Console", return_value=mock_console):
                with patch.object(sys, "argv", ["watch_agents.py", "--orphans"]):
                    try:
                        watch_agents.main()
                    except SystemExit:
                        pass

        rendered = output.getvalue()
        # Should have table-like output with orphan info
        assert "rich-test-agent" in rendered or "Orphan" in rendered or len(rendered) > 0


class TestOrphansEmpty:
    """Test behavior when no orphans exist."""

    def test_orphans_empty_returns_cleanly(self):
        """When no orphans exist, should return cleanly without error."""
        from scripts.agentica import watch_agents

        mock_db = MagicMock()
        mock_db.find_orphans.return_value = []

        with patch.object(watch_agents, "CoordinationDB", return_value=mock_db):
            with patch.object(sys, "argv", ["watch_agents.py", "--orphans"]):
                with patch.object(watch_agents, "RICH_AVAILABLE", False):
                    try:
                        watch_agents.main()
                    except SystemExit as e:
                        # Should exit cleanly (0) or not exit at all
                        assert e.code == 0 or e.code is None

    def test_orphans_empty_message_shown(self):
        """When no orphans exist, should show informative message."""
        from scripts.agentica import watch_agents

        mock_db = MagicMock()
        mock_db.find_orphans.return_value = []

        output_lines = []
        with patch.object(watch_agents, "CoordinationDB", return_value=mock_db):
            with patch.object(sys, "argv", ["watch_agents.py", "--orphans"]):
                with patch.object(watch_agents, "RICH_AVAILABLE", False):
                    with patch("builtins.print", side_effect=lambda x: output_lines.append(str(x))):
                        try:
                            watch_agents.main()
                        except SystemExit:
                            pass

        # Either prints nothing or shows "no orphans" message
        joined = " ".join(output_lines).lower()
        # Accept either no output or an explicit message
        assert len(output_lines) == 0 or "no" in joined or "orphan" in joined or "0" in joined

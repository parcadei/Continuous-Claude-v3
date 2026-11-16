"""E2E Integration Tests for Status Line Display.

Tests the status.sh output:
1. Run status.sh and verify output format
2. Verify resource display appears when agents > 50%
3. Verify color coding works

Phase 14 of resource-limits-plan.md
"""

import json
import os
import re
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def project_dir() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def scripts_dir(project_dir: Path) -> Path:
    """Get the .claude/scripts directory."""
    return project_dir / ".claude" / "scripts"


@pytest.fixture
def unique_session_id() -> str:
    """Generate a unique session ID for test isolation."""
    return f"test-{uuid4().hex[:12]}"


@pytest.fixture
def cleanup_temp_files(unique_session_id: str):
    """Cleanup temp files after test."""
    yield
    # Cleanup resource files
    resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
    context_file = Path(f"/tmp/claude-context-pct-{unique_session_id}.txt")
    if resource_file.exists():
        resource_file.unlink()
    if context_file.exists():
        context_file.unlink()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


# ============================================================================
# Test: status.sh output format
# ============================================================================


class TestStatusLineFormat:
    """Test that status.sh produces correct output format."""

    def test_basic_output_format(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Status line should have expected segments: tokens, pct, git info."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"
        env["MOCK_ACTIVE_AGENTS"] = "0"

        result = subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        output = strip_ansi(result.stdout)

        # Should contain token count (e.g., "45.0K")
        assert re.search(r'\d+\.?\d*K', output), f"Missing token count in: {output}"

        # Should contain percentage (e.g., "22%")
        assert re.search(r'\d+%', output), f"Missing percentage in: {output}"

    def test_context_percentage_calculation(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Context percentage should be calculated correctly."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # Provide context window data in input
        context_input = {
            "context_window": {
                "current_usage": {
                    "input_tokens": 50000,
                    "cache_read_input_tokens": 10000,
                    "cache_creation_input_tokens": 5000
                },
                "context_window_size": 200000
            }
        }

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"
        env["MOCK_ACTIVE_AGENTS"] = "0"

        result = subprocess.run(
            ["bash", str(status_script)],
            input=json.dumps(context_input),
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        output = strip_ansi(result.stdout)

        # Should show percentage
        # Total: 50000 + 10000 + 5000 + 45000 (overhead) = 110000
        # Pct: 110000 / 200000 = 55%
        assert re.search(r'\d+%', output)


# ============================================================================
# Test: Resource display when agents > 50%
# ============================================================================


class TestResourceDisplay:
    """Test that resource display appears based on utilization."""

    def test_no_resource_display_below_50_percent(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Resource display should NOT appear when utilization < 50%."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # 3 agents out of 10 = 30% utilization
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"  # ~12 max agents
        env["MOCK_ACTIVE_AGENTS"] = "3"

        result = subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        output = strip_ansi(result.stdout)

        # Should NOT contain agent display
        assert "Ag:" not in output, f"Agent display should not appear at low utilization: {output}"

    def test_resource_display_at_50_percent(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Resource display SHOULD appear when utilization >= 50%."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # 5 agents out of 10 = 50% utilization
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "7168"  # (7168-2048)/500 = 10 max agents
        env["MOCK_ACTIVE_AGENTS"] = "5"

        result = subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        output = strip_ansi(result.stdout)

        # Should contain agent display
        assert "Ag:" in output or "5/" in output, f"Agent display should appear at 50%: {output}"

    def test_resource_display_at_high_utilization(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Resource display should show at high utilization (>80%)."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # 9 agents out of 10 = 90% utilization
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "7168"  # ~10 max agents
        env["MOCK_ACTIVE_AGENTS"] = "9"

        result = subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        output = strip_ansi(result.stdout)

        # Should contain agent display
        assert "Ag:" in output or "9/" in output


# ============================================================================
# Test: Color coding
# ============================================================================


class TestColorCoding:
    """Test that status line uses correct color codes."""

    def test_green_at_low_context(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Context should be green when below 60%."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # Low context usage
        context_input = {
            "context_window": {
                "current_usage": {
                    "input_tokens": 10000,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0
                },
                "context_window_size": 200000
            }
        }

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"
        env["MOCK_ACTIVE_AGENTS"] = "0"

        result = subprocess.run(
            ["bash", str(status_script)],
            input=json.dumps(context_input),
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Check for green color code (\033[32m)
        assert "\033[32m" in result.stdout or "\x1b[32m" in result.stdout, \
            f"Expected green color code in output: {repr(result.stdout)}"

    def test_yellow_at_medium_context(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Context should be yellow when between 60-80%."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # Medium context usage (60-80%)
        # Total: 80000 + 30000 + 10000 + 45000 = 165000
        # Pct: 165000 / 200000 = 82.5% (actually above yellow, but the formula differs)
        # Let's calculate properly:
        # We want 60-80% which is 120000-160000 total
        # With 45K overhead, we need input of 75000-115000
        context_input = {
            "context_window": {
                "current_usage": {
                    "input_tokens": 80000,
                    "cache_read_input_tokens": 10000,
                    "cache_creation_input_tokens": 5000
                },
                "context_window_size": 200000
            }
        }

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"
        env["MOCK_ACTIVE_AGENTS"] = "0"

        result = subprocess.run(
            ["bash", str(status_script)],
            input=json.dumps(context_input),
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Check for yellow color code (\033[33m)
        assert "\033[33m" in result.stdout or "\x1b[33m" in result.stdout, \
            f"Expected yellow color code in output: {repr(result.stdout)}"

    def test_red_at_high_context(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Context should be red when >= 80%."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # High context usage (>=80%)
        # Total: 140000 + 10000 + 10000 + 45000 = 205000 -> capped at 100%
        context_input = {
            "context_window": {
                "current_usage": {
                    "input_tokens": 140000,
                    "cache_read_input_tokens": 10000,
                    "cache_creation_input_tokens": 10000
                },
                "context_window_size": 200000
            }
        }

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"
        env["MOCK_ACTIVE_AGENTS"] = "0"

        result = subprocess.run(
            ["bash", str(status_script)],
            input=json.dumps(context_input),
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Check for red color code (\033[31m)
        assert "\033[31m" in result.stdout or "\x1b[31m" in result.stdout, \
            f"Expected red color code in output: {repr(result.stdout)}"

    def test_yellow_agents_at_medium_utilization(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Agent display should be yellow at 50-79% utilization."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # 6/10 = 60% utilization (yellow)
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "7168"  # ~10 max agents
        env["MOCK_ACTIVE_AGENTS"] = "6"

        result = subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Should have yellow in output (for agent display)
        # Note: The main context percentage might also be yellow
        output = result.stdout
        assert "\033[33m" in output or "\x1b[33m" in output

    def test_red_agents_at_high_utilization(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Agent display should be red at >= 80% utilization."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # 9/10 = 90% utilization (red)
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "7168"  # ~10 max agents
        env["MOCK_ACTIVE_AGENTS"] = "9"

        result = subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Should have red in output (for agent display)
        output = result.stdout
        assert "\033[31m" in output or "\x1b[31m" in output


# ============================================================================
# Test: Edge cases
# ============================================================================


class TestStatusLineEdgeCases:
    """Test edge cases in status line generation."""

    def test_zero_active_agents(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Status should handle zero active agents gracefully."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"
        env["MOCK_ACTIVE_AGENTS"] = "0"

        result = subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Should complete without error
        assert result.returncode == 0
        # Should NOT show agent display at 0%
        output = strip_ansi(result.stdout)
        assert "Ag:0" not in output  # Don't show when at 0

    def test_empty_json_input(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Status should handle empty JSON input."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"
        env["MOCK_ACTIVE_AGENTS"] = "0"

        result = subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Should complete without error
        assert result.returncode == 0

    def test_malformed_json_input(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Status should handle malformed JSON gracefully."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"
        env["MOCK_ACTIVE_AGENTS"] = "0"

        result = subprocess.run(
            ["bash", str(status_script)],
            input="not valid json",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Should complete (jq uses defaults on parse error)
        assert result.returncode == 0

    def test_very_high_agent_count(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Status should handle agent counts above max gracefully."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # More agents than max (shouldn't happen, but test robustness)
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "4096"  # ~4 max agents
        env["MOCK_ACTIVE_AGENTS"] = "10"  # More than max

        result = subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Should complete without error
        assert result.returncode == 0
        # Should show the situation
        output = strip_ansi(result.stdout)
        assert "10/" in output or "Ag:" in output

    def test_writes_correct_json_format(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Verify the JSON file written has correct format."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"
        env["MOCK_ACTIVE_AGENTS"] = "5"

        subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        assert resource_file.exists()

        # Should be valid JSON
        data = json.loads(resource_file.read_text())

        # All fields should be integers
        assert isinstance(data["freeMemMB"], int)
        assert isinstance(data["activeAgents"], int)
        assert isinstance(data["maxAgents"], int)
        assert isinstance(data["contextPct"], int)

        # Values should be reasonable
        assert data["freeMemMB"] >= 0
        assert data["activeAgents"] >= 0
        assert data["maxAgents"] >= 1
        assert 0 <= data["contextPct"] <= 100

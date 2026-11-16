"""Tests for Phase 13: Add Resource Info to Status Line Display.

These tests verify that status.sh:
1. Shows RAM info in compact format: "RAM:4G"
2. Shows agent count: "Ag:3/8"
3. Only shows when utilization >= 50%
4. Color codes based on utilization (yellow 50-80%, red >80%)

Tests use MOCK_ACTIVE_AGENTS and MOCK_FREE_MEM_MB environment variables
to control resource values for testing.

Tests are designed to FAIL initially (TDD approach) until Phase 13 is implemented.

See plan: docs/handoffs/resource-limits-plan.md (Phase 13)
"""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestStatusLineResourceDisplay:
    """Tests for resource info in status line output."""

    @pytest.fixture
    def scripts_dir(self) -> Path:
        """Path to scripts directory."""
        return Path(__file__).parents[2] / ".claude" / "scripts"

    @pytest.fixture
    def unique_session_id(self) -> str:
        """Generate unique session ID for test isolation."""
        return f"test-display-{os.getpid()}-{id(self)}"

    @pytest.fixture
    def temp_project_dir(self):
        """Create temp directory without git to avoid git info pollution."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cleanup_temp_files(self, unique_session_id: str):
        """Clean up temp files after test."""
        yield
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        if resource_file.exists():
            resource_file.unlink()
        context_file = Path(f"/tmp/claude-context-pct-{unique_session_id}.txt")
        if context_file.exists():
            context_file.unlink()

    def _run_status_sh(
        self,
        scripts_dir: Path,
        session_id: str,
        active_agents: int,
        free_mem_mb: int,
        project_dir: Path | None = None,
    ) -> subprocess.CompletedProcess:
        """Helper to run status.sh with mocked resource values.

        Uses MOCK_ACTIVE_AGENTS and MOCK_FREE_MEM_MB env vars.
        """
        status_script = scripts_dir / "status.sh"

        if not status_script.exists():
            pytest.skip("status.sh doesn't exist yet")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir or scripts_dir.parent.parent)
        # Mock values for testing - script should check these first
        env["MOCK_ACTIVE_AGENTS"] = str(active_agents)
        env["MOCK_FREE_MEM_MB"] = str(free_mem_mb)

        input_json = json.dumps({
            "context_window": {
                "current_usage": {
                    "input_tokens": 50000,
                    "cache_read_input_tokens": 10000,
                    "cache_creation_input_tokens": 5000
                },
                "context_window_size": 200000
            },
            "workspace": {
                "current_dir": str(project_dir or scripts_dir.parent.parent)
            }
        })

        return subprocess.run(
            ["bash", str(status_script)],
            input=input_json,
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes from text."""
        return re.sub(r'\033\[[0-9;]*m', '', text)

    # ─────────────────────────────────────────────────────────────────
    # Basic Display Tests
    # ─────────────────────────────────────────────────────────────────

    def test_shows_agent_count_when_high_utilization(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """Status line shows agent count when utilization >= 50%."""
        # 6GB free RAM: (6144 - 2048) / 500 = 8 max agents
        # 5 active = 62.5% utilization
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=5, free_mem_mb=6144,
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        output = self._strip_ansi(result.stdout)

        # Should show agent count in format like "Ag:5/8" or "5/8"
        assert "5/8" in output, (
            f"Status line should show agent count '5/8' when utilization >= 50%. "
            f"Got: {output}"
        )

    def test_shows_ram_when_high_utilization(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """Status line shows RAM info when utilization >= 50%."""
        # 4GB free RAM: (4096 - 2048) / 500 = 4 max agents
        # 3 active = 75% utilization
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=3, free_mem_mb=4096,
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        output = self._strip_ansi(result.stdout)

        # Should show RAM in GB format
        assert "4G" in output or "RAM:" in output, (
            f"Status line should show RAM info when utilization >= 50%. "
            f"Got: {output}"
        )

    def test_hides_resources_when_low_utilization(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """Status line hides resource info when utilization < 50%."""
        # 10GB free RAM: (10240 - 2048) / 500 = 16 max agents
        # 2 active = 12.5% utilization
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=2, free_mem_mb=10240,
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        output = self._strip_ansi(result.stdout)

        # Should NOT show agent count when utilization is low
        # But must be careful - git status may show "A:" for added files
        # Look for specific agent format pattern
        assert "Ag:" not in output, (
            f"Status line should NOT show 'Ag:' when utilization < 50%. "
            f"Got: {output}"
        )

    def test_hides_resources_when_zero_agents(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """Status line hides resource info when no agents are running."""
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=0, free_mem_mb=8192,
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        output = self._strip_ansi(result.stdout)

        # With 0 agents, should not show resource info
        assert "Ag:" not in output and "0/" not in output, (
            f"Should not show agent info when 0 agents running. Got: {output}"
        )

    # ─────────────────────────────────────────────────────────────────
    # Color Coding Tests
    # ─────────────────────────────────────────────────────────────────

    def test_yellow_color_when_50_to_80_percent(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """Agent info is yellow when utilization is 50-80%."""
        # 6GB free: max 8 agents, 5 active = 62.5%
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=5, free_mem_mb=6144,
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        # Yellow ANSI code is \033[33m
        # Check that output contains yellow AND agent info
        output = result.stdout
        assert "\033[33m" in output and "5/8" in self._strip_ansi(output), (
            f"Agent info should be yellow (ANSI 33) at 62.5% utilization. "
            f"Got: {repr(output)}"
        )

    def test_red_color_when_above_80_percent(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """Agent info is red when utilization > 80%."""
        # 4GB free: max 4 agents, 4 active = 100%
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=4, free_mem_mb=4096,
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        # Red ANSI code is \033[31m
        output = result.stdout
        assert "\033[31m" in output and "4/4" in self._strip_ansi(output), (
            f"Agent info should be red (ANSI 31) at 100% utilization. "
            f"Got: {repr(output)}"
        )

    def test_red_at_exactly_80_percent(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """At exactly 80% utilization, shows red or yellow (boundary)."""
        # 5.5GB free: max 7 agents, 6 active = 85.7%
        # Let's use values where we get exactly 80%
        # (7168 - 2048) / 500 = 10 max, 8 active = 80%
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=8, free_mem_mb=7168,
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        output = result.stdout
        # At 80%, accept either yellow or red (implementation choice)
        has_color = "\033[33m" in output or "\033[31m" in output
        assert has_color and "8/10" in self._strip_ansi(output), (
            f"At 80% utilization, should show yellow or red. "
            f"Got: {repr(output)}"
        )

    # ─────────────────────────────────────────────────────────────────
    # Compact Format Tests
    # ─────────────────────────────────────────────────────────────────

    def test_ram_shows_gb_format(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """RAM is shown in compact GB format."""
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=5, free_mem_mb=4096,  # 4GB
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        output = self._strip_ansi(result.stdout)

        # Should show "4G" somewhere (compact format)
        assert "4G" in output, (
            f"RAM should show in GB format (4G). Got: {output}"
        )

    def test_output_fits_terminal_width(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """Status line fits in terminal width even with resource info."""
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=15, free_mem_mb=12288,  # 12GB
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        output = self._strip_ansi(result.stdout).strip()

        # Should fit in typical terminal width
        assert len(output) <= 120, (
            f"Status line should fit in terminal (<= 120 chars). "
            f"Length: {len(output)}, Content: {output}"
        )

    # ─────────────────────────────────────────────────────────────────
    # Error Handling Tests
    # ─────────────────────────────────────────────────────────────────

    def test_handles_missing_mock_env_vars_gracefully(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """Script works when mock env vars are not set (uses real values)."""
        status_script = scripts_dir / "status.sh"

        if not status_script.exists():
            pytest.skip("status.sh doesn't exist yet")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["CLAUDE_PROJECT_DIR"] = str(scripts_dir.parent.parent)
        # Don't set MOCK_* vars - should use real values

        input_json = json.dumps({
            "context_window": {
                "current_usage": {"input_tokens": 50000},
                "context_window_size": 200000
            }
        })

        result = subprocess.run(
            ["bash", str(status_script)],
            input=input_json,
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Should succeed even without mock values
        assert result.returncode == 0, f"status.sh failed: {result.stderr}"
        assert result.stdout.strip(), "Status line should produce output"


class TestResourceDisplayEdgeCases:
    """Edge case tests for resource display."""

    @pytest.fixture
    def scripts_dir(self) -> Path:
        """Path to scripts directory."""
        return Path(__file__).parents[2] / ".claude" / "scripts"

    @pytest.fixture
    def unique_session_id(self) -> str:
        """Generate unique session ID for test isolation."""
        return f"test-edge-{os.getpid()}-{id(self)}"

    @pytest.fixture
    def temp_project_dir(self):
        """Create temp directory without git."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cleanup_temp_files(self, unique_session_id: str):
        """Clean up temp files after test."""
        yield
        for pattern in [
            f"/tmp/claude-resources-{unique_session_id}.json",
            f"/tmp/claude-context-pct-{unique_session_id}.txt"
        ]:
            path = Path(pattern)
            if path.exists():
                path.unlink()

    def _run_status_sh(
        self,
        scripts_dir: Path,
        session_id: str,
        active_agents: int,
        free_mem_mb: int,
        project_dir: Path,
    ) -> subprocess.CompletedProcess:
        """Helper to run status.sh with mocked values."""
        status_script = scripts_dir / "status.sh"

        if not status_script.exists():
            pytest.skip("status.sh doesn't exist yet")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
        env["MOCK_ACTIVE_AGENTS"] = str(active_agents)
        env["MOCK_FREE_MEM_MB"] = str(free_mem_mb)

        input_json = json.dumps({
            "context_window": {
                "current_usage": {"input_tokens": 50000},
                "context_window_size": 200000
            },
            "workspace": {"current_dir": str(project_dir)}
        })

        return subprocess.run(
            ["bash", str(status_script)],
            input=input_json,
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

    def test_exactly_50_percent_shows_info(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """At exactly 50% utilization, resource info is shown."""
        # (7168 - 2048) / 500 = 10 max, 5 active = 50%
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=5, free_mem_mb=7168,
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        output = re.sub(r'\033\[[0-9;]*m', '', result.stdout)

        # At exactly 50%, should show resource info
        assert "5/10" in output, (
            f"At exactly 50% utilization, should show '5/10'. Got: {output}"
        )

    def test_just_below_50_percent_hides_info(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """At 49% utilization, resource info is hidden."""
        # (7168 - 2048) / 500 = 10 max, 4 active = 40%
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=4, free_mem_mb=7168,
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        output = re.sub(r'\033\[[0-9;]*m', '', result.stdout)

        # Below 50%, should NOT show agent resource info
        assert "Ag:" not in output, (
            f"Below 50% utilization, should not show 'Ag:'. Got: {output}"
        )

    def test_very_low_memory_clamped_to_1_max(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """With very low memory, max_agents is clamped to 1."""
        # 2GB free: (2048 - 2048) / 500 = 0, clamped to 1
        # 1 active = 100%
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=1, free_mem_mb=2048,
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        output = re.sub(r'\033\[[0-9;]*m', '', result.stdout)

        # Should show 1/1 (100% utilization)
        assert "1/1" in output, (
            f"With minimal RAM, should show '1/1'. Got: {output}"
        )

    def test_very_high_memory_clamped_to_20_max(
        self, scripts_dir: Path, unique_session_id: str, temp_project_dir: Path, cleanup_temp_files
    ) -> None:
        """With very high memory, max_agents is clamped to 20."""
        # 64GB free: (65536 - 2048) / 500 = 126, clamped to 20
        # 15 active = 75%
        result = self._run_status_sh(
            scripts_dir, unique_session_id,
            active_agents=15, free_mem_mb=65536,
            project_dir=temp_project_dir
        )

        assert result.returncode == 0, f"status.sh failed: {result.stderr}"

        output = re.sub(r'\033\[[0-9;]*m', '', result.stdout)

        # Should show /20 (clamped max)
        assert "/20" in output, (
            f"With high RAM, max should be clamped to 20. Got: {output}"
        )

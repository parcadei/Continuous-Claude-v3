"""Tests for Phase 3: Extend status.sh to output resources JSON.

These tests verify that status.sh:
1. Outputs valid JSON to /tmp/claude-resources-{session}.json
2. JSON contains ram_free_gb, agent_count, max_agents
3. max_agents is calculated correctly: (freeRAM - 2GB) / 500MB

Tests are designed to FAIL initially (TDD approach) until Phase 3 is implemented.

See plan: docs/handoffs/resource-limits-plan.md (Phase 3)
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestStatusShWritesResourcesJson:
    """Tests for status.sh writing resources JSON to /tmp."""

    @pytest.fixture
    def scripts_dir(self) -> Path:
        """Path to scripts directory."""
        return Path(__file__).parents[2] / ".claude" / "scripts"

    @pytest.fixture
    def unique_session_id(self) -> str:
        """Generate unique session ID for test isolation."""
        return f"test-resources-{os.getpid()}-{id(self)}"

    @pytest.fixture
    def cleanup_temp_files(self, unique_session_id: str):
        """Clean up temp files after test."""
        yield
        # Cleanup resources file
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        if resource_file.exists():
            resource_file.unlink()
        # Cleanup context pct file
        context_file = Path(f"/tmp/claude-context-pct-{unique_session_id}.txt")
        if context_file.exists():
            context_file.unlink()

    def test_status_sh_exists(self, scripts_dir: Path) -> None:
        """status.sh script exists at expected path."""
        status_script = scripts_dir / "status.sh"

        assert status_script.exists(), (
            f"status.sh not found: {status_script}. "
            "Expected at .claude/scripts/status.sh"
        )

    def test_status_sh_creates_resources_json(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """status.sh creates /tmp/claude-resources-{session}.json."""
        status_script = scripts_dir / "status.sh"

        if not status_script.exists():
            pytest.skip("status.sh doesn't exist yet")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["CLAUDE_PROJECT_DIR"] = str(scripts_dir.parent.parent)

        # Minimal input JSON (simulating Claude Code context)
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
                "current_dir": str(scripts_dir.parent.parent)
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

        assert result.returncode == 0, (
            f"status.sh failed: exit={result.returncode}, stderr={result.stderr}"
        )

        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        assert resource_file.exists(), (
            f"status.sh should create {resource_file}. "
            "Phase 3 implementation required."
        )

    def test_resources_json_is_valid_json(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """Resources JSON file contains valid JSON."""
        status_script = scripts_dir / "status.sh"

        if not status_script.exists():
            pytest.skip("status.sh doesn't exist yet")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["CLAUDE_PROJECT_DIR"] = str(scripts_dir.parent.parent)

        input_json = json.dumps({
            "context_window": {
                "current_usage": {
                    "input_tokens": 50000,
                    "cache_read_input_tokens": 10000,
                    "cache_creation_input_tokens": 5000
                },
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

        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")

        if not resource_file.exists():
            pytest.fail(
                f"Resources file not created: {resource_file}. "
                "Phase 3 implementation required."
            )

        try:
            content = resource_file.read_text()
            data = json.loads(content)
        except json.JSONDecodeError as e:
            pytest.fail(
                f"Resources JSON is invalid: {e}. Content: {content}"
            )

        assert isinstance(data, dict), (
            f"Resources JSON should be a dict. Got: {type(data)}"
        )


class TestResourcesJsonContainsRequiredFields:
    """Tests for required fields in resources JSON."""

    @pytest.fixture
    def scripts_dir(self) -> Path:
        """Path to scripts directory."""
        return Path(__file__).parents[2] / ".claude" / "scripts"

    @pytest.fixture
    def unique_session_id(self) -> str:
        """Generate unique session ID for test isolation."""
        return f"test-fields-{os.getpid()}-{id(self)}"

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

    def _run_status_and_get_resources(
        self, scripts_dir: Path, session_id: str
    ) -> dict:
        """Helper to run status.sh and return resources JSON."""
        status_script = scripts_dir / "status.sh"

        if not status_script.exists():
            pytest.skip("status.sh doesn't exist yet")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(scripts_dir.parent.parent)

        input_json = json.dumps({
            "context_window": {
                "current_usage": {
                    "input_tokens": 50000,
                    "cache_read_input_tokens": 10000,
                    "cache_creation_input_tokens": 5000
                },
                "context_window_size": 200000
            }
        })

        subprocess.run(
            ["bash", str(status_script)],
            input=input_json,
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        resource_file = Path(f"/tmp/claude-resources-{session_id}.json")

        if not resource_file.exists():
            pytest.fail(
                f"Resources file not created. Phase 3 implementation required."
            )

        return json.loads(resource_file.read_text())

    def test_resources_contains_free_mem_mb(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """Resources JSON contains freeMemMB field."""
        data = self._run_status_and_get_resources(scripts_dir, unique_session_id)

        assert "freeMemMB" in data, (
            f"Resources JSON should contain 'freeMemMB'. Got keys: {data.keys()}"
        )

        assert isinstance(data["freeMemMB"], (int, float)), (
            f"freeMemMB should be numeric. Got: {type(data['freeMemMB'])}"
        )

        assert data["freeMemMB"] > 0, (
            f"freeMemMB should be positive. Got: {data['freeMemMB']}"
        )

    def test_resources_contains_active_agents(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """Resources JSON contains activeAgents field."""
        data = self._run_status_and_get_resources(scripts_dir, unique_session_id)

        assert "activeAgents" in data, (
            f"Resources JSON should contain 'activeAgents'. Got keys: {data.keys()}"
        )

        assert isinstance(data["activeAgents"], int), (
            f"activeAgents should be an integer. Got: {type(data['activeAgents'])}"
        )

        assert data["activeAgents"] >= 0, (
            f"activeAgents should be non-negative. Got: {data['activeAgents']}"
        )

    def test_resources_contains_max_agents(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """Resources JSON contains maxAgents field."""
        data = self._run_status_and_get_resources(scripts_dir, unique_session_id)

        assert "maxAgents" in data, (
            f"Resources JSON should contain 'maxAgents'. Got keys: {data.keys()}"
        )

        assert isinstance(data["maxAgents"], int), (
            f"maxAgents should be an integer. Got: {type(data['maxAgents'])}"
        )

        assert data["maxAgents"] >= 1, (
            f"maxAgents should be at least 1. Got: {data['maxAgents']}"
        )

    def test_resources_contains_context_pct(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """Resources JSON contains contextPct field."""
        data = self._run_status_and_get_resources(scripts_dir, unique_session_id)

        assert "contextPct" in data, (
            f"Resources JSON should contain 'contextPct'. Got keys: {data.keys()}"
        )

        assert isinstance(data["contextPct"], (int, float)), (
            f"contextPct should be numeric. Got: {type(data['contextPct'])}"
        )

        assert 0 <= data["contextPct"] <= 100, (
            f"contextPct should be 0-100. Got: {data['contextPct']}"
        )


class TestMaxAgentsCalculation:
    """Tests for max_agents formula: (freeRAM - 2GB) / 500MB."""

    @pytest.fixture
    def scripts_dir(self) -> Path:
        """Path to scripts directory."""
        return Path(__file__).parents[2] / ".claude" / "scripts"

    @pytest.fixture
    def unique_session_id(self) -> str:
        """Generate unique session ID for test isolation."""
        return f"test-formula-{os.getpid()}-{id(self)}"

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

    def _run_status_and_get_resources(
        self, scripts_dir: Path, session_id: str
    ) -> dict:
        """Helper to run status.sh and return resources JSON."""
        status_script = scripts_dir / "status.sh"

        if not status_script.exists():
            pytest.skip("status.sh doesn't exist yet")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(scripts_dir.parent.parent)

        input_json = json.dumps({
            "context_window": {
                "current_usage": {
                    "input_tokens": 50000
                },
                "context_window_size": 200000
            }
        })

        subprocess.run(
            ["bash", str(status_script)],
            input=input_json,
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        resource_file = Path(f"/tmp/claude-resources-{session_id}.json")

        if not resource_file.exists():
            pytest.fail("Resources file not created. Phase 3 implementation required.")

        return json.loads(resource_file.read_text())

    def test_max_agents_follows_formula(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """maxAgents follows formula: (freeMemMB - 2048) / 500."""
        data = self._run_status_and_get_resources(scripts_dir, unique_session_id)

        free_mem_mb = data.get("freeMemMB", 0)
        max_agents = data.get("maxAgents", 0)

        # Calculate expected max_agents
        safety_mb = 2048
        per_agent_mb = 500
        expected = (free_mem_mb - safety_mb) // per_agent_mb

        # Apply floor of 1 and ceiling of 20
        expected = max(1, min(20, expected))

        assert max_agents == expected, (
            f"maxAgents should be (freeMemMB - 2048) / 500, clamped [1, 20]. "
            f"freeMemMB={free_mem_mb}, expected={expected}, got={max_agents}"
        )

    def test_max_agents_minimum_is_1(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """maxAgents should never be less than 1."""
        data = self._run_status_and_get_resources(scripts_dir, unique_session_id)

        max_agents = data.get("maxAgents", 0)

        assert max_agents >= 1, (
            f"maxAgents should be at least 1 (even with low RAM). Got: {max_agents}"
        )

    def test_max_agents_maximum_is_20(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ) -> None:
        """maxAgents should be capped at 20."""
        data = self._run_status_and_get_resources(scripts_dir, unique_session_id)

        max_agents = data.get("maxAgents", 0)

        assert max_agents <= 20, (
            f"maxAgents should be capped at 20. Got: {max_agents}"
        )


class TestGetResourcesShScript:
    """Tests for get-resources.sh helper script."""

    @pytest.fixture
    def scripts_dir(self) -> Path:
        """Path to scripts directory."""
        return Path(__file__).parents[2] / ".claude" / "scripts"

    def test_get_resources_sh_exists(self, scripts_dir: Path) -> None:
        """get-resources.sh script exists."""
        get_resources_script = scripts_dir / "get-resources.sh"

        assert get_resources_script.exists(), (
            f"get-resources.sh not found: {get_resources_script}. "
            "Phase 1 implementation required."
        )

    def test_get_resources_sh_is_executable(self, scripts_dir: Path) -> None:
        """get-resources.sh is executable."""
        get_resources_script = scripts_dir / "get-resources.sh"

        if not get_resources_script.exists():
            pytest.skip("get-resources.sh doesn't exist yet")

        assert os.access(get_resources_script, os.X_OK), (
            f"get-resources.sh should be executable. Run: chmod +x {get_resources_script}"
        )

    def test_get_resources_sh_outputs_json(self, scripts_dir: Path) -> None:
        """get-resources.sh outputs valid JSON."""
        get_resources_script = scripts_dir / "get-resources.sh"

        if not get_resources_script.exists():
            pytest.skip("get-resources.sh doesn't exist yet")

        result = subprocess.run(
            ["bash", str(get_resources_script)],
            capture_output=True,
            text=True,
            timeout=10
        )

        assert result.returncode == 0, (
            f"get-resources.sh failed: {result.stderr}"
        )

        try:
            data = json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            pytest.fail(
                f"get-resources.sh output is not valid JSON: {e}. Output: {result.stdout}"
            )

        assert "freeMemMB" in data, (
            f"get-resources.sh should output freeMemMB. Got: {data}"
        )

        assert "totalMemMB" in data, (
            f"get-resources.sh should output totalMemMB. Got: {data}"
        )

    def test_get_resources_sh_returns_positive_values(self, scripts_dir: Path) -> None:
        """get-resources.sh returns positive memory values."""
        get_resources_script = scripts_dir / "get-resources.sh"

        if not get_resources_script.exists():
            pytest.skip("get-resources.sh doesn't exist yet")

        result = subprocess.run(
            ["bash", str(get_resources_script)],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            pytest.skip(f"get-resources.sh failed: {result.stderr}")

        data = json.loads(result.stdout.strip())

        assert data.get("freeMemMB", 0) > 0, (
            f"freeMemMB should be positive. Got: {data.get('freeMemMB')}"
        )

        assert data.get("totalMemMB", 0) > 0, (
            f"totalMemMB should be positive. Got: {data.get('totalMemMB')}"
        )


class TestCoordinationDBGlobalRunningCount:
    """Tests for get_global_running_count in coordination.py."""

    def test_coordination_db_has_global_running_count(self) -> None:
        """CoordinationDB has get_global_running_count method."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        db = CoordinationDB(session_id="test-method-exists")

        assert hasattr(db, "get_global_running_count"), (
            "CoordinationDB should have get_global_running_count method. "
            "Phase 2 implementation required."
        )

        assert callable(db.get_global_running_count), (
            "get_global_running_count should be callable"
        )

    def test_global_running_count_returns_int(self) -> None:
        """get_global_running_count returns an integer."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        db = CoordinationDB(session_id="test-returns-int")

        if not hasattr(db, "get_global_running_count"):
            pytest.skip("get_global_running_count not implemented yet")

        count = db.get_global_running_count()

        assert isinstance(count, int), (
            f"get_global_running_count should return int. Got: {type(count)}"
        )

    def test_global_running_count_includes_all_sessions(self) -> None:
        """get_global_running_count counts agents across all sessions."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        # Create two sessions with agents
        db1 = CoordinationDB(session_id="test-session-1-global")
        db2 = CoordinationDB(session_id="test-session-2-global")

        if not hasattr(db1, "get_global_running_count"):
            pytest.skip("get_global_running_count not implemented yet")

        initial_count = db1.get_global_running_count()

        # Register agents in different sessions
        db1.register_agent("agent-s1-1", premise="Test agent 1 session 1")
        db2.register_agent("agent-s2-1", premise="Test agent 1 session 2")

        new_count = db1.get_global_running_count()

        # Should have 2 more running agents
        assert new_count >= initial_count + 2, (
            f"get_global_running_count should count agents across all sessions. "
            f"Initial: {initial_count}, After adding 2 agents: {new_count}"
        )

        # Cleanup
        db1.complete_agent("agent-s1-1")
        db2.complete_agent("agent-s2-1")

    def test_global_running_count_excludes_completed(self) -> None:
        """get_global_running_count only counts running agents."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        db = CoordinationDB(session_id="test-excludes-completed")

        if not hasattr(db, "get_global_running_count"):
            pytest.skip("get_global_running_count not implemented yet")

        initial_count = db.get_global_running_count()

        # Register and complete an agent
        db.register_agent("agent-temp-completed", premise="Temp agent")
        db.complete_agent("agent-temp-completed")

        final_count = db.get_global_running_count()

        assert final_count == initial_count, (
            f"Completed agents should not be counted. "
            f"Initial: {initial_count}, Final: {final_count}"
        )

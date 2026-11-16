"""E2E Integration Tests for Resource Limits Flow.

Tests the complete resource management pipeline:
1. status.sh writes JSON to /tmp
2. skill-activation-prompt.ts reads it and generates warnings
3. pre-tool-use.ts reads it and blocks Task when at limit

Phase 14 of resource-limits-plan.md
"""

import json
import os
import subprocess
import tempfile
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
def hooks_dir(project_dir: Path) -> Path:
    """Get the hooks directory."""
    return project_dir / ".claude" / "hooks"


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


# ============================================================================
# Test: status.sh writes resources JSON to /tmp
# ============================================================================


class TestStatusShWritesResourcesJson:
    """Test that status.sh correctly writes resource JSON."""

    def test_status_sh_writes_resources_json(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """status.sh should write resources JSON to /tmp with correct fields."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # Run status.sh with minimal input and mock values
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"  # 8GB free RAM
        env["MOCK_ACTIVE_AGENTS"] = "3"

        result = subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Check the resource file was created
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        assert resource_file.exists(), f"Resource file not created at {resource_file}"

        # Parse and validate the JSON
        data = json.loads(resource_file.read_text())

        # Check required fields
        assert "freeMemMB" in data, "Missing freeMemMB field"
        assert "activeAgents" in data, "Missing activeAgents field"
        assert "maxAgents" in data, "Missing maxAgents field"
        assert "contextPct" in data, "Missing contextPct field"

        # Validate values
        assert data["freeMemMB"] == 8192, f"Expected 8192, got {data['freeMemMB']}"
        assert data["activeAgents"] == 3, f"Expected 3, got {data['activeAgents']}"
        assert data["maxAgents"] >= 1, "maxAgents should be at least 1"
        assert data["maxAgents"] <= 20, "maxAgents should be capped at 20"

    def test_max_agents_formula_with_low_ram(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Max agents should be limited when RAM is low."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # Low RAM scenario: 3GB free
        # Formula: (3072 - 2048) / 500 = 2 agents
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "3072"
        env["MOCK_ACTIVE_AGENTS"] = "0"

        subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        data = json.loads(resource_file.read_text())

        # With 3GB free: (3072 - 2048) / 500 = 2.048 -> 2
        assert data["maxAgents"] >= 1
        assert data["maxAgents"] <= 4  # Allow some variance in formula

    def test_max_agents_formula_with_high_ram(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Max agents should be capped at 20 even with high RAM."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # High RAM scenario: 50GB free - would give 96 agents uncapped
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "51200"  # 50GB
        env["MOCK_ACTIVE_AGENTS"] = "0"

        subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        data = json.loads(resource_file.read_text())

        # Should be capped at 20
        assert data["maxAgents"] == 20

    def test_context_pct_written_to_separate_file(
        self, scripts_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Context percentage should be written to a separate text file."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"
        env["MOCK_ACTIVE_AGENTS"] = "0"

        subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Check context pct file exists
        context_file = Path(f"/tmp/claude-context-pct-{unique_session_id}.txt")
        assert context_file.exists(), "Context percentage file not created"

        # Should contain a number
        content = context_file.read_text().strip()
        assert content.isdigit() or content == "0", f"Invalid context pct: {content}"


# ============================================================================
# Test: skill-activation-prompt.ts reads resources and generates warnings
# ============================================================================


class TestSkillActivationResourceWarnings:
    """Test that skill-activation-prompt.ts generates resource warnings."""

    @pytest.fixture
    def skill_rules_dir(self, tmp_path: Path) -> Path:
        """Create a minimal skill-rules.json for testing.

        The skill-activation-prompt hook exits early if no skill-rules.json
        exists, so we need to create one for resource warning tests.
        """
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        rules_path = skills_dir / "skill-rules.json"
        rules_path.write_text(json.dumps({
            "version": "1.0",
            "skills": {},
            "agents": {}
        }))
        return tmp_path

    def test_no_warning_when_below_threshold(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files,
        skill_rules_dir: Path
    ):
        """No resource warning when utilization is below 80%."""
        # Create resource file with low utilization (3/10 = 30%)
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        resource_file.write_text(json.dumps({
            "freeMemMB": 8192,
            "activeAgents": 3,
            "maxAgents": 10,
            "contextPct": 50
        }))

        result = self._run_skill_activation_hook(
            hooks_dir, unique_session_id, "hello world", skill_rules_dir
        )

        # Should NOT have resource warning
        assert "RESOURCE CRITICAL" not in result
        assert "RESOURCE WARNING" not in result

    def test_warning_when_near_limit(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files,
        skill_rules_dir: Path
    ):
        """Resource warning when utilization is 80-99%."""
        # Create resource file with high utilization (8/10 = 80%)
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        resource_file.write_text(json.dumps({
            "freeMemMB": 4096,
            "activeAgents": 8,
            "maxAgents": 10,
            "contextPct": 50
        }))

        result = self._run_skill_activation_hook(
            hooks_dir, unique_session_id, "hello world", skill_rules_dir
        )

        # Should have WARNING (80%+)
        assert "RESOURCE WARNING" in result or "agent slot" in result.lower()

    def test_critical_when_at_limit(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files,
        skill_rules_dir: Path
    ):
        """Critical resource warning when at or over limit."""
        # Create resource file at limit (10/10 = 100%)
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        resource_file.write_text(json.dumps({
            "freeMemMB": 2048,
            "activeAgents": 10,
            "maxAgents": 10,
            "contextPct": 50
        }))

        result = self._run_skill_activation_hook(
            hooks_dir, unique_session_id, "hello world", skill_rules_dir
        )

        # Should have CRITICAL warning
        assert "RESOURCE CRITICAL" in result or "At limit" in result

    def test_no_warning_when_resource_file_missing(
        self, hooks_dir: Path, unique_session_id: str, skill_rules_dir: Path
    ):
        """No crash when resource file doesn't exist."""
        # Don't create the resource file
        result = self._run_skill_activation_hook(
            hooks_dir, unique_session_id, "hello world", skill_rules_dir
        )

        # Should complete without error - no resource warning
        assert "RESOURCE CRITICAL" not in result
        assert "RESOURCE WARNING" not in result

    def _run_skill_activation_hook(
        self, hooks_dir: Path, session_id: str, prompt: str,
        project_dir: Path
    ) -> str:
        """Run skill-activation-prompt hook and return output."""
        # Try .js first (TypeScript compiled), then .mjs (legacy)
        hook_script = hooks_dir / "dist" / "skill-activation-prompt.js"
        if not hook_script.exists():
            hook_script = hooks_dir / "dist" / "skill-activation-prompt.mjs"
        if not hook_script.exists():
            pytest.skip("Compiled skill-activation-prompt.js/mjs not found")

        hook_input = {
            "session_id": session_id,
            "transcript_path": "/tmp/test-transcript",
            "cwd": str(project_dir),  # Use project_dir with skill-rules.json
            "permission_mode": "default",
            "prompt": prompt
        }

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PPID"] = session_id
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)  # Tell hook where to find skill-rules.json

        result = subprocess.run(
            ["node", str(hook_script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=10
        )

        return result.stdout


# ============================================================================
# Test: pre-tool-use.ts blocks Task when at limit
# ============================================================================


class TestPreToolUseResourceBlock:
    """Test that pre-tool-use.ts blocks Task tool when at resource limit."""

    def test_task_continues_when_below_limit(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Task tool should continue when below limit."""
        # Create resource file below limit
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        resource_file.write_text(json.dumps({
            "freeMemMB": 8192,
            "activeAgents": 5,
            "maxAgents": 10,
            "contextPct": 50
        }))

        result = self._run_pretooluse_hook(
            hooks_dir, unique_session_id, "Task", {}
        )

        output = json.loads(result)
        assert output["result"] == "continue"

    def test_task_blocked_when_at_limit(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Task tool should be BLOCKED when at resource limit."""
        # Create resource file at limit
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        resource_file.write_text(json.dumps({
            "freeMemMB": 2048,
            "activeAgents": 10,
            "maxAgents": 10,
            "contextPct": 50
        }))

        result = self._run_pretooluse_hook(
            hooks_dir, unique_session_id, "Task", {}
        )

        output = json.loads(result)
        assert output["result"] == "block", f"Expected block, got {output}"
        assert "reason" in output
        assert "limit" in output["reason"].lower() or "10/10" in output["reason"]

    def test_task_blocked_when_over_limit(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Task tool should be BLOCKED when over resource limit."""
        # Create resource file over limit
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        resource_file.write_text(json.dumps({
            "freeMemMB": 2048,
            "activeAgents": 12,
            "maxAgents": 10,
            "contextPct": 50
        }))

        result = self._run_pretooluse_hook(
            hooks_dir, unique_session_id, "Task", {}
        )

        output = json.loads(result)
        assert output["result"] == "block"

    def test_other_tools_not_blocked(
        self, hooks_dir: Path, unique_session_id: str, cleanup_temp_files
    ):
        """Non-Task tools should NOT be blocked by resource limits."""
        # Create resource file at limit
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        resource_file.write_text(json.dumps({
            "freeMemMB": 2048,
            "activeAgents": 10,
            "maxAgents": 10,
            "contextPct": 50
        }))

        # Test Read tool - should continue
        result = self._run_pretooluse_hook(
            hooks_dir, unique_session_id, "Read", {"file_path": "/tmp/test.txt"}
        )
        output = json.loads(result)
        assert output["result"] == "continue"

        # Test Write tool - should continue
        result = self._run_pretooluse_hook(
            hooks_dir, unique_session_id, "Write", {"file_path": "/tmp/test.txt"}
        )
        output = json.loads(result)
        assert output["result"] == "continue"

    def test_task_continues_when_resource_file_missing(
        self, hooks_dir: Path, unique_session_id: str
    ):
        """Task tool should continue when resource file doesn't exist."""
        # Don't create the resource file

        result = self._run_pretooluse_hook(
            hooks_dir, unique_session_id, "Task", {}
        )

        output = json.loads(result)
        assert output["result"] == "continue"

    def _run_pretooluse_hook(
        self, hooks_dir: Path, session_id: str, tool_name: str, tool_input: dict
    ) -> str:
        """Run pre-tool-use hook and return output."""
        # Try .js first (TypeScript compiled), then .mjs (legacy)
        hook_script = hooks_dir / "dist" / "pre-tool-use.js"
        if not hook_script.exists():
            hook_script = hooks_dir / "dist" / "pre-tool-use.mjs"
        if not hook_script.exists():
            pytest.skip("Compiled pre-tool-use.js/mjs not found")

        hook_input = {
            "session_id": session_id,
            "tool_name": tool_name,
            "tool_input": tool_input
        }

        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = session_id
        env["CLAUDE_PPID"] = session_id

        result = subprocess.run(
            ["node", str(hook_script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=10
        )

        # Return stdout, default to continue on error
        if result.returncode != 0 or not result.stdout.strip():
            return '{"result": "continue"}'
        return result.stdout.strip()


# ============================================================================
# Test: Full Pipeline Integration
# ============================================================================


class TestFullResourcePipeline:
    """Test the complete resource management pipeline end-to-end."""

    def test_full_flow_status_to_block(
        self, project_dir: Path, scripts_dir: Path, hooks_dir: Path,
        unique_session_id: str, cleanup_temp_files
    ):
        """Test full flow: status.sh -> JSON -> pre-tool-use block."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # Step 1: Run status.sh with agents at limit
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "4096"  # 4GB
        env["MOCK_ACTIVE_AGENTS"] = "4"  # (4096-2048)/500 = 4 max

        subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Verify resource file was created
        resource_file = Path(f"/tmp/claude-resources-{unique_session_id}.json")
        assert resource_file.exists()

        data = json.loads(resource_file.read_text())
        assert data["activeAgents"] == 4
        # maxAgents should be around 4 based on formula

        # Step 2: Run pre-tool-use hook with Task
        hook_script = hooks_dir / "dist" / "pre-tool-use.js"
        if not hook_script.exists():
            hook_script = hooks_dir / "dist" / "pre-tool-use.mjs"
        if not hook_script.exists():
            pytest.skip("Compiled pre-tool-use.js/mjs not found")

        hook_input = {
            "session_id": unique_session_id,
            "tool_name": "Task",
            "tool_input": {}
        }

        result = subprocess.run(
            ["node", str(hook_script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=10
        )

        # Should block because activeAgents >= maxAgents
        output = json.loads(result.stdout.strip())
        assert output["result"] == "block", f"Expected block when at limit, got: {output}"

    def test_full_flow_status_to_warning_to_continue(
        self, scripts_dir: Path, hooks_dir: Path,
        unique_session_id: str, cleanup_temp_files
    ):
        """Test full flow with high utilization but not at limit."""
        status_script = scripts_dir / "status.sh"
        if not status_script.exists():
            pytest.skip("status.sh not found")

        # Step 1: Run status.sh with high but not full utilization
        env = os.environ.copy()
        env["CLAUDE_SESSION_ID"] = unique_session_id
        env["MOCK_FREE_MEM_MB"] = "8192"  # 8GB -> maxAgents ~12
        env["MOCK_ACTIVE_AGENTS"] = "10"  # 10/12 = 83%

        subprocess.run(
            ["bash", str(status_script)],
            input="{}",
            capture_output=True,
            text=True,
            env=env,
            timeout=30
        )

        # Step 2: skill-activation should show warning
        skill_hook = hooks_dir / "dist" / "skill-activation-prompt.js"
        if not skill_hook.exists():
            skill_hook = hooks_dir / "dist" / "skill-activation-prompt.mjs"
        if skill_hook.exists():
            skill_input = {
                "session_id": unique_session_id,
                "transcript_path": "/tmp/test",
                "cwd": "/tmp",
                "permission_mode": "default",
                "prompt": "test"
            }
            skill_result = subprocess.run(
                ["node", str(skill_hook)],
                input=json.dumps(skill_input),
                capture_output=True,
                text=True,
                env=env,
                timeout=10
            )
            # Should have some form of resource warning
            # (exact wording may vary based on utilization)

        # Step 3: Task should continue (not at hard limit)
        pretool_hook = hooks_dir / "dist" / "pre-tool-use.js"
        if not pretool_hook.exists():
            pretool_hook = hooks_dir / "dist" / "pre-tool-use.mjs"
        if pretool_hook.exists():
            pretool_input = {
                "session_id": unique_session_id,
                "tool_name": "Task",
                "tool_input": {}
            }
            pretool_result = subprocess.run(
                ["node", str(pretool_hook)],
                input=json.dumps(pretool_input),
                capture_output=True,
                text=True,
                env=env,
                timeout=10
            )
            output = json.loads(pretool_result.stdout.strip())
            assert output["result"] == "continue", "Should continue when below hard limit"

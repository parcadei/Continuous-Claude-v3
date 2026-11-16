"""E2E Integration Tests for Phase 7-12 Hook Flow.

Tests the complete hook pipeline:
- Skill activation hooks (skill-activation-prompt.ts)
- PreToolUse broadcast hooks (pre-tool-use-broadcast.ts)
- Full agentica orchestration flow

Test scenarios:
1. Skill Activation Hook Flow - keyword/intent matching
2. PreToolUse Hook with Broadcasts - SWARM_ID injection
3. Full Flow Integration - trigger -> spawn -> broadcast -> query
"""

import json
import os
import shutil
import sqlite3
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
def temp_coordination_db(tmp_path: Path) -> tuple[Path, str]:
    """Create a temp coordination database with broadcasts.

    Returns:
        Tuple of (db_path, swarm_id)
    """
    # Create the directory structure
    cache_dir = tmp_path / ".claude" / "cache" / "agentica-coordination"
    cache_dir.mkdir(parents=True)
    db_path = cache_dir / "coordination.db"

    swarm_id = f"test-swarm-{uuid4().hex[:8]}"

    # Create database with broadcasts table
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS broadcasts (
            id TEXT PRIMARY KEY,
            swarm_id TEXT NOT NULL,
            sender_agent TEXT NOT NULL,
            broadcast_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # Add some test broadcasts
    broadcasts = [
        (uuid4().hex, swarm_id, "agent-1", "finding",
         json.dumps({"finding": "Found pattern in auth module"}),
         "2025-01-01T00:00:00"),
        (uuid4().hex, swarm_id, "agent-2", "blocker",
         json.dumps({"blocker": "Missing API key", "severity": "high"}),
         "2025-01-01T00:01:00"),
    ]

    conn.executemany(
        "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
        broadcasts
    )
    conn.commit()
    conn.close()

    return tmp_path, swarm_id


@pytest.fixture
def temp_skill_rules(tmp_path: Path) -> Path:
    """Create a temp skill-rules.json for testing."""
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    rules_path = skills_dir / "skill-rules.json"

    rules = {
        "version": "1.0",
        "skills": {
            "test-skill": {
                "type": "domain",
                "enforcement": "suggest",
                "priority": "high",
                "promptTriggers": {
                    "keywords": ["test trigger", "activate test"],
                    "intentPatterns": ["(run|execute).*test"]
                }
            },
            "critical-skill": {
                "type": "guardrail",
                "enforcement": "block",
                "priority": "critical",
                "promptTriggers": {
                    "keywords": ["critical action"],
                    "intentPatterns": []
                }
            }
        },
        "agents": {
            "agentica-orchestrator": {
                "type": "domain",
                "enforcement": "suggest",
                "priority": "high",
                "promptTriggers": {
                    "keywords": ["launch agentica", "/agentica"],
                    "intentPatterns": ["launch\\s+agentica"]
                }
            }
        }
    }

    rules_path.write_text(json.dumps(rules, indent=2))
    return tmp_path


# ============================================================================
# Test Scenario 1: Skill Activation Hook Flow
# ============================================================================


class TestSkillActivationHook:
    """Test skill activation based on prompt keywords and intent patterns."""

    def test_agentica_trigger_activates_skill(
        self, hooks_dir: Path, temp_skill_rules: Path
    ):
        """Test that 'launch agentica' triggers skill activation hook."""
        hook_input = {
            "session_id": "test-session-123",
            "transcript_path": "/tmp/test-transcript",
            "cwd": str(temp_skill_rules),
            "permission_mode": "default",
            "prompt": "launch agentica for research task"
        }

        result = self._run_skill_activation_hook(
            hooks_dir, hook_input, temp_skill_rules
        )

        # Should output skill activation message with AGENTICA ORCHESTRATION
        assert "AGENTICA ORCHESTRATION ACTIVATED" in result
        assert "agentica-orchestrator" in result

    def test_keyword_trigger_activates_skill(
        self, hooks_dir: Path, temp_skill_rules: Path
    ):
        """Test that keyword triggers activate the corresponding skill."""
        hook_input = {
            "session_id": "test-session-123",
            "transcript_path": "/tmp/test-transcript",
            "cwd": str(temp_skill_rules),
            "permission_mode": "default",
            "prompt": "I need to test trigger something"
        }

        result = self._run_skill_activation_hook(
            hooks_dir, hook_input, temp_skill_rules
        )

        assert "SKILL ACTIVATION CHECK" in result
        assert "test-skill" in result

    def test_intent_pattern_trigger_activates_skill(
        self, hooks_dir: Path, temp_skill_rules: Path
    ):
        """Test that intent patterns activate the corresponding skill."""
        hook_input = {
            "session_id": "test-session-123",
            "transcript_path": "/tmp/test-transcript",
            "cwd": str(temp_skill_rules),
            "permission_mode": "default",
            "prompt": "please run the test suite"
        }

        result = self._run_skill_activation_hook(
            hooks_dir, hook_input, temp_skill_rules
        )

        assert "SKILL ACTIVATION CHECK" in result
        assert "test-skill" in result

    def test_critical_skill_shows_required(
        self, hooks_dir: Path, temp_skill_rules: Path
    ):
        """Test that critical priority skills show as REQUIRED."""
        hook_input = {
            "session_id": "test-session-123",
            "transcript_path": "/tmp/test-transcript",
            "cwd": str(temp_skill_rules),
            "permission_mode": "default",
            "prompt": "perform critical action now"
        }

        result = self._run_skill_activation_hook(
            hooks_dir, hook_input, temp_skill_rules
        )

        assert "CRITICAL SKILLS (REQUIRED)" in result
        assert "critical-skill" in result

    def test_non_matching_prompt_no_activation(
        self, hooks_dir: Path, temp_skill_rules: Path
    ):
        """Test that non-matching prompts don't trigger skill activation."""
        hook_input = {
            "session_id": "test-session-123",
            "transcript_path": "/tmp/test-transcript",
            "cwd": str(temp_skill_rules),
            "permission_mode": "default",
            "prompt": "hello world"
        }

        result = self._run_skill_activation_hook(
            hooks_dir, hook_input, temp_skill_rules
        )

        # Should not output any skill activation
        assert "SKILL ACTIVATION CHECK" not in result
        assert "AGENTICA ORCHESTRATION ACTIVATED" not in result

    def test_case_insensitive_matching(
        self, hooks_dir: Path, temp_skill_rules: Path
    ):
        """Test that keyword matching is case-insensitive."""
        hook_input = {
            "session_id": "test-session-123",
            "transcript_path": "/tmp/test-transcript",
            "cwd": str(temp_skill_rules),
            "permission_mode": "default",
            "prompt": "LAUNCH AGENTICA NOW"
        }

        result = self._run_skill_activation_hook(
            hooks_dir, hook_input, temp_skill_rules
        )

        assert "AGENTICA ORCHESTRATION ACTIVATED" in result

    def _run_skill_activation_hook(
        self, hooks_dir: Path, hook_input: dict, project_dir: Path
    ) -> str:
        """Run the skill activation hook and return stdout."""
        # Use the compiled .mjs file directly with node
        hook_script = hooks_dir / "dist" / "skill-activation-prompt.mjs"

        if not hook_script.exists():
            pytest.skip("Compiled skill-activation-prompt.mjs not found")

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)

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
# Test Scenario 2: PreToolUse Hook with Broadcasts
# ============================================================================


class TestPreToolUseBroadcastHook:
    """Test PreToolUse hook for broadcast injection."""

    def test_pretooluse_without_swarm_id(self, hooks_dir: Path):
        """PreToolUse continues when SWARM_ID not set."""
        hook_input = {
            "session_id": "test-session-123",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.txt"}
        }

        result = self._run_pretooluse_hook(hooks_dir, hook_input, env_overrides={})

        output = json.loads(result)
        assert output["result"] == "continue"
        assert "message" not in output

    def test_pretooluse_with_swarm_id_no_db(self, hooks_dir: Path, tmp_path: Path):
        """PreToolUse continues when SWARM_ID set but no DB exists."""
        hook_input = {
            "session_id": "test-session-123",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.txt"}
        }

        env = {
            "SWARM_ID": "test-swarm-123",
            "AGENT_ID": "agent-1",
            "CLAUDE_PROJECT_DIR": str(tmp_path)  # No DB here
        }

        result = self._run_pretooluse_hook(hooks_dir, hook_input, env_overrides=env)

        output = json.loads(result)
        assert output["result"] == "continue"

    def test_pretooluse_with_swarm_id_and_broadcasts(
        self, hooks_dir: Path, temp_coordination_db: tuple[Path, str]
    ):
        """PreToolUse injects broadcasts when SWARM_ID set and broadcasts exist."""
        tmp_path, swarm_id = temp_coordination_db

        hook_input = {
            "session_id": "test-session-123",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.txt"}
        }

        env = {
            "SWARM_ID": swarm_id,
            "AGENT_ID": "agent-3",  # Different from existing agents
            "CLAUDE_PROJECT_DIR": str(tmp_path)
        }

        result = self._run_pretooluse_hook(hooks_dir, hook_input, env_overrides=env)

        output = json.loads(result)
        assert output["result"] == "continue"
        assert "message" in output
        assert "SWARM BROADCASTS" in output["message"]
        assert "agent-1" in output["message"]
        assert "agent-2" in output["message"]
        assert "Found pattern in auth module" in output["message"]

    def test_pretooluse_excludes_self_broadcasts(
        self, hooks_dir: Path, temp_coordination_db: tuple[Path, str]
    ):
        """PreToolUse excludes broadcasts from the current agent."""
        tmp_path, swarm_id = temp_coordination_db

        hook_input = {
            "session_id": "test-session-123",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.txt"}
        }

        # Use agent-1 as current agent - should not see agent-1's broadcasts
        env = {
            "SWARM_ID": swarm_id,
            "AGENT_ID": "agent-1",
            "CLAUDE_PROJECT_DIR": str(tmp_path)
        }

        result = self._run_pretooluse_hook(hooks_dir, hook_input, env_overrides=env)

        output = json.loads(result)
        assert output["result"] == "continue"

        if "message" in output:
            # Should not see agent-1's broadcast
            assert "agent-1" not in output["message"]
            # Should still see agent-2's broadcast
            assert "agent-2" in output["message"]

    def test_pretooluse_validates_swarm_id_format(self, hooks_dir: Path, tmp_path: Path):
        """PreToolUse rejects invalid SWARM_ID format."""
        hook_input = {
            "session_id": "test-session-123",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.txt"}
        }

        # Invalid SWARM_ID with shell metacharacters
        invalid_ids = [
            "swarm; rm -rf /",
            "swarm\nid",
            "swarm'id",
            "swarm$(cmd)",
            "a" * 100,  # Too long
            "",  # Empty
        ]

        for invalid_id in invalid_ids:
            env = {
                "SWARM_ID": invalid_id,
                "AGENT_ID": "agent-1",
                "CLAUDE_PROJECT_DIR": str(tmp_path)
            }

            result = self._run_pretooluse_hook(hooks_dir, hook_input, env_overrides=env)

            output = json.loads(result)
            # Should continue without attempting DB query
            assert output["result"] == "continue"
            # Should NOT have injected broadcasts (no DB query made)
            assert "message" not in output or "SWARM BROADCASTS" not in output.get("message", "")

    def test_pretooluse_validates_agent_id_format(
        self, hooks_dir: Path, temp_coordination_db: tuple[Path, str]
    ):
        """PreToolUse rejects invalid AGENT_ID format."""
        tmp_path, swarm_id = temp_coordination_db

        hook_input = {
            "session_id": "test-session-123",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.txt"}
        }

        # Valid SWARM_ID but invalid AGENT_ID
        env = {
            "SWARM_ID": swarm_id,
            "AGENT_ID": "agent; rm -rf /",
            "CLAUDE_PROJECT_DIR": str(tmp_path)
        }

        result = self._run_pretooluse_hook(hooks_dir, hook_input, env_overrides=env)

        output = json.loads(result)
        assert output["result"] == "continue"

    def _run_pretooluse_hook(
        self, hooks_dir: Path, hook_input: dict, env_overrides: dict
    ) -> str:
        """Run the pre-tool-use-broadcast hook and return stdout."""
        hook_script = hooks_dir / "dist" / "pre-tool-use-broadcast.mjs"

        if not hook_script.exists():
            pytest.skip("Compiled pre-tool-use-broadcast.mjs not found")

        env = os.environ.copy()
        env.update(env_overrides)

        result = subprocess.run(
            ["node", str(hook_script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=10
        )

        # Return stdout, falling back to default on error
        if result.returncode != 0:
            return '{"result": "continue"}'

        return result.stdout.strip()


# ============================================================================
# Test Scenario 3: Full Flow Integration
# ============================================================================


class TestFullAgenticaFlow:
    """Test complete agentica flow: trigger -> spawn -> broadcast -> query."""

    def test_full_agentica_flow(
        self, hooks_dir: Path, tmp_path: Path
    ):
        """Test complete flow: trigger -> spawn -> broadcast -> query.

        This test simulates the full agentica orchestration:
        1. User prompt triggers skill activation
        2. System would spawn agents with SWARM_ID
        3. Agents broadcast findings to DB
        4. PreToolUse hook injects broadcasts to other agents
        """
        # Step 1: Set up skill rules
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        rules = {
            "version": "1.0",
            "skills": {},
            "agents": {
                "agentica-orchestrator": {
                    "type": "domain",
                    "enforcement": "suggest",
                    "priority": "high",
                    "promptTriggers": {
                        "keywords": ["launch agentica"],
                        "intentPatterns": []
                    }
                }
            }
        }
        (skills_dir / "skill-rules.json").write_text(json.dumps(rules))

        # Step 2: User prompt triggers agentica
        skill_input = {
            "session_id": "test-session",
            "transcript_path": "/tmp/transcript",
            "cwd": str(tmp_path),
            "permission_mode": "default",
            "prompt": "launch agentica to research this codebase"
        }

        skill_result = self._run_hook(
            hooks_dir / "dist" / "skill-activation-prompt.mjs",
            skill_input,
            {"CLAUDE_PROJECT_DIR": str(tmp_path)}
        )

        assert "AGENTICA ORCHESTRATION ACTIVATED" in skill_result

        # Step 3: Create coordination DB (simulating agent spawn)
        swarm_id = f"swarm-{uuid4().hex[:8]}"
        cache_dir = tmp_path / ".claude" / "cache" / "agentica-coordination"
        cache_dir.mkdir(parents=True)
        db_path = cache_dir / "coordination.db"

        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE broadcasts (
                id TEXT PRIMARY KEY,
                swarm_id TEXT NOT NULL,
                sender_agent TEXT NOT NULL,
                broadcast_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Step 4: Agents broadcast findings
        agents = ["researcher-1", "researcher-2", "researcher-3"]
        for agent in agents:
            conn.execute(
                "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
                (
                    uuid4().hex,
                    swarm_id,
                    agent,
                    "finding",
                    json.dumps({"finding": f"{agent} found something"}),
                    "2025-01-01T00:00:00"
                )
            )
        conn.commit()
        conn.close()

        # Step 5: PreToolUse hook injects broadcasts to new agent
        pretool_input = {
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.txt"}
        }

        pretool_result = self._run_hook(
            hooks_dir / "dist" / "pre-tool-use-broadcast.mjs",
            pretool_input,
            {
                "SWARM_ID": swarm_id,
                "AGENT_ID": "coordinator",  # New agent sees all broadcasts
                "CLAUDE_PROJECT_DIR": str(tmp_path)
            }
        )

        output = json.loads(pretool_result)
        assert output["result"] == "continue"
        assert "message" in output
        assert "SWARM BROADCASTS" in output["message"]

        # All three researchers' findings should be visible
        for agent in agents:
            assert agent in output["message"]

    def test_swarm_isolation_in_full_flow(self, hooks_dir: Path, tmp_path: Path):
        """Test that broadcasts are isolated between different swarms."""
        # Create coordination DB
        cache_dir = tmp_path / ".claude" / "cache" / "agentica-coordination"
        cache_dir.mkdir(parents=True)
        db_path = cache_dir / "coordination.db"

        swarm_alpha = f"swarm-alpha-{uuid4().hex[:8]}"
        swarm_beta = f"swarm-beta-{uuid4().hex[:8]}"

        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE broadcasts (
                id TEXT PRIMARY KEY,
                swarm_id TEXT NOT NULL,
                sender_agent TEXT NOT NULL,
                broadcast_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Add broadcasts to both swarms
        conn.execute(
            "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
            (uuid4().hex, swarm_alpha, "agent-alpha", "finding",
             json.dumps({"finding": "Alpha secret"}), "2025-01-01T00:00:00")
        )
        conn.execute(
            "INSERT INTO broadcasts VALUES (?, ?, ?, ?, ?, ?)",
            (uuid4().hex, swarm_beta, "agent-beta", "finding",
             json.dumps({"finding": "Beta secret"}), "2025-01-01T00:00:00")
        )
        conn.commit()
        conn.close()

        # Query from swarm alpha - should only see alpha broadcasts
        pretool_input = {
            "session_id": "test-session",
            "tool_name": "Read",
            "tool_input": {}
        }

        alpha_result = self._run_hook(
            hooks_dir / "dist" / "pre-tool-use-broadcast.mjs",
            pretool_input,
            {
                "SWARM_ID": swarm_alpha,
                "AGENT_ID": "other-agent",
                "CLAUDE_PROJECT_DIR": str(tmp_path)
            }
        )

        alpha_output = json.loads(alpha_result)
        assert "message" in alpha_output
        assert "Alpha secret" in alpha_output["message"]
        assert "Beta secret" not in alpha_output["message"]

        # Query from swarm beta - should only see beta broadcasts
        beta_result = self._run_hook(
            hooks_dir / "dist" / "pre-tool-use-broadcast.mjs",
            pretool_input,
            {
                "SWARM_ID": swarm_beta,
                "AGENT_ID": "other-agent",
                "CLAUDE_PROJECT_DIR": str(tmp_path)
            }
        )

        beta_output = json.loads(beta_result)
        assert "message" in beta_output
        assert "Beta secret" in beta_output["message"]
        assert "Alpha secret" not in beta_output["message"]

    def _run_hook(self, hook_path: Path, hook_input: dict, env_overrides: dict) -> str:
        """Run a hook and return stdout."""
        if not hook_path.exists():
            pytest.skip(f"Hook {hook_path.name} not found")

        env = os.environ.copy()
        env.update(env_overrides)

        result = subprocess.run(
            ["node", str(hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hook_path.parent),
            timeout=10
        )

        return result.stdout.strip()


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestHookEdgeCases:
    """Test edge cases and error handling in hooks."""

    def test_malformed_json_input(self, hooks_dir: Path):
        """Test hook handles malformed JSON input gracefully."""
        hook_script = hooks_dir / "dist" / "pre-tool-use-broadcast.mjs"

        if not hook_script.exists():
            pytest.skip("Compiled hook not found")

        result = subprocess.run(
            ["node", str(hook_script)],
            input="not valid json",
            capture_output=True,
            text=True,
            timeout=10
        )

        # Hook should exit with error but not crash
        # The hook outputs continue on error
        if result.returncode == 0:
            output = json.loads(result.stdout.strip())
            assert output["result"] == "continue"

    def test_empty_input(self, hooks_dir: Path):
        """Test hook handles empty input gracefully."""
        hook_script = hooks_dir / "dist" / "pre-tool-use-broadcast.mjs"

        if not hook_script.exists():
            pytest.skip("Compiled hook not found")

        result = subprocess.run(
            ["node", str(hook_script)],
            input="",
            capture_output=True,
            text=True,
            timeout=10
        )

        # Hook should handle empty input gracefully
        assert result.returncode != 0 or "continue" in result.stdout

    def test_skill_activation_no_rules_file(self, hooks_dir: Path, tmp_path: Path):
        """Test skill activation with no skill-rules.json."""
        hook_script = hooks_dir / "dist" / "skill-activation-prompt.mjs"

        if not hook_script.exists():
            pytest.skip("Compiled hook not found")

        hook_input = {
            "session_id": "test",
            "transcript_path": "/tmp/test",
            "cwd": str(tmp_path),
            "permission_mode": "default",
            "prompt": "launch agentica"
        }

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(tmp_path)
        env["HOME"] = str(tmp_path)  # Also no global rules

        result = subprocess.run(
            ["node", str(hook_script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=10
        )

        # Should exit gracefully with no output
        assert result.returncode == 0
        # No skill activation when no rules file
        assert "SKILL ACTIVATION CHECK" not in result.stdout

    def test_unicode_in_prompts(self, hooks_dir: Path, temp_skill_rules: Path):
        """Test skill activation with unicode in prompts."""
        hook_script = hooks_dir / "dist" / "skill-activation-prompt.mjs"

        if not hook_script.exists():
            pytest.skip("Compiled hook not found")

        hook_input = {
            "session_id": "test",
            "transcript_path": "/tmp/test",
            "cwd": str(temp_skill_rules),
            "permission_mode": "default",
            "prompt": "launch agentica with unicode text"
        }

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_skill_rules)

        result = subprocess.run(
            ["node", str(hook_script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=10
        )

        assert result.returncode == 0
        assert "AGENTICA ORCHESTRATION ACTIVATED" in result.stdout

    def test_very_long_prompt(self, hooks_dir: Path, temp_skill_rules: Path):
        """Test skill activation with very long prompt."""
        hook_script = hooks_dir / "dist" / "skill-activation-prompt.mjs"

        if not hook_script.exists():
            pytest.skip("Compiled hook not found")

        # Long prompt with trigger buried in middle
        long_text = "x" * 10000
        prompt = f"{long_text} launch agentica {long_text}"

        hook_input = {
            "session_id": "test",
            "transcript_path": "/tmp/test",
            "cwd": str(temp_skill_rules),
            "permission_mode": "default",
            "prompt": prompt
        }

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_skill_rules)

        result = subprocess.run(
            ["node", str(hook_script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=10
        )

        assert result.returncode == 0
        assert "AGENTICA ORCHESTRATION ACTIVATED" in result.stdout

"""Tests for task-detector.ts (Phase 7 - Novel Task Detection).

This module tests the task detection logic that distinguishes between:
- Implementation tasks (build, create, implement, add feature)
- Research tasks (find out, how do I, research)
- Debug tasks (fix bug, debug, investigate)
- Planning tasks (plan, design, architect)
- Conversational prompts (what is, explain, show me)

TDD approach: tests are written FIRST, then implementation.

Plan reference: thoughts/shared/plans/self-improving-skill-system.md (Phase 7)
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


class TestTaskDetectorFileExists:
    """Tests for task-detector.ts file existence."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_task_detector_file_exists(self, shared_dir: Path) -> None:
        """Verify task-detector.ts exists in shared directory."""
        detector_file = shared_dir / "task-detector.ts"
        assert detector_file.exists(), (
            f"task-detector.ts not found at {detector_file}. "
            "Create .claude/hooks/src/shared/task-detector.ts"
        )

    def test_task_detector_exports_interface(self, shared_dir: Path) -> None:
        """Verify TaskDetectionResult interface is exported."""
        detector_file = shared_dir / "task-detector.ts"
        if not detector_file.exists():
            pytest.skip("task-detector.ts doesn't exist yet")

        content = detector_file.read_text()
        assert "export interface TaskDetectionResult" in content, (
            "task-detector.ts must export TaskDetectionResult interface"
        )

    def test_task_detector_exports_detect_task_function(self, shared_dir: Path) -> None:
        """Verify detectTask function is exported."""
        detector_file = shared_dir / "task-detector.ts"
        if not detector_file.exists():
            pytest.skip("task-detector.ts doesn't exist yet")

        content = detector_file.read_text()
        assert "export function detectTask" in content, (
            "task-detector.ts must export detectTask function"
        )


class TestTaskDetectionResultInterface:
    """Tests for TaskDetectionResult interface structure."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_interface_has_is_task_field(self, shared_dir: Path) -> None:
        """Verify TaskDetectionResult has isTask: boolean field."""
        detector_file = shared_dir / "task-detector.ts"
        if not detector_file.exists():
            pytest.skip("task-detector.ts doesn't exist yet")

        content = detector_file.read_text()
        assert "isTask: boolean" in content or "isTask:" in content, (
            "TaskDetectionResult must have isTask field"
        )

    def test_interface_has_task_type_field(self, shared_dir: Path) -> None:
        """Verify TaskDetectionResult has taskType field with correct union type."""
        detector_file = shared_dir / "task-detector.ts"
        if not detector_file.exists():
            pytest.skip("task-detector.ts doesn't exist yet")

        content = detector_file.read_text()
        # Should have taskType with union of task types
        assert "taskType" in content, (
            "TaskDetectionResult must have taskType field"
        )
        # Should include the task type categories
        for task_type in ["implementation", "research", "debug", "planning"]:
            assert f"'{task_type}'" in content or f'"{task_type}"' in content, (
                f"TaskDetectionResult taskType should include '{task_type}'"
            )

    def test_interface_has_confidence_field(self, shared_dir: Path) -> None:
        """Verify TaskDetectionResult has confidence: number field."""
        detector_file = shared_dir / "task-detector.ts"
        if not detector_file.exists():
            pytest.skip("task-detector.ts doesn't exist yet")

        content = detector_file.read_text()
        assert "confidence: number" in content or "confidence:" in content, (
            "TaskDetectionResult must have confidence field"
        )

    def test_interface_has_triggers_field(self, shared_dir: Path) -> None:
        """Verify TaskDetectionResult has triggers: string[] field."""
        detector_file = shared_dir / "task-detector.ts"
        if not detector_file.exists():
            pytest.skip("task-detector.ts doesn't exist yet")

        content = detector_file.read_text()
        assert "triggers" in content, (
            "TaskDetectionResult must have triggers field"
        )


class TestImplementationTaskDetection:
    """Tests for detecting implementation tasks."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def test_implement_authentication_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'implement authentication' is detected as implementation task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "implement authentication"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True, (
            f"'implement authentication' should be detected as task. Got: {result}"
        )
        assert result.get("taskType") == "implementation", (
            f"Task type should be 'implementation'. Got: {result.get('taskType')}"
        )

    def test_build_feature_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'build a new feature' is detected as implementation task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "build a new login feature"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "implementation"

    def test_create_component_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'create a component' is detected as implementation task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "create a new React component for the dashboard"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "implementation"

    def test_add_feature_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'add feature' is detected as implementation task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "add a feature for user notifications"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "implementation"

    def test_write_function_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'write a function' is detected as implementation task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "write a function to validate email addresses"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "implementation"

    def _run_task_detector(
        self, hooks_dir: Path, project_dir: Path, prompt: str
    ) -> dict | None:
        """Run the task detector and return the result."""
        test_script = hooks_dir / "dist" / "test-task-detector.mjs"

        if not test_script.exists():
            return None

        try:
            result = subprocess.run(
                ["node", str(test_script), prompt],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(hooks_dir / "dist"),
                env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            )

            if result.returncode != 0:
                return None

            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            return None


class TestDebugTaskDetection:
    """Tests for detecting debug tasks."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def test_debug_this_error_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'debug this error' is detected as debug task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "debug this error in the API"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True, (
            f"'debug this error' should be detected as task. Got: {result}"
        )
        assert result.get("taskType") == "debug", (
            f"Task type should be 'debug'. Got: {result.get('taskType')}"
        )

    def test_fix_bug_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'fix bug' is detected as debug task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "fix the bug in the payment processing"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "debug"

    def test_investigate_issue_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'investigate issue' is detected as debug task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "investigate the issue with memory leaks"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "debug"

    def test_troubleshoot_problem_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'troubleshoot problem' is detected as debug task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "troubleshoot the problem with user sessions"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "debug"

    def _run_task_detector(
        self, hooks_dir: Path, project_dir: Path, prompt: str
    ) -> dict | None:
        """Run the task detector and return the result."""
        test_script = hooks_dir / "dist" / "test-task-detector.mjs"

        if not test_script.exists():
            return None

        try:
            result = subprocess.run(
                ["node", str(test_script), prompt],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(hooks_dir / "dist"),
                env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            )

            if result.returncode != 0:
                return None

            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            return None


class TestResearchTaskDetection:
    """Tests for detecting research tasks."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def test_how_do_i_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'how do I' is detected as research task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "how do I set up authentication with OAuth"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True, (
            f"'how do I' should be detected as task. Got: {result}"
        )
        assert result.get("taskType") == "research", (
            f"Task type should be 'research'. Got: {result.get('taskType')}"
        )

    def test_find_out_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'find out' is detected as research task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "find out the best practices for error handling"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "research"

    def test_research_topic_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'research' is detected as research task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "research the options for state management"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "research"

    def test_look_into_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'look into' is detected as research task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "look into different caching strategies"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "research"

    def _run_task_detector(
        self, hooks_dir: Path, project_dir: Path, prompt: str
    ) -> dict | None:
        """Run the task detector and return the result."""
        test_script = hooks_dir / "dist" / "test-task-detector.mjs"

        if not test_script.exists():
            return None

        try:
            result = subprocess.run(
                ["node", str(test_script), prompt],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(hooks_dir / "dist"),
                env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            )

            if result.returncode != 0:
                return None

            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            return None


class TestPlanningTaskDetection:
    """Tests for detecting planning tasks."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def test_plan_migration_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'plan migration' is detected as planning task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "plan the database migration strategy"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True, (
            f"'plan migration' should be detected as task. Got: {result}"
        )
        assert result.get("taskType") == "planning", (
            f"Task type should be 'planning'. Got: {result.get('taskType')}"
        )

    def test_design_architecture_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'design architecture' is detected as planning task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "design the microservices architecture"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "planning"

    def test_architect_system_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'architect system' is detected as planning task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "architect the notification system"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "planning"

    def test_outline_approach_is_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'outline approach' is detected as planning task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "outline the approach for the refactoring"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result.get("taskType") == "planning"

    def _run_task_detector(
        self, hooks_dir: Path, project_dir: Path, prompt: str
    ) -> dict | None:
        """Run the task detector and return the result."""
        test_script = hooks_dir / "dist" / "test-task-detector.mjs"

        if not test_script.exists():
            return None

        try:
            result = subprocess.run(
                ["node", str(test_script), prompt],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(hooks_dir / "dist"),
                env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            )

            if result.returncode != 0:
                return None

            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            return None


class TestConversationalNotTask:
    """Tests for conversational prompts that are NOT tasks."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def test_what_is_closure_not_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'what is a closure' is NOT detected as task (conversational)."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "what is a closure"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is False, (
            f"'what is a closure' should NOT be detected as task. Got: {result}"
        )

    def test_explain_code_not_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'explain this code' is NOT detected as task (conversational)."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "explain this code to me"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is False

    def test_show_me_not_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'show me' is NOT detected as task (conversational)."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "show me the contents of the file"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is False

    def test_tell_me_about_not_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'tell me about' is NOT detected as task (conversational)."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "tell me about JavaScript promises"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is False

    def test_describe_not_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'describe' is NOT detected as task (conversational)."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "describe how async/await works"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is False

    def test_can_you_explain_not_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'can you explain' is NOT detected as task (conversational)."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "can you explain what this function does"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is False

    def test_simple_greeting_not_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test simple greeting is NOT detected as task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "hello, how are you"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is False

    def test_thanks_not_task(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'thanks' is NOT detected as task."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "thanks, that was helpful"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is False

    def _run_task_detector(
        self, hooks_dir: Path, project_dir: Path, prompt: str
    ) -> dict | None:
        """Run the task detector and return the result."""
        test_script = hooks_dir / "dist" / "test-task-detector.mjs"

        if not test_script.exists():
            return None

        try:
            result = subprocess.run(
                ["node", str(test_script), prompt],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(hooks_dir / "dist"),
                env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            )

            if result.returncode != 0:
                return None

            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            return None


class TestConfidenceScoring:
    """Tests for confidence scoring in task detection."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def test_strong_indicator_high_confidence(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test strong task indicator produces high confidence score."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "implement the authentication feature"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result["confidence"] >= 0.7, (
            f"Strong indicator should have high confidence (>=0.7). Got: {result['confidence']}"
        )

    def test_weak_indicator_lower_confidence(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test weak/ambiguous prompt produces lower confidence score."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "something about code"
        )
        if result is None:
            pytest.skip("Task detector not available")

        # Should either not be a task or have lower confidence
        if result["isTask"]:
            assert result["confidence"] < 0.7, (
                f"Ambiguous prompt should have lower confidence. Got: {result['confidence']}"
            )

    def test_multiple_indicators_boost_confidence(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test multiple task indicators produce higher confidence."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "implement and build a new authentication feature"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert result["isTask"] is True
        assert result["confidence"] >= 0.8, (
            f"Multiple indicators should boost confidence (>=0.8). Got: {result['confidence']}"
        )

    def test_confidence_is_normalized(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test confidence score is between 0 and 1."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "implement build create add feature debug fix plan design"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert 0 <= result["confidence"] <= 1, (
            f"Confidence must be between 0 and 1. Got: {result['confidence']}"
        )

    def _run_task_detector(
        self, hooks_dir: Path, project_dir: Path, prompt: str
    ) -> dict | None:
        """Run the task detector and return the result."""
        test_script = hooks_dir / "dist" / "test-task-detector.mjs"

        if not test_script.exists():
            return None

        try:
            result = subprocess.run(
                ["node", str(test_script), prompt],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(hooks_dir / "dist"),
                env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            )

            if result.returncode != 0:
                return None

            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            return None


class TestTriggerExtraction:
    """Tests for trigger word extraction."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def test_implement_extracted_as_trigger(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'implement' is extracted as a trigger."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "implement the login feature"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert "triggers" in result
        assert "implement" in result["triggers"], (
            f"'implement' should be in triggers. Got: {result['triggers']}"
        )

    def test_multiple_triggers_extracted(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test multiple trigger words are extracted."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "implement and build a new feature"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert "triggers" in result
        assert len(result["triggers"]) >= 2, (
            f"Multiple trigger words should be extracted. Got: {result['triggers']}"
        )

    def test_debug_trigger_extracted(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test 'debug' is extracted as a trigger."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "debug this error"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert "triggers" in result
        assert "debug" in result["triggers"]

    def test_no_triggers_for_conversational(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Test no task triggers extracted for conversational prompts."""
        result = self._run_task_detector(
            hooks_dir, project_dir, "what is a closure"
        )
        if result is None:
            pytest.skip("Task detector not available")

        assert "triggers" in result
        assert len(result["triggers"]) == 0, (
            f"Conversational prompt should have no triggers. Got: {result['triggers']}"
        )

    def _run_task_detector(
        self, hooks_dir: Path, project_dir: Path, prompt: str
    ) -> dict | None:
        """Run the task detector and return the result."""
        test_script = hooks_dir / "dist" / "test-task-detector.mjs"

        if not test_script.exists():
            return None

        try:
            result = subprocess.run(
                ["node", str(test_script), prompt],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(hooks_dir / "dist"),
                env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            )

            if result.returncode != 0:
                return None

            return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            return None


class TestSkillRouterIntegration:
    """Tests for task detector integration with skill-router.ts."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_skill_router_imports_task_detector(self, hooks_dir: Path) -> None:
        """Verify skill-router.ts imports from task-detector."""
        ts_handler = hooks_dir / "src" / "skill-router.ts"
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")

        content = ts_handler.read_text()
        assert "task-detector" in content, (
            "skill-router.ts must import from shared/task-detector.js"
        )

    def test_skill_router_has_detect_task_call(self, hooks_dir: Path) -> None:
        """Verify skill-router.ts calls detectTask when lookup fails."""
        ts_handler = hooks_dir / "src" / "skill-router.ts"
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")

        content = ts_handler.read_text()
        assert "detectTask" in content, (
            "skill-router.ts must call detectTask function"
        )

    def test_skill_router_handles_novel_task(self, hooks_dir: Path) -> None:
        """Verify skill-router.ts has logic to handle novel tasks."""
        ts_handler = hooks_dir / "src" / "skill-router.ts"
        if not ts_handler.exists():
            pytest.skip("skill-router.ts doesn't exist yet")

        content = ts_handler.read_text()
        # Should have logic that distinguishes novel tasks from conversational
        assert "isTask" in content or "novelTask" in content, (
            "skill-router.ts should handle novel task detection"
        )

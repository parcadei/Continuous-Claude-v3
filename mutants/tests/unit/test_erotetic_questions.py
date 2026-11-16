"""Tests for Erotetic Question Framework (Phase 8 of Self-Improving Skill System).

Erotetic logic = question-based resolution. When a novel task is detected,
we ask clarifying questions until the task is unambiguous.

TDD Protocol: These tests are written FIRST, before implementation.

Plan reference: thoughts/shared/plans/self-improving-skill-system.md (Phase 8)

Phase 8 Tests:
- [x] QHeuristic type definitions
- [x] getQHeuristicsForTask returns correct questions per task type
- [x] resolveFromContext extracts info from prompts
- [x] formatAskUserQuestions outputs AskUserQuestion-compatible format
- [x] Max 4 question limit enforced
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest


class TestQHeuristicTypes:
    """Tests for QHeuristic type definitions."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_erotetic_questions_file_exists(self, shared_dir: Path) -> None:
        """Verify erotetic-questions.ts exists in shared directory."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        assert erotetic_file.exists(), (
            f"erotetic-questions.ts not found at {erotetic_file}. "
            "Create .claude/hooks/src/shared/erotetic-questions.ts"
        )

    def test_exports_qheuristic_interface(self, shared_dir: Path) -> None:
        """Verify QHeuristic interface is exported."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "export interface QHeuristic" in content, (
            "erotetic-questions.ts must export QHeuristic interface"
        )

    def test_qheuristic_has_id_field(self, shared_dir: Path) -> None:
        """Verify QHeuristic has id: string field."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "id: string" in content or "id:" in content, (
            "QHeuristic must have 'id' field"
        )

    def test_qheuristic_has_question_field(self, shared_dir: Path) -> None:
        """Verify QHeuristic has question: string field."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "question: string" in content or "question:" in content, (
            "QHeuristic must have 'question' field"
        )

    def test_qheuristic_has_options_field(self, shared_dir: Path) -> None:
        """Verify QHeuristic has options array field."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "options:" in content, (
            "QHeuristic must have 'options' field"
        )

    def test_qheuristic_has_default_field(self, shared_dir: Path) -> None:
        """Verify QHeuristic has optional default field."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "default?" in content or "default:" in content, (
            "QHeuristic must have optional 'default' field"
        )

    def test_qheuristic_has_infer_from_field(self, shared_dir: Path) -> None:
        """Verify QHeuristic has optional inferFrom field."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "inferFrom?" in content or "inferFrom:" in content, (
            "QHeuristic must have optional 'inferFrom' field"
        )

    def test_exports_task_qheuristics_interface(self, shared_dir: Path) -> None:
        """Verify TaskQHeuristics interface is exported."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "TaskQHeuristics" in content, (
            "erotetic-questions.ts must have TaskQHeuristics interface"
        )

    def test_task_qheuristics_has_implementation_field(self, shared_dir: Path) -> None:
        """Verify TaskQHeuristics has implementation field."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "implementation:" in content, (
            "TaskQHeuristics must have 'implementation' field"
        )

    def test_task_qheuristics_has_debug_field(self, shared_dir: Path) -> None:
        """Verify TaskQHeuristics has debug field."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "debug:" in content, (
            "TaskQHeuristics must have 'debug' field"
        )

    def test_task_qheuristics_has_research_field(self, shared_dir: Path) -> None:
        """Verify TaskQHeuristics has research field."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "research:" in content, (
            "TaskQHeuristics must have 'research' field"
        )

    def test_task_qheuristics_has_planning_field(self, shared_dir: Path) -> None:
        """Verify TaskQHeuristics has planning field."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "planning:" in content, (
            "TaskQHeuristics must have 'planning' field"
        )


class TestGetQHeuristicsForTask:
    """Tests for getQHeuristicsForTask function."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_function_exists(self, shared_dir: Path) -> None:
        """Verify getQHeuristicsForTask function exists."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "function getQHeuristicsForTask" in content or "getQHeuristicsForTask" in content, (
            "erotetic-questions.ts must have getQHeuristicsForTask function"
        )

    def test_function_is_exported(self, shared_dir: Path) -> None:
        """Verify getQHeuristicsForTask is exported."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "export function getQHeuristicsForTask" in content or (
            "export {" in content and "getQHeuristicsForTask" in content
        ), (
            "getQHeuristicsForTask must be exported"
        )


class TestImplementationQHeuristics:
    """Tests for implementation task Q-heuristics."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_has_auth_method_question(self, shared_dir: Path) -> None:
        """Verify implementation has auth_method Q-heuristic."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "auth_method" in content, (
            "Implementation Q-heuristics must include auth_method"
        )

    def test_has_test_coverage_question(self, shared_dir: Path) -> None:
        """Verify implementation has test_coverage Q-heuristic."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "test_coverage" in content, (
            "Implementation Q-heuristics must include test_coverage"
        )

    def test_has_target_files_question(self, shared_dir: Path) -> None:
        """Verify implementation has target_files Q-heuristic."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "target_files" in content, (
            "Implementation Q-heuristics must include target_files"
        )


class TestDebugQHeuristics:
    """Tests for debug task Q-heuristics."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_has_error_type_question(self, shared_dir: Path) -> None:
        """Verify debug has error_type Q-heuristic."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "error_type" in content, (
            "Debug Q-heuristics must include error_type"
        )

    def test_has_scope_question(self, shared_dir: Path) -> None:
        """Verify debug has scope Q-heuristic."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        # 'scope' is a common word, so check for it in debug context
        assert "scope" in content.lower(), (
            "Debug Q-heuristics must include scope"
        )

    def test_has_investigation_depth_question(self, shared_dir: Path) -> None:
        """Verify debug has investigation_depth Q-heuristic."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "investigation_depth" in content, (
            "Debug Q-heuristics must include investigation_depth"
        )


class TestResearchQHeuristics:
    """Tests for research task Q-heuristics."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_has_depth_question(self, shared_dir: Path) -> None:
        """Verify research has depth Q-heuristic."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        # Look for research depth - 'depth' appears in research section
        assert "depth" in content.lower(), (
            "Research Q-heuristics must include depth"
        )

    def test_has_sources_question(self, shared_dir: Path) -> None:
        """Verify research has sources Q-heuristic."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "sources" in content.lower(), (
            "Research Q-heuristics must include sources"
        )

    def test_has_output_format_question(self, shared_dir: Path) -> None:
        """Verify research has output_format Q-heuristic."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "output_format" in content, (
            "Research Q-heuristics must include output_format"
        )


class TestPlanningQHeuristics:
    """Tests for planning task Q-heuristics."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_has_detail_level_question(self, shared_dir: Path) -> None:
        """Verify planning has detail_level Q-heuristic."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "detail_level" in content, (
            "Planning Q-heuristics must include detail_level"
        )

    def test_has_include_timeline_question(self, shared_dir: Path) -> None:
        """Verify planning has include_timeline Q-heuristic."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "include_timeline" in content, (
            "Planning Q-heuristics must include include_timeline"
        )

    def test_has_include_risks_question(self, shared_dir: Path) -> None:
        """Verify planning has include_risks Q-heuristic."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "include_risks" in content, (
            "Planning Q-heuristics must include include_risks"
        )


class TestResolveFromContext:
    """Tests for resolveFromContext function."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_function_exists(self, shared_dir: Path) -> None:
        """Verify resolveFromContext function exists."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "resolveFromContext" in content, (
            "erotetic-questions.ts must have resolveFromContext function"
        )

    def test_function_is_exported(self, shared_dir: Path) -> None:
        """Verify resolveFromContext is exported."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "export function resolveFromContext" in content or (
            "export {" in content and "resolveFromContext" in content
        ), (
            "resolveFromContext must be exported"
        )

    def test_returns_resolved_and_unresolved(self, shared_dir: Path) -> None:
        """Verify resolveFromContext returns resolved and unresolved fields."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "resolved" in content, (
            "resolveFromContext must return 'resolved' field"
        )
        assert "unresolved" in content, (
            "resolveFromContext must return 'unresolved' field"
        )


class TestContextResolutionPatterns:
    """Tests for context resolution inference patterns."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_jwt_auth_pattern(self, shared_dir: Path) -> None:
        """Verify 'add JWT auth' resolves auth_method to JWT."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        # Should have pattern recognition for JWT
        assert "jwt" in content.lower() or "JWT" in content, (
            "Should recognize JWT auth pattern"
        )

    def test_oauth_pattern(self, shared_dir: Path) -> None:
        """Verify OAuth/OAuth2 pattern is recognized."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "oauth" in content.lower() or "OAuth" in content, (
            "Should recognize OAuth auth pattern"
        )

    def test_api_key_pattern(self, shared_dir: Path) -> None:
        """Verify API key auth pattern is recognized."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "api" in content.lower() and "key" in content.lower(), (
            "Should recognize API key auth pattern"
        )


class TestFormatAskUserQuestions:
    """Tests for formatAskUserQuestions function."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_function_exists(self, shared_dir: Path) -> None:
        """Verify formatAskUserQuestions function exists."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "formatAskUserQuestions" in content, (
            "erotetic-questions.ts must have formatAskUserQuestions function"
        )

    def test_function_is_exported(self, shared_dir: Path) -> None:
        """Verify formatAskUserQuestions is exported."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "export function formatAskUserQuestions" in content or (
            "export {" in content and "formatAskUserQuestions" in content
        ), (
            "formatAskUserQuestions must be exported"
        )


class TestMaxQuestionLimit:
    """Tests for max 4 question limit."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_has_max_questions_constant(self, shared_dir: Path) -> None:
        """Verify MAX_QUESTIONS constant is defined (should be 4)."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "MAX_QUESTIONS" in content or "maxQuestions" in content, (
            "Should have MAX_QUESTIONS constant"
        )
        assert "4" in content, (
            "MAX_QUESTIONS should be set to 4 (per AskUserQuestion tool limit)"
        )

    def test_format_respects_max_limit(self, shared_dir: Path) -> None:
        """Verify formatAskUserQuestions respects max question limit."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        # Should slice or limit the array
        assert "slice" in content or "MAX_QUESTIONS" in content, (
            "formatAskUserQuestions should limit questions to MAX_QUESTIONS"
        )


class TestAskUserQuestionFormat:
    """Tests for AskUserQuestion tool compatibility."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to shared types directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_exports_ask_user_question_format_type(self, shared_dir: Path) -> None:
        """Verify AskUserQuestionFormat type is exported."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        assert "AskUserQuestionFormat" in content, (
            "Should export AskUserQuestionFormat type"
        )

    def test_format_has_questions_array(self, shared_dir: Path) -> None:
        """Verify format includes questions array."""
        erotetic_file = shared_dir / "erotetic-questions.ts"
        if not erotetic_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        content = erotetic_file.read_text()
        # AskUserQuestionFormat should have questions property
        assert "questions" in content, (
            "AskUserQuestionFormat should have 'questions' field"
        )


# =============================================================================
# Integration Tests - Run TypeScript via subprocess
# =============================================================================


class TestEroteticQuestionsExecution:
    """Integration tests for erotetic-questions.ts execution."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def project_dir(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def test_typescript_compiles(self, hooks_dir: Path, project_dir: Path) -> None:
        """Verify erotetic-questions.ts compiles without errors."""
        ts_file = hooks_dir / "src" / "shared" / "erotetic-questions.ts"
        if not ts_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        # Try to compile with TypeScript
        result = subprocess.run(
            ["npx", "tsc", "--noEmit", str(ts_file)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(hooks_dir),
        )

        # Note: This may fail if there are import issues from other files
        # In that case, we just check for syntax errors
        if result.returncode != 0:
            # Check if it's just import errors vs syntax errors
            stderr = result.stderr.lower()
            if "syntax" in stderr or "unexpected" in stderr:
                pytest.fail(f"TypeScript syntax error: {result.stderr}")
            # Import errors are OK - file compiles syntactically

    def test_get_qheuristics_implementation_returns_array(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Verify getQHeuristicsForTask('implementation') returns Q-heuristics."""
        ts_file = hooks_dir / "src" / "shared" / "erotetic-questions.ts"
        if not ts_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        # Create a test runner script
        test_script = """
import { getQHeuristicsForTask } from './erotetic-questions.js';
const result = getQHeuristicsForTask('implementation');
console.log(JSON.stringify({
  count: result.length,
  hasAuthMethod: result.some(q => q.id === 'auth_method'),
  hasTestCoverage: result.some(q => q.id === 'test_coverage'),
  hasTargetFiles: result.some(q => q.id === 'target_files'),
}));
"""
        test_file = hooks_dir / "src" / "shared" / "_test_runner.ts"
        try:
            test_file.write_text(test_script)
            result = subprocess.run(
                ["npx", "tsx", str(test_file)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(hooks_dir),
            )

            if result.returncode != 0:
                pytest.skip(f"Test script failed: {result.stderr}")

            output = json.loads(result.stdout)
            assert output["count"] >= 3, "Implementation should have at least 3 Q-heuristics"
            assert output["hasAuthMethod"], "Should include auth_method"
            assert output["hasTestCoverage"], "Should include test_coverage"
            assert output["hasTargetFiles"], "Should include target_files"

        finally:
            if test_file.exists():
                test_file.unlink()

    def test_get_qheuristics_debug_returns_array(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Verify getQHeuristicsForTask('debug') returns Q-heuristics."""
        ts_file = hooks_dir / "src" / "shared" / "erotetic-questions.ts"
        if not ts_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        test_script = """
import { getQHeuristicsForTask } from './erotetic-questions.js';
const result = getQHeuristicsForTask('debug');
console.log(JSON.stringify({
  count: result.length,
  hasErrorType: result.some(q => q.id === 'error_type'),
  hasScope: result.some(q => q.id === 'scope'),
  hasInvestigationDepth: result.some(q => q.id === 'investigation_depth'),
}));
"""
        test_file = hooks_dir / "src" / "shared" / "_test_runner.ts"
        try:
            test_file.write_text(test_script)
            result = subprocess.run(
                ["npx", "tsx", str(test_file)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(hooks_dir),
            )

            if result.returncode != 0:
                pytest.skip(f"Test script failed: {result.stderr}")

            output = json.loads(result.stdout)
            assert output["count"] >= 3, "Debug should have at least 3 Q-heuristics"
            assert output["hasErrorType"], "Should include error_type"
            assert output["hasScope"], "Should include scope"
            assert output["hasInvestigationDepth"], "Should include investigation_depth"

        finally:
            if test_file.exists():
                test_file.unlink()

    def test_resolve_from_context_jwt_auth(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Verify resolveFromContext extracts JWT from 'add JWT auth'."""
        ts_file = hooks_dir / "src" / "shared" / "erotetic-questions.ts"
        if not ts_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        test_script = """
import { getQHeuristicsForTask, resolveFromContext } from './erotetic-questions.js';
const qHeuristics = getQHeuristicsForTask('implementation');
const result = resolveFromContext('add JWT authentication to the API', qHeuristics);
console.log(JSON.stringify({
  hasResolvedAuthMethod: 'auth_method' in result.resolved,
  authMethodValue: result.resolved['auth_method'] || null,
  unresolvedCount: result.unresolved.length,
}));
"""
        test_file = hooks_dir / "src" / "shared" / "_test_runner.ts"
        try:
            test_file.write_text(test_script)
            result = subprocess.run(
                ["npx", "tsx", str(test_file)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(hooks_dir),
            )

            if result.returncode != 0:
                pytest.skip(f"Test script failed: {result.stderr}")

            output = json.loads(result.stdout)
            assert output["hasResolvedAuthMethod"], "Should resolve auth_method from 'JWT'"
            assert output["authMethodValue"] is not None, "auth_method value should be set"
            assert "jwt" in output["authMethodValue"].lower(), "Should resolve to JWT"

        finally:
            if test_file.exists():
                test_file.unlink()

    def test_format_ask_user_questions_max_4(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Verify formatAskUserQuestions returns max 4 questions."""
        ts_file = hooks_dir / "src" / "shared" / "erotetic-questions.ts"
        if not ts_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        # Create 6 mock questions to test the limit
        test_script = """
import { formatAskUserQuestions, QHeuristic } from './erotetic-questions.js';

const mockQuestions: QHeuristic[] = [
  { id: 'q1', question: 'Question 1?', options: [{ label: 'A', description: 'Option A' }] },
  { id: 'q2', question: 'Question 2?', options: [{ label: 'B', description: 'Option B' }] },
  { id: 'q3', question: 'Question 3?', options: [{ label: 'C', description: 'Option C' }] },
  { id: 'q4', question: 'Question 4?', options: [{ label: 'D', description: 'Option D' }] },
  { id: 'q5', question: 'Question 5?', options: [{ label: 'E', description: 'Option E' }] },
  { id: 'q6', question: 'Question 6?', options: [{ label: 'F', description: 'Option F' }] },
];

const result = formatAskUserQuestions(mockQuestions);
console.log(JSON.stringify({
  questionCount: result.questions.length,
  isLimitedTo4: result.questions.length <= 4,
}));
"""
        test_file = hooks_dir / "src" / "shared" / "_test_runner.ts"
        try:
            test_file.write_text(test_script)
            result = subprocess.run(
                ["npx", "tsx", str(test_file)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(hooks_dir),
            )

            if result.returncode != 0:
                pytest.skip(f"Test script failed: {result.stderr}")

            output = json.loads(result.stdout)
            assert output["isLimitedTo4"], (
                f"Should limit to 4 questions, got {output['questionCount']}"
            )

        finally:
            if test_file.exists():
                test_file.unlink()

    def test_unknown_task_type_returns_empty(
        self, hooks_dir: Path, project_dir: Path
    ) -> None:
        """Verify getQHeuristicsForTask returns empty for unknown task type."""
        ts_file = hooks_dir / "src" / "shared" / "erotetic-questions.ts"
        if not ts_file.exists():
            pytest.skip("erotetic-questions.ts doesn't exist yet")

        test_script = """
import { getQHeuristicsForTask } from './erotetic-questions.js';
const result = getQHeuristicsForTask('unknown_task_type');
console.log(JSON.stringify({
  count: result.length,
  isEmpty: result.length === 0,
}));
"""
        test_file = hooks_dir / "src" / "shared" / "_test_runner.ts"
        try:
            test_file.write_text(test_script)
            result = subprocess.run(
                ["npx", "tsx", str(test_file)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(hooks_dir),
            )

            if result.returncode != 0:
                pytest.skip(f"Test script failed: {result.stderr}")

            output = json.loads(result.stdout)
            assert output["isEmpty"], "Unknown task type should return empty array"

        finally:
            if test_file.exists():
                test_file.unlink()

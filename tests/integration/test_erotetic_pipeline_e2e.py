"""
End-to-End Tests for Full Erotetic Pipeline.

Tests the complete integration between:
1. Hook: .claude/hooks/erotetic-clarification.sh - Detects implementation tasks
2. Extractor: scripts/extract_propositions.py - Converts NL to propositions
3. Checker: scripts/z3_erotetic.py - Determines unknowns via E(X,Q)

Pipeline flow:
    User prompt → Hook detects implementation task
                → Extractor extracts propositions (mocked Claude)
                → Z3 Checker identifies unknowns
                → Returns evocation result

TDD Approach: These tests define expected behavior for the full pipeline.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def project_root() -> Path:
    """Path to project root."""
    return Path(__file__).parents[2]


@pytest.fixture
def hooks_dir(project_root: Path) -> Path:
    """Path to hooks directory."""
    return project_root / ".claude" / "hooks"


# =============================================================================
# Test Full Pipeline Flow (Mocked Claude)
# =============================================================================


@pytest.mark.integration
class TestEroteticPipelineFullFlow:
    """End-to-end tests for the complete erotetic pipeline with mocked Claude."""

    @pytest.mark.asyncio
    async def test_full_flow_with_unknowns(self):
        """
        Full pipeline: Build prompt with unknowns.

        Flow:
        1. Hook detects 'Build an API' as implementation task
        2. Extractor produces propositions with UNKNOWN values
        3. Z3 Checker identifies unknowns
        4. Result shows E(X,Q) is not empty
        """
        from scripts.extract_propositions import extract_propositions
        from scripts.z3_erotetic import check_evocation

        # Step 1: Mock Claude to return propositions with unknowns
        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_api": True,
                    "auth_method": "UNKNOWN",  # Unknown - not specified
                    "database": "UNKNOWN",     # Unknown - not specified
                    "session_format": "JWT",   # Specified
                },
                "confidence": 0.75,
            }

            # Step 2: Extract propositions from user prompt
            extraction_result = await extract_propositions(
                "Build an API with JWT sessions"
            )

            # Step 3: Check evocation using Z3
            evocation_result = check_evocation(extraction_result["propositions"])

            # Verify full pipeline results
            assert evocation_result["isEmpty"] is False, \
                "E(X,Q) should NOT be empty when unknowns exist"
            assert evocation_result["count"] == 2, \
                f"Expected 2 unknowns, got {evocation_result['count']}"
            assert "auth_method" in evocation_result["unknowns"]
            assert "database" in evocation_result["unknowns"]

    @pytest.mark.asyncio
    async def test_full_flow_all_known(self):
        """
        Full pipeline: Specific prompt with all propositions known.

        Flow:
        1. Hook detects implementation task
        2. Extractor produces fully specified propositions
        3. Z3 Checker finds no unknowns
        4. Result shows E(X,Q) is empty (proceed to implementation)
        """
        from scripts.extract_propositions import extract_propositions
        from scripts.z3_erotetic import check_evocation

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_api": True,
                    "auth_method": "OAuth2",
                    "database": "PostgreSQL",
                    "session_format": "JWT",
                    "error_format": "JSON",
                },
                "confidence": 0.95,
            }

            extraction_result = await extract_propositions(
                "Build a REST API with OAuth2 auth, PostgreSQL database, "
                "JWT sessions, and JSON error responses"
            )

            evocation_result = check_evocation(extraction_result["propositions"])

            assert evocation_result["isEmpty"] is True, \
                "E(X,Q) should be empty when all propositions are known"
            assert evocation_result["count"] == 0
            assert evocation_result["unknowns"] == []

    @pytest.mark.asyncio
    async def test_full_flow_mixed_propositions(self):
        """
        Full pipeline: Some known, some unknown propositions.

        Tests the common case where user specifies some requirements
        but leaves others ambiguous.
        """
        from scripts.extract_propositions import extract_propositions
        from scripts.z3_erotetic import check_evocation

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_api": True,
                    "framework": "FastAPI",
                    "auth_method": "UNKNOWN",    # Not specified
                    "database": "PostgreSQL",
                    "rate_limiting": None,       # Not specified (None variant)
                    "logging_enabled": True,
                },
                "confidence": 0.80,
            }

            extraction_result = await extract_propositions(
                "Build a FastAPI service with PostgreSQL and logging"
            )

            evocation_result = check_evocation(extraction_result["propositions"])

            assert evocation_result["isEmpty"] is False
            assert evocation_result["count"] == 2
            assert "auth_method" in evocation_result["unknowns"]
            assert "rate_limiting" in evocation_result["unknowns"]
            assert "framework" not in evocation_result["unknowns"]
            assert "database" not in evocation_result["unknowns"]


# =============================================================================
# Test Hook to Extractor Chain
# =============================================================================


@pytest.mark.integration
class TestHookToExtractorChain:
    """Tests for hook output triggering extraction correctly."""

    def _run_hook(
        self, hooks_dir: Path, project_dir: Path, prompt: str
    ) -> dict[str, Any]:
        """Execute hook with given prompt and return parsed output."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"

        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("erotetic-clarification.sh is not executable")

        test_input = json.dumps({
            "prompt": prompt,
            "session_id": "test-session-pipeline-e2e"
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            cwd=str(hooks_dir),
        )

        if result.returncode != 0:
            pytest.fail(f"Hook execution failed: {result.stderr}")

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Hook output is not valid JSON: {e}. stdout: {result.stdout}")

    def test_hook_triggers_extraction_for_build_prompt(
        self, hooks_dir: Path, project_root: Path
    ):
        """Hook should trigger for 'Build' prompts, enabling extraction."""
        output = self._run_hook(hooks_dir, project_root, "Build an API for users")

        assert output["result"] == "continue"
        assert "message" in output
        assert "EROTETIC CLARIFICATION" in output["message"]
        # Message should reference z3_erotetic script for checking
        assert "z3_erotetic" in output["message"]

    def test_hook_message_contains_extraction_instructions(
        self, hooks_dir: Path, project_root: Path
    ):
        """Hook message should contain instructions for extraction workflow."""
        output = self._run_hook(
            hooks_dir, project_root, "Implement authentication system"
        )

        message = output.get("message", "")

        # Should mention the E(X,Q) notation
        assert "E(X,Q)" in message

        # Should mention script path
        assert "scripts/z3_erotetic" in message or "z3_erotetic.py" in message

    @pytest.mark.asyncio
    async def test_chain_hook_then_extraction_then_check(
        self, hooks_dir: Path, project_root: Path
    ):
        """
        Complete chain test:
        1. Hook detects implementation task
        2. Extraction produces propositions
        3. Z3 check determines unknowns
        """
        from scripts.extract_propositions import extract_propositions
        from scripts.z3_erotetic import check_evocation

        # Step 1: Hook detects implementation
        hook_output = self._run_hook(
            hooks_dir, project_root, "Build a payment processing module"
        )
        assert "EROTETIC CLARIFICATION" in hook_output.get("message", "")

        # Step 2: Extraction (with mocked Claude)
        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_payments": True,
                    "payment_provider": "UNKNOWN",  # Not specified
                    "currency_support": "UNKNOWN",  # Not specified
                },
                "confidence": 0.70,
            }

            extraction_result = await extract_propositions(
                "Build a payment processing module"
            )

        # Step 3: Z3 Check
        evocation_result = check_evocation(extraction_result["propositions"])

        # Verify chain result
        assert evocation_result["isEmpty"] is False
        assert evocation_result["count"] == 2
        assert "payment_provider" in evocation_result["unknowns"]
        assert "currency_support" in evocation_result["unknowns"]


# =============================================================================
# Test JSON Roundtrip Fidelity
# =============================================================================


@pytest.mark.integration
class TestJSONRoundtripFidelity:
    """Tests for JSON serialization/deserialization fidelity."""

    @pytest.mark.asyncio
    async def test_extraction_result_json_serializable(self):
        """Extraction result should be fully JSON serializable."""
        from scripts.extract_propositions import extract_propositions

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_api": True,
                    "auth_method": "UNKNOWN",
                    "features": ["auth", "logging"],
                },
                "confidence": 0.85,
            }

            result = await extract_propositions("Build an API")

            # Should serialize without error
            json_str = json.dumps(result)
            assert json_str is not None

            # Should deserialize back to equivalent structure
            parsed = json.loads(json_str)
            assert parsed["propositions"] == result["propositions"]
            assert parsed["source"] == result["source"]
            assert parsed["confidence"] == result["confidence"]

    def test_evocation_result_json_serializable(self):
        """Evocation result should be fully JSON serializable."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "prop1": True,
            "prop2": "UNKNOWN",
            "prop3": None,
        })

        # Should serialize without error
        json_str = json.dumps(result)
        assert json_str is not None

        # Should deserialize back to equivalent structure
        parsed = json.loads(json_str)
        assert parsed["isEmpty"] == result["isEmpty"]
        assert parsed["unknowns"] == result["unknowns"]
        assert parsed["count"] == result["count"]

    @pytest.mark.asyncio
    async def test_full_pipeline_json_roundtrip(self):
        """Full pipeline results should survive JSON roundtrip."""
        from scripts.extract_propositions import extract_propositions
        from scripts.z3_erotetic import check_evocation

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "has_api": True,
                    "auth_method": "UNKNOWN",
                },
                "confidence": 0.80,
            }

            extraction_result = await extract_propositions("Build an API")

            # Serialize extraction result
            extraction_json = json.dumps(extraction_result)
            extraction_parsed = json.loads(extraction_json)

            # Use parsed result for evocation check
            evocation_result = check_evocation(extraction_parsed["propositions"])

            # Serialize evocation result
            evocation_json = json.dumps(evocation_result)
            evocation_parsed = json.loads(evocation_json)

            # Verify final result
            assert evocation_parsed["isEmpty"] is False
            assert "auth_method" in evocation_parsed["unknowns"]


# =============================================================================
# Test Edge Cases
# =============================================================================


@pytest.mark.integration
class TestPipelineEdgeCases:
    """Edge case tests for the full pipeline."""

    def _run_hook(
        self, hooks_dir: Path, project_dir: Path, prompt: str
    ) -> dict[str, Any]:
        """Execute hook with given prompt and return parsed output."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"

        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("erotetic-clarification.sh is not executable")

        test_input = json.dumps({
            "prompt": prompt,
            "session_id": "test-session-edge-e2e"
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_dir)},
            cwd=str(hooks_dir),
        )

        if result.returncode != 0:
            pytest.fail(f"Hook execution failed: {result.stderr}")

        return json.loads(result.stdout)

    def test_non_implementation_prompt_skips_pipeline(
        self, hooks_dir: Path, project_root: Path
    ):
        """Non-implementation prompts should not trigger the pipeline."""
        output = self._run_hook(hooks_dir, project_root, "Fix the typo in README")

        assert output["result"] == "continue"
        # Should NOT have erotetic message
        assert "EROTETIC CLARIFICATION" not in output.get("message", "")

    def test_empty_propositions_yields_empty_evocation(self):
        """Empty propositions should yield isEmpty=True."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({})

        assert result["isEmpty"] is True
        assert result["count"] == 0
        assert result["unknowns"] == []

    @pytest.mark.asyncio
    async def test_all_unknown_propositions(self):
        """All UNKNOWN propositions should yield high count."""
        from scripts.extract_propositions import extract_propositions
        from scripts.z3_erotetic import check_evocation

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "auth_method": "UNKNOWN",
                    "database": None,
                    "framework": "UNKNOWN",
                    "deployment": None,
                },
                "confidence": 0.30,
            }

            result = await extract_propositions("Build something")
            evocation = check_evocation(result["propositions"])

            assert evocation["isEmpty"] is False
            assert evocation["count"] == 4
            assert len(evocation["unknowns"]) == 4

    @pytest.mark.asyncio
    async def test_mixed_none_and_unknown_string(self):
        """Both None and 'UNKNOWN' should be treated as unknown."""
        from scripts.z3_erotetic import check_evocation

        result = check_evocation({
            "prop1": "UNKNOWN",
            "prop2": None,
            "prop3": True,
            "prop4": "value",
        })

        assert result["count"] == 2
        assert "prop1" in result["unknowns"]
        assert "prop2" in result["unknowns"]
        assert "prop3" not in result["unknowns"]
        assert "prop4" not in result["unknowns"]


# =============================================================================
# Test Pipeline with Multiple Unknowns
# =============================================================================


@pytest.mark.integration
class TestPipelineMultipleUnknowns:
    """Tests for handling multiple unknowns in the pipeline."""

    @pytest.mark.asyncio
    async def test_count_matches_unknowns_list_length(self):
        """Evocation count should always match unknowns list length."""
        from scripts.extract_propositions import extract_propositions
        from scripts.z3_erotetic import check_evocation

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "prop1": "UNKNOWN",
                    "prop2": "UNKNOWN",
                    "prop3": "UNKNOWN",
                    "prop4": True,
                    "prop5": "value",
                },
                "confidence": 0.60,
            }

            result = await extract_propositions("Build something complex")
            evocation = check_evocation(result["propositions"])

            assert evocation["count"] == len(evocation["unknowns"])
            assert evocation["count"] == 3

    @pytest.mark.asyncio
    async def test_unknowns_list_contains_only_unknown_prop_names(self):
        """Unknowns list should contain only names of unknown propositions."""
        from scripts.extract_propositions import extract_propositions
        from scripts.z3_erotetic import check_evocation

        with patch("scripts.extract_propositions.call_claude") as mock_claude:
            mock_claude.return_value = {
                "propositions": {
                    "known1": True,
                    "unknown1": "UNKNOWN",
                    "known2": "value",
                    "unknown2": None,
                    "known3": False,
                },
                "confidence": 0.75,
            }

            result = await extract_propositions("Build a feature")
            evocation = check_evocation(result["propositions"])

            # Should only contain unknowns
            assert "unknown1" in evocation["unknowns"]
            assert "unknown2" in evocation["unknowns"]

            # Should NOT contain knowns
            assert "known1" not in evocation["unknowns"]
            assert "known2" not in evocation["unknowns"]
            assert "known3" not in evocation["unknowns"]


# =============================================================================
# Test Real Shell Wrapper Invocation
# =============================================================================


@pytest.mark.integration
class TestRealShellWrapperInvocation:
    """Tests for real shell wrapper invocation."""

    def test_shell_wrapper_produces_valid_json(
        self, hooks_dir: Path, project_root: Path
    ):
        """Shell wrapper should always produce valid JSON output."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"

        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("erotetic-clarification.sh is not executable")

        test_input = json.dumps({
            "prompt": "Build an API",
            "session_id": "test-wrapper-e2e"
        })

        result = subprocess.run(
            [str(shell_wrapper)],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_root)},
            cwd=str(hooks_dir),
        )

        assert result.returncode == 0

        # Output must be valid JSON
        try:
            output = json.loads(result.stdout)
            assert "result" in output
        except json.JSONDecodeError as e:
            pytest.fail(f"Shell wrapper output is not valid JSON: {e}")

    def test_shell_wrapper_handles_empty_input(
        self, hooks_dir: Path, project_root: Path
    ):
        """Shell wrapper should handle empty JSON input gracefully."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"

        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("erotetic-clarification.sh is not executable")

        result = subprocess.run(
            [str(shell_wrapper)],
            input="{}",
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_root)},
            cwd=str(hooks_dir),
        )

        # Should not crash
        assert result.returncode == 0

        # Should produce valid JSON
        try:
            output = json.loads(result.stdout)
            assert output.get("result") == "continue"
        except json.JSONDecodeError:
            pytest.fail("Shell wrapper must produce valid JSON for empty input")

    def test_shell_wrapper_handles_malformed_json(
        self, hooks_dir: Path, project_root: Path
    ):
        """Shell wrapper should handle malformed JSON input gracefully."""
        shell_wrapper = hooks_dir / "erotetic-clarification.sh"

        if not shell_wrapper.exists():
            pytest.skip("erotetic-clarification.sh doesn't exist yet")
        if not os.access(shell_wrapper, os.X_OK):
            pytest.skip("erotetic-clarification.sh is not executable")

        result = subprocess.run(
            [str(shell_wrapper)],
            input="{not valid json}",
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(project_root)},
            cwd=str(hooks_dir),
        )

        # Should not crash
        assert result.returncode == 0

        # Should produce valid JSON (graceful fallback)
        try:
            output = json.loads(result.stdout)
            assert output.get("result") == "continue"
        except json.JSONDecodeError:
            pytest.fail("Shell wrapper must produce valid JSON for malformed input")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])

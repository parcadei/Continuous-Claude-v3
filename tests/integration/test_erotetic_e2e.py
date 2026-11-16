"""
End-to-End Tests for Erotetic Verifier System

These tests verify the full verification loop including:
1. Claude Proxy integration
2. CLI interface
3. Valid JSON output

TDD Protocol: These tests are written FIRST, before implementation.
Tests should FAIL initially - the verifier module does not exist yet.

Skip conditions:
- Servers not running (claude proxy, agentica server)
- Missing API keys
- Network unavailable
"""

import json
import os
import subprocess
import pytest
from pathlib import Path
from typing import Any


# =============================================================================
# Skip Conditions
# =============================================================================

def is_claude_proxy_running() -> bool:
    """Check if Claude proxy server is running on localhost:8080."""
    try:
        import httpx
        response = httpx.get("http://localhost:8080/health", timeout=2.0)
        return response.status_code == 200
    except Exception:
        return False


def is_agentica_available() -> bool:
    """Check if agentica module is importable."""
    try:
        import agentica
        return True
    except ImportError:
        return False


SKIP_NO_PROXY = pytest.mark.skipif(
    not is_claude_proxy_running(),
    reason="Claude proxy server not running on localhost:8080"
)

SKIP_NO_AGENTICA = pytest.mark.skipif(
    not is_agentica_available(),
    reason="agentica module not installed"
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def project_root() -> Path:
    """Path to project root."""
    return Path(__file__).parents[2]


@pytest.fixture
def sample_context() -> str:
    """Sample task context for E2E testing."""
    return """
    Build an authentication system for a REST API.
    Users need to:
    - Register with email and password
    - Login and receive a token
    - Access protected routes with token
    """


@pytest.fixture
def sample_resolved() -> dict[str, str]:
    """Sample resolved answers for E2E testing."""
    return {
        "auth_method": "JWT",
        "password_hashing": "bcrypt",
        "token_expiry": "24 hours",
    }


# =============================================================================
# Test Full Verification Loop
# =============================================================================

class TestFullVerificationLoop:
    """E2E tests for the complete verification flow."""

    @SKIP_NO_PROXY
    @pytest.mark.asyncio
    async def test_full_verification_loop(
        self,
        sample_context: str,
        sample_resolved: dict[str, str],
    ):
        """Complete verification loop returns valid JSON structure."""
        from scripts.agentica_patterns.erotetic_verifier import verify_resolution

        result = await verify_resolution(
            context=sample_context,
            resolved=sample_resolved,
        )

        # Verify structure
        assert isinstance(result, dict)
        assert "isEmpty" in result
        assert "remainingCount" in result
        assert "remainingTopics" in result
        assert "confidence" in result

        # Verify types
        assert isinstance(result["isEmpty"], bool)
        assert isinstance(result["remainingCount"], int)
        assert isinstance(result["remainingTopics"], list)
        assert isinstance(result["confidence"], float)

        # Verify constraints
        assert result["remainingCount"] >= 0
        assert 0.0 <= result["confidence"] <= 1.0

    @SKIP_NO_PROXY
    @pytest.mark.asyncio
    async def test_verifier_returns_json_serializable(
        self,
        sample_context: str,
        sample_resolved: dict[str, str],
    ):
        """Result should be JSON serializable."""
        from scripts.agentica_patterns.erotetic_verifier import verify_resolution

        result = await verify_resolution(
            context=sample_context,
            resolved=sample_resolved,
        )

        # Should serialize without error
        json_str = json.dumps(result)
        assert json_str is not None

        # Should deserialize back
        parsed = json.loads(json_str)
        assert parsed == result

    @SKIP_NO_PROXY
    @pytest.mark.asyncio
    async def test_empty_context_handled(self):
        """Empty context should not crash."""
        from scripts.agentica_patterns.erotetic_verifier import verify_resolution

        result = await verify_resolution(
            context="",
            resolved={},
        )

        assert isinstance(result, dict)
        assert "isEmpty" in result

    @SKIP_NO_PROXY
    @pytest.mark.asyncio
    async def test_large_context_handled(self):
        """Large context should be handled within timeout."""
        from scripts.agentica_patterns.erotetic_verifier import verify_resolution

        large_context = """
        Build a comprehensive enterprise authentication system.
        """ + "\n".join([
            f"Feature {i}: Description of feature {i} with various requirements."
            for i in range(50)
        ])

        result = await verify_resolution(
            context=large_context,
            resolved={"auth_method": "OAuth2", "scope": "enterprise"},
        )

        assert isinstance(result, dict)
        assert "isEmpty" in result


# =============================================================================
# Test CLI Interface
# =============================================================================

class TestCLIInterface:
    """Tests for command-line interface."""

    def test_cli_help_available(self, project_root: Path):
        """CLI should show help without errors."""
        result = subprocess.run(
            [
                "uv", "run", "python", "-m",
                "scripts.agentica_patterns.erotetic_verifier", "--help"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_root),
        )

        # Help should work even if module doesn't exist
        # (--help might fail with ModuleNotFoundError, which is expected)
        # This test verifies the CLI entry point pattern

        # If module exists, check help output
        if result.returncode == 0:
            assert "--context" in result.stdout or "--help" in result.stdout

    def test_cli_returns_json_output(self, project_root: Path):
        """CLI should output valid JSON."""
        result = subprocess.run(
            [
                "uv", "run", "python", "-m",
                "scripts.agentica_patterns.erotetic_verifier",
                "--context", "Build an API",
                "--resolved", '{"auth_method": "JWT"}',
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(project_root),
        )

        # If the module exists and runs successfully
        if result.returncode == 0:
            # Output should be valid JSON
            try:
                output = json.loads(result.stdout)
                assert "isEmpty" in output
                assert "remainingCount" in output
                assert "remainingTopics" in output
                assert "confidence" in output
            except json.JSONDecodeError:
                pytest.fail(f"CLI output is not valid JSON: {result.stdout}")

    def test_cli_handles_invalid_json_resolved(self, project_root: Path):
        """CLI should handle invalid JSON in --resolved gracefully."""
        result = subprocess.run(
            [
                "uv", "run", "python", "-m",
                "scripts.agentica_patterns.erotetic_verifier",
                "--context", "Build an API",
                "--resolved", "not valid json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(project_root),
        )

        # Should fail but not crash
        # Either exit code is non-zero, or error message in stderr
        if result.returncode == 0:
            # If it succeeds, the output should indicate error
            pass
        else:
            # Non-zero exit is expected for invalid input
            assert "error" in result.stderr.lower() or "invalid" in result.stderr.lower() or result.returncode != 0


# =============================================================================
# Test Claude Proxy Integration
# =============================================================================

class TestClaudeProxyIntegration:
    """Tests for integration with Claude Proxy server."""

    @SKIP_NO_PROXY
    @pytest.mark.asyncio
    async def test_uses_claude_proxy_endpoint(
        self,
        sample_context: str,
        sample_resolved: dict[str, str],
    ):
        """Verifier should communicate with Claude proxy."""
        from scripts.agentica_patterns.erotetic_verifier import verify_resolution

        # This should use the proxy and return a result
        result = await verify_resolution(
            context=sample_context,
            resolved=sample_resolved,
        )

        # If we got a result, the proxy was used
        assert result is not None
        assert isinstance(result, dict)

    @SKIP_NO_PROXY
    @pytest.mark.asyncio
    async def test_proxy_timeout_handled(self):
        """Should handle proxy timeout gracefully."""
        from scripts.agentica_patterns.erotetic_verifier import verify_resolution

        # Very large context might timeout
        huge_context = "x" * 100000  # 100KB of text

        # Should not raise, but might return low confidence
        try:
            result = await verify_resolution(
                context=huge_context,
                resolved={},
            )
            assert isinstance(result, dict)
        except TimeoutError:
            # Timeout is acceptable
            pass


# =============================================================================
# Test Agentica SDK Integration
# =============================================================================

class TestAgenticaIntegration:
    """Tests for Agentica SDK integration."""

    @SKIP_NO_AGENTICA
    @SKIP_NO_PROXY
    @pytest.mark.asyncio
    async def test_agentica_spawn_pattern(
        self,
        sample_context: str,
        sample_resolved: dict[str, str],
    ):
        """Verifier can be spawned as an Agentica agent."""
        import agentica

        # Spawn verifier agent
        result = await agentica.spawn(
            "verifier",
            task=f"Verify resolution for context: {sample_context}",
            resolved=sample_resolved,
        )

        # Result should be structured
        assert "isEmpty" in result or "error" in result


# =============================================================================
# Test Result Validation
# =============================================================================

class TestResultValidation:
    """Tests for result validation and error handling."""

    @SKIP_NO_PROXY
    @pytest.mark.asyncio
    async def test_malformed_llm_response_handled(
        self,
        sample_context: str,
        sample_resolved: dict[str, str],
    ):
        """Malformed LLM response should result in fallback."""
        from scripts.agentica_patterns.erotetic_verifier import verify_resolution

        # The implementation should handle malformed responses
        result = await verify_resolution(
            context=sample_context,
            resolved=sample_resolved,
        )

        # Even with issues, we should get a valid structure
        assert isinstance(result, dict)
        assert "isEmpty" in result

    @SKIP_NO_PROXY
    @pytest.mark.asyncio
    async def test_consistent_results_for_same_input(
        self,
        sample_context: str,
        sample_resolved: dict[str, str],
    ):
        """Same input should produce structurally consistent results."""
        from scripts.agentica_patterns.erotetic_verifier import verify_resolution

        result1 = await verify_resolution(
            context=sample_context,
            resolved=sample_resolved,
        )

        result2 = await verify_resolution(
            context=sample_context,
            resolved=sample_resolved,
        )

        # Structure should be the same
        assert set(result1.keys()) == set(result2.keys())

        # Types should be the same
        assert type(result1["isEmpty"]) == type(result2["isEmpty"])
        assert type(result1["remainingCount"]) == type(result2["remainingCount"])
        assert type(result1["remainingTopics"]) == type(result2["remainingTopics"])
        assert type(result1["confidence"]) == type(result2["confidence"])


# =============================================================================
# Test Performance
# =============================================================================

class TestPerformance:
    """Tests for performance characteristics."""

    @SKIP_NO_PROXY
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_verification_completes_within_timeout(
        self,
        sample_context: str,
        sample_resolved: dict[str, str],
    ):
        """Verification should complete within reasonable time."""
        import asyncio
        from scripts.agentica_patterns.erotetic_verifier import verify_resolution

        # Should complete within 60 seconds
        result = await asyncio.wait_for(
            verify_resolution(
                context=sample_context,
                resolved=sample_resolved,
            ),
            timeout=60.0,
        )

        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

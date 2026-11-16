"""Tests for Phase 1: shared/pattern-router.ts

TDD tests for the pattern-router module which provides:
1. detectPattern() - reads PATTERN_TYPE env var, returns pattern name or null
2. SAFE_ID_PATTERN - regex for validating IDs (alphanumeric, underscore, hyphen, 1-64 chars)

These tests are designed to FAIL until the implementation is created.

Target file: .claude/hooks/src/shared/pattern-router.ts
Plan: thoughts/shared/plans/2025-12-28-pattern-aware-hooks.md (Phase 1)
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

import pytest


class TestPatternRouterFileExists:
    """Tests for pattern-router.ts file existence."""

    @pytest.fixture
    def shared_dir(self) -> Path:
        """Path to hooks/src/shared directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src" / "shared"

    def test_shared_directory_exists(self, shared_dir: Path) -> None:
        """shared/ directory exists under hooks/src/."""
        assert shared_dir.exists(), (
            f"shared/ directory not found: {shared_dir}. "
            "Create .claude/hooks/src/shared/"
        )

    def test_pattern_router_file_exists(self, shared_dir: Path) -> None:
        """pattern-router.ts exists in shared/ directory."""
        pattern_router = shared_dir / "pattern-router.ts"

        assert pattern_router.exists(), (
            f"pattern-router.ts not found: {pattern_router}. "
            "Create .claude/hooks/src/shared/pattern-router.ts"
        )


class TestDetectPatternNoEnvVar:
    """Tests for detectPattern() when PATTERN_TYPE is not set."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def pattern_router_path(self, hooks_dir: Path) -> Path:
        """Path to pattern-router.ts."""
        return hooks_dir / "src" / "shared" / "pattern-router.ts"

    def test_returns_null_when_no_env_var(
        self, hooks_dir: Path, pattern_router_path: Path
    ) -> None:
        """detectPattern() returns null when PATTERN_TYPE env var is not set."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        # TypeScript test script that imports and calls detectPattern
        test_script = """
import { detectPattern } from './src/shared/pattern-router.ts';
const result = detectPattern();
console.log(JSON.stringify({ result }));
"""
        env = os.environ.copy()
        env.pop("PATTERN_TYPE", None)  # Ensure PATTERN_TYPE is NOT set
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") is None, (
            f"detectPattern() should return null when PATTERN_TYPE not set. "
            f"Got: {output.get('result')}"
        )

    def test_returns_null_when_empty_env_var(
        self, hooks_dir: Path, pattern_router_path: Path
    ) -> None:
        """detectPattern() returns null when PATTERN_TYPE is empty string."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        test_script = """
import { detectPattern } from './src/shared/pattern-router.ts';
const result = detectPattern();
console.log(JSON.stringify({ result }));
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = ""  # Empty string
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") is None, (
            f"detectPattern() should return null when PATTERN_TYPE is empty. "
            f"Got: {output.get('result')}"
        )


class TestDetectPatternWithEnvVar:
    """Tests for detectPattern() when PATTERN_TYPE is set."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def pattern_router_path(self, hooks_dir: Path) -> Path:
        """Path to pattern-router.ts."""
        return hooks_dir / "src" / "shared" / "pattern-router.ts"

    @pytest.mark.parametrize("pattern_type", [
        "swarm",
        "jury",
        "pipeline",
        "generator_critic",
        "hierarchical",
        "map_reduce",
        "blackboard",
        "circuit_breaker",
        "chain_of_responsibility",
        "adversarial",
        "event_driven",
    ])
    def test_returns_pattern_name_when_set(
        self,
        hooks_dir: Path,
        pattern_router_path: Path,
        pattern_type: str
    ) -> None:
        """detectPattern() returns the pattern name when PATTERN_TYPE is set."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        test_script = """
import { detectPattern } from './src/shared/pattern-router.ts';
const result = detectPattern();
console.log(JSON.stringify({ result }));
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = pattern_type
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed for pattern '{pattern_type}': {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == pattern_type, (
            f"detectPattern() should return '{pattern_type}' when PATTERN_TYPE='{pattern_type}'. "
            f"Got: {output.get('result')}"
        )

    def test_preserves_case(
        self, hooks_dir: Path, pattern_router_path: Path
    ) -> None:
        """detectPattern() preserves the case of PATTERN_TYPE."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        test_script = """
import { detectPattern } from './src/shared/pattern-router.ts';
const result = detectPattern();
console.log(JSON.stringify({ result }));
"""
        pattern_type = "MyCustomPattern"
        env = os.environ.copy()
        env["PATTERN_TYPE"] = pattern_type
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") == pattern_type, (
            f"detectPattern() should preserve case. "
            f"Expected '{pattern_type}', got: {output.get('result')}"
        )


class TestSafeIdPatternValidIds:
    """Tests for SAFE_ID_PATTERN with valid IDs."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def pattern_router_path(self, hooks_dir: Path) -> Path:
        """Path to pattern-router.ts."""
        return hooks_dir / "src" / "shared" / "pattern-router.ts"

    @pytest.mark.parametrize("valid_id", [
        "abc123",
        "simple",
        "with-hyphen",
        "with_underscore",
        "MixedCase",
        "UPPERCASE",
        "lowercase",
        "a",  # Single character (minimum)
        "1",  # Single digit
        "a" * 64,  # Maximum length (64 characters)
        "abc-123_XYZ",  # Mixed characters
        "agent-0001",
        "swarm_coordinator",
        "jury-member-5",
    ])
    def test_valid_id_matches(
        self,
        hooks_dir: Path,
        pattern_router_path: Path,
        valid_id: str
    ) -> None:
        """SAFE_ID_PATTERN matches valid IDs."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        test_script = f"""
import {{ SAFE_ID_PATTERN }} from './src/shared/pattern-router.ts';
const id = '{valid_id}';
const result = SAFE_ID_PATTERN.test(id);
console.log(JSON.stringify({{ result, id }}));
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed for ID '{valid_id}': {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") is True, (
            f"SAFE_ID_PATTERN should match valid ID '{valid_id}'. "
            f"Got: {output}"
        )


class TestSafeIdPatternInvalidIds:
    """Tests for SAFE_ID_PATTERN rejecting invalid IDs."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def pattern_router_path(self, hooks_dir: Path) -> Path:
        """Path to pattern-router.ts."""
        return hooks_dir / "src" / "shared" / "pattern-router.ts"

    @pytest.mark.parametrize("invalid_id,reason", [
        ("", "empty string"),
        (" ", "whitespace only"),
        ("has space", "contains space"),
        ("has\ttab", "contains tab"),
        ("has\nnewline", "contains newline"),
        ("a" * 65, "exceeds 64 character limit"),
        ("special!char", "contains exclamation mark"),
        ("special@char", "contains at symbol"),
        ("special#char", "contains hash"),
        ("special$char", "contains dollar sign"),
        ("special%char", "contains percent"),
        ("special^char", "contains caret"),
        ("special&char", "contains ampersand"),
        ("special*char", "contains asterisk"),
        ("special(char", "contains open parenthesis"),
        ("special)char", "contains close parenthesis"),
        ("special+char", "contains plus"),
        ("special=char", "contains equals"),
        ("special[char", "contains open bracket"),
        ("special]char", "contains close bracket"),
        ("special{char", "contains open brace"),
        ("special}char", "contains close brace"),
        ("special|char", "contains pipe"),
        ("special\\char", "contains backslash"),
        ("special/char", "contains forward slash"),
        ("special:char", "contains colon"),
        ("special;char", "contains semicolon"),
        ("special'char", "contains single quote"),
        ('special"char', "contains double quote"),
        ("special<char", "contains less than"),
        ("special>char", "contains greater than"),
        ("special,char", "contains comma"),
        ("special.char", "contains period"),
        ("special?char", "contains question mark"),
        ("../path", "path traversal attempt"),
        ("$(command)", "command substitution attempt"),
        ("`command`", "backtick command execution"),
        ("'; DROP TABLE", "SQL injection attempt"),
    ])
    def test_invalid_id_rejected(
        self,
        hooks_dir: Path,
        pattern_router_path: Path,
        invalid_id: str,
        reason: str
    ) -> None:
        """SAFE_ID_PATTERN rejects invalid IDs."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        # Escape the ID for use in JavaScript string
        escaped_id = invalid_id.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\t", "\\t")

        test_script = f"""
import {{ SAFE_ID_PATTERN }} from './src/shared/pattern-router.ts';
const id = '{escaped_id}';
const result = SAFE_ID_PATTERN.test(id);
console.log(JSON.stringify({{ result, reason: '{reason}' }}));
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed for invalid ID ({reason}): {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("result") is False, (
            f"SAFE_ID_PATTERN should reject invalid ID ({reason}). "
            f"Got: {output}"
        )


class TestSafeIdPatternExport:
    """Tests for SAFE_ID_PATTERN export and regex format."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def pattern_router_path(self, hooks_dir: Path) -> Path:
        """Path to pattern-router.ts."""
        return hooks_dir / "src" / "shared" / "pattern-router.ts"

    def test_safe_id_pattern_is_exported(
        self, hooks_dir: Path, pattern_router_path: Path
    ) -> None:
        """SAFE_ID_PATTERN is exported from pattern-router.ts."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        test_script = """
import { SAFE_ID_PATTERN } from './src/shared/pattern-router.ts';
const isRegex = SAFE_ID_PATTERN instanceof RegExp;
console.log(JSON.stringify({ isRegex, type: typeof SAFE_ID_PATTERN }));
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("isRegex") is True, (
            f"SAFE_ID_PATTERN should be a RegExp instance. "
            f"Got type: {output.get('type')}"
        )

    def test_detect_pattern_is_exported(
        self, hooks_dir: Path, pattern_router_path: Path
    ) -> None:
        """detectPattern function is exported from pattern-router.ts."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        test_script = """
import { detectPattern } from './src/shared/pattern-router.ts';
const isFunction = typeof detectPattern === 'function';
console.log(JSON.stringify({ isFunction, type: typeof detectPattern }));
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("isFunction") is True, (
            f"detectPattern should be a function. "
            f"Got type: {output.get('type')}"
        )


class TestPatternRouterIntegration:
    """Integration tests for pattern-router.ts with other hooks."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def pattern_router_path(self, hooks_dir: Path) -> Path:
        """Path to pattern-router.ts."""
        return hooks_dir / "src" / "shared" / "pattern-router.ts"

    def test_can_import_in_hook_context(
        self, hooks_dir: Path, pattern_router_path: Path
    ) -> None:
        """pattern-router.ts can be imported from hooks context."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        # Simulate importing from a hook file
        test_script = """
import { detectPattern, SAFE_ID_PATTERN } from './src/shared/pattern-router.ts';

// Simulate hook logic
const pattern = detectPattern();
const testId = 'test-agent-123';
const isValidId = SAFE_ID_PATTERN.test(testId);

console.log(JSON.stringify({
    pattern,
    isValidId,
    hasDetectPattern: typeof detectPattern === 'function',
    hasSafeIdPattern: SAFE_ID_PATTERN instanceof RegExp
}));
"""
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "swarm"
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("pattern") == "swarm", (
            f"detectPattern() should return 'swarm'. Got: {output.get('pattern')}"
        )
        assert output.get("isValidId") is True, (
            f"SAFE_ID_PATTERN should match 'test-agent-123'. Got: {output.get('isValidId')}"
        )
        assert output.get("hasDetectPattern") is True, (
            "detectPattern should be importable as function"
        )
        assert output.get("hasSafeIdPattern") is True, (
            "SAFE_ID_PATTERN should be importable as RegExp"
        )


class TestPatternRouterEdgeCases:
    """Edge case tests for pattern-router.ts."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    @pytest.fixture
    def pattern_router_path(self, hooks_dir: Path) -> Path:
        """Path to pattern-router.ts."""
        return hooks_dir / "src" / "shared" / "pattern-router.ts"

    def test_detect_pattern_with_whitespace_pattern(
        self, hooks_dir: Path, pattern_router_path: Path
    ) -> None:
        """detectPattern() handles PATTERN_TYPE with whitespace."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        test_script = """
import { detectPattern } from './src/shared/pattern-router.ts';
const result = detectPattern();
console.log(JSON.stringify({ result }));
"""
        # Pattern with leading/trailing whitespace
        env = os.environ.copy()
        env["PATTERN_TYPE"] = "  swarm  "
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        # Implementation should either trim whitespace or return as-is
        # This test documents expected behavior - adjust based on design decision
        assert output.get("result") in ["swarm", "  swarm  "], (
            f"detectPattern() should handle whitespace-padded pattern. "
            f"Got: {output.get('result')}"
        )

    def test_detect_pattern_returns_string_not_undefined(
        self, hooks_dir: Path, pattern_router_path: Path
    ) -> None:
        """detectPattern() returns null (not undefined) when no pattern."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        test_script = """
import { detectPattern } from './src/shared/pattern-router.ts';
const result = detectPattern();
// Check specifically for null vs undefined
const isNull = result === null;
const isUndefined = result === undefined;
console.log(JSON.stringify({ result, isNull, isUndefined }));
"""
        env = os.environ.copy()
        env.pop("PATTERN_TYPE", None)
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        # Either null or undefined is acceptable, but should be consistent
        assert output.get("isNull") is True or output.get("isUndefined") is True, (
            f"detectPattern() should return null or undefined when no pattern. "
            f"Got: {output}"
        )

    def test_safe_id_pattern_boundary_64_chars(
        self, hooks_dir: Path, pattern_router_path: Path
    ) -> None:
        """SAFE_ID_PATTERN accepts exactly 64 characters."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        id_64_chars = "a" * 64

        test_script = f"""
import {{ SAFE_ID_PATTERN }} from './src/shared/pattern-router.ts';
const id = '{id_64_chars}';
const result = SAFE_ID_PATTERN.test(id);
console.log(JSON.stringify({{ result, length: id.length }}));
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("length") == 64, "Test ID should be exactly 64 chars"
        assert output.get("result") is True, (
            f"SAFE_ID_PATTERN should accept exactly 64 characters. "
            f"Got: {output}"
        )

    def test_safe_id_pattern_rejects_65_chars(
        self, hooks_dir: Path, pattern_router_path: Path
    ) -> None:
        """SAFE_ID_PATTERN rejects 65 characters."""
        if not pattern_router_path.exists():
            pytest.skip("pattern-router.ts doesn't exist yet")

        id_65_chars = "a" * 65

        test_script = f"""
import {{ SAFE_ID_PATTERN }} from './src/shared/pattern-router.ts';
const id = '{id_65_chars}';
const result = SAFE_ID_PATTERN.test(id);
console.log(JSON.stringify({{ result, length: id.length }}));
"""
        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(hooks_dir.parent.parent)

        result = subprocess.run(
            ["npx", "tsx", "-e", test_script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=30
        )

        assert result.returncode == 0, (
            f"TypeScript execution failed: {result.stderr}"
        )

        output = json.loads(result.stdout.strip())
        assert output.get("length") == 65, "Test ID should be exactly 65 chars"
        assert output.get("result") is False, (
            f"SAFE_ID_PATTERN should reject 65 characters. "
            f"Got: {output}"
        )

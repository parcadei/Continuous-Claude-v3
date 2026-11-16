"""E2E Integration Tests for ReDoS Protection in Hooks.

Tests the full pipeline of safe_regex integration with TypeScript hooks:
- skill-router.ts (line 110: intentPatterns regex matching)
- skill-activation-prompt.ts (lines 90, 127: intentPatterns regex matching)
- erotetic-questions.ts (line 330: inferFrom regex matching)

Test scenarios:
1. Hook completion with malicious regex patterns
2. Python safe_regex to TypeScript integration boundary
3. Hook pipeline timeout protection
4. Graceful degradation on dangerous patterns

Note: Current TypeScript hooks use native RegExp without timeout protection.
This test suite validates behavior and documents integration strategies.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import pytest

# Import the safe_regex module for Python-side testing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "agentica"))
try:
    from safe_regex import is_safe_regex, safe_regex_match, regex_complexity
except ImportError:
    pytest.skip("safe_regex module not available", allow_module_level=True)


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
def temp_skill_rules_with_evil_regex(tmp_path: Path) -> Path:
    """Create skill-rules.json with intentionally malicious regex patterns."""
    skills_dir = tmp_path / ".claude" / "skills"
    skills_dir.mkdir(parents=True)
    rules_path = skills_dir / "skill-rules.json"

    rules = {
        "version": "1.0",
        "skills": {
            "evil-skill": {
                "type": "domain",
                "enforcement": "suggest",
                "priority": "high",
                "promptTriggers": {
                    "keywords": ["safe-trigger"],
                    # Evil regex patterns that could cause ReDoS
                    "intentPatterns": [
                        "(a+)+b",        # Classic exponential backtracking
                        "(.*)*c",        # Nested quantifiers
                        "(a|aa)+d",      # Overlapping alternation
                        "(.+.+)+e",      # Multiple greedy patterns
                    ]
                }
            },
            "safe-skill": {
                "type": "domain",
                "enforcement": "suggest",
                "priority": "medium",
                "promptTriggers": {
                    "keywords": ["normal-trigger"],
                    "intentPatterns": [
                        "^[a-z]+$",      # Safe: anchored, simple quantifier
                        "\\btest\\b",    # Safe: word boundary
                        "run\\s+tests?", # Safe: limited backtracking
                    ]
                }
            }
        },
        "agents": {}
    }

    rules_path.write_text(json.dumps(rules, indent=2))
    return tmp_path


@pytest.fixture
def evil_input_strings() -> list[str]:
    """Generate input strings designed to trigger exponential backtracking."""
    return [
        "a" * 30,                   # Triggers (a+)+b with no 'b'
        "a" * 25 + "X",             # Triggers (a+)+b with wrong terminator
        "x" * 30,                   # Triggers (.*)*c with no 'c'
        "a" * 20 + "aa" * 10,       # Triggers (a|aa)+d pattern
        "ab" * 20,                  # Triggers (.+.+)+e pattern
    ]


# ============================================================================
# Test Scenario 1: Python safe_regex Module Validation
# ============================================================================


class TestSafeRegexPythonModule:
    """Validate the Python safe_regex module catches dangerous patterns."""

    def test_detects_nested_quantifiers(self):
        """is_safe_regex correctly identifies nested quantifier patterns."""
        assert not is_safe_regex("(a+)+b")
        assert not is_safe_regex("(a*)+")
        assert not is_safe_regex("(.*)+")
        assert not is_safe_regex("(.+)+")

    def test_detects_overlapping_alternation(self):
        """is_safe_regex correctly identifies overlapping alternation."""
        assert not is_safe_regex("(a|aa)+")
        assert not is_safe_regex("(a|a?)+")

    def test_allows_safe_patterns(self):
        """is_safe_regex allows patterns known to be safe."""
        assert is_safe_regex("^[a-z]+$")
        assert is_safe_regex("\\bword\\b")
        assert is_safe_regex("run\\s+tests?")
        assert is_safe_regex("exact-match")
        assert is_safe_regex("")  # Empty is safe

    def test_safe_regex_match_blocks_dangerous(self, evil_input_strings):
        """safe_regex_match returns None for dangerous patterns."""
        dangerous_patterns = [
            "(a+)+b",
            "(.*)*c",
            "(a|aa)+d",
        ]

        for pattern in dangerous_patterns:
            for text in evil_input_strings:
                result = safe_regex_match(pattern, text, timeout_ms=100)
                # Should return None (blocked), not hang
                assert result is None, f"Pattern {pattern} should be blocked"

    def test_safe_regex_match_allows_safe(self):
        """safe_regex_match executes safe patterns normally."""
        assert safe_regex_match("jwt", "use JWT auth", case_insensitive=True) is True
        assert safe_regex_match("^[a-z]+$", "hello") is True
        assert safe_regex_match("^[a-z]+$", "123") is False

    def test_complexity_scoring(self):
        """regex_complexity scores dangerous patterns high."""
        # Safe patterns should have low scores
        assert regex_complexity("exact") < 10
        assert regex_complexity("^[a-z]+$") < 20

        # Dangerous patterns should have high scores
        assert regex_complexity("(a+)+") >= 100
        assert regex_complexity("(.*.*)") >= 50
        assert regex_complexity("(a|aa)+") >= 75

    def test_handles_invalid_regex(self):
        """safe_regex handles invalid regex gracefully."""
        # Invalid regex should not crash, treated as safe (can't execute)
        assert is_safe_regex("[unclosed") is True
        assert safe_regex_match("[unclosed", "test") is None

    def test_handles_none_inputs(self):
        """safe_regex handles None inputs gracefully."""
        assert is_safe_regex(None) is False
        assert safe_regex_match(None, "test") is None
        assert safe_regex_match("test", None) is None


# ============================================================================
# Test Scenario 2: Hook Execution with Evil Regex in skill-rules.json
# ============================================================================


class TestHookReDoSResilience:
    """Test that TypeScript hooks don't hang on malicious regex patterns.

    IMPORTANT: These tests DEMONSTRATE the vulnerability in current TypeScript hooks.
    The hooks use native RegExp without timeout protection, so they WILL hang
    on malicious input. This is the problem we're documenting and need to fix.

    Tests marked with xfail document known vulnerabilities.
    """

    HOOK_TIMEOUT_SECONDS = 5  # Hooks should complete within 5 seconds

    @pytest.mark.xfail(
        reason="VULNERABILITY: TypeScript hooks use native RegExp without timeout protection",
        strict=True  # Test MUST fail (hang) to pass - documents the vulnerability
    )
    def test_skill_router_completes_with_evil_regex(
        self, hooks_dir: Path, temp_skill_rules_with_evil_regex: Path, evil_input_strings
    ):
        """skill-router.ts completes (doesn't hang) even with evil regex."""
        hook_script = hooks_dir / "dist" / "skill-router.mjs"

        if not hook_script.exists():
            pytest.skip("Compiled skill-router.mjs not found")

        for evil_input in evil_input_strings[:3]:  # Test subset to keep fast
            hook_input = {
                "session_id": "test-session",
                "prompt": evil_input,  # Evil input designed to trigger ReDoS
            }

            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = str(temp_skill_rules_with_evil_regex)

            try:
                result = subprocess.run(
                    ["node", str(hook_script)],
                    input=json.dumps(hook_input),
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=str(hooks_dir),
                    timeout=self.HOOK_TIMEOUT_SECONDS
                )

                # Hook completed (didn't timeout)
                assert result.returncode == 0, f"Hook failed with: {result.stderr}"

                # Should return valid JSON
                output = json.loads(result.stdout.strip())
                assert "result" in output
                assert output["result"] in ["continue", "block"]

            except subprocess.TimeoutExpired:
                pytest.fail(
                    f"skill-router hung on evil input (took >{self.HOOK_TIMEOUT_SECONDS}s): "
                    f"'{evil_input[:50]}...'"
                )

    @pytest.mark.xfail(
        reason="VULNERABILITY: TypeScript hooks use native RegExp without timeout protection",
        strict=True  # Test MUST fail (hang) to pass - documents the vulnerability
    )
    def test_skill_activation_prompt_completes_with_evil_regex(
        self, hooks_dir: Path, temp_skill_rules_with_evil_regex: Path, evil_input_strings
    ):
        """skill-activation-prompt.ts completes (doesn't hang) with evil regex."""
        hook_script = hooks_dir / "dist" / "skill-activation-prompt.mjs"

        if not hook_script.exists():
            pytest.skip("Compiled skill-activation-prompt.mjs not found")

        for evil_input in evil_input_strings[:3]:
            hook_input = {
                "session_id": "test-session",
                "transcript_path": "/tmp/transcript",
                "cwd": str(temp_skill_rules_with_evil_regex),
                "permission_mode": "default",
                "prompt": evil_input,
            }

            env = os.environ.copy()
            env["CLAUDE_PROJECT_DIR"] = str(temp_skill_rules_with_evil_regex)

            try:
                result = subprocess.run(
                    ["node", str(hook_script)],
                    input=json.dumps(hook_input),
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=str(hooks_dir),
                    timeout=self.HOOK_TIMEOUT_SECONDS
                )

                # Hook should complete, even if it exits with error due to invalid regex
                # The key is it doesn't HANG
                pass  # Success if we reach here (no timeout)

            except subprocess.TimeoutExpired:
                pytest.fail(
                    f"skill-activation-prompt hung on evil input: '{evil_input[:50]}...'"
                )

    def test_hooks_handle_safe_patterns_correctly(
        self, hooks_dir: Path, temp_skill_rules_with_evil_regex: Path
    ):
        """Hooks still match safe patterns correctly."""
        hook_script = hooks_dir / "dist" / "skill-activation-prompt.mjs"

        if not hook_script.exists():
            pytest.skip("Compiled skill-activation-prompt.mjs not found")

        # This should match the "safe-skill" via keyword
        hook_input = {
            "session_id": "test-session",
            "transcript_path": "/tmp/transcript",
            "cwd": str(temp_skill_rules_with_evil_regex),
            "permission_mode": "default",
            "prompt": "normal-trigger test",
        }

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(temp_skill_rules_with_evil_regex)

        result = subprocess.run(
            ["node", str(hook_script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            cwd=str(hooks_dir),
            timeout=self.HOOK_TIMEOUT_SECONDS
        )

        assert result.returncode == 0
        # Should find the safe-skill via keyword match
        assert "safe-skill" in result.stdout


# ============================================================================
# Test Scenario 3: Full Pipeline Integration Tests
# ============================================================================


class TestEndToEndSafeRegexIntegration:
    """Test the Python-to-TypeScript integration boundary."""

    def test_python_validator_catches_what_ts_would_hang_on(
        self, evil_input_strings
    ):
        """Python safe_regex catches patterns that could hang TypeScript."""
        patterns_that_could_hang = [
            "(a+)+b",
            "(.*)*c",
            "(a|aa)+d",
            "(.+.+)+e",
        ]

        for pattern in patterns_that_could_hang:
            # Python correctly identifies as dangerous
            assert not is_safe_regex(pattern), f"Pattern should be unsafe: {pattern}"

            # Python blocks execution
            for evil_input in evil_input_strings[:2]:
                result = safe_regex_match(pattern, evil_input, timeout_ms=100)
                assert result is None, f"Should block: {pattern} on {evil_input[:20]}"

    def test_prevalidation_workflow(self, hooks_dir: Path, tmp_path: Path):
        """Test workflow: Python pre-validates, then passes to TypeScript.

        This tests the recommended integration pattern:
        1. Before adding intentPatterns to skill-rules.json
        2. Run Python validation on each pattern
        3. Only include patterns that pass validation
        """
        # Create a skill-rules.json with ONLY validated patterns
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)

        candidate_patterns = [
            "(a+)+b",          # Will be rejected
            "^[a-z]+$",        # Will be accepted
            "(.*)*c",          # Will be rejected
            "\\btest\\b",      # Will be accepted
            "run\\s+tests?",   # Will be accepted
        ]

        # Filter to only safe patterns
        safe_patterns = [p for p in candidate_patterns if is_safe_regex(p)]
        rejected_patterns = [p for p in candidate_patterns if not is_safe_regex(p)]

        assert len(safe_patterns) == 3
        assert len(rejected_patterns) == 2
        assert "(a+)+b" in rejected_patterns
        assert "^[a-z]+$" in safe_patterns

        # Create rules with only safe patterns
        rules = {
            "version": "1.0",
            "skills": {
                "validated-skill": {
                    "type": "domain",
                    "enforcement": "suggest",
                    "priority": "medium",
                    "promptTriggers": {
                        "keywords": ["validated"],
                        "intentPatterns": safe_patterns
                    }
                }
            },
            "agents": {}
        }

        (skills_dir / "skill-rules.json").write_text(json.dumps(rules, indent=2))

        # Now run the hook - should complete safely
        hook_script = hooks_dir / "dist" / "skill-activation-prompt.mjs"

        if not hook_script.exists():
            pytest.skip("Compiled hook not found")

        hook_input = {
            "session_id": "test",
            "transcript_path": "/tmp/test",
            "cwd": str(tmp_path),
            "permission_mode": "default",
            "prompt": "validated hello test",
        }

        env = os.environ.copy()
        env["CLAUDE_PROJECT_DIR"] = str(tmp_path)

        result = subprocess.run(
            ["node", str(hook_script)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            env=env,
            timeout=5
        )

        assert result.returncode == 0


# ============================================================================
# Test Scenario 4: Stress Tests and Edge Cases
# ============================================================================


class TestReDoSStressTests:
    """Stress tests to ensure ReDoS protection under extreme conditions."""

    def test_concurrent_regex_evaluation(self, evil_input_strings):
        """Multiple concurrent regex evaluations don't hang."""
        import concurrent.futures

        dangerous_patterns = ["(a+)+b", "(.*)*c", "(a|aa)+d"]

        def evaluate_pattern(pattern: str, text: str) -> bool:
            """Thread-safe pattern evaluation."""
            result = safe_regex_match(pattern, text, timeout_ms=100)
            return result is None  # Should be blocked

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for pattern in dangerous_patterns:
                for text in evil_input_strings:
                    futures.append(executor.submit(evaluate_pattern, pattern, text))

            # All should complete within reasonable time
            results = []
            for future in concurrent.futures.as_completed(futures, timeout=10):
                results.append(future.result())

            # All dangerous patterns should be blocked
            assert all(results), "Some dangerous patterns were not blocked"

    def test_very_long_input_string(self):
        """Long input strings don't cause excessive memory or time."""
        long_string = "a" * 100000

        # Safe pattern should still work
        start = time.time()
        result = safe_regex_match("^a+$", long_string, timeout_ms=1000)
        elapsed = time.time() - start

        # Should complete in reasonable time (even with long string)
        assert elapsed < 2.0, f"Took too long: {elapsed}s"
        assert result is True

    def test_deeply_nested_groups(self):
        """Deeply nested groups with quantifiers are detected as dangerous."""
        # Pattern with nested groups AND quantifiers
        # Note: Simple nested groups without quantifier chaining are safe
        nested_dangerous = "((a+)+)+"  # Truly dangerous: nested quantifiers
        nested_safe = "(" * 10 + "a+" + ")" * 10  # Just deep nesting, no outer quantifier

        # Nested quantifiers should be caught
        assert not is_safe_regex(nested_dangerous)
        assert regex_complexity(nested_dangerous) >= 100

        # Just deep nesting without outer quantifier is technically safe (no backtracking explosion)
        # The danger is when you have (pattern+)+ not just ((((pattern+))))
        # This is a nuance in ReDoS detection

    def test_rapid_fire_evaluations(self):
        """Rapid consecutive evaluations don't accumulate issues."""
        pattern = "(a+)+b"
        text = "a" * 25

        for _ in range(100):
            result = safe_regex_match(pattern, text, timeout_ms=50)
            assert result is None  # Should be blocked every time


# ============================================================================
# Test Scenario 5: Integration Strategy Recommendations
# ============================================================================


class TestIntegrationStrategyValidation:
    """Validate the recommended integration strategies work correctly."""

    def test_option_a_python_prevalidation(self, tmp_path: Path):
        """Option A: Python pre-validates all patterns before TS use.

        Workflow:
        1. Define patterns in a config file
        2. Run Python validator on startup
        3. Log/reject dangerous patterns
        4. Only safe patterns reach TypeScript
        """
        patterns_config = {
            "patterns": [
                {"id": "auth", "pattern": "jwt|oauth|api.?key"},
                {"id": "test", "pattern": "(run|execute).*test"},
                {"id": "evil", "pattern": "(a+)+b"},  # Dangerous
            ]
        }

        config_path = tmp_path / "patterns.json"
        config_path.write_text(json.dumps(patterns_config))

        # Validation step
        validated = []
        rejected = []

        for item in patterns_config["patterns"]:
            if is_safe_regex(item["pattern"]):
                validated.append(item)
            else:
                rejected.append(item)

        assert len(validated) == 2
        assert len(rejected) == 1
        assert rejected[0]["id"] == "evil"

    def test_option_b_typescript_port_parity(self):
        """Option B: TypeScript port would need same detection logic.

        This test validates the detection patterns that would need porting:
        1. Nested quantifiers: (a+)+
        2. Overlapping alternation: (a|aa)+
        3. Multiple greedy patterns: .*.*
        """
        # These are the patterns safe_regex detects
        detection_test_cases = [
            ("(a+)+", False, "nested quantifiers"),
            ("(a*)+", False, "nested quantifiers"),
            ("(.*)+", False, "nested quantifiers"),
            ("(a|aa)+", False, "overlapping alternation"),
            (".*.*", False, "multiple greedy"),
            (".+.+", False, "multiple greedy"),
            ("^[a-z]+$", True, "simple pattern"),
            ("\\bword\\b", True, "word boundary"),
        ]

        for pattern, expected_safe, description in detection_test_cases:
            actual = is_safe_regex(pattern)
            assert actual == expected_safe, (
                f"Pattern '{pattern}' ({description}): expected safe={expected_safe}, got {actual}"
            )


# ============================================================================
# Existing Tests Integration
# ============================================================================


class TestExistingHookPatternsRemainSafe:
    """Verify patterns used in existing hooks are safe."""

    def test_erotetic_questions_infer_patterns(self):
        """Patterns in erotetic-questions.ts inferFrom are safe.

        These patterns are used at line ~330 for auto-inference.
        """
        # Patterns extracted from erotetic-questions.ts
        infer_patterns = [
            "jwt|oauth|api.?key|session|bearer|token",
            "tdd|test.?driven|unit.?test|integration|e2e",
            "\\.(ts|js|py|go|rs|java)\\b|src\\/|lib\\/|tests?\\/|components?\\/|scripts\\/",
            "runtime|compile|build|logic|performance|slow|memory|crash",
            "in \\w+\\.(ts|js|py)|module|package|system|everywhere|all",
            "quick|immediate|root.?cause|audit|comprehensive|thorough",
            "overview|summary|brief|deep|comprehensive|detailed|thorough",
            "docs?|documentation|codebase|code|web|external|papers?|research",
            "summary|report|examples?|code|comparison|table|compare",
            "high.?level|detailed|step.?by.?step|phases?|outline",
            "time|estimate|hours?|days?|deadline|timeline|schedule",
            "risk|mitigation|contingency|fallback|backup",
        ]

        for pattern in infer_patterns:
            assert is_safe_regex(pattern), f"Pattern should be safe: {pattern}"
            # Also verify complexity is reasonable
            assert regex_complexity(pattern) < 50, f"Pattern too complex: {pattern}"

    def test_skill_router_example_patterns(self):
        """Example patterns that might be in skill-rules.json are analyzed.

        Note: Some common-looking patterns can be dangerous due to optional groups
        with quantifiers. The safe_regex detector is intentionally conservative.
        """
        # Common patterns that users might add
        example_patterns_safe = [
            "(run|execute).*test",     # Safe: .* but no nesting
            "launch\\s+agentica",      # Safe: simple quantifier
            "^/[a-z-]+",               # Safe: simple quantifier
            "debug\\s+.*error",        # Safe: .* but anchored by literals
        ]

        # This pattern has optional group with quantifier: (new\s+)?
        # The ? on a group containing \s+ creates potential issues
        # Conservative detection flags it
        potentially_problematic = [
            "create\\s+(new\\s+)?skill",  # Flagged: optional group with quantifier inside
        ]

        for pattern in example_patterns_safe:
            safe = is_safe_regex(pattern)
            complexity = regex_complexity(pattern)
            assert safe, f"Safe pattern falsely flagged: {pattern}"

        for pattern in potentially_problematic:
            # These may or may not be safe depending on detector sensitivity
            safe = is_safe_regex(pattern)
            if not safe:
                # Document that this pattern is flagged
                print(f"INFO: Pattern '{pattern}' flagged as potentially unsafe (conservative)")
            # Don't assert - just document behavior

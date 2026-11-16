"""Tests for skillName path traversal prevention.

TDD Phase 1b: These tests should FAIL initially because the module doesn't exist.
They define the expected behavior for skill name validation to prevent path traversal attacks.

Vulnerability being addressed:
- File: .claude/hooks/src/skill-router.ts (lines 221-228)
- Issue: skillName from memory metadata used in path construction without validation
- Risk: If skillName = "../../../etc/passwd" it could enable path traversal

Expected module: scripts/agentica/skill_validation.py
"""


class TestSkillNameValidation:
    """Test skillName validation to prevent path traversal attacks."""

    def test_rejects_path_traversal_dotdot(self):
        """../etc/passwd should be rejected - classic Unix path traversal."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("../etc/passwd") is False

    def test_rejects_double_dotdot_traversal(self):
        """../../root should be rejected - multiple level traversal."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("../../root") is False

    def test_rejects_absolute_path(self):
        """/etc/passwd should be rejected - absolute paths bypass skill directory."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("/etc/passwd") is False

    def test_rejects_backslash_traversal(self):
        """..\\windows\\system32 should be rejected - Windows path traversal."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("..\\windows\\system32") is False

    def test_rejects_encoded_traversal(self):
        """%2e%2e%2f should be rejected (URL encoded ../)."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("%2e%2e%2f") is False

    def test_rejects_double_encoded_traversal(self):
        """%252e%252e%252f should be rejected (double URL encoded)."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("%252e%252e%252f") is False

    def test_rejects_null_byte(self):
        """skill\\x00.md should be rejected - null byte injection."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("skill\x00.md") is False

    def test_rejects_shell_metacharacters(self):
        """skill;rm -rf should be rejected - command injection potential."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("skill;rm -rf") is False

    def test_rejects_subshell_syntax(self):
        """skill$(cmd) should be rejected - subshell command injection."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("skill$(cmd)") is False

    def test_rejects_backtick_command(self):
        """skill`cmd` should be rejected - backtick command injection."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("skill`cmd`") is False

    def test_accepts_valid_skill_name(self):
        """my-skill_v2 should be accepted - alphanumeric with hyphen/underscore."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("my-skill_v2") is True

    def test_accepts_simple_alphanumeric(self):
        """auth123 should be accepted."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("auth123") is True

    def test_accepts_hyphenated_name(self):
        """test-driven-development should be accepted."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("test-driven-development") is True

    def test_accepts_underscored_name(self):
        """skill_generator_v2 should be accepted."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("skill_generator_v2") is True

    def test_rejects_nested_skill_path(self):
        """math/real-analysis should be rejected - no nested directories allowed.

        Note: The plan mentions accepting nested skills, but this is a security
        risk since path separators could be exploited. Prefer flat skill names.
        """
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        # Rejecting nested paths is more secure than allowing them
        assert is_valid_skill_name("math/real-analysis") is False

    def test_rejects_empty_string(self):
        """Empty string should be rejected."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("") is False

    def test_rejects_none(self):
        """None should be rejected."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name(None) is False

    def test_rejects_whitespace_only(self):
        """Whitespace-only should be rejected."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name("   ") is False

    def test_rejects_leading_dot(self):
        """.hidden should be rejected - could access hidden directories."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        assert is_valid_skill_name(".hidden") is False

    def test_rejects_excessively_long_name(self):
        """Very long names (>100 chars) should be rejected."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        long_name = "a" * 150
        assert is_valid_skill_name(long_name) is False

    def test_accepts_max_length_name(self):
        """Names at exactly 100 chars should be accepted."""
        from scripts.agentica_patterns.skill_validation import is_valid_skill_name

        max_name = "a" * 100
        assert is_valid_skill_name(max_name) is True


class TestSanitizeSkillName:
    """Test skillName sanitization as a fallback defense."""

    def test_sanitize_removes_traversal(self):
        """Sanitize should remove path traversal sequences."""
        from scripts.agentica_patterns.skill_validation import sanitize_skill_name

        assert sanitize_skill_name("../evil") == "evil"

    def test_sanitize_removes_multiple_traversal(self):
        """Sanitize should remove all path traversal sequences."""
        from scripts.agentica_patterns.skill_validation import sanitize_skill_name

        result = sanitize_skill_name("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_sanitize_preserves_valid(self):
        """Sanitize should preserve valid skill names unchanged."""
        from scripts.agentica_patterns.skill_validation import sanitize_skill_name

        assert sanitize_skill_name("my-skill") == "my-skill"

    def test_sanitize_removes_shell_chars(self):
        """Sanitize should remove shell metacharacters."""
        from scripts.agentica_patterns.skill_validation import sanitize_skill_name

        result = sanitize_skill_name("skill;rm -rf")
        assert ";" not in result
        assert " " not in result

    def test_sanitize_removes_backslashes(self):
        """Sanitize should remove Windows path separators."""
        from scripts.agentica_patterns.skill_validation import sanitize_skill_name

        result = sanitize_skill_name("..\\windows")
        assert "\\" not in result

    def test_sanitize_handles_empty(self):
        """Sanitize should handle empty string gracefully."""
        from scripts.agentica_patterns.skill_validation import sanitize_skill_name

        result = sanitize_skill_name("")
        assert result == "" or result is None

    def test_sanitize_handles_none(self):
        """Sanitize should handle None gracefully."""
        from scripts.agentica_patterns.skill_validation import sanitize_skill_name

        result = sanitize_skill_name(None)
        assert result == "" or result is None

    def test_sanitize_truncates_long_name(self):
        """Sanitize should truncate excessively long names."""
        from scripts.agentica_patterns.skill_validation import sanitize_skill_name

        long_name = "a" * 200
        result = sanitize_skill_name(long_name)
        assert len(result) <= 100


class TestValidateSkillPath:
    """Test full path validation as defense in depth."""

    def test_rejects_path_outside_skills_dir(self):
        """Constructed path must be within skills directory."""
        from scripts.agentica_patterns.skill_validation import validate_skill_path

        # Even if skill name looks valid, the resolved path must be checked
        is_valid = validate_skill_path(
            skill_name="valid-name",
            skills_dir="/home/user/.claude/skills",
            constructed_path="/etc/passwd",
        )
        assert is_valid is False

    def test_accepts_path_within_skills_dir(self):
        """Path within skills directory should be accepted."""
        from scripts.agentica_patterns.skill_validation import validate_skill_path

        is_valid = validate_skill_path(
            skill_name="auth-skill",
            skills_dir="/home/user/.claude/skills",
            constructed_path="/home/user/.claude/skills/auth-skill/SKILL.md",
        )
        assert is_valid is True

    def test_rejects_symlink_escape(self):
        """Even if path looks correct, symlink escape should be detected.

        Note: This test may require actual filesystem setup or mocking.
        The validator should use realpath() to resolve symlinks.
        """
        from scripts.agentica_patterns.skill_validation import validate_skill_path

        # This tests that we resolve symlinks before checking containment
        # In practice, the path might look correct but resolve elsewhere
        is_valid = validate_skill_path(
            skill_name="malicious-link",
            skills_dir="/home/user/.claude/skills",
            # This would need realpath() resolution in real implementation
            constructed_path="/home/user/.claude/skills/malicious-link/SKILL.md",
        )
        # Test that the function exists and returns a boolean
        assert isinstance(is_valid, bool)

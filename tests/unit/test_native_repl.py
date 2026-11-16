"""
Tests for Native REPL Approach - run_claude() function.

The Native REPL approach uses Claude Code CLI as the execution layer
for Agentica agents. This provides file I/O access via Claude Code's
native tools (Read, Write, Edit, Bash) while keeping Agentica for
agent orchestration.

Architecture:
  Agentica Agent (orchestration)
    └─ REPL Session
        └─ scope: { run_claude: async fn }
            └─ Executes: subprocess.run(['claude', '-p', ...])

Reference: scripts/agentica/native_repl/RESEARCH.md
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add scripts/agentica to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "agentica"))


# ============================================================================
# Mock Implementation of run_claude() for Testing
# ============================================================================
# NOTE: This is a reference implementation based on RESEARCH.md
# The actual implementation should be in scripts/agentica/native_repl/run_claude.py


async def run_claude(
    task: str,
    tools: list[str] | None = None,
    max_turns: int = 3,
    system_prompt: str | None = None,
    timeout: int = 900,
) -> str:
    """
    Execute a task using Claude Code CLI.

    Args:
        task: The task prompt for Claude to execute
        tools: List of allowed tools (e.g., ["Read", "Write", "Edit", "Bash"])
               If None, defaults to all tools
        max_turns: Maximum number of agentic turns (default: 3)
        system_prompt: Optional custom system prompt to append
        timeout: Timeout in seconds (default: 900 = 15 minutes)

    Returns:
        The output from Claude CLI (stdout)

    Raises:
        subprocess.TimeoutExpired: If execution exceeds timeout
        subprocess.CalledProcessError: If claude CLI returns non-zero exit code
        FileNotFoundError: If 'claude' command not found in PATH

    Example:
        ```python
        # Read a file
        result = await run_claude(
            task="Read pyproject.toml and list dependencies",
            tools=["Read"],
            max_turns=1
        )

        # Modify a file
        result = await run_claude(
            task="Update version to 1.0.0 in pyproject.toml",
            tools=["Read", "Edit"],
            max_turns=3
        )
        ```
    """
    # Build command
    cmd = [
        "claude",
        "-p",  # Print mode (non-interactive)
        task,
        "--max-turns", str(max_turns),
        "--output-format", "json",
        "--dangerously-skip-permissions",
    ]

    # Add tool restrictions
    if tools:
        cmd.extend(["--allowed-tools", ",".join(tools)])

    # Add custom system prompt
    if system_prompt:
        cmd.extend(["--append-system-prompt", system_prompt])

    # Run in executor to avoid blocking event loop
    loop = asyncio.get_running_loop()

    def _run():
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # Raise on non-zero exit code
        result.check_returncode()
        return result.stdout.strip()

    return await loop.run_in_executor(None, _run)


# ============================================================================
# Test Suite
# ============================================================================


class TestRunClaudeBasic:
    """Test basic functionality of run_claude()."""

    @pytest.mark.asyncio
    async def test_basic_task_execution(self):
        """Should execute a basic task and return output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Task completed successfully"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            result = await run_claude(task="What is 2+2?")

            # Verify subprocess was called
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]

            # Check command structure
            assert args[0] == "claude"
            assert "-p" in args
            assert "What is 2+2?" in args
            assert "--max-turns" in args
            assert "--output-format" in args
            assert "json" in args
            assert "--dangerously-skip-permissions" in args

            # Check result
            assert result == "Task completed successfully"

    @pytest.mark.asyncio
    async def test_with_tool_restrictions(self):
        """Should pass tool restrictions to Claude CLI."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "File read successfully"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await run_claude(
                task="Read pyproject.toml",
                tools=["Read"],
            )

            args = mock_run.call_args[0][0]
            assert "--allowed-tools" in args
            allowed_tools_idx = args.index("--allowed-tools")
            assert args[allowed_tools_idx + 1] == "Read"

    @pytest.mark.asyncio
    async def test_with_multiple_tools(self):
        """Should allow multiple tools as comma-separated list."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "File updated"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await run_claude(
                task="Update config.json",
                tools=["Read", "Write", "Edit"],
            )

            args = mock_run.call_args[0][0]
            assert "--allowed-tools" in args
            allowed_tools_idx = args.index("--allowed-tools")
            assert args[allowed_tools_idx + 1] == "Read,Write,Edit"

    @pytest.mark.asyncio
    async def test_with_custom_system_prompt(self):
        """Should append custom system prompt."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Custom response"
        mock_result.check_returncode = MagicMock()

        custom_prompt = "Be concise and use bullet points"

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await run_claude(
                task="Summarize features",
                system_prompt=custom_prompt,
            )

            args = mock_run.call_args[0][0]
            assert "--append-system-prompt" in args
            prompt_idx = args.index("--append-system-prompt")
            assert args[prompt_idx + 1] == custom_prompt

    @pytest.mark.asyncio
    async def test_with_max_turns_limit(self):
        """Should set max turns limit."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await run_claude(
                task="Complex task",
                max_turns=5,
            )

            args = mock_run.call_args[0][0]
            assert "--max-turns" in args
            turns_idx = args.index("--max-turns")
            assert args[turns_idx + 1] == "5"

    @pytest.mark.asyncio
    async def test_default_max_turns(self):
        """Should use default max_turns of 3."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await run_claude(task="Simple task")

            args = mock_run.call_args[0][0]
            turns_idx = args.index("--max-turns")
            assert args[turns_idx + 1] == "3"


class TestRunClaudeErrorHandling:
    """Test error handling in run_claude()."""

    @pytest.mark.asyncio
    async def test_subprocess_timeout(self):
        """Should raise TimeoutExpired on timeout."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("claude", 900)):
            with pytest.raises(subprocess.TimeoutExpired):
                await run_claude(task="Long running task", timeout=1)

    @pytest.mark.asyncio
    async def test_claude_not_found(self):
        """Should raise FileNotFoundError if 'claude' not in PATH."""
        with patch('subprocess.run', side_effect=FileNotFoundError("claude not found")):
            with pytest.raises(FileNotFoundError):
                await run_claude(task="Any task")

    @pytest.mark.asyncio
    async def test_non_zero_exit_code(self):
        """Should raise CalledProcessError on non-zero exit code."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: invalid command"
        mock_result.check_returncode = MagicMock(
            side_effect=subprocess.CalledProcessError(1, "claude")
        )

        with patch('subprocess.run', return_value=mock_result):
            with pytest.raises(subprocess.CalledProcessError):
                await run_claude(task="Invalid task")

    @pytest.mark.asyncio
    async def test_custom_timeout(self):
        """Should use custom timeout value."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await run_claude(task="Task", timeout=60)

            # Check that timeout was passed to subprocess.run
            kwargs = mock_run.call_args[1]
            assert kwargs.get('timeout') == 60

    @pytest.mark.asyncio
    async def test_empty_output(self):
        """Should handle empty stdout gracefully."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "   \n  "  # Whitespace only
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result):
            result = await run_claude(task="Task")
            assert result == ""  # Should strip to empty string


class TestRunClaudeOutputParsing:
    """Test output parsing and JSON handling."""

    @pytest.mark.asyncio
    async def test_json_output_format(self):
        """Should request JSON output format."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"result": "success"}'
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            result = await run_claude(task="Task")

            args = mock_run.call_args[0][0]
            assert "--output-format" in args
            format_idx = args.index("--output-format")
            assert args[format_idx + 1] == "json"

            # Result should be the JSON string (not parsed)
            assert result == '{"result": "success"}'

    @pytest.mark.asyncio
    async def test_multiline_output(self):
        """Should preserve multiline output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Line 1\nLine 2\nLine 3"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result):
            result = await run_claude(task="Task")
            assert result == "Line 1\nLine 2\nLine 3"


class TestRunClaudeIntegrationWithAgentica:
    """Test integration patterns with Agentica scope."""

    @pytest.mark.asyncio
    async def test_as_agentica_scope_function(self):
        """Should work as a scope function in Agentica agent."""
        # This tests the pattern from RESEARCH.md:
        # agent = await spawn(
        #     premise="...",
        #     scope={"run_claude": run_claude}
        # )

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Task completed"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result):
            # Simulate calling from within an agent's REPL
            result = await run_claude(
                task="Read pyproject.toml",
                tools=["Read"],
                max_turns=1
            )

            assert result == "Task completed"

    @pytest.mark.asyncio
    async def test_concurrent_execution(self):
        """Should support concurrent execution from multiple agents."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result):
            # Simulate multiple agents calling run_claude concurrently
            tasks = [
                run_claude(task=f"Task {i}", tools=["Read"])
                for i in range(5)
            ]
            results = await asyncio.gather(*tasks)

            assert len(results) == 5
            assert all(r == "Result" for r in results)


class TestRunClaudeCommandConstruction:
    """Test CLI command construction details."""

    @pytest.mark.asyncio
    async def test_print_mode_flag(self):
        """Should always include -p flag for print mode."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await run_claude(task="Task")

            args = mock_run.call_args[0][0]
            assert "-p" in args

    @pytest.mark.asyncio
    async def test_dangerous_skip_permissions_flag(self):
        """Should include --dangerously-skip-permissions for headless operation."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await run_claude(task="Task")

            args = mock_run.call_args[0][0]
            assert "--dangerously-skip-permissions" in args

    @pytest.mark.asyncio
    async def test_command_order(self):
        """Should construct command in correct order."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await run_claude(
                task="Test task",
                tools=["Read"],
                max_turns=5,
                system_prompt="Custom prompt"
            )

            args = mock_run.call_args[0][0]

            # Check basic structure
            assert args[0] == "claude"
            assert args[1] == "-p"
            assert args[2] == "Test task"

            # Flags should be present (order may vary)
            assert "--max-turns" in args
            assert "--output-format" in args
            assert "--allowed-tools" in args
            assert "--append-system-prompt" in args

    @pytest.mark.asyncio
    async def test_no_tools_specified(self):
        """Should not include --allowed-tools if tools is None."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await run_claude(task="Task", tools=None)

            args = mock_run.call_args[0][0]
            assert "--allowed-tools" not in args

    @pytest.mark.asyncio
    async def test_empty_tools_list(self):
        """Should handle empty tools list gracefully."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await run_claude(task="Task", tools=[])

            args = mock_run.call_args[0][0]
            # Empty list should still add flag but with empty string
            # or could choose not to add flag at all
            # Implementation choice - document expected behavior
            if "--allowed-tools" in args:
                idx = args.index("--allowed-tools")
                assert args[idx + 1] == ""


class TestRunClaudeAsyncBehavior:
    """Test async/await behavior and event loop integration."""

    @pytest.mark.asyncio
    async def test_runs_in_executor(self):
        """Should run subprocess in executor to avoid blocking event loop."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result):
            # This should not block the event loop
            result = await run_claude(task="Task")
            assert result == "Result"

    @pytest.mark.asyncio
    async def test_awaitable_return(self):
        """Should return awaitable that resolves to string."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Test result"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result):
            coro = run_claude(task="Task")

            # Should be awaitable
            assert asyncio.iscoroutine(coro)

            # Should resolve to string
            result = await coro
            assert isinstance(result, str)
            assert result == "Test result"


class TestRunClaudeEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_very_long_task(self):
        """Should handle very long task strings."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        long_task = "A" * 10000  # 10k character task

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            result = await run_claude(task=long_task)

            args = mock_run.call_args[0][0]
            assert long_task in args
            assert result == "Result"

    @pytest.mark.asyncio
    async def test_special_characters_in_task(self):
        """Should handle special characters in task string."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        special_task = 'Task with "quotes" and \'apostrophes\' and $vars and \n newlines'

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            result = await run_claude(task=special_task)

            args = mock_run.call_args[0][0]
            assert special_task in args
            assert result == "Result"

    @pytest.mark.asyncio
    async def test_unicode_in_task(self):
        """Should handle Unicode characters in task."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result with émojis 🎉"
        mock_result.check_returncode = MagicMock()

        unicode_task = "Analyze file with émojis 🚀 and 日本語"

        with patch('subprocess.run', return_value=mock_result):
            result = await run_claude(task=unicode_task)
            assert "émojis 🎉" in result

    @pytest.mark.asyncio
    async def test_zero_max_turns(self):
        """Should handle max_turns=0 (edge case)."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Result"
        mock_result.check_returncode = MagicMock()

        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await run_claude(task="Task", max_turns=0)

            args = mock_run.call_args[0][0]
            turns_idx = args.index("--max-turns")
            assert args[turns_idx + 1] == "0"

    @pytest.mark.asyncio
    async def test_very_short_timeout(self):
        """Should respect very short timeout."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired("claude", 1)):
            with pytest.raises(subprocess.TimeoutExpired):
                await run_claude(task="Task", timeout=1)

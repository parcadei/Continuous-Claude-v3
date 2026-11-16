#!/usr/bin/env python3
"""Async wrapper for Claude Code CLI.

This module provides an async function to execute Claude Code CLI
commands from within Agentica REPL agents. It's designed to be used
as a scope function in agent spawning.

Architecture:
    Agentica Agent → REPL → run_claude() → subprocess → Claude Code CLI

Usage:
    from scripts.agentica_patterns.native_repl.run_claude import run_claude

    # As a scope function in an agent
    agent = await spawn(
        premise="You are a code analyzer.",
        scope={"run_claude": run_claude}
    )

    # In agent's REPL code:
    result = await run_claude(
        task="Read pyproject.toml and extract the project name",
        tools=["Read"],
        max_turns=3
    )

References:
    - RESEARCH.md: Architecture and design decisions
    - Claude Code CLI: https://code.claude.com/docs/en/cli-reference
"""

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4


class ClaudeExecutionError(Exception):
    """Raised when Claude Code CLI execution fails."""
    pass


# =============================================================================
# System Prompt Templates
# =============================================================================

MODULAR_SYSTEM_PROMPT = """
ARCHITECTURE: Organize as a Python package with clear separation of concerns.

LAYERS (each = separate file(s)):
- Data layer: Dataclasses/Pydantic models, no logic
- Tool layer: External integrations, wrappers, API calls
- Core layer: Business logic orchestration
- Interface layer: CLI/API entry points

CONSTRAINTS:
- No file exceeds 250 lines
- No function exceeds 50 lines
- Use type hints everywhere
- Import direction: data <- tools <- core <- interface
- When file approaches limit, split into sub-modules

AVAILABLE SCRIPTS (call via Bash):
- Code quality: `qlty check --fix` (run after implementation)
- Docs lookup: `uv run python scripts/nia_docs.py --package <pkg> --query "..."`
- Web research: `uv run python scripts/perplexity_search.py --research "..."`
"""


class ClaudeParseError(Exception):
    """Raised when Claude Code CLI output cannot be parsed."""
    pass


async def run_claude(
    task: str,
    tools: list[str] | None = None,
    max_turns: int = 0,  # 0 = unlimited turns
    system_prompt: str | None = None,
    model: str | None = None,
    timeout: int = 1800,  # 30 min timeout for complex tasks
    modular: bool = False,  # Inject MODULAR_SYSTEM_PROMPT for package architecture
    validate: bool = False,  # Run qlty check --fix after implementation
) -> dict[str, Any]:
    """Execute Claude Code CLI and return parsed result.

    This function wraps the Claude Code CLI for use in Agentica REPL
    agents. It executes Claude autonomously with JSON output parsing.

    Args:
        task: The prompt/task for Claude to execute
        tools: Optional list of allowed tools (e.g., ["Read", "Write", "Bash(git:*)"])
               If None, all tools are allowed (with permission prompts)
        max_turns: Maximum agentic turns to allow (default: 5)
        system_prompt: Optional system prompt to append to defaults
        model: Optional model override (e.g., "sonnet", "opus")
        timeout: Subprocess timeout in seconds (default: 300)
        modular: If True, inject MODULAR_SYSTEM_PROMPT for clean package architecture
        validate: If True, append instruction to run qlty check --fix after implementation

    Returns:
        Dictionary with parsed JSON output from Claude Code CLI.
        Structure depends on the --output-format json schema:
        {
            "status": "success" | "error",
            "result": <task result>,
            "turns": <number of turns>,
            "output": <full output text>,
            ...
        }

    Raises:
        ClaudeExecutionError: If Claude Code CLI fails to execute
        ClaudeParseError: If JSON output cannot be parsed
        FileNotFoundError: If 'claude' CLI not found in PATH

    Examples:
        # Basic call
        >>> result = await run_claude(task="Read pyproject.toml")

        # Modular implementation with validation
        >>> result = await run_claude(
        ...     task="Implement user authentication",
        ...     modular=True,
        ...     validate=True,
        ...     max_turns=15
        ... )
        >>> print(result["result"])
    """
    # Handle modular flag: inject MODULAR_SYSTEM_PROMPT
    if modular:
        base_prompt = system_prompt or ""
        system_prompt = MODULAR_SYSTEM_PROMPT + "\n\n" + base_prompt

    # Handle validate flag: append qlty check instruction to task
    if validate:
        task = task + "\n\nAfter implementation, run: qlty check --fix"

    # Check if claude CLI is available
    if not shutil.which("claude"):
        raise FileNotFoundError(
            "Claude Code CLI not found in PATH. "
            "Install from: https://code.claude.com/download"
        )

    # Generate subprocess session ID for Braintrust correlation
    # Must be a valid UUID for Claude CLI --session-id
    subprocess_id = str(uuid4())

    # Build command
    cmd = [
        "claude",
        "-p",  # Short form of --print (non-interactive mode)
        "--output-format", "json",  # Parseable output
        "--dangerously-skip-permissions",  # Autonomous execution
        "--session-id", subprocess_id,  # Enable parent-child correlation
    ]

    # Add max turns
    if max_turns > 0:
        cmd.extend(["--max-turns", str(max_turns)])

    # Add allowed tools (comma-separated per CLI docs)
    if tools:
        cmd.extend(["--allowed-tools", ",".join(tools)])

    # Add system prompt (use --append-system-prompt to preserve defaults)
    if system_prompt:
        cmd.extend(["--append-system-prompt", system_prompt])

    # Add model override
    if model:
        cmd.extend(["--model", model])

    # Add separator and task as final arguments
    # The -- separator is required because --allowed-tools is variadic
    # and would otherwise consume the task as part of the tools list
    cmd.append("--")
    cmd.append(task)

    try:
        # Execute subprocess asynchronously
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait for completion with timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
        except TimeoutError:
            process.kill()
            await process.wait()
            raise ClaudeExecutionError(
                f"Claude Code execution timed out after {timeout}s"
            )

        # Check return code
        if process.returncode != 0:
            stderr_text = stderr.decode("utf-8", errors="replace")
            raise ClaudeExecutionError(
                f"Claude Code CLI failed with code {process.returncode}\n"
                f"Error: {stderr_text}"
            )

        # Parse JSON output
        stdout_text = stdout.decode("utf-8", errors="replace")
        try:
            result = json.loads(stdout_text)
            return result
        except json.JSONDecodeError as e:
            raise ClaudeParseError(
                f"Failed to parse Claude Code output as JSON: {e}\n"
                f"Output: {stdout_text[:500]}"
            )

    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"Failed to execute command: {e}\n"
            f"Command: {' '.join(cmd)}"
        )
    except Exception as e:
        if isinstance(e, (ClaudeExecutionError, ClaudeParseError)):
            raise
        raise ClaudeExecutionError(f"Unexpected error executing Claude Code: {e}")


def run_claude_sync(
    task: str,
    tools: list[str] | None = None,
    max_turns: int = 5,
    system_prompt: str | None = None,
    model: str | None = None,
    timeout: int = 300,
    modular: bool = False,
    validate: bool = False,
) -> dict[str, Any]:
    """Synchronous wrapper for run_claude.

    This is a convenience function for non-async contexts.
    Prefer the async version when possible.

    Args:
        Same as run_claude()

    Returns:
        Same as run_claude()

    Raises:
        Same as run_claude()
    """
    return asyncio.run(run_claude(
        task=task,
        tools=tools,
        max_turns=max_turns,
        system_prompt=system_prompt,
        model=model,
        timeout=timeout,
        modular=modular,
        validate=validate,
    ))


# =============================================================================
# Convenience Wrappers (Extensible Tool Layer)
# =============================================================================
# These wrappers provide a clean interface for common operations.
# They can be swapped out for MCP tools or other implementations later.


async def read_file(path: str, max_turns: int = 0) -> str:
    """Read a file and return its contents.

    Args:
        path: Path to the file to read
        max_turns: Maximum turns for Claude (default: 3)

    Returns:
        File contents as string

    Example:
        content = await read_file("pyproject.toml")
    """
    result = await run_claude(
        task=f"Read the file at {path} and return its complete contents verbatim. Output ONLY the raw file contents.",
        tools=["Read"],
        max_turns=max_turns,
    )
    # Extract the result text from the JSON response
    # Claude Code CLI returns: {"type": "result", "result": "...", ...}
    if isinstance(result, dict):
        return str(result.get("result", ""))
    return str(result)


async def write_file(path: str, content: str, max_turns: int = 0) -> str:
    """Write content to a file.

    Args:
        path: Path to the file to write
        content: Content to write to the file
        max_turns: Maximum turns for Claude (default: 3)

    Returns:
        Confirmation message

    Example:
        await write_file("hello.py", "print('hello world')")
    """
    # Escape content for safe passing
    escaped_content = content.replace('"""', '\\"\\"\\"')
    result = await run_claude(
        task=f'Create the file {path} with exactly this content:\n{escaped_content}',
        tools=["Write"],
        max_turns=max_turns,
    )
    if isinstance(result, dict):
        return str(result.get("result", "File written"))
    return str(result)


async def edit_file(path: str, old_text: str, new_text: str, max_turns: int = 0) -> str:
    """Edit a file by replacing text.

    Args:
        path: Path to the file to edit
        old_text: Text to find and replace
        new_text: Text to replace with
        max_turns: Maximum turns for Claude (default: 4)

    Returns:
        Confirmation message

    Example:
        await edit_file("config.py", "DEBUG = True", "DEBUG = False")
    """
    result = await run_claude(
        task=f'Edit the file {path}. Find this exact text:\n{old_text}\n\nAnd replace it with:\n{new_text}',
        tools=["Edit", "Read"],
        max_turns=max_turns,
    )
    if isinstance(result, dict):
        return str(result.get("result", "File edited"))
    return str(result)


async def run_bash(command: str, max_turns: int = 0) -> str:
    """Run a bash command and return output.

    Args:
        command: Bash command to execute
        max_turns: Maximum turns for Claude (default: 3)

    Returns:
        Command output

    Example:
        output = await run_bash("git status")
    """
    result = await run_claude(
        task=f"Run this bash command and return the output: {command}",
        tools=["Bash"],
        max_turns=max_turns,
    )
    if isinstance(result, dict):
        return str(result.get("result", ""))
    return str(result)


async def search_codebase(query: str, path: str = ".", max_turns: int = 0) -> str:
    """Search the codebase for a pattern.

    Args:
        query: Search query or pattern
        path: Path to search in (default: current directory)
        max_turns: Maximum turns for Claude (default: 3)

    Returns:
        Search results

    Example:
        results = await search_codebase("def run_claude", "scripts/")
    """
    result = await run_claude(
        task=f'Search for "{query}" in {path}. Return the matching files and relevant code snippets.',
        tools=["Grep", "Glob", "Read"],
        max_turns=max_turns,
    )
    if isinstance(result, dict):
        return str(result.get("result", ""))
    return str(result)


# For testing
if __name__ == "__main__":
    import sys

    async def test_basic():
        """Test basic execution."""
        print("Testing basic Claude Code execution...")
        result = await run_claude(
            task="What is 2+2? Return just the number.",
            tools=[],  # No file system access needed
            max_turns=1,
        )
        print(f"Result: {json.dumps(result, indent=2)}")

    async def test_file_read():
        """Test file reading."""
        print("\nTesting file read...")
        project_root = Path(__file__).parent.parent.parent.parent
        pyproject = project_root / "pyproject.toml"

        if pyproject.exists():
            result = await run_claude(
                task=f"Read {pyproject} and extract the project name from [project] section",
                tools=["Read"],
                max_turns=3,
            )
            print(f"Result: {json.dumps(result, indent=2)}")
        else:
            print(f"Skipping: {pyproject} not found")

    async def test_error_handling():
        """Test error handling."""
        print("\nTesting error handling...")
        try:
            result = await run_claude(
                task="Invalid task with no tools",
                tools=[],
                max_turns=1,
                timeout=5,
            )
            print(f"Result: {json.dumps(result, indent=2)}")
        except ClaudeExecutionError as e:
            print(f"Caught expected error: {e}")

    # Run tests
    try:
        asyncio.run(test_basic())
        asyncio.run(test_file_read())
        asyncio.run(test_error_handling())
        print("\n✓ All tests passed")
    except Exception as e:
        print(f"\n✗ Test failed: {e}", file=sys.stderr)
        sys.exit(1)

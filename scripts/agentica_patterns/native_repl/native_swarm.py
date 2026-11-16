#!/usr/bin/env python3
"""Native REPL Dependency Swarm.

A DependencySwarm that uses Claude Code CLI in the REPL scope for file operations.

This implements Approach 3 from RESEARCH.md:
- Agentica agents for orchestration
- Claude Code CLI for execution (file I/O, bash)
- Integration via scope functions (run_claude)

The key pattern: agents write Python code that calls `await run_claude()` to
delegate operations to Claude Code CLI running in a subprocess.

Usage:
    # Run example swarm
    uv run python -m runtime.harness scripts/agentica/native_repl/native_swarm.py

    # Run with custom tasks
    uv run python -m runtime.harness scripts/agentica/native_repl/native_swarm.py \\
        --task "Analyze Python files in scripts/" \\
        --task "Check pyproject.toml dependencies"
"""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Import Agentica spawn
try:
    from agentica import spawn
except ImportError:
    async def spawn(**kwargs):  # type: ignore
        """Stub spawn function for testing."""
        raise NotImplementedError("agentica not installed")

# Import DependencySwarm components
try:
    from scripts.agentica_patterns.coordination import CoordinationDB
    from scripts.agentica_patterns.dependency_swarm import DependencySwarm
except ImportError:
    print("Error: Cannot import DependencySwarm or CoordinationDB", file=sys.stderr)
    print("Make sure you're running from the project root", file=sys.stderr)
    sys.exit(1)

# Import run_claude wrapper
try:
    from scripts.agentica_patterns.native_repl.run_claude import (
        read_file,
        run_bash,
        run_claude,
        search_codebase,
        write_file,
    )
except ImportError:
    print("Error: Cannot import run_claude", file=sys.stderr)
    sys.exit(1)

if TYPE_CHECKING:
    pass


# =============================================================================
# Native REPL Swarm Configuration
# =============================================================================


class NativeSwarm:
    """DependencySwarm with Claude Code CLI in REPL scope.

    This swarm passes run_claude functions to agents so they can delegate
    file operations to Claude Code CLI while maintaining Agentica orchestration.

    Example agent REPL code:
        ```python
        # Read a file
        content = await run_claude("Read pyproject.toml", tools=["Read"])

        # Parse and analyze
        if "agentica" in content:
            return "Found agentica dependency"
        ```
    """

    def __init__(
        self,
        db: "CoordinationDB",
        model: str = "anthropic:claude-sonnet-4",
        fail_fast: bool = True,
        max_parallel: int = 3,
    ):
        """Initialize NativeSwarm.

        Args:
            db: CoordinationDB for tracking
            model: Model to use for agents
            fail_fast: Stop on first error
            max_parallel: Max tasks in parallel
        """
        self.db = db
        self.model = model

        # Build scope with Claude Code CLI wrappers
        self.scope = {
            # Main wrapper - agents can use this for custom operations
            "run_claude": run_claude,
            # Convenience wrappers for common operations
            "read_file": read_file,
            "write_file": write_file,
            "run_bash": run_bash,
            "search_codebase": search_codebase,
        }

        # Create DependencySwarm with native REPL scope
        self.swarm = DependencySwarm(
            db=db,
            model=model,
            scope=self.scope,
            fail_fast=fail_fast,
            max_parallel=max_parallel,
        )

    def add_task(
        self,
        name: str,
        premise: str,
        depends_on: list[str] | None = None,
    ) -> str:
        """Add a task to the swarm.

        The premise should instruct the agent to use the available scope
        functions (run_claude, read_file, etc.) for file operations.

        Args:
            name: Task name
            premise: Agent premise (should mention available tools)
            depends_on: Task dependencies

        Returns:
            Task ID
        """
        # Inject scope documentation into premise
        enhanced_premise = f"""{premise}

**Available Tools (in REPL scope):**
- `run_claude(task, tools=["Read"|"Write"|"Bash"|...])` - Execute Claude Code CLI
- `read_file(path)` - Read a file via Claude Code
- `write_file(path, content)` - Write a file via Claude Code
- `run_bash(command)` - Run bash command via Claude Code
- `search_codebase(query, pattern)` - Search codebase via Claude Code

**Important:** Use `await` when calling these functions in your REPL code.

Example:
```python
content = await read_file("pyproject.toml")
return "agentica" in content
```
"""

        return self.swarm.add_task(
            name=name,
            premise=enhanced_premise,
            depends_on=depends_on,
        )

    async def execute(self) -> dict[str, Any]:
        """Execute the task graph."""
        return await self.swarm.execute()


# =============================================================================
# Example Tasks
# =============================================================================


async def example_file_analysis_swarm() -> dict[str, Any]:
    """Example swarm that analyzes project files using Claude Code CLI.

    Demonstrates:
    1. Reading files via Claude Code
    2. Running bash commands via Claude Code
    3. Dependency coordination between tasks
    """
    db = CoordinationDB()
    swarm = NativeSwarm(db=db, max_parallel=2)

    # Task 1: Analyze project structure
    task1 = swarm.add_task(
        name="analyze_structure",
        premise="""Analyze the project structure.

Use `run_bash("ls -la scripts/agentica/")` to list files in scripts/agentica/.
Return a list of Python files found.""",
    )

    # Task 2: Check dependencies (depends on task1)
    task2 = swarm.add_task(
        name="check_dependencies",
        premise="""Check project dependencies.

Use `read_file("pyproject.toml")` to read the dependencies.
Return whether 'agentica' is listed as a dependency (True/False).""",
        depends_on=[task1],
    )

    # Task 3: Verify test files exist (depends on task1)
    task3 = swarm.add_task(
        name="verify_tests",
        premise="""Verify test files exist.

Use `search_codebase("test_agentica", pattern="*.py")` to find test files.
Return the number of test files found.""",
        depends_on=[task1],
    )

    # Task 4: Generate summary (depends on task2 and task3)
    swarm.add_task(
        name="generate_summary",
        premise="""Generate a summary report.

Based on dependency results, create a brief summary of the project state.
Return a markdown-formatted summary.""",
        depends_on=[task2, task3],
    )

    print("Executing native REPL swarm...", file=sys.stderr)
    results = await swarm.execute()

    return results


async def example_implementation_swarm() -> dict[str, Any]:
    """Example swarm that implements files using Claude Code CLI.

    Demonstrates:
    1. Writing files via Claude Code
    2. Sequential dependencies
    3. Verification steps
    """
    db = CoordinationDB()
    swarm = NativeSwarm(db=db, max_parallel=1)

    # Task 1: Create a test file
    task1 = swarm.add_task(
        name="create_test_file",
        premise="""Create a test Python file.

Use `write_file("workspace/test_native.py", content)` to create a file with:
- A simple function that returns "Hello from native REPL"
- A main block that calls the function

Return the path of the created file.""",
    )

    # Task 2: Verify file exists (depends on task1)
    task2 = swarm.add_task(
        name="verify_file",
        premise="""Verify the test file exists.

Use `read_file("workspace/test_native.py")` to read the file.
Return True if it contains "Hello from native REPL", False otherwise.""",
        depends_on=[task1],
    )

    # Task 3: Run the test file (depends on task2)
    swarm.add_task(
        name="run_test",
        premise="""Run the test file.

Use `run_bash("python workspace/test_native.py")` to execute it.
Return the output from the script.""",
        depends_on=[task2],
    )

    print("Executing implementation swarm...", file=sys.stderr)
    results = await swarm.execute()

    return results


async def example_research_swarm(topic: str) -> dict[str, Any]:
    """Example research swarm that gathers info using Claude Code.

    Args:
        topic: Research topic (e.g., "Python async patterns")

    Demonstrates:
    1. Using Claude Code for complex queries
    2. Parallel research branches
    3. Synthesis phase
    """
    db = CoordinationDB()
    swarm = NativeSwarm(db=db, max_parallel=2)

    # Task 1: Search codebase for relevant files
    task1 = swarm.add_task(
        name="search_codebase",
        premise=f"""Search the codebase for files related to: {topic}

Use `search_codebase("{topic}", pattern="*.py")` to find relevant files.
Return a list of file paths found.""",
    )

    # Task 2: Analyze found files (depends on task1)
    task2 = swarm.add_task(
        name="analyze_files",
        premise="""Analyze the files found in the search.

For each file path from the previous task, use `read_file(path)` to read it.
Identify key patterns and implementations.
Return a summary of findings.""",
        depends_on=[task1],
    )

    # Task 3: Check documentation (parallel to task2)
    task3 = swarm.add_task(
        name="check_docs",
        premise=f"""Check for documentation about: {topic}

Use `search_codebase("{topic}", pattern="*.md")` to find markdown docs.
Return a summary of documentation found.""",
        depends_on=[task1],
    )

    # Task 4: Synthesize findings (depends on task2 and task3)
    swarm.add_task(
        name="synthesize",
        premise="""Synthesize the research findings.

Based on code analysis and documentation, create a comprehensive summary.
Return a markdown report with:
- Key findings
- Implementation patterns
- Documentation references
""",
        depends_on=[task2, task3],
    )

    print(f"Researching: {topic}", file=sys.stderr)
    results = await swarm.execute()

    return results


# =============================================================================
# CLI Entry Point
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Native REPL Dependency Swarm - Claude Code CLI in Agentica scope",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run default file analysis example
  %(prog)s

  # Run implementation example
  %(prog)s --example implementation

  # Run research example
  %(prog)s --example research --topic "async patterns"

  # Custom task
  %(prog)s --task "Analyze pyproject.toml dependencies"
        """
    )

    parser.add_argument(
        "--example",
        choices=["analysis", "implementation", "research"],
        default="analysis",
        help="Which example swarm to run (default: analysis)"
    )
    parser.add_argument(
        "--topic",
        default="Agentica integration",
        help="Topic for research example (default: 'Agentica integration')"
    )
    parser.add_argument(
        "--task",
        action="append",
        help="Add custom task (can be specified multiple times)"
    )
    parser.add_argument(
        "--output",
        help="Output file for results (default: stdout)"
    )

    return parser.parse_args()


async def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Run selected example or custom tasks
    if args.task:
        # Custom tasks mode
        db = CoordinationDB()
        swarm = NativeSwarm(db=db)

        task_ids = []
        for i, task_premise in enumerate(args.task):
            task_id = swarm.add_task(
                name=f"task_{i+1}",
                premise=task_premise,
                depends_on=task_ids[-1:] if task_ids else None,  # Chain tasks
            )
            task_ids.append(task_id)

        results = await swarm.execute()

    elif args.example == "analysis":
        results = await example_file_analysis_swarm()

    elif args.example == "implementation":
        results = await example_implementation_swarm()

    elif args.example == "research":
        results = await example_research_swarm(args.topic)

    else:
        print(f"Unknown example: {args.example}", file=sys.stderr)
        sys.exit(1)

    # Output results
    import json
    output = json.dumps(results, indent=2, default=str)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Results saved to: {args.output}", file=sys.stderr)
    else:
        print("\n=== Results ===")
        print(output)


if __name__ == "__main__":
    asyncio.run(main())

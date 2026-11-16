#!/usr/bin/env python3
"""
Build Hierarchical Research Coordinator using Native REPL Swarm.

This script demonstrates Approach 3: Agentica agents with Claude Code CLI
in REPL scope. Agents write Python code that calls `await run_claude()`
to delegate file operations to Claude Code CLI subprocess.

USAGE:
    # Start servers first (see agentica-server skill)
    # Terminal 1: uv run python scripts/agentica/claude_proxy.py --port 8080
    # Terminal 2: cd workspace/agentica-research/agentica-server && \\
    #             INFERENCE_ENDPOINT_URL=http://localhost:8080/v1/chat/completions \\
    #             uv run agentica-server --port 2345

    # Then run this script:
    S_M_BASE_URL=http://localhost:2345 uv run --extra agentica \\
        python scripts/agentica/native_repl/build_research_coordinator_native.py

    # With tracking:
    S_M_BASE_URL=http://localhost:2345 uv run --extra agentica \\
        python scripts/agentica/native_repl/build_research_coordinator_native.py --track

ARCHITECTURE:
    NativeSwarm
        └─ Agent (REPL)
            └─ scope: {run_claude, read_file, write_file, run_bash, search_codebase}
                └─ claude -p subprocess with --session-id for correlation

This is Approach 3 from the three-approaches evaluation.
Compare with:
    - Approach 1: scripts/agentica/baseline/ (single Claude Task agent)
    - Approach 2: scripts/agentica/build_research_coordinator.py (DependencySwarm)
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.agentica_patterns.coordination import CoordinationDB
from scripts.agentica_patterns.native_repl.native_swarm import NativeSwarm


async def main():
    """Build Research Coordinator using NativeSwarm (Approach 3)."""
    parser = argparse.ArgumentParser(
        description="Build Hierarchical Research Coordinator using Native REPL Swarm",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--track",
        action="store_true",
        help="Enable CoordinationDB tracking for observability"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="anthropic:claude-sonnet-4.5",
        help="Model to use for agents (default: anthropic:claude-sonnet-4.5)"
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=True,
        help="Stop on first task failure (default: True)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for generated files (default: project root)"
    )
    args = parser.parse_args()

    # Check for Agentica server connection
    if not os.getenv("S_M_BASE_URL"):
        print("Error: S_M_BASE_URL environment variable not set")
        print("\nPlease set the Agentica server URL:")
        print("  export S_M_BASE_URL=http://localhost:2345")
        print("\nOr ensure servers are running (see --help for startup commands)")
        sys.exit(1)

    # Setup coordination DB
    db = None
    if args.track:
        db = CoordinationDB()
        print(f"Tracking enabled. Session: {db.session_id}")
    else:
        db = CoordinationDB(session_id="native-repl-build")
        print(f"Using minimal tracking. Session: {db.session_id}")

    print("=" * 70)
    print("Building Hierarchical Research Coordinator with Native REPL Swarm")
    print("(Approach 3: Agents use Claude Code CLI via REPL scope)")
    print("=" * 70)

    # Get project paths
    project_root = Path(__file__).parent.parent.parent.parent
    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = project_root

    plan_path = project_root / "thoughts/shared/plans/2025-12-26-hierarchical-research.md"

    # Output to separate location to avoid conflicts with Approach 2
    impl_path = output_dir / "scripts/agentica/native_repl/research_coordinator_native.py"
    test_path = output_dir / "tests/unit/test_research_coordinator_native.py"

    # Ensure parent directories exist
    impl_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.parent.mkdir(parents=True, exist_ok=True)

    # Create NativeSwarm with Claude Code CLI in scope
    swarm = NativeSwarm(
        db=db,
        model=args.model,
        fail_fast=args.fail_fast,
        max_parallel=1,  # Sequential to avoid race conditions with subprocesses
    )

    print("\nDefining tasks...")
    print("-" * 70)
    print("Note: Agents will use `await run_claude()` for file operations")
    print("-" * 70)

    # Task 1: Read the plan using Claude Code CLI
    task_read_plan = swarm.add_task(
        name="read_plan",
        premise=f"""Read the implementation plan for the Hierarchical Research Coordinator.

Plan location: {plan_path}

Use `await read_file("{plan_path}")` to read the plan.

Extract and return a summary of:
1. What needs to be implemented
2. Key data models (ResearchSection, ResearchFindings, ResearchDocument)
3. Key classes (ResearchCoordinator)
4. MCP tool wrappers needed
5. Success criteria

Return a concise summary (500 words max) that can guide the implementation.

IMPORTANT: Use the `read_file` function from your scope. Do NOT try to access files directly.""",
    )
    print(f"  Task 1: read_plan [{task_read_plan}]")

    # Task 2: Write tests (depends on plan understanding)
    task_write_tests = swarm.add_task(
        name="write_tests",
        premise=f"""Write comprehensive unit tests for the Hierarchical Research Coordinator.

Test file location: {test_path}

Based on the plan summary from the previous task, create tests for:
1. ResearchSection dataclass (to_dict)
2. ResearchFindings dataclass (to_markdown)
3. ResearchDocument dataclass (to_markdown)
4. ResearchCoordinator.decompose() (JSON parsing, fallback)
5. ResearchCoordinator.research_sections() (parallel execution)
6. ResearchCoordinator tracking with CoordinationDB

Use pytest and asyncio. Mock external dependencies (MCP tools, agents).
Include proper imports and fixtures.

Write the COMPLETE test file using:
```python
content = '''... your complete test file content ...'''
result = await write_file("{test_path}", content)
return result
```

Do NOT use placeholders or TODOs. Write the full implementation.""",
        depends_on=[task_read_plan],
    )
    print(f"  Task 2: write_tests [{task_write_tests}] (depends on: read_plan)")

    # Task 3: Implement research coordinator (depends on plan and tests)
    task_implement = swarm.add_task(
        name="implement_coordinator",
        premise=f"""Implement the Hierarchical Research Coordinator.

Implementation file location: {impl_path}

Based on the plan and the tests written, implement:

1. Data models (ResearchSection, ResearchFindings, ResearchDocument)
2. MCP tool wrappers (call_perplexity_sync, call_nia_sync, wrapper functions)
3. ResearchCoordinator class with methods:
   - __init__ (setup with optional CoordinationDB)
   - decompose() (LLM decomposes topic into sections)
   - _research_section() (specialist researches one section)
   - research_sections() (parallel research)
   - synthesize() (coordinator synthesizes findings)
   - research() (full workflow)
4. CLI entry point with argparse

Follow the plan EXACTLY. Include:
- Proper imports
- Complete docstrings
- Error handling (JSON parse failures, timeouts)
- Proper async/await
- CoordinationDB integration via tracked_spawn

Write the COMPLETE implementation using:
```python
content = '''... your complete implementation ...'''
result = await write_file("{impl_path}", content)
return result
```

Do NOT use placeholders or TODOs. The implementation MUST pass the tests.""",
        depends_on=[task_read_plan, task_write_tests],
    )
    print(f"  Task 3: implement_coordinator [{task_implement}] (depends on: read_plan, write_tests)")

    # Task 4: Run tests (depends on implementation)
    task_run_tests = swarm.add_task(
        name="run_tests",
        premise=f"""Run the unit tests to verify the implementation.

Use:
```python
result = await run_bash("uv run pytest {test_path} -v --tb=short")
return result
```

If tests fail:
1. Read the failure output carefully
2. Identify the root cause
3. Report what needs to be fixed

Return:
- Test results (passed/failed counts)
- Any failure details
- Recommendations for fixes if needed

Note: This is verification only. Do NOT fix code - just report status.""",
        depends_on=[task_implement],
    )
    print(f"  Task 4: run_tests [{task_run_tests}] (depends on: implement_coordinator)")

    print("\nValidating task graph...")
    try:
        swarm.swarm.graph.validate()
        print("  Graph validation passed (no cycles, all dependencies valid)")
    except ValueError as e:
        print(f"  Graph validation failed: {e}")
        sys.exit(1)

    print("\nExecuting tasks...")
    print("=" * 70)
    print("NOTE: Each task spawns Claude Code CLI subprocess with --session-id")
    print("      Monitor via Braintrust: filter by 'subprocess-*' session IDs")
    print("=" * 70)

    try:
        results = await swarm.execute()

        print("\n" + "=" * 70)
        print("Build Results (Native REPL Approach)")
        print("=" * 70)

        for task_name, result in results.items():
            print(f"\n{task_name}:")
            print("-" * 70)
            # Truncate long results
            result_str = str(result)
            if len(result_str) > 500:
                print(result_str[:500] + f"... ({len(result_str)} chars total)")
            else:
                print(result_str)

        # Show tracking summary if enabled
        if args.track and db:
            print("\n" + "=" * 70)
            print("Coordination Summary")
            print("=" * 70)
            summary = db.get_session_summary()
            print(f"Agents spawned: {sum(summary['agents_by_status'].values())}")
            print(f"By status: {summary['agents_by_status']}")
            print(f"By pattern: {summary['agents_by_pattern']}")
            print(f"Tasks completed: {summary['total_tasks']}")

        # Check if all tasks completed
        all_completed = all(
            node.status == "completed"
            for node in swarm.swarm.graph.nodes.values()
        )

        if all_completed:
            print("\n" + "=" * 70)
            print("SUCCESS: All tasks completed!")
            print("=" * 70)
            print(f"\nGenerated files:")
            print(f"  Implementation: {impl_path}")
            print(f"  Tests: {test_path}")
            print("\nNext steps:")
            print(f"1. Review the generated code")
            print(f"2. Run: uv run pytest {test_path} -v")
            print(f"3. Compare with Approach 1 (baseline) and Approach 2 (DependencySwarm)")
        else:
            print("\n" + "=" * 70)
            print("PARTIAL: Some tasks failed")
            print("=" * 70)
            failed_tasks = [
                f"  - {node.name} ({node.id}): {node.error}"
                for node in swarm.swarm.graph.nodes.values()
                if node.status == "failed"
            ]
            for task in failed_tasks:
                print(task)
            sys.exit(1)

    except Exception as e:
        print(f"\nBuild failed: {e}")
        import traceback
        traceback.print_exc()
        if db:
            print(f"Check coordination DB for details: {db.db_path}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""
Build Hierarchical Research Coordinator using DependencySwarm.

This script demonstrates using DependencySwarm to orchestrate building a complex
multi-agent system with proper dependency management.

USAGE:
    # Basic usage (uses Anthropic API directly)
    uv run --extra agentica python scripts/agentica/build_research_coordinator.py

    # With tracking/observability
    uv run --extra agentica python scripts/agentica/build_research_coordinator.py --track

    # Using specific model
    uv run --extra agentica python scripts/agentica/build_research_coordinator.py --model anthropic:claude-sonnet-4-5

REQUIREMENTS:
    - ANTHROPIC_API_KEY environment variable set
    - uv sync --extra agentica

The swarm will:
1. Read the implementation plan
2. Write unit tests (depends on plan)
3. Implement the research coordinator (depends on plan and tests)
4. Run the tests to verify implementation (depends on implementation)

Each task is executed by a separate agent, with proper dependency tracking.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.agentica_patterns.coordination import CoordinationDB
from scripts.agentica_patterns.dependency_swarm import DependencySwarm


async def main():
    """Build Research Coordinator using DependencySwarm."""
    parser = argparse.ArgumentParser(
        description="Build Hierarchical Research Coordinator using DependencySwarm",
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
    args = parser.parse_args()

    # Check for Agentica server connection
    if not os.getenv("S_M_BASE_URL"):
        print("Error: S_M_BASE_URL environment variable not set")
        print("\nPlease set the Agentica server URL:")
        print("  export S_M_BASE_URL=http://localhost:2345")
        sys.exit(1)

    # Setup coordination DB if tracking enabled
    db = None
    if args.track:
        db = CoordinationDB()
        print(f"Tracking enabled. Session: {db.session_id}")
    else:
        # Always need DB for DependencySwarm (even without full tracking)
        db = CoordinationDB(session_id="build-research-coordinator")
        print(f"Using minimal tracking. Session: {db.session_id}")

    print("=" * 70)
    print("Building Hierarchical Research Coordinator with DependencySwarm")
    print("=" * 70)

    # Get project paths
    project_root = Path(__file__).parent.parent.parent
    plan_path = project_root / "thoughts/shared/plans/2025-12-26-hierarchical-research.md"
    impl_path = project_root / "scripts/agentica/research_coordinator.py"
    test_path = project_root / "tests/unit/test_research_coordinator.py"

    # Create DependencySwarm
    swarm = DependencySwarm(
        db=db,
        model=args.model,
        fail_fast=args.fail_fast,
        max_parallel=2,  # Limit parallel execution for Claude proxy
        bundle="implementation",  # Use implementation bundle
    )

    print("\nDefining tasks...")
    print("-" * 70)

    # Task 1: Read the plan
    task_read_plan = swarm.add_task(
        name="read_plan",
        premise=f"""Read the implementation plan for the Hierarchical Research Coordinator.

Plan location: {plan_path}

Extract and return a summary of:
1. What needs to be implemented
2. Key data models (ResearchSection, ResearchFindings, ResearchDocument)
3. Key classes (ResearchCoordinator)
4. MCP tool wrappers needed
5. Success criteria

Return a concise summary (500 words max) that can guide the implementation.""",
    )
    print(f"✓ Task 1: read_plan [{task_read_plan}]")

    # Task 2: Write tests (depends on plan understanding)
    task_write_tests = swarm.add_task(
        name="write_tests",
        premise=f"""Write comprehensive unit tests for the Hierarchical Research Coordinator.

Test file: {test_path}

Based on the plan summary from the previous task, create tests for:
1. ResearchSection dataclass (to_dict)
2. ResearchFindings dataclass (to_markdown)
3. ResearchDocument dataclass (to_markdown)
4. ResearchCoordinator.decompose() (JSON parsing, fallback)
5. ResearchCoordinator.research_sections() (parallel execution)
6. ResearchCoordinator tracking with CoordinationDB

Use pytest and asyncio. Mock external dependencies (MCP tools, agents).
Include proper imports and fixtures.

Write the complete test file. Do NOT use placeholders or TODOs.""",
        file_path=str(test_path),
        depends_on=[task_read_plan],
    )
    print(f"✓ Task 2: write_tests [{task_write_tests}] (depends on: read_plan)")

    # Task 3: Implement research coordinator (depends on plan and tests)
    task_implement = swarm.add_task(
        name="implement_coordinator",
        premise=f"""Implement the Hierarchical Research Coordinator.

Implementation file: {impl_path}

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

Write the complete implementation. Do NOT use placeholders or TODOs.
The implementation MUST pass the tests written in the previous task.""",
        file_path=str(impl_path),
        depends_on=[task_read_plan, task_write_tests],
    )
    print(f"✓ Task 3: implement_coordinator [{task_implement}] (depends on: read_plan, write_tests)")

    # Task 4: Run tests (depends on implementation)
    task_run_tests = swarm.add_task(
        name="run_tests",
        premise=f"""Run the unit tests to verify the implementation.

Test command:
    uv run pytest {test_path} -v --tb=short

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
    print(f"✓ Task 4: run_tests [{task_run_tests}] (depends on: implement_coordinator)")

    print("\nValidating task graph...")
    try:
        swarm.graph.validate()
        print("✓ Graph validation passed (no cycles, all dependencies valid)")
    except ValueError as e:
        print(f"✗ Graph validation failed: {e}")
        sys.exit(1)

    print("\nExecuting tasks...")
    print("=" * 70)

    try:
        results = await swarm.execute()

        print("\n" + "=" * 70)
        print("Build Results")
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
            for node in swarm.graph.nodes.values()
        )

        if all_completed:
            print("\n✓ All tasks completed successfully!")
            print(f"\nImplementation: {impl_path}")
            print(f"Tests: {test_path}")
            print("\nNext steps:")
            print("1. Review the generated code")
            print("2. Run: uv run pytest tests/unit/test_research_coordinator.py -v")
            print("3. Try: uv run python scripts/agentica/research_coordinator.py --help")
        else:
            print("\n✗ Some tasks failed. Check results above.")
            failed_tasks = [
                f"{node.name} ({node.id}): {node.error}"
                for node in swarm.graph.nodes.values()
                if node.status == "failed"
            ]
            for task in failed_tasks:
                print(f"  - {task}")
            sys.exit(1)

    except Exception as e:
        print(f"\n✗ Build failed: {e}")
        if db:
            print(f"Check coordination DB for details: {db.db_path}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

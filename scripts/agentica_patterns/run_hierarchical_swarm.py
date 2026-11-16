#!/usr/bin/env python3
"""Run Dependency Swarm to Implement Hierarchical Research Coordinator.

Uses the DependencySwarm to implement Phases 2-5 of the Hierarchical Research plan
through Agentica, which routes through the Claude proxy.

USAGE:
    # Ensure both servers are running:
    # Terminal 1: uv run python scripts/agentica/claude_proxy.py --port 8080
    # Terminal 2: INFERENCE_ENDPOINT_URL=http://localhost:8080/v1/chat/completions \
    #             uv run agentica-server (from agentica-server dir)

    # Run this script:
    S_M_BASE_URL=http://localhost:2345 uv run python scripts/agentica/run_hierarchical_swarm.py

REQUIRES:
    - agentica-server running on port 2345
    - claude_proxy running on port 8080
    - S_M_BASE_URL=http://localhost:2345
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure we can import from scripts/agentica
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.agentica_patterns.coordination import CoordinationDB
from scripts.agentica_patterns.dependency_swarm import DependencySwarm


# Read the plan for context
PLAN_PATH = Path(__file__).parent.parent.parent / "thoughts/shared/plans/2025-12-26-hierarchical-research.md"

# Phases 2-5 premises (Phase 1 data models already done)
PHASE_2_PREMISE = """You are implementing Phase 2: MCP Tool Wrappers for the Hierarchical Research Coordinator.

The plan location: thoughts/shared/plans/2025-12-26-hierarchical-research.md

Your task is to append to scripts/agentica/research_coordinator.py the following:
1. Import asyncio, json, subprocess, Path
2. _get_project_dir() helper function
3. call_perplexity_sync(query, mode) - subprocess wrapper for perplexity_search.py
4. call_nia_sync(package, query, registry) - subprocess wrapper for nia_docs.py
5. perplexity_research(query) - agent-callable wrapper
6. perplexity_deep(query) - agent-callable wrapper for deep research
7. library_docs(package, query) - agent-callable wrapper for Nia

Read the plan Phase 2 section for exact code. Append to the existing file.
Return a summary of what you added.
"""

PHASE_3_PREMISE = """You are implementing Phase 3: ResearchCoordinator Class for the Hierarchical Research Coordinator.

Dependency completed: Phase 2 MCP Tool Wrappers are now available in research_coordinator.py

The plan location: thoughts/shared/plans/2025-12-26-hierarchical-research.md

Your task is to append to scripts/agentica/research_coordinator.py:
1. Import from coordination and tracked_agent modules
2. Import spawn from agentica (with fallback)
3. ResearchCoordinator class with:
   - COORDINATOR_PREMISE and SPECIALIST_PREMISE constants
   - __init__ method with topic, depth, max_sections, model, db params
   - _spawn_coordinator() method
   - decompose() method - LLM-driven topic decomposition
   - _research_section() method - specialist research
   - research_sections() method - parallel execution
   - synthesize() method - final document creation
   - research() method - full workflow

Read the plan Phase 3 section for exact code. Append to the existing file.
Return a summary of what you added.
"""

PHASE_4_PREMISE = """You are implementing Phase 4: CLI and Tests for the Hierarchical Research Coordinator.

Dependencies completed: Phase 2 (MCP wrappers) and Phase 3 (ResearchCoordinator class) are done.

The plan location: thoughts/shared/plans/2025-12-26-hierarchical-research.md

Your tasks:
1. Append CLI entry point (main function with argparse) to scripts/agentica/research_coordinator.py
2. Create tests/unit/test_research_coordinator.py with:
   - TestResearchSection class
   - TestResearchFindings class
   - TestResearchDocument class
   - TestResearchCoordinator class with async tests

Read the plan Phase 4 section for exact code.
Return a summary of files created/modified.
"""

PHASE_5_PREMISE = """You are implementing Phase 5: Example Script and Documentation.

All previous phases are complete. The ResearchCoordinator is now fully functional.

The plan location: thoughts/shared/plans/2025-12-26-hierarchical-research.md

Your tasks:
1. Create scripts/agentica/examples/ directory
2. Create scripts/agentica/examples/__init__.py (empty)
3. Create scripts/agentica/examples/research_example.py with full example

Read the plan Phase 5 section for exact code.
Return a summary of files created.
"""


async def main():
    """Run the dependency swarm to implement Hierarchical Research."""

    # Check S_M_BASE_URL is set
    sm_url = os.getenv("S_M_BASE_URL")
    if not sm_url:
        print("ERROR: S_M_BASE_URL not set")
        print("Run: S_M_BASE_URL=http://localhost:2345 uv run python scripts/agentica/run_hierarchical_swarm.py")
        sys.exit(1)

    print(f"Using Agentica server at: {sm_url}")
    print("=" * 60)

    # Verify servers are up
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            # Check Claude proxy
            r = await client.get("http://localhost:8080/health")
            print(f"Claude proxy: {r.json()}")

            # Check Agentica server
            r = await client.get(f"{sm_url}/health")
            print(f"Agentica server: {r.json()}")
    except Exception as e:
        print(f"ERROR: Server health check failed: {e}")
        print("Ensure both servers are running.")
        sys.exit(1)

    print("=" * 60)

    # Create CoordinationDB for tracking
    db = CoordinationDB()
    print(f"Coordination session: {db.session_id}")

    # Create swarm
    swarm = DependencySwarm(
        db=db,
        model="anthropic:claude-sonnet-4",  # Will route through our proxy
        fail_fast=True,
        # No bundle - keep it simple for testing
    )

    # Add tasks with dependencies
    print("\nAdding tasks to swarm...")

    phase2_id = swarm.add_task(
        name="phase2_mcp_wrappers",
        premise=PHASE_2_PREMISE,
        file_path="scripts/agentica/research_coordinator.py",
    )
    print(f"  Phase 2: {phase2_id}")

    phase3_id = swarm.add_task(
        name="phase3_coordinator_class",
        premise=PHASE_3_PREMISE,
        file_path="scripts/agentica/research_coordinator.py",
        depends_on=[phase2_id],
    )
    print(f"  Phase 3: {phase3_id} (depends on Phase 2)")

    phase4_id = swarm.add_task(
        name="phase4_cli_tests",
        premise=PHASE_4_PREMISE,
        depends_on=[phase3_id],
    )
    print(f"  Phase 4: {phase4_id} (depends on Phase 3)")

    phase5_id = swarm.add_task(
        name="phase5_example",
        premise=PHASE_5_PREMISE,
        depends_on=[phase4_id],
    )
    print(f"  Phase 5: {phase5_id} (depends on Phase 4)")

    print("\n" + "=" * 60)
    print("Executing swarm...")
    print("=" * 60 + "\n")

    try:
        results = await swarm.execute()

        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)

        for name, result in results.items():
            print(f"\n{name}:")
            print("-" * 40)
            # Truncate long results
            result_str = str(result)
            if len(result_str) > 500:
                result_str = result_str[:500] + "..."
            print(result_str)

        # Print coordination summary
        print("\n" + "=" * 60)
        print("COORDINATION SUMMARY")
        print("=" * 60)
        summary = db.get_session_summary()
        print(f"Agents: {summary['agents_by_status']}")
        print(f"Patterns: {summary['agents_by_pattern']}")
        print(f"Total tasks: {summary['total_tasks']}")

    except Exception as e:
        print(f"\nERROR: Swarm execution failed: {e}")
        import traceback
        traceback.print_exc()

        # Still print what we have
        print("\n" + "=" * 60)
        print("PARTIAL RESULTS")
        print("=" * 60)
        for task_id, node in swarm.graph.nodes.items():
            print(f"  {node.name}: {node.status}")
            if node.error:
                print(f"    Error: {node.error}")

        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

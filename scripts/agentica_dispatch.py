#!/usr/bin/env python3
"""Agentica Task Dispatcher - Route tasks to Agentica instead of Task tool.

USAGE:
    # Basic task
    uv run python scripts/agentica_dispatch.py --prompt "Research authentication patterns"

    # With pattern hint
    uv run python scripts/agentica_dispatch.py --prompt "Implement feature X" --pattern hierarchical

    # With session ID
    uv run python scripts/agentica_dispatch.py --prompt "Debug issue Y" --session-id abc123

This script is the bridge between Claude Code and Agentica. Instead of using
the Task tool, Claude should call this script via Bash.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def dispatch(prompt: str, pattern: str | None, session_id: str) -> dict:
    """Dispatch a task to Agentica via orchestrate_with_gates."""
    from scripts.agentica_patterns.unified_gate import (
        orchestrate_with_gates,
        ClarificationRequired,
        ResourcesInsufficient,
        CompositionInvalid,
    )

    try:
        result = await orchestrate_with_gates(
            prompt=prompt,
            session_id=session_id,
            pattern_hint=pattern,
        )
        return {
            "success": result.get("success", False),
            "pattern_used": result.get("pattern_used"),
            "output": result.get("aggregated_output"),
            "errors": result.get("errors", []),
            "duration_ms": result.get("total_duration_ms"),
        }

    except ClarificationRequired as e:
        return {
            "success": False,
            "error_type": "clarification_required",
            "unknowns": e.unknowns,
            "message": f"Task needs clarification. Unknown items: {', '.join(e.unknowns)}",
        }

    except ResourcesInsufficient as e:
        return {
            "success": False,
            "error_type": "resources_insufficient",
            "bottleneck": e.bottleneck,
            "suggestion": e.suggestion,
            "message": f"Insufficient resources: {e.bottleneck}. {e.suggestion}",
        }

    except CompositionInvalid as e:
        return {
            "success": False,
            "error_type": "composition_invalid",
            "errors": e.errors,
            "message": f"Invalid pattern composition: {'; '.join(e.errors)}",
        }

    except Exception as e:
        return {
            "success": False,
            "error_type": "execution_error",
            "message": str(e),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Dispatch tasks to Agentica instead of Task tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Research task (auto-detects swarm pattern)
    %(prog)s --prompt "Research best practices for error handling"

    # Implementation task (auto-detects hierarchical pattern)
    %(prog)s --prompt "Implement user authentication with JWT"

    # Explicit pattern
    %(prog)s --prompt "Review these 5 PRs" --pattern jury

Patterns: swarm, hierarchical, pipeline, jury, map_reduce, generator_critic
        """,
    )

    parser.add_argument(
        "--prompt",
        required=True,
        help="The task description/prompt to execute",
    )

    parser.add_argument(
        "--pattern",
        choices=["swarm", "hierarchical", "pipeline", "jury", "map_reduce", "generator_critic"],
        help="Pattern hint (optional - auto-detected if not provided)",
    )

    parser.add_argument(
        "--session-id",
        default=os.environ.get("CLAUDE_SESSION_ID", "default"),
        help="Session ID for tracking (default: from CLAUDE_SESSION_ID or 'default')",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON (default: human-readable)",
    )

    args = parser.parse_args()

    # Run the dispatch
    result = asyncio.run(dispatch(args.prompt, args.pattern, args.session_id))

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # Human-readable output
        if result.get("success"):
            print(f"✓ Task completed via {result.get('pattern_used', 'unknown')} pattern")
            print(f"  Duration: {result.get('duration_ms', 0):.0f}ms")
            print()
            if result.get("output"):
                print("Output:")
                print(result["output"])
        else:
            print(f"✗ Task failed: {result.get('message', 'Unknown error')}")
            if result.get("unknowns"):
                print(f"  Needs clarification: {', '.join(result['unknowns'])}")
            if result.get("errors"):
                for err in result["errors"]:
                    print(f"  - {err}")

    # Exit with error code if failed
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    main()

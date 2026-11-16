#!/usr/bin/env python3
"""Flywheel CLI Entry Point (Phase 3 Task 3.10).

USAGE:
    uv run python scripts/run_flywheel.py --skill deploy-api --prompt "Deploy to AWS"

    # Dry-run mode (no persistence)
    uv run python scripts/run_flywheel.py --skill deploy-api --prompt "Deploy to AWS" --dry-run

    # With persistence
    uv run python scripts/run_flywheel.py --skill deploy-api --prompt "Deploy to AWS" --persist

    # Analyze corrections for a skill
    uv run python scripts/run_flywheel.py --skill deploy-api --analyze-corrections

    # List shared patterns
    uv run python scripts/run_flywheel.py --list-patterns

The flywheel CLI provides manual testing and execution of the skill flywheel.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Skill Flywheel CLI - continuous learning for Claude Code skills"
    )

    parser.add_argument(
        "--skill",
        type=str,
        help="Path to skill directory or SKILL.md file"
    )

    parser.add_argument(
        "--prompt",
        type=str,
        default="",
        help="User prompt that triggered the skill"
    )

    parser.add_argument(
        "--persist",
        action="store_true",
        help="Persist changes to SKILL.md"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without persisting (default if --persist not specified)"
    )

    parser.add_argument(
        "--analyze-corrections",
        action="store_true",
        help="Analyze corrections for the skill and show suggestions"
    )

    parser.add_argument(
        "--list-patterns",
        action="store_true",
        help="List all shared patterns in the registry"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    return parser.parse_args()


async def run_flywheel_command(
    skill_path: str,
    prompt: str,
    persist: bool
) -> dict:
    """Run the flywheel on a skill."""
    from scripts.skill_flywheel import run_flywheel

    result = await run_flywheel(skill_path, prompt, persist=persist)

    return {
        "success": result.success,
        "converted": result.converted,
        "reason": result.reason,
        "parity_score": result.parity_score,
        "backup_path": result.backup_path,
        "diff": result.diff
    }


def analyze_corrections_command(skill_path: str) -> dict:
    """Analyze corrections for a skill."""
    from scripts.skill_feedback import load_corrections
    from scripts.skill_pattern_analyzer import (
        analyze_corrections,
        identify_weak_patterns
    )

    # Get skill_id from path
    path = Path(skill_path)
    if path.is_dir():
        skill_id = path.name
    else:
        skill_id = path.parent.name

    corrections = load_corrections(skill_id)
    weak = identify_weak_patterns(corrections)
    suggestions = analyze_corrections(corrections)

    return {
        "skill_id": skill_id,
        "correction_count": len(corrections),
        "weak_patterns": weak,
        "suggestions": suggestions
    }


def list_patterns_command() -> dict:
    """List all shared patterns."""
    from scripts.skill_pattern_registry import (
        get_default_registry,
        lookup_patterns_by_domain
    )

    registry = get_default_registry()

    # Get patterns by domain
    domains = set(p["domain"] for p in registry.patterns.values())

    result = {}
    for domain in sorted(domains):
        patterns = lookup_patterns_by_domain(registry, domain)
        result[domain] = [
            {"name": p["name"], "description": p["description"]}
            for p in patterns
        ]

    return result


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # List patterns mode
    if args.list_patterns:
        result = list_patterns_command()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("Shared Patterns:")
            for domain, patterns in result.items():
                print(f"\n  {domain}:")
                for p in patterns:
                    print(f"    - {p['name']}: {p['description']}")
        return 0

    # Require --skill for other modes
    if not args.skill:
        print("Error: --skill is required", file=sys.stderr)
        return 1

    # Analyze corrections mode
    if args.analyze_corrections:
        result = analyze_corrections_command(args.skill)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Corrections for {result['skill_id']}:")
            print(f"  Total: {result['correction_count']}")
            print(f"  Weak patterns: {result['weak_patterns']}")
            if result['suggestions']:
                print("  Suggestions:")
                for s in result['suggestions']:
                    print(f"    - {s['param']}: {s.get('pattern', 'N/A')}")
        return 0

    # Run flywheel mode
    persist = args.persist and not args.dry_run

    try:
        result = asyncio.run(run_flywheel_command(args.skill, args.prompt, persist))
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Flywheel Result:")
        print(f"  Success: {result['success']}")
        print(f"  Converted: {result['converted']}")
        print(f"  Reason: {result['reason']}")
        if result['parity_score']:
            print(f"  Parity: {result['parity_score']:.1%}")
        if result['backup_path']:
            print(f"  Backup: {result['backup_path']}")
        if result['diff']:
            print(f"\nDiff:\n{result['diff']}")

    return 0 if result['success'] else 1


if __name__ == "__main__":
    sys.exit(main())

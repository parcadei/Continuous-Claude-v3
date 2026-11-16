#!/usr/bin/env python3
"""Extract all CLI subcommands from math scripts.

USAGE:
    uv run python scripts/audit_math_commands.py
    uv run python scripts/audit_math_commands.py --json
    uv run python scripts/audit_math_commands.py --compare  # Compare with math_router.py routes
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path

# Math scripts to audit
MATH_SCRIPTS = [
    "scripts/sympy_compute.py",
    "scripts/numpy_compute.py",
    "scripts/scipy_compute.py",
    "scripts/mpmath_compute.py",
    "scripts/pint_compute.py",
    "scripts/shapely_compute.py",
    "scripts/z3_solve.py",
    "scripts/math_scratchpad.py",
    "scripts/math_tutor.py",
    "scripts/math_plot.py",
]


def extract_add_parser_commands(filepath: str) -> list[dict]:
    """Extract commands from add_parser() calls using AST."""
    commands = []
    try:
        with open(filepath, "r") as f:
            content = f.read()

        # Use regex to find add_parser calls since AST can be complex
        # Pattern: subparsers.add_parser("command" or add_parser('command'
        pattern = r'subparsers\.add_parser\s*\(\s*["\']([^"\']+)["\']'
        matches = re.findall(pattern, content)

        for cmd in matches:
            commands.append({
                "name": cmd,
                "source": "add_parser",
            })
    except Exception as e:
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)

    return commands


def extract_math_command_decorators(filepath: str) -> list[dict]:
    """Extract commands from @math_command decorators."""
    commands = []
    try:
        with open(filepath, "r") as f:
            content = f.read()

        # Pattern 1: @math_command(\n    name="command_name" or name='command_name'
        pattern1 = r'@math_command\s*\([^)]*name\s*=\s*["\']([^"\']+)["\']'
        matches = re.findall(pattern1, content, re.DOTALL)

        for cmd in matches:
            commands.append({
                "name": cmd,
                "source": "math_command",
            })

        # Pattern 2: def cmd_XXX functions (the function name after cmd_)
        pattern2 = r'def cmd_([a-zA-Z0-9_]+)\s*\('
        fn_matches = re.findall(pattern2, content)

        # Create a set of already found commands
        found_names = {c["name"] for c in commands}

        for fn_name in fn_matches:
            # Convert function name to command name (e.g., cmd_mp_sqrt -> mp_sqrt)
            cmd_name = fn_name
            if cmd_name not in found_names:
                commands.append({
                    "name": cmd_name,
                    "source": "cmd_function",
                })
                found_names.add(cmd_name)
    except Exception as e:
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)

    return commands


def extract_subcommands(filepath: str) -> list[dict]:
    """Extract all subcommands from a script using multiple methods."""
    # Check if file uses @math_command decorator pattern
    with open(filepath, "r") as f:
        content = f.read()

    uses_math_command = "@math_command" in content
    uses_add_parser = "add_parser" in content

    commands = []

    if uses_math_command:
        commands.extend(extract_math_command_decorators(filepath))

    if uses_add_parser:
        commands.extend(extract_add_parser_commands(filepath))

    # Deduplicate by name
    seen = set()
    unique_commands = []
    for cmd in commands:
        if cmd["name"] not in seen:
            seen.add(cmd["name"])
            unique_commands.append(cmd)

    return unique_commands


def extract_router_routes(router_path: str) -> dict[str, set[str]]:
    """Extract existing routes from math_router.py.

    This now imports the ROUTES list directly to capture both
    hand-crafted and dynamically generated routes.
    """
    routes_by_script: dict[str, set[str]] = {}
    try:
        # Try to import math_router module directly
        from scripts import math_router
        for r in math_router.ROUTES:
            if r.script not in routes_by_script:
                routes_by_script[r.script] = set()
            routes_by_script[r.script].add(r.subcommand)
        return routes_by_script
    except ImportError:
        pass  # Fall back to sibling import

    try:
        # Try sibling import (when run from scripts/)
        import math_router  # type: ignore
        for r in math_router.ROUTES:
            if r.script not in routes_by_script:
                routes_by_script[r.script] = set()
            routes_by_script[r.script].add(r.subcommand)
        return routes_by_script
    except ImportError:
        pass  # Fall back to static parsing

    # Fallback: parse statically (won't capture dynamic routes)
    try:
        with open(router_path, "r") as f:
            content = f.read()

        # Pattern: subcommand="command_name"
        # Combined with script="script_name.py"

        # Find Route definitions
        route_pattern = r'Route\s*\([^)]*script\s*=\s*["\']([^"\']+)["\'][^)]*subcommand\s*=\s*["\']([^"\']+)["\']'
        matches = re.findall(route_pattern, content, re.DOTALL)

        for script, subcommand in matches:
            if script not in routes_by_script:
                routes_by_script[script] = set()
            routes_by_script[script].add(subcommand)

        # Also try reverse order
        route_pattern2 = r'Route\s*\([^)]*subcommand\s*=\s*["\']([^"\']+)["\'][^)]*script\s*=\s*["\']([^"\']+)["\']'
        matches2 = re.findall(route_pattern2, content, re.DOTALL)

        for subcommand, script in matches2:
            if script not in routes_by_script:
                routes_by_script[script] = set()
            routes_by_script[script].add(subcommand)

    except Exception as e:
        print(f"Error parsing router: {e}", file=sys.stderr)

    return routes_by_script


def main():
    parser = argparse.ArgumentParser(description="Audit math script CLI subcommands")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--compare", action="store_true", help="Compare with existing routes in math_router.py")
    args = parser.parse_args()

    # Get the project root
    project_root = Path(__file__).parent.parent

    # Collect all commands
    all_commands = {}
    total_commands = 0

    for script in MATH_SCRIPTS:
        script_path = project_root / script
        if not script_path.exists():
            print(f"Warning: {script} not found", file=sys.stderr)
            continue

        commands = extract_subcommands(str(script_path))
        script_name = Path(script).name
        all_commands[script_name] = commands
        total_commands += len(commands)

    if args.compare:
        # Compare with router
        router_path = project_root / "scripts" / "math_router.py"
        existing_routes = extract_router_routes(str(router_path))

        comparison = {
            "total_commands_found": total_commands,
            "total_routes_found": sum(len(v) for v in existing_routes.values()),
            "scripts": {},
        }

        for script_name, commands in all_commands.items():
            script_routes = existing_routes.get(script_name, set())
            cmd_names = {c["name"] for c in commands}

            missing = cmd_names - script_routes
            extra = script_routes - cmd_names

            comparison["scripts"][script_name] = {
                "total_commands": len(commands),
                "routed_commands": len(script_routes),
                "missing_routes": sorted(list(missing)),
                "extra_routes": sorted(list(extra)),
                "coverage_percent": round(100 * len(script_routes & cmd_names) / len(cmd_names), 1) if cmd_names else 100.0,
            }

        if args.json:
            print(json.dumps(comparison, indent=2))
        else:
            print(f"\nMath Router Coverage Analysis")
            print(f"=" * 60)
            print(f"Total commands in scripts: {comparison['total_commands_found']}")
            print(f"Total routes in router:    {comparison['total_routes_found']}")
            print()

            for script_name, data in comparison["scripts"].items():
                missing_count = len(data["missing_routes"])
                print(f"\n{script_name}:")
                print(f"  Commands: {data['total_commands']}, Routed: {data['routed_commands']}, Coverage: {data['coverage_percent']}%")
                if missing_count > 0:
                    print(f"  Missing routes ({missing_count}):")
                    for cmd in data["missing_routes"][:20]:  # Limit output
                        print(f"    - {cmd}")
                    if missing_count > 20:
                        print(f"    ... and {missing_count - 20} more")
    else:
        if args.json:
            print(json.dumps(all_commands, indent=2))
        else:
            print(f"\nMath Script CLI Subcommands Audit")
            print(f"=" * 60)
            print(f"Total commands found: {total_commands}")

            for script_name, commands in all_commands.items():
                print(f"\n{script_name} ({len(commands)} commands):")
                for cmd in sorted(commands, key=lambda x: x["name"]):
                    print(f"  - {cmd['name']} [{cmd['source']}]")


if __name__ == "__main__":
    main()

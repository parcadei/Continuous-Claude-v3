#!/usr/bin/env python3
"""Extract command schemas from @math_command decorators.

USAGE:
    # Human-readable summary
    uv run python scripts/extract_command_schemas.py

    # Full JSON output
    uv run python scripts/extract_command_schemas.py --json

    # Statistics by argument type
    uv run python scripts/extract_command_schemas.py --stats

    # Process specific file(s)
    uv run python scripts/extract_command_schemas.py numpy_compute.py

Parses @math_command decorators from math scripts and extracts:
- name: command name
- category: command category
- description: command description
- args: full list of arguments with name, type, default, help, etc.
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# Default files to parse
DEFAULT_FILES = [
    "numpy_compute.py",
    "scipy_compute.py",
    "mpmath_compute.py",
]


def extract_value(node: ast.AST) -> Any:
    """Extract a Python value from an AST node.

    Handles:
    - Constants (str, int, float, bool, None)
    - Lists
    - Dicts
    - Names (e.g., int, str, float)
    """
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.Name):
        # For type references like int, str, float
        return node.id
    elif isinstance(node, ast.List):
        return [extract_value(elt) for elt in node.elts]
    elif isinstance(node, ast.Dict):
        result = {}
        for key, value in zip(node.keys, node.values):
            if key is not None:
                k = extract_value(key)
                v = extract_value(value)
                result[k] = v
        return result
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        # Handle negative numbers
        val = extract_value(node.operand)
        if isinstance(val, (int, float)):
            return -val
        return val
    elif isinstance(node, ast.Attribute):
        # Handle things like np.inf, argparse.REMAINDER
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))
    else:
        return f"<unsupported: {type(node).__name__}>"


def parse_decorator_args(call: ast.Call) -> Dict[str, Any]:
    """Parse arguments from a decorator call node.

    Returns dict with: name, category, description, latex_template, args
    """
    result = {
        "name": None,
        "category": None,
        "description": "",
        "latex_template": None,
        "args": []
    }

    # Parse keyword arguments
    for kw in call.keywords:
        key = kw.arg
        if key in result:
            result[key] = extract_value(kw.value)

    return result


def process_args_list(args: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process the args list from @math_command into structured format.

    Determines:
    - positional: True if name doesn't start with --
    - required: True if positional or no default specified
    - type: from 'type' key or defaults to 'str'
    """
    processed = []

    for arg in args:
        if not isinstance(arg, dict):
            continue

        name = arg.get("name", "")
        if not name:
            continue

        # Determine if positional or optional
        is_positional = not name.startswith("-")

        # Determine if required
        has_default = "default" in arg
        has_nargs = "nargs" in arg and arg["nargs"] in ["?", "*"]
        is_required = is_positional and not has_nargs

        # Get type
        arg_type = arg.get("type", "str")
        if isinstance(arg_type, type):
            arg_type = arg_type.__name__

        # Check for store_true/store_false actions
        action = arg.get("action")
        if action in ("store_true", "store_false"):
            arg_type = "bool"
            is_required = False

        processed_arg = {
            "name": name,
            "type": arg_type,
            "required": is_required,
            "positional": is_positional,
        }

        # Add optional fields if present
        if "default" in arg:
            processed_arg["default"] = arg["default"]
        if "dest" in arg:
            processed_arg["dest"] = arg["dest"]
        if "help" in arg:
            processed_arg["help"] = arg["help"]
        if "nargs" in arg:
            processed_arg["nargs"] = arg["nargs"]
        if action:
            processed_arg["action"] = action
        if "choices" in arg:
            processed_arg["choices"] = arg["choices"]

        processed.append(processed_arg)

    return processed


def extract_commands_from_file(filepath: Path) -> Dict[str, Dict[str, Any]]:
    """Extract all @math_command decorated functions from a file.

    Returns dict mapping command name to its schema.
    """
    commands = {}

    try:
        with open(filepath, "r") as f:
            source = f.read()
        tree = ast.parse(source)
    except (SyntaxError, FileNotFoundError) as e:
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)
        return commands

    # Walk through all function definitions
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue

        # Check decorators
        for decorator in node.decorator_list:
            # Look for @math_command(...) calls
            if not isinstance(decorator, ast.Call):
                continue

            # Check if it's math_command
            func = decorator.func
            if isinstance(func, ast.Name) and func.id == "math_command":
                # Parse decorator arguments
                dec_args = parse_decorator_args(decorator)

                if dec_args["name"]:
                    # Process args list
                    raw_args = dec_args.get("args", [])
                    processed_args = process_args_list(raw_args)

                    commands[dec_args["name"]] = {
                        "category": dec_args.get("category"),
                        "description": dec_args.get("description", ""),
                        "args": processed_args,
                    }

                    # Include latex_template if present
                    if dec_args.get("latex_template"):
                        commands[dec_args["name"]]["latex_template"] = dec_args["latex_template"]

    return commands


def extract_all_schemas(files: List[str], scripts_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Extract schemas from all specified files."""
    all_schemas = {}

    for filename in files:
        filepath = scripts_dir / filename
        if not filepath.exists():
            print(f"Warning: {filepath} not found", file=sys.stderr)
            continue

        commands = extract_commands_from_file(filepath)
        if commands:
            all_schemas[filename] = commands

    return all_schemas


def print_human_readable(schemas: Dict[str, Dict[str, Any]]) -> None:
    """Print schemas in human-readable format."""
    for filename, commands in sorted(schemas.items()):
        print(f"\n{'='*60}")
        print(f" {filename}")
        print(f"{'='*60}")
        print(f"Total commands: {len(commands)}")

        # Group by category
        by_category: Dict[str, List[str]] = {}
        for cmd_name, cmd_info in commands.items():
            cat = cmd_info.get("category") or "uncategorized"
            by_category.setdefault(cat, []).append(cmd_name)

        for category, cmd_names in sorted(by_category.items()):
            print(f"\n  [{category}] ({len(cmd_names)} commands)")
            for cmd_name in sorted(cmd_names):
                cmd = commands[cmd_name]
                args = cmd.get("args", [])

                # Format args summary
                arg_parts = []
                for arg in args:
                    name = arg["name"]
                    if arg.get("positional"):
                        arg_parts.append(name)
                    else:
                        arg_parts.append(f"[{name}]")

                args_str = " ".join(arg_parts) if arg_parts else "(no args)"
                print(f"    {cmd_name}: {args_str}")


def print_stats(schemas: Dict[str, Dict[str, Any]]) -> None:
    """Print statistics about the schemas."""
    total_commands = 0
    total_args = 0

    arg_types: Dict[str, int] = {}
    categories: Dict[str, int] = {}
    positional_count = 0
    optional_count = 0

    for filename, commands in schemas.items():
        total_commands += len(commands)

        for cmd_name, cmd_info in commands.items():
            cat = cmd_info.get("category") or "uncategorized"
            categories[cat] = categories.get(cat, 0) + 1

            for arg in cmd_info.get("args", []):
                total_args += 1

                arg_type = arg.get("type", "str")
                arg_types[arg_type] = arg_types.get(arg_type, 0) + 1

                if arg.get("positional"):
                    positional_count += 1
                else:
                    optional_count += 1

    print("\n" + "="*40)
    print(" Command Schema Statistics")
    print("="*40)

    print(f"\nTotal files parsed: {len(schemas)}")
    print(f"Total commands: {total_commands}")
    print(f"Total arguments: {total_args}")
    print(f"  Positional: {positional_count}")
    print(f"  Optional: {optional_count}")

    print(f"\nArgument types:")
    for arg_type, count in sorted(arg_types.items(), key=lambda x: -x[1]):
        print(f"  {arg_type}: {count}")

    print(f"\nCategories:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract command schemas from @math_command decorators"
    )
    parser.add_argument(
        "files",
        nargs="*",
        help=f"Files to parse (default: {', '.join(DEFAULT_FILES)})"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full JSON schema"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics"
    )
    parser.add_argument(
        "--scripts-dir",
        type=Path,
        default=None,
        help="Scripts directory (default: auto-detect)"
    )

    args = parser.parse_args()

    # Determine scripts directory
    if args.scripts_dir:
        scripts_dir = args.scripts_dir
    else:
        # Try to find scripts/ relative to this file
        this_file = Path(__file__).resolve()
        scripts_dir = this_file.parent

    # Use specified files or defaults
    files = args.files if args.files else DEFAULT_FILES

    # Extract schemas
    schemas = extract_all_schemas(files, scripts_dir)

    if not schemas:
        print("No commands found.", file=sys.stderr)
        return 1

    # Output
    if args.json:
        print(json.dumps(schemas, indent=2, default=str))
    elif args.stats:
        print_stats(schemas)
    else:
        print_human_readable(schemas)

    return 0


if __name__ == "__main__":
    sys.exit(main())

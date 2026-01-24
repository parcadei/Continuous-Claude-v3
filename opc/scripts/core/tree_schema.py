#!/usr/bin/env python3
"""JSON schema validation for knowledge tree format.

Validates knowledge-tree.json files against the expected schema.

Usage:
    uv run python scripts/core/core/tree_schema.py --validate /path/to/knowledge-tree.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

SCHEMA = {
    "type": "object",
    "required": ["version", "updated_at", "project", "structure"],
    "properties": {
        "version": {"type": "string"},
        "updated_at": {"type": "string"},
        "project": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "type": {"type": "string"},
                "stack": {"type": "array", "items": {"type": "string"}}
            }
        },
        "structure": {
            "type": "object",
            "required": ["root", "directories"],
            "properties": {
                "root": {"type": "string"},
                "directories": {"type": "object"}
            }
        },
        "components": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "type"],
                "properties": {
                    "name": {"type": "string"},
                    "type": {"type": "string"},
                    "files": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string"},
                    "related": {"type": "array", "items": {"type": "string"}}
                }
            }
        },
        "navigation": {
            "type": "object",
            "properties": {
                "common_tasks": {"type": "object"},
                "entry_points": {"type": "object"}
            }
        },
        "goals": {
            "type": "object",
            "properties": {
                "source": {"type": ["string", "null"]},
                "current": {
                    "type": ["object", "null"],
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "started": {"type": "string"}
                    }
                },
                "completed": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "completed": {"type": ["string", "null"]}
                        }
                    }
                },
                "planned": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "priority": {"type": "string"}
                        }
                    }
                }
            }
        },
        "critical_info": {"type": "object"}
    }
}


def validate_type(value: Any, expected: str | list[str]) -> bool:
    if isinstance(expected, list):
        return any(validate_type(value, t) for t in expected)

    type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None)
    }

    if expected not in type_map:
        return True
    return isinstance(value, type_map[expected])


def validate_schema(data: Any, schema: dict[str, Any], path: str = "") -> list[str]:
    errors = []

    if "type" in schema:
        if not validate_type(data, schema["type"]):
            errors.append(f"{path}: expected {schema['type']}, got {type(data).__name__}")
            return errors

    if schema.get("type") == "object" and isinstance(data, dict):
        for req in schema.get("required", []):
            if req not in data:
                errors.append(f"{path}: missing required field '{req}'")

        props = schema.get("properties", {})
        for key, val in data.items():
            if key in props:
                sub_errors = validate_schema(val, props[key], f"{path}.{key}" if path else key)
                errors.extend(sub_errors)

    if schema.get("type") == "array" and isinstance(data, list):
        items_schema = schema.get("items", {})
        for i, item in enumerate(data):
            sub_errors = validate_schema(item, items_schema, f"{path}[{i}]")
            errors.extend(sub_errors)

    return errors


def validate_tree(tree: dict[str, Any]) -> tuple[bool, list[str]]:
    errors = validate_schema(tree, SCHEMA)

    if tree.get("version") != SCHEMA_VERSION:
        errors.append(f"version mismatch: expected {SCHEMA_VERSION}, got {tree.get('version')}")

    return len(errors) == 0, errors


def load_and_validate(filepath: Path) -> tuple[bool, dict[str, Any] | None, list[str]]:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            tree = json.load(f)
    except json.JSONDecodeError as e:
        return False, None, [f"JSON parse error: {e}"]
    except FileNotFoundError:
        return False, None, [f"File not found: {filepath}"]

    valid, errors = validate_tree(tree)
    return valid, tree if valid else None, errors


def main():
    parser = argparse.ArgumentParser(description="Validate knowledge tree schema")
    parser.add_argument("--validate", "-v", required=True, help="Path to knowledge-tree.json")
    args = parser.parse_args()

    filepath = Path(args.validate)
    valid, tree, errors = load_and_validate(filepath)

    if valid:
        print(f"Valid: {filepath}")
        print(f"  Project: {tree['project']['name']}")
        print(f"  Directories: {len(tree['structure']['directories'])}")
        print(f"  Components: {len(tree.get('components', []))}")
    else:
        print(f"Invalid: {filepath}", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

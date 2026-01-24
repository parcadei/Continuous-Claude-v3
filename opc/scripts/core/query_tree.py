#!/usr/bin/env python3
"""Query interface for knowledge tree traversal.

Provides natural language queries against the knowledge tree.

Usage:
    uv run python scripts/core/core/query_tree.py --project /path/to/project --query "where to add tests"
    uv run python scripts/core/core/query_tree.py --project . --goals
    uv run python scripts/core/core/query_tree.py --project . --describe

Common queries:
    "where to add API endpoint" → Navigate to routes/controllers
    "how does auth work" → Return auth component with related files
    "what is this project about" → Return project.description + goals
    "what are we working on" → Return goals.current
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

QUERY_PATTERNS = {
    r"where.*(add|create|new).*(api|endpoint|route)": "add_api_endpoint",
    r"where.*(add|create|new).*(model|database|db|schema)": "add_database_model",
    r"where.*(add|create|new).*(component|ui|view)": "add_component",
    r"where.*(add|create|new).*(test|spec)": "add_test",
    r"where.*(add|create|new).*(hook)": "add_hook",
    r"where.*(add|create|new).*(skill)": "add_skill",
    r"(what|how).*(auth|login|session)": "component:Authentication",
    r"(what|how).*(api|endpoint)": "component:API",
    r"(what|how).*(database|db|model)": "component:Database",
    r"(what|how).*(config|setting)": "component:Configuration",
    r"what.*(project|about|does|is)": "describe",
    r"(current|working on|goal|focus)": "goals",
    r"(structure|organization|layout)": "structure",
    r"(entry|main|start)": "entry_points",
}


def load_tree(project_path: Path) -> dict[str, Any] | None:
    tree_path = project_path / ".claude" / "knowledge-tree.json"
    if not tree_path.exists():
        tree_path = project_path / "knowledge-tree.json"
    if not tree_path.exists():
        return None
    try:
        with open(tree_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def match_query(query: str) -> str | None:
    query_lower = query.lower()
    for pattern, result_type in QUERY_PATTERNS.items():
        if re.search(pattern, query_lower):
            return result_type
    return None


def query_task(tree: dict[str, Any], task_key: str) -> dict[str, Any]:
    nav = tree.get("navigation", {})
    tasks = nav.get("common_tasks", {})

    if task_key in tasks:
        return {
            "type": "task",
            "task": task_key,
            "paths": tasks[task_key],
            "hint": f"Look in: {', '.join(tasks[task_key])}"
        }

    return {
        "type": "task",
        "task": task_key,
        "paths": [],
        "hint": "No specific location found for this task type"
    }


def query_component(tree: dict[str, Any], component_name: str) -> dict[str, Any]:
    components = tree.get("components", [])

    for comp in components:
        if comp["name"].lower() == component_name.lower():
            return {
                "type": "component",
                "name": comp["name"],
                "component_type": comp.get("type"),
                "files": comp.get("files", []),
                "description": comp.get("description", ""),
                "related": comp.get("related", [])
            }

    return {
        "type": "component",
        "name": component_name,
        "files": [],
        "hint": f"Component '{component_name}' not found in project"
    }


def query_describe(tree: dict[str, Any]) -> dict[str, Any]:
    project = tree.get("project", {})
    goals = tree.get("goals", {})

    return {
        "type": "describe",
        "name": project.get("name", "Unknown"),
        "description": project.get("description", "No description available"),
        "project_type": project.get("type", "unknown"),
        "stack": project.get("stack", []),
        "current_goal": goals.get("current"),
        "critical_info": tree.get("critical_info", {})
    }


def query_goals(tree: dict[str, Any]) -> dict[str, Any]:
    goals = tree.get("goals", {})

    return {
        "type": "goals",
        "source": goals.get("source"),
        "current": goals.get("current"),
        "completed_count": len(goals.get("completed", [])),
        "completed": goals.get("completed", [])[:5],
        "planned": goals.get("planned", [])[:5]
    }


def query_structure(tree: dict[str, Any]) -> dict[str, Any]:
    structure = tree.get("structure", {})
    directories = structure.get("directories", {})

    top_level = [d for d in directories.keys() if d.count("/") <= 1]

    return {
        "type": "structure",
        "root": structure.get("root", ""),
        "total_directories": len(directories),
        "top_level": {d: directories[d] for d in sorted(top_level)[:15]}
    }


def query_entry_points(tree: dict[str, Any]) -> dict[str, Any]:
    nav = tree.get("navigation", {})
    entries = nav.get("entry_points", {})

    return {
        "type": "entry_points",
        "entries": entries
    }


def process_query(tree: dict[str, Any], query: str) -> dict[str, Any]:
    matched = match_query(query)

    if not matched:
        return {
            "type": "unknown",
            "query": query,
            "hint": "Try: 'where to add endpoint', 'what is this project', 'current goal'",
            "available_tasks": list(tree.get("navigation", {}).get("common_tasks", {}).keys()),
            "components": [c["name"] for c in tree.get("components", [])]
        }

    if matched.startswith("add_"):
        return query_task(tree, matched)

    if matched.startswith("component:"):
        comp_name = matched.split(":", 1)[1]
        return query_component(tree, comp_name)

    if matched == "describe":
        return query_describe(tree)

    if matched == "goals":
        return query_goals(tree)

    if matched == "structure":
        return query_structure(tree)

    if matched == "entry_points":
        return query_entry_points(tree)

    return {"type": "unknown", "matched": matched}


def format_result(result: dict[str, Any]) -> str:
    rtype = result.get("type", "unknown")
    lines = []

    if rtype == "task":
        lines.append(f"Task: {result.get('task')}")
        paths = result.get("paths", [])
        if paths:
            lines.append(f"Locations: {', '.join(paths)}")
        lines.append(result.get("hint", ""))

    elif rtype == "component":
        lines.append(f"Component: {result.get('name')}")
        if result.get("description"):
            lines.append(f"  {result['description']}")
        files = result.get("files", [])
        if files:
            lines.append(f"Files: {', '.join(files)}")
        related = result.get("related", [])
        if related:
            lines.append(f"Related: {', '.join(related)}")

    elif rtype == "describe":
        lines.append(f"Project: {result.get('name')}")
        lines.append(f"Type: {result.get('project_type')}")
        if result.get("description"):
            lines.append(f"Description: {result['description']}")
        stack = result.get("stack", [])
        if stack:
            lines.append(f"Stack: {', '.join(stack)}")
        if result.get("current_goal"):
            goal = result["current_goal"]
            lines.append(f"Current Goal: {goal.get('title', 'Unknown')}")

    elif rtype == "goals":
        current = result.get("current")
        if current:
            lines.append(f"Current Focus: {current.get('title')}")
            if current.get("description"):
                lines.append(f"  {current['description']}")
        else:
            lines.append("No current goal set")

        lines.append(f"Completed: {result.get('completed_count', 0)} items")
        planned = result.get("planned", [])
        if planned:
            lines.append("Planned:")
            for p in planned[:3]:
                lines.append(f"  - {p.get('title')} ({p.get('priority', 'medium')})")

    elif rtype == "structure":
        lines.append(f"Root: {result.get('root')}")
        lines.append(f"Total directories: {result.get('total_directories')}")
        lines.append("Top-level structure:")
        for d, info in result.get("top_level", {}).items():
            purpose = info.get("purpose", "")
            lines.append(f"  {d}: {purpose}")

    elif rtype == "entry_points":
        entries = result.get("entries", {})
        lines.append("Entry points:")
        for name, path in entries.items():
            lines.append(f"  {name}: {path}")

    else:
        lines.append(f"Query not understood: {result.get('query', '')}")
        lines.append(result.get("hint", ""))
        tasks = result.get("available_tasks", [])
        if tasks:
            lines.append(f"Available tasks: {', '.join(tasks)}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Query knowledge tree")
    parser.add_argument("--project", "-p", required=True, help="Project root directory")
    parser.add_argument("--query", "-q", help="Natural language query")
    parser.add_argument("--goals", "-g", action="store_true", help="Show current goals")
    parser.add_argument("--describe", "-d", action="store_true", help="Describe project")
    parser.add_argument("--structure", "-s", action="store_true", help="Show structure")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    project_path = Path(args.project).resolve()
    tree = load_tree(project_path)

    if not tree:
        print(f"No knowledge tree found at {project_path}/.claude/knowledge-tree.json", file=sys.stderr)
        print("Run: uv run python scripts/core/core/knowledge_tree.py --project .", file=sys.stderr)
        sys.exit(1)

    if args.goals:
        result = query_goals(tree)
    elif args.describe:
        result = query_describe(tree)
    elif args.structure:
        result = query_structure(tree)
    elif args.query:
        result = process_query(tree, args.query)
    else:
        result = query_describe(tree)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_result(result))


if __name__ == "__main__":
    main()

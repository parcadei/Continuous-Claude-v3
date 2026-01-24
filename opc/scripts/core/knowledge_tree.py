#!/usr/bin/env python3
"""Knowledge Tree generator - creates project-specific navigation maps.

Scans project directory structure, identifies key files, parses content
for descriptions, and builds a hierarchical knowledge tree for Claude Code.

Usage:
    uv run python scripts/core/core/knowledge_tree.py --project /path/to/project
    uv run python scripts/core/core/knowledge_tree.py --project . --output tree.json

Output: {project}/.claude/knowledge-tree.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"

KEY_FILES = {
    "README.md": "project_description",
    "readme.md": "project_description",
    "package.json": "project_config",
    "pyproject.toml": "project_config",
    "Cargo.toml": "project_config",
    "go.mod": "project_config",
    "ROADMAP.md": "goals",
    "roadmap.md": "goals",
    "CLAUDE.md": "claude_config",
    ".env.example": "env_vars",
    "docker-compose.yml": "deployment",
    "Dockerfile": "deployment",
}

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".cache", "coverage", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "target", ".idea", ".vscode"
}

IGNORE_PATTERNS = {
    r"\.pyc$", r"\.pyo$", r"\.so$", r"\.dll$", r"\.exe$",
    r"\.lock$", r"-lock\.", r"\.log$", r"\.tmp$"
}

PROJECT_TYPE_MARKERS = {
    "package.json": "javascript",
    "tsconfig.json": "typescript",
    "pyproject.toml": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "java",
    "build.gradle": "java",
    "Gemfile": "ruby",
}

STACK_MARKERS = {
    "react": ["react", "jsx", "tsx"],
    "vue": ["vue", ".vue"],
    "angular": ["angular", "@angular"],
    "next.js": ["next", "next.config"],
    "express": ["express"],
    "fastapi": ["fastapi"],
    "django": ["django"],
    "flask": ["flask"],
    "postgresql": ["postgres", "psycopg", "pg"],
    "mongodb": ["mongo", "pymongo"],
    "redis": ["redis", "ioredis"],
}


def should_ignore(path: Path) -> bool:
    name = path.name
    if name in IGNORE_DIRS:
        return True
    for pattern in IGNORE_PATTERNS:
        if re.search(pattern, name):
            return True
    return False


def detect_project_type(project_root: Path) -> tuple[str, list[str]]:
    proj_type = "unknown"
    stack = []

    for marker, ptype in PROJECT_TYPE_MARKERS.items():
        if (project_root / marker).exists():
            proj_type = ptype
            break

    all_text = ""
    for f in ["package.json", "pyproject.toml", "requirements.txt"]:
        fp = project_root / f
        if fp.exists():
            try:
                all_text += fp.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass

    for tech, markers in STACK_MARKERS.items():
        for m in markers:
            if m.lower() in all_text.lower():
                stack.append(tech)
                break

    return proj_type, list(set(stack))


def extract_description(filepath: Path) -> str:
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    name = filepath.name.lower()

    if name == "readme.md":
        lines = content.split("\n")
        desc_lines = []
        in_header = False
        for line in lines[:30]:
            if line.startswith("# "):
                in_header = True
                continue
            if in_header and line.strip() and not line.startswith("#"):
                desc_lines.append(line.strip())
            if len(desc_lines) >= 3:
                break
        return " ".join(desc_lines)[:500]

    if name == "package.json":
        try:
            data = json.loads(content)
            return data.get("description", "")
        except Exception:
            return ""

    if name == "pyproject.toml":
        match = re.search(r'description\s*=\s*"([^"]+)"', content)
        if match:
            return match.group(1)

    return ""


def parse_roadmap(filepath: Path) -> dict[str, Any]:
    if not filepath.exists():
        return {"source": None, "current": None, "completed": [], "planned": []}

    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {"source": str(filepath), "current": None, "completed": [], "planned": []}

    result = {
        "source": str(filepath.name),
        "current": None,
        "completed": [],
        "planned": []
    }

    lines = content.split("\n")
    section = None
    current_title = None

    for line in lines:
        stripped = line.strip()

        if stripped.lower().startswith("## current"):
            section = "current"
            continue
        elif stripped.lower().startswith("## completed"):
            section = "completed"
            continue
        elif stripped.lower().startswith("## planned"):
            section = "planned"
            continue
        elif stripped.startswith("## "):
            section = None
            continue

        if section == "current" and stripped.startswith("**") and stripped.endswith("**"):
            current_title = stripped.strip("*").strip()
            result["current"] = {"title": current_title, "description": ""}
        elif section == "current" and result["current"] and stripped.startswith("-"):
            if result["current"]["description"]:
                result["current"]["description"] += "; "
            result["current"]["description"] += stripped.lstrip("- ").strip()

        if section == "completed":
            match = re.match(r"-\s*\[x\]\s*(.+?)(?:\s*\(([^)]+)\))?$", stripped, re.I)
            if match:
                result["completed"].append({
                    "title": match.group(1).strip(),
                    "completed": match.group(2) if match.group(2) else None
                })

        if section == "planned":
            match = re.match(r"-\s*\[\s*\]\s*(.+?)(?:\s*\(([^)]+)\))?$", stripped, re.I)
            if match:
                priority = "medium"
                title = match.group(1).strip()
                prio_match = match.group(2)
                if prio_match:
                    if "high" in prio_match.lower():
                        priority = "high"
                    elif "low" in prio_match.lower():
                        priority = "low"
                result["planned"].append({"title": title, "priority": priority})

    return result


def scan_directory(root: Path, max_depth: int = 4) -> dict[str, Any]:
    directories = {}

    def scan(current: Path, depth: int, prefix: str = ""):
        if depth > max_depth:
            return
        if should_ignore(current):
            return

        try:
            entries = list(current.iterdir())
        except PermissionError:
            return

        dirs = sorted([e for e in entries if e.is_dir() and not should_ignore(e)])
        files = sorted([e for e in entries if e.is_file() and not should_ignore(e)])

        rel_path = str(current.relative_to(root)) + "/" if current != root else ""

        if rel_path:
            key_files = [f.name for f in files if f.name in KEY_FILES][:5]
            purpose = infer_directory_purpose(current.name, [f.name for f in files])
            directories[rel_path] = {
                "purpose": purpose,
                "key_files": key_files if key_files else None
            }

        for d in dirs:
            scan(d, depth + 1, rel_path)

    scan(root, 0)
    return directories


def infer_directory_purpose(name: str, files: list[str]) -> str:
    name_lower = name.lower()

    purpose_map = {
        "src": "Source code",
        "lib": "Library code",
        "test": "Test files",
        "tests": "Test files",
        "__tests__": "Test files",
        "spec": "Test specifications",
        "docs": "Documentation",
        "doc": "Documentation",
        "scripts": "Build/utility scripts",
        "bin": "Executable scripts",
        "config": "Configuration files",
        "configs": "Configuration files",
        "public": "Public assets",
        "static": "Static files",
        "assets": "Asset files",
        "components": "UI components",
        "pages": "Page components/routes",
        "api": "API endpoints",
        "routes": "Route handlers",
        "models": "Data models",
        "services": "Service layer",
        "utils": "Utility functions",
        "helpers": "Helper functions",
        "hooks": "React/custom hooks",
        "middleware": "Middleware",
        "migrations": "Database migrations",
        "fixtures": "Test fixtures",
        "mocks": "Mock data/objects",
        "types": "Type definitions",
        "interfaces": "Interface definitions",
        "core": "Core functionality",
        "shared": "Shared code",
        "common": "Common utilities",
        "features": "Feature modules",
        "modules": "Application modules",
        "skills": "Skill definitions",
        "agents": "Agent definitions",
        "rules": "Rule definitions",
    }

    if name_lower in purpose_map:
        return purpose_map[name_lower]

    ext_counts: dict[str, int] = {}
    for f in files:
        if "." in f:
            ext = f.rsplit(".", 1)[1].lower()
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

    if ext_counts:
        top_ext = max(ext_counts, key=ext_counts.get)
        ext_purposes = {
            "py": "Python modules",
            "ts": "TypeScript modules",
            "tsx": "React/TypeScript components",
            "js": "JavaScript modules",
            "jsx": "React components",
            "css": "Stylesheets",
            "scss": "SCSS styles",
            "json": "JSON data/config",
            "yml": "YAML config",
            "yaml": "YAML config",
            "md": "Markdown documentation",
            "sql": "SQL scripts",
        }
        if top_ext in ext_purposes:
            return ext_purposes[top_ext]

    return "Project directory"


def detect_components(root: Path, directories: dict[str, Any]) -> list[dict[str, Any]]:
    components = []

    component_dirs = {
        "auth": ("Authentication", "feature", ["auth/", "authentication/", "login/"]),
        "api": ("API", "layer", ["api/", "routes/", "endpoints/"]),
        "database": ("Database", "layer", ["models/", "db/", "migrations/"]),
        "ui": ("UI Components", "layer", ["components/", "ui/", "views/"]),
        "services": ("Services", "layer", ["services/", "providers/"]),
        "config": ("Configuration", "system", ["config/", "settings/"]),
    }

    for comp_key, (name, comp_type, patterns) in component_dirs.items():
        matching_dirs = []
        for dir_path in directories.keys():
            for pattern in patterns:
                if pattern in dir_path.lower():
                    matching_dirs.append(dir_path)
                    break

        if matching_dirs:
            components.append({
                "name": name,
                "type": comp_type,
                "files": matching_dirs[:5],
                "description": f"{name} - {comp_type} component",
                "related": []
            })

    return components


def build_navigation(directories: dict[str, Any]) -> dict[str, Any]:
    common_tasks = {}
    entry_points = {}

    task_mappings = {
        "add_api_endpoint": ["api/", "routes/", "controllers/", "endpoints/"],
        "add_database_model": ["models/", "db/", "migrations/", "schema/"],
        "add_component": ["components/", "ui/", "views/"],
        "add_test": ["tests/", "test/", "__tests__/", "spec/"],
        "add_hook": ["hooks/"],
        "add_skill": ["skills/"],
    }

    for task, patterns in task_mappings.items():
        matching = [d for d in directories.keys() for p in patterns if p in d.lower()]
        if matching:
            common_tasks[task] = matching[:3]

    entry_mappings = {
        "main": ["src/index", "src/main", "src/app", "main.py", "app.py", "index.ts"],
        "cli": ["bin/", "cli/", "cli.py", "cli.ts"],
        "config": ["config/", "settings/", ".env"],
    }

    for entry, patterns in entry_mappings.items():
        for d in directories.keys():
            for p in patterns:
                if p in d.lower():
                    entry_points[entry] = d
                    break
            if entry in entry_points:
                break

    return {"common_tasks": common_tasks, "entry_points": entry_points}


def generate_tree(project_path: Path) -> dict[str, Any]:
    project_path = project_path.resolve()

    proj_type, stack = detect_project_type(project_path)

    description = ""
    for key_file in ["README.md", "readme.md", "package.json", "pyproject.toml"]:
        fp = project_path / key_file
        if fp.exists():
            description = extract_description(fp)
            if description:
                break

    directories = scan_directory(project_path)
    components = detect_components(project_path, directories)
    navigation = build_navigation(directories)

    roadmap_path = project_path / "ROADMAP.md"
    goals = parse_roadmap(roadmap_path)

    critical_info = {}
    if (project_path / ".env.example").exists():
        critical_info["env_vars"] = ".env.example"
    if (project_path / "docs" / "DEPLOYMENT.md").exists():
        critical_info["deployment"] = "docs/DEPLOYMENT.md"
    if (project_path / "CLAUDE.md").exists():
        critical_info["claude_config"] = "CLAUDE.md"

    tree = {
        "version": SCHEMA_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "name": project_path.name,
            "description": description,
            "type": proj_type,
            "stack": stack
        },
        "structure": {
            "root": str(project_path),
            "directories": directories
        },
        "components": components,
        "navigation": navigation,
        "goals": goals,
        "critical_info": critical_info
    }

    return tree


def save_tree(tree: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Generate project knowledge tree")
    parser.add_argument("--project", "-p", required=True, help="Project root directory")
    parser.add_argument("--output", "-o", help="Output file (default: {project}/.claude/knowledge-tree.json)")
    parser.add_argument("--print", "-P", action="store_true", help="Print tree to stdout")
    args = parser.parse_args()

    project_path = Path(args.project).resolve()
    if not project_path.is_dir():
        print(f"Error: {project_path} is not a directory", file=sys.stderr)
        sys.exit(1)

    tree = generate_tree(project_path)

    if args.print:
        print(json.dumps(tree, indent=2))
        return

    output_path = Path(args.output) if args.output else project_path / ".claude" / "knowledge-tree.json"
    save_tree(tree, output_path)
    print(f"Knowledge tree saved to: {output_path}")


if __name__ == "__main__":
    main()

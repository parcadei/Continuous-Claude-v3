#!/usr/bin/env python3
"""
Qlty MCP Server - Code quality tools via MCP protocol.

This server wraps the qlty CLI to provide code quality checking,
formatting, and metrics as MCP tools.

Requires: qlty CLI installed (https://github.com/qltysh/qlty)
"""

import asyncio
import json
import subprocess
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("qlty")


def find_qlty() -> str:
    """Find qlty binary in common locations."""
    import shutil
    from pathlib import Path

    # Check PATH first
    qlty_path = shutil.which("qlty")
    if qlty_path:
        return qlty_path

    # Check common install locations
    home = Path.home()
    candidates = [
        home / ".qlty" / "bin" / "qlty",
        home / ".local" / "bin" / "qlty",
        home / "bin" / "qlty",
        Path("/usr/local/bin/qlty"),
    ]

    for path in candidates:
        if path.exists():
            return str(path)

    return "qlty"  # Fall back to PATH lookup


QLTY_BIN = find_qlty()


def run_qlty(args: list[str], cwd: str | None = None) -> dict[str, Any]:
    """Run qlty CLI command and return result."""
    try:
        result = subprocess.run(
            [QLTY_BIN, *args],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=300,  # 5 minute timeout
        )
        return {
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "qlty CLI not found. Install from https://github.com/qltysh/qlty",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "Command timed out after 5 minutes",
        }


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available qlty tools."""
    return [
        Tool(
            name="qlty_check",
            description="Run linters on files. Returns issues found. Use --fix to auto-fix.",
            inputSchema={
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files or directories to check (empty = changed files)",
                    },
                    "all": {
                        "type": "boolean",
                        "description": "Check all files, not just changed",
                        "default": False,
                    },
                    "fix": {
                        "type": "boolean",
                        "description": "Auto-fix issues where possible",
                        "default": False,
                    },
                    "level": {
                        "type": "string",
                        "enum": ["note", "low", "medium", "high"],
                        "description": "Minimum issue level to report",
                        "default": "low",
                    },
                    "json_output": {
                        "type": "boolean",
                        "description": "Return JSON instead of text",
                        "default": True,
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory (must have .qlty/qlty.toml)",
                    },
                },
            },
        ),
        Tool(
            name="qlty_fmt",
            description="Auto-format files using configured formatters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to format (empty = changed files)",
                    },
                    "all": {
                        "type": "boolean",
                        "description": "Format all files",
                        "default": False,
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory",
                    },
                },
            },
        ),
        Tool(
            name="qlty_metrics",
            description="Calculate code quality metrics (complexity, duplication, etc).",
            inputSchema={
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to analyze (empty = changed files)",
                    },
                    "all": {
                        "type": "boolean",
                        "description": "Analyze all files",
                        "default": False,
                    },
                    "sort": {
                        "type": "string",
                        "enum": ["complexity", "duplication", "maintainability"],
                        "description": "Sort results by metric",
                    },
                    "json_output": {
                        "type": "boolean",
                        "description": "Return JSON instead of text",
                        "default": True,
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory",
                    },
                },
            },
        ),
        Tool(
            name="qlty_smells",
            description="Find code smells (duplication, complexity hotspots).",
            inputSchema={
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to analyze",
                    },
                    "all": {
                        "type": "boolean",
                        "description": "Analyze all files",
                        "default": False,
                    },
                    "json_output": {
                        "type": "boolean",
                        "description": "Return JSON instead of text",
                        "default": True,
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory",
                    },
                },
            },
        ),
        Tool(
            name="qlty_init",
            description="Initialize qlty in a repository. Creates .qlty/qlty.toml.",
            inputSchema={
                "type": "object",
                "properties": {
                    "yes": {
                        "type": "boolean",
                        "description": "Auto-accept defaults",
                        "default": True,
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Repository to initialize",
                    },
                },
            },
        ),
        Tool(
            name="qlty_plugins_list",
            description="List available qlty plugins.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cwd": {
                        "type": "string",
                        "description": "Working directory",
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    cwd = arguments.get("cwd")

    if name == "qlty_check":
        args = ["check"]
        if arguments.get("all"):
            args.append("--all")
        if arguments.get("fix"):
            args.append("--fix")
        if arguments.get("level"):
            args.extend(["--level", arguments["level"]])
        if arguments.get("json_output", True):
            args.append("--json")
        if arguments.get("paths"):
            args.extend(arguments["paths"])
        result = run_qlty(args, cwd)

    elif name == "qlty_fmt":
        args = ["fmt"]
        if arguments.get("all"):
            args.append("--all")
        if arguments.get("paths"):
            args.extend(arguments["paths"])
        result = run_qlty(args, cwd)

    elif name == "qlty_metrics":
        args = ["metrics"]
        if arguments.get("all"):
            args.append("--all")
        if arguments.get("sort"):
            args.extend(["--sort", arguments["sort"]])
        if arguments.get("json_output", True):
            args.append("--json")
        if arguments.get("paths"):
            args.extend(arguments["paths"])
        result = run_qlty(args, cwd)

    elif name == "qlty_smells":
        args = ["smells"]
        if arguments.get("all"):
            args.append("--all")
        if arguments.get("json_output", True):
            args.append("--json")
        if arguments.get("paths"):
            args.extend(arguments["paths"])
        result = run_qlty(args, cwd)

    elif name == "qlty_init":
        args = ["init"]
        if arguments.get("yes", True):
            args.append("--yes")
        result = run_qlty(args, cwd)

    elif name == "qlty_plugins_list":
        args = ["plugins", "list"]
        result = run_qlty(args, cwd)

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    # Format output
    output_parts = []
    if result["stdout"]:
        output_parts.append(result["stdout"])
    if result["stderr"]:
        output_parts.append(f"[stderr]\n{result['stderr']}")
    if not output_parts:
        output_parts.append(
            f"Command completed with exit code {result['returncode']}"
        )

    return [TextContent(type="text", text="\n".join(output_parts))]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

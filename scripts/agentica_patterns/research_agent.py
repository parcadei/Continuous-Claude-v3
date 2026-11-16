#!/usr/bin/env python3
"""
Agentica Research Agent with Perplexity + Nia MCP Tools

Demonstrates building an AI research agent using the Agentica SDK
with access to MCP tools for web research and library documentation.

USAGE:
    # Run directly (requires agentica extra)
    uv run --extra agentica python scripts/agentica/research_agent.py \
        --query "best practices for Python async error handling"

    # With specific mode
    uv run --extra agentica python scripts/agentica/research_agent.py \
        --query "React hooks patterns" \
        --mode library

MODES:
    - web: Use Perplexity for web research (default)
    - library: Use Nia for library documentation
    - both: Query both sources and synthesize

REQUIREMENTS:
    - Python 3.12+ (Agentica requirement)
    - uv sync --extra agentica
    - Claude proxy running OR OpenRouter API key set

ENVIRONMENT:
    OPENROUTER_API_KEY - For OpenRouter models (recommended)
    PERPLEXITY_API_KEY - For Perplexity MCP tool
    NIA_API_KEY - For Nia MCP tool
"""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


# --- MCP Tool Wrappers ---

def call_perplexity(query: str, mode: str = "research") -> dict[str, Any]:
    """
    Web research via Perplexity MCP tool.

    Args:
        query: Research query
        mode: "research" for thorough, "quick" for fast

    Returns:
        Research results as dict
    """
    project_dir = Path(__file__).parent.parent.parent
    result = subprocess.run(
        [
            "uv", "run", "python", "-m", "runtime.harness",
            str(project_dir / "scripts" / "perplexity_search.py"),
            "--query", query,
            "--mode", mode,
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    if result.returncode != 0:
        return {"error": result.stderr, "success": False}

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"content": result.stdout, "success": True}


def call_nia(package: str, query: str, registry: str = "npm") -> dict[str, Any]:
    """
    Library documentation search via Nia MCP tool.

    Args:
        package: Package name to search
        query: Documentation query
        registry: npm, py_pi, crates, or go_modules

    Returns:
        Documentation results as dict
    """
    project_dir = Path(__file__).parent.parent.parent
    result = subprocess.run(
        [
            "uv", "run", "python", "-m", "runtime.harness",
            str(project_dir / "scripts" / "nia_docs.py"),
            "--package", package,
            "--query", query,
            "--registry", registry,
        ],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
    )

    if result.returncode != 0:
        return {"error": result.stderr, "success": False}

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"content": result.stdout, "success": True}


async def research_with_agentica(query: str, mode: str = "web") -> dict[str, Any]:
    """
    Main research function using Agentica agent.

    Args:
        query: Research question
        mode: "web", "library", or "both"

    Returns:
        Research findings
    """
    try:
        from agentica import spawn
    except ImportError:
        print("Error: Agentica not installed. Run: uv sync --extra agentica")
        print("Note: Agentica requires Python 3.12+")
        sys.exit(1)

    # Create research agent with tool access
    agent = await spawn(
        premise="""You are a research agent with access to two tools:

1. perplexity_search(query: str) - Search the web for current information, best practices, tutorials
2. nia_docs(package: str, query: str, registry: str) - Search library documentation

When asked to research something:
1. Identify if it's about a specific library (use nia_docs) or general topic (use perplexity_search)
2. Call the appropriate tool(s)
3. Synthesize the findings into a structured response

Always return your findings in a structured format with:
- key_findings: list of main discoveries
- sources: list of source descriptions
- recommendations: actionable suggestions
- open_questions: things that need more investigation
""",
        scope={
            "perplexity_search": lambda q: call_perplexity(q, "research"),
            "nia_docs": call_nia,
        },
        model="anthropic:claude-sonnet-4.5",  # Or use openai:gpt-4.1
    )

    # Execute research based on mode
    if mode == "library":
        prompt = f"""Research this library/API documentation topic: {query}

Use nia_docs to search for relevant documentation.
If the query mentions a specific package, search that package.
Otherwise, infer the most relevant package from the query context."""

    elif mode == "both":
        prompt = f"""Thoroughly research: {query}

Use BOTH tools:
1. perplexity_search for web resources, tutorials, and best practices
2. nia_docs for official library documentation

Synthesize findings from both sources into a comprehensive answer."""

    else:  # web mode (default)
        prompt = f"""Research this topic using web search: {query}

Use perplexity_search to find current information, best practices, and examples.
Focus on practical, actionable information."""

    # Call the agent (use str return type - dict not yet supported)
    result = await agent.call(
        str,
        prompt
    )

    # Parse as JSON if possible, otherwise return as-is
    try:
        return json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return {"response": result}


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Research Agent using Agentica + MCP Tools"
    )
    parser.add_argument(
        "--query",
        type=str,
        required=True,
        help="Research query",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="web",
        choices=["web", "library", "both"],
        help="Research mode: web, library, or both (default: web)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (optional, defaults to stdout)",
    )
    args = parser.parse_args()

    print(f"Researching: {args.query}")
    print(f"Mode: {args.mode}")
    print("-" * 50)

    result = await research_with_agentica(args.query, args.mode)

    # Format output
    output = json.dumps(result, indent=2)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Results written to: {args.output}")
    else:
        print(output)

    return result


if __name__ == "__main__":
    asyncio.run(main())

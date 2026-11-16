"""Tool wrappers for the Native REPL Research Coordinator.

This module provides async tool functions that wrap run_claude() for
use in specialist agent scopes. Each function invokes Claude Code CLI
with specific tools enabled.

Functions:
    web_research: Search the web for information
    codebase_research: Analyze codebase patterns
    docs_research: Fetch and analyze documentation
    comprehensive_research: Multi-tool thorough research
"""

from typing import Any

from .run_claude import run_claude


async def web_research(query: str, max_turns: int = 5) -> str:
    """Search the web for information using Claude Code CLI.

    This invokes Claude Code with WebSearch enabled to research a topic.

    Args:
        query: The research query
        max_turns: Maximum agentic turns for Claude

    Returns:
        Research results as string

    Example:
        >>> results = await web_research("Python async patterns 2025")
    """
    result = await run_claude(
        task=f"""Research this topic thoroughly and provide a comprehensive summary:

{query}

Include:
- Key facts and findings
- Relevant sources/references
- Any important caveats or limitations

Format your response as structured text that can be parsed.""",
        tools=["WebSearch"],
        max_turns=max_turns,
        system_prompt="You are a research assistant. Be thorough and cite sources.",
    )

    return _extract_result(result)


async def codebase_research(
    query: str,
    path: str = ".",
    max_turns: int = 5
) -> str:
    """Search the codebase for patterns and implementations.

    This invokes Claude Code with Read/Grep/Glob to analyze code.

    Args:
        query: What to search for
        path: Directory to search in
        max_turns: Maximum agentic turns

    Returns:
        Code analysis results

    Example:
        >>> results = await codebase_research("async spawn patterns", "scripts/")
    """
    result = await run_claude(
        task=f"""Analyze the codebase for: {query}

Search in: {path}

Find relevant:
- Code patterns
- Implementations
- Examples
- Documentation

Summarize your findings with file paths and code snippets.""",
        tools=["Read", "Grep", "Glob"],
        max_turns=max_turns,
        system_prompt="You are a code analyst. Find relevant patterns and implementations.",
    )

    return _extract_result(result)


async def docs_research(url: str, query: str, max_turns: int = 3) -> str:
    """Fetch and analyze documentation from a URL.

    This invokes Claude Code with WebFetch to read documentation.

    Args:
        url: Documentation URL to fetch
        query: What to look for in the docs
        max_turns: Maximum agentic turns

    Returns:
        Documentation analysis

    Example:
        >>> docs = await docs_research("https://docs.python.org/3/library/asyncio.html", "gather")
    """
    result = await run_claude(
        task=f"""Fetch and analyze the documentation at: {url}

Look for information about: {query}

Summarize:
- Key concepts
- Usage examples
- Best practices
- Common pitfalls""",
        tools=["WebFetch"],
        max_turns=max_turns,
        system_prompt="You are a documentation analyst. Extract key information clearly.",
    )

    return _extract_result(result)


async def comprehensive_research(
    topic: str,
    max_turns: int = 10,
    depth: str = "standard"
) -> str:
    """Comprehensive research using all available tools.

    This is the main research function for specialists. It invokes Claude Code
    with multiple tools to gather comprehensive information.

    Args:
        topic: Research topic
        max_turns: Maximum agentic turns
        depth: "standard" or "deep"

    Returns:
        Comprehensive research findings

    Example:
        >>> findings = await comprehensive_research("MCP server patterns", depth="deep")
    """
    depth_instruction = ""
    if depth == "deep":
        depth_instruction = """
This is a DEEP research request. Be extremely thorough:
- Search multiple sources
- Cross-reference findings
- Look for edge cases and nuances
- Provide detailed analysis
"""

    result = await run_claude(
        task=f"""Conduct comprehensive research on:

{topic}

{depth_instruction}

Your research should include:
1. Key findings and facts
2. Current best practices
3. Code examples (if applicable)
4. Common pitfalls to avoid
5. Reliable sources

Format your response as structured text with clear sections.""",
        tools=["WebSearch", "Read", "Grep", "Glob", "WebFetch"],
        max_turns=max_turns,
        system_prompt="You are a senior research analyst. Provide thorough, accurate research.",
    )

    return _extract_result(result)


def _extract_result(result: Any) -> str:
    """Extract result string from run_claude response.

    Args:
        result: Response from run_claude (dict or other)

    Returns:
        Result as string
    """
    if isinstance(result, dict):
        return str(result.get("result", ""))
    return str(result)


def get_tool_scope() -> dict[str, Any]:
    """Get the tool scope for specialist agents.

    Returns a dictionary of tools that can be passed to spawn(scope=...).

    Returns:
        Dictionary mapping tool names to async functions

    Example:
        >>> scope = get_tool_scope()
        >>> agent = await spawn(premise="...", scope=scope)
    """
    return {
        "run_claude": run_claude,
        "web_research": web_research,
        "codebase_research": codebase_research,
        "docs_research": docs_research,
        "comprehensive_research": comprehensive_research,
    }

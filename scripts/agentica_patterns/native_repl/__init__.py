"""Native REPL Research Coordinator package.

This package implements the Native REPL approach (Approach 3) for multi-agent
research using Claude Code CLI via run_claude().

Architecture:
    - Agentica agents handle orchestration
    - Claude Code CLI (via run_claude) handles execution
    - Specialists delegate research to Claude with appropriate tools

Modules:
    models: Data classes (ResearchSection, ResearchFindings, ResearchDocument)
    tools: run_claude() wrappers (web_research, codebase_research, etc.)
    coordinator: ResearchCoordinator class
    cli: CLI entry point
    run_claude: Core async wrapper for Claude Code CLI

Usage:
    from scripts.agentica_patterns.native_repl import ResearchCoordinator

    coordinator = ResearchCoordinator("Python async patterns")
    document = await coordinator.research()
    print(document.to_markdown())

CLI:
    uv run python -m scripts.agentica.native_repl.cli --topic "Python async patterns"
"""

# Data models
# Coordinator
from .coordinator import ResearchCoordinator
from .models import ResearchDocument, ResearchFindings, ResearchSection, ToolHint

# Core run_claude function
from .run_claude import (
    ClaudeExecutionError,
    ClaudeParseError,
    run_claude,
    run_claude_sync,
)

# Tools
from .tools import (
    codebase_research,
    comprehensive_research,
    docs_research,
    get_tool_scope,
    web_research,
)

__all__ = [
    # Models
    "ResearchSection",
    "ResearchFindings",
    "ResearchDocument",
    "ToolHint",
    # Coordinator
    "ResearchCoordinator",
    # Tools
    "web_research",
    "codebase_research",
    "docs_research",
    "comprehensive_research",
    "get_tool_scope",
    # run_claude
    "run_claude",
    "run_claude_sync",
    "ClaudeExecutionError",
    "ClaudeParseError",
]

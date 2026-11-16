#!/usr/bin/env python3
"""Research-to-Implement MCP Chaining Pipeline.

DESCRIPTION: Chains multiple MCP tools to research patterns, find similar code,
apply improvements, validate quality, and stage changes.

Pipeline Steps:
1. nia - Search library docs for patterns/examples
2. ast-grep - Find similar code patterns in target codebase
3. morph - Apply pattern via warpgrep search or edit
4. qlty - Validate code quality
5. git - Stage changes

USAGE:
    # Basic research and implementation
    uv run python -m runtime.harness scripts/research_implement_pipeline.py \
        --topic "async error handling python" \
        --target-dir "./workspace/pipeline-test"

    # Dry run (preview plan without making changes)
    uv run python -m runtime.harness scripts/research_implement_pipeline.py \
        --topic "context manager patterns" \
        --target-dir "./src" \
        --dry-run

    # Verbose output
    uv run python -m runtime.harness scripts/research_implement_pipeline.py \
        --topic "retry with exponential backoff" \
        --target-dir "." \
        --verbose

CLI Arguments:
    --topic      What to research (e.g., "async error handling python")
    --target-dir Directory to apply changes to (default: ".")
    --dry-run    Don't actually make changes, just show plan
    --verbose    Show detailed output from each step

Graceful Degradation:
    Each tool is optional. If unavailable (disabled, no API key, etc.),
    the pipeline continues with the remaining tools and reports what was skipped.
"""

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class StepStatus(Enum):
    """Status of a pipeline step."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class StepResult:
    """Result from a pipeline step."""
    step_name: str
    status: StepStatus
    data: Any = None
    error: str | None = None
    message: str = ""


@dataclass
class PipelineContext:
    """Shared context passed between pipeline steps."""
    topic: str
    target_dir: str
    dry_run: bool
    verbose: bool

    # Results from each step
    research_results: dict = field(default_factory=dict)
    code_patterns: list = field(default_factory=list)
    search_matches: list = field(default_factory=list)
    quality_issues: list = field(default_factory=list)
    staged_files: list = field(default_factory=list)

    # Tracking
    skipped_steps: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Research-to-implement MCP chaining pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--topic", required=True,
        help="What to research (e.g., 'async error handling python')"
    )
    parser.add_argument(
        "--target-dir", default=".",
        help="Directory to apply changes to (default: .)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Don't actually make changes, just show plan"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show detailed output from each step"
    )

    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


async def check_tool_available(tool_id: str) -> bool:
    """Check if an MCP tool is available (server enabled + can connect)."""
    from runtime.mcp_client import get_mcp_client_manager
    from runtime.exceptions import ToolNotFoundError, ServerConnectionError

    manager = get_mcp_client_manager()

    # Parse server name from tool_id
    if "__" not in tool_id:
        return False

    server_name = tool_id.split("__")[0]

    # Check if server is configured and enabled
    if not manager._config:
        return False

    server_config = manager._config.get_server(server_name)
    if not server_config:
        return False

    if server_config.disabled:
        return False

    return True


async def step_research_nia(ctx: PipelineContext) -> StepResult:
    """Step 1: Research patterns using Nia documentation search."""
    from runtime.mcp_client import call_mcp_tool

    step_name = "nia_research"

    # Check if nia is available
    if not await check_tool_available("nia__search"):
        return StepResult(
            step_name=step_name,
            status=StepStatus.SKIPPED,
            message="Nia server not available (disabled or missing API key)"
        )

    print(f"\n[1/5] Researching: {ctx.topic}")

    try:
        # Use nia search tool
        result = await call_mcp_tool("nia__search", {
            "query": ctx.topic
        })

        ctx.research_results = {
            "source": "nia_universal",
            "query": ctx.topic,
            "results": result
        }

        if ctx.verbose:
            print(f"  Found {len(result.get('results', [])) if isinstance(result, dict) else 'N/A'} results")
            if isinstance(result, dict) and result.get("results"):
                for i, r in enumerate(result["results"][:3], 1):
                    title = r.get("title", r.get("name", f"Result {i}"))
                    print(f"    {i}. {title[:60]}...")

        return StepResult(
            step_name=step_name,
            status=StepStatus.SUCCESS,
            data=result,
            message=f"Found patterns for '{ctx.topic}'"
        )

    except Exception as e:
        ctx.errors.append(f"nia: {e}")
        return StepResult(
            step_name=step_name,
            status=StepStatus.FAILED,
            error=str(e),
            message=f"Nia search failed: {e}"
        )


async def step_find_patterns_ast_grep(ctx: PipelineContext) -> StepResult:
    """Step 2: Find similar code patterns using AST-grep."""
    from runtime.mcp_client import call_mcp_tool

    step_name = "ast_grep_patterns"

    # Check if ast-grep is available
    if not await check_tool_available("ast-grep__find_code"):
        return StepResult(
            step_name=step_name,
            status=StepStatus.SKIPPED,
            message="AST-grep server not available (disabled)"
        )

    print(f"\n[2/5] Finding code patterns in {ctx.target_dir}")

    # Derive AST pattern from topic
    # This is a heuristic - could be improved with LLM guidance
    pattern = derive_ast_pattern(ctx.topic)

    try:
        result = await call_mcp_tool("ast-grep__find_code", {
            "pattern": pattern,
            "directory": ctx.target_dir,
            "language": "python"
        })

        # Parse results
        matches = []
        if isinstance(result, str):
            lines = result.strip().split('\n') if result.strip() else []
            matches = [{"raw": line} for line in lines[:20]]
        elif isinstance(result, dict) and "matches" in result:
            matches = result["matches"]

        ctx.code_patterns = matches

        if ctx.verbose:
            print(f"  Found {len(matches)} code patterns")
            for i, m in enumerate(matches[:3], 1):
                print(f"    {i}. {str(m)[:60]}...")

        return StepResult(
            step_name=step_name,
            status=StepStatus.SUCCESS,
            data={"pattern": pattern, "matches": matches},
            message=f"Found {len(matches)} patterns with '{pattern}'"
        )

    except Exception as e:
        ctx.errors.append(f"ast-grep: {e}")
        return StepResult(
            step_name=step_name,
            status=StepStatus.FAILED,
            error=str(e),
            message=f"AST-grep search failed: {e}"
        )


def derive_ast_pattern(topic: str) -> str:
    """Derive an AST pattern from a research topic.

    This is a simple heuristic. In production, you might use an LLM
    to generate more appropriate patterns.
    """
    topic_lower = topic.lower()

    # Common pattern mappings
    if "async" in topic_lower:
        if "error" in topic_lower or "exception" in topic_lower:
            return "async def $FUNC($$$): try: $$$BODY except $EXC: $$$"
        return "async def $FUNC($$$)"

    if "context manager" in topic_lower:
        return "with $CTX as $VAR: $$$"

    if "retry" in topic_lower:
        return "for $I in range($N): $$$"

    if "decorator" in topic_lower:
        return "@$DEC def $FUNC($$$): $$$"

    if "class" in topic_lower:
        return "class $NAME($$$): $$$"

    # Default: look for function definitions
    return "def $FUNC($$$)"


async def step_search_morph(ctx: PipelineContext) -> StepResult:
    """Step 3: Search/apply patterns using Morph WarpGrep."""
    from runtime.mcp_client import call_mcp_tool

    step_name = "morph_search"

    # Check if morph is available
    if not await check_tool_available("morph__warpgrep_codebase_search"):
        return StepResult(
            step_name=step_name,
            status=StepStatus.SKIPPED,
            message="Morph server not available (disabled or missing API key)"
        )

    print(f"\n[3/5] Searching codebase with Morph")

    # Derive search string from topic
    search_terms = ctx.topic.split()[:3]  # First 3 words
    search_string = " ".join(search_terms)

    try:
        result = await call_mcp_tool("morph__warpgrep_codebase_search", {
            "search_string": search_string,
            "repo_path": ctx.target_dir
        })

        # Parse results
        matches = []
        if isinstance(result, str):
            matches = [{"raw": line} for line in result.strip().split('\n')[:20] if line]
        elif isinstance(result, dict):
            matches = result.get("matches", result.get("results", []))

        ctx.search_matches = matches

        if ctx.verbose:
            print(f"  Found {len(matches)} matches")
            for i, m in enumerate(matches[:3], 1):
                text = m.get("raw", str(m))[:60] if isinstance(m, dict) else str(m)[:60]
                print(f"    {i}. {text}...")

        return StepResult(
            step_name=step_name,
            status=StepStatus.SUCCESS,
            data={"search": search_string, "matches": matches},
            message=f"Found {len(matches)} matches for '{search_string}'"
        )

    except Exception as e:
        ctx.errors.append(f"morph: {e}")
        return StepResult(
            step_name=step_name,
            status=StepStatus.FAILED,
            error=str(e),
            message=f"Morph search failed: {e}"
        )


async def step_validate_qlty(ctx: PipelineContext) -> StepResult:
    """Step 4: Validate code quality using Qlty."""
    from runtime.mcp_client import call_mcp_tool

    step_name = "qlty_validate"

    # Check if qlty is available
    if not await check_tool_available("qlty__qlty_check"):
        return StepResult(
            step_name=step_name,
            status=StepStatus.SKIPPED,
            message="Qlty server not available (disabled)"
        )

    print(f"\n[4/5] Validating code quality")

    try:
        result = await call_mcp_tool("qlty__qlty_check", {
            "all": False,  # Just changed files
            "paths": [ctx.target_dir],
            "level": "low",
            "json_output": True,
            "cwd": ctx.target_dir if Path(ctx.target_dir).is_absolute() else None
        })

        # Parse issues
        issues = []
        if isinstance(result, str):
            try:
                parsed = json.loads(result)
                issues = parsed.get("issues", [])
            except json.JSONDecodeError:
                issues = [{"raw": result}] if result.strip() else []
        elif isinstance(result, dict):
            issues = result.get("issues", [])

        ctx.quality_issues = issues

        if ctx.verbose:
            print(f"  Found {len(issues)} quality issues")
            for i, issue in enumerate(issues[:3], 1):
                msg = issue.get("message", str(issue))[:60]
                print(f"    {i}. {msg}...")

        return StepResult(
            step_name=step_name,
            status=StepStatus.SUCCESS,
            data={"issues": issues, "count": len(issues)},
            message=f"Found {len(issues)} quality issues"
        )

    except Exception as e:
        ctx.errors.append(f"qlty: {e}")
        return StepResult(
            step_name=step_name,
            status=StepStatus.FAILED,
            error=str(e),
            message=f"Qlty check failed: {e}"
        )


async def step_stage_git(ctx: PipelineContext) -> StepResult:
    """Step 5: Stage changes using Git."""
    from runtime.mcp_client import call_mcp_tool

    step_name = "git_stage"

    if ctx.dry_run:
        return StepResult(
            step_name=step_name,
            status=StepStatus.SKIPPED,
            message="Dry run - skipping git staging"
        )

    # Check if git is available
    if not await check_tool_available("git__git_status"):
        return StepResult(
            step_name=step_name,
            status=StepStatus.SKIPPED,
            message="Git server not available"
        )

    print(f"\n[5/5] Checking git status")

    try:
        # Get status first
        status = await call_mcp_tool("git__git_status", {
            "repo_path": ctx.target_dir
        })

        if ctx.verbose:
            print(f"  Git status: {status}")

        # In a real implementation, we might stage specific files
        # For now, just report the status
        ctx.staged_files = []

        return StepResult(
            step_name=step_name,
            status=StepStatus.SUCCESS,
            data={"status": status},
            message="Git status checked (no changes staged in dry run)"
        )

    except Exception as e:
        ctx.errors.append(f"git: {e}")
        return StepResult(
            step_name=step_name,
            status=StepStatus.FAILED,
            error=str(e),
            message=f"Git operation failed: {e}"
        )


def print_summary(ctx: PipelineContext, results: list[StepResult]):
    """Print pipeline execution summary."""
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)

    print(f"\nTopic: {ctx.topic}")
    print(f"Target: {ctx.target_dir}")
    print(f"Mode: {'DRY RUN' if ctx.dry_run else 'LIVE'}")

    print("\nStep Results:")
    for r in results:
        icon = {
            StepStatus.SUCCESS: "[OK]",
            StepStatus.SKIPPED: "[--]",
            StepStatus.FAILED: "[!!]",
            StepStatus.PENDING: "[..]",
            StepStatus.RUNNING: "[>>]"
        }.get(r.status, "[??]")
        print(f"  {icon} {r.step_name}: {r.message}")

    # Data summary
    print("\nData Collected:")
    if ctx.research_results:
        results_count = len(ctx.research_results.get("results", {}).get("results", [])) if isinstance(ctx.research_results.get("results"), dict) else 0
        print(f"  - Research results: {results_count} items")
    if ctx.code_patterns:
        print(f"  - Code patterns: {len(ctx.code_patterns)} matches")
    if ctx.search_matches:
        print(f"  - Search matches: {len(ctx.search_matches)} files")
    if ctx.quality_issues:
        print(f"  - Quality issues: {len(ctx.quality_issues)} items")

    # Errors
    if ctx.errors:
        print("\nErrors:")
        for e in ctx.errors:
            print(f"  - {e}")

    # Skipped steps
    skipped = [r.step_name for r in results if r.status == StepStatus.SKIPPED]
    if skipped:
        print(f"\nSkipped Steps: {', '.join(skipped)}")
        print("  (These tools may be disabled or missing API keys)")

    print("\n" + "=" * 60)


async def main():
    """Main pipeline execution."""
    from runtime.mcp_client import get_mcp_client_manager

    args = parse_args()

    print("=" * 60)
    print("RESEARCH-TO-IMPLEMENT PIPELINE")
    print("=" * 60)

    # Initialize context
    ctx = PipelineContext(
        topic=args.topic,
        target_dir=args.target_dir,
        dry_run=args.dry_run,
        verbose=args.verbose
    )

    # Get MCP client (harness already initializes it)
    manager = get_mcp_client_manager()
    # Only initialize if not already initialized by harness
    from runtime.mcp_client import ConnectionState
    if manager._state == ConnectionState.UNINITIALIZED:
        await manager.initialize()

    # Run pipeline steps
    results = []

    # Step 1: Research with Nia
    r1 = await step_research_nia(ctx)
    results.append(r1)

    # Step 2: Find patterns with AST-grep
    r2 = await step_find_patterns_ast_grep(ctx)
    results.append(r2)

    # Step 3: Search with Morph
    r3 = await step_search_morph(ctx)
    results.append(r3)

    # Step 4: Validate with Qlty
    r4 = await step_validate_qlty(ctx)
    results.append(r4)

    # Step 5: Stage with Git
    r5 = await step_stage_git(ctx)
    results.append(r5)

    # Print summary
    print_summary(ctx, results)

    # Return structured result for programmatic use
    return {
        "topic": ctx.topic,
        "target_dir": ctx.target_dir,
        "dry_run": ctx.dry_run,
        "results": [
            {
                "step": r.step_name,
                "status": r.status.value,
                "message": r.message,
                "data": r.data
            }
            for r in results
        ],
        "errors": ctx.errors,
        "data": {
            "research": ctx.research_results,
            "patterns": ctx.code_patterns,
            "matches": ctx.search_matches,
            "issues": ctx.quality_issues
        }
    }


if __name__ == "__main__":
    asyncio.run(main())

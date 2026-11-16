#!/usr/bin/env python3
"""Test Harness for Research-to-Implement Pipeline.

DESCRIPTION: Sets up isolated test environment, runs the pipeline against sandbox code,
and verifies results. Designed to test graceful degradation when tools are unavailable.

USAGE:
    # Run full test suite
    uv run python -m runtime.harness scripts/test_research_pipeline.py

    # Run specific test
    uv run python -m runtime.harness scripts/test_research_pipeline.py --test async

    # Keep sandbox after test (for inspection)
    uv run python -m runtime.harness scripts/test_research_pipeline.py --keep-sandbox

    # Verbose output
    uv run python -m runtime.harness scripts/test_research_pipeline.py --verbose

Test Cases:
    1. async_patterns - Research async error handling patterns
    2. context_managers - Research context manager patterns
    3. retry_logic - Research retry with exponential backoff
    4. graceful_degradation - Verify pipeline works with tools disabled
"""

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


# Test configurations
TEST_CASES = {
    "async_patterns": {
        "topic": "async error handling python",
        "description": "Find async patterns with error handling",
        "expected_ast_pattern": "async def",
    },
    "context_managers": {
        "topic": "context manager patterns python",
        "description": "Find context manager usage patterns",
        "expected_ast_pattern": "with $CTX",
    },
    "retry_logic": {
        "topic": "retry with exponential backoff",
        "description": "Find retry loop patterns",
        "expected_ast_pattern": "for $I in range",
    },
    "graceful_degradation": {
        "topic": "error handling patterns",
        "description": "Verify pipeline handles unavailable tools",
        "expected_ast_pattern": "try:",
    },
}

# Sample code to copy into sandbox
SAMPLE_CODE = '''"""Sample code for testing - auto-generated."""

import time


def fetch_data(url):
    """Fetch without error handling."""
    import urllib.request
    response = urllib.request.urlopen(url)
    return response.read()


def process_items(items):
    """Process synchronously."""
    results = []
    for item in items:
        time.sleep(0.1)
        results.append(item.upper())
    return results


def read_file(path):
    """Read without context manager."""
    f = open(path, 'r')
    content = f.read()
    f.close()
    return content


async def async_fetch(url):
    """Async fetch example."""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.text()
    except Exception as e:
        raise RuntimeError(f"Fetch failed: {e}")


def retry_operation(func, max_retries=3):
    """Retry logic example."""
    for i in range(max_retries):
        try:
            return func()
        except Exception:
            if i == max_retries - 1:
                raise
            time.sleep(2 ** i)
'''


def parse_args():
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Test harness for research pipeline")
    parser.add_argument(
        "--test",
        choices=list(TEST_CASES.keys()) + ["all"],
        default="all",
        help="Which test case to run"
    )
    parser.add_argument(
        "--keep-sandbox",
        action="store_true",
        help="Keep sandbox directory after test"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output"
    )
    parser.add_argument(
        "--sandbox-dir",
        help="Use existing directory as sandbox (don't create temp)"
    )

    args_to_parse = [arg for arg in sys.argv[1:] if not arg.endswith(".py")]
    return parser.parse_args(args_to_parse)


async def setup_sandbox(sandbox_dir: Path | None = None) -> Path:
    """Create isolated test sandbox with sample code.

    Returns:
        Path to sandbox directory
    """
    if sandbox_dir:
        sandbox = sandbox_dir
        sandbox.mkdir(parents=True, exist_ok=True)
    else:
        sandbox = Path(tempfile.mkdtemp(prefix="pipeline_test_"))

    # Create sample code file
    sample_file = sandbox / "sample_code.py"
    sample_file.write_text(SAMPLE_CODE)

    # Create additional test files
    (sandbox / "utils.py").write_text('''"""Utility functions."""

def helper():
    """Helper function."""
    return True

def process(data):
    """Process data."""
    try:
        return data.strip()
    except:
        return None
''')

    (sandbox / "config.py").write_text('''"""Configuration."""

# Hardcoded values (bad pattern)
DATABASE_HOST = "localhost"
DATABASE_PORT = 5432
API_KEY = "hardcoded_key"

def get_config():
    return {
        "host": DATABASE_HOST,
        "port": DATABASE_PORT,
    }
''')

    print(f"  Sandbox created: {sandbox}")
    return sandbox


def cleanup_sandbox(sandbox: Path, keep: bool = False):
    """Clean up test sandbox."""
    if keep:
        print(f"  Keeping sandbox for inspection: {sandbox}")
        return

    if sandbox.exists() and str(sandbox).startswith(tempfile.gettempdir()):
        shutil.rmtree(sandbox)
        print(f"  Sandbox cleaned up: {sandbox}")


async def run_pipeline(topic: str, target_dir: str, verbose: bool = False) -> dict[str, Any]:
    """Run the research-implement pipeline.

    Args:
        topic: Research topic
        target_dir: Directory to analyze
        verbose: Show detailed output

    Returns:
        Pipeline result dictionary
    """
    # Import here to avoid circular deps
    from scripts.research_implement_pipeline import (
        PipelineContext,
        step_research_nia,
        step_find_patterns_ast_grep,
        step_search_morph,
        step_validate_qlty,
        step_stage_git,
    )
    from runtime.mcp_client import get_mcp_client_manager, ConnectionState

    # Get MCP client (harness already initializes it)
    manager = get_mcp_client_manager()
    # Only initialize if not already initialized by harness
    if manager._state == ConnectionState.UNINITIALIZED:
        await manager.initialize()

    # Create context
    ctx = PipelineContext(
        topic=topic,
        target_dir=target_dir,
        dry_run=True,  # Always dry run in tests
        verbose=verbose
    )

    # Run steps
    results = []

    r1 = await step_research_nia(ctx)
    results.append({"step": "nia", "status": r1.status.value, "message": r1.message})

    r2 = await step_find_patterns_ast_grep(ctx)
    results.append({"step": "ast_grep", "status": r2.status.value, "message": r2.message})

    r3 = await step_search_morph(ctx)
    results.append({"step": "morph", "status": r3.status.value, "message": r3.message})

    r4 = await step_validate_qlty(ctx)
    results.append({"step": "qlty", "status": r4.status.value, "message": r4.message})

    r5 = await step_stage_git(ctx)
    results.append({"step": "git", "status": r5.status.value, "message": r5.message})

    return {
        "topic": topic,
        "target_dir": target_dir,
        "results": results,
        "errors": ctx.errors,
        "data": {
            "research_count": len(ctx.research_results) if ctx.research_results else 0,
            "pattern_count": len(ctx.code_patterns),
            "match_count": len(ctx.search_matches),
            "issue_count": len(ctx.quality_issues),
        }
    }


async def run_test_case(test_name: str, test_config: dict, sandbox: Path, verbose: bool) -> dict:
    """Run a single test case.

    Args:
        test_name: Name of the test
        test_config: Test configuration
        sandbox: Path to sandbox directory
        verbose: Show detailed output

    Returns:
        Test result dictionary
    """
    print(f"\n{'=' * 60}")
    print(f"TEST: {test_name}")
    print(f"  Description: {test_config['description']}")
    print(f"  Topic: {test_config['topic']}")
    print(f"{'=' * 60}")

    try:
        result = await run_pipeline(
            topic=test_config["topic"],
            target_dir=str(sandbox),
            verbose=verbose
        )

        # Analyze results
        passed_steps = sum(1 for r in result["results"] if r["status"] == "success")
        skipped_steps = sum(1 for r in result["results"] if r["status"] == "skipped")
        failed_steps = sum(1 for r in result["results"] if r["status"] == "failed")

        # Test passes if:
        # - At least one step succeeded OR
        # - All steps gracefully degraded (skipped, not failed)
        success = passed_steps > 0 or (failed_steps == 0 and skipped_steps > 0)

        print(f"\n  Results: {passed_steps} passed, {skipped_steps} skipped, {failed_steps} failed")
        print(f"  Status: {'PASS' if success else 'FAIL'}")

        if verbose:
            for r in result["results"]:
                icon = {"success": "[OK]", "skipped": "[--]", "failed": "[!!]"}.get(r["status"], "[??]")
                print(f"    {icon} {r['step']}: {r['message']}")

        return {
            "test": test_name,
            "success": success,
            "passed_steps": passed_steps,
            "skipped_steps": skipped_steps,
            "failed_steps": failed_steps,
            "details": result
        }

    except Exception as e:
        print(f"  ERROR: {e}")
        return {
            "test": test_name,
            "success": False,
            "error": str(e)
        }


async def main():
    """Main test execution."""
    args = parse_args()

    print("=" * 60)
    print("RESEARCH-IMPLEMENT PIPELINE TEST HARNESS")
    print("=" * 60)

    # Determine which tests to run
    if args.test == "all":
        tests_to_run = list(TEST_CASES.keys())
    else:
        tests_to_run = [args.test]

    print(f"\nTests to run: {', '.join(tests_to_run)}")

    # Setup sandbox
    print("\nSetting up test sandbox...")
    sandbox_path = Path(args.sandbox_dir) if args.sandbox_dir else None
    sandbox = await setup_sandbox(sandbox_path)

    # Run tests
    test_results = []
    try:
        for test_name in tests_to_run:
            test_config = TEST_CASES[test_name]
            result = await run_test_case(test_name, test_config, sandbox, args.verbose)
            test_results.append(result)

    finally:
        # Cleanup
        print("\nCleaning up...")
        cleanup_sandbox(sandbox, args.keep_sandbox)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in test_results if r.get("success", False))
    total = len(test_results)

    for r in test_results:
        icon = "[OK]" if r.get("success") else "[!!]"
        print(f"  {icon} {r['test']}")

    print(f"\nOverall: {passed}/{total} tests passed")
    print("=" * 60)

    # Return results for programmatic use
    return {
        "passed": passed,
        "total": total,
        "success": passed == total,
        "results": test_results
    }


if __name__ == "__main__":
    asyncio.run(main())

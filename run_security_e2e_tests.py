#!/usr/bin/env python3
"""Test runner for security E2E integration tests.

Executes the comprehensive security test suite and reports results.
"""

import subprocess
import sys


def main():
    """Run security E2E tests and report results."""
    print("=" * 80)
    print("Security E2E Integration Test Suite")
    print("=" * 80)
    print()
    print("Running comprehensive security tests...")
    print("Testing: Path validation, async locks, cross-component integration")
    print()

    # Run pytest
    cmd = [
        "uv",
        "run",
        "pytest",
        "tests/integration/test_security_e2e.py",
        "-v",
        "--tb=short",
    ]

    try:
        result = subprocess.run(cmd, cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit")
        sys.exit(result.returncode)
    except Exception as e:
        print(f"Error running tests: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

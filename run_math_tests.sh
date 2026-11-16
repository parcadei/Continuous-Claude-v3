#!/bin/bash
# Wrapper script for mutation testing - runs from project root
PROJECT_DIR="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
cd "$PROJECT_DIR"

exec uv run python -m pytest tests/unit/test_math_scratchpad.py tests/unit/test_math_scratchpad_bugs.py -x -q --timeout=30 --ignore=tests/integration

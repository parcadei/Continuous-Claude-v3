#!/bin/bash
# Test runner for Phase 6: Agent Scope Injection

set -e

echo "=== Phase 6: Agent Scope Injection Tests ==="
echo ""

cd "$(dirname "$0")"

echo "Running pytest tests..."
uv run pytest tests/unit/test_agent_scope.py -v

echo ""
echo "Running QLTY check..."
qlty check scripts/agentica/agent_scope.py

echo ""
echo "=== All tests passed! ==="

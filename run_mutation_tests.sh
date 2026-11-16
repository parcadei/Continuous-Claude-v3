#!/bin/bash
# Run mutation tests and report results

cd "$(dirname "$0")"

echo "========================================================================"
echo "Running TDD Security Mutation Tests"
echo "========================================================================"
echo ""
echo "These tests SHOULD FAIL initially to prove mutation gaps exist."
echo ""

uv run pytest tests/unit/test_security_mutation.py -v --tb=short

echo ""
echo "========================================================================"
echo "Test Execution Complete"
echo "========================================================================"

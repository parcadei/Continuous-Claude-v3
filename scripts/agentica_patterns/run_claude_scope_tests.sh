#!/bin/bash
#
# Run end-to-end tests for claude_scope with server management
#
# Usage:
#   bash scripts/agentica/run_claude_scope_tests.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "========================================="
echo "Claude Scope E2E Test Runner"
echo "========================================="

# Check if servers are running
PROXY_RUNNING=false
SERVER_RUNNING=false

if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    PROXY_RUNNING=true
fi

if curl -s http://localhost:2345/health > /dev/null 2>&1; then
    SERVER_RUNNING=true
fi

# Start servers if needed
START_PROXY=false
START_SERVER=false

if [ "$PROXY_RUNNING" = false ]; then
    echo ""
    echo "Starting Claude proxy on port 8080..."
    cd "$PROJECT_DIR"
    uv run python scripts/agentica/claude_proxy.py --port 8080 > /tmp/claude_proxy.log 2>&1 &
    PROXY_PID=$!
    START_PROXY=true
    echo "Started proxy (PID: $PROXY_PID)"

    # Wait for proxy to be ready
    echo "Waiting for proxy to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:8080/health > /dev/null 2>&1; then
            echo "✓ Proxy ready"
            break
        fi
        sleep 1
    done
else
    echo "✓ Claude proxy already running on port 8080"
fi

if [ "$SERVER_RUNNING" = false ]; then
    echo ""
    echo "Starting Agentica server on port 2345..."
    cd "$PROJECT_DIR/workspace/agentica-research/agentica-server"
    INFERENCE_ENDPOINT_URL=http://localhost:8080/v1/chat/completions uv run agentica-server --port 2345 > /tmp/agentica_server.log 2>&1 &
    SERVER_PID=$!
    START_SERVER=true
    echo "Started server (PID: $SERVER_PID)"

    # Wait for server to be ready
    echo "Waiting for server to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:2345/health > /dev/null 2>&1; then
            echo "✓ Server ready"
            break
        fi
        sleep 1
    done
    cd "$PROJECT_DIR"
else
    echo "✓ Agentica server already running on port 2345"
fi

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up..."
    if [ "$START_PROXY" = true ] && [ -n "$PROXY_PID" ]; then
        echo "Stopping proxy (PID: $PROXY_PID)"
        kill $PROXY_PID 2>/dev/null || true
    fi
    if [ "$START_SERVER" = true ] && [ -n "$SERVER_PID" ]; then
        echo "Stopping server (PID: $SERVER_PID)"
        kill $SERVER_PID 2>/dev/null || true
    fi
}

trap cleanup EXIT

# Run tests
echo ""
echo "========================================="
echo "Running Tests"
echo "========================================="
cd "$PROJECT_DIR"

# Option 1: Run with pytest
echo "Running with pytest..."
S_M_BASE_URL=http://localhost:2345 uv run pytest tests/integration/test_claude_scope_e2e.py -v -s

# Exit code from pytest
EXIT_CODE=$?

echo ""
echo "========================================="
echo "Test Results"
echo "========================================="

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ ALL TESTS PASSED"
else
    echo "❌ TESTS FAILED (exit code: $EXIT_CODE)"
    echo ""
    echo "Check logs:"
    echo "  Proxy: /tmp/claude_proxy.log"
    echo "  Server: /tmp/agentica_server.log"
fi

exit $EXIT_CODE

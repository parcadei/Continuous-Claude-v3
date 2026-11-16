#!/bin/bash
#
# Check if Claude proxy and Agentica server are running
#

echo "Checking servers..."
echo ""

# Check proxy
echo -n "Claude proxy (port 8080): "
if curl -s http://localhost:8080/health > /dev/null 2>&1; then
    echo "✓ RUNNING"
    PROXY_STATUS=$(curl -s http://localhost:8080/health)
    echo "  Status: $PROXY_STATUS"
else
    echo "❌ NOT RUNNING"
    echo "  Start with: uv run python scripts/agentica/claude_proxy.py --port 8080"
fi

echo ""

# Check server
echo -n "Agentica server (port 2345): "
if curl -s http://localhost:2345/health > /dev/null 2>&1; then
    echo "✓ RUNNING"
    SERVER_STATUS=$(curl -s http://localhost:2345/health)
    echo "  Status: $SERVER_STATUS"
else
    echo "❌ NOT RUNNING"
    echo "  Start with: cd workspace/agentica-research/agentica-server && \\"
    echo "    INFERENCE_ENDPOINT_URL=http://localhost:8080/v1/chat/completions uv run agentica-server --port 2345"
fi

echo ""
echo "Environment:"
echo "  S_M_BASE_URL: ${S_M_BASE_URL:-NOT SET}"
echo ""

if curl -s http://localhost:8080/health > /dev/null 2>&1 && \
   curl -s http://localhost:2345/health > /dev/null 2>&1; then
    echo "✓ All servers ready for testing"
    exit 0
else
    echo "❌ Servers not ready"
    exit 1
fi

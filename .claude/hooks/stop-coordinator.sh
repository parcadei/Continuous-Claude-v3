#!/bin/bash
# Stop Coordinator - Pattern-aware hook for multi-agent orchestration
# Early exit in bash to avoid Node startup latency when no pattern is active

# Early exit if no pattern is active - skip Node entirely (~500ms saved)
if [[ -z "$PATTERN_TYPE" ]]; then
  echo '{}'
  exit 0
fi

# Only invoke TypeScript if a multi-agent pattern is running
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
cat | npx tsx src/stop-coordinator.ts

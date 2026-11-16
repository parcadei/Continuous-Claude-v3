#!/bin/bash
set -e
# Task Router - Intercepts Task tool to route to Agentica
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
export CLAUDE_PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
cd "$SCRIPT_DIR"
cat | npx tsx src/task-router.ts

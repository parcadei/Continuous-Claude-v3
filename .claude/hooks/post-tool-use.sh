#!/bin/bash
# PostToolUse Router - Shell wrapper for post-tool-use.ts
# Phase 56 of pattern-aware hooks plan

set -e

# Determine project directory
if [ -n "$CLAUDE_PROJECT_DIR" ]; then
    PROJECT_DIR="$CLAUDE_PROJECT_DIR"
else
    # Fallback: script is in .claude/hooks/
    PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
fi

cd "$PROJECT_DIR/.claude/hooks"
cat | npx tsx src/post-tool-use.ts

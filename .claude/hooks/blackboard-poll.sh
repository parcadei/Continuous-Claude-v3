#!/bin/bash
# Pre-tool-use hook for blackboard polling
# Polls shared blackboard and injects relevant entries as system reminder

set -e
cd "$CLAUDE_PROJECT_DIR/.claude/hooks"
cat | npx tsx src/blackboard-poll.ts

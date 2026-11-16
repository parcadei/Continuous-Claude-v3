#!/bin/bash
set -e
cd ~/.claude/hooks
cat | node dist/subagent-stop-continuity.mjs

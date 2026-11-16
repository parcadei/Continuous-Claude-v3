#!/bin/bash
# Move updated files to replace originals

cd /Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit

mv docs/refactor/17-upgrade-path-NEW.md docs/refactor/17-upgrade-path.md
mv docs/refactor/22-migration-rollback-NEW.md docs/refactor/22-migration-rollback.md
mv docs/refactor/15-security-NEW.md docs/refactor/15-security.md
mv docs/refactor/13-mcp-offline-NEW.md docs/refactor/13-mcp-offline.md

echo "Files moved successfully"

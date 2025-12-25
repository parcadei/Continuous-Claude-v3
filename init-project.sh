#!/bin/bash
# Initialize a project for Continuous Claude
# Run this in any project to set up required directories and database.
#
# Usage:
#   cd /path/to/your/project
#   /path/to/claude-continuity-kit/init-project.sh
#
# Or if you have the kit in PATH:
#   init-project.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(pwd)"

echo ""
echo "┌─────────────────────────────────────────────────────────────┐"
echo "│  Continuous Claude - Project Initialization                 │"
echo "└─────────────────────────────────────────────────────────────┘"
echo ""
echo "Project: $PROJECT_DIR"
echo ""

# Create directory structure
echo "Creating directory structure..."
mkdir -p "$PROJECT_DIR/thoughts/ledgers"
mkdir -p "$PROJECT_DIR/thoughts/shared/handoffs"
mkdir -p "$PROJECT_DIR/thoughts/shared/plans"
mkdir -p "$PROJECT_DIR/.claude/cache/artifact-index"

# Initialize the Artifact Index database (skip if exists - brownfield safe)
echo "Initializing Artifact Index database..."
if [ -f "$PROJECT_DIR/.claude/cache/artifact-index/context.db" ]; then
    echo "  ✓ Database already exists, skipping (brownfield project)"
elif [ -f "$SCRIPT_DIR/scripts/artifact_schema.sql" ]; then
    sqlite3 "$PROJECT_DIR/.claude/cache/artifact-index/context.db" < "$SCRIPT_DIR/scripts/artifact_schema.sql"
    echo "  ✓ Database created at .claude/cache/artifact-index/context.db"
else
    echo "  ⚠ Schema not found - database not created"
    echo "    Run manually: sqlite3 .claude/cache/artifact-index/context.db < scripts/artifact_schema.sql"
fi

# Add to .gitignore if it exists
if [ -f "$PROJECT_DIR/.gitignore" ]; then
    if ! grep -q ".claude/cache/" "$PROJECT_DIR/.gitignore" 2>/dev/null; then
        echo "" >> "$PROJECT_DIR/.gitignore"
        echo "# Continuous Claude cache (local only)" >> "$PROJECT_DIR/.gitignore"
        echo ".claude/cache/" >> "$PROJECT_DIR/.gitignore"
        echo "  ✓ Added .claude/cache/ to .gitignore"
    fi
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Project initialized! Directory structure:"
echo ""
echo "  thoughts/"
echo "  ├── ledgers/           ← Continuity ledgers (git tracked)"
echo "  └── shared/"
echo "      ├── handoffs/      ← Session handoffs (git tracked)"
echo "      └── plans/         ← Implementation plans (git tracked)"
echo ""
echo "  .claude/"
echo "  └── cache/"
echo "      └── artifact-index/"
echo "          └── context.db ← Search index (gitignored)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "  1. Start Claude Code in this project"
echo "  2. Use /continuity_ledger to create your first ledger"
echo "  3. Hooks will now work fully!"
echo ""

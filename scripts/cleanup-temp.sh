#!/bin/bash
# cleanup-temp.sh - Remove stale Claude temp files
#
# Usage: ./scripts/cleanup-temp.sh [--dry-run]
#
# These temp files are created by Claude Code sessions but not always cleaned up.
# Safe to run periodically (e.g., weekly or on system startup).

set -e

DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "DRY RUN - no files will be deleted"
    echo ""
fi

# Locations where temp files accumulate
LOCATIONS=(
    "$HOME"
    "$HOME/continuous-claude/opc"
    "$CLAUDE_PROJECT_DIR/opc"
)

TOTAL=0

for loc in "${LOCATIONS[@]}"; do
    if [[ -d "$loc" ]]; then
        count=$(ls -1 "$loc"/tmpclaude-*-cwd 2>/dev/null | wc -l || echo 0)
        if [[ $count -gt 0 ]]; then
            echo "Found $count temp files in $loc"
            if [[ "$DRY_RUN" == "false" ]]; then
                rm -f "$loc"/tmpclaude-*-cwd
                echo "  Deleted."
            fi
            TOTAL=$((TOTAL + count))
        fi
    fi
done

if [[ $TOTAL -gt 0 ]]; then
    echo "Cleaned $TOTAL temp files."
elif [[ "$DRY_RUN" == "true" ]]; then
    echo "No temp files found."
fi
# Silent when nothing to clean (ideal for shell startup)

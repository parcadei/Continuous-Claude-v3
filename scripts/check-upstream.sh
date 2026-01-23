#!/bin/bash
# check-upstream.sh - Check for updates from upstream (parcadei) repo
#
# Usage: ./scripts/check-upstream.sh [--diff] [--merge]
#
# Options:
#   --diff   Show full diff of changes
#   --merge  Create test branch and attempt merge

set -e

# Configuration
UPSTREAM_REMOTE="origin"
FORK_REMOTE="fork"
MAIN_BRANCH="main"

# Files with local customizations to watch
WATCH_FILES=(
    "opc/scripts/core/memory_daemon.py"
    "docker/init-schema.sql"
    "docker/docker-compose.yml"
)

echo "========================================"
echo "  Upstream Update Checker"
echo "========================================"
echo ""

# Fetch upstream
echo "Fetching from upstream (${UPSTREAM_REMOTE})..."
git fetch ${UPSTREAM_REMOTE} --quiet

# Check for new commits
NEW_COMMITS=$(git log ${MAIN_BRANCH}..${UPSTREAM_REMOTE}/${MAIN_BRANCH} --oneline 2>/dev/null || echo "")

if [ -z "$NEW_COMMITS" ]; then
    echo ""
    echo "[OK] You're up to date with upstream!"
    exit 0
fi

# Count new commits
COMMIT_COUNT=$(echo "$NEW_COMMITS" | wc -l | tr -d ' ')
echo ""
echo "[!] Found ${COMMIT_COUNT} new commit(s) from upstream:"
echo ""
echo "$NEW_COMMITS"
echo ""

# Check if watched files are affected
echo "Checking impact on your customized files..."
echo ""

HAS_AFFECTED=0
for file in "${WATCH_FILES[@]}"; do
    if git diff ${MAIN_BRANCH}..${UPSTREAM_REMOTE}/${MAIN_BRANCH} --name-only 2>/dev/null | grep -q "$file"; then
        echo "  [!] CHANGED: $file"
        HAS_AFFECTED=1
    fi
done

if [ $HAS_AFFECTED -eq 0 ]; then
    echo "  [OK] None of your customized files are affected"
fi

echo ""

# Show summary stats
echo "Change summary:"
git diff ${MAIN_BRANCH}..${UPSTREAM_REMOTE}/${MAIN_BRANCH} --stat 2>/dev/null | tail -1
echo ""

# Handle --diff flag
if [[ "$1" == "--diff" ]]; then
    echo "Full diff:"
    echo ""
    git diff ${MAIN_BRANCH}..${UPSTREAM_REMOTE}/${MAIN_BRANCH}
    exit 0
fi

# Handle --merge flag
if [[ "$1" == "--merge" ]]; then
    echo "Creating test branch for merge..."

    TEST_BRANCH="test-upstream-merge-$(date +%Y%m%d-%H%M%S)"
    git checkout -b "$TEST_BRANCH"

    echo "Attempting merge..."
    if git merge ${UPSTREAM_REMOTE}/${MAIN_BRANCH} --no-edit; then
        echo ""
        echo "[OK] Merge successful!"
        echo ""
        echo "Next steps:"
        echo "  1. Test your setup (run daemon, check hooks)"
        echo "  2. If good:  git checkout main && git merge $TEST_BRANCH && git push fork main"
        echo "  3. If bad:   git checkout main && git branch -D $TEST_BRANCH"
    else
        echo ""
        echo "[ERROR] Merge has conflicts"
        echo ""
        echo "Conflicting files:"
        git diff --name-only --diff-filter=U
        echo ""
        echo "To resolve:"
        echo "  1. Edit conflicting files (keep your customizations)"
        echo "  2. git add <resolved-files>"
        echo "  3. git commit"
        echo ""
        echo "To abort:"
        echo "  git merge --abort && git checkout main && git branch -D $TEST_BRANCH"
    fi
    exit 0
fi

# Default: show next steps
echo "Next steps:"
echo "  1. Review changes:    ./scripts/check-upstream.sh --diff"
echo "  2. Try merge:         ./scripts/check-upstream.sh --merge"
echo "  3. Or cherry-pick:    git cherry-pick <commit-hash>"
echo ""

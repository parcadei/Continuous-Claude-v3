# Fork Sync Guide

How to safely pull updates from the upstream `parcadei/Continuous-Claude-v3` repo while preserving your local customizations.

## Quick Reference

```bash
# Check for updates (safe, no changes)
# On Windows Git Bash, use 'source' to run the script:
cd C:\Users\david.hayes\continuous-claude
source scripts/check-upstream.sh

# See full diff
source scripts/check-upstream.sh --diff

# Attempt merge on test branch
source scripts/check-upstream.sh --merge

# Alternative: run directly with bash
bash -c 'cd /c/Users/david.hayes/continuous-claude && source scripts/check-upstream.sh'
```

## Understanding Your Remotes

| Remote | URL | Purpose |
|--------|-----|---------|
| `origin` | `github.com/parcadei/Continuous-Claude-v3` | Upstream (source of updates) |
| `fork` | `github.com/Rev4nchist/Continuous-Claude-v3` | Your fork (push here) |

## Files With Local Customizations

These files have your customizations - review merge conflicts carefully:

| File | Customization |
|------|---------------|
| `opc/scripts/core/memory_daemon.py` | Session resurrection logic |
| `docker/init-schema.sql` | `last_activity_at`, `memory_extracted_at` columns |
| `TEAMMATE-SETUP.md` | Your onboarding docs |

## Workflow Options

### Option 1: Full Merge (Trust All Changes)

Use when upstream changes don't conflict with your customizations.

```bash
# 1. Fetch and review
git fetch origin
git log main..origin/main --oneline

# 2. Merge
git merge origin/main

# 3. Push to your fork
git push fork main
```

### Option 2: Safe Test Merge (Recommended)

Use when you want to test before committing to main.

```bash
# 1. Create test branch
git checkout -b test-upstream-merge

# 2. Attempt merge
git merge origin/main

# 3. If conflicts, resolve them:
#    - Edit files, keeping your customizations
#    - git add <resolved-files>
#    - git commit

# 4. Test everything
#    - Start daemon: cd opc && uv run python scripts/core/memory_daemon.py status
#    - Check hooks work
#    - Verify database connections

# 5a. If good - apply to main:
git checkout main
git merge test-upstream-merge
git push fork main
git branch -d test-upstream-merge

# 5b. If bad - abandon:
git checkout main
git branch -D test-upstream-merge
```

### Option 3: Cherry-Pick Specific Commits

Use when you only want specific changes from upstream.

```bash
# 1. See available commits
git fetch origin
git log main..origin/main --oneline

# 2. Pick the ones you want
git cherry-pick abc1234
git cherry-pick def5678

# 3. Push
git push fork main
```

### Option 4: Manual Integration

Use for complex conflicts or when you want full control.

```bash
# 1. View the upstream file
git show origin/main:path/to/file.py > /tmp/upstream-version.py

# 2. Compare with yours
diff opc/scripts/core/memory_daemon.py /tmp/upstream-version.py

# 3. Manually copy what you want
# Edit your file, adding the parts you need

# 4. Commit and push
git add -p  # Interactive staging
git commit -m "feat: integrate upstream changes for X"
git push fork main
```

## Handling Merge Conflicts

When git reports conflicts:

```
CONFLICT (content): Merge conflict in opc/scripts/core/memory_daemon.py
```

### Resolution Steps

1. **Open the conflicting file** - Look for conflict markers:
   ```python
   <<<<<<< HEAD
   # Your version (keep this if it's your customization)
   def pg_get_stale_sessions():
       # Your session resurrection logic
   =======
   # Upstream version
   def pg_get_stale_sessions():
       # Their simpler version
   >>>>>>> origin/main
   ```

2. **Decide what to keep:**
   - Keep yours if it's a deliberate customization
   - Keep theirs if it's a bug fix you want
   - Merge both if they're complementary changes

3. **Remove conflict markers** and save

4. **Stage and commit:**
   ```bash
   git add opc/scripts/core/memory_daemon.py
   git commit -m "merge: integrate upstream, preserve session resurrection"
   ```

## Automated Update Checking

### Using the Script

```bash
# Make executable (first time only)
chmod +x scripts/check-upstream.sh

# Run check
./scripts/check-upstream.sh
```

### Sample Output

```
========================================
  Upstream Update Checker
========================================

Fetching from upstream (origin)...
Found 3 new commit(s) from upstream:

abc1234 fix: handle edge case in memory extraction
def5678 feat: add new recall option
ghi9012 docs: update README

Checking impact on your customized files...

  ⚠ CHANGED: opc/scripts/core/memory_daemon.py

Change summary:
 4 files changed, 52 insertions(+), 12 deletions(-)

Next steps:
  1. Review changes:    ./scripts/check-upstream.sh --diff
  2. Try merge:         ./scripts/check-upstream.sh --merge
  3. Or cherry-pick:    git cherry-pick <commit-hash>
```

## Best Practices

### Before Merging

1. **Commit your local changes first** - Don't merge with uncommitted work
2. **Read the upstream changelog** - Understand what changed and why
3. **Check for breaking changes** - Look at schema changes, API changes

### After Merging

1. **Run the daemon** - Verify it starts without errors
2. **Test memory extraction** - Make sure session resurrection still works
3. **Check database** - Verify schema is correct

### If Something Breaks

```bash
# Undo the last merge (if not pushed yet)
git reset --hard HEAD~1

# Or revert a pushed merge
git revert -m 1 <merge-commit-hash>
git push fork main
```

## Keeping Track of Divergence

To see how far your fork has diverged:

```bash
# Commits you have that upstream doesn't
git log origin/main..main --oneline

# Commits upstream has that you don't
git log main..origin/main --oneline

# Visual graph
git log --oneline --graph --all --decorate | head -20
```

## Schedule Regular Syncs

Consider checking for updates weekly:

```bash
# Add to your Monday routine
cd ~/continuous-claude
./scripts/check-upstream.sh
```

Or set up a git alias:

```bash
git config alias.upstream-check '!./scripts/check-upstream.sh'

# Then just run:
git upstream-check
```

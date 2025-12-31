---
name: upgrade-claude-documentation
description: Recursively update CLAUDE.md files across the repository after major implementation changes
---

# Upgrade Claude Documentation

Update CLAUDE.md files throughout the repository to reflect implementation changes. Works bottom-up across 3 directory levels.

## When to Use

- After completing a major feature implementation
- After significant refactoring
- After adding new directories or modules
- When asked to "update claude docs", "refresh documentation", or "sync claude.md"
- Before creating a PR for substantial changes

## Instructions

### Step 1: Identify Changed Areas

Determine which directories were affected by recent changes:

```bash
# Check recent changes
git diff --name-only HEAD~5 | cut -d'/' -f1-2 | sort -u

# Or check uncommitted changes
git status --short | awk '{print $2}' | cut -d'/' -f1-2 | sort -u
```

### Step 2: Update Bottom-Up (Level 3 → Level 1)

Update CLAUDE.md files starting from the deepest affected directories and working up.

**Level 3 directories** (deepest - update first):
- `thoughts/shared/plans/`
- `thoughts/shared/research/`
- `thoughts/shared/handoffs/`
- Any 3-level deep directories with implementation files

**Level 2 directories**:
- `src/runtime/`, `src/prompts/`, `src/mcp_execution/`
- `tests/unit/`, `tests/integration/`
- `.claude/skills/`, `.claude/agents/`, `.claude/rules/`, `.claude/hooks/`
- `thoughts/shared/`

**Level 1 directories**:
- `src/`, `tests/`, `scripts/`, `thoughts/`, `.claude/`

### Step 3: For Each Affected Directory

1. **Read current CLAUDE.md** to understand existing documentation
2. **Explore the directory** to identify changes:
   - New files added
   - Files removed
   - Significant code changes
   - New patterns or conventions
3. **Update CLAUDE.md** with:
   - New files/modules and their purposes
   - Updated key functions/classes
   - Changed patterns or conventions
   - Removed deprecated content

### Step 4: Update Root CLAUDE.md

After updating subdirectory docs, update the root `CLAUDE.md`:
- Ensure cross-reference table is accurate
- Update any changed terminology or patterns
- Add new directories to the table if created

### Step 5: Verify and Commit

```bash
# Check all CLAUDE.md files modified
git status | grep CLAUDE.md

# Review changes
git diff --stat

# Commit documentation updates
git add -A && git commit -m "Update CLAUDE.md documentation after [feature/change]"
```

## Directory CLAUDE.md Template

When creating a new CLAUDE.md, use this structure:

```markdown
# [Directory Name] - [Brief Purpose]

[One-line description of what this directory contains]

## Key Files

| File | Purpose |
|------|---------|
| `file1.py` | Description |
| `file2.py` | Description |

## Patterns

[Key patterns, conventions, or design decisions]

## Usage

[How to use/interact with this directory's contents]

## Related

- [Links to related CLAUDE.md files]
```

## Using Subagents for Large Updates

For repository-wide updates, spawn Explore agents in parallel:

```
Use subagents to update CLAUDE.md files:
- Agent 1: Update src/ and its subdirectories
- Agent 2: Update tests/ and its subdirectories
- Agent 3: Update .claude/ and its subdirectories
- Agent 4: Update thoughts/ and scripts/
```

Each agent should:
1. Explore its assigned directories
2. Read existing CLAUDE.md files
3. Identify what needs updating
4. Write updated CLAUDE.md files
5. Return summary of changes

## Checklist

- [ ] Identified all affected directories
- [ ] Updated Level 3 CLAUDE.md files (deepest)
- [ ] Updated Level 2 CLAUDE.md files
- [ ] Updated Level 1 CLAUDE.md files
- [ ] Updated root CLAUDE.md cross-references
- [ ] Verified all links work
- [ ] Committed changes with descriptive message

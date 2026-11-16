# Migrating from Ledger to Handoff Format

## Why Migrate?

The separate ledger file (`thoughts/ledgers/CONTINUITY_CLAUDE-*.md`) is deprecated. The handoff now contains an embedded Ledger section as the single source of truth.

**Benefits of the new format:**
- **No state drift**: Ledger and handoff in one file cannot get out of sync
- **Simpler workflow**: One file to update, one file to resume from
- **Better for parallel sessions**: Each session has its own clear handoff
- **Faster resume**: SessionStart hook extracts just the Ledger section (~50 lines)

## Migration Steps

### 1. Create New Format Handoff

Run `/create_handoff` to create a handoff with the new embedded Ledger section:

```bash
# The skill will create:
# thoughts/shared/handoffs/{session-name}/current.md
```

### 2. Copy Existing Ledger State

If you have an existing ledger, copy its state into the new handoff's Ledger section:

```bash
# View your existing ledger
cat thoughts/ledgers/CONTINUITY_CLAUDE-*.md

# The content should be migrated into the ## Ledger section
# of your new handoff file
```

**Map the old sections to new:**

| Old Ledger Section | New Handoff Ledger Field |
|--------------------|--------------------------|
| Goal | `**Goal:**` line |
| State > Done | `### This Session` with `[x]` items |
| State > Now | `### Now` with `[->]` item |
| State > Next | `### Next` with `[ ]` items |
| Key Decisions | `### Decisions` |
| Open Questions | `### Open Questions` (keep UNCONFIRMED prefix) |
| Working Set | `**Branch:**` and `**Test:**` lines |

### 3. Archive Legacy Ledger

Once the migration is complete and verified:

```bash
# Create archive directory
mkdir -p thoughts/ledgers/archived

# Move legacy ledger to archive
mv thoughts/ledgers/CONTINUITY_CLAUDE-*.md thoughts/ledgers/archived/
```

## Verification

After migration, test that the SessionStart hook loads from your handoff:

```bash
# Test the hook
echo '{"source": "resume", "session_id": "test"}' | .claude/hooks/session-start-continuity.sh
```

**Expected behavior:**
- Hook should load the Ledger section from your handoff
- No deprecation warning should appear (that only shows for legacy ledger files)
- On `/clear`, the hook should reload your Ledger section automatically

## New Handoff Structure

Your handoff should now look like this:

```markdown
---
date: 2025-01-15T10:00:00Z
session_name: my-feature
branch: feature/my-feature
status: active
---

# Work Stream: my-feature

## Ledger
<!-- This section is extracted by SessionStart hook -->
**Updated:** 2025-01-15T10:00:00Z
**Goal:** Implement feature X with full test coverage
**Branch:** feature/my-feature
**Test:** npm test

### Now
[->] Current focus item

### This Session
- [x] Completed item 1
- [x] Completed item 2

### Next
- [ ] Priority 1
- [ ] Priority 2

### Decisions
- Decision 1: Rationale

### Open Questions
- UNCONFIRMED: Items needing verification after clear

---

## Context
<!-- Full detail - read on demand by resume_handoff -->
... rest of handoff content (task details, learnings, artifacts, etc.) ...
```

## Troubleshooting

### Hook still loads from legacy ledger

Check that your handoff has the `## Ledger` section:
```bash
grep "## Ledger" thoughts/shared/handoffs/*/current.md
```

### Legacy deprecation warning appears

This means the hook found a legacy ledger file but no handoff with Ledger section:
1. Verify your handoff exists and has `## Ledger` section
2. Archive or delete the legacy ledger file

### State seems stale after resume

Always update the `**Updated:**` timestamp when modifying the Ledger section.
The hook uses the most recent handoff by modification time.

## Commands Reference

| Action | Command |
|--------|---------|
| Create new handoff | `/create_handoff` |
| Update ledger section | `/continuity_ledger` |
| Resume from handoff | `/resume_handoff {session-name}` |
| Test hook | `echo '{"source": "resume"}' \| .claude/hooks/session-start-continuity.sh` |

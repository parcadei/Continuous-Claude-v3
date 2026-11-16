---
globs: ["thoughts/ledgers/CONTINUITY_CLAUDE-*.md"]
---

# Continuity Ledger Rules

The ledger is the single source of truth - for session state AND multi-phase implementations.

## File Location
- Ledgers live in: `thoughts/ledgers/`
- Format: `thoughts/ledgers/CONTINUITY_CLAUDE-<session-name>.md`
- Use kebab-case for session name
- One ledger per active work stream

## Required Sections
1. **Goal** - Success criteria (what does "done" look like?)
2. **Constraints** - Technical requirements, patterns to follow
3. **Key Decisions** - Choices made with rationale
4. **State** - Done/Now/Next with checkboxes for multi-phase work
5. **Open Questions** - Mark uncertain items as UNCONFIRMED
6. **Working Set** - Files, branch, test commands

## State Section: Multi-Phase Format

For multi-phase implementations, use checkboxes in State:

```markdown
## State
- Done:
  - [x] Phase 1: Setup database schema
  - [x] Phase 2: Create API endpoints
- Now: [→] Phase 3: Add validation logic
- Next: Phase 4: Frontend components
- Remaining:
  - [ ] Phase 5: Wire up API calls
  - [ ] Phase 6: Write tests
```

**Checkbox states:**
- `[x]` = Completed
- `[→]` = In progress (current)
- `[ ]` = Pending

**Why checkboxes in files:** TodoWrite survives compaction, but the *understanding* around those todos degrades each time context is compressed. File-based checkboxes are never compressed—full fidelity preserved.

## Starting an Implementation

When implementing a plan with multiple phases:
1. Add all phases as checkboxes in State section
2. Mark current phase with `[→]`
3. Update checkboxes as you complete each phase
4. StatusLine shows: `✓ Phase 2 → Phase 3: Current work`

## When to Update
- After completing a phase (update checkbox immediately)
- Before `/clear` (always clear, never compact)
- When context usage >70%

## UNCONFIRMED Prefix
```markdown
## Open Questions
- UNCONFIRMED: Does the auth middleware need updating?
```

## After Clear
1. Ledger loads automatically (SessionStart hook)
2. Find `[→]` to see current phase
3. Verify any UNCONFIRMED items
4. Continue from where you left off with fresh context

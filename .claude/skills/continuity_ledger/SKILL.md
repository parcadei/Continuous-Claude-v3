---
description: Create or update continuity ledger for state preservation across clears
---

# Continuity Ledger

> **Note:** This skill now updates the Ledger section within your handoff file.
> The separate ledger file (`thoughts/ledgers/`) is deprecated.
> Use `/create_handoff` to create a new handoff with embedded Ledger section.

Maintain a Ledger section that survives `/clear` for long-running sessions. The Ledger lives inside the handoff file at `thoughts/shared/handoffs/{session-name}/current.md`.

**Why clear instead of compact?** Each compaction is lossy compression—after several compactions, you're working with degraded context. Clearing + loading the ledger gives you fresh context with full signal.

## When to Use

- Before running `/clear`
- Context usage approaching 70%+
- Multi-day implementations
- Complex refactors you pick up/put down
- Any session expected to hit 85%+ context

## When NOT to Use

- Quick tasks (< 30 min)
- Simple bug fixes
- Single-file changes

## Process

### 1. Find or Create Handoff File

Check if a handoff already exists:
```bash
ls thoughts/shared/handoffs/*/current.md 2>/dev/null
```

- **If exists**: Update the Ledger section in that file
- **If not**: Create new file: `thoughts/shared/handoffs/{session-name}/current.md`
  - First ensure directory exists: `mkdir -p thoughts/shared/handoffs/{session-name}`
  - Use kebab-case for session name (e.g., `auth-refactor`, `api-migration`)

### 2. Ledger Section Template

The Ledger section appears at the top of the handoff file, after the YAML frontmatter:

```markdown
---
date: <ISO timestamp>
session_name: <session-name>
branch: <branch>
status: active
---

# Work Stream: <session-name>

## Ledger
<!-- This section is extracted by SessionStart hook for quick resume -->
**Updated:** <ISO timestamp>
**Goal:** <one-liner success criteria>
**Branch:** <branch>
**Test:** <test command>

### Now
[->] <current focus - ONE thing only>

### This Session
- [x] <completed item 1>
- [x] <completed item 2>

### Next
- [ ] <priority 1>
- [ ] <priority 2>

### Decisions
- <decision>: <rationale>

### Open Questions
- UNCONFIRMED: <things needing verification after clear>

### Workflow State
pattern: [workflow pattern name]
phase: [current phase number]
total_phases: [total phases]
retries: 0
max_retries: 3

#### Resolved
- goal: "[user's stated goal]"
- resource_allocation: [conservative|balanced|aggressive]

#### Unknowns
- [any unresolved questions marked UNKNOWN]

#### Last Failure
[error context if any]

---

## Context
<!-- Full detail - read on demand by resume_handoff -->
... rest of handoff content ...
```

### 3. Updating the Ledger Section

When updating an existing handoff:

1. **Read the current handoff**
2. **Preserve content before `## Ledger`** (YAML frontmatter, title)
3. **Preserve content after `---`** (Context section and beyond)
4. **Replace only the Ledger section** with updated content
5. **Always update the timestamp**

**Pattern for in-place update:**
```
[YAML frontmatter]
# Work Stream: {name}

## Ledger
<!-- NEW Ledger content goes here -->
**Updated:** {NEW timestamp}
...rest of updated ledger...

---

## Context
[PRESERVED: Original context section unchanged]
```

### 4. Update Guidelines

**When to update the ledger:**
- Session start: Read and refresh
- After major decisions
- Before `/clear`
- At natural breakpoints
- When context usage >70%

**What to update:**
- Move completed items from "Now" to "This Session"
- Update "Now" with current focus (ONE item only)
- Add new decisions as they're made
- Mark items as UNCONFIRMED if uncertain
- **Always update the timestamp**

### 5. After Clear Recovery

When resuming after `/clear`:

1. **Ledger loads automatically** (SessionStart hook extracts Ledger section)
2. **Review UNCONFIRMED items**
3. **Ask 1-3 targeted questions** to validate assumptions
4. **Update ledger** with clarifications
5. **Continue work** with fresh context

## Template Response

After creating/updating the ledger, respond:

```
Continuity ledger updated: thoughts/shared/handoffs/<session-name>/current.md

Current state:
- Done: <summary of This Session items>
- Now: <current focus>
- Next: <upcoming priorities>

Ready for /clear - ledger will reload on resume.
```

## Creating Minimal Handoff (Ledger Only)

If no handoff exists and you just need ledger state:

```markdown
---
date: <ISO timestamp>
session_name: <session-name>
branch: <branch>
status: active
---

# Work Stream: <session-name>

## Ledger
**Updated:** <ISO timestamp>
**Goal:** <one-liner>
**Branch:** <branch>
**Test:** <test command>

### Now
[->] <current focus>

### This Session
- [x] Session started

### Next
- [ ] <priority 1>

### Decisions
- (none yet)

### Workflow State
pattern: [workflow pattern name]
phase: 1
total_phases: [total phases]
retries: 0
max_retries: 3

#### Resolved
- goal: "[user's stated goal]"
- resource_allocation: balanced

#### Unknowns
- [any unresolved questions marked UNKNOWN]

#### Last Failure
(none)

### Checkpoints
<!-- Agent checkpoint state for resumable workflows -->
**Agent:** [agent name, e.g., kraken]
**Task:** [task description]
**Started:** [ISO timestamp]
**Last Updated:** [ISO timestamp]

#### Phase Status
- Phase 1: ○ PENDING
- Phase 2: ○ PENDING
- Phase 3: ○ PENDING

#### Validation State
```json
{
  "test_count": 0,
  "tests_passing": 0,
  "files_modified": [],
  "last_test_command": null,
  "last_test_exit_code": null
}
```

#### Resume Context
- Current focus: (not started)
- Next action: Begin Phase 1
- Blockers: (none)

---

## Context
Minimal handoff created for ledger tracking. Full context to be added.
```

## Comparison with Other Tools

| Tool | Scope | Fidelity |
|------|-------|----------|
| CLAUDE.md | Project | Always fresh, stable patterns |
| TodoWrite | Turn | Survives compaction, but understanding degrades |
| Handoff Ledger section | Session | External file—never compressed, full fidelity |

## Example

```markdown
---
date: 2025-01-15T14:30:00Z
session_name: auth-refactor
branch: feature/session-auth
status: active
---

# Work Stream: auth-refactor

## Ledger
**Updated:** 2025-01-15T14:30:00Z
**Goal:** Replace JWT auth with session-based auth. Done when all tests pass and no JWT imports remain.
**Branch:** feature/session-auth
**Test:** npm test -- --grep session

### Now
[->] Logout endpoint and session invalidation

### This Session
- [x] Session model created
- [x] Redis integration complete
- [x] Login endpoint working

### Next
- [ ] Middleware swap
- [ ] Remove JWT imports
- [ ] Update tests

### Decisions
- Session tokens: UUID v4 (simpler than signed tokens for our use case)
- Storage: Redis with 24h TTL (matches current JWT expiry)
- Migration: Dual-auth period, feature flag controlled

### Open Questions
- UNCONFIRMED: Does rate limiter need session awareness?

### Workflow State
pattern: hierarchical
phase: 3
total_phases: 6
retries: 0
max_retries: 3

#### Resolved
- goal: "Replace JWT auth with session-based auth"
- resource_allocation: balanced

#### Unknowns
- rate_limiter_awareness: UNKNOWN

#### Last Failure
(none)

### Checkpoints
<!-- Agent checkpoint state for resumable workflows -->
**Agent:** kraken
**Task:** Replace JWT auth with session-based auth
**Started:** 2025-01-15T10:00:00Z
**Last Updated:** 2025-01-15T14:30:00Z

#### Phase Status
- Phase 1 (Tests Written): ✓ VALIDATED (12 tests, all failing as expected)
- Phase 2 (Session Model): ✓ VALIDATED (12 tests passing)
- Phase 3 (Redis Integration): ✓ VALIDATED (15 tests passing)
- Phase 4 (Login Endpoint): → IN_PROGRESS (started 2025-01-15T14:00:00Z)
- Phase 5 (Logout Endpoint): ○ PENDING
- Phase 6 (Middleware Swap): ○ PENDING

#### Validation State
```json
{
  "test_count": 15,
  "tests_passing": 15,
  "files_modified": ["src/auth/session.py", "src/auth/redis_store.py", "tests/unit/test_session_auth.py"],
  "last_test_command": "uv run pytest tests/unit/test_session_auth.py -v",
  "last_test_exit_code": 0
}
```

#### Resume Context
- Current focus: Implementing login endpoint with session creation
- Next action: Create session token on successful login
- Blockers: (none)

---

## Context
Full task context, learnings, and detailed notes go here.
```

## Additional Notes

- **Keep it concise** - Brevity matters for context
- **One "Now" item** - Forces focus, prevents sprawl
- **UNCONFIRMED prefix** - Signals what to verify after clear
- **Update frequently** - Stale ledgers lose value quickly
- **Clear > compact** - Fresh context beats degraded context
- **Single file** - Ledger + handoff together = no drift

## Checkpoint Section Usage

The `### Checkpoints` section enables resumable agent workflows (e.g., kraken TDD agent).

### Checkpoint State Symbols

| Symbol | State | Meaning |
|--------|-------|---------|
| `○` | PENDING | Not yet started |
| `→` | IN_PROGRESS | Currently working (with timestamp) |
| `✓` | VALIDATED | Completed and verified |
| `✗` | FAILED | Validation failed (requires retry) |

### When to Update Checkpoints

1. **On phase start:** Mark phase `→ IN_PROGRESS` with timestamp
2. **On phase completion:** Run validation, mark `✓ VALIDATED` if passing
3. **On validation failure:** Mark `✗ FAILED`, record error in Resume Context
4. **Before context clear:** Ensure current state is persisted

### Resume Pattern

When spawning a resumable agent:

```typescript
Task({
  subagent_type: "kraken",
  prompt: `
    Resume from checkpoint.

    Handoff: thoughts/shared/handoffs/auth-refactor/current.md

    Continue from last validated phase.
  `
})
```

The agent reads the checkpoint, verifies the last validated phase still passes, then continues from the next pending or in-progress phase.

### Validation State JSON

The `Validation State` block stores machine-readable state:

```json
{
  "test_count": 15,           // Total tests in scope
  "tests_passing": 15,        // Tests currently passing
  "files_modified": [...],    // Files touched this session
  "last_test_command": "...", // Command to re-validate
  "last_test_exit_code": 0    // Expected exit code
}
```

On resume, the agent re-runs `last_test_command` and confirms the exit code matches before proceeding.

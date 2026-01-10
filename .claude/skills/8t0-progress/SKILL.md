---
name: 8t0-progress
description: Generate or update project progress dashboard by aggregating status from ROADMAP.md, SUMMARY.md files, and specs.
user-invocable: true
keywords: [progress, dashboard, status, tracking, roadmap]
---

# Progress Dashboard

<purpose>
Aggregate project status into .planning/PROGRESS.md by reading:
- .planning/ROADMAP.md (phase structure)
- .planning/phases/*/SUMMARY.md (completed work)
- docs/specs/index.md (module status)
- docs/adr/README.md (pending decisions)
</purpose>

<rules>
1. Always read all source files before generating dashboard
2. Calculate progress based on PLAN.md → SUMMARY.md completion
3. Flag blockers clearly
4. Prioritize next actions
5. Support both interactive and silent modes
</rules>

<modes>
## Interactive Mode (default)
- Full dashboard generation
- Use AskUserQuestion for blocker resolution
- Identifies and suggests next actions
- Shows detailed progress report

## Silent Mode
- Update PROGRESS.md without interaction
- Only interrupt if critical blockers found
- Log update to session history
- Use when: automated updates, pre-stop checks

To invoke silent mode: `/8t0-progress silent`
</modes>

<workflow>

## Step 1: Read Sources

Gather data from:
```
.planning/ROADMAP.md              → Phase definitions
.planning/phases/*/*-SUMMARY.md   → Look for *-SUMMARY.md files (exists = plan complete)
docs/specs/index.md               → Module status
docs/adr/README.md                → ADR status
```

## Step 2: Calculate Progress

For each phase:
- All `{phase}-*-SUMMARY.md` files exist for all `{phase}-*-PLAN.md` files → Complete (100%)
- Has PLAN.md files but missing some SUMMARY.md → In Progress (count completed/total)
- No PLAN.md files → Pending (0%)

For each module:
- Check spec status in index.md
- Check if implementation files exist
- Check if tests exist

## Step 3: Generate Dashboard

Write/update `.planning/PROGRESS.md`:

```markdown
# Project Progress

**Last Updated**: [timestamp]
**Overall**: [X]% complete

## Phase Status

| Phase | Status | Progress | Blockers |
|-------|--------|----------|----------|
| 01-[name] | Complete | 100% | - |
| 02-[name] | In Progress | [X]% | [blocker] |
| 03-[name] | Pending | 0% | Blocked by 02 |

## Module Status

| Module | Spec | Implementation | Tests |
|--------|------|----------------|-------|
| [name] | Complete | [X]% | Pending |

## Recent Completions
- [date]: [phase/task completed]

## Active Blockers
- [ ] [blocker description]

## Decisions Pending
- [ ] ADR-XXX: [topic] (Proposed)

## Next Actions
1. [highest priority action]
2. [next action]
```

## Step 4: Identify Blockers

Flag as blockers:
- Phases waiting on previous phase
- Modules with unresolved Open Questions
- ADRs in "Proposed" status blocking implementation
- Failed verifications in SUMMARY.md

</workflow>

<silent_mode_behavior>
When mode="silent":
1. Skip all AskUserQuestion calls
2. Generate dashboard with available data
3. If blockers found, add to dashboard but don't ask
4. Return brief summary: "Progress updated: X% complete, N blockers"
</silent_mode_behavior>

<question_quality>
BAD (too generic):
- "What's the project status?"
- "Are we on track?"

GOOD (actionable):
- "Phase 02 is at 60% but Phase 03 depends on it. Should we start Phase 03 planning in parallel?"
- "ADR-0003 has been 'Proposed' for 5 days. Should we accept it to unblock the auth module?"
</question_quality>

<success_criteria>
- PROGRESS.md reflects current state
- All phases accounted for
- Blockers clearly identified
- Next actions prioritized
- Dashboard timestamp updated
</success_criteria>

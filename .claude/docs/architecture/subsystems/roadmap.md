# ROADMAP Subsystem

## Overview

ROADMAP.md is the **single authoritative view** of project status for Continuous Claude. It is automatically maintained by 4 specialized hooks but manually governable through the `/roadmap` skill.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         ROADMAP.md                              │
│  ┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │
│  │Current Focus│ │ Planned  │ │Completed │ │Recent Planning  │  │
│  └──────┬──────┘ └────┬─────┘ └────┬─────┘ └────────┬────────┘  │
└─────────┼─────────────┼────────────┼────────────────┼───────────┘
          │             │            │                │
          ▼             ▼            ▼                ▼
┌─────────────────┐ ┌──────────────┐ ┌─────────────┐ ┌────────────┐
│post-plan-roadmap│ │prd-roadmap-  │ │git-commit-  │ │post-plan-  │
│                 │ │sync          │ │roadmap      │ │roadmap     │
│ ExitPlanMode    │ │ PRD Write/   │ │ Bash git    │ │ExitPlanMode│
│ trigger         │ │ Edit trigger │ │ commit      │ │trigger     │
└─────────────────┘ └──────────────┘ └─────────────┘ └────────────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │roadmap-     │
                                    │completion   │
                                    │ TaskUpdate  │
                                    └─────────────┘
```

## Section Ownership Model

| Section | Primary Source | Automation | Human Override |
|---------|----------------|------------|----------------|
| **Current Focus** | Planning sessions | `post-plan-roadmap` | `/roadmap focus` |
| **Planned** | PRD files + manual | `prd-roadmap-sync` | `/roadmap add` |
| **Completed** | Git commits + tasks | `git-commit-roadmap` + `roadmap-completion` | `/roadmap complete` |
| **Recent Planning** | ExitPlanMode | `post-plan-roadmap` | Archive manually |

## Components

| Component | File | Purpose |
|-----------|------|---------|
| Plan Hook | `hooks/src/post-plan-roadmap.ts` | Updates Current Focus on ExitPlanMode |
| PRD Hook | `hooks/src/prd-roadmap-sync.ts` | Syncs PRD files to Planned |
| Commit Hook | `hooks/src/git-commit-roadmap.ts` | Adds commits to Completed |
| Completion Hook | `hooks/src/roadmap-completion.ts` | TaskUpdate → Completed |
| Skill | `skills/roadmap/SKILL.md` | Manual management |

## Hook Reference

### prd-roadmap-sync

**Trigger:** PostToolUse (Write|Edit) for `prd-*.md` or `PRD-*.md` files

**Behavior:**
1. Extracts PRD metadata (title, status, priority)
2. Finds ROADMAP.md via recursive upward search (or CLAUDE_PROJECT_DIR)
3. Adds new PRD to Planned section if not duplicate
4. Updates progress when tasks file changes

### post-plan-roadmap

**Trigger:** PostToolUse (ExitPlanMode)

**Behavior:**
1. Reads latest plan from `.claude/plans/` directory
2. Extracts title, decisions, steps, files
3. Updates Current Focus with new goal
4. Moves previous goal to Completed
5. Records planning session in Recent Planning

### git-commit-roadmap

**Trigger:** PostToolUse (Bash) matching `git commit`

**Behavior:**
1. Parses conventional commit message (feat:, fix:, etc.)
2. Skips chore, style, ci commits
3. Adds commit to Completed section with hash

### roadmap-completion

**Trigger:** PostToolUse (TaskUpdate with status=completed) or UserPromptSubmit with completion signals

**Behavior:**
1. Detects completion signals (tests passed, git push, "done")
2. Moves Current Focus to Completed
3. Optionally promotes next Planned item

## /roadmap Skill

| Command | Purpose | Example |
|---------|---------|---------|
| `/roadmap show` | Display current state | `/roadmap show` |
| `/roadmap add <item>` | Add to Planned | `/roadmap add "Dark mode" --priority high` |
| `/roadmap focus <item>` | Set Current Focus | `/roadmap focus "Auth system"` |
| `/roadmap complete` | Mark done | `/roadmap complete` |

## ROADMAP Location

Search order (hooks use recursive upward search):
1. `$CLAUDE_PROJECT_DIR/ROADMAP.md` (if env var set)
2. `$CLAUDE_PROJECT_DIR/.claude/ROADMAP.md`
3. Recursive upward from current directory
4. `~/.claude/ROADMAP.md` (fallback)

## Integration Points

| System | Integration |
|--------|-------------|
| Knowledge Tree | `goals.source` references ROADMAP |
| Memory System | Planning decisions stored via `archival_memory` |
| Git | `git-commit-roadmap` auto-updates Completed |
| Task System | `roadmap-completion` responds to TaskUpdate |

## Plan Directory Fallback

The `post-plan-roadmap` hook checks plans in 3 locations (in order):
1. `{projectDir}/.claude/plans` - Standard project plans
2. `{projectDir}/plans` - When project IS ~/.claude
3. `~/.claude/plans` - User-level fallback

## Quick Usage

```bash
# Manual management
/roadmap show
/roadmap add "New feature" --priority high
/roadmap focus "Current work"
/roadmap complete

# Automation triggers automatically:
# - Exit plan mode → Current Focus updated
# - Create PRD file → Planned updated
# - Git commit feat/fix → Completed updated
# - TaskUpdate completed → Current → Completed
```

## Deep Dive

For implementation details and path resolution fixes:
→ `~/continuous-claude/docs/Roadmap Source of Truth Implementation.md`

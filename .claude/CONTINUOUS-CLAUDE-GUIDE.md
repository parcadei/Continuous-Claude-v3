# Continuous Claude Guide

> Cross-session memory, coordination, and continuity for Claude Code

## What Continuous Claude Does For You

### Automatic (No Action Required)

| Feature | What It Does | How It Works |
|---------|--------------|--------------|
| **PostgreSQL Auto-Start** | Starts memory database if not running | `session-start-docker` hook |
| **Session Registration** | Tracks your active Claude sessions | `session-register` hook on startup |
| **Knowledge Tree** | Maps project structure for navigation | `tree-daemon` watches files (2s debounce) |
| **Heartbeat** | Keeps session alive, detects when you leave | Updates every tool call |
| **Cross-Terminal Awareness** | Warns if another session is editing same files | PostgreSQL tracks file claims |
| **ROADMAP Updates** | Syncs goals with planning/tasks | `post-plan-roadmap`, `prd-roadmap-sync` hooks |
| **Handoff Loading** | Loads context from previous sessions | Hook reads `current.md` on startup |
| **Repo Sync** | Auto-syncs ~/.claude changes to team repo | `sync-to-repo` hook on Write/Edit |

### On-Demand (Commands You Run)

| Feature | When To Use | Command |
|---------|-------------|---------|
| **Recall Memory** | Before starting similar work | See "Recall Learnings" below |
| **Store Learning** | When you discover something worth remembering | See "Store Learning" below |
| **Check Peers** | See other active Claude sessions | See "Session Queries" below |
| **Create Handoff** | Before ending a complex session | `/skill:create_handoff` |

---

## Startup Checklist

When starting a new Claude session, these happen automatically:
1. Session registered in PostgreSQL
2. Handoff ledger loaded (if exists at `~/.claude/thoughts/shared/handoffs/*/current.md`)
3. Memory daemon verified running
4. Peer sessions checked (you'll see notification if others active)

**You should see** in your session start:
- "SessionStart hook success" messages
- Handoff context (if resuming work)

---

## Essential Commands

### Recall Learnings (Before Starting Work)

```bash
cd ~/.claude && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "<what you're working on>" --k 5
```

**When to use:** Before implementing something you may have done before

**Examples:**
```bash
# Before working on hooks
--query "hook development patterns"

# Before debugging
--query "TypeScript errors solutions"

# Before database work
--query "PostgreSQL migration patterns"
```

### Store Learning (When You Discover Something)

```bash
cd ~/.claude && PYTHONPATH=. uv run python scripts/core/store_learning.py \
  --session-id "<short-id>" \
  --type <TYPE> \
  --content "<what you learned>" \
  --context "<related topic>" \
  --tags "tag1,tag2" \
  --confidence high
```

**Note:** `--project-dir` auto-detects from `CLAUDE_PROJECT_DIR` env var for project isolation.

**Types:** `WORKING_SOLUTION` | `ARCHITECTURAL_DECISION` | `ERROR_FIX` | `FAILED_APPROACH` | `CODEBASE_PATTERN`

**When to use:**
- Solved a tricky problem
- Made a design decision with rationale
- Found something that doesn't work (save others the pain)

### Session Queries

```bash
# Active sessions (last 5 min)
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c \
  "SELECT id, project, working_on FROM sessions WHERE last_heartbeat > NOW() - INTERVAL '5 minutes';"

# All recent sessions
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c \
  "SELECT id, project, last_heartbeat FROM sessions ORDER BY last_heartbeat DESC LIMIT 10;"

# File claims (who's editing what)
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c \
  "SELECT file_path, session_id FROM file_claims ORDER BY claimed_at DESC LIMIT 10;"
```

### Memory Daemon Status

```bash
# Check if running
cat ~/.claude/memory-daemon.pid && tasklist | grep $(cat ~/.claude/memory-daemon.pid)

# View recent log
tail -20 ~/.claude/memory-daemon.log

# Restart if needed
cd ~/.claude/scripts/core/core && uv run python memory_daemon.py start
```

---

## Handoff System

### Two Handoff Locations (Important!)

| Location | Used By | Purpose |
|----------|---------|---------|
| `~/.claude/thoughts/shared/handoffs/` | Session-start hook (auto-load) | Global handoffs |
| `./thoughts/shared/handoffs/` | `/resume_handoff` skill | Project-relative handoffs |

**Best practice:** Keep handoffs in `./thoughts/` (project directory) and they work with both.

### When To Create Handoffs

Create a handoff when:
- Ending a multi-session project
- About to run `/compact`
- Work is incomplete but you need to stop
- Switching to different work

### Creating a Handoff

```
/skill:create_handoff
```

Or ask Claude: "Create a handoff document for this work"

Handoffs are stored in: `./thoughts/shared/handoffs/<session-name>/YYYY-MM-DD_HH-MM_description.yaml`

### Resuming From Handoff

Handoffs load automatically on session start. You'll see:
```
SessionStart hook additional context: Handoff Ledger loaded from current.md
```

To manually resume: `/skill:resume_handoff`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLAUDE CODE SESSION                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  SessionStart hooks (sequential):                                            │
│    ┌──────────────────────┐   ┌──────────────────────┐                      │
│    │ session-start-docker │──►│   session-register   │                      │
│    │ Start PostgreSQL     │   │ Register in coord DB │                      │
│    └──────────────────────┘   └──────────┬───────────┘                      │
│                                          │                                   │
│    ┌──────────────────────┐   ┌──────────▼───────────┐                      │
│    │ session-continuity   │──►│  tree-daemon.ps1     │                      │
│    │ Load handoff ledger  │   │ Knowledge tree watch │                      │
│    └──────────────────────┘   └──────────┬───────────┘                      │
│                                          │                                   │
│                               ┌──────────▼───────────┐                      │
│                               │ memory-daemon.ps1    │ ◄── NEW              │
│                               │ Auto-start extractor │                      │
│                               └──────────────────────┘                      │
│                                                                              │
│  PostToolUse hooks:                                                          │
│    post-plan-roadmap ─────► Update ROADMAP on plan exit                     │
│    roadmap-completion ────► Mark goals complete                             │
│    prd-roadmap-sync ──────► Sync PRD/Tasks with ROADMAP                     │
│    sync-to-repo ──────────► Auto-sync to team repo                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       FOUR PILLARS (All Auto-Start ✅)                       │
├─────────────────────┬─────────────────────┬─────────────────────┬───────────┤
│                     │                     │                     │           │
│  ┌───────────────┐  │  ┌───────────────┐  │  ┌───────────────┐  │ HANDOFFS  │
│  │    MEMORY     │  │  │  KNOWLEDGE    │  │  │   ROADMAP     │  │           │
│  │    SYSTEM     │  │  │    TREE       │  │  │               │  │ current.  │
│  ├───────────────┤  │  ├───────────────┤  │  ├───────────────┤  │ md auto-  │
│  │ PostgreSQL +  │  │  │ knowledge-    │  │  │ ROADMAP.md    │  │ loaded on │
│  │ pgvector      │  │  │ tree.json     │  │  │               │  │ session   │
│  │               │  │  │               │  │  │ ## Current    │  │ start     │
│  │ memory_daemon │  │  │ tree_daemon   │  │  │ ## Completed  │  │           │
│  │ extracts from │  │  │ watches files │  │  │ ## Planned    │  │           │
│  │ stale sessions│  │  │ 2s debounce   │  │  │               │  │           │
│  └───────────────┘  │  └───────────────┘  │  └───────────────┘  │           │
│                     │                     │                     │           │
│  Auto: daemon hook  │  Auto: daemon hook  │  Auto: plan hooks   │  Auto:    │
│  ✅                 │  ✅                 │  ✅                 │  ✅       │
└─────────────────────┴─────────────────────┴─────────────────────┴───────────┘
```

---

## Troubleshooting

### "No handoff loaded"
- Check: `ls ~/.claude/thoughts/shared/handoffs/*/current.md`
- Create one with `/skill:create_handoff`

### Memory recall returns nothing
```bash
# Check learning count
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c \
  "SELECT COUNT(*) FROM archival_memory;"

# If low, manually store some learnings from current session
```

### Daemon not extracting
```bash
# Check daemon log
tail -30 ~/.claude/memory-daemon.log

# Verify PostgreSQL is running
docker ps | grep continuous-claude-postgres

# Restart daemon
cd ~/.claude/scripts/core/core && uv run python memory_daemon.py start
```

### Multiple sessions conflict warning
This is working as intended! The other session has claimed files. Coordinate with yourself (other terminal) or wait for that session to end.

---

## ROADMAP Integration

The ROADMAP system tracks project goals with automatic updates:

### Automatic Updates
| Event | Hook | ROADMAP Action |
|-------|------|----------------|
| Exit plan mode | `post-plan-roadmap` | Adds planning session to Recent |
| TaskUpdate completed | `roadmap-completion` | Moves Current → Completed |
| Create PRD | `prd-roadmap-sync` | Adds to Planned section |
| Edit tasks file | `prd-roadmap-sync` | Updates progress %, promotes to Current |

### PRD/Tasks Workflow
```
1. Create PRD:  Use @create-prd.md → prd-feature.md → Added to ROADMAP Planned
2. Generate Tasks: Use @generate-tasks.md → tasks-feature.md → Promoted to Current
3. Work Tasks: Check off [x] → Progress updates (e.g., "12/20 (60%)")
4. Complete: All tasks [x] → Moved to Completed with date
```

---

## Key Paths

| Path | Purpose |
|------|---------|
| `~/.claude/.env` | DATABASE_URL (port 5434), Braintrust keys |
| `~/.claude/docker/.env` | PostgreSQL port configuration |
| `~/.claude/projects/` | Session JSONL files |
| `~/.claude/thoughts/shared/handoffs/` | Handoff documents |
| `~/.claude/scripts/core/` | recall_learnings.py, store_learning.py |
| `~/.claude/scripts/core/core/` | tree_daemon.py, knowledge_tree.py |
| `{project}/.claude/knowledge-tree.json` | Project navigation map |
| `{project}/ROADMAP.md` | Project goals tracking |
| `{project}/tasks/` | PRD and task files |

---

## Best Practices

1. **Start of session:** Glance at handoff context loaded, recall relevant memories
2. **During session:** Store learnings when you solve something tricky
3. **Before compact:** Let pre-compact hook create handoff automatically
4. **End of session:** For important work, explicitly create handoff

The system is designed to be mostly automatic. The main manual actions are:
- **Recall** before starting similar work
- **Store** when you learn something valuable
- **Handoff** for complex multi-session projects

# Continuous Claude Guide

> Cross-session memory, coordination, and continuity for Claude Code

**See also:** [Architecture Docs](docs/architecture/INDEX.md) for system diagrams, agent selection, and deep dives

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
| **Memory Auto-Injection** | Surfaces relevant past learnings | `memory-awareness` hook |

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
# Hybrid search (RECOMMENDED - best accuracy)
cd $CLAUDE_OPC_DIR && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "<what you're working on>" --hybrid

# Standard search
cd $CLAUDE_OPC_DIR && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "<what you're working on>" --k 5

# PageIndex only (for large docs)
cd $CLAUDE_OPC_DIR && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "<what you're working on>" --pageindex
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
cd $CLAUDE_OPC_DIR && PYTHONPATH=. uv run python scripts/core/store_learning.py \
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

## PageIndex System (Document Navigation)

PageIndex provides **reasoning-based document search** with 98.7% accuracy (vs ~50% for vector similarity).

### How It Works
1. Documents parsed into hierarchical tree (titles, sections)
2. LLM reasons over tree outline (~500 tokens) to find relevant nodes
3. Full content retrieved from matched nodes

### When to Use
| Use PageIndex | Use Vector Memory |
|---------------|-------------------|
| Large docs (ROADMAP, ARCHITECTURE) | Session learnings |
| Hierarchical content | Code patterns |
| "What does X say about Y?" | "How did we solve X?" |

### Commands
```bash
# Generate tree for a document
cd $CLAUDE_OPC_DIR && uv run python scripts/pageindex/cli/pageindex_cli.py generate ROADMAP.md

# Search indexed docs
cd $CLAUDE_OPC_DIR && uv run python scripts/pageindex/cli/pageindex_cli.py search "query"

# Hybrid search (best accuracy - combines both)
cd $CLAUDE_OPC_DIR && uv run python scripts/core/recall_learnings.py --query "topic" --hybrid
```

### Auto-Updates
The `pageindex-watch` hook automatically regenerates trees when .md files are edited.

---

## Git Safety (Memory Integration)

The `git-memory-check` hook automatically protects against mistakes:

| Command | Check | Action |
|---------|-------|--------|
| `git push origin` | "NEVER push to origin" memories | Block with warning |
| `git push --force` | Force push warnings | Block with warning |
| `git reset --hard` | Reset warnings | Warn if relevant |

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
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         FIVE PILLARS (All Auto-Start ✅)                            │
├─────────────────┬─────────────────┬─────────────────┬─────────────────┬─────────────┤
│     MEMORY      │   KNOWLEDGE     │   PAGEINDEX     │    ROADMAP      │  HANDOFFS   │
│     SYSTEM      │     TREE        │   (NEW)         │                 │             │
├─────────────────┼─────────────────┼─────────────────┼─────────────────┼─────────────┤
│ PostgreSQL +    │ knowledge-      │ Tree-based      │ ROADMAP.md      │ current.md  │
│ pgvector        │ tree.json       │ doc search      │                 │ auto-loaded │
│                 │                 │                 │                 │             │
│ Vector search   │ File navigate   │ 98.7% accuracy  │ Goal tracking   │ Session     │
│ for learnings   │ 2s debounce     │ LLM reasoning   │ Auto-update     │ continuity  │
├─────────────────┼─────────────────┼─────────────────┼─────────────────┼─────────────┤
│ Auto: daemon    │ Auto: daemon    │ Auto: watch     │ Auto: plan      │ Auto: hook  │
│ hook ✅         │ hook ✅         │ hook ✅         │ hooks ✅        │ ✅          │
└─────────────────┴─────────────────┴─────────────────┴─────────────────┴─────────────┘
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

ROADMAP.md is the **single authoritative view** of project status, maintained by 4 specialized hooks with manual override via `/roadmap` skill.

### Section Ownership Model

| Section | Primary Source | Automation | Human Override |
|---------|----------------|------------|----------------|
| **Current Focus** | Planning sessions | `post-plan-roadmap` | `/roadmap focus` |
| **Planned** | PRD files + manual | `prd-roadmap-sync` | `/roadmap add` |
| **Completed** | Git commits + tasks | `git-commit-roadmap` + `roadmap-completion` | `/roadmap complete` |
| **Recent Planning** | ExitPlanMode | `post-plan-roadmap` | Archive manually |

### The 4 ROADMAP Hooks

| Hook | Trigger | ROADMAP Section |
|------|---------|-----------------|
| `post-plan-roadmap` | ExitPlanMode | Current Focus + Recent Planning |
| `prd-roadmap-sync` | Write\|Edit PRD files | Planned |
| `git-commit-roadmap` | Bash git commit | Completed |
| `roadmap-completion` | TaskUpdate completed | Current Focus → Completed |

### /roadmap Skill Commands

| Command | Purpose |
|---------|---------|
| `/roadmap show` | Display current ROADMAP state |
| `/roadmap add <item>` | Add item to Planned section |
| `/roadmap focus <item>` | Set Current Focus |
| `/roadmap complete` | Mark current goal done |

### PRD/Tasks Workflow
```
1. Create PRD:  Use @create-prd.md → prd-feature.md → Added to ROADMAP Planned
2. Generate Tasks: Use @generate-tasks.md → tasks-feature.md → Promoted to Current
3. Work Tasks: Check off [x] → Progress updates (e.g., "12/20 (60%)")
4. Complete: All tasks [x] → Moved to Completed with date
```

### Plan Directory Fallback
The post-plan-roadmap hook checks plans in 3 locations (in order):
1. `{projectDir}/.claude/plans` - Standard project plans
2. `{projectDir}/plans` - When project IS ~/.claude
3. `~/.claude/plans` - User-level fallback

### Deep Dive
→ [ROADMAP Subsystem](docs/architecture/subsystems/roadmap.md) for architecture details

---

## Key Paths

| Path | Purpose |
|------|---------|
| `~/.claude/.env` | DATABASE_URL (port 5432), Braintrust keys |
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

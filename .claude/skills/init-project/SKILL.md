---
name: init-project
description: Initialize Continuous Claude for a new project - knowledge tree, ROADMAP, and daemon
user-invocable: true
triggers: ["/init-project", "new project", "setup project", "initialize project"]
allowed-tools: [Bash, Read, Write, Task]
---

# Init Project - Continuous Claude Setup

Set up a new project with the full Continuous Claude infrastructure: knowledge tree, ROADMAP tracking, and optional continuous updates.

## When to Use

- First time opening a project folder in Claude Code
- User says "init project", "setup continuous claude", "new project"
- Session start hook suggests initialization for uninitialized projects

## Quick Start

```bash
# Minimal setup (just knowledge tree)
/init-project

# Full setup with daemon
/init-project --daemon

# Skip interactive prompts
/init-project --yes
```

## What Gets Created

| File | Purpose |
|------|---------|
| `.claude/knowledge-tree.json` | Project navigation map |
| `ROADMAP.md` | Goals and progress tracking |
| `.claude/tree-daemon.pid` | Daemon process (if --daemon) |

## Setup Steps

### Step 1: Generate Knowledge Tree

```bash
uv run python ~/.claude/scripts/core/core/knowledge_tree.py --project .
```

Creates `.claude/knowledge-tree.json` with:
- Project description (from README)
- Directory structure and purposes
- Component detection
- Navigation hints for common tasks

### Step 2: Create ROADMAP.md

Template for tracking goals:

```markdown
# Project Roadmap

## Current Focus
**[Your current goal]**
- What you're working on
- Started: YYYY-MM-DD

## Completed
- [x] Initial setup (YYYY-MM-DD)

## Planned
- [ ] First feature (high priority)
- [ ] Second feature (medium priority)

## Recent Planning Sessions
_Planning sessions will be recorded here automatically._
```

### Step 3: Start Daemon (Optional)

```bash
uv run python ~/.claude/scripts/core/core/tree_daemon.py --project . --background
```

Continuously updates knowledge tree when files change.

### Step 4: Deep Analysis (Optional)

For brownfield projects, spawn the onboard agent:

```
Use Task tool with subagent_type: "onboard"
```

This creates a detailed handoff with architecture analysis.

## Integration Points

### Hooks (Auto-Active)

| Hook | Event | Purpose |
|------|-------|---------|
| `pre-tool-knowledge.mjs` | PreToolUse:Task | Injects tree context |
| `post-plan-roadmap.mjs` | PostToolUse:ExitPlanMode | Updates ROADMAP |
| `session-start-continuity.mjs` | SessionStart | Loads handoff context |

### Skills

| Skill | Purpose |
|-------|---------|
| `/knowledge-tree` | Query and manage the tree |
| `/onboard` | Deep brownfield analysis |
| `/create_handoff` | Create session handoffs |

## Project Types

### Greenfield (New Project)

```bash
/init-project
# Creates minimal tree + ROADMAP template
# User fills in goals manually
```

### Brownfield (Existing Code)

```bash
/init-project
# Then:
/onboard
# Creates detailed analysis + handoff
```

## Verification

After running `/init-project`, verify:

```bash
# Check tree exists
ls -la .claude/knowledge-tree.json

# Check ROADMAP
cat ROADMAP.md

# Query goals
uv run python ~/.claude/scripts/core/core/query_tree.py --project . --goals

# Check daemon (if started)
uv run python ~/.claude/scripts/core/core/tree_daemon.py --project . --status
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No knowledge tree" | Run `uv run python ~/.claude/scripts/core/core/knowledge_tree.py --project .` |
| "watchdog not installed" | Run `uv pip install watchdog` |
| "Daemon won't start" | Check `.claude/tree-daemon.log` |
| Goals not showing | Regenerate tree after creating ROADMAP.md |

## Implementation Notes

When implementing `/init-project`, follow this sequence:

1. Check if `.claude/knowledge-tree.json` exists
2. If not, generate it
3. Check if `ROADMAP.md` exists
4. If not, create template (ask user for initial goal)
5. Ask if user wants daemon started
6. Ask if user wants deep analysis (/onboard)
7. Summarize what was created

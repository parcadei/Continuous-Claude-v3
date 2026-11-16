# Claude Continuity Kit

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-348%20passing-brightgreen.svg)](#testing)

Session continuity, token-efficient MCP execution, and multi-agent orchestration patterns for Claude Code.

**11 patterns implemented**: Swarm, Jury, Pipeline, Generator-Critic, Hierarchical, Map-Reduce, Blackboard, Circuit Breaker, Chain of Responsibility, Adversarial, Event-Driven.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [The Problem](#the-problem) / [The Solution](#the-solution)
- [Quick Start](#quick-start) (project or global install)
- [How to Talk to Claude](#how-to-talk-to-claude)
- [Skills vs Agents](#skills-vs-agents)
- [MCP Code Execution](#mcp-code-execution)
- [Continuity System](#continuity-system)
- [Memory System](#memory-system)
- [Hooks System](#hooks-system)
- [Reasoning History](#reasoning-history)
- [Braintrust Session Tracing](#braintrust-session-tracing-optional) + [Compound Learnings](#compound-learnings)
- [Artifact Index](#artifact-index) (handoff search, outcome tracking)
- [TDD Workflow](#tdd-workflow)
- [Code Quality (qlty)](#code-quality-qlty)
- [Directory Structure](#directory-structure)
- [Environment Variables](#environment-variables)
- [Glossary](#glossary)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Acknowledgments](#acknowledgments)
- [License](#license)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CLAUDE CODE SESSION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌────────────┐  │
│   │ SessionStart│───▶│   Working   │───▶│  PreCompact │───▶│ SessionEnd │  │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └─────┬──────┘  │
│          │                  │                  │                  │         │
│          ▼                  ▼                  ▼                  ▼         │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌───────────┐   │
│   │Load Ledger   │   │PreToolUse    │   │Auto-Handoff  │   │Mark       │   │
│   │Load Handoff  │   │ TS Preflight │   │Block Manual  │   │Outcome    │   │
│   │Surface       │   │PostToolUse   │   │              │   │Cleanup    │   │
│   │Learnings     │   │UserPrompt    │   │              │   │Learn      │   │
│   └──────────────┘   └──────────────┘   └──────────────┘   └───────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                │                │                │                │
                ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  thoughts/                    .claude/cache/                                │
│  ├── ledgers/                 ├── artifact-index/                           │
│  │   └── CONTINUITY_*.md          └── context.db (SQLite+FTS5)             │
│  └── shared/                  ├── learnings/                                │
│      ├── handoffs/                └── <date>_<session>.md                   │
│      │   └── <session>/       └── braintrust_sessions/                      │
│      │       └── *.md             └── <session>.json                        │
│      └── plans/                                                             │
│          └── *.md             .git/claude/                                  │
│                               └── commits/                                  │
│                                   └── <hash>/reasoning.md                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                │                                        │
                ▼                                        ▼
┌───────────────────────────────────┐  ┌───────────────────────────────────┐
│          SKILLS                   │  │           AGENTS                   │
├───────────────────────────────────┤  ├───────────────────────────────────┤
│                                   │  │                                   │
│  ┌──────────────────┐             │  │  ┌──────────────────┐             │
│  │ continuity_ledger│ Save state  │  │  │ plan-agent       │ Create plan │
│  ├──────────────────┤             │  │  ├──────────────────┤             │
│  │ create_handoff   │ End session │  │  │ validate-agent   │ Check tech  │
│  ├──────────────────┤             │  │  ├──────────────────┤             │
│  │ resume_handoff   │ Resume work │  │  │ implement_plan   │ Execute     │
│  ├──────────────────┤             │  │  ├──────────────────┤             │
│  │ commit           │ Git commit  │  │  │ research-agent   │ Research    │
│  ├──────────────────┤             │  │  ├──────────────────┤             │
│  │ tdd-workflow     │ Red/Green   │  │  │ debug-agent      │ Debug       │
│  ├──────────────────┤             │  │  ├──────────────────┤             │
│  │ hook-developer   │ Hook ref    │  │  │ rp-explorer      │ Codebase    │
│  ├──────────────────┤             │  │  └──────────────────┘             │
│  │ compound-learn   │ Make rules  │  │                                   │
│  └──────────────────┘             │  │                                   │
└───────────────────────────────────┘  └───────────────────────────────────┘
                │                                        │
                └────────────────────┬───────────────────┘
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SCRIPTS (MCP Execution)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Artifact Index              Braintrust              MCP Tools              │
│  ┌──────────────────┐        ┌──────────────────┐    ┌──────────────────┐   │
│  │ artifact_index   │        │ braintrust_       │    │ perplexity_      │   │
│  │ artifact_query   │        │    analyze        │    │    search        │   │
│  │ artifact_mark    │        │ (--learn,         │    │ nia_docs         │   │
│  └──────────────────┘        │  --sessions)      │    │ firecrawl_scrape │   │
│                              └──────────────────┘    │ github_search    │   │
│                                                      │ morph_search     │   │
│                                                      │ ast_grep_find    │   │
│                                                      │ qlty_check       │   │
│                                                      └──────────────────┘   │
│                                                                             │
│  Executed via: uv run python -m runtime.harness scripts/<script>.py        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES (Optional)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │Braintrust│  │Perplexity│  │ Firecrawl│  │   Morph  │  │   Nia    │      │
│  │ Tracing  │  │  Search  │  │  Scrape  │  │ WarpGrep │  │   Docs   │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
│                                                                             │
│  Local-only: git, ast-grep, qlty                                           │
│  License required: repoprompt (Pro for MCP tools)                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Session Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         THE CONTINUITY LOOP                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  1. SESSION START                     2. WORKING
  ┌────────────────────┐               ┌────────────────────┐
  │                    │               │                    │
  │  Ledger loaded ────┼──▶ Context    │  PostToolUse ──────┼──▶ Index handoffs
  │  Handoff loaded    │               │  UserPrompt ───────┼──▶ Skill hints
  │  Learnings shown   │               │  SubagentStop ─────┼──▶ Agent reports
  │                    │               │                    │
  └────────────────────┘               └────────────────────┘
           │                                    │
           │                                    ▼
           │                           ┌────────────────────┐
           │                           │ 3. PRE-COMPACT     │
           │                           │                    │
           │                           │  Auto-handoff ─────┼──▶ thoughts/
           │                           │  Block manual      │
           │                           │                    │
           │                           └────────────────────┘
           │                                    │
           │                                    ▼
           │                           ┌────────────────────┐
           │                           │ 4. SESSION END     │
           │                           │                    │
           │                           │  Mark outcome ─────┼──▶ artifact.db
           │                           │  Extract learnings ┼──▶ cache/
           │                           │  Cleanup           │
           │                           │                    │
           │                           └────────────────────┘
           │                                    │
           │                                    │
           └──────────────◀────── /clear ◀──────┘
                          Fresh context + state preserved
```

### The 3-Step Agent Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PLAN → VALIDATE → IMPLEMENT                              │
└─────────────────────────────────────────────────────────────────────────────┘

  "Design a feature"          "Ready to implement"        "Execute the plan"
         │                           │                           │
         ▼                           ▼                           ▼
  ┌──────────────┐           ┌──────────────┐           ┌──────────────┐
  │ plan-agent   │──────────▶│validate-agent│──────────▶│implement_plan│
  │              │           │              │           │              │
  │ Research     │           │ RAG-judge    │           │ Orchestrate  │
  │ Design       │           │ WebSearch    │           │ Task agents  │
  │ Write plan   │           │ Flag issues  │           │ TDD workflow │
  └──────────────┘           └──────────────┘           └──────────────┘
         │                           │                           │
         ▼                           ▼                           ▼
  thoughts/shared/           Validation report         thoughts/shared/
  plans/*.md                 (in context)              handoffs/session/*.md
```

---

## The Problem

When Claude Code runs low on context, it compacts (summarizes) the conversation. Each compaction is lossy. After several, you're working with a summary of a summary of a summary. Signal degrades into noise.

```
Session Start: Full context, high signal
    ↓ work, work, work
Compaction 1: Some detail lost
    ↓ work, work, work
Compaction 2: Context getting murky
    ↓ work, work, work
Compaction 3: Now working with compressed noise
    ↓ Claude starts hallucinating context
```

## The Solution

**Clear, don't compact.** Save state to a ledger, wipe context, resume fresh.

```
Session Start: Fresh context + ledger loaded
    ↓ focused work
Complete task, save to ledger
    ↓ /clear
Fresh context + ledger loaded
    ↓ continue with full signal
```

**Why this works:**
- Ledgers are lossless - you control what's saved
- Fresh context = full signal
- Agents spawn with clean context, not degraded summaries

---

## Quick Start

**Which option?**
- Just trying it on ONE project? → Start with Option 1
- Want it on ALL your projects? → Do Option 2 (global), then Option 3 (per-project)

### Option 1: Use in This Project

```bash
# Clone
git clone https://github.com/parcadei/claude-continuity-kit.git
cd claude-continuity-kit

# Install Python deps
uv sync

# Configure (optional - add API keys for extra features)
cp .env.example .env

# Start
claude
```

**Works immediately** - hooks are pre-bundled, no `npm install` needed.

### Option 2: Install Globally (Use in Any Project)

```bash
# After cloning and syncing
./install-global.sh
```

**What it does:**

```
┌─────────────────────────────────────────────────────────────┐
│  Continuous Claude - Global Installation                    │
└─────────────────────────────────────────────────────────────┘

This will install to: ~/.claude

⚠️  WARNING: The following will be REPLACED:
   • ~/.claude/skills/     (all skills)
   • ~/.claude/agents/     (all agents)
   • ~/.claude/rules/      (all rules)
   • ~/.claude/hooks/      (all hooks)
   • ~/.claude/settings.json (backup created)

✓ PRESERVED (not touched):
   • ~/.claude/.env
   • ~/.claude/cache/
   • ~/.claude/state/

📦 A full backup will be created at ~/.claude-backup-<timestamp>

Continue with installation? [y/N] y

Installing Continuous Claude to ~/.claude...

✓ uv installed (Python package manager)
✓ qlty installed (code quality toolkit)
Installing MCP runtime package globally...
✓ MCP commands installed: mcp-exec, mcp-generate, mcp-discover

Creating full backup at ~/.claude-backup-20251225_043445...
Backup complete. To restore: rm -rf ~/.claude && mv ~/.claude-backup-<timestamp> ~/.claude

Copying skills...
Copying agents...
Copying rules...
Copying hooks...
Copying scripts...
Copying plugins...
Installing settings.json...
Creating .env template...

Installation complete!
```

**Global MCP cleanup (optional):**

If you have MCP servers defined globally in `~/.claude.json`, the script detects them:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  GLOBAL MCP SERVERS DETECTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Found 9 global MCP servers in ~/.claude.json:
  • agi-memory
  • ast-grep
  • beads
  • firecrawl
  • github
  ...

These servers are inherited by ALL projects and can cause
skills to use unexpected tools (e.g., /onboard using 'beads').

Recommended: Remove global MCP servers and configure them
per-project in each project's .mcp.json instead.

Remove global MCP servers from ~/.claude.json? [y/N] y
Backup created: ~/.claude.json.backup.<timestamp>
✓ Removed global MCP servers

To restore: cp ~/.claude.json.backup.<timestamp> ~/.claude.json
```

**Why remove global MCP?** Global MCP servers are inherited by ALL projects. This can cause unexpected behavior where skills use random tools instead of following their instructions. Best practice: configure MCP servers per-project in `.mcp.json`.

### Option 3: Initialize a New Project

After global install, set up any project for full continuity support:

```bash
cd your-project
~/.claude/scripts/init-project.sh
```

**What it does:**

```
┌─────────────────────────────────────────────────────────────┐
│  Continuous Claude - Project Initialization                 │
└─────────────────────────────────────────────────────────────┘

This will create:
  • thoughts/ledgers/     - Continuity ledgers
  • thoughts/shared/      - Plans and handoffs
  • .claude/cache/        - Artifact Index database

Project: /path/to/your-project

Continue? [y/N] y

Creating directories...
✓ thoughts/ledgers/
✓ thoughts/shared/handoffs/
✓ thoughts/shared/plans/
✓ .claude/cache/artifact-index/

Initializing Artifact Index database...
✓ Created context.db with FTS5 schema

Adding to .gitignore...
✓ Added .claude/cache/ to .gitignore

Project initialized! You can now:
  • Use /continuity_ledger to save session state
  • Use /create_handoff to create session handoffs
  • Use /onboard to analyze the codebase
```

This creates:
- `thoughts/` - Plans, handoffs, ledgers (gitignored)
- `.claude/cache/artifact-index/` - Local search database (SQLite + FTS5)
- Adds `.claude/cache/` to `.gitignore`

**For brownfield projects**, run `/onboard` after initialization to analyze the codebase and create an initial ledger.

### What's Optional?

All external services are optional. Without API keys:
- **Continuity system**: Works (no external deps)
- **TDD workflow**: Works (no external deps)
- **Session tracing**: Disabled (needs BRAINTRUST_API_KEY)
- **Web search**: Disabled (needs PERPLEXITY_API_KEY)
- **Code search**: Falls back to grep (MORPH_API_KEY speeds it up)

See `.env.example` for the full list of optional services.

---

## How to Talk to Claude

This kit responds to natural language triggers. Say certain phrases and Claude activates the right skill or spawns an agent.

### Session Management

| Say This | What Happens |
|----------|--------------|
| "save state", "update ledger", "before clear" | Updates continuity ledger, preserves state for `/clear` |
| "done for today", "wrap up", "create handoff" | Creates detailed handoff doc for next session |
| "resume work", "continue from handoff", "pick up where" | Loads handoff, analyzes context, continues |

### Onboarding (New Projects)

| Say This | What Happens |
|----------|--------------|
| "onboard", "get familiar", "analyze this project" | Runs **/onboard** skill - analyzes codebase, creates initial ledger |
| "explore codebase", "understand the code", "what does this do" | Spawns **rp-explorer** for token-efficient exploration |

**The `/onboard` skill** is designed for brownfield projects (existing codebases). It:

1. **Checks prerequisites** - Verifies `thoughts/` structure exists (run `init-project.sh` first)
2. **Analyzes codebase** - Uses RepoPrompt if available, falls back to bash commands:
   - `rp-cli -e 'tree'` - Directory structure
   - `rp-cli -e 'builder "understand the codebase"'` - AI-powered file selection
   - `rp-cli -e 'structure .'` - Code signatures (token-efficient)
3. **Detects tech stack** - Language, framework, database, testing, CI/CD
4. **Asks your goal** - Feature work, bug fixes, refactoring, or learning
5. **Creates continuity ledger** - At `thoughts/ledgers/CONTINUITY_CLAUDE-<project>.md`

**Example workflow:**
```bash
# 1. Initialize project structure
~/.claude/scripts/init-project.sh

# 2. Start Claude and onboard
claude
> /onboard
```

### Planning & Implementation

| Say This | What Happens |
|----------|--------------|
| "create plan", "design", "architect", "greenfield" | Spawns **plan-agent** to create implementation plan |
| "validate plan", "before implementing", "ready to implement" | Spawns **validate-agent** (RAG-judge + WebSearch) |
| "implement plan", "execute plan", "run the plan" | Spawns **implement_plan** with agent orchestration |
| "verify implementation", "did it work", "check code" | Runs **validate_plan** to verify against plan |

**The 3-step flow:**
```
1. plan-agent     → Creates plan in thoughts/shared/plans/
2. validate-agent → RAG-judge (past precedent) + WebSearch (best practices)
3. implement_plan → Executes with task agents, creates handoffs
```

### Code Quality

| Say This | What Happens |
|----------|--------------|
| "implement", "add feature", "fix bug", "refactor" | **TDD workflow** activates - write failing test first |
| "lint", "code quality", "auto-fix", "check code" | Runs **qlty-check** (70+ linters, auto-fix) |
| "commit", "push", "save changes" | Runs **commit** skill (removes Claude attribution) |
| "describe pr", "create pr" | Generates PR description from changes |

### Codebase Exploration

| Say This | What Happens |
|----------|--------------|
| "brownfield", "existing codebase", "repoprompt" | Spawns **rp-explorer** - uses RepoPrompt for token-efficient exploration |
| "how does X work", "trace", "data flow", "deep dive" | Spawns **codebase-analyzer** for detailed analysis |
| "find files", "where are", "which files handle" | Spawns **codebase-locator** (super grep/glob) |
| "find examples", "similar pattern", "how do we do X" | Spawns **codebase-pattern-finder** |
| "explore", "get familiar", "overview" | Spawns **explore** agent with configurable depth |

**rp-explorer uses RepoPrompt tools** (requires Pro license - $14.99/mo or $349 lifetime):
- **Context Builder** - Deep AI-powered exploration (async, 30s-5min)
- **Codemaps** - Function/class signatures without full file content (10x fewer tokens)
- **Slices** - Read specific line ranges, not whole files
- **Search** - Pattern matching with context lines
- **Workspaces** - Switch between projects

*Free tier available with basic features (32k token limit, no MCP server)*

### Research

| Say This | What Happens |
|----------|--------------|
| "research", "investigate", "find out", "best practices" | Spawns **research-agent** (uses MCP tools) |
| "research repo", "analyze this repo", "clone and analyze" | Spawns **repo-research-analyst** |
| "docs", "documentation", "library docs", "API reference" | Runs **nia-docs** for library documentation |
| "web search", "look up", "latest", "current info" | Runs **perplexity-search** for web research |

### Debugging

| Say This | What Happens |
|----------|--------------|
| "debug", "investigate issue", "why is it broken" | Spawns **debug-agent** (logs, code search, git history) |
| "not working", "error", "failing", "what's wrong" | Same - triggers debug-agent |

### Code Search

| Say This | What Happens |
|----------|--------------|
| "search code", "grep", "find in code", "find text" | Runs **morph-search** (20x faster than grep) |
| "ast", "find all calls", "refactor", "codemod" | Runs **ast-grep-find** (structural search) |
| "search github", "find repo", "github issue" | Runs **github-search** |

### Learning & Insights

| Say This | What Happens |
|----------|--------------|
| "compound learnings", "turn learnings into rules" | Runs **compound-learnings** - transforms session learnings into skills/rules |
| "analyze session", "what happened", "session insights" | Runs **braintrust-analyze** to review traces |
| "recall", "what was tried", "past reasoning" | Searches **reasoning history** |

### Hook Development

| Say This | What Happens |
|----------|--------------|
| "create hook", "write hook", "hook for" | Loads **hook-developer** skill - complete reference for all 10 hook types |
| "hook schema", "hook input", "hook output" | Same - shows input/output schemas, matchers, testing patterns |
| "debug hook", "hook not working", "hook failing" | Runs **debug-hooks** skill - systematic debugging workflow |

**The `/hook-developer` skill** is a comprehensive reference covering:
- All 10 Claude Code hook types (PreToolUse, PostToolUse, SessionStart, etc.)
- Input/output JSON schemas for each hook
- Matcher patterns and registration in settings.json
- Shell wrapper → TypeScript handler pattern
- Testing commands for manual hook validation

### Other

| Say This | What Happens |
|----------|--------------|
| "scrape", "fetch url", "crawl" | Runs **firecrawl-scrape** |
| "create skill", "skill triggers", "skill system" | Runs **skill-developer** meta-skill |
| "codebase structure", "file tree", "signatures" | Runs **repoprompt** for code maps |

---

## Skills vs Agents

**Skills** run in current context. Quick, focused, minimal token overhead.

**Agents** spawn with fresh context. Use for complex tasks that would degrade in a compacted context. They return a summary and optionally create handoffs.

### When to Use Agents

- Brownfield exploration → `rp-explorer` first
- Multi-step research → `research-agent`
- Complex debugging → `debug-agent`
- Implementation with handoffs → `implement_plan`

### Agent Orchestration

For large implementations, `implement_plan` spawns task agents:

```
implement_plan (orchestrator)
    ├── task-agent (task 1) → handoff-01.md
    ├── task-agent (task 2) → handoff-02.md
    └── task-agent (task 3) → handoff-03.md
```

Each task agent:
1. Reads previous handoff
2. Does its work with TDD
3. Creates handoff for next agent
4. Returns summary to orchestrator

---

## MCP Code Execution

Tools are executed via scripts, not loaded into context. This saves tokens.

```bash
# Example: run a script
uv run python -m runtime.harness scripts/qlty_check.py --fix

# Available scripts
ls scripts/
```

### Adding MCP Servers

1. Edit `mcp_config.json` (or `.mcp.json`)
2. Add API keys to `.env`
3. Run `uv run mcp-generate`

```json
{
  "mcpServers": {
    "my-server": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "my-mcp-server"],
      "env": { "API_KEY": "${MY_API_KEY}" }
    }
  }
}
```

### Developing Custom MCP Scripts

After running `install-global.sh`, you can create and run MCP scripts from any project:

```bash
# Global commands available everywhere
mcp-exec scripts/my_script.py      # Run a script
mcp-generate                        # Generate wrappers for configured servers
```

**Config Merging:** Global config (`~/.claude/mcp_config.json`) is merged with project config (`.mcp.json` or `mcp_config.json`). Project settings override global for same-named servers.

**Creating a new script:**

```python
# scripts/my_tool.py
"""
USAGE: uv run python -m runtime.harness scripts/my_tool.py --query "search term"
"""
import argparse
from runtime.mcp_client import call_mcp_tool

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    args = parser.parse_args()

    # Tool format: serverName__toolName
    result = await call_mcp_tool("my-server__search", {"query": args.query})
    print(result)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

**Creating a skill wrapper:**

```bash
mkdir -p .claude/skills/my-tool
cat > .claude/skills/my-tool/SKILL.md << 'EOF'
---
name: my-tool
description: Search with my tool
---
# My Tool

```bash
uv run python -m runtime.harness scripts/my_tool.py --query "your query"
```
EOF
```

**Adding skill triggers for auto-activation:**

```json
// .claude/skills/skill-rules.json
{
  "skills": {
    "my-tool": {
      "type": "domain",
      "enforcement": "suggest",
      "priority": "high",
      "description": "Search with my tool",
      "promptTriggers": {
        "keywords": ["my-tool", "search with tool"],
        "intentPatterns": ["(search|find).*?with.*?tool"]
      }
    }
  }
}
```

**Enforcement levels:**
- `suggest` - Skill appears as suggestion (most common)
- `block` - Requires skill before proceeding (guardrail)
- `warn` - Shows warning but allows proceeding

**Priority levels:** `critical` > `high` > `medium` > `low`

#### Agent Integration

Agents can reference your scripts for complex workflows. Example from `.claude/agents/research-agent.md`:

```markdown
## Step 3: Research with MCP Tools

### For External Knowledge
```bash
# Documentation search (Nia)
uv run python -m runtime.harness scripts/nia_docs.py --query "your query"

# Web research (Perplexity)
uv run python -m runtime.harness scripts/perplexity_search.py --query "your query"
```

### For Codebase Knowledge
```bash
# Fast code search (Morph)
uv run python -m runtime.harness scripts/morph_search.py --query "pattern" --path "."
```
\```
```

Agents use MCP scripts to:
- Perform research across multiple sources
- Investigate issues with codebase search
- Apply fixes using fast editing tools
- Gather information for analysis

See `.claude/agents/research-agent.md` and `.claude/agents/debug-agent.md` for complete examples.

#### Full Pattern: MCP Server → Scripts → Skills → Agents

The complete integration flow:

```
1. MCP Server Configuration
   ↓ (mcp_config.json or .mcp.json)

2. Script Creation
   ↓ (scripts/my_tool.py with CLI args)

3. Skill Wrapper
   ↓ (.claude/skills/my-tool/SKILL.md)

4. Skill Triggers
   ↓ (.claude/skills/skill-rules.json)

5. Agent Integration (optional)
   ↓ (.claude/agents/my-agent.md references the script)

6. Auto-activation
   → User types trigger keyword → Skill suggests → Script executes
```

**Real-world example:** `morph-search`

1. **Server:** `morph` MCP server in `mcp_config.json`
2. **Script:** `scripts/morph_search.py` with `--query`, `--path` args
3. **Skill:** `.claude/skills/morph-search/SKILL.md` documents usage
4. **Triggers:** `.claude/skills/skill-rules.json` activates on "search code", "fast search"
5. **Agents:** `research-agent.md` and `debug-agent.md` use for codebase search
6. **Activation:** User says "search code for error handling" → auto-suggests

**Key benefits:**
- **Progressive disclosure:** 110 tokens (99.6% reduction) vs full tool schemas
- **Reusability:** Scripts work for agents, skills, and direct execution
- **Auto-discovery:** skill-rules.json enables context-aware suggestions
- **Flexibility:** Change parameters via CLI, no code edits needed

---

## Continuity System

### Ledger (within session)

Before running `/clear`:
```
"Update the ledger, I'm about to clear"
```

Creates/updates `CONTINUITY_CLAUDE-<session>.md` with:
- Goal and constraints
- What's done, what's next
- Key decisions
- Working files

After `/clear`, the ledger loads automatically.

---

## Memory System

Agents spawned via `tracked_spawn()` have persistent memory auto-wired:

```python
from scripts.agentica_patterns.tracked_agent import tracked_spawn

# Memory is automatic - no setup required
agent = await tracked_spawn(db=db, premise="Research task")

# Agent scope includes:
# scope["remember"](key, value)       - Core memory
# scope["recall"](query)              - Search all memory
# scope["store_fact"](content, tags)  - Archival memory
# scope["search_memory"](query, ...)  - Full-text search
```

**Features:**
- **Datetime filtering**: `scope["recall"]("notes", start_date="2025-01-01")`
- **Tag filtering**: `scope["search_memory"]("api", tags=["important"], tag_match_mode="any")`
- **Conversation search**: `scope["conversation_search"]("debugging", roles=["user"])`
- **Block-based core memory**: Letta-compatible structured blocks
- **RRF hybrid search**: FTS + vector with Reciprocal Rank Fusion

**Backends:** SQLite (development) or PostgreSQL with pgvector (production)

**Documentation:**
- [Memory System Guide](docs/memory-system-guide.md) - User guide with examples
- [Memory Architecture](docs/architecture/memory-system.md) - Technical details
- [Migration Guide](docs/migration/memory-auto-wiring.md) - From manual to auto-wired

---

### Handoff (between sessions)

When done for the day:
```
"Create a handoff, I'm done for today"
```

Creates `thoughts/handoffs/<session>/handoff-<timestamp>.md` with:
- Detailed context
- Recent changes with file:line references
- Learnings and patterns
- Next steps

Next session:
```
"Resume from handoff"
```

---

## Hooks System

Hooks are the backbone of continuity. They intercept Claude Code lifecycle events and automate state preservation.

### StatusLine (Context Indicator)

The colored status bar shows context usage in real-time:

```
45.2K 23% | main U:3 | ✓ Fixed auth → Add tests
 ↑     ↑      ↑   ↑        ↑           ↑
 │     │      │   │        │           └── Current focus (from ledger)
 │     │      │   │        └── Last completed item
 │     │      │   └── Uncommitted changes (Staged/Unstaged/Added)
 │     │      └── Git branch
 │     └── Context percentage used
 └── Token count
```

**Color coding:**

| Color | Range | Meaning |
|-------|-------|---------|
| 🟢 Green | < 60% | Normal - full continuity info shown |
| 🟡 Yellow | 60-79% | Warning - consider creating handoff soon |
| 🔴 Red | ≥ 80% | Critical - shows `⚠` icon, prompts handoff |

The StatusLine writes context % to `/tmp/claude-context-pct-{SESSION_ID}.txt` (per-session to avoid multi-instance conflicts).

### Hook Events

| Event | When | What This Kit Does |
|-------|------|-------------------|
| **SessionStart** | New session, `/clear`, compact | Loads ledger + latest handoff into context |
| **PreToolUse** | Before tool execution | **TypeScript preflight** - catches type errors before Edit/Write on .ts files |
| **PreCompact** | Before context compaction | Creates auto-handoff, blocks manual compact |
| **UserPromptSubmit** | Before processing user message | Shows skill suggestions, context warnings |
| **PostToolUse** | After Edit/Write/Bash | Tracks modified files for auto-summary |
| **SubagentStop** | Agent finishes | Logs agent completion |
| **SessionEnd** | Session closes | Cleanup temp files |

### SessionStart Hook

Runs on: `resume`, `clear`, `compact`

**What it does:**
1. Finds most recent `CONTINUITY_CLAUDE-*.md` ledger
2. Extracts Goal and current focus ("Now:")
3. Finds latest handoff (task-*.md or auto-handoff-*.md)
4. Injects ledger + handoff into system context

**Result:** After `/clear`, Claude immediately knows:
- What you're working on
- What's done vs pending
- Recent decisions and learnings

### PreCompact Hook

Runs: Before any compaction

**Auto-compact (trigger: auto):**
1. Parses transcript to extract tool calls and responses
2. Generates detailed `auto-handoff-<timestamp>.md` with:
   - Files modified
   - Recent tool outputs
   - Current work state
3. Saves to `thoughts/handoffs/<session>/`

**Manual compact (trigger: manual):**
- Blocks compaction
- Prompts you to run `/continuity_ledger` first

### UserPromptSubmit Hook

Runs: Every message you send

**Two functions:**

1. **Skill activation** - Scans your message for keywords defined in `skill-rules.json`. Shows relevant skills:
   ```
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   🎯 SKILL ACTIVATION CHECK
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   ⚠️ CRITICAL SKILLS (REQUIRED):
     → create_handoff

   📚 RECOMMENDED SKILLS:
     → commit
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   ```

2. **Context warnings** - Reads context % and shows tiered warnings:
   - 70%: `Consider handoff when you reach a stopping point.`
   - 80%: `Recommend: /create_handoff then /clear soon`
   - 90%: `CONTEXT CRITICAL: Run /create_handoff NOW!`

### TypeScript Preflight Hook (PreToolUse)

Runs: Before Edit/Write on `.ts` or `.tsx` files

**What it does:**
1. Runs `tsc --noEmit` on the file being edited
2. If type errors exist, blocks the edit and shows errors to Claude
3. Claude fixes the issues before proceeding

**Why this matters:** Catches type errors early, before they compound across multiple edits. Claude sees the errors in context and can fix them immediately.

**Example output when blocked:**
```
TypeScript errors in src/hooks/my-hook.ts:
  Line 15: Property 'result' does not exist on type 'HookOutput'
  Line 23: Argument of type 'string' is not assignable to parameter of type 'number'
```

### How Hooks Work

Hooks are **pre-bundled** - no runtime dependencies needed. Shell wrappers call bundled JS:

```bash
# .claude/hooks/session-start-continuity.sh
#!/bin/bash
set -e
cd "$CLAUDE_PROJECT_DIR/.claude/hooks"
cat | node dist/session-start-continuity.mjs
```

**For developers** who want to modify hooks:
```bash
cd .claude/hooks
vim src/session-start-continuity.ts  # Edit source
./build.sh                            # Rebuild dist/
```

**Note on latency:** Some hooks (especially `SessionEnd` and `Stop`) may add 1-3 seconds of latency as they finalize traces and extract learnings. This is expected - the hooks run fire-and-forget processes that don't block the next session.

Hooks receive JSON input and return JSON output:

```typescript
// Input varies by event type
interface SessionStartInput {
  source: 'startup' | 'resume' | 'clear' | 'compact';
  session_id: string;
}

// Output controls behavior (varies by hook type)
interface HookOutput {
  continue?: boolean;             // true to proceed (default)
  decision?: 'block';             // Block stops the action (PreToolUse only)
  reason?: string;                // Shown when blocking
  hookSpecificOutput?: {          // Injected into context
    additionalContext: string;
  };
}
```

### Registering Hooks

Hooks are configured in `.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "$CLAUDE_PROJECT_DIR/.claude/scripts/status.sh"
  },
  "hooks": {
    "SessionStart": [{
      "matcher": "clear",
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/session-start-continuity.sh"
      }]
    }]
  }
}
```

**Matcher patterns:** Use `|` for multiple triggers: `"Edit|Write|Bash"`

---

## Reasoning History

The system captures what was tried during development - build failures, fixes, experiments. This creates searchable memory across sessions.

**How it works:**

1. **During work** - The `/commit` skill tracks what was attempted
2. **On commit** - `generate-reasoning.sh` saves attempts to `.git/claude/commits/<hash>/reasoning.md`
3. **Later** - "recall what was tried" searches past reasoning for similar problems

**Scripts in `.claude/scripts/`:**

| Script | Purpose |
|--------|---------|
| `generate-reasoning.sh` | Captures attempts after each commit |
| `search-reasoning.sh` | Finds past solutions to similar problems |
| `aggregate-reasoning.sh` | Combines reasoning across commits |
| `status.sh` | StatusLine - shows context %, git status, focus |

**Example:**
```
"recall what was tried for authentication bugs"
→ Searches .git/claude/commits/*/reasoning.md
→ Returns: "In commit abc123, tried X but failed because Y, fixed with Z"
```

This is why `/commit` matters - it's not just git, it's building Claude's memory.

---

## Braintrust Session Tracing (Optional)

Track every session with Braintrust for learning from past work.

### What It Provides

1. **Session traces** - Every turn, tool call, and LLM response logged
2. **Automatic learnings** - At session end, extracts "What Worked/Failed/Patterns"
3. **Artifact Index integration** - Handoffs linked to trace IDs for correlation

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        BRAINTRUST TRACING ARCHITECTURE                      │
└─────────────────────────────────────────────────────────────────────────────┘

                             ┌─────────────────┐
                             │   Braintrust    │
                             │     Cloud       │
                             │  (braintrust.   │
                             │      dev)       │
                             └────────┬────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              │                       │                       │
              ▼                       ▼                       ▼
      ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
      │   Project A  │       │   Project B  │       │   Project C  │
      │   (traces)   │       │   (traces)   │       │   (traces)   │
      └──────────────┘       └──────────────┘       └──────────────┘


                    WITHIN A PROJECT: Session Trace Structure
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   SESSION (root span) ─── created by SessionStart hook                      │
│   │                                                                         │
│   ├── TURN 1 (task span) ─── created by UserPromptSubmit hook              │
│   │   │                                                                     │
│   │   ├── LLM Call (llm span) ─── created by Stop hook                     │
│   │   │   └── input: [user message], output: [assistant + tool_use]        │
│   │   │                                                                     │
│   │   ├── Tool: Read file.ts (tool span) ─── PostToolUse hook              │
│   │   ├── Tool: Edit file.ts (tool span) ─── PostToolUse hook              │
│   │   │                                                                     │
│   │   └── LLM Call (llm span) ─── created by Stop hook                     │
│   │       └── input: [tool results], output: [assistant response]          │
│   │                                                                         │
│   ├── TURN 2 (task span)                                                   │
│   │   └── ... (same structure)                                             │
│   │                                                                         │
│   └── TURN N (task span)                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


                    CROSS-SESSION: The Learning Loop
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   SESSION 1                SESSION 2                SESSION 3               │
│   ┌─────────┐              ┌─────────┐              ┌─────────┐             │
│   │  Work   │              │  Work   │              │  Work   │             │
│   │   +     │              │   +     │              │   +     │             │
│   │ Traces  │              │ Traces  │              │ Traces  │             │
│   └────┬────┘              └────┬────┘              └────┬────┘             │
│        │                        │                        │                  │
│        ▼                        ▼                        ▼                  │
│   ┌─────────┐              ┌─────────┐              ┌─────────┐             │
│   │SessionEnd              │SessionEnd              │SessionEnd             │
│   │--learn  │              │--learn  │              │--learn  │             │
│   └────┬────┘              └────┬────┘              └────┬────┘             │
│        │                        │                        │                  │
│        ▼                        ▼                        ▼                  │
│   ┌─────────────────────────────────────────────────────────────┐           │
│   │                .claude/cache/learnings/                      │           │
│   │  ├── 2025-12-24_session-1.md  (What Worked, What Failed)    │           │
│   │  ├── 2025-12-24_session-2.md  (Key Decisions, Patterns)     │           │
│   │  └── 2025-12-25_session-3.md                                │           │
│   └──────────────────────────┬──────────────────────────────────┘           │
│                              │                                              │
│                              ▼                                              │
│                     ┌─────────────────┐                                     │
│                     │  SessionStart   │                                     │
│                     │  (next session) │                                     │
│                     │                 │                                     │
│                     │ Surfaces recent │                                     │
│                     │ learnings (48h) │                                     │
│                     └─────────────────┘                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


                    HANDOFF ↔ TRACE CORRELATION
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│   Handoff File (thoughts/shared/handoffs/session/task-01.md)               │
│   ┌─────────────────────────────────────────────────────────────┐           │
│   │ ---                                                         │           │
│   │ root_span_id: abc-123-main  ◄──── Links to Braintrust trace│           │
│   │ turn_span_id: def-456-turn  ◄──── Span that created it     │           │
│   │ session_id: abc-123-main                                    │           │
│   │ ---                                                         │           │
│   │ # Task: Implement feature X                                 │           │
│   │ ...                                                         │           │
│   └─────────────────────────────────────────────────────────────┘           │
│                              │                                              │
│                              │ Query by span_id                             │
│                              ▼                                              │
│   ┌─────────────────────────────────────────────────────────────┐           │
│   │                    Braintrust Trace                         │           │
│   │  - See exact tool calls that produced the handoff           │           │
│   │  - Review token usage and timing                            │           │
│   │  - Debug what went wrong in failed sessions                 │           │
│   └─────────────────────────────────────────────────────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Built on braintrust-claude-plugin

This kit extends the [official Braintrust Claude plugin](https://github.com/braintrustdata/braintrust-claude-plugin), which provides a single `stop_hook.sh` for basic session tracing. We've enhanced it with:

| Original Plugin | Our Enhancements |
|-----------------|------------------|
| `stop_hook.sh` only | Full hook suite (6 hooks) |
| Basic session logging | Hierarchical span structure |
| No learning extraction | Auto-extracts learnings at session end |
| No cross-session memory | Surfaces learnings at session start |
| No handoff correlation | Links handoffs to trace IDs |

**Our additions:**

| Hook | Purpose |
|------|---------|
| `common.sh` | Shared utilities (UUID, timestamps, state management) |
| `session_start.sh` | Creates root span for the session |
| `user_prompt_submit.sh` | Creates turn spans, reconciles interrupted sessions |
| `post_tool_use.sh` | Logs tool spans with input/output |
| `stop_hook.sh` | Enhanced - creates LLM spans with full conversation context |
| `session_end.sh` | Triggers `braintrust_analyze.py --learn` for auto-learning |

**Key improvements:**

1. **Hierarchical tracing** - Session → Turn → Tool/LLM spans (not flat logs)
2. **Cross-session learning** - Extracts patterns from past sessions
3. **Artifact correlation** - Handoffs linked to traces via `root_span_id`
4. **Multi-project support** - Each project gets its own trace namespace
5. **Fix for large content** - Uses temp files to avoid shell argument limits

### Enabling Braintrust

1. **Get API key** from [braintrust.dev](https://braintrust.dev)

2. **Add to environment:**
   ```bash
   echo 'BRAINTRUST_API_KEY="sk-..."' >> ~/.claude/.env
   ```

3. **Hooks are pre-configured** - The plugin is bundled in `.claude/plugins/braintrust-tracing/`

### How It Works

| Hook | What It Does |
|------|--------------|
| **SessionStart** | Creates root span for the session trace |
| **UserPromptSubmit** | Creates turn span, reconciles interrupted turns |
| **PostToolUse** | Logs tool spans with input/output |
| **Stop** | Finalizes current turn span |
| **SessionEnd** | Closes session trace, triggers `--learn` |

### The Learning Loop

```
1. You work → Braintrust traces every interaction
2. /clear or exit → SessionEnd triggers braintrust_analyze.py --learn
3. LLM extracts: What Worked, What Failed, Key Decisions, Patterns
4. Saves to: .claude/cache/learnings/<date>_<session_id>.md
5. Next session → SessionStart surfaces learnings from last 48h
```

### Artifact Index + Braintrust

Handoffs are automatically linked to Braintrust traces:

```yaml
# Handoff frontmatter (auto-injected by PostToolUse hook)
root_span_id: abc-123-main    # Braintrust trace ID
turn_span_id: def-456-turn    # Span that created this handoff
session_id: abc-123-main      # Claude session ID
```

This enables:
- **Trace → Handoff** correlation (what work produced this handoff?)
- **Session family queries** (all handoffs from session X)
- **RAG-enhanced judging** (Artifact Index precedent for plan validation)

### Disabling Braintrust

Remove or comment out the Braintrust hooks in `.claude/settings.json`:
```json
{
  "hooks": {
    "SessionStart": [
      // Comment out the braintrust-tracing hooks
    ]
  }
}
```

### Scripts

| Script | Purpose |
|--------|---------|
| `braintrust_analyze.py --sessions N` | List recent sessions |
| `braintrust_analyze.py --replay <id>` | View session trace |
| `braintrust_analyze.py --learn` | Extract learnings from last session |
| `braintrust_analyze.py --learn --session-id <id>` | Learn from specific session |

### Compound Learnings

After several sessions, you accumulate learnings in `.claude/cache/learnings/`. Run the `/compound-learnings` skill to transform these into permanent rules:

```
"compound my learnings"
→ Analyzes .claude/cache/learnings/*.md
→ Identifies recurring patterns
→ Creates new rules in .claude/rules/
→ Archives processed learnings
```

This closes the loop: **sessions → learnings → rules → better sessions**.

---

## Artifact Index

A local SQLite database that indexes handoffs and plans for fast search.

### What It Does

- **Indexes handoffs** with full-text search (FTS5)
- **Tracks session outcomes** (SUCCEEDED, PARTIAL, FAILED)
- **Links to Braintrust traces** for correlation
- **Surfaces unmarked handoffs** at session start

### How It Works

```
1. Create handoff → PostToolUse hook indexes it immediately
2. Session ends → Prompts you to mark outcome
3. Next session → SessionStart surfaces unmarked handoffs
4. Mark outcomes → Improves future session recommendations
```

### Marking Outcomes

After completing work, mark the outcome:

```bash
# List unmarked handoffs
uv run python scripts/artifact_query.py --unmarked

# Mark an outcome
uv run python scripts/artifact_mark.py \
  --handoff abc123 \
  --outcome SUCCEEDED
```

**Outcomes:** SUCCEEDED | PARTIAL_PLUS | PARTIAL_MINUS | FAILED

### Querying the Index

```bash
# Search handoffs by content
uv run python scripts/artifact_query.py --search "authentication bug"

# Get session history
uv run python scripts/artifact_query.py --session open-source-release
```

---

## TDD Workflow

When you say "implement", "add feature", or "fix bug", TDD activates:

```
1. RED    - Write failing test first
2. GREEN  - Minimal code to pass
3. REFACTOR - Clean up, tests stay green
```

**The rule:** No production code without a failing test.

If you write code first, the skill prompts you to delete it and start with a test.

---

## Code Quality (qlty)

**Automatically installed** by `install-global.sh`. The `.qlty/` config is included in this repo, so no `qlty init` needed.

Manual install (if needed):
```bash
curl -fsSL https://qlty.sh/install.sh | bash
```

Use it:
```
"lint my code"
"check code quality"
"auto-fix issues"
```

Or directly:
```bash
qlty check --fix
qlty fmt
qlty metrics
```

---

## Directory Structure

```
.claude/
├── skills/          # Skill definitions (SKILL.md)
├── hooks/           # Session lifecycle (TypeScript)
├── agents/          # Agent configurations
├── rules/           # Behavioral rules
└── settings.json    # Hook registrations

scripts/             # MCP workflow scripts
servers/             # Generated tool wrappers (gitignored)
thoughts/            # Research, plans, handoffs (gitignored)
src/runtime/         # MCP execution runtime
```

---

## Environment Variables

Add to `.env`:

```bash
# Required for paid services
GITHUB_PERSONAL_ACCESS_TOKEN="ghp_..."
PERPLEXITY_API_KEY="pplx-..."
FIRECRAWL_API_KEY="fc-..."
MORPH_API_KEY="sk-..."
NIA_API_KEY="nk_..."
```

Services without API keys still work:
- `git` - local git operations
- `ast-grep` - structural code search
- `qlty` - code quality (auto-installed by `install-global.sh`)

License-based (no API key, requires purchase):
- `repoprompt` - codebase maps (Free tier: basic features; Pro: MCP tools, CodeMaps)

---

## Glossary

| Term | Definition |
|------|------------|
| Session | A single Claude Code conversation (from start to /clear or exit) |
| Ledger | In-session state file (`CONTINUITY_CLAUDE-*.md`) that survives /clear |
| Handoff | End-of-session document for transferring work to a new session |
| Outcome | Session result marker: SUCCEEDED, PARTIAL_PLUS, PARTIAL_MINUS, FAILED |
| Span | Braintrust trace unit - a turn or tool call within a session |
| Artifact Index | SQLite database indexing handoffs, plans, and ledgers for RAG queries |

---

## Troubleshooting

**"MCP server not configured"**
- Check `mcp_config.json` exists
- Run `uv run mcp-generate`
- Verify `.env` has required keys

**Skills not working**
- Run via harness: `uv run python -m runtime.harness scripts/...`
- Not directly: `python scripts/...`

**Ledger not loading**
- Check `CONTINUITY_CLAUDE-*.md` exists
- Verify hooks are registered in `.claude/settings.json`
- Make hooks executable: `chmod +x .claude/hooks/*.sh`

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Quick start:**

```bash
# Fork and clone
git clone https://github.com/your-username/claude-continuity-kit.git
cd claude-continuity-kit

# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest tests/unit/
```

---

## Acknowledgments

### Patterns & Architecture
- **[@numman-ali](https://github.com/numman-ali)** - Continuity ledger pattern
- **[Anthropic](https://anthropic.com)** - [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- **[obra/superpowers](https://github.com/obra/superpowers)** - Agent orchestration patterns
- **[EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin)** - Compound engineering workflow
- **[yoloshii/mcp-code-execution-enhanced](https://github.com/yoloshii/mcp-code-execution-enhanced)** - Enhanced MCP execution
- **[HumanLayer](https://github.com/humanlayer/humanlayer)** - Agent patterns

### Tools & Services
- **[Braintrust](https://braintrust.dev)** - LLM evaluation, logging, and session tracing
- **[qlty](https://github.com/qltysh/qlty)** - Universal code quality CLI (70+ linters)
- **[ast-grep](https://github.com/ast-grep/ast-grep)** - AST-based code search and refactoring
- **[Nia](https://trynia.ai)** - Library documentation search
- **[Morph](https://www.morphllm.com)** - WarpGrep fast code search
- **[Firecrawl](https://www.firecrawl.dev)** - Web scraping API
- **[RepoPrompt](https://repoprompt.com)** - Token-efficient codebase maps (Pro license for MCP tools)

---

## License

MIT License - see [LICENSE](LICENSE) for details.

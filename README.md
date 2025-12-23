# Continuous Claude

Session continuity, token-efficient MCP execution, and agentic workflows for Claude Code.

---

## Table of Contents

- [The Problem](#the-problem) / [The Solution](#the-solution)
- [Quick Start](#quick-start)
- [How to Talk to Claude](#how-to-talk-to-claude)
- [Skills vs Agents](#skills-vs-agents)
- [MCP Code Execution](#mcp-code-execution)
- [Continuity System](#continuity-system)
- [Hooks System](#hooks-system)
- [Reasoning History](#reasoning-history)
- [TDD Workflow](#tdd-workflow)
- [Code Quality (qlty)](#code-quality-qlty)
- [Directory Structure](#directory-structure)
- [Environment Variables](#environment-variables)
- [Troubleshooting](#troubleshooting)
- [Acknowledgments](#acknowledgments)

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

```bash
# Clone
git clone https://github.com/parcadei/claude-continuity-kit.git
cd claude-continuity-kit

# Install Python deps
uv sync

# Configure (add your API keys)
cp .env.example .env

# Generate MCP wrappers
uv run mcp-generate

# Start
claude
```

**Zero-dep hooks** - hooks are pre-bundled, no `npm install` needed.

The continuity system loads automatically via hooks.

---

## How to Talk to Claude

This kit responds to natural language triggers. Say certain phrases and Claude activates the right skill or spawns an agent.

### Session Management

| Say This | What Happens |
|----------|--------------|
| "save state", "update ledger", "before clear" | Updates continuity ledger, preserves state for `/clear` |
| "done for today", "wrap up", "create handoff" | Creates detailed handoff doc for next session |
| "resume work", "continue from handoff", "pick up where" | Loads handoff, analyzes context, continues |

### Planning & Implementation

| Say This | What Happens |
|----------|--------------|
| "create plan", "design", "architect", "greenfield" | Spawns **plan-agent** to create implementation plan |
| "validate plan", "before implementing", "ready to implement" | Spawns **validate-agent** to check tech choices |
| "implement plan", "execute plan", "run the plan" | Spawns **implement_plan** with agent orchestration |
| "verify implementation", "did it work", "check code" | Runs **validate_plan** to verify against plan |

**The 3-step flow:**
```
1. plan-agent     → Creates plan in thoughts/shared/plans/
2. validate-agent → Checks tech choices against best practices
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

**rp-explorer uses RepoPrompt tools:**
- **Context Builder** - Deep AI-powered exploration (async, 30s-5min)
- **Codemaps** - Function/class signatures without full file content (10x fewer tokens)
- **Slices** - Read specific line ranges, not whole files
- **Search** - Pattern matching with context lines
- **Workspaces** - Switch between projects

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

### Other

| Say This | What Happens |
|----------|--------------|
| "scrape", "fetch url", "crawl" | Runs **firecrawl-scrape** |
| "recall", "what was tried", "past reasoning" | Searches **reasoning history** (see below) |
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

Hooks receive JSON input and return JSON output:

```typescript
// Input varies by event type
interface SessionStartInput {
  source: 'startup' | 'resume' | 'clear' | 'compact';
  session_id: string;
}

// Output controls behavior
interface HookOutput {
  result: 'continue' | 'block';  // Block stops the action
  message?: string;               // Shown to user
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

Install qlty:
```bash
curl -fsSL https://qlty.sh/install.sh | bash
qlty init
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
- `repoprompt` - codebase maps
- `qlty` - code quality (after install)

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

## Acknowledgments

### Patterns & Architecture
- **[@numman-ali](https://github.com/numman-ali)** - Continuity ledger pattern
- **[Anthropic](https://anthropic.com)** - [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- **[obra/superpowers](https://github.com/obra/superpowers)** - Agent orchestration patterns
- **[EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin)** - Compound engineering workflow
- **[yoloshii/mcp-code-execution-enhanced](https://github.com/yoloshii/mcp-code-execution-enhanced)** - Enhanced MCP execution
- **[HumanLayer](https://github.com/humanlayer/humanlayer)** - Agent patterns

### Tools & Services
- **[qlty](https://github.com/qltysh/qlty)** - Universal code quality CLI (70+ linters)
- **[ast-grep](https://github.com/ast-grep/ast-grep)** - AST-based code search and refactoring
- **[Nia](https://trynia.ai)** - Library documentation search
- **[Morph](https://www.morphllm.com)** - WarpGrep fast code search
- **[Firecrawl](https://www.firecrawl.dev)** - Web scraping API
- **[RepoPrompt](https://repoprompt.com)** - Token-efficient codebase maps

---

## License

MIT License - see [LICENSE](LICENSE) for details.

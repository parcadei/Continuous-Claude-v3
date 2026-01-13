# Continuous Claude

> A persistent, learning, multi-agent development environment built on Claude Code

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude-Code-orange.svg)](https://claude.ai/code)
[![Skills](https://img.shields.io/badge/Skills-105-green.svg)](#skills-system)
[![Agents](https://img.shields.io/badge/Agents-32-purple.svg)](#agents-system)
[![Hooks](https://img.shields.io/badge/Hooks-65-blue.svg)](#hooks-system)

**Continuous Claude** transforms Claude Code into a continuously learning system that maintains context across sessions, orchestrates specialized agents, and eliminates wasting tokens through intelligent code analysis.

## Table of Contents

- [Why Continuous Claude?](#why-continuous-claude)
- [Design Principles](#design-principles)
- [How to Talk to Claude](#how-to-talk-to-claude)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Core Systems](#core-systems)
  - [Skills (105)](#skills-system)
  - [Agents (32)](#agents-system)
  - [Hooks (65)](#hooks-system)
  - [TLDR Code Analysis](#tldr-code-analysis)
  - [Memory System](#memory-system)
  - [Continuity System](#continuity-system)
  - [Math System](#math-system)
- [Workflows](#workflows)
- [Installation](#installation)
- [Updating](#updating)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [License](#license)

---

## Why Continuous Claude?

Claude Code has a **compaction problem**: when context fills up, the system compacts your conversation, losing nuanced understanding and decisions made during the session.

**Continuous Claude solves this with:**

| Problem | Solution |
|---------|----------|
| Context loss on compaction | YAML handoffs - more token-efficient transfer |
| Starting fresh each session | Memory system recalls + daemon auto-extracts learnings |
| Reading entire files burns tokens | 5-layer code analysis + semantic index |
| Complex tasks need coordination | Meta-skills orchestrate agent workflows |
| Repeating workflows manually | 105 skills with natural language triggers |

**The mantra: Compound, don't compact.** Extract learnings automatically, then start fresh with full context.

### Why "Continuous"? Why "Compounding"?

The name is a pun. **Continuous** because Claude maintains state across sessions. **Compounding** because each session makes the system smarter—learnings accumulate like compound interest.

---

## Design Principles

An agent is five things: **Prompt + Tools + Context + Memory + Model**.

| Component | What We Optimize |
|-----------|------------------|
| **Prompt** | Skills inject relevant context; hooks add system reminders |
| **Tools** | TLDR reduces tokens; agents parallelize work |
| **Context** | Not just *what* Claude knows, but *how* it's provided |
| **Memory** | Daemon extracts learnings; recall surfaces them |
| **Model** | Becomes swappable when the other four are solid |

### Anti-Complexity

We resist plugin sprawl. Every MCP, subscription, and tool you add promises improvement but risks breaking context, tools, or prompts through clashes.

**Our approach:**
- **Time, not money** — No required paid services. Perplexity and NIA are optional, high-value-per-token.
- **Learn, don't accumulate** — A system that learns handles edge cases better than one that collects plugins.
- **Shift-left validation** — Hooks run pyright/ruff after edits, catching errors before tests.

The failure modes of complex systems are structurally invisible until they happen. A learning, context-efficient system doesn't prevent all failures—but it recovers and improves.

---

## How to Talk to Claude

**You don't need to memorize slash commands.** Just describe what you want naturally.

### The Skill Activation System

When you send a message, a hook injects context that tells **Claude** which skills and agents are relevant. Claude infers from a rule-based system and decides which tools to use.

```
> "Fix the login bug in auth.py"

🎯 SKILL ACTIVATION CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ CRITICAL SKILLS (REQUIRED):
  → create_handoff

📚 RECOMMENDED SKILLS:
  → fix
  → debug

🤖 RECOMMENDED AGENTS (token-efficient):
  → debug-agent
  → scout

ACTION: Use Skill tool BEFORE responding
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Priority Levels

| Level | Meaning |
|-------|---------|
| ⚠️ **CRITICAL** | Must use (e.g., handoffs before ending session) |
| 📚 **RECOMMENDED** | Should use (e.g., workflow skills) |
| 💡 **SUGGESTED** | Consider using (e.g., optimization tools) |
| 📌 **OPTIONAL** | Nice to have (e.g., documentation helpers) |

### Natural Language Examples

| What You Say | What Activates |
|--------------|----------------|
| "Fix the broken login" | `/fix` workflow → debug-agent, scout |
| "Build a user dashboard" | `/build` workflow → plan-agent, kraken |
| "I want to understand this codebase" | `/explore` + scout agent |
| "What could go wrong with this plan?" | `/premortem` |
| "Help me figure out what I need" | `/discovery-interview` |
| "Done for today" | `create_handoff` (critical) |
| "Resume where we left off" | `resume_handoff` |
| "Research auth patterns" | oracle agent + perplexity |
| "Find all usages of this API" | scout agent + ast-grep |

### Why This Approach?

| Benefit | How |
|---------|-----|
| **More Discoverable** | Don't need to know commands exist |
| **Context-Aware** | System knows when you're 90% through context |
| **Reduces Cognitive Load** | Describe intent naturally, get curated suggestions |
| **Power User Friendly** | Still supports /fix, /build, etc. directly |

### Skill vs Workflow vs Agent

| Type | Purpose | Example |
|------|---------|---------|
| **Skill** | Single-purpose tool | `commit`, `tldr-code`, `qlty-check` |
| **Workflow** | Multi-step process | `/fix` (sleuth → premortem → kraken → commit) |
| **Agent** | Specialized sub-session | scout (exploration), oracle (research) |

[See detailed skill activation docs →](docs/skill-activation.md)

---

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Docker (for PostgreSQL)
- Claude Code CLI

### Installation

```bash
# Clone
git clone https://github.com/grantray/Continuous-Claude-v3.git
cd Continuous-Claude-v3/opc

# Run setup wizard (12 steps)
uv run python -m scripts.setup.wizard
```

> **Note:** The `pyproject.toml` is in `opc/`. Always run `uv` commands from the `opc/` directory.

### What the Wizard Does

| Step | What It Does |
|------|--------------|
| 1 | Backup existing .claude/ config (if present) |
| 2 | Check prerequisites (Docker, Python, uv) |
| 3-5 | Database + API key configuration |
| 6-7 | Start Docker stack, run migrations |
| 8 | Install Claude Code integration (32 agents, 105 skills, 65 hooks) |
| 9 | Math features (SymPy, Z3, Pint - optional) |
| 10 | TLDR code analysis tool |
| 11-12 | Diagnostics tools + Loogle (optional) |

### First Session

```bash
# Start Claude Code
claude

# Try a workflow
> /workflow
```

### First Session Commands

| Command | What it does |
|---------|--------------|
| `/workflow` | Goal-based routing (Research/Plan/Build/Fix) |
| `/fix bug <description>` | Investigate and fix a bug |
| `/build greenfield <feature>` | Build a new feature from scratch |
| `/explore` | Understand the codebase |
| `/premortem` | Risk analysis before implementation |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CONTINUOUS CLAUDE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   Skills    │    │   Agents    │    │    Hooks    │             │
│  │   (105)     │───▶│    (32)     │◀───│    (32)     │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
│         │                  │                  │                     │
│         ▼                  ▼                  ▼                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     TLDR Code Analysis                       │   │
│  │   L1:AST → L2:CallGraph → L3:CFG → L4:DFG → L5:Slicing      │   │
│  │                    (95% token savings)                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│         │                  │                  │                     │
│         ▼                  ▼                  ▼                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   Memory    │    │ Continuity  │    │ Coordination│             │
│  │   System    │    │   Ledgers   │    │    Layer    │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Session Lifecycle

```
SessionStart                    Working                      SessionEnd
    │                              │                             │
    ▼                              ▼                             ▼
┌─────────┐                  ┌─────────┐                   ┌─────────┐
│  Load   │                  │  Track  │                   │  Save   │
│ context │─────────────────▶│ changes │──────────────────▶│  state  │
└─────────┘                  └─────────┘                   └─────────┘
    │                              │                             │
    ├── Continuity ledger          ├── File claims               ├── Handoff
    ├── Memory recall              ├── TLDR indexing             ├── Learnings
    └── Symbol index               └── Blackboard                └── Outcome
                                         │
                                         ▼
                                    ┌─────────┐
                                    │ /clear  │
                                    │ Fresh   │
                                    │ context │
                                    └─────────┘
```

### The Continuity Loop (Detailed)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            THE CONTINUITY LOOP                              │
└─────────────────────────────────────────────────────────────────────────────┘

  1. SESSION START                     2. WORKING
  ┌────────────────────┐               ┌────────────────────┐
  │                    │               │                    │
  │  Ledger loaded ────┼──▶ Context    │  PostToolUse ──────┼──▶ Index handoffs
  │  Handoff loaded    │               │  UserPrompt ───────┼──▶ Skill hints
  │  Memory recalled   │               │  Edit tracking ────┼──▶ Dirty flag++
  │  TLDR cache warmed │               │  SubagentStop ─────┼──▶ Agent reports
  │                    │               │                    │
  └────────────────────┘               └────────────────────┘
           │                                    │
           │                                    ▼
           │                           ┌────────────────────┐
           │                           │ 3. PRE-COMPACT     │
           │                           │                    │
           │                           │  Auto-handoff ─────┼──▶ thoughts/shared/
           │                           │  (YAML format)     │    handoffs/*.yaml
           │                           │  Dirty > 20? ──────┼──▶ TLDR re-index
           │                           │                    │
           │                           └────────────────────┘
           │                                    │
           │                                    ▼
           │                           ┌────────────────────┐
           │                           │ 4. SESSION END     │
           │                           │                    │
           │                           │  Stale heartbeat ──┼──▶ Daemon wakes
           │                           │  Daemon spawns ────┼──▶ Headless Claude
           │                           │  Thinking blocks ──┼──▶ archival_memory
           │                           │                    │
           │                           └────────────────────┘
           │                                    │
           │                                    │
           └──────────────◀────── /clear ◀──────┘
                          Fresh context + state preserved
```

### Workflow Chains

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           META-SKILL WORKFLOWS                              │
└─────────────────────────────────────────────────────────────────────────────┘

  /fix bug                              /build greenfield
  ─────────                             ─────────────────
  ┌──────────┐  ┌──────────┐            ┌──────────┐  ┌──────────┐
  │  sleuth  │─▶│ premortem│            │discovery │─▶│plan-agent│
  │(diagnose)│  │  (risk)  │            │(clarify) │  │ (design) │
  └──────────┘  └────┬─────┘            └──────────┘  └────┬─────┘
                     │                                      │
                     ▼                                      ▼
              ┌──────────┐                          ┌──────────┐
              │  kraken  │                          │ validate │
              │  (fix)   │                          │ (check)  │
              └────┬─────┘                          └────┬─────┘
                   │                                      │
                   ▼                                      ▼
              ┌──────────┐                          ┌──────────┐
              │  arbiter │                          │  kraken  │
              │ (test)   │                          │(implement│
              └────┬─────┘                          └────┬─────┘
                   │                                      │
                   ▼                                      ▼
              ┌──────────┐                          ┌──────────┐
              │  commit  │                          │  commit  │
              └──────────┘                          └──────────┘


  /tdd                                  /refactor
  ────                                  ─────────
  ┌──────────┐  ┌──────────┐            ┌──────────┐  ┌──────────┐
  │plan-agent│─▶│  arbiter │            │ phoenix  │─▶│  warden  │
  │ (design) │  │(tests 🔴)│            │(analyze) │  │ (review) │
  └──────────┘  └────┬─────┘            └──────────┘  └────┬─────┘
                     │                                      │
                     ▼                                      ▼
              ┌──────────┐                          ┌──────────┐
              │  kraken  │                          │  kraken  │
              │(code 🟢) │                          │(transform│
              └────┬─────┘                          └────┬─────┘
                   │                                      │
                   ▼                                      ▼
              ┌──────────┐                          ┌──────────┐
              │  arbiter │                          │  judge   │
              │(verify ✓)│                          │ (review) │
              └──────────┘                          └──────────┘
```

### Data Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TLDR 5-LAYER CODE ANALYSIS              SEMANTIC INDEX                     │
│  ┌────────────────────────┐              ┌────────────────────────┐         │
│  │ L1: AST (~500 tok)     │              │ BGE-large-en-v1.5      │         │
│  │     └── Functions,     │              │ ├── All 5 layers       │         │
│  │         classes, sigs  │              │ ├── 10 lines context   │         │
│  │                        │              │ └── FAISS index        │         │
│  │ L2: Call Graph (+440)  │              │                        │         │
│  │     └── Cross-file     │──────────────│ Query: "auth logic"    │         │
│  │         dependencies   │              │ Returns: ranked funcs  │         │
│  │                        │              └────────────────────────┘         │
│  │ L3: CFG (+110 tok)     │                                                 │
│  │     └── Control flow   │                                                 │
│  │                        │              MEMORY (PostgreSQL+pgvector)       │
│  │ L4: DFG (+130 tok)     │              ┌────────────────────────┐         │
│  │     └── Data flow      │              │ sessions (heartbeat)   │         │
│  │                        │              │ file_claims (locks)    │         │
│  │ L5: PDG (+150 tok)     │              │ archival_memory (BGE)  │         │
│  │     └── Slicing        │              │ handoffs (embeddings)  │         │
│  └────────────────────────┘              └────────────────────────┘         │
│         ~1,200 tokens                                                       │
│         vs 23,000 raw                                                       │
│         = 95% savings                    FILE SYSTEM                        │
│                                          ┌────────────────────────┐         │
│                                          │ thoughts/              │         │
│                                          │ ├── ledgers/           │         │
│                                          │ │   └── CONTINUITY_*.md│         │
│                                          │ └── shared/            │         │
│                                          │     ├── handoffs/*.yaml│         │
│                                          │     └── plans/*.md     │         │
│                                          │                        │         │
│                                          │ .tldr/                 │         │
│                                          │ └── (daemon cache)     │         │
│                                          └────────────────────────┘         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Systems

### Skills System

Skills are modular capabilities triggered by natural language. Located in `.claude/skills/`.

#### Meta-Skills (Workflow Orchestrators)

| Meta-Skill | Chain | Use When |
|------------|-------|----------|
| `/workflow` | Router → appropriate workflow | Don't know where to start |
| `/build` | discovery → plan → validate → implement → commit | Building features |
| `/fix` | sleuth → premortem → kraken → test → commit | Fixing bugs |
| `/tdd` | plan → arbiter (tests) → kraken (implement) → arbiter | Test-first development |
| `/refactor` | phoenix → plan → kraken → reviewer → arbiter | Safe code transformation |
| `/review` | parallel specialized reviews → synthesis | Code review |
| `/explore` | scout (quick/deep/architecture) | Understand codebase |
| `/security` | vulnerability scan → verification | Security audits |
| `/release` | audit → E2E → review → changelog | Ship releases |

#### Meta-Skill Reference

Each meta-skill supports modes, scopes, and flags. Type the skill alone (e.g., `/build`) to get an interactive question flow.

**`/build <mode> [options] [description]`**

| Mode | Chain | Use For |
|------|-------|---------|
| `greenfield` | discovery → plan → validate → implement → commit → PR | New feature from scratch |
| `brownfield` | onboard → research → plan → validate → implement | Feature in existing codebase |
| `tdd` | plan → test-first → implement | Test-driven development |
| `refactor` | impact analysis → plan → TDD → implement | Safe refactoring |

| Option | Effect |
|--------|--------|
| `--skip-discovery` | Skip interview phase (have clear spec) |
| `--skip-validate` | Skip plan validation |
| `--skip-commit` | Don't auto-commit |
| `--skip-pr` | Don't create PR description |
| `--parallel` | Run research agents in parallel |

**`/fix <scope> [options] [description]`**

| Scope | Chain | Use For |
|-------|-------|---------|
| `bug` | debug → implement → test → commit | General bug fix |
| `hook` | debug-hooks → hook-developer → implement → test | Hook issues |
| `deps` | preflight → oracle → plan → implement → qlty | Dependency errors |
| `pr-comments` | github-search → research → plan → implement → commit | PR feedback |

| Option | Effect |
|--------|--------|
| `--no-test` | Skip regression test |
| `--dry-run` | Diagnose only, don't fix |
| `--no-commit` | Don't auto-commit |

**`/explore <depth> [options]`**

| Depth | Time | What It Does |
|-------|------|--------------|
| `quick` | ~1 min | tldr tree + structure overview |
| `deep` | ~5 min | onboard + tldr + research + documentation |
| `architecture` | ~3 min | tldr arch + call graph + layers |

| Option | Effect |
|--------|--------|
| `--focus "area"` | Focus on specific area (e.g., `--focus "auth"`) |
| `--output handoff` | Create handoff for implementation |
| `--output doc` | Create documentation file |
| `--entry "func"` | Start from specific entry point |

**`/tdd`, `/refactor`, `/review`, `/security`, `/release`**

These follow their defined chains without mode flags. Just run:
```
/tdd "implement retry logic"
/refactor "extract auth module"
/review                           # reviews current changes
/security "authentication code"
/release v1.2.0
```

#### Key Skills (High-Value Tools)

**Planning & Risk**
- **premortem**: TIGERS & ELEPHANTS risk analysis - use before any significant implementation
- **discovery-interview**: Transform vague ideas into detailed specs

**Context Management**
- **create_handoff**: Capture session state for transfer
- **resume_handoff**: Resume from handoff with context
- **continuity_ledger**: Track state within session

**Code Analysis (95% Token Savings)**
- **tldr-code**: Call graph, CFG, DFG, slicing
- **ast-grep-find**: Structural code search
- **morph-search**: Fast text search (20x faster than grep)

**Research**
- **perplexity-search**: AI-powered web search
- **nia-docs**: Library documentation search
- **github-search**: Search GitHub code/issues/PRs

**Quality**
- **qlty-check**: 70+ linters, auto-fix
- **braintrust-analyze**: Session analysis, replay, and debugging failed sessions

**Math & Formal Proofs**
- **math**: Unified computation (SymPy, Z3, Pint) — one entry point for all math
- **prove**: Lean4 theorem proving with 5-phase workflow (Research → Design → Test → Implement → Verify)
- **pint-compute**: Unit-aware arithmetic and conversions
- **shapely-compute**: Computational geometry

The `/prove` skill enables machine-verified proofs without learning Lean syntax. Used to create the first Lean formalization of Sylvester-Gallai theorem.

#### The Thought Process

```
What do I want to do?
├── Don't know → /workflow (guided router)
├── Building → /build greenfield or brownfield
├── Fixing → /fix bug
├── Understanding → /explore
├── Planning → premortem first, then plan-agent
├── Researching → oracle or perplexity-search
├── Reviewing → /review
├── Proving → /prove (Lean4 formal verification)
├── Computing → /math (SymPy, Z3, Pint)
└── Shipping → /release
```

[See detailed skills breakdown →](docs/skills/)

---

### Agents System

Agents are specialized AI workers spawned via the Task tool. Located in `.claude/agents/`.

#### Agent Categories (32 active)

> **Note:** There are likely too many agents—consolidation is a v4 goal. Use what fits your workflow.

**Orchestrators (2)**
- **maestro**: Multi-agent coordination with patterns (Pipeline, Swarm, Jury)
- **kraken**: TDD implementation agent with checkpoint/resume support

**Planners (4)**
- **architect**: Feature planning + API integration
- **phoenix**: Refactoring + framework migration planning
- **plan-agent**: Lightweight planning with research/MCP tools
- **validate-agent**: Validate plans against best practices

**Explorers (4)**
- **scout**: Codebase exploration (use instead of Explore)
- **oracle**: External research (web, docs, APIs)
- **pathfinder**: External repository analysis
- **research-codebase**: Document codebase as-is

**Implementers (3)**
- **kraken**: TDD implementation with strict test-first workflow
- **spark**: Lightweight fixes and quick tweaks
- **agentica-agent**: Build Python agents using Agentica SDK

**Debuggers (3)**
- **sleuth**: General bug investigation and root cause
- **debug-agent**: Issue investigation via logs/code search
- **profiler**: Performance profiling and race conditions

**Validators (2)** - arbiter, atlas

**Reviewers (6)** - critic, judge, surveyor, liaison, plan-reviewer, review-agent

**Specialized (8)** - aegis, herald, scribe, chronicler, session-analyst, braintrust-analyst, memory-extractor, onboard

#### Common Workflows

| Workflow | Agent Chain |
|----------|-------------|
| Feature | architect → plan-reviewer → kraken → review-agent → arbiter |
| Refactoring | phoenix → plan-reviewer → kraken → judge → arbiter |
| Bug Fix | sleuth → spark/kraken → arbiter → scribe |

[See detailed agent guide →](docs/agents/)

---

### Hooks System

Hooks intercept Claude Code at lifecycle points. Located in `.claude/hooks/`.

#### Hook Events (65 hooks total)

| Event | Key Hooks | Purpose |
|-------|-----------|---------|
| **SessionStart** | session-start-continuity, session-register, braintrust-tracing | Load context, register session |
| **PreToolUse** | tldr-read-enforcer, smart-search-router, tldr-context-inject, file-claims | Token savings, search routing |
| **PostToolUse** | post-edit-diagnostics, handoff-index, post-edit-notify | Validation, indexing |
| **PreCompact** | pre-compact-continuity | Auto-save before compaction |
| **UserPromptSubmit** | skill-activation-prompt, memory-awareness | Skill hints, memory recall |
| **SubagentStop** | subagent-stop-continuity | Save agent state |
| **SessionEnd** | session-end-cleanup, session-outcome | Cleanup, extract learnings |

#### Key Hooks

| Hook | Purpose |
|------|---------|
| **tldr-context-inject** | Adds code analysis to agent prompts |
| **smart-search-router** | Routes grep to AST-grep when appropriate |
| **post-edit-diagnostics** | Runs pyright/ruff after edits |
| **memory-awareness** | Surfaces relevant learnings |

[See all 65 hooks →](docs/hooks/)

---

### TLDR Code Analysis

TLDR provides token-efficient code summaries through 5 analysis layers.

#### The 5-Layer Stack

| Layer | Name | What it provides | Tokens |
|-------|------|------------------|--------|
| **L1** | AST | Functions, classes, signatures | ~500 tokens |
| **L2** | Call Graph | Who calls what (cross-file) | +440 tokens |
| **L3** | CFG | Control flow, complexity | +110 tokens |
| **L4** | DFG | Data flow, variable tracking | +130 tokens |
| **L5** | PDG | Program slicing, impact analysis | +150 tokens |

**Total: ~1,200 tokens vs 23,000 raw = 95% savings**

#### CLI Commands

```bash
# Structure analysis
tldr tree src/                      # File tree
tldr structure src/ --lang python   # Code structure (codemaps)

# Search and extraction
tldr search "process_data" src/     # Find code
tldr context process_data --project src/ --depth 2  # LLM-ready context

# Flow analysis
tldr cfg src/main.py main           # Control flow graph
tldr dfg src/main.py main           # Data flow graph
tldr slice src/main.py main 42      # What affects line 42?

# Codebase analysis
tldr impact process_data src/       # Who calls this function?
tldr dead src/                      # Find unreachable code
tldr arch src/                      # Detect architectural layers

# Semantic search (natural language)
tldr daemon semantic "find authentication logic"
```

#### Semantic Index

Beyond structural analysis, TLDR builds a **semantic index** of your codebase:

- **Natural language queries** — Ask "where is error handling?" instead of grepping
- **Auto-rebuild** — Dirty flag hook tracks file changes; index rebuilds after N edits
- **Selective indexing** — Use `.tldrignore` to control what gets indexed

```bash
# .tldrignore example
__pycache__/
*.test.py
node_modules/
.venv/
```

The semantic index uses all 5 layers plus 10 lines of surrounding code context—not just docstrings.

#### Hook Integration

TLDR is automatically integrated via hooks:

- **tldr-read-enforcer**: Returns L1+L2+L3 instead of full file reads
- **smart-search-router**: Routes Grep to `tldr search`
- **post-tool-use-tracker**: Updates indexes when files change

[See TLDR documentation →](https://github.com/a-h/llm-tldr)

---

### Memory System

Cross-session learning powered by PostgreSQL + pgvector.

#### How It Works

```
Session ends → Database detects stale heartbeat (>5 min)
            → Daemon spawns headless Claude (Sonnet)
            → Analyzes thinking blocks from session
            → Extracts learnings to archival_memory
            → Next session recalls relevant learnings
```

The key insight: **thinking blocks contain the real reasoning**—not just what Claude did, but why. The daemon extracts this automatically.

#### Conversational Interface

| What You Say | What Happens |
|--------------|--------------|
| "Remember that auth uses JWT" | Stores learning with context |
| "Recall authentication patterns" | Searches memory, surfaces matches |
| "What did we decide about X?" | Implicit recall via memory-awareness hook |

#### Database Schema (4 tables)

| Table | Purpose |
|-------|---------|
| **sessions** | Cross-terminal awareness |
| **file_claims** | Cross-terminal file locking |
| **archival_memory** | Long-term learnings with BGE embeddings |
| **handoffs** | Session handoffs with embeddings |

#### Recall Commands

```bash
# Recall learnings (hybrid text + vector search)
cd opc && uv run python scripts/core/recall_learnings.py \
    --query "authentication patterns"

# Store a learning explicitly
cd opc && uv run python scripts/core/store_learning.py \
    --session-id "my-session" \
    --type WORKING_SOLUTION \
    --content "What I learned" \
    --confidence high
```

#### Automatic Memory

The **memory-awareness** hook surfaces relevant learnings when you send a message. You'll see `MEMORY MATCH` indicators—Claude can use these without you asking.

---

### Continuity System

Preserve state across context clears and sessions.

#### Continuity Ledger

Within-session state tracking. Location: `thoughts/ledgers/CONTINUITY_<topic>.md`

```markdown
# Session: feature-x
Updated: 2026-01-08

## Goal
Implement feature X with proper error handling

## Completed
- [x] Designed API schema
- [x] Implemented core logic

## In Progress
- [ ] Add error handling

## Blockers
- Need clarification on retry policy
```

#### Handoffs

Between-session knowledge transfer. Location: `thoughts/shared/handoffs/<session>/`

```yaml
---
date: 2026-01-08T15:26:01+0000
session_name: feature-x
status: complete
---

# Handoff: Feature X Implementation

## Task(s)
| Task | Status |
|------|--------|
| Design API | Completed |
| Implement core | Completed |
| Error handling | Pending |

## Next Steps
1. Add retry logic to API calls
2. Write integration tests
```

#### Commands

| Command | Effect |
|---------|--------|
| "save state" | Updates continuity ledger |
| "done for today" / `/handoff` | Creates handoff document |
| "resume work" | Loads latest handoff |

---

### Math System

Two capabilities: **computation** (SymPy, Z3, Pint) and **formal verification** (Lean4 + Mathlib).

#### The Stack

| Tool | Purpose | Example |
|------|---------|---------|
| **SymPy** | Symbolic math | Solve equations, integrals, matrix operations |
| **Z3** | Constraint solving | Prove inequalities, SAT problems |
| **Pint** | Unit conversion | Convert miles to km, dimensional analysis |
| **Lean4** | Formal proofs | Machine-verified theorems |
| **Mathlib** | 100K+ theorems | Pre-formalized lemmas to build on |
| **Loogle** | Type-aware search | Find Mathlib lemmas by signature |

#### Two Entry Points

| Skill | Use When |
|-------|----------|
| `/math` | Computing, solving, calculating |
| `/prove` | Formal verification, machine-checked proofs |

#### /math Examples

```bash
# Solve equation
"Solve x² - 4 = 0"  →  x = ±2

# Compute eigenvalues
"Eigenvalues of [[2,1],[1,2]]"  →  {1: 1, 3: 1}

# Prove inequality
"Is x² + y² ≥ 2xy always true?"  →  PROVED (equals (x-y)²)

# Convert units
"26.2 miles to km"  →  42.16 km
```

#### /prove - Formal Verification

5-phase workflow for machine-verified proofs:

```
📚 RESEARCH → 🏗️ DESIGN → 🧪 TEST → ⚙️ IMPLEMENT → ✅ VERIFY
```

1. **Research**: Search Mathlib with Loogle, find proof strategy
2. **Design**: Create skeleton with `sorry` placeholders
3. **Test**: Search for counterexamples before proving
4. **Implement**: Fill sorries with compiler-in-the-loop feedback
5. **Verify**: Audit axioms, confirm zero sorries

```
/prove every group homomorphism preserves identity
/prove continuous functions on compact sets are uniformly continuous
```

**Achievement**: Used to create the first Lean formalization of the Sylvester-Gallai theorem.

#### Prerequisites (Optional)

Math features require installation via wizard step 9:

```bash
# Installed automatically by wizard
uv pip install sympy z3-solver pint shapely

# Lean4 (for /prove)
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh
```

---

## Workflows

### /workflow - Goal-Based Router

```
> /workflow

? What's your goal?
  ○ Research - Understand codebase/docs
  ○ Plan - Design implementation approach
  ○ Build - Implement features
  ○ Fix - Investigate and resolve issues
```

### /fix - Bug Resolution

```bash
/fix bug "login fails silently"
```

**Chain:** sleuth → [checkpoint] → [premortem] → kraken → test → commit

| Scope | What it does |
|-------|--------------|
| `bug` | General bug investigation |
| `hook` | Hook-specific debugging |
| `deps` | Dependency issues |
| `pr-comments` | Address PR feedback |

### /build - Feature Development

```bash
/build greenfield "user dashboard"
```

**Chain:** discovery → plan → validate → implement → commit → PR

| Mode | What it does |
|------|--------------|
| `greenfield` | New feature from scratch |
| `brownfield` | Modify existing codebase |
| `tdd` | Test-first development |
| `refactor` | Safe code transformation |

### /premortem - Risk Analysis

```bash
/premortem deep thoughts/shared/plans/feature-x.md
```

**Output:**
- **TIGERS**: Clear threats (HIGH/MEDIUM/LOW severity)
- **ELEPHANTS**: Unspoken concerns

Blocks on HIGH severity until user accepts/mitigates risks.

---

## Installation

### Full Installation (Recommended)

```bash
# Clone
git clone https://github.com/grantray/Continuous-Claude-v3.git
cd Continuous-Claude-v3/opc

# Run the setup wizard
uv run python -m scripts.setup.wizard
```

The wizard walks you through all configuration options interactively.

## Updating

Pull latest changes and sync your installation:

```bash
cd continuous-claude/opc
uv run python -m scripts.setup.update
```

This will:
- Pull latest from GitHub
- Update hooks, skills, rules, agents
- Upgrade TLDR if installed
- Rebuild TypeScript hooks if changed

### What Gets Installed

| Component | Location |
|-----------|----------|
| Agents (32) | ~/.claude/agents/ |
| Skills (105) | ~/.claude/skills/ |
| Hooks (65) | ~/.claude/hooks/ |
| Rules | ~/.claude/rules/ |
| Scripts | ~/.claude/scripts/ |
| PostgreSQL | Docker container |

### For Brownfield Projects

After installation, start Claude and run:
```
> /onboard
```

This analyzes the codebase and creates an initial continuity ledger.

---

## Configuration

### .claude/settings.json

Central configuration for hooks, tools, and workflows.

```json
{
  "hooks": {
    "SessionStart": [...],
    "PreToolUse": [...],
    "PostToolUse": [...],
    "UserPromptSubmit": [...]
  }
}
```

### .claude/skills/skill-rules.json

Skill activation triggers.

```json
{
  "rules": [
    {
      "skill": "fix",
      "keywords": ["fix this", "broken", "not working"],
      "intentPatterns": ["fix.*(bug|issue|error)"]
    }
  ]
}
```

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `BRAINTRUST_API_KEY` | Session tracing | No |
| `PERPLEXITY_API_KEY` | Web search | No |
| `NIA_API_KEY` | Documentation search | No |

Services without API keys still work:
- Continuity system (ledgers, handoffs)
- TLDR code analysis
- Local git operations
- TDD workflow

---

## Directory Structure

```
continuous-claude/
├── .claude/
│   ├── agents/           # 32 specialized AI agents
│   ├── hooks/            # 32 lifecycle hooks
│   │   ├── src/          # TypeScript source
│   │   └── dist/         # Compiled JavaScript
│   ├── skills/           # 105 modular capabilities
│   ├── rules/            # System policies
│   ├── scripts/          # Python utilities
│   └── settings.json     # Hook configuration
├── opc/
│   ├── scripts/
│   │   ├── setup/        # Wizard, Docker, integration
│   │   └── core/         # recall_learnings, store_learning
│   ├── src/              # Runtime harness, MCP client
│   ├── docker/           # Docker configs
│   └── init-db.sql       # 4-table PostgreSQL schema
├── thoughts/
│   ├── ledgers/          # Continuity ledgers (CONTINUITY_*.md)
│   └── shared/
│       ├── handoffs/     # Session handoffs (*.yaml)
│       └── plans/        # Implementation plans
└── docs/                 # Documentation
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Adding new skills
- Creating agents
- Developing hooks
- Extending TLDR

---

## Acknowledgments

### Patterns & Architecture
- **[@numman-ali](https://github.com/numman-ali)** - Continuity ledger pattern
- **[Anthropic](https://anthropic.com)** - Claude Code and "Code Execution with MCP"
- **[obra/superpowers](https://github.com/obra/superpowers)** - Agent orchestration patterns
- **[EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin)** - Compound engineering workflow
- **[yoloshii/mcp-code-execution-enhanced](https://github.com/yoloshii/mcp-code-execution-enhanced)** - Enhanced MCP execution
- **[HumanLayer](https://github.com/humanlayer/humanlayer)** - Agent patterns

### Tools & Services
- **[uv](https://github.com/astral-sh/uv)** - Python packaging
- **[tree-sitter](https://tree-sitter.github.io/)** - Code parsing
- **[Braintrust](https://braintrust.dev)** - LLM evaluation, logging, and session tracing
- **[qlty](https://github.com/qltysh/qlty)** - Universal code quality CLI (70+ linters)
- **[ast-grep](https://github.com/ast-grep/ast-grep)** - AST-based code search and refactoring
- **[Nia](https://trynia.ai)** - Library documentation search
- **[Morph](https://www.morphllm.com)** - WarpGrep fast code search
- **[Firecrawl](https://www.firecrawl.dev)** - Web scraping API
- **[RepoPrompt](https://repoprompt.com)** - Token-efficient codebase maps

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=grantray/Continuous-Claude-v3&type=timeline)](https://star-history.com/#grantray/Continuous-Claude-v3&Date)

---

## License

[MIT](LICENSE) - Use freely, contribute back.

---

**Continuous Claude**: Not just a coding assistant—a persistent, learning, multi-agent development environment that gets smarter with every session.

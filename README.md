# Continuous Claude

> Give Claude a notebook, memory, and specialized assistants — so every conversation builds on the last

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude-Code-orange.svg)](https://claude.ai/code)

**Continuous Claude transforms how you work with Claude Code** — whether you're writing code, analyzing data, creating content, or researching topics. Instead of starting fresh every time, Claude remembers what you've worked on and gets smarter with each session.

---

## What Is This?

Think of Claude Code as having a brilliant assistant who helps you with tasks. The problem? Every time you close the conversation, they forget everything you did together. When you start a new chat, you have to explain your project from scratch.

**Continuous Claude solves this** by giving Claude three superpowers:

1. **📓 A Persistent Notebook** — Saves key decisions, learnings, and context so nothing gets lost when you start a new conversation
2. **🎓 Long-term Memory** — Automatically remembers what worked (and what didn't) across all your sessions, retrievable when relevant
3. **👥 Specialist Assistants** — Delegates complex tasks to focused AI agents (like having a research assistant, debugger, and code reviewer on call)

It's like the difference between emailing someone vs. working with a colleague who remembers your previous conversations and can delegate work to their team.

---

## 🚀 Can I Build Software Without Knowing How to Code?

**Yes. That's the whole point.**

Continuous Claude was built so that **non-technical people can create working software** by describing what they want in plain English. You don't write code — you describe outcomes, and the system figures out how to build it.

### How This Works

1. **You describe what you want:** "Build me a dashboard that shows sales by region"
2. **Maestro orchestrates the work:** Breaks your request into tasks and assigns them to specialist agents
3. **Agents do the technical work:** Research agent finds best practices, architect agent designs the solution, builder agent writes the code, tester agent verifies it works
4. **You review and refine:** See the results, give feedback in plain English, iterate until it's right

**You're the director. The agents are your technical team.**

### What You Can Build (Examples)

| What You Describe | What Gets Built |
|-------------------|-----------------|
| "A form that collects customer feedback and emails me summaries" | Working web form with email integration |
| "A tool that analyzes our spreadsheet and finds anomalies" | Data analysis script with visualizations |
| "A simple app to track our team's project status" | Project management dashboard |
| "Automate our weekly report from these data sources" | Scheduled automation with formatted output |

The system handles the technical complexity. You focus on what you want it to do.

---

## ⭐ What Makes This Fork Special?

This fork includes significant improvements over the original Continuous Claude, developed through real-world use:

### 🎼 Maestro: The Orchestrator (Our Flagship Improvement)

**The Problem:** Complex tasks require coordinating multiple specialists — researcher, planner, builder, tester, reviewer. Managing this manually is tedious and error-prone.

**Our Solution:** Maestro acts as a project manager for AI agents. When you describe a complex task:

1. **Discovery Interview** — Maestro asks clarifying questions to understand exactly what you need
2. **Task Breakdown** — Splits your request into logical phases (research → plan → build → test)
3. **Agent Assignment** — Assigns the right specialist to each phase (oracle for research, architect for planning, kraken for building)
4. **Progress Tracking** — Keeps you informed as each phase completes
5. **Quality Synthesis** — Combines outputs into coherent deliverables

**Plain English Example:**
```
You: "Build me a customer feedback system"

Maestro: "Let me understand what you need..."
  → Asks: Web or mobile? What fields? Where should responses go?

Maestro: "Here's my plan..."
  → Phase 1: Research best practices (oracle agent)
  → Phase 2: Design the solution (architect agent)
  → Phase 3: Build it (kraken agent)
  → Phase 4: Test it works (arbiter agent)

You: "Approved, go ahead"

Maestro: [Executes each phase, reports progress, delivers working system]
```

### 📚 138 Skills (vs. Original ~50)

Skills are pre-built workflows you trigger by describing what you want:

| Skill | What It Does | How You Trigger It |
|-------|--------------|-------------------|
| `/build` | Creates complete features from descriptions | "Build a login page" |
| `/fix` | Investigates and repairs broken things | "This button doesn't work" |
| `/research` | Deep-dives into topics with sources | "Research competitor pricing" |
| `/review` | Gets multiple perspectives on work | "Review this document" |
| `/premortem` | Identifies what could go wrong | "What risks does this plan have?" |

### 🧠 Persistent Memory System

**The Problem:** Every Claude conversation starts fresh. You waste time re-explaining your project, preferences, and past decisions.

**Our Solution:** A PostgreSQL database stores learnings from every session:

- **What worked** — Successful approaches get remembered and reused
- **What failed** — Mistakes get flagged so you don't repeat them
- **Your preferences** — How you like things done
- **Project context** — What you're building and why

**In Practice:** Start a new session, and Claude already knows your project, your preferences, and what you tried last time.

### 🔍 95% Token Efficiency (TLDR System)

**The Problem:** Claude normally reads entire files to understand code, burning through your token budget quickly.

**Our Solution:** The TLDR system analyzes code structure instead of reading every line — like scanning a book's table of contents instead of reading every page.

**The Benefit:** Same understanding, 95% fewer tokens. Longer conversations, more complex projects, lower costs.

---

## Why Use It?

### For Everyone

**Stop Repeating Yourself**
- Context persists across sessions — no more "here's my project again"
- Claude recalls relevant past work automatically
- Decisions and learnings accumulate like compound interest

**Work Faster**
- Delegate research, analysis, and implementation to specialized agents
- Get structured workflows instead of back-and-forth prompting
- Natural language triggers — just describe what you want

**Stay Organized**
- Automatic session summaries and handoffs
- Track progress on multi-day projects
- Resume exactly where you left off

### For Technical Users

**95% Efficiency Boost**
- Analyzes code structure instead of reading every line (like scanning a table of contents instead of the whole book)
- Smart search finds relevant code instantly
- Pattern detection finds similar code across your project

**Developer Workflows**
- Test-driven development with automatic test generation
- Risk analysis before implementation ("What could go wrong?" checklist)
- Automated code review with multiple specialized reviewers
- Cross-file refactoring with impact analysis

**Advanced Capabilities**
- Mathematical proof verification (for those who need formal guarantees)
- Symbolic computation for equations and constraints
- Machine-verified proofs without learning specialized syntax

---

## Who Is This For?

### Marketing & Content

**Research & Writing**
- "Research our top 3 competitors and their messaging" → oracle agent gathers intel
- "Find trends in customer feedback about feature X" → analyzes patterns
- "Create a campaign brief for product launch" → structures workflow from research to deliverables

**Campaign Management**
- Track multi-week campaigns with persistent context
- Remember brand guidelines and voice across sessions
- Recall what messaging performed well previously

### Sales

**Meeting Preparation**
- "Research [company] and prepare talking points" → gathers industry context, competitive landscape
- "Summarize our last 3 conversations with this prospect" → memory system recalls relevant details
- "Create a proposal for [use case]" → builds on past successful proposals

**Competitive Intelligence**
- Track competitor moves across sessions
- Remember pricing discussions and objections
- Build relationship context that persists

### Operations, Finance, Legal

**Documentation & Analysis**
- "Analyze Q4 spending patterns" → structures data analysis workflow
- "Update our compliance documentation for new regulations" → researches changes, proposes updates
- "Create a process document for onboarding" → systematic workflow creation

**Report Generation**
- Persistent templates and formatting preferences
- Recall data sources and calculation methods
- Multi-session report building with continuity

### Engineering

**Development Workflows**
- `/build greenfield "user dashboard"` → end-to-end feature implementation
- `/fix bug "login timeout"` → diagnosis → plan → fix → test → commit
- `/refactor "extract auth module"` → safe refactoring with impact analysis

**Code Understanding**
- "Explain how authentication works in this codebase" → semantic analysis without reading every file
- "Find all places that call this API" → instant structural search
- "What would break if I change this function?" → impact analysis

---

## Quick Start

### Prerequisites

You need these installed:

- [Docker Desktop](https://www.docker.com/products/docker-desktop) — stores your session history and learnings (like a filing cabinet for Claude's memory)
- [Node.js 18+](https://nodejs.org/) — runs background helpers (you won't interact with it directly)
- [Python 3.11+](https://www.python.org/downloads/) with [uv](https://github.com/astral-sh/uv) — runs the setup wizard and memory system
- [Claude Code CLI](https://docs.anthropic.com/claude/docs/claude-code) — the main app you already use (if you're using Claude in terminal, you have this)

### Install

```bash
# Clone the repository
git clone https://github.com/parcadei/continuous-claude.git
cd continuous-claude/opc

# Run the setup wizard
uv run python -m scripts.setup.wizard
```

**Time:** 5 minutes if prerequisites installed, 15-20 minutes for fresh setup with Docker.

The wizard walks you through 12 steps:

1. ✅ Backs up your existing Claude configuration
2. ✅ Checks that prerequisites are installed
3. ✅ Sets up the database and API keys (optional)
4. ✅ Starts Docker containers for PostgreSQL
5. ✅ Installs 32 specialized agents
6. ✅ Installs 138 skill workflows
7. ✅ Installs 77 lifecycle hooks
8. ✅ Installs code analysis tools (95% efficiency boost)
9. ✅ Installs math capabilities (optional)
10. ✅ Configures diagnostics and linting
11. ✅ Sets up search tools
12. ✅ Tests that everything works

### First Session

```bash
# Start Claude Code
claude

# Try a workflow
> /workflow

? What's your goal?
  ○ Research - Understand codebase/docs
  ○ Plan - Design implementation approach
  ○ Build - Implement features
  ○ Fix - Investigate and resolve issues
```

That's it. You're now using Continuous Claude.

---

## How It Works (Simple Explanation)

### The Problem

Claude has a "context window" — think of it like short-term memory. When conversations get too long, Claude has to "forget" earlier parts to make room for new information. This means:

- You lose important decisions and context
- Each new session starts from zero
- Complex projects require constant re-explaining
- Reading entire files burns through your token budget

### The Solution

Continuous Claude adds four layers:

**1. Persistent State (Ledgers & Handoffs)**

Like a notebook that follows you between sessions:

```
Session 1: "Build user authentication"
→ Creates handoff: Goals, decisions, next steps

Session 2 (next day): "Resume work"
→ Loads handoff: Exactly where you left off
```

**2. Learning Memory (Automatic)**

A background system that watches for patterns:

```
Session ends → Database detects inactive session
            → Spawns background Claude to analyze
            → Extracts learnings: "What worked, what failed, why"
            → Stores with semantic embeddings

Next session → Relevant learnings surface automatically
```

**3. Specialized Agents (Delegation)**

Instead of one generalist, you get a team:

```
You: "Fix the authentication bug and add tests"

Claude: Spawns 3 agents in sequence:
  → sleuth (investigates bug)
  → kraken (implements fix)
  → arbiter (writes tests)

You: Get structured results without micromanaging
```

**4. Smart Code Analysis (95% Token Savings)**

Instead of reading entire files, Claude sees structure:

```
Traditional: Read 23,000 tokens (entire file)
Continuous Claude: Read 1,200 tokens (functions, calls, logic flows)

Result: Same understanding, 95% fewer tokens
```

---

## What You Get

### 112 Skills (Pre-Built Workflows)

Skills are like apps you trigger by asking naturally. No need to memorize commands.

| What You Say | What Happens |
|--------------|--------------|
| "Fix the login bug" | `/fix` workflow → investigate → plan → implement → test → commit |
| "Build a user dashboard" | `/build` workflow → clarify → design → validate → implement |
| "What could go wrong with this plan?" | `/premortem` → TIGERS (clear threats) + ELEPHANTS (unspoken concerns) |
| "Research authentication patterns" | `oracle` agent → searches web, docs, examples |
| "Find all calls to this function" | `tldr impact` → structural analysis, not text search |
| "Done for today" | `create_handoff` → saves state for next session |

**Key workflows:**

- **Research:** oracle (web search), scout (codebase exploration), nia-docs (library documentation)
- **Planning:** premortem (risk analysis), discovery-interview (clarify vague ideas)
- **Building:** /build (greenfield or brownfield), /tdd (test-first), /refactor (safe transformation)
- **Fixing:** /fix (bugs), /security (vulnerabilities), /review (code review)
- **Continuity:** create_handoff, resume_handoff, continuity_ledger

### 32 Specialized Agents

Agents are AI assistants focused on specific tasks. Claude delegates to them automatically.

**Planners (4)**
- **architect** — Feature planning with API integration
- **phoenix** — Refactoring and framework migrations
- **plan-agent** — Lightweight planning with research
- **validate-agent** — Validate plans against best practices

**Explorers (4)**
- **scout** — Codebase exploration (90% accurate vs. 60% for generic search)
- **oracle** — External research (web, docs, GitHub)
- **pathfinder** — External repository analysis
- **research-codebase** — Document codebase as-is

**Implementers (3)**
- **kraken** — Test-driven implementation with strict TDD workflow
- **spark** — Lightweight fixes and quick tweaks
- **agentica-agent** — Build Python agents using Agentica SDK

**Debuggers (3)**
- **sleuth** — Root cause investigation
- **debug-agent** — Issue investigation via logs/code
- **profiler** — Performance profiling and race conditions

**Reviewers (6)**
- **critic**, **judge**, **surveyor** — Different review perspectives
- **liaison**, **plan-reviewer**, **review-agent** — Structured reviews

**Validators (2)**
- **arbiter** — Test validation
- **atlas** — Integration testing

**Specialized (8)**
- **aegis** — Security review
- **herald** — Release management
- **scribe** — Documentation generation
- **chronicler**, **session-analyst**, **braintrust-analyst** — Session analysis
- **memory-extractor** — Learning extraction
- **onboard** — Codebase onboarding

### 66 Hooks (Automatic Helpers)

Hooks run in the background at specific moments — you don't call them directly.

**When you start a session:**
- Loads your continuity ledger (where you left off)
- Registers your session in the database
- Recalls relevant memories from past work

**Before Claude reads a file:**
- Checks if a summary already exists (95% token savings)
- Routes searches to structural tools instead of text grep
- Claims the file (prevents conflicts if multiple terminals open)

**After you edit a file:**
- Runs type checking and linting automatically
- Updates code indexes
- Tracks which files changed (for testing later)

**Before running out of tokens:**
- Automatically creates a handoff document
- Saves state so you can resume later
- Re-indexes modified code

**After your session ends:**
- Detects stale heartbeat (you closed Claude)
- Spawns background analysis to extract learnings
- Stores memories for future recall

### 12 Rules (System Policies)

Rules keep Claude consistent and safe:

- **Evidence-based claims** — No "this is faster" without benchmarks
- **Read before write** — Always check existing code before changes
- **Minimal comments** — Code should be self-explanatory
- **Security-first** — Never commit secrets, always validate input
- **Git safety** — Confirm before destructive operations
- **Delegation** — Use agents for complex tasks to preserve main context

---

## Common Use Cases

### "I Need to Understand This Codebase"

```
> /explore deep --focus "authentication"

Spawns scout agent:
  1. Analyzes file structure
  2. Traces authentication flow
  3. Identifies entry points
  4. Maps dependencies
  5. Creates summary document

Result: Structured understanding in ~5 minutes
```

### "I Have a Vague Idea, Need Help Clarifying"

```
> "I want to improve our user onboarding, not sure how"

Triggers /discovery-interview:
  → Asks clarifying questions
  → Identifies constraints
  → Proposes options with trade-offs
  → Creates implementation plan

Result: Spec document ready for /build
```

### "This Is Broken, Help Me Fix It"

```
> /fix bug "users can't upload files over 10MB"

Workflow:
  1. sleuth investigates → finds timeout + size limit
  2. premortem analyzes → risk: breaking existing uploads
  3. kraken implements → chunked upload + progress bar
  4. arbiter tests → integration test for large files
  5. commit creates → descriptive commit message

Result: Fixed, tested, documented
```

### "Build This Feature for Me"

```
> /build greenfield "user dashboard with activity feed"

Workflow:
  1. discovery clarifies → real-time or polling? filters?
  2. plan designs → API schema, UI components, database
  3. validate checks → performance, security, edge cases
  4. kraken implements → TDD: tests first, then code
  5. commit + PR → ready for review

Result: Complete feature with tests and documentation
```

### "What Could Go Wrong?"

```
> /premortem thoughts/shared/plans/user-dashboard.md

Output:
  🐯 TIGERS (Clear Threats):
    [HIGH] Real-time updates could spike database load
    [MEDIUM] No pagination → memory issues with long feeds
    [LOW] Time zones not handled in activity timestamps

  🐘 ELEPHANTS (Unspoken Concerns):
    - Team hasn't worked with WebSockets before
    - No monitoring for real-time connection failures
    - Unclear how to test real-time features

Action: Blocks until you accept risks or mitigate
```

### "Research This Topic for Me"

```
> "Research how other SaaS apps handle webhook retries"

Spawns oracle agent:
  → Searches web for patterns
  → Finds library documentation
  → Analyzes GitHub examples
  → Synthesizes recommendations

Result: Structured findings with sources
```

---

## Components Explained Simply

### Skills (112)

**What they are:** Pre-built workflows you trigger by describing what you want

**How you use them:**
- Natural language: "Fix this bug"
- Direct command: `/fix bug "description"`
- Workflow: `/workflow` asks what you want to do, routes you

**Examples:**
- `create_handoff` — Save your session state before ending
- `premortem` — Risk analysis (TIGERS & ELEPHANTS)
- `tldr-code` — Analyze code structure (95% token savings)
- `perplexity-search` — AI-powered web search
- `qlty-check` — Run 70+ linters and auto-fix issues

**Do I need to code?** No. Skills work via natural language.

### Agents (32)

**What they are:** Specialized AI assistants Claude delegates work to

**How you use them:**
- Automatic: Workflows spawn them (you don't manage)
- Manual: `/agent scout "find authentication code"`

**Why they help:**
- **Preserve context** — Agent does research, returns summary
- **Parallel work** — Spawn multiple agents at once
- **Specialization** — Each agent has a focused role and detailed prompt

**Examples:**
- `scout` explores codebases without reading every file
- `oracle` researches external topics (web, docs, APIs)
- `sleuth` investigates bugs with root cause analysis
- `kraken` implements features with test-driven development

**Do I need to code?** No. Agents work on your behalf.

### Hooks (66)

**What they are:** Background helpers that run automatically at specific moments

**How you use them:**
- You don't — they're automatic
- They activate on events like "session start" or "before file read"

**Examples:**
- **tldr-read-enforcer** — Returns code summaries instead of full files (token savings)
- **smart-search-router** — Routes text searches to structural analysis tools
- **post-edit-diagnostics** — Runs type checking after you edit code
- **memory-awareness** — Surfaces relevant learnings from past sessions

**Do I need to code?** No. Hooks work invisibly.

### Rules (12)

**What they are:** Guidelines that keep Claude consistent

**Examples:**
- Don't claim something is "faster" without benchmarks
- Ask before deleting files or running destructive git commands
- Use agents for complex tasks to keep main context clean
- Read files before editing them

**Do I need to code?** No. Rules are policy, not code.

---

## Common Questions

### Do I Need to Code?

**Short answer:** No.

**Longer answer:**
- **Most features** work through natural language (research, planning, analysis)
- **Code analysis** works on codebases you provide — you don't write the analysis code
- **Workflows** trigger via commands like `/fix` or `/build`
- **Advanced features** (hooks, custom agents) require coding, but are optional

If you can describe what you want, Continuous Claude can do it.

### What If Something Breaks?

**Common issues:**

| Problem | Solution |
|---------|----------|
| "Docker not running" | Start Docker Desktop |
| "Database connection failed" | Run `docker ps` to check containers, restart with wizard |
| "Skill not found" | Re-run wizard step 6 to reinstall skills |
| "Agent failed to spawn" | Check `~/.claude/agents/` exists, verify settings.json |

**Troubleshooting:**

```bash
# Check Docker containers
docker ps

# Restart database
cd continuous-claude/opc
docker-compose down
docker-compose up -d

# Reinstall components
uv run python -m scripts.setup.wizard
# Select the step you want to re-run
```

**Get help:**
- [GitHub Issues](https://github.com/parcadei/continuous-claude/issues) — file a bug report
- [Discussions](https://github.com/parcadei/continuous-claude/discussions) — ask questions
- [Documentation](https://github.com/parcadei/continuous-claude/tree/main/docs) — detailed guides

### How Do I Uninstall?

```bash
cd continuous-claude/opc
uv run python -m scripts.setup.wizard --uninstall
```

This will:
1. Archive your current setup (timestamped, nothing deleted)
2. Restore your pre-installation backup
3. Preserve your data:
   - Command history
   - API keys
   - MCP servers
   - Project configurations
4. Remove Continuous Claude components (hooks, skills, agents, rules)

Your Claude Code setup returns to exactly how it was before installation.

### Do I Need API Keys?

**Optional API keys** (features work without them):

| Service | What It Does | Cost |
|---------|--------------|------|
| [Perplexity](https://www.perplexity.ai/settings/api) | AI-powered web search | $5/mo or pay-per-use |
| [Nia](https://trynia.ai) | Library documentation search | Free tier available |
| [Braintrust](https://braintrust.dev) | Session tracing and debugging | Free tier available |

**Core features work without any keys:**
- Continuity system (ledgers, handoffs, memory)
- Code analysis (95% token savings)
- All workflows (/build, /fix, /tdd, /refactor)
- Local agents (scout, kraken, sleuth)
- Git operations

API keys unlock optional research features, not core functionality.

### What About Privacy?

**Data stored locally:**
- Continuity ledgers (Markdown files in `thoughts/`)
- Handoffs (YAML files in `thoughts/shared/`)
- Code analysis cache (`.tldr/` directory)
- PostgreSQL database (Docker container on your machine)

**Data sent to Anthropic:**
- Your prompts and Claude's responses (standard Claude usage)
- Code you ask Claude to analyze (only what you share)

**Data sent to third-party APIs (if you use them):**
- Perplexity: Search queries only
- Nia: Library names for documentation lookup
- Braintrust: Session traces for debugging (opt-in)

**No data leaves your machine** except what you explicitly share with Claude or optional third-party APIs.

### Can I Use This with Existing Projects?

**Yes.** After installation:

```bash
# Navigate to your project
cd ~/my-project

# Start Claude
claude

# Run onboarding
> /onboard
```

The onboard agent will:
1. Analyze your codebase structure
2. Detect languages and frameworks
3. Create an initial continuity ledger
4. Build a semantic index for code search

Then you can use all features (`/build`, `/fix`, etc.) with full context about your project.

### How Does It Compare to X?

**vs. GitHub Copilot:**
- Copilot autocompletes as you type (editor-focused)
- Continuous Claude orchestrates workflows (task-focused)
- Use both together — they solve different problems

**vs. Cursor:**
- Cursor is an IDE with AI built in
- Continuous Claude extends Claude Code (works in any terminal)
- Similar multi-agent concepts, different execution

**vs. Vanilla Claude Code:**
- Claude Code gives you Claude in the terminal
- Continuous Claude adds memory, agents, and workflows
- Like upgrading from a chat interface to a development environment

---

## For Developers

<details>
<summary>Click to expand technical architecture, code analysis, and advanced features</summary>

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CONTINUOUS CLAUDE                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   Skills    │    │   Agents    │    │    Hooks    │             │
│  │   (112)     │───▶│    (32)     │◀───│    (66)     │             │
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

### The 5-Layer Code Analysis Stack

**Problem:** Reading a 1,000-line file costs ~23,000 tokens and provides mostly irrelevant details.

**Solution:** Extract 5 layers of structural information totaling ~1,200 tokens.

| Layer | Name | What It Provides | Tokens |
|-------|------|------------------|--------|
| **L1** | AST | Functions, classes, signatures | ~500 |
| **L2** | Call Graph | Who calls what (cross-file) | +440 |
| **L3** | CFG | Control flow, complexity | +110 |
| **L4** | DFG | Data flow, variable tracking | +130 |
| **L5** | PDG | Program slicing, impact analysis | +150 |

**Total: ~1,200 tokens vs. 23,000 raw = 95% savings**

**CLI Examples:**

```bash
# See what exists without reading files
tldr tree src/ --ext .py

# Find code structurally, not textually
tldr search "process_data" src/

# Get context for implementation
tldr context process_data --project src/ --depth 2

# Understand control flow
tldr cfg src/processor.py process_data

# Impact analysis before refactoring
tldr impact process_data src/ --depth 3

# Find dead code for cleanup
tldr dead src/ --entry main cli

# Detect architectural layers
tldr arch src/
```

### Semantic Index

Beyond structural analysis, TLDR builds a semantic index:

- **Natural language queries** — "where is error handling?" instead of grepping
- **Auto-rebuild** — Hooks track file changes, index rebuilds when dirty
- **Selective indexing** — `.tldrignore` controls what gets indexed

```bash
# Natural language search
tldr daemon semantic "find authentication logic"
```

The index uses all 5 layers plus 10 lines of surrounding code — not just docstrings.

### Memory System Architecture

**How it works:**

```
Session ends → Database detects stale heartbeat (>5 min)
            → Daemon spawns headless Claude (Sonnet)
            → Analyzes thinking blocks from session
            → Extracts learnings to archival_memory
            → Next session recalls via semantic search
```

**Key insight:** Thinking blocks contain real reasoning (not just actions). The daemon extracts this automatically.

**Database schema (4 tables):**

| Table | Purpose |
|-------|---------|
| `sessions` | Cross-terminal awareness (heartbeat tracking) |
| `file_claims` | Cross-terminal file locking |
| `archival_memory` | Long-term learnings with BGE embeddings (1024-dim) |
| `handoffs` | Session handoffs with embeddings |

**Recall examples:**

```bash
# Hybrid search (text + vector, RRF ranking)
cd continuous-claude/opc
uv run python scripts/core/recall_learnings.py --query "authentication patterns"

# Store a learning explicitly
cd continuous-claude/opc
uv run python scripts/core/store_learning.py \
    --session-id "my-session" \
    --type WORKING_SOLUTION \
    --content "What I learned" \
    --context "Relevant context" \
    --tags "auth,jwt,security" \
    --confidence high
```

### Continuity System

**Ledgers (within-session):** Track state during work

Location: `thoughts/ledgers/CONTINUITY_<topic>.md`

```markdown
# Session: feature-x
Updated: 2026-01-23

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

**Handoffs (between-session):** Transfer knowledge between sessions

Location: `thoughts/shared/handoffs/<session>/current.yaml`

```yaml
---
date: 2026-01-23T15:26:01+0000
session_name: feature-x
status: complete
---

# Handoff: Feature X Implementation

## Tasks
| Task | Status |
|------|--------|
| Design API | Completed |
| Implement core | Completed |
| Error handling | Pending |

## Next Steps
1. Add retry logic to API calls
2. Write integration tests
```

### Workflow Examples

**Test-Driven Development:**

```
> /tdd "implement retry logic with exponential backoff"

Chain:
  1. plan-agent → designs test cases
  2. arbiter → writes failing tests (🔴)
  3. kraken → implements until tests pass (🟢)
  4. arbiter → verifies all tests pass (✓)
  5. commit → descriptive commit message
```

**Safe Refactoring:**

```
> /refactor "extract auth module"

Chain:
  1. phoenix → analyzes dependencies
  2. plan-reviewer → validates approach
  3. kraken → transforms code (TDD)
  4. judge → reviews changes
  5. arbiter → runs full test suite
```

**Formal Verification:**

```
> /prove "every group homomorphism preserves identity"

5-Phase Workflow:
  📚 RESEARCH → Find Mathlib lemmas, proof strategies
  🏗️ DESIGN → Create skeleton with sorry placeholders
  🧪 TEST → Search for counterexamples
  ⚙️ IMPLEMENT → Fill sorries with compiler feedback
  ✅ VERIFY → Audit axioms, confirm zero sorries
```

### Hook Integration Points

| Event | Key Hooks | What They Do |
|-------|-----------|--------------|
| **SessionStart** | session-start-continuity, session-register | Load ledger, register in DB |
| **PreToolUse** | tldr-read-enforcer, smart-search-router | Token savings, route searches |
| **PostToolUse** | post-edit-diagnostics, handoff-index | Type check, update indexes |
| **PreCompact** | pre-compact-continuity | Auto-save before context clears |
| **UserPromptSubmit** | skill-activation-prompt, memory-awareness | Suggest skills, recall learnings |
| **SubagentStop** | subagent-stop-continuity | Save agent state |
| **SessionEnd** | session-end-cleanup, session-outcome | Extract learnings, cleanup |

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `CONTINUOUS_CLAUDE_DB_URL` | PostgreSQL connection | Yes (wizard sets) |
| `CLAUDE_OPC_DIR` | Path to opc/ directory | Yes (wizard sets) |
| `CLAUDE_PROJECT_DIR` | Current project root | Yes (hook sets) |
| `BRAINTRUST_API_KEY` | Session tracing | No |
| `PERPLEXITY_API_KEY` | Web search | No |
| `NIA_API_KEY` | Documentation search | No |

### Directory Structure

```
continuous-claude/
├── .claude/
│   ├── agents/           # 32 specialized AI agents
│   ├── hooks/            # 66 lifecycle hooks
│   │   ├── src/          # TypeScript source
│   │   └── dist/         # Compiled JavaScript
│   ├── skills/           # 112 modular capabilities
│   ├── rules/            # 12 system policies
│   ├── scripts/          # Python utilities
│   └── settings.json     # Hook configuration
├── opc/
│   ├── packages/
│   │   └── tldr-code/    # 5-layer code analysis
│   ├── scripts/
│   │   ├── setup/        # Wizard, Docker, integration
│   │   └── core/         # recall_learnings, store_learning
│   └── docker/
│       └── init-schema.sql  # 4-table PostgreSQL schema
├── thoughts/
│   ├── ledgers/          # Continuity ledgers (CONTINUITY_*.md)
│   └── shared/
│       ├── handoffs/     # Session handoffs (*.yaml)
│       └── plans/        # Implementation plans
└── docs/                 # Documentation
```

### Remote Database Setup

For production or team setups, use a remote PostgreSQL instance:

```bash
# 1. Enable pgvector extension (requires superuser)
psql -h hostname -U user -d continuous_claude
CREATE EXTENSION IF NOT EXISTS vector;

# 2. Apply schema
psql -h hostname -U user -d continuous_claude -f docker/init-schema.sql

# 3. Configure connection
# In ~/.claude/settings.json:
{
  "env": {
    "CONTINUOUS_CLAUDE_DB_URL": "postgresql://user:password@hostname:5432/continuous_claude"
  }
}
```

**Managed PostgreSQL tips:**
- **AWS RDS:** Add `vector` to `shared_preload_libraries` in Parameter Group
- **Supabase:** Enable via Database Extensions page
- **Azure:** Use Extensions pane to enable pgvector

### Installation Modes

| Mode | How It Works | Best For |
|------|--------------|----------|
| **Copy** (default) | Copies files to `~/.claude/` | End users, stable setup |
| **Symlink** | Links `~/.claude/` to repo | Contributors, development |

**Switching to symlink mode:**

```bash
# Backup current config
mkdir -p ~/.claude/backups/$(date +%Y%m%d)
cp -r ~/.claude/{rules,skills,hooks,agents} ~/.claude/backups/$(date +%Y%m%d)/

# Remove copies
rm -rf ~/.claude/{rules,skills,hooks,agents}

# Create symlinks
REPO="$HOME/continuous-claude"
ln -s "$REPO/.claude/rules" ~/.claude/rules
ln -s "$REPO/.claude/skills" ~/.claude/skills
ln -s "$REPO/.claude/hooks" ~/.claude/hooks
ln -s "$REPO/.claude/agents" ~/.claude/agents

# Verify
ls -la ~/.claude | grep -E "rules|skills|hooks|agents"
```

### Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Adding skills
- Creating agents
- Developing hooks
- Extending TLDR
- Testing workflows

</details>

---

## What's Next?

After installation, try these in order:

1. **First workflow:** `/workflow` → Pick "Research" → "Understand codebase"
2. **Save state:** "Done for today" → Creates handoff automatically
3. **Resume:** Next session, "Resume work" → Loads handoff
4. **Build something:** `/build greenfield "describe feature"`
5. **Fix something:** `/fix bug "describe problem"`
6. **Risk analysis:** `/premortem` → See what could go wrong before implementing

The system learns from each session. The more you use it, the smarter it gets.

---

## Acknowledgments

### Patterns & Architecture
- **[@numman-ali](https://github.com/numman-ali)** - Continuity ledger pattern
- **[Anthropic](https://anthropic.com)** - Claude Code
- **[obra/superpowers](https://github.com/obra/superpowers)** - Agent orchestration patterns
- **[EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin)** - Compound engineering workflow

### Tools & Services
- **[uv](https://github.com/astral-sh/uv)** - Python packaging
- **[tree-sitter](https://tree-sitter.github.io/)** - Code parsing
- **[Braintrust](https://braintrust.dev)** - LLM tracing and evaluation
- **[qlty](https://github.com/qltysh/qlty)** - Universal code quality (70+ linters)
- **[ast-grep](https://github.com/ast-grep/ast-grep)** - AST-based code search
- **[Nia](https://trynia.ai)** - Library documentation search
- **[Morph](https://www.morphllm.com)** - Fast code search
- **[Firecrawl](https://www.firecrawl.dev)** - Web scraping API

---

## License

[MIT](LICENSE) - Use freely, contribute back.

---

**Continuous Claude**: Not just a coding assistant — a persistent, learning, multi-agent development environment that gets smarter with every session.

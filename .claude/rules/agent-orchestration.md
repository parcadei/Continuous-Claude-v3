# Agent Orchestration Rules

**PRIMARY:** Use Agentica for multi-step tasks. The main conversation is the orchestrator.

## CRITICAL: Use Agentica, Not Task Tool

**DO NOT use the Task tool** for multi-step work. Use Agentica via Bash:

```bash
uv run python scripts/agentica_dispatch.py --prompt "Your task description here"
```

**Why:**
- Agentica has Scope (tool registry), pattern detection, and resource gating
- Main conversation stays the orchestrator - you decide what to dispatch
- Task tool is vanilla subagent spawning without these capabilities

## When to Use What

| Task Type | Tool | Command |
|-----------|------|---------|
| Multi-file implementation | **Agentica** | `uv run python scripts/agentica_dispatch.py --prompt "..."` |
| Research / exploration | **Agentica** | `--pattern swarm` |
| Following a plan phase | **Agentica** | `--pattern hierarchical` |
| Review / validation | **Agentica** | `--pattern jury` |
| Single-line fix | Direct edit | Use Edit tool directly |
| Quick config change | Direct edit | Use Edit tool directly |

**Rule: If it takes more than 2-3 tool calls, dispatch to Agentica.**

## Example Dispatch Commands

```bash
# Research task (auto-detects swarm)
uv run python scripts/agentica_dispatch.py \
  --prompt "Research authentication patterns in this codebase"

# Implementation task (auto-detects hierarchical)
uv run python scripts/agentica_dispatch.py \
  --prompt "Implement Phase 4: Outcome Marking Hook from thoughts/shared/plans/2025-12-24-artifact-index.md"

# Explicit pattern hint
uv run python scripts/agentica_dispatch.py \
  --prompt "Review these 3 PRs for security issues" \
  --pattern jury
```

## The Orchestration Pattern

```
You (main conversation) = Orchestrator
      ↓
Dispatch to Agentica (Bash)
      ↓
Agentica selects pattern (swarm/hierarchical/jury/etc)
      ↓
Agents execute with Scope (tools)
      ↓
Result returned to you
      ↓
You summarize for user
```

## Trigger Words → Agentica Dispatch

When user says these, **dispatch to Agentica**:
- "implement", "build", "create feature"
- "follow the plan", "do phase X"
- "research", "investigate", "explore"
- "review", "validate", "check"

## Multi-Agent Pattern Selection

When orchestrating complex tasks, select the appropriate pattern based on task characteristics.
Reference: `scripts/agentica/PATTERNS.md` for full pattern details.

### Pattern Selection Guide

| Task Involves... | Pattern | Implementation |
|------------------|---------|----------------|
| Research, exploration, "investigate" | **Swarm** | Spawn 3+ agents with different angles, synthesize |
| Implementation, "build", "create" | **Hierarchical** | Coordinator → specialists → grunts |
| Review, critique, "feedback" | **Generator/Critic** | One proposes → one critiques → iterate |
| Validation, "is correct", high-stakes | **Jury** | 3+ agents vote independently, majority wins |
| Linear workflow, clear steps | **Pipeline** | A → B → C → D (sequential handoff) |
| Parallel independent work | **Map/Reduce** | Fan out N agents → aggregator combines |
| Unknown complexity | **Start Hierarchical** | Adapt and spawn swarms as needed |

### Hybrid Patterns

Patterns can compose:
- **Hierarchical + Swarm**: Coordinator spawns swarm for research phase
- **Generator/Critic + Jury**: Multiple critics vote on generator output
- **Pipeline + Circuit Breaker**: Fallback agents on step failure

### Meta-Pattern: Claude IS the Router

Don't build a separate router - Claude selects patterns based on:
1. Task keywords (see table above)
2. Complexity assessment
3. Risk level (high-stakes → Jury)
4. Parallelizability (independent subtasks → Swarm/Map-Reduce)

## Avoid Hot-Path LLMs

Don't use LLMs for retrieval. Use them for reasoning.

**DO:**
- Store facts in SQLite/structured data
- Query DB for "what's done" (milliseconds)
- Use LLMs for summarization, ambiguity resolution

**DON'T:**
- Ask an "Oracle agent" to recall state
- Route coordination queries through LLMs
- Use LLMs for anything that could be a database lookup

**Source Sessions:** a6a1772c, a8b5a799

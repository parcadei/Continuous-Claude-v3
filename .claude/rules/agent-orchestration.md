# Agent Orchestration Rules

When the user asks to implement something, use implementation agents to preserve main context.

## The Pattern

**Wrong - burns context:**
```
Main: Read files → Understand → Make edits → Report
      (2000+ tokens consumed in main context)
```

**Right - preserves context:**
```
Main: Spawn agent("implement X per plan")
      ↓
Agent: Reads files → Understands → Edits → Tests
      ↓
Main: Gets summary (~200 tokens)
```

## When to Use Agents

| Task Type | Use Agent? | Reason |
|-----------|------------|--------|
| Multi-file implementation | Yes | Agent handles complexity internally |
| Following a plan phase | Yes | Agent reads plan, implements |
| New feature with tests | Yes | Agent can run tests |
| Single-line fix | No | Faster to do directly |
| Quick config change | No | Overhead not worth it |

## Key Insight

Agents read their own context. Don't read files in main chat just to understand what to pass to an agent - give them the task and they figure it out.

## Example Prompt

```
Implement Phase 4: Outcome Marking Hook from the Artifact Index plan.

**Plan location:** thoughts/shared/plans/2025-12-24-artifact-index.md (search for "Phase 4")

**What to create:**
1. TypeScript hook
2. Shell wrapper
3. Python script
4. Register in settings.json

When done, provide a summary of files created and any issues.
```

## Trigger Words

When user says these, consider using an agent:
- "implement", "build", "create feature"
- "follow the plan", "do phase X"
- "use implementation agents"

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

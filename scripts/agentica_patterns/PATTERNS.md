# Multi-Agent Patterns

Reference for agentic orchestration patterns. Use to inform router decisions.

## Core Patterns

### 1. Hierarchical (Coordinator → Specialists → Grunts)
- **Structure:** Tree with info flowing up
- **StateKeeper:** Coordinator maintains state, writes handoff at end
- **Use when:** Complex tasks with clear decomposition, need accountability chain

### 2. Swarm (Parallel Attack)
- **Structure:** Multiple agents attack problem from different angles simultaneously
- **Use when:** Research, exploration, need diverse perspectives, time-sensitive

### 3. Sequential/Pipeline (Solo Chain)
- **Structure:** A → B → C → D (each agent hands off to next)
- **Use when:** Clear linear workflow, each step transforms output

### 4. Generator/Critic (Propose → Critique → Refine)
- **Structure:** Generator proposes → Critic evaluates → Generator refines → loop
- **Use when:** Code review, writing, any iterative refinement task

### 5. Adversarial (Red vs Blue)
- **Structure:** Red team attacks → Blue team defends → Judge synthesizes
- **Use when:** Security review, stress testing ideas, finding edge cases

### 6. Map/Reduce (Fan Out → Aggregate)
- **Structure:** Fan out to N parallel workers → Aggregator combines results
- **Use when:** Research across sources, batch processing, parallelizable analysis

### 7. Blackboard (Shared State)
- **Structure:** Central shared state that all agents read/write
- **Use when:** Collaborative problem solving, emergent solutions

### 8. Circuit Breaker (Primary → Fallback)
- **Structure:** Try primary → On failure, try fallback → On failure, escalate
- **Use when:** Resilient pipelines, graceful degradation

### 9. Jury/Voting (N Agents Vote)
- **Structure:** N agents independently evaluate → Consensus/majority wins
- **Use when:** High-stakes decisions, reducing hallucination, validation

### 10. Chain of Responsibility (Escalation)
- **Structure:** Try A → if can't handle, try B → if can't, try C
- **Use when:** Capability matching, tiered support, cost optimization

### 11. Event-Driven (Subscribe/React)
- **Structure:** Agents subscribe to events, react when triggered
- **Use when:** Monitoring, reactive systems, async workflows

## Hybrid Patterns

### Hierarchical + Swarm
```
         Coordinator
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
  Swarm A   Swarm B   Swarm C
```

### Generator/Critic + Jury
```
  Generator → Critic A ─┐
                        ├→ Voting → Final
            → Critic B ─┘
```

### Pipeline + Circuit Breaker
```
  A → B → C
      │
      └→ B-fallback (if B fails)
```

## Meta-Pattern: Adaptive Routing

The coordinator/router decides which pattern based on task characteristics:
- Research task? → Swarm or Map/Reduce
- Code implementation? → Generator/Critic or Hierarchical
- High-stakes decision? → Jury
- Unknown complexity? → Start hierarchical, spawn swarms as needed

## Open Questions

1. Should routing be explicit (rules) or emergent (LLM decides)?
2. Can patterns compose dynamically at runtime?
3. What's the optimal agent count before coordination overhead dominates?
4. How do patterns interact with state persistence (handoffs)?

# Architecture Map: Headless Claude Agent Orchestration

This document maps the complete architecture for orchestrating headless Claude CLI agents **without Agentica SDK**.

## Executive Summary

The current architecture routes Task tool calls through a unified gate (erotetic, resources, composition) and into Agentica SDK for pattern execution. Removing Agentica requires:

1. **Keep**: Pattern algebra, composition validation, resource gating, erotetic logic
2. **Replace**: Agentica SDK spawn() with Claude Code Task tool
3. **Simplify**: Remove websocket multiplexing, agent registries, claude_proxy.py

The Task tool already provides agent spawning - we just need the pattern selection and gating logic.

---

## Pattern Execution Flow

### Current Flow (WITH Agentica)

```
User prompt
    |
    v
[skill-router.ts] --> skill activation
    |
    v
[task-router.ts] --> PreToolUse hook intercepts Task calls
    |
    v
[unified_gate.py] --> 3-gate validation:
    |   1. gate1_erotetic() - check E(X,Q) for unknowns
    |   2. gate2_resources() - check RAM/CPU via psutil
    |   3. gate3_composition() - validate pattern algebra
    |
    v
[pattern_inference.py] --> infer pattern from prompt keywords
    |
    v
[orchestration_layer.py] --> route to pattern executor
    |
    v
[patterns.py] --> Agentica spawn() for Swarm/Jury/etc.
    |
    v
[claude_proxy.py] --> WebSocket multiplexing to Claude CLI
```

### Proposed Flow (WITHOUT Agentica)

```
User prompt
    |
    v
[Main Claude Conversation] --> pattern detection
    |
    +---> Simple task (< 100 chars, quick fix)
    |         |
    |         v
    |     Direct tool use (no agent spawn)
    |
    +---> Complex task (implementation, research, review)
          |
          v
      [Pattern Selection] (infer from keywords)
          |
          +---> Swarm pattern
          |         |
          |         v
          |     Task(prompt="Research angle 1", wait=true)
          |     Task(prompt="Research angle 2", wait=true)
          |     Task(prompt="Research angle 3", wait=true)
          |     (main summarizes results)
          |
          +---> Pipeline pattern
          |         |
          |         v
          |     Task(prompt="Step 1: ...", wait=true)
          |         |
          |         v (handoff via result)
          |     Task(prompt="Step 2 using: {step1_result}", wait=true)
          |
          +---> Jury pattern
          |         |
          |         v
          |     Task(prompt="Vote 1: ...", wait=true)
          |     Task(prompt="Vote 2: ...", wait=true)
          |     Task(prompt="Vote 3: ...", wait=true)
          |     (main aggregates votes)
          |
          +---> Hierarchical pattern
                    |
                    v
                Coordinator Task(prompt="Decompose...", wait=true)
                    |
                    v
                Worker Tasks (spawned by coordinator or main)
```

### Key Insight: Main Conversation IS the Orchestrator

The main Claude conversation can:
1. Detect patterns via keyword analysis (from `pattern_inference.py`)
2. Spawn agents via `Task(prompt="...", wait=true)`
3. Aggregate results and handoff between agents
4. Apply composition rules by structuring Task calls

**No separate orchestration layer needed** - Claude Code's Task tool IS the spawning mechanism.

---

## Process Algebra Integration

### Pattern Algebra Operators

From `docs/agentic-orchestration/pattern-algebra.md` and `scripts/validate_composition.py`:

| Operator | Symbol | Claude Task Mapping |
|----------|--------|---------------------|
| Sequential | `;` | Task A, wait, then Task B with A's result |
| Parallel | `\|` | Multiple Tasks spawned before any await |
| Choice | `+` | Task A, if fails then Task B |

### Can Composition Operators Work with Task Tool?

**YES** - but the composition logic lives in the main conversation, not in code:

```python
# Sequential composition: Pipeline ;[handoff] Aggregator
result_a = Task(prompt="Pipeline step 1")  # wait for completion
result_b = Task(prompt=f"Aggregate: {result_a}")  # pass result

# Parallel composition: Swarm |[iso] Jury
# (isolated scope - agents don't share state)
votes = []
votes.append(Task(prompt="Evaluate X from angle 1"))
votes.append(Task(prompt="Evaluate X from angle 2"))
votes.append(Task(prompt="Evaluate X from angle 3"))
# Main conversation aggregates

# Choice composition: Primary +[iso] CircuitBreaker
try:
    result = Task(prompt="Primary approach")
except:
    result = Task(prompt="Fallback approach")
```

### Scope Types Map to Task Isolation

| Scope | Meaning | Task Tool Behavior |
|-------|---------|-------------------|
| `iso` (Isolated) | No shared state | Default - each Task is independent |
| `handoff` | State transfer at boundaries | Pass result string between Tasks |
| `shared` | Agents see each other's work | NOT supported - use PostgreSQL or files |
| `fed` (Federated) | Cross-agent queries | NOT supported without explicit mechanism |

**Recommendation**: For `shared` and `fed` scopes, use:
- CoordinationDB (PostgreSQL) for structured state
- File-based handoffs for document state
- Explicit prompt context for read-only queries

---

## Erotetic Logic Assessment

### What It Does

From `scripts/z3_erotetic.py` and `scripts/erotetic_skill_check.py`:

1. **Proposition Extraction**: Extracts key propositions from prompts (framework, database, auth method, etc.)
2. **E(X,Q) Computation**: Uses Z3 solver to identify unknowns (propositions that need clarification)
3. **Clarification Gate**: Blocks execution when unknowns exist, prompts user for clarification

### Current Implementation

```typescript
// .claude/hooks/src/erotetic-clarification.ts
// Calls z3_erotetic_cli.py to compute E(X,Q)
// Returns unknowns to prompt user
```

### Is It Useful?

**YES, but overkill for most cases.**

The erotetic logic provides formal guarantees but has overhead:
- Z3 solver invocation per task
- Pattern matching for proposition extraction
- Complex configuration per skill

**Simplified Alternative**:
- Keyword-based heuristic (already in `pattern_inference.py`)
- Simple unknowns list in skill YAML
- No Z3 dependency

### Recommendation

**Keep simplified erotetic logic**:
1. Skill YAML defines required parameters
2. Hook extracts parameters from prompt
3. Missing parameters trigger clarification
4. No Z3 solver needed

---

## Hook Integration Points

### Existing Hooks That Support Agent Routing

| Hook | File | Purpose | Keep? |
|------|------|---------|-------|
| `skill-router.ts` | `.claude/hooks/src/skill-router.ts` | Activates skills from prompt | YES |
| `task-router.ts` | `.claude/hooks/src/task-router.ts` | Intercepts Task tool, routes to Agentica | MODIFY |
| `erotetic-clarification.ts` | `.claude/hooks/src/erotetic-clarification.ts` | Blocks on unknowns | SIMPLIFY |
| `resource-gate.ts` | `.claude/hooks/src/resource-gate.ts` | Checks system resources | KEEP |
| `composition-gate-hook.ts` | `.claude/hooks/src/composition-gate-hook.ts` | Validates pattern algebra | KEEP |

### Proposed Hook Architecture

```
[PreToolUse: Task]
    |
    v
[pattern-gate.sh] --> NEW unified hook
    |
    +---> Check resources (psutil-based)
    +---> Infer pattern (keyword matching)
    +---> Validate composition (if multi-step)
    +---> Return message with pattern guidance
    |
    v
[Task tool executes normally]
```

The key insight: **Don't block Task tool** - just provide guidance via hook message. Main conversation decides how to structure Task calls.

### Could skill-rules.json Trigger Agent Patterns?

**YES** - add pattern metadata to skill rules:

```json
{
  "implement-feature": {
    "pattern": "hierarchical",
    "subpatterns": {
      "research_phase": "swarm",
      "review_phase": "jury"
    },
    "triggers": ["implement", "build", "create"]
  }
}
```

Hook reads this and includes pattern guidance in message.

---

## Keep vs Delete List

### Keep (Essential for Headless Agent Orchestration)

| File | Reason |
|------|--------|
| `scripts/validate_composition.py` | Pattern algebra validation (can_compose, scope checks) |
| `scripts/agentica_patterns/pattern_inference.py` | Keyword-based pattern detection |
| `scripts/agentica_patterns/pattern_resolver.py` | Bridges tasks to patterns |
| `scripts/validate_resources.py` | Resource validation (psutil-based) |
| `scripts/z3_erotetic.py` | Core evocation logic (simplify to heuristic) |
| `.claude/hooks/src/skill-router.ts` | Skill activation |
| `.claude/hooks/src/resource-gate.ts` | Resource gating |
| `docs/agentic-orchestration/pattern-algebra.md` | Pattern algebra spec |

### Modify (Adapt for Task Tool)

| File | Modification |
|------|--------------|
| `.claude/hooks/src/task-router.ts` | Remove Agentica routing, keep pattern detection |
| `.claude/hooks/src/erotetic-clarification.ts` | Simplify to keyword-based (remove Z3) |
| `.claude/rules/agent-orchestration.md` | Update to use Task tool instead of Agentica dispatch |

### Delete (Agentica-Specific)

| File | Reason |
|------|--------|
| `scripts/agentica_dispatch.py` | Entry point for Agentica - not needed |
| `scripts/agentica_patterns/claude_proxy.py` | WebSocket proxy to CLI - Task tool replaces |
| `scripts/agentica_patterns/websocket_multiplex.py` | WebSocket multiplexing - not needed |
| `scripts/agentica_patterns/unified_gate.py` | Agentica orchestration entry - simplify to hook |
| `scripts/agentica_patterns/orchestration_layer.py` | Agentica pattern execution - Task tool replaces |
| `scripts/agentica_patterns/patterns.py` | Agentica spawn() implementations - rewrite for Task |
| `scripts/agentica_patterns/agent_scope.py` | Agentica scope management - not needed |
| `scripts/agentica_patterns/claude_scope.py` | Agentica scope for Claude - not needed |
| `scripts/agentica_patterns/unified_scope.py` | Unified scope abstraction - not needed |
| `scripts/agentica_patterns/coordination.py` | Agentica coordination DB - move to PostgreSQL |
| `scripts/agentica_patterns/task_executor.py` | Agentica task execution - Task tool replaces |
| `scripts/agentica_patterns/resource_pool.py` | Agentica resource pooling - not needed |
| `scripts/agentica_patterns/tracked_agent.py` | Agentica agent tracking - not needed |
| `scripts/agentica_patterns/watch_agents.py` | Agentica agent monitor - not needed |
| `scripts/agentica_patterns/session_tree.py` | Agentica session hierarchy - not needed |
| `scripts/agentica_patterns/memory_*.py` | Agentica memory services - move to PostgreSQL |
| `scripts/agentica_patterns/embedding_service.py` | Agentica embeddings - move to PostgreSQL |
| `scripts/agentica_patterns/span_processor.py` | Agentica tracing - Braintrust replaces |
| `scripts/agentica_patterns/skill_*.py` | Agentica skill injection - Claude skills replace |
| `.claude/skills/agentica-*/` | Agentica-specific skills - delete |
| `.claude/skills/sub-agents/` | Agentica sub-agent docs - rewrite for Task tool |

### Move to PostgreSQL

| File | New Location |
|------|--------------|
| `scripts/agentica_patterns/postgres_pool.py` | Keep as core PostgreSQL pool |
| `scripts/agentica_patterns/memory_service_pg.py` | Generalize for coordination state |
| `scripts/agentica_patterns/coordination.py` | Simplify to PostgreSQL-only |
| `scripts/agentica_patterns/blackboard.py` | Keep for shared state pattern |

---

## Next Steps

1. **Create minimal pattern executor** that uses Task tool instead of spawn()
2. **Update agent-orchestration.md** rules to reference Task tool patterns
3. **Simplify erotetic hook** to keyword-based (no Z3)
4. **Migrate coordination state** from SQLite to PostgreSQL
5. **Delete Agentica-specific files** per list above
6. **Test pattern execution** with Task tool directly

---

## Appendix: Pattern-to-Task Mapping Examples

### Swarm Pattern (Research)

```python
# Main conversation orchestrates:
angles = [
    "authentication patterns in codebase",
    "security vulnerabilities in auth flow",
    "best practices from docs"
]
results = []
for angle in angles:
    result = Task(prompt=f"Research: {angle}", wait=True)
    results.append(result)
# Main synthesizes results
```

### Jury Pattern (Voting)

```python
# Main conversation orchestrates:
votes = []
for i in range(3):
    vote = Task(prompt=f"Vote {i+1}: Is this PR safe to merge?", wait=True)
    votes.append(vote)
# Main counts votes, decides
```

### Hierarchical Pattern (Coordinator + Workers)

```python
# Coordinator task decomposes:
plan = Task(prompt="Decompose: implement user auth feature", wait=True)
# Main parses plan, spawns workers:
for step in plan.steps:
    Task(prompt=f"Implement: {step}", wait=True)
```

### Pipeline Pattern (Sequential Handoff)

```python
# Main orchestrates sequential flow:
design = Task(prompt="Design the API schema", wait=True)
impl = Task(prompt=f"Implement based on design: {design}", wait=True)
tests = Task(prompt=f"Write tests for: {impl}", wait=True)
```

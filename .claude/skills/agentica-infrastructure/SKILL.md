---
name: agentica-infrastructure
description: Reference guide for Agentica multi-agent infrastructure APIs
allowed-tools: [Read]
---

# Agentica Infrastructure Reference

Complete API specification for Agentica multi-agent coordination infrastructure.

## When to Use

- Building multi-agent workflows with Agentica patterns
- Need exact constructor signatures for pattern classes
- Want to understand coordination database schema
- Implementing custom patterns using primitives
- Debugging agent tracking or orphan detection

## Quick Reference

### 11 Pattern Classes

| Pattern | Purpose | Key Method |
|---------|---------|------------|
| `Swarm` | Parallel perspectives | `.execute(query)` |
| `Pipeline` | Sequential stages | `.run(initial_state)` |
| `Hierarchical` | Coordinator + specialists | `.execute(task)` |
| `Jury` | Voting consensus | `.decide(return_type, question)` |
| `GeneratorCritic` | Iterative refinement | `.run(task)` |
| `CircuitBreaker` | Failure fallback | `.execute(query)` |
| `Adversarial` | Debate + judge | `.resolve(question)` |
| `ChainOfResponsibility` | Route to handler | `.process(query)` |
| `MapReduce` | Fan out + reduce | `.execute(query, chunks)` |
| `Blackboard` | Shared state | `.solve(query)` |
| `EventDriven` | Event bus | `.publish(event)` |

### Core Infrastructure

| Component | File | Purpose |
|-----------|------|---------|
| `CoordinationDB` | `coordination.py` | SQLite tracking |
| `tracked_spawn` | `tracked_agent.py` | Agent with tracking |
| `HandoffAtom` | `handoff_atom.py` | Universal handoff format |
| `BlackboardCache` | `blackboard.py` | Hot tier communication |
| `MemoryService` | `memory_service.py` | Core + Archival memory |
| `create_claude_scope` | `claude_scope.py` | Scope with file ops |

### Primitives

| Primitive | Purpose |
|-----------|---------|
| `Consensus` | Voting (MAJORITY, UNANIMOUS, THRESHOLD) |
| `Aggregator` | Combine results (MERGE, CONCAT, BEST) |
| `HandoffState` | Structured agent handoff |
| `build_premise` | Structured premise builder |
| `gather_fail_fast` | TaskGroup-based parallel execution |

## Full API Spec

See: `API_SPEC.md` in this skill directory

## Usage Example

```python
from scripts.agentica_patterns.patterns import Swarm, Jury
from scripts.agentica_patterns.primitives import ConsensusMode
from scripts.agentica_patterns.coordination import CoordinationDB
from scripts.agentica_patterns.tracked_agent import tracked_spawn

# Create tracking database
db = CoordinationDB(session_id="my-session")

# Swarm with tracking
swarm = Swarm(
    perspectives=["Security expert", "Performance expert"],
    db=db
)
result = await swarm.execute("Review this code")

# Jury with consensus
jury = Jury(
    num_jurors=3,
    consensus_mode=ConsensusMode.MAJORITY,
    premise="You evaluate code quality",
    db=db
)
verdict = await jury.decide(bool, "Is this code production ready?")
```

## Location

API spec: `.claude/skills/agentica-infrastructure/API_SPEC.md`
Source: `scripts/agentica_patterns/`

# Moment 1: Orchestration Begins

**Date**: 2025-12-30
**Context**: Main session orchestrating while parallel instances work

---

## Where We Are

Three active workstreams:

| Instance | Focus | Status |
|----------|-------|--------|
| **This session** | Orchestration, documentation | Starting |
| **Instance 2** | Math functions (SciPy, mpmath, NumPy) | In progress |
| **Instance 3** | Erotetic flywheel refinement | In progress |

## Two Big Blocks Remaining

### Block A: Pattern Composition & Workflows

**What exists:**
- 13 patterns designed, 11 implemented (152 tests)
- Algebraic composition notation: `A;B` (seq), `A|B` (parallel), `A(B)` (nesting)
- Pattern selection guide in `.claude/rules/agent-orchestration.md`

**What's missing:**
- 6 Specialists not implemented (Kraken = refactoring, plus Finder, Oracle, Librarian, Sentinel, Hydra)
- No runtime pattern composition (currently manual selection)
- Workflow orchestration layer (brownfield analysis, hydra multi-branch)

**Composition algebra available:**
```
A ; B    → Sequential (always valid)
A | B    → Parallel (only if no dependencies)
A(B)     → Nesting (Pattern A contains B internally)
A + B    → Choice/routing (condition-dependent)
A*       → Iteration (with termination condition)
```

**Example compositions:**
- Hierarchical + Swarm: Coordinator spawns swarms for research
- Generator/Critic + Jury: Multiple critics vote on output
- Pipeline + Circuit Breaker: Fallback agents on step failure

### Block B: Memory Activation

**What exists:**
- Full implementation: `scripts/agentica/memory_*.py`
- SQLite backend active (`.claude/cache/agentica-memory/memory.db`)
- PostgreSQL backend ready (needs docker)
- Agent scope integration: `create_agent_scope()`, `create_unified_scope()`

**What's missing:**
- Not wired into main Claude Code sessions
- No automatic memory persistence across clears
- Embedding service not activated (voyage/local)

**To activate:**
```bash
# SQLite (works now)
export AGENTICA_MEMORY_BACKEND=sqlite

# PostgreSQL (needs docker)
cd docker/ && ./start-postgres.sh
export AGENTICA_MEMORY_BACKEND=postgres
```

## Decision: What This Orchestration Session Will Do

1. **Coordinate** - Track progress of parallel instances via Moments docs
2. **Sequence** - Determine what to tackle next based on completions
3. **Document** - Build narrative that future sessions can follow
4. **Integrate** - Wire completed components together

## Active Parallel Work

### Instance 2: Math Functions
Adding to `scripts/`:
- NumPy numerical operations
- SciPy scientific computing
- mpmath arbitrary precision
- Combinatorics support

### Instance 3: Erotetic Flywheel
Refining in `.claude/hooks/`:
- TypeScript hook wiring
- Domain detection
- Multi-round question loops

## Next Decision Point

When either parallel instance completes:
1. Update this Moment doc with results
2. Decide: activate memory OR implement specialists OR integrate math skills
3. Create Moment 2 with new direction

---

## Reference: Full Stack Formula

```
Execution = Workflow(Pattern(Specialist(Auction(Model))))
```

Layers (inner to outer):
1. Model Auction - Dynamic model selection
2. Specialists (6) - Domain executors (NOT YET IMPLEMENTED)
3. Patterns (13) - Coordination strategies (11 IMPLEMENTED)
4. Workflows - Brownfield, Greenfield, PR Review, etc.
5. Branch Orchestration - Swarms of workflows

## Reference: The 6 Specialists (Kraken Library)

| Specialist | Job | Tools | Status |
|------------|-----|-------|--------|
| **Finder** | Codebase search | Read, Grep, Glob | Designed |
| **Oracle** | Reasoning, tricky bugs | Read, Grep, Web, Amp | Designed |
| **Librarian** | Library/API usage | Remote repo API | Designed |
| **Kraken** | Refactoring transformations | fastmod, code editors | Designed |
| **Sentinel** | PR review (post-commit) | Git diff, Comment API | Designed |
| **Hydra** | Multi-branch iteration | Git, Edit, Test runner | Designed |

---

*This document will be updated as orchestration proceeds. Each Moment captures a decision point and direction change.*

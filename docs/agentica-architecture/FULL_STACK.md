# Agentica Full Stack Architecture

## The Composition Formula

```
Execution = Workflow(Pattern(Specialist(Auction(Model))))
                │         │         │          │
                │         │         │          └── Which weights
                │         │         └── Who does it
                │         └── How to coordinate
                └── What to achieve
```

---

## Three Abstraction Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  WHAT          │  HOW              │  WHO                       │
│  Workflows     │  Patterns         │  Specialists               │
├────────────────┼───────────────────┼────────────────────────────┤
│  Brownfield    │  Swarm            │  Finder                    │
│  Greenfield    │  Pipeline         │  Oracle                    │
│  PR Review     │  Jury             │  Librarian                 │
│  Branch Iter   │  Hierarchical     │  Kraken                    │
│  Research      │  Generator-Critic │  Sentinel                  │
│                │  MapReduce        │  Hydra                     │
│                │  ...              │                            │
└────────────────┴───────────────────┴────────────────────────────┘

Composition: Workflow = Pattern(Specialists)
```

---

## The 13 Core Patterns

| # | Pattern | Split | Combine | One-liner |
|---|---------|-------|---------|-----------|
| 1 | **Single** | Don't | Don't | One agent does everything |
| 2 | **Pipeline** | By stage | Pass forward | Assembly line |
| 3 | **Swarm** | By perspective | Merge all | Crowd opinions |
| 4 | **Dependency Swarm** | By DAG | Topological order | Parallel with deps |
| 5 | **Hierarchical** | By subtask | Roll up | Boss delegates |
| 6 | **Jury** | Same task, N times | Vote | Committee decision |
| 7 | **Generator-Critic** | Propose vs evaluate | Loop until approved | Draft and review |
| 8 | **MapReduce** | By data chunk | Aggregate | Divide and conquer |
| 9 | **Adversarial** | By position | Judge decides | Debate |
| 10 | **Chain of Responsibility** | Don't (escalate) | First success | Try handlers |
| 11 | **Circuit Breaker** | Primary vs fallback | Switch on failure | Plan B |
| 12 | **Blackboard** | By expertise | Shared state | Whiteboard collab |
| 13 | **Event-Driven** | By subscription | React independently | Pub/sub |

**Implementation status:** 11 implemented, 2 pending (Single = trivial, Dependency Swarm = designed)

---

## The 6 Specialists

| Specialist | Job | Models | Tools |
|------------|-----|--------|-------|
| **Finder** | Codebase Search | Sonnet → Qwen3 → Haiku | Read, Grep, Glob |
| **Oracle** | Reasoning, Tricky Bugs | o3 → GPT-5.1 | Read, Grep, Web, Amp |
| **Librarian** | Library Use | Sonnet | Remote repo API |
| **Kraken** | Refactoring | Sonnet | fastmod, etc. |
| **Sentinel** | PR Review (post-commit) | Sonnet or Oracle | Git diff, Comment API |
| **Hydra** | Branch Iteration | Sonnet + test loop | Git, Edit, Test runner |

**Implementation status:** Designed, not implemented

---

## Pattern Composition Algebra

| Symbol | Operation | Meaning | Validity |
|--------|-----------|---------|----------|
| `A ; B` | Sequential | Do A, then B | Always valid |
| `A \| B` | Parallel | Do A and B concurrently | Only if no deps |
| `A(B)` | Nesting | Pattern A uses B internally | Type compatible |
| `A + B` | Choice | Route to A or B | Condition defined |
| `A*` | Iteration | Repeat A | Termination defined |

### Validity Predicate

```
CanParallel(A, B) ⟺
    ¬∃r. SharesResource(A, B, r)
  ∧ ¬NeedsOutput(B, A)
  ∧ ¬NeedsOutput(A, B)
  ∧ ¬MustPrecede(A, B)
```

---

## Workflow Examples

### Brownfield Analysis

```
codemap ; (research | tests) ; plan ; implement ; validate

Categorical:
  codemap ──┬──▶ research ──┬──▶ plan ──▶ implement ──▶ validate
            └──▶ tests ─────┘

Pattern: Dependency Swarm (parallel where possible)
```

### Hydra Multi-Branch

```
Branch orchestration = Swarm of Workflows

branch/approach-A ──┐
branch/approach-B ──┼── Parallel execution ──▶ Compare ──▶ Best
branch/approach-C ──┘

Meta-pattern: Swarm at workflow level, not agent level
```

---

## Category Theory Stack

```
NON-CONTROLLABLE (Lab Work):
  Neural Activations → Token Predictions → Token Sequence

CONTROLLABLE (Optimization Space):
  Turn States → Sessions → Outcomes

OBSERVABILITY:
  Braintrust Traces (logs all morphisms)
```

### Three Categories

| Category | Objects | Morphisms | Optimization |
|----------|---------|-----------|--------------|
| **Turn States** | State snapshots | Tool calls | Fewer calls |
| **Sessions** | Session instances | Handoffs | Fewer sessions |
| **Outcomes** | Results | Refinements | Better outcomes |

### Functors

| Functor | From → To | Meaning |
|---------|-----------|---------|
| **Tactical** | Turns → Session | How turns accumulate |
| **Strategic** | Session → Outcome | The 13 patterns |
| **Observability** | Session → Trace | Preserves what execution loses |

---

## The Full Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BRANCH ORCHESTRATION                                 │
│   branch/A ──┬── Swarm of Workflows ── Compare ── Best Branch               │
│   branch/B ──┘                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              WORKFLOWS                                       │
│   Brownfield │ Greenfield │ PR Review │ Branch Iterate │ Research           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PATTERNS (13)                                   │
│   Single │ Pipeline │ Swarm │ DepSwarm │ Hierarchical │ Jury │ Gen/Crit    │
│   MapReduce │ Adversarial │ Chain │ Circuit │ Blackboard │ Event           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SPECIALISTS (6)                                    │
│   Finder │ Oracle │ Librarian │ Kraken │ Sentinel │ Hydra                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         MODEL SELECTION (Auction)                            │
│   Task metadata → Query history → Compute bids → Winner                     │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            MORPHISMS (Tools)                                 │
│   Read → Grep → Edit → Bash → Test → Write                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           OBSERVABILITY                                      │
│   Braintrust Traces ← Log Functor ← All layers                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Patterns Considered But Skipped

| Pattern | Why Skipped |
|---------|-------------|
| **Speculative** | Creates dead code waste |
| **Gossip/Epidemic** | Multi-machine, not CLI |
| **Contract Net** | Overkill for single machine |
| **Ring/Token** | Sequential bottleneck |
| **Hub-Spoke** | Same as Hierarchical |

---

## Patterns To Add

| Pattern | Use Case | Status |
|---------|----------|--------|
| **Market/Auction** | Model selection from history | Designed |
| **Reflection** | Self-review without second agent | Maps to compound |
| **Router/Wizard** | Classify task → select pattern | Implicit in Claude |

---

## Implementation Status

| Layer | Status | Notes |
|-------|--------|-------|
| Patterns (11/13) | ✅ Implemented | 152+ tests |
| Specialists (0/6) | Designed | Need skill specs |
| Workflows | Implicit | Need formalization |
| Model Auction | Designed | Need `model_performance` table |
| Scope/Memory | ✅ Ready | Needs wiring to patterns |
| Resource Management | ✅ Implemented | RAM limits, orphan detection |
| Pattern-Aware Hooks | Planned | 60-phase plan ready |

---

## Next Steps

1. **Wire memory to patterns** - Add `create_full_scope()` usage
2. **Implement Specialists** - Start with Finder, Oracle
3. **Formalize Workflows** - Brownfield, Greenfield as compositions
4. **Model Auction** - Track performance, bid on tasks
5. **Pattern-Aware Hooks** - Execute 60-phase plan

# Obviously: What It Is (Expert Notes)

MAKE — expert review requested.

This is the compact technical rationale for how the logic stack emerged and where each formalism lives in the codebase. It is written for readers who already know MDPs, modal logic, and process algebra.

## 1) Why erotetic logic entered the system

**Observation:** the dominant failure mode was underspecification, not model capability.  
**Response:** formalize “unknowns” and turn them into clarifying questions.

**Implementation reality:** our system is **erotetic‑inspired**, not formal IEL.  
Evidence:
- Hardcoded questions: `.claude/hooks/src/shared/erotetic-questions.ts`
- Count-based termination: `.claude/hooks/src/shared/erotetic-termination.ts`
- Formal IEL compliance = 0/8 properties (see `thoughts/shared/agents/erotetic-validation.md`)

We use E(X,Q) as a practical unknowns set, not as a full entailment‑theoretic operator.

## 2) Logic stack mapping (pragmatic fusion)

We fused modal families as a compression layer, not a proof system:

```
Epistemic:   K(p) vs B(p)          → claim verification gate
Deontic:     O(a), F(a), P(a)      → tool constraints / allowed actions
Temporal:    □p, ◇p               → invariants & eventual termination
Modal:       ◇/□ as “can/must”     → soft vs hard constraints
Erotetic:    E(X,Q)                → unknowns → clarifying questions
Decision:    Q-values              → policy ranking + mitigations
```

The hybridization is explicitly **fusion + bridge principles** (see `.claude/cache/learnings/2025-12-29_2cfcb431...md`).

## 3) Decision theory implementation (skills as options)

Core insight: **skills are options** (Sutton & Barto).

```
Option o = (I, pi, beta)
I     = initiation
pi    = policy
beta  = termination
```

Mapped to v6.0 skill format:

```
I   = activation conditions
Y   = observation space (I‑state content)
U   = action space (tools + forbidden)
pi  = policy (eta |-> action)
beta= termination (success/failure)
Q   = qualitative action ranking (HIGH/MED/LOW)
```

Reference sources:
- `thoughts/shared/agents/decision-theory-research/1-foundations.md`
- `thoughts/experiments/decision-theory-skills/FRAMEWORK.md`

## 4) Category theory usage (lightweight)

Category theory is used as **composition language**:

- Pattern nesting uses functor composition: `A(B(C)) = (A . B)(C)`
  (see `docs/agentic-orchestration/pattern-algebra.md`)
- HandoffAtom models *morphisms* between states (see `scripts/agentica_patterns/handoff_atom.py`)

This is conceptual scaffolding, not a formal category‑theoretic implementation.

## 5) Pattern algebra (process algebra foundation)

Pattern algebra is a design spec synthesized from CSP/CCS/Pi‑calculus and Algebra of Programming.

Operators (sequential, parallel, choice, nesting, iteration) map to agent patterns:

```
A ; B     pipeline
A ||| B   swarm (interleave)
A [] B    choice (router)
A(B)      hierarchical nesting
A*        iteration / retry
```

Spec:
- `docs/agentic-orchestration/pattern-algebra.md` (explicitly marked aspirational)
- Validated in `docs/pattern-algebra-validation.md`

Runtime enforcement of algebraic laws is incomplete; it is a **north‑star spec**.

## 6) Task algebra (decomposition layer)

Task algebra describes **what** gets decomposed, orthogonal to pattern algebra (how it’s executed).

Core operators (CSP + workflow algebra):

```
T1 ; T2   sequence
T1 | T2   parallel
T1 + T2   choice
T1 -> T2  dependency
T1 ! T2   race
T?        optional
```

Sources:
- `thoughts/shared/agents/task-algebra-nia-oracle.md`
- `thoughts/shared/agents/task-algebra-ragie-research.md`

This is a spec, not a fully deployed runtime layer.

## 7) Why this is still epistemically sound

- Formal claims are sourced via RAGIE textbooks and are **tagged aspirational** when not implemented.
- Empirical claims are validated via tiktoken and A/B runs.
- Where logic is used as **notation**, it is documented as such.

## 8) RAGIE usage model

RAGIE is used to retrieve:
- Decision theory (LaValle, Sutton & Barto)
- Process algebra (CSP/CCS/Pi‑calculus)
- Algebra of programming (Bird & de Moor)

But the conversion workflow now **compiles** those patterns into a converter skill, so repeated RAG queries are avoided.

## 9) Status summary (implementation vs spec)

```
Erotetic:     implemented (pragmatic), not formal IEL
Decision:     implemented (v6.0 format + Q‑ranking)
Category:     conceptual (composition language)
Pattern alg:  spec + partial runtime checks
Task alg:     spec only
```

## 10) References

- `docs/agentic-orchestration/pattern-algebra.md`
- `docs/pattern-algebra-validation.md`
- `thoughts/shared/agents/task-algebra-nia-oracle.md`
- `thoughts/shared/agents/decision-theory-research/1-foundations.md`
- `thoughts/shared/agents/erotetic-validation.md`

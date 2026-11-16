# Skills System

This system supports three skill formats and a formal conversion pipeline. The goal is to reduce redundancy without losing correctness.

## Formats and when to use them

```
Prose (<800 tokens)   → keep prose
Complex (>800 tokens) → v6.0 formal
Typed params          → add when missing info matters
```

### 1) Prose skills (default)

- Path: `.claude/skills/<name>/SKILL.md`
- Best for small, dense instructions
- Lowest overhead and most human-readable

### 2) Typed skills (erotetic aware)

- YAML frontmatter `parameters` with `infer_from` regex
- Enables E(X,Q) clarification (asks only missing info)
- Deterministic extraction (~5ms)

Typed params flow:

```
Prompt → regex infer_from → UNKNOWN fields → AskUserQuestion → resolved
```

E(X,Q) engine (finite domains):

```
Typed params → z3_erotetic.py → unknown propositions
  → ordered questions (erotetic_q_ranking.py)
  → AskUserQuestion batch
```

### 3) v6.0 formal skills (decision theory + modal logic)

- Path: `.claude/skills/<name>/SKILL.v6.md`
- Structure: I, Y, U, pi, beta, invariants
- Includes Q-values and mitigations to preserve “why”

v6.0 section map:

```
I   = initiation (when to activate)
Y   = observation space (what to check)
U   = action space (allowed/forbidden)
pi  = policy (state → action)
beta= termination (when to stop)
Inv = always-true constraints
```

## Skill pipeline diagram

```
        ┌─────────────────────┐
        │ User prompt         │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │ skill-router         │
        └─────────┬───────────┘
                  │
         ┌────────┴────────┐
         │                 │
         ▼                 ▼
┌────────────────┐  ┌─────────────────────┐
│ Prose skill    │  │ v6.0 skill (formal) │
│ SKILL.md       │  │ SKILL.v6.md         │
└───────┬────────┘  └─────────┬──────────┘
        │                     │
        ▼                     ▼
  Execute steps          Execute policy
```

## Decision rule (verified)

- <800 tokens: keep prose
- >800 tokens: use v6.0

Measured examples:
- braintrust-analyze: 851 → 484 (-43.1%)
- plan-agent: 1685 → 801 (-52.5%)
- create_handoff: 2174 → 884 (-59.3%)
- commit: 448 → 643 (+43.5% worse)

## Conversion path

```
Prose skill
  → /formalize (skill-injected patterns)
  → SKILL.v6.md
  → archive SKILL.md as SKILL.prose.md
```

## Conversion strategies (tested)

```
RAG-backed (4 textbooks)  → formal + citations, verbose
Skill-injected (/formalize) → formal + verification, compact
Template-only             → compact, less rigorous
```

Empirical result: skill-injected matches RAG formalism at 55-73% fewer tokens for the same skill.

## Validation and A/B protocol

```
Skill A (prose)  → Agent A → Output A
Skill B (v6.0)   → Agent B → Output B

Compare: commands, data retrieved, conclusions
```

Execution equivalence has been verified for:
- braintrust-analyze
- plan-agent
- create_handoff
- math/complex-analysis/residues

## Runtime selection rule

One-time migration decides format:

```
If SKILL.v6.md exists → load it
Else → load SKILL.md
```

No runtime token counting. The 800-token cutoff is used during migration.

## Erotetic systems (two scopes)

- **Skill clarification**: E(X,Q) over typed parameters, used to ask missing questions before execution.
- **Math logic**: `scripts/z3_erotetic.py` uses SAT/constraint checks for formal proofs.

## Tooling

- Converter skill: `.claude/skills/formalize/SKILL.md`
- Validator: `scripts/validate_skill_v6.py`
- Flywheel: `scripts/skill_flywheel.py`
- Skill upgrader (legacy): `.claude/skills/skill-upgrader/SKILL.md` (to be updated to /formalize)

Related docs:
- `docs/typed-skill-erotetic-system.md`
- `docs/continuous-learning-flywheel.md`

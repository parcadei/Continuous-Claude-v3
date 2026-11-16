# Obviously: What It Is (Layman)

This is the short, non-math explanation of why we built the system this way and how the “logic stack” ended up in the repo.

## Why any logic at all?

We started with one simple goal: reduce wasted tokens without losing correctness. Prose works for small skills, but it repeats the same ideas in many different words. Logic lets us say the same thing with less repetition.

Think of it like a checklist turned into a compact language:

```
"Always read the file before editing"
→  □ read_fully(file)    # "always"
```

We are not trying to build a theorem prover. We are trying to keep the *meaning* while reducing the *redundancy*.

## How we arrived at erotetic logic (question logic)

We noticed that most failed tasks weren’t because the model was “bad,” but because the prompt was missing key details.

Example:
```
"Deploy my app"
```

Missing questions:
- Which hosting provider?
- What framework?
- Any database?

Erotetic logic is just a formal name for “ask the questions you need before acting.” In the codebase this shows up as E(X,Q) = the set of unknowns.

```
Known facts (X) → Unknowns (Q) → Ask user → Proceed
```

## How we combined multiple logics (in plain English)

Each logic answers a different kind of question:

```
Epistemic:   What do we KNOW?          (K vs B)
Deontic:     What is allowed/forbidden? (P/O/F)
Temporal:    What must always happen?   (□ / ◇)
Modal:       What is possible/required? (can / must)
Decision:    What should we DO next?    (Q-values)
```

We didn’t “implement” them as full math. We used their *vocabulary* to compress meaning.

## Decision theory: the action map

Decision theory became the way we describe how a skill actually runs.

We use the “Options” idea:

```
I     = when the skill can start
pi    = what steps to take
beta  = when the skill stops
```

That became the v6.0 skill format.

## Category theory (lightweight use)

Category theory is a language for “things and arrows.” We use it to talk about *composition*:

```
Task A → Task B → Task C
```

This helps us reason about how patterns chain without rewriting everything each time. We use it as a *conceptual map*, not a full formal implementation. It shows up mainly in pattern composition and handoff structure.

## Pattern algebra (how agent patterns compose)

Pattern algebra tells us how agent patterns can combine safely:

```
A ; B    (sequence)
A || B   (parallel)
A + B    (choice)
A(B)     (nesting)
A*       (repeat)
```

This is the “grammar” for multi‑agent workflows. The math is documented, but the runtime enforcement is still partial.

## Task algebra (how work decomposes)

Task algebra says how big tasks turn into small tasks:

```
T1 ; T2     # do T1 then T2
T1 | T2     # do in parallel
T1 -> T2    # T2 depends on T1
T1 ! T2     # race, take first
T?          # optional task
```

This is research‑level right now; it’s a design spec, not a full runtime.

## Where RAGIE fits

RAGIE (R-A-G-I-E) is our document system that stores books. We used it to pull textbook definitions and make sure we weren’t inventing math.

But the key insight was: once we learned the patterns, we can compile them into a reusable skill. That avoids repeated RAG calls.

## The big picture (flow)

```
Token efficiency problem
    ↓
Erotetic questions (ask only what's missing)
    ↓
Decision theory for execution (I, pi, beta)
    ↓
Pattern algebra for agent workflows
    ↓
Task algebra for decomposition
```

## Why this is a net‑positive exploration

- It reduces redundancy for complex skills (43–59% token reduction measured).
- It keeps the “why” of rules (mitigations + Q‑values).
- It supports iterative improvement (flywheel learning).
- It keeps the system honest: claims are verified, not just believed.

If you only remember one sentence: **we compress the language of instructions while preserving the reasons that make them correct.**

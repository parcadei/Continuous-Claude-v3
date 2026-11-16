# Ideas and Hypotheses

This project is experimental by design. It prioritizes empirical evidence over elegant theory.

## Core ideas

1) Prompt compilation
- Prose → structured policy
- Less redundancy, same execution

2) Compression with fidelity
- Compression must preserve directional correctness
- Remove redundancy, not meaning

3) Epistemic correctness (K > B)
- Facts must be verified
- Claims are provisional until tested

4) Skill evolution as a flywheel
- Detect missing structure
- Convert once, persist forever
- Learn from corrections (pattern registry + confidence decay)

5) State outside the context window
- Agentica holds runtime state
- Memory + handoffs preserve continuity
- Main LLM context stays small

## Compression-fidelity spectrum

```
High prose density ───────────┬────────── High redundancy
(simple skills)                │           (complex skills)
                               │
  Keep prose                   │     Formalize (v6.0)
  (v6.0 adds overhead)         │     (v6.0 removes redundancy)
```

## Hypotheses (tested or pending)

- Complex skills are compressible; simple skills are not.
- Formal schemas outperform long prose in accuracy and speed.
- Erotetic questions reduce wasted execution.
- Agentica shifts state out of the LLM context, enabling large workflows.
- jq-in-Python reduces token overhead for data transforms without losing scope.
- Formal conversion is only worth it for skills >800 tokens.

## Disproved or refined

- Full formal pipelines (DisCoPy, full IEL) are too heavy for CLI execution.
- RAG-backed conversion is too verbose for runtime use.

## Related experiments

```
Verbose vs Modal vs Decision Theory
  → Decision theory hybrid wins on density and coverage
```

Source: `thoughts/experiments/ab-test-jsonl-backfill/COMPARISON_3WAY.md`

## Source thread

- `docs/typed-skill-erotetic-system.md`
- `docs/continuous-learning-flywheel.md`
- `thoughts/shared/handoffs/open-source-release/2025-12-31_08-47-19_formalize-skill-ab-testing.md`

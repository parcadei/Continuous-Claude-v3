# Experiments and Metrics

This section documents the empirical tests that validate the upgrade.

## A/B testing protocol

```
Skill A (prose) → Agent A → Output A
Skill B (v6.0)  → Agent B → Output B

Compare: commands, data, conclusions
```

Experiment pipeline:

```
Hypothesis → A/B spec → Run agents → tiktoken measure → Verdict
```

## Token efficiency (tiktoken verified)

| Skill              | Prose | v6.0 | Change  | Result |
|-------------------|-------|------|---------|--------|
| braintrust-analyze| 851   | 484  | -43.1%  | Equivalent output |
| plan-agent        | 1685  | 801  | -52.5%  | Equivalent output |
| create_handoff    | 2174  | 884  | -59.3%  | Equivalent output |
| commit            | 448   | 643  | +43.5%  | Equivalent output, worse tokens |

Decision rule:
- <800 tokens → keep prose
- >800 tokens → convert to v6.0

## RAG vs skill-injected conversion

```
RAG-backed:      Formal + citations + long explanations
Skill-injected:  Formal + compact verification (no citations)
Template:        Plain English only
```

Outcome:
- Skill-injected matches RAG quality at 55-73% fewer tokens.

## Decision theory skill comparison (3-way)

From `thoughts/experiments/ab-test-jsonl-backfill/COMPARISON_3WAY.md`:
- Verbose prose → most complete but highest tokens
- Modal logic → better risks/effort, lower tokens
- Decision theory hybrid → best density/coverage tradeoff

## JSONL backfill experiment

Source: `thoughts/experiments/ab-test-jsonl-backfill/*`

Key findings:
- Claude JSONL schema differs from Braintrust spans
- Content hash consistency is critical for dedupe
- Decision-theory plan yielded most actionable steps

## jq-in-Python transform test

```
Python transform: 125 tokens
jq transform:     53 tokens
Reduction:        57.6%
```

Key conclusion: jq in Python keeps state while reducing token overhead.

## Flywheel implementation metrics

- 40 atomic tasks across 3 phases
- 98 tests written before implementation (TDD)
- Double verification (structural + semantic)
- Confidence decay and pattern registry added

## Memory system validation

From `thoughts/shared/handoffs/open-source-release/2025-12-31_08-31-22_memory-system-implementation-complete.md`:
- Temporal memory: TEL/LTL inertia rules
- 197 tests across temporal memory and LLMSpanMemory
- E(X,Q) ranking integrated for open questions

## Operational learnings (cache-derived)

```
Read plan first → implement exact code
Avoid TaskOutput → keep context clean
Summaries should state truncation explicitly
```

Sources: `.claude/cache/learnings/*.md`

## Temporal memory implementation metrics

- 22 atomic phases
- 197 tests
- TEL inertia rules + ranked summaries + handoff protocol

## Agentica integration metrics

- Working proxy + server pipeline
- 12 orchestration patterns validated
- Rerouting LLM calls through Claude CLI eliminated extra LLM cost

## Token burn analysis (hook overhead)

Source: `.claude/cache/agents/braintrust-analyst/token-burn-analysis.md`

Findings:
- SessionStart and UserPromptSubmit hooks dominate token overhead
- Agent spawning frequency is the second largest contributor

## Sources

- `docs/continuous-learning-flywheel.md`
- `docs/typed-skill-erotetic-system.md`
- `thoughts/shared/handoffs/open-source-release/2025-12-30_19-45-14_flywheel-implementation-complete.md`
- `thoughts/shared/handoffs/open-source-release/2025-12-31_08-31-22_memory-system-implementation-complete.md`
- `docs/AGENTICA_INTEGRATION_JOURNEY.md`

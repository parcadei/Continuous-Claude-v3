# LLM Tuning Patterns

Evidence-based patterns for configuring LLM parameters, based on APOLLO and Godel-Prover research.

## Pattern

Different tasks require different LLM configurations. Use these evidence-based settings.

## Theorem Proving / Formal Reasoning

Based on APOLLO parity analysis:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| max_tokens | 4096 | Proofs need space for chain-of-thought |
| temperature | 0.6 | Higher creativity for tactic exploration |
| top_p | 0.95 | Allow diverse proof paths |

### Proof Plan Prompt

Always request a proof plan before tactics:

```
Given the theorem to prove:
[theorem statement]

First, write a high-level proof plan explaining your approach.
Then, suggest Lean 4 tactics to implement each step.
```

The proof plan (chain-of-thought) significantly improves tactic quality.

### Parallel Sampling

For hard proofs, use parallel sampling:
- Generate N=8-32 candidate proof attempts
- Use best-of-N selection
- Each sample at temperature 0.6-0.8

## Code Generation

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| max_tokens | 2048 | Sufficient for most functions |
| temperature | 0.2-0.4 | Prefer deterministic output |

## Creative / Exploration Tasks

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| max_tokens | 4096 | Space for exploration |
| temperature | 0.8-1.0 | Maximum creativity |

## Anti-Patterns

- **Too low tokens for proofs**: 512 tokens truncates chain-of-thought
- **Too low temperature for proofs**: 0.2 misses creative tactic paths
- **No proof plan**: Jumping to tactics without planning reduces success rate

## Source Sessions

- This session: APOLLO parity - increased max_tokens 512->4096, temp 0.2->0.6
- This session: Added proof plan prompt for chain-of-thought before tactics

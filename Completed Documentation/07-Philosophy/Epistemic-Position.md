# Epistemic Position

## Core stance

- Prefer K (knowledge) over B (belief).
- Every claim must be testable by evidence: tests, traces, or documents.
- If a claim is not verified, label it as a hypothesis.

## Claim verification pipeline

```
Claim → Test/Trace → Verify → Record
```

Verification ladder:

```
B(p): believed  (hypothesis)
K(p): verified  (tests, traces, tiktoken)
K*(p): validated in production (user-visible outcomes)
```

## K vs B diagram

```
K(p): p is known and verified
B(p): p is believed but unverified

System rule: Prefer K, reject B unless labeled as hypothesis
```

## Why this matters for prompts

Compression without verification creates brittle policies.
Formal logic must preserve the reason a rule exists, not just the rule.

Example:
- Bad: Q(partial_read) = -inf
- Better: Q(partial_read) = -inf | why: missing context | mitigation: read fully

## Epistemic logic in practice

- Claims about token reduction must be measured (tiktoken).
- Claims about execution equivalence must be validated via A/B tests.
- Memory systems must record outcomes to distinguish success vs failure.
- Documentation must separate "observed" vs "inferred".

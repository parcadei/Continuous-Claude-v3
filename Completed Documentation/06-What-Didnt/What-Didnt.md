# What Did Not Work

## Overly heavy formalism

- Full formal pipelines (DisCoPy, full IEL) are too heavy for CLI usage.
- RAG-backed conversions are too verbose for runtime use.

## Universal v6.0 conversion

- v6.0 format adds fixed overhead (~200-400 tokens).
- For small skills (<800 tokens), v6.0 is worse (example: commit skill).

## Tradeoffs and failures

- Formal output can be less natural language unless rendered.
- Runtime RAG adds latency and cost without improving execution.
- Some early A/B tests failed due to vague agent specs.
- Full erotetic termination (E(X,Q)=∅) conflicts with UX hard caps.
- Hook overhead can inflate tokens if too many skills inject.
- Token burn spikes when SessionStart/UserPromptSubmit hooks over-inject content.

## Lessons learned

- Compression only helps when redundancy exceeds schema overhead.
- Inject explicit specs when delegating tasks to agents.
- Keep verification lightweight but mandatory.
- Avoid repeated RAG calls when the same logic can be compiled into a skill.
- Validate hook budgets with Braintrust token-burn analysis before enabling by default.

## Sources

- `thoughts/shared/handoffs/open-source-release/2025-12-31_08-47-19_formalize-skill-ab-testing.md`
- `thoughts/shared/handoffs/open-source-release/2025-12-31_00-18-54_decision-theory-v6-hybrid-implementation.md`

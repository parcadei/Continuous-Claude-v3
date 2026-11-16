# Completed Documentation

This folder is the curated, up-to-date documentation set for the current codebase state. It is intentionally structured like a short technical book: fast onboarding, deep architecture, empirical results, and clear next steps.

Everything here is derived from:
- `docs/` (system and integration docs)
- `.claude/cache/` (agent outputs and artifacts)
- `thoughts/` (handoffs and plans)

## Overall System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                USER PROMPT                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Hooks & Routing                                                            │
│  - skill-router (intent → skill)                                            │
│  - erotetic-clarification (ask missing info)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Skill System                                                               │
│  - Prose skills (SKILL.md)                                                  │
│  - Typed skills (parameters + infer_from)                                   │
│  - v6.0 formal skills (decision theory + modal logic)                       │
└─────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Execution & Tooling                                                        │
│  - MCP tools / shell / repo operations                                      │
│  - Agentica agents (optional)                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Memory + Learning                                                          │
│  - LLMSpanMemory (per-span retrieval)                                       │
│  - Temporal Memory (invariants, transitions, open questions)                │
│  - Flywheel (infer → verify → persist → learn)                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

For the full end-to-end architecture, see:
- `02-Architecture/Full-Setup-Mega-Diagram.md`

## How to use this set

- Start here: `01-Quick-Start/Quick-Start.md`
- Architecture map: `02-Architecture/System-Map.md`
- Full setup diagram: `02-Architecture/Full-Setup-Mega-Diagram.md`
- Skill system details: `02-Architecture/Skills-System.md`
- Memory stack details: `02-Architecture/Memory-System.md`
- Orchestration layer: `02-Architecture/Agentic-Orchestration.md`
- Experiments and metrics: `04-Experiments/Experiments-and-Metrics.md`
- Philosophy (epistemic stance): `07-Philosophy/Epistemic-Position.md`

## Structure

- `01-Quick-Start/` - Practical runbook for getting the system running.
- `02-Architecture/` - System maps, components, flows, and interfaces.
- `03-Ideas/` - Core hypotheses and design intent.
- `04-Experiments/` - Empirical tests and metrics (token counts, A/B tests).
- `05-What-Worked/` - Confirmed wins and reliable patterns.
- `06-What-Didnt/` - Dead ends and tradeoffs.
- `07-Philosophy/` - Epistemic rules and compression-fidelity stance.
- `08-Roadmap/` - Next steps and migration plan.
- `09-Appendix/` - Glossary and source index.
- `10-Obviously/` - Layman + expert explanations of the logic stack.

## Principle

This set favors high signal and verified claims. When something is not measured, it is marked as a hypothesis. Token claims are verified with tiktoken. Execution equivalence is tested via A/B prompts where possible.

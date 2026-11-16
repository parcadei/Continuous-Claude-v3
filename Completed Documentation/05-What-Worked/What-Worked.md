# What Worked

## Skills and formalization

- v6.0 format compresses complex skills by 43-59% without changing execution.
- Typed params + erotetic questions reduce ambiguity before execution.
- Skill-injected converter yields formal notation without runtime RAG.

## Flywheel and learning

- Double verification (structural + semantic) prevents drift.
- Pattern registry + confidence decay create a true learning loop.
- Atomic tasks + TDD preserved correctness under rapid iteration.
- Hook ordering (skill-router → erotetic-clarification) prevents double-injection.
- Explicit specs in agent prompts prevent output drift.

## Memory and handoffs

- Per-LLM-span extraction preserves reasoning steps.
- Temporal memory captures invariants, transitions, and open questions.
- Handoff format is machine-parseable and human-readable.
- LLMSpanMemory per-span extraction recovered reasoning steps missed by session summaries.

## Agentica integration

- Proxy architecture works and avoids extra LLM costs.
- Task-based agent orchestration keeps main context small.
- Watcher gives runtime visibility into agent activity.
- Injecting skills into agent prompts yields deterministic A/B tests.

## Operational patterns (from cache learnings)

```
Read plan first → implement exact code → test → review → handoff
```

Why this worked:
- Reduced mis-implementations
- Kept context small
- Produced durable artifacts in `thoughts/` and `.claude/cache/`

## Flywheel loop diagram

```
Detect → Infer → Verify → Diff → Persist → Learn
```

## Sources

- `docs/continuous-learning-flywheel.md`
- `docs/llm-span-memory/README.md`
- `docs/AGENTICA_INTEGRATION_JOURNEY.md`
- `thoughts/shared/handoffs/open-source-release/2025-12-30_19-45-14_flywheel-implementation-complete.md`
- `thoughts/shared/handoffs/open-source-release/2025-12-31_08-31-22_memory-system-implementation-complete.md`

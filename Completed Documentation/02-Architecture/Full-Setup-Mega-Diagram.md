# Full Setup Mega Diagram

This is the full, end-to-end architecture diagram that connects hooks, skills, orchestration, memory, and learning.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         USER PROMPT                                           │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       HOOK PIPELINE                                           │
│  SessionStart → UserPromptSubmit → skill-router → erotetic-clarification → post_tool_use     │
│                                                                                              │
│  Outputs:                                                                                     │
│  - Selected skill (rules + memory lookup)                                                     │
│  - Clarification questions (typed params / erotetic)                                          │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         SKILL LAYER                                            │
│  - Prose skills (SKILL.md)             - Typed params (YAML frontmatter)                       │
│  - v6.0 formal skills (I,Y,U,pi,beta)  - /formalize converter (decision theory + modal logic) │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     EXECUTION RUNTIME                                         │
│  Claude Code (main)                                                                          │
│   ├── Direct tools: Read / Write / Bash / MCP                                                 │
│   └── Agentica (optional): proxy → server → scoped agent runs                                 │
│                                                                                              │
│  jq-in-Python transforms reduce token overhead while keeping state in scope.                 │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       MEMORY STACK                                            │
│  LLMSpanMemory: per-span extraction + retrieval                                                │
│  Temporal Memory: invariants + current_state + transitions + open_questions                    │
│  Handoff: structured summary for continuity                                                    │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       LEARNING LOOP                                            │
│  Flywheel: infer → verify (structural + semantic) → diff → persist → learn                    │
│  Pattern registry + confidence decay + feedback capture                                       │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                                      OBSERVABILITY                                             │
│  Braintrust spans, skill decision traces, memory backfill                                      │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Notes

- Hooks are the entry points and define order of operations.
- Skill format is chosen by size: <800 tokens keep prose, >800 tokens use v6.0.
- Agentica is optional; it moves state out of context when needed.
- Memory and learning are orthogonal: memory stores, flywheel improves skills.

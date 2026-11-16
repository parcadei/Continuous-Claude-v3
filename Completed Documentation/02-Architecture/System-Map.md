# System Map

This section describes the full system architecture after the upgrade. The system is a layered pipeline: hooks → skills → tools → memory → learning.

## Full-stack architecture diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                Claude Code                               │
│                                                                          │
│  User Prompt                                                             │
│    │                                                                     │
│    ▼                                                                     │
│  Hook Pipeline                                                           │
│    - skill-router                                                        │
│    - erotetic-clarification                                               │
│    - post_tool_use_flywheel                                               │
│    │                                                                     │
│    ▼                                                                     │
│  Skill Execution                                                         │
│    - prose skills (SKILL.md)                                              │
│    - typed params (YAML frontmatter)                                     │
│    - v6.0 formal skills (decision theory + modal logic)                  │
│    │                                                                     │
│    ▼                                                                     │
│  Tooling (MCP / Bash / Read / Write)                                     │
│    │                                                                     │
│    ▼                                                                     │
│  Memory + Learning                                                       │
│    - LLMSpanMemory                                                       │
│    - Temporal Memory                                                     │
│    - Flywheel (infer → verify → persist → learn)                         │
└──────────────────────────────────────────────────────────────────────────┘
```

## Subsystems and responsibilities

### A) Hook and routing layer

```
Prompt → skill-router → erotetic-clarification → selected skill
```

- Determines which skill to load.
- If parameters are missing, asks the minimal set of questions.

Hook ordering (critical):

```
SessionStart
  → UserPromptSubmit
     → skill-router
     → erotetic-clarification
     → skill-activation-prompt
  → PostToolUse (flywheel / tracing)
```

If `skill-router` runs after `erotetic-clarification`, skills can be double-injected or asked without context.

### B) Skill execution layer

```
Prose / Typed / v6.0 → execution policy → tool calls
```

- Prose: best for small, dense instructions.
- Typed: adds E(X,Q) clarification.
- v6.0: formal decision policy for complex workflows.

Skill discovery path:

```
skill-rules.json
  ├── keyword matches
  ├── intent regexes
  └── memory lookup (if enabled)
        └── best-match skill
```

### C) Tooling and MCP layer

```
Skill steps → MCP tools / Bash / Read / Write → outputs
```

- Tools are orchestrated by Claude Code or Agentica.
- jq-in-Python can reduce token overhead for data transforms.

Tool orchestration variants:

```
Claude Code
  ├── Direct tools (Read/Write/Bash)
  └── MCP wrappers (perplexity, nia, braintrust)
```

### D) Memory and learning layer

```
Tool outputs → LLMSpanMemory + Temporal Memory → summaries + handoffs
```

- LLMSpanMemory preserves per-span reasoning.
- Temporal memory captures invariants, transitions, and open questions.
- Flywheel upgrades skills over time.

Memory flow:

```
Span events → LLMSpanMemory → retrieval
Turn facts  → Temporal Memory → summaries + handoffs
Corrections → Flywheel → skill upgrades
```

## Major architectural changes introduced

- v6.0 formal skill format (decision theory + modal logic)
- Skill conversion flywheel with verification
- Temporal handoff format for agent-to-agent continuity
- Agentica integration to move state out of context
- Formalization via /formalize to compress large skills
- jq-in-Python for token-efficient data transforms

## Related diagrams

- `Full-Setup-Mega-Diagram.md` (full stack view)

## Related docs

- `Skills-System.md`
- `Memory-System.md`
- `Agentica-Integration.md`
- `Agentic-Orchestration.md`

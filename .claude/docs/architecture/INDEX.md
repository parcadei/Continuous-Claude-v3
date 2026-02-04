# Continuous Claude Architecture

## Quick Start

| Task Type | Go To |
|-----------|-------|
| Understand codebase | [Decision Trees → Research](DECISION-TREES.md#research) |
| Implement feature | [Decision Trees → Implementation](DECISION-TREES.md#implementation) |
| Debug/Fix issue | [Decision Trees → Debugging](DECISION-TREES.md#debugging) |
| Store/recall memory | [Memory Subsystem](subsystems/memory.md) |
| Manage goals | [ROADMAP Subsystem](subsystems/roadmap.md) |
| Use agents | [Agent Picker](quick-ref/agent-picker.md) |
| Find a hook | [Hook Catalog](quick-ref/hook-catalog.md) |

## System at a Glance

| Subsystem | Purpose | Entry Point |
|-----------|---------|-------------|
| Memory | Persistent learnings across sessions | `recall_learnings.py` |
| Hooks | Intercept & modify Claude behavior | `.claude/hooks/` |
| Agents | Specialized task delegation | Task tool |
| PageIndex | Document navigation & search | `pageindex_cli.py` |
| Workflows | Multi-step orchestration | `/ralph`, `/maestro` |

## Five Pillars

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLAUDE SESSION                                     │
│     User Prompt → Hooks → Tools/Agents → Output → Hooks                      │
└─────────────────────────────────────────────────────────────────────────────┘
        │           │           │           │           │
        ▼           ▼           ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  MEMORY  │ │  HOOKS   │ │  AGENTS  │ │ PAGEINDEX│ │ WORKFLOWS│
│PostgreSQL│ │100+ TS/JS│ │18+ types │ │Doc search│ │Ralph/    │
│+pgvector │ │intercepts│ │Task tool │ │LLM reason│ │Maestro   │
└──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘
```

## Cross-References

- **All hooks:** [Hook Catalog](quick-ref/hook-catalog.md)
- **All agents:** [Agent Picker](quick-ref/agent-picker.md)
- **All commands:** [Command Reference](quick-ref/command-ref.md)
- **System diagrams:** [System Overview](SYSTEM-OVERVIEW.md)

## Deep Dives

**Quick Reference (local):**
- [Memory System](subsystems/memory.md) - PostgreSQL, pgvector, embeddings
- [PageIndex System](subsystems/pageindex.md) - Tree-based doc search, LLM reasoning
- [ROADMAP System](subsystems/roadmap.md) - Goal tracking, 4 hooks, /roadmap skill
- [Hook System](subsystems/hooks.md) - Lifecycle, blocking, patterns
- [Agent Orchestration](subsystems/agents.md) - When to use which agent
- [Workflows](subsystems/workflows.md) - Ralph, Maestro, compound workflows

**Comprehensive Documentation (continuous-claude/docs/):**
- [ARCHITECTURE.md](file:///C:/Users/david.hayes/continuous-claude/docs/ARCHITECTURE.md) - Full system architecture with TLDR analysis
- [memory-architecture.md](file:///C:/Users/david.hayes/continuous-claude/docs/memory-architecture.md) - Complete memory system with Mermaid diagrams
- [hooks/README.md](file:///C:/Users/david.hayes/continuous-claude/docs/hooks/README.md) - Full hook reference (718 lines)
- [agents/README.md](file:///C:/Users/david.hayes/continuous-claude/docs/agents/README.md) - Agent selection guide (750 lines)

**User Guides:**
- [CONTINUOUS-CLAUDE-GUIDE.md](../../CONTINUOUS-CLAUDE-GUIDE.md) - User guide with essential commands
- [CONTINUOUS-CLAUDE-CHEATSHEET.md](../../CONTINUOUS-CLAUDE-CHEATSHEET.md) - Windows cheat sheet

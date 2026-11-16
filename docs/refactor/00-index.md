# Claude Continuity Kit v3 Refactor Specification

**Version:** 3.0
**Date:** 2026-01-01
**Status:** Approved for Implementation

---

## Executive Summary

This refactor removes the Agentica SDK dependency and replaces it with headless Claude CLI agents via `claude -p`. The 11 multi-agent patterns are preserved but spawn via Bash instead of Python REPL. CoordinationDB migrates to PostgreSQL with Redis for hot polling (SpawnQueue). A shared Docker sandbox enables cross-agent computation. The TUI provides real-time monitoring with a clean, Palantir-inspired design.

> **Architecture Decisions**: See [00-architecture-decisions.md](./00-architecture-decisions.md) for all foundational decisions that inform these modules.

---

## Module Index

| Module | File | Description |
|--------|------|-------------|
| **Agent Orchestration** | [05-agent-orchestration.md](./05-agent-orchestration.md) | `claude -p` spawning, nesting limits, config inheritance |
| **Concurrency & Coordination** | [06-concurrency-coordination.md](./06-concurrency-coordination.md) | PostgreSQL coordination, dynamic strategies, blackboard polling |
| **Z3 & Erotetic Logic** | [07-z3-erotetic.md](./07-z3-erotetic.md) | Dynamic propositions, personalization, LLM pre-pass |
| **Sentinel Pattern** | [08-sentinel-pattern.md](./08-sentinel-pattern.md) | First-class sentinel for quality monitoring |
| **TUI & Monitoring** | [09-tui-monitoring.md](./09-tui-monitoring.md) | Dashboard design, health checks, JSONL streaming |
| **Hooks & Skills** | [10-hooks-skills.md](./10-hooks-skills.md) | Auto-discovery, inheritance, skill-rules.json |
| **Setup Wizard** | [11-setup-wizard.md](./11-setup-wizard.md) | Docker stack, JSONL backfill, personalization |
| **Error Recovery** | [12-error-recovery.md](./12-error-recovery.md) | Crash handling, temporal memory resume |
| **MCP & Offline Mode** | [13-mcp-offline.md](./13-mcp-offline.md) | MCP inheritance, graceful degradation |
| **Shared Sandbox** | [14-sandbox.md](./14-sandbox.md) | Docker execution, Redis/PostgreSQL state |
| **Security Model** | [15-security.md](./15-security.md) | Agent sandboxing, access controls |
| **Testing Strategy** | [16-testing.md](./16-testing.md) | Unit, integration, E2E testing |
| **Upgrade Path** | [17-upgrade-path.md](./17-upgrade-path.md) | v2 → v3 migration guide |
| **Agent Routing** | [05-agent-orchestration.md#agent-routing-deterministic](./05-agent-orchestration.md#agent-routing-deterministic) | Deterministic trigger->agent mappings for 18 agents (see [00-architecture-decisions.md](./00-architecture-decisions.md) for full roster) |
| **Codify & Skill Evolution** | [19-codify-skill-evolution.md](./19-codify-skill-evolution.md) | Pattern extraction, auto skill generation, lifecycle |
| **Temporal Archival** | [20-temporal-archival.md](./20-temporal-archival.md) | 90-day archival, hot/cold tiers, LLM summarization |
| **Testing Strategy** | [21-testing-strategy.md](./21-testing-strategy.md) | Unit, E2E, property-based, integration tests |
| **Migration Rollback** | [22-migration-rollback.md](./22-migration-rollback.md) | Snapshot + restore strategy |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Main Orchestrator (Claude)                          │
│  - Pattern detection & selection                                            │
│  - Agent spawning via `claude -p`                                           │
│  - Result aggregation & synthesis                                           │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
            ▼                       ▼                       ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│ Headless Agent 1  │   │ Headless Agent 2  │   │ Headless Agent 3  │
│ (claude -p)       │   │ (claude -p)       │   │ (claude -p)       │
│ DEPTH_LEVEL=1     │   │ DEPTH_LEVEL=1     │   │ DEPTH_LEVEL=1     │
└─────────┬─────────┘   └─────────┬─────────┘   └─────────┬─────────┘
          │                       │                       │
          └───────────────────────┼───────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Docker Stack                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   PostgreSQL    │  │     Redis       │  │ Sandbox Runner  │             │
│  │  + pgvector     │  │   (hot cache)   │  │   (isolated)    │             │
│  │                 │  │                 │  │                 │             │
│  │ - Coordination  │  │ - Sandbox state │  │ - Code execution│             │
│  │ - Temporal mem  │  │ - Blackboard    │  │ - Shared compute│             │
│  │ - Embeddings    │  │ - Health cache  │  │                 │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Monitor TUI                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Health    │  │   Swarms    │  │  Sentinel   │  │   Agents    │        │
│  │  Dashboard  │  │   Status    │  │   Checks    │  │   Detail    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘        │
│  Data: JSONL (live events) + PostgreSQL (status)                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Decisions Summary

| Area | Decision | Rationale |
|------|----------|-----------|
| Agent spawning | `claude -p` via Bash | True process isolation, full CLI control |
| Concurrency | Dynamic per-pattern | Swarm=append-only, Jury=optimistic locking |
| Nesting | Max 3 layers, hard reject | Prevent runaway resource consumption |
| Z3 | Keep, dynamic propositions | Formal guarantees + personalization |
| Sentinel | First-class pattern | Explicit quality monitoring, not implicit |
| Polling | Write-path only | Reduce latency for read operations |
| TUI data | JSONL + PostgreSQL hybrid | Live events + durable status |
| Hooks | Auto-discover + override | Convention over configuration |
| Resume | Fresh start + temporal summary | Avoid context overflow |
| Sandbox | Docker + Redis + PostgreSQL | Isolation + speed + durability |
| Agent routing | Deterministic trigger->agent | 18 specialized agents (5 Leads + 13 Workers) with keyword-based routing |
| Session isolation | MAX_AGENTS_PER_SESSION=4 | Prevents cross-session resource contention |
| Codify | Archival Memory + auto-generate | Sub-agents write raw, orchestrator aggregates and auto-approves |
| Testing | All 4 types | Unit → E2E → Property-based → Integration |
| Rollback | Snapshot + restore | Full backup before migration, restore on failure |

---

## Dependencies Between Modules

```
Setup Wizard ──────────────────────────────────────────────┐
     │                                                     │
     ▼                                                     │
Docker Stack (PostgreSQL, Redis, Sandbox)                  │
     │                                                     │
     ├──▶ Concurrency & Coordination ◀─────────────────────┤
     │         │                                           │
     │         ▼                                           │
     ├──▶ Agent Orchestration ◀────────────────────────────┤
     │         │                                           │
     │         ├──▶ Sentinel Pattern                       │
     │         │                                           │
     │         ├──▶ Z3 & Erotetic Logic                    │
     │         │                                           │
     │         └──▶ Hooks & Skills                         │
     │                                                     │
     ├──▶ Shared Sandbox                                   │
     │                                                     │
     ├──▶ TUI & Monitoring ◀───────────────────────────────┤
     │                                                     │
     ├──▶ Error Recovery                                   │
     │                                                     │
     └──▶ MCP & Offline Mode                               │
                                                           │
Security Model ◀───────────────────────────────────────────┘
     │
     ▼
Testing Strategy
     │
     ▼
Upgrade Path (depends on all above)
```

---

## Files to Delete (from existing refactor plan)

See [04-refactor-plan.md](./04-refactor-plan.md) for complete deletion list (~25 files).

Key deletions:
- `scripts/agentica_patterns/native_repl/` - entire directory
- `scripts/agentica_patterns/baseline/` - entire directory
- `scripts/agentica_patterns/websocket_multiplex.py`
- `.claude/skills/agentica-sdk/`, `agentica-spawn/`, `agentica-server/`, `agentica-infrastructure/`

---

## Implementation Order

1. **Docker Stack** - PostgreSQL, Redis, Sandbox runner
2. **Concurrency & Coordination** - PostgreSQL migration
3. **Agent Orchestration** - `claude -p` wrapper
4. **Hooks & Skills** - Auto-discovery
5. **Sentinel Pattern** - First-class implementation
6. **Z3 & Erotetic** - Dynamic propositions
7. **Shared Sandbox** - Cross-agent computation
8. **TUI & Monitoring** - Dashboard upgrade
9. **Error Recovery** - Temporal memory integration
10. **MCP & Offline** - Graceful degradation
11. **Security** - Sandboxing verification
12. **Testing** - Full test suite
13. **Setup Wizard** - Personalized onboarding
14. **Upgrade Path** - v2 → v3 migration
15. **Agent Routing** - Deterministic trigger->agent mappings (see 05-agent-orchestration.md)
16. **Codify & Skill Evolution** - Pattern extraction, auto generation
17. **Testing Suite** - Full test coverage
18. **Migration & Rollback** - v2 → v3 migration with backup

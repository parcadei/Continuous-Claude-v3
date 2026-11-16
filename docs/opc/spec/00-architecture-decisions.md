# V3 Architecture Decisions

**Source**: Interview session 2026-01-01 (45+ questions resolved)
**Plan**: `/Users/cosimo/.claude/plans/concurrent-juggling-cook.md`

This document frontloads all interview decisions that inform the refactor modules. All other docs in this folder MUST align with these decisions.

---

## Core Philosophy

> **"The goal isn't to do work inside the chat window; it's to orchestrate work."**

- **No small changes** - Everything goes through workflow stages
- **No complexity detection** - 22K context cost is acceptable for structured orchestration
- **Erotetic gates BLOCK** - User must resolve unknowns before proceeding
- **Workflows compose** - /onboard → /plan → /implement → /review

---

## Agent Roster (18 Agents)

| Domain | Agents |
|--------|--------|
| Implement | Kraken, Spark |
| Document | Scribe |
| Debug | Sleuth, Aegis, Profiler |
| Validate | Arbiter, Atlas |
| Research | Oracle, Scout, Pathfinder |
| Plan | Architect, Phoenix |
| Review | Sentinel, Warden |
| Session | Chronicler |
| Deploy | Herald |
| Orchestrate | Maestro |

### Leads vs Workers

**Lead agents (can spawn):** Kraken, Architect, Phoenix, Herald, Maestro
**Workers (leaf nodes):** All others - cannot spawn agents

### Routing Table

| Activity | Trigger Words | Agent |
|----------|---------------|-------|
| implement, large | implement, build, create, develop | Kraken |
| implement, small | fix, patch, tweak | Spark |
| document | document, write docs, explain | Scribe |
| debug | debug, investigate, trace | Sleuth |
| security | security, vulnerability, audit | Aegis |
| performance | performance, optimize, profile | Profiler |
| test, unit | unit test, test function | Arbiter |
| test, e2e | e2e test, integration test | Atlas |
| research, external | research, look up, find docs | Oracle |
| research, internal | explore codebase, find code | Scout |
| research, repo | analyze repo, understand project | Pathfinder |
| plan, feature | plan feature, design, architect | Architect |
| plan, refactor | plan refactor, migrate, restructure | Phoenix |
| review, build | review plan, check design | Sentinel |
| review, change | review refactor, validate migration | Warden |
| session | session analysis, what happened | Chronicler |
| deploy | deploy, release, publish | Herald |

---

## Spawn Coordination

### SpawnQueue (formerly "spawn blackboard")

**Architecture**: Redis (hot polling, 100ms) + PostgreSQL (durability/audit)

**NOT to be confused with**: Pattern Blackboard (shared state during task execution)

### Session Isolation

```
MAX_AGENTS_PER_SESSION = 4
```

Each session gets an isolated agent pool. No cross-session resource contention.

### Depth Limits

| Depth | Who Can Spawn | Rule |
|-------|---------------|------|
| 0 | Main session | Spawns leads or workers |
| 1 | Leads | Can spawn workers |
| 2 | Leads | Can spawn workers (last level for leads) |
| 3+ | Nobody | Hard reject |

### SpawnCoordinator Logic

```python
class SpawnCoordinator:
    def request_spawn(self, requester: str, target: str, depth: int) -> bool:
        if depth >= 3: return False  # Hard limit
        if is_lead(target) and depth >= 2: return False  # Leads can't spawn at depth 2+
        if not resources_available(): return False  # Pool exhausted
        return True
```

---

## Routing Engine

**Approach**: Keyword matching + LLM classification fallback

1. **First**: Try keyword match (instant, covers 80% of cases)
2. **Fallback**: LLM classifies (handles edge cases, ~500ms)
3. **NOT erotetic**: Erotetic is for parameter extraction, not routing

---

## Erotetic Logic

### Gates BLOCK (Not Continue)

When E(X,Q) ≠ ∅ (unknowns exist):
```typescript
return { result: 'block', message: 'Resolve unknowns before proceeding' }
```

NOT:
```typescript
return { result: 'continue', message: 'Warning: unknowns exist' }  // WRONG
```

### Question Batching

- Max 4 questions per round (AskUserQuestion tool limit)
- After user answers, recompute E(X,Q)
- Repeat until E(X,Q) = ∅

### Z3 Hybrid

| Component | Role | Timeout |
|-----------|------|---------|
| Z3 | Composition validation (goal consistency) | 2 seconds |
| Sentinel | Parameter extraction (tool/resource availability) | N/A |

If Z3 times out, fall back to sentinel detection.

---

## Handoff Format

### Extended HandoffState

```python
@dataclass
class HandoffState:
    context: str
    next_instruction: str
    artifacts: dict[str, Any]
    metadata: dict[str, Any]
    # NEW FIELDS:
    resolved: list[str]        # Decided propositions
    unknowns: list[str]        # E(X,Q) open questions
    decision_matrix: list[Decision]  # Options with risk/value
    diff: dict[str, str]       # Files created/modified
    spawn_next: str | None     # Agent to hand off to
```

### YAML Frontmatter

```yaml
resolved:
  - framework: FastAPI
  - database: PostgreSQL
unknowns:
  - auth_method
  - caching_strategy
decision_matrix:
  - action: add_caching
    options:
      redis: {risk: 0.1, value: 0.9}
      memory: {risk: 0.05, value: 0.6}
diff:
  created: [src/api/routes.py]
  modified: [pyproject.toml]
spawn_next: sentinel
```

---

## Workflows

### User-Facing Workflows

| Command | Pattern | Agents |
|---------|---------|--------|
| /onboard | Pipeline | Scout → Scribe |
| /plan | GeneratorCritic | Architect or Phoenix |
| /implement | Hierarchical | Kraken |
| /review | Jury | Sentinel or Warden |

### Meta-Workflows

- `/build` = onboard → plan → implement (with erotetic gates between phases)
- Default: Auto-proceed if E(X,Q) = ∅
- Config: `REQUIRE_GATE_APPROVAL=true` for explicit "Continue?" prompt

### Interactive Features

- Post-onboard prompt: "Would you like a system walkthrough?"
- `/explain` command for Feynman-style guide
- Natural language recommendation (Claude handles inline)

---

## Hook Security

### Invocation Pattern

1. **JSON over stdin** - Never interpolate into command line
2. **Subprocess with array** - Use `execFile` with argument array, not shell string

```typescript
// CORRECT
execFile('python', [script], { input: JSON.stringify(data) })

// WRONG - command injection risk
execSync(`python ${script} --props '${JSON.stringify(data)}'`)
```

---

## Poll Cleanup (Blackboard)

### Status Tracking

1. Track read counts in `read_by` JSONB array
2. Mark resolved when all target agents have read
3. Archive to `blackboard_archive` table
4. Delete from active blackboard

---

## Claude Code Isolation

### Development Setup

```json
// .claude/settings.local.json (gitignored, project-only)
{
  "disableAllHooks": true,
  "permissions": {
    "deny": ["Bash(git push:*)", "Read(.env*)"]
  }
}
```

### Scope Hierarchy

1. Enterprise (highest precedence)
2. **Local** ← Use this for experiments
3. Project
4. User (lowest precedence)

---

## Testing Strategy

### Fresh Tests Philosophy

> All tests start from scratch for v3 architecture. Do not migrate v2 tests.

### Coverage Requirements

- Full test coverage BEFORE release
- Unit tests per agent, per component
- Integration tests for pattern execution, spawn flow
- E2E tests for full workflows: /onboard → /plan → /implement

### Workflow Tests Required

- /onboard E2E
- /plan E2E
- /implement E2E
- /review E2E

---

## Documentation Structure

### Three-Layer Erotetic Docs

1. **EROTETIC_THEORY.md** - IEL foundations, E(X,Q) notation, formal semantics
2. **EROTETIC_BLOG.md** - "Why asking questions beats guessing" narrative
3. **EROTETIC_GUIDE.md** - Practical usage with code examples

### Archive Strategy

Deprecated agents and files → `docs/archive/` (not delete)

---

## Session Identity

### Explicit Identity Rule

> Never rely on "latest" or "current" when crossing process boundaries.

- Pass `--session-id $ID` when spawning processes
- Store IDs in state files for later correlation
- Use full UUIDs, not partial matches

### Fallback Behavior

- **Production**: Fail loudly if SESSION_ID missing
- **Development**: Generate ephemeral UUID
- Switch via `CLAUDE_ENV=dev|prod`

---

## OPC vs v2

### OPC is a Fresh Repository

- NOT an upgrade path from v2
- Fresh tests, fresh docs
- Archive current codebase, build clean in new folder

### Migration Docs Scope

- `17-upgrade-path.md` applies to existing claude-continuity-kit v2 users only
- OPC users start fresh with no migration needed

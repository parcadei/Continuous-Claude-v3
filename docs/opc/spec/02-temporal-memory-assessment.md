# Temporal Memory Assessment

**Assessment Date:** 2025-01-01
**Branch:** feature/agentica-integration

---

## Architecture Overview

The Temporal Memory system is Layer 3 of a three-layer memory architecture designed for "better agent memory retention." It is a TEL (Temporal Epistemic Logic)-inspired system that tracks facts over time with turn-based indexing.

### Core Components

```
scripts/temporal_memory/
  atoms.py        # TemporalAtom - TEL operators (ALWAYS, EVENTUALLY, UNTIL, NEXT, HOLDS)
  inertia.py      # TEL inertia rules, RevisionPriority, conflict resolution
  store.py        # SQLite-backed TemporalMemoryStore
  store_pg.py     # PostgreSQL-backed TemporalMemoryStorePG (with pgvector)
  summarizer.py   # TemporalSummarizer - token-budgeted summaries
  handoff.py      # TemporalHandoffState - agent-to-agent transfer format
  cli.py          # CLI interface (record, summarize commands)
  factory.py      # Backend selection (sqlite/postgres)
  protocol.py     # Protocol definitions for backend abstraction
```

### Data Model

**temporal_facts table:**
- `session_id`, `key`, `value` - fact identity
- `turn_established`, `turn_last_changed` - temporal tracking
- `change_count` - invariant detection (0 = never changed)
- `confidence` - calibrated confidence score
- `embedding` - vector embedding (PostgreSQL only, 1024 dimensions)

**temporal_traces table:**
- Turn-by-turn snapshots of all facts
- `facts_json` - JSONB snapshot
- `erotetic_json` - E(X,Q) evocation data (open questions)

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Inertia Rule** | `holds(P, T+1) :- holds(P, T), not -holds(P, T+1)` - facts persist unless explicitly negated |
| **Invariants** | Facts where `change_count == 0` - never changed (stable anchors) |
| **Transitions** | State changes between turns, ranked by utility = importance x recency x frequency |
| **Open Questions** | Facts marked as `UNKNOWN` - unresolved decisions tracked via E(X,Q) |
| **Pending Goals** | Facts with keys starting with `goal_` that are not `achieved` |
| **Utility Scoring** | 15-turn half-life decay for recency weighting |

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| SQLite Store (store.py) | **Complete** | Full CRUD, reconnect, inertia rule |
| PostgreSQL Store (store_pg.py) | **Complete** | asyncpg, connection pooling, pgvector |
| Protocol Abstraction | **Complete** | TemporalStoreProtocol, TemporalWriterProtocol |
| Factory Pattern | **Complete** | Environment-driven backend selection |
| CLI Interface | **Complete** | record, summarize commands |
| Summarizer | **Complete** | Invariant extraction, utility ranking, token budgeting |
| Handoff Format | **Complete** | to_markdown(), parse_temporal_handoff(), load_temporal_handoff() |
| Inertia Rules | **Complete** | RevisionPriority, conflict resolution |
| TEL Atoms | **Complete** | ALWAYS, EVENTUALLY, UNTIL, NEXT, HOLDS operators |
| Vector Search | **Complete** | pgvector with 1024-dim embeddings |
| Recall CLI | **Complete** | Semantic search with reranking (Voyage/Cohere/local) |
| Unit Tests | **Complete** | 39+ tests per backend |
| E2E Tests | **Complete** | PostgreSQL + SQLite E2E coverage |
| Hook Integration | **Not Wired** | CLI exists but no hooks call it |
| Scope Registration | **Not Wired** | Not registered in Agentica Scope |
| Backfill Pipeline | **Complete** | TemporalWriter, TemporalWriterPG for Braintrust spans |

### Integration Gaps

1. **No active hooks** - The README shows hook integration examples, but `.claude/settings.json` has no temporal memory hooks registered
2. **No Scope registration** - Temporal memory is not part of the Agentica agent Scope/tool registry
3. **Blackboard uses TEMPORAL scope** - The blackboard.py has a `ScopeLevel.TEMPORAL` layer that references "PostgreSQL, full history, semantic search" but does not actually wire to temporal_memory

---

## Value Proposition

### What Temporal Memory Provides

| Capability | Layer 1-2 Alternative | Temporal Memory Value-Add |
|------------|----------------------|---------------------------|
| Fact storage | Ledger files, TodoWrite | Turn-indexed tracking, change_count |
| Invariant detection | Manual | Automatic (facts that never changed) |
| State transitions | Git diff | Utility-ranked, 15-turn half-life |
| Open questions | UNCONFIRMED prefix | E(X,Q) formal evocation tracking |
| Token efficiency | Prose handoffs | Structured TEL format (~60-70% reduction) |
| Semantic recall | Grep/Morph | pgvector similarity search |
| Agent handoffs | Markdown files | Structured TemporalHandoffState with parsing |

### Unique Value

1. **Turn-based tracking** - No other layer tracks "when" facts were established or changed
2. **Inertia semantics** - Facts persist unless explicitly negated (formal belief revision)
3. **Invariant detection** - Automatically identifies stable architectural decisions
4. **E(X,Q) integration** - Formal question tracking, not just prose markers
5. **Vector search on facts** - Semantic recall across sessions (PostgreSQL)

### Overlapping Value

1. **Handoff format** - Similar to existing markdown ledgers/handoffs (but structured)
2. **Fact storage** - Ledger files already store key facts
3. **Goal tracking** - TodoWrite already tracks pending goals

---

## Complexity Assessment

### Lines of Code

| Component | LOC |
|-----------|-----|
| atoms.py | 181 |
| inertia.py | 186 |
| store.py | 449 |
| store_pg.py | 605 |
| summarizer.py | 414 |
| handoff.py | 367 |
| cli.py | 221 |
| factory.py | 233 |
| protocol.py | 254 |
| **Total** | **~2,900** |

### Dependencies

- `aiosqlite` (SQLite backend)
- `asyncpg` (PostgreSQL backend)
- `numpy` (embedding padding)
- `z3_erotetic` (E(X,Q) integration)
- Connection pooling infrastructure
- Voyage/Cohere API for embeddings (optional)

### Test Coverage

- 11 test files with 100+ tests
- Unit tests for each component
- E2E tests for both backends
- Integration tests for PostgreSQL with Docker

---

## Recommendation

### Verdict: **Simplify - Keep Core, Remove Complexity**

The temporal memory system is well-built but **over-engineered for current use**. It provides formal semantics (TEL, E(X,Q)) that are not being leveraged by any active hooks or agents.

### What to Keep

| Component | Reason |
|-----------|--------|
| Basic fact storage (store.py) | Simple turn-indexed key-value storage is useful |
| Invariant detection | Automatic "what never changed" is genuinely valuable |
| CLI interface | Enables hook integration without code changes |
| Handoff format | Structured agent-to-agent transfer is useful |

### What to Simplify or Remove

| Component | Action | Reason |
|-----------|--------|--------|
| TEL Atoms (atoms.py) | Remove | ALWAYS/EVENTUALLY/UNTIL operators unused in practice |
| E(X,Q) integration | Remove | UNKNOWN string in facts is sufficient |
| Utility scoring | Simplify | 15-turn half-life is over-engineered; simple recency works |
| PostgreSQL backend | Keep (but optional) | Multi-agent scenarios need it |
| Vector embeddings | Remove from core | Move to separate semantic_memory module |
| Protocol abstraction | Keep | Clean backend switching is valuable |

### Simplified Architecture

```
scripts/temporal_memory/
  store.py          # SQLite, basic turn-indexed facts + change_count
  store_pg.py       # PostgreSQL, same interface
  summarizer.py     # Invariants + transitions (simplified utility)
  handoff.py        # Keep as-is
  cli.py            # Keep as-is
  factory.py        # Keep as-is

# Move to separate module
scripts/semantic_memory/
  embedding_store.py  # Vector search on facts (pgvector)
  recall.py           # Semantic recall CLI
```

---

## Integration Path for Headless Agents

### Current State (Not Integrated)

Headless Claude agents have **no path** to temporal memory:
1. No hooks registered in `.claude/settings.json`
2. No Scope registration for Agentica agents
3. No automatic fact recording from tool use

### Proposed Integration

**Option A: CLI-based (Minimal)**

```bash
# Agent records facts via CLI
uv run python -m scripts.temporal_memory.cli record \
  --session-id "$CLAUDE_SESSION_ID" \
  --turn "$TURN" \
  --facts '{"task": "implement auth", "status": "in_progress"}'

# Agent summarizes for handoff
uv run python -m scripts.temporal_memory.cli summarize \
  --session-id "$CLAUDE_SESSION_ID" \
  --output markdown
```

Hook registration:
```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/session-end-temporal.sh"
      }]
    }]
  }
}
```

**Option B: Scope Registration (Full Integration)**

```python
# In Agentica agent Scope
class TemporalMemoryScope:
    """Temporal fact recording for agents."""

    @agentic.tool()
    async def record_fact(self, key: str, value: str) -> None:
        """Record a fact at current turn."""
        store = await create_temporal_store(session_id=self.session_id)
        await store.record(turn=self.turn, facts={key: value})

    @agentic.tool()
    async def get_invariants(self) -> dict[str, str]:
        """Get facts that never changed."""
        store = await create_temporal_store(session_id=self.session_id)
        return await store.get_invariants()
```

**Option C: Simpler Alternative - Just Use Ledgers**

Given that the continuity ledger pattern already works:

```markdown
## State
- Done:
  - [x] Phase 1: Database schema
- Now: [->] Phase 2: API endpoints
- Invariants:
  - db_type: postgres
  - auth_provider: auth0
```

The ledger is:
- Human-readable (Claude can parse it naturally)
- Git-versioned (history tracked)
- Already wired to SessionStart hook
- No additional database required

**Recommendation:** Use **Option A** (CLI-based) for explicit fact recording when needed, but rely on **ledgers** for most state tracking. Temporal memory is overkill for typical single-agent workflows.

---

## Summary

| Aspect | Finding |
|--------|---------|
| **Is it useful?** | Yes, but over-engineered for current use |
| **Is it being used?** | No - not wired to any hooks or agents |
| **Should we keep it?** | Partially - keep core, remove TEL formalism |
| **What's the simpler alternative?** | Continuity ledgers + markdown handoffs |
| **When is temporal memory justified?** | Multi-agent, long-running, cross-session recall |

### Action Items

1. **Short-term:** Wire CLI to at least one hook (e.g., Stop event for session summary)
2. **Medium-term:** Simplify by removing TEL atoms and E(X,Q) formal logic
3. **Long-term:** Evaluate if vector search on facts provides value over ledger pattern
4. **Consider:** Moving semantic recall to a separate module

---

## File References

### Core Implementation
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/temporal_memory/store.py` - SQLite store
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/temporal_memory/store_pg.py` - PostgreSQL store
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/temporal_memory/summarizer.py` - Token-efficient summarization
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/temporal_memory/handoff.py` - Agent handoff format
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/temporal_memory/cli.py` - CLI interface

### Documentation
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/temporal_memory/README.md` - Full system documentation
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/docs/architecture/temporal-memory-backends.md` - Backend architecture
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/Completed Documentation/02-Architecture/Memory-System.md` - Three-layer overview

### Tests
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_temporal_store.py` - SQLite tests
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_temporal_store_pg.py` - PostgreSQL tests
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/integration/test_temporal_memory_e2e.py` - E2E tests

### Related Systems
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica_patterns/blackboard.py` - References TEMPORAL scope but does not integrate
- `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/.claude/skills/recall/SKILL.md` - Semantic recall skill

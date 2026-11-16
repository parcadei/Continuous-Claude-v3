# Memory System

The memory system has three layers: backend storage, LLM-span extraction, and temporal symbolic memory. The aim is to provide reliable recall, explainable summaries, and agent-to-agent continuity.

## 1) Memory backend (core + archival + recall)

```
User Code
  → create_memory_service()
     ├── sqlite (dev)
     └── postgres + pgvector (prod)

Memory layers:
  Core memory   = always in context
  Archival      = searchable facts
  Recall        = query across all stores
```

Key doc: `docs/memory-backend.md`

## 2) LLMSpanMemory (per-span retrieval)

Why it exists: session-level facts missed 29+ reasoning steps per session.

```
Braintrust spans
  → extract LLMSpanMemory
     - intent
     - decision
     - tools
     - files
  → store with content_hash (metadata)
  → retrieve by semantic query
```

Deduping behavior:
- Searches by content_hash in metadata
- Avoids writing duplicates across backfills

LLMSpanMemory retrieval path:

```
Query → hybrid search (BM25 + vectors)
  → top spans
  → response synthesis
```

Key doc: `docs/llm-span-memory/README.md`

## 3) Temporal memory (facts over time)

Temporal memory is a TEL-inspired system that treats facts as time-indexed atoms.

```
Record facts (turn-based)
  → apply inertia (facts persist unless updated)
  → detect invariants (never changed)
  → compute transitions (state changes)
  → rank open questions (erotetic)
  → summarize to token budget (includes current_state)
```

Key rules:
- Inertia: holds(P,T+1) unless evidence of change
- Priority: explicit negation > recent observation > invariant > historical
- Utility: importance × recency × frequency (15-turn half-life)

## 4) Temporal handoff format

```
# Temporal Handoff
- Open Questions (ranked)
- Invariants (always)
- Current State (snapshot)
- Pending Goals
- Transitions
- Context / Next Instruction
```

Snapshot vs invariants:
- Invariants = facts that never changed
- Current State = latest known values (volatile)

This is the bridge between agents: structured + human-readable.

## Integration points

```
Hooks → Temporal CLI → Summary → Handoff → Next agent
```

CLI behavior:
- `record_with_erotetic()` computes erotetic unknowns by default
- `summarize` enforces a total token budget including current_state

## Related sources

- `docs/llm-span-memory/README.md`
- `scripts/temporal_memory/README.md`
- `thoughts/shared/handoffs/open-source-release/2025-12-31_08-31-22_memory-system-implementation-complete.md`

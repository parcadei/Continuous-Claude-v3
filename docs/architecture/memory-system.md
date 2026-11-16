# Memory System Architecture

## Overview

The memory system provides a three-tier architecture for agent memory management, supporting both development (SQLite) and production (PostgreSQL with pgvector) backends. Memory is automatically wired into agents via `tracked_spawn()`.

## Component Diagram

```
                        ┌─────────────────────────────────────────────────────────────┐
                        │                    Application Layer                         │
                        │  ┌───────────────────────────────────────────────────────┐   │
                        │  │              tracked_spawn(db, premise, ...)          │   │
                        │  │              inject_memory=True (default)             │   │
                        │  └───────────────────────────┬───────────────────────────┘   │
                        └──────────────────────────────┼───────────────────────────────┘
                                                       │
                                                       ▼
                        ┌─────────────────────────────────────────────────────────────┐
                        │                     Scope Factory Layer                      │
                        │  ┌───────────────────────────────────────────────────────┐   │
                        │  │           create_unified_scope(session_id, ...)       │   │
                        │  │                                                        │   │
                        │  │  Merges:                                               │   │
                        │  │  - File operations (read_file, write_file, bash...)   │   │
                        │  │  - Memory operations (remember, recall, store_fact)   │   │
                        │  │  - Task operations (create_task, complete_task...)    │   │
                        │  │  - Vector operations (recall_vector, remember_with_)  │   │
                        │  │  - Message operations (store_message, conversation_)  │   │
                        │  └───────────────────────────┬───────────────────────────┘   │
                        └──────────────────────────────┼───────────────────────────────┘
                                                       │
                              ┌────────────────────────┼────────────────────────┐
                              │                        │                        │
                              ▼                        ▼                        ▼
               ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
               │   MemoryService      │  │  MemoryServicePG     │  │  MessageMemoryService│
               │   (SQLite Backend)   │  │  (PostgreSQL Backend)│  │  (Conversation)      │
               │                      │  │                      │  │                      │
               │ - aiosqlite          │  │ - asyncpg            │  │ - PostgreSQL FTS     │
               │ - FTS5 full-text     │  │ - pgvector           │  │ - Role filtering     │
               │ - WAL mode           │  │ - RRF hybrid search  │  │ - Temporal filtering │
               │ - Session isolation  │  │ - Tag filtering      │  │                      │
               └──────────┬───────────┘  └──────────┬───────────┘  └──────────┬───────────┘
                          │                         │                         │
                          └─────────────────────────┼─────────────────────────┘
                                                    │
                                                    ▼
                                    ┌───────────────────────────────┐
                                    │     MemoryBackend Protocol    │
                                    │                               │
                                    │ Core Memory:                  │
                                    │   set_core, get_core,         │
                                    │   list_core_keys, delete_core │
                                    │                               │
                                    │ Archival Memory:              │
                                    │   store, search, delete       │
                                    │                               │
                                    │ Recall:                       │
                                    │   recall, to_context          │
                                    │                               │
                                    │ Lifecycle:                    │
                                    │   connect, close              │
                                    └───────────────────────────────┘
```

## Data Flow: Memory Auto-Wiring

```
1. tracked_spawn() called
          │
          ▼
2. inject_memory=True? ──No──→ Use user scope or empty dict
          │
         Yes
          │
          ▼
3. Get session_id from:
   - CLAUDE_SESSION_ID env var
   - Fallback: f"agent-{agent_id}"
          │
          ▼
4. create_unified_scope(
     session_id=session_id,
     enable_memory=True,
     enable_tasks=False
   )
          │
          ▼
5. Merge with user scope:
   - Protected keys: remember, recall, search_memory, store_fact
   - User scope cannot override protected keys
          │
          ▼
6. Pass merged scope to agentica.spawn()
          │
          ▼
7. Agent now has memory functions in scope
```

## Memory Tier Architecture

### Core Memory

In-context key-value storage for session state.

```
┌─────────────────────────────────────────────────┐
│                  Core Memory                     │
├─────────────────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│ │ persona │ │  task   │ │ context │ │ state   │ │
│ │         │ │         │ │         │ │         │ │
│ │ "Senior │ │ "Build  │ │ "User   │ │ "Step   │ │
│ │ Python  │ │ REST    │ │ prefers │ │ 3 of 5" │ │
│ │ dev"    │ │ API"    │ │ async"  │ │         │ │
│ └─────────┘ └─────────┘ └─────────┘ └─────────┘ │
└─────────────────────────────────────────────────┘

Storage: PostgreSQL or SQLite table
Access: Always in context, fast reads
Update: Upsert on set_core()
```

### Archival Memory

Long-term searchable storage with FTS and optional vector embeddings.

```
┌─────────────────────────────────────────────────────────────────┐
│                      Archival Memory                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ id: uuid-1                                                │   │
│  │ content: "User prefers pytest over unittest"              │   │
│  │ metadata: {"source": "conversation"}                      │   │
│  │ tags: ["preference", "testing"]                           │   │
│  │ embedding: [0.12, 0.45, ...]  (4096 dimensions, padded)   │   │
│  │ created_at: 2025-12-31T10:30:00                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ id: uuid-2                                                │   │
│  │ content: "Chose FastAPI for async support and speed"      │   │
│  │ metadata: {"type": "decision"}                            │   │
│  │ tags: ["decision", "api", "important"]                    │   │
│  │ embedding: [0.23, 0.67, ...]                              │   │
│  │ created_at: 2025-12-31T11:00:00                          │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

Search Methods:
- FTS (Full-Text Search): Keyword matching with ranking
- Vector: Cosine similarity with embeddings
- Hybrid: Weighted combination of FTS + vector
- RRF: Reciprocal Rank Fusion (robust hybrid)
```

### Recall Memory

Query interface combining core and archival sources.

```
         Query: "What framework should I use?"
                        │
                        ▼
              ┌─────────────────┐
              │     recall()    │
              └────────┬────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌───────────────┐           ┌─────────────────┐
│ Core Memory   │           │ Archival Memory │
│ Key Matching  │           │ FTS Search      │
└───────┬───────┘           └────────┬────────┘
        │                            │
        │ [Core/task]: Build API     │ [Archival]: Chose FastAPI...
        │                            │
        └──────────────┬─────────────┘
                       │
                       ▼
              Combined Context String
```

## Session Isolation

Memory is scoped by session and optionally by agent:

```
Session: "swarm-001"
├── Agent: coordinator
│   └── Core Memory: {"role": "Coordinate tasks", ...}
│   └── Archival: [decisions, outcomes]
│
├── Agent: worker-1
│   └── Core Memory: {"role": "Execute task A", ...}
│   └── Archival: [task-specific facts]
│
└── Agent: worker-2
    └── Core Memory: {"role": "Execute task B", ...}
    └── Archival: [task-specific facts]

Shared Archival (same session_id, no agent_id):
└── Facts visible to all agents in session
```

## Tag Filtering Architecture

Tags provide flexible categorization for archival memory:

```
┌─────────────────────────────────────────────────────────────────┐
│                      memory_tags Table                           │
├─────────────────────────────────────────────────────────────────┤
│ memory_id │ tag          │ session_id                           │
├───────────┼──────────────┼──────────────────────────────────────┤
│ uuid-1    │ important    │ session-abc                          │
│ uuid-1    │ decision     │ session-abc                          │
│ uuid-1    │ api          │ session-abc                          │
│ uuid-2    │ bug          │ session-abc                          │
│ uuid-2    │ high-priority│ session-abc                          │
└───────────┴──────────────┴──────────────────────────────────────┘

Queries:
- tags=["important"], mode="any"  → uuid-1
- tags=["bug", "security"], mode="any"  → uuid-2 (has bug)
- tags=["bug", "high-priority"], mode="all"  → uuid-2 (has both)
- tags=["api", "decision"], mode="all"  → uuid-1 (has both)
```

## Hybrid Search: RRF (Reciprocal Rank Fusion)

RRF combines FTS and vector rankings without score normalization issues:

```
Query: "Python async patterns"
                │
    ┌───────────┴───────────┐
    │                       │
    ▼                       ▼
┌───────────────┐   ┌───────────────┐
│  FTS Search   │   │ Vector Search │
│  Rank by      │   │ Rank by       │
│  ts_rank()    │   │ cosine sim    │
└───────┬───────┘   └───────┬───────┘
        │                   │
        ▼                   ▼
   Rank 1: doc-A       Rank 1: doc-B
   Rank 2: doc-C       Rank 2: doc-A
   Rank 3: doc-B       Rank 3: doc-D
   Rank 4: doc-D       Rank 4: doc-C

RRF Score (k=60):
   doc-A: 1/(60+1) + 1/(60+2) = 0.0163 + 0.0161 = 0.0324
   doc-B: 1/(60+3) + 1/(60+1) = 0.0159 + 0.0163 = 0.0322
   doc-C: 1/(60+2) + 1/(60+4) = 0.0161 + 0.0156 = 0.0317
   doc-D: 1/(60+4) + 1/(60+3) = 0.0156 + 0.0159 = 0.0315

Final Ranking: doc-A, doc-B, doc-C, doc-D
```

## Block-Based Core Memory

Letta-compatible structured blocks with character limits:

```
┌─────────────────────────────────────────────────────────────────┐
│                      BlockManager                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  blocks: Dict[str, Block]                                        │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Block: "persona"                                            │ │
│  │ ├── label: "persona"                                        │ │
│  │ ├── value: "I am a senior Python developer..."              │ │
│  │ ├── limit: 5000 (characters)                                │ │
│  │ ├── remaining: 4850                                         │ │
│  │ └── metadata: {}                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Block: "human"                                              │ │
│  │ ├── label: "human"                                          │ │
│  │ ├── value: "User is Alice, a senior engineer..."           │ │
│  │ ├── limit: 5000                                             │ │
│  │ ├── remaining: 4920                                         │ │
│  │ └── metadata: {"company": "TechCorp"}                       │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  to_core_memory_string() →                                       │
│    <persona>                                                     │
│    I am a senior Python developer...                            │
│    </persona>                                                    │
│                                                                  │
│    <human>                                                       │
│    User is Alice, a senior engineer...                          │
│    </human>                                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Connection Pool Architecture (PostgreSQL)

```
┌─────────────────────────────────────────────────────────────────┐
│                     Global Singleton Pool                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    asyncpg.Pool                           │   │
│  │  ├── min_size: 2                                          │   │
│  │  ├── max_size: 10                                         │   │
│  │  └── command_timeout: 60s                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Protected by: asyncio.Lock                                      │
│  Lazy initialization: created on first get_pool() call          │
│                                                                  │
│  Context Managers:                                               │
│  ├── get_connection() → async with pool.acquire() as conn       │
│  └── get_transaction() → conn.transaction() with commit/rollback│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

                         Used by:
    ┌──────────────┬──────────────┬──────────────┐
    │ MemoryService│ Message      │ Coordination │
    │ PG           │ Memory       │ DB           │
    └──────────────┴──────────────┴──────────────┘
```

## Letta Parity

The memory system maintains compatibility with Letta/MemGPT patterns:

| Letta Feature | Agentica Implementation | Notes |
|---------------|------------------------|-------|
| Core Memory Blocks | Block dataclass + BlockManager | 5000 char limit default |
| Archival Memory | archival_memory table + FTS | With optional embeddings |
| Recall | recall() combining sources | Core key match + archival search |
| Conversation Search | MessageMemoryService | With role and date filtering |
| Memory Editing | set_core() / update() | Enforced character limits |
| Agent Memory | agent_id scoping | PostgreSQL only |
| Embedding Storage | pgvector (4096 dim, padded) | Provider-agnostic |

## File Locations

```
scripts/agentica_patterns/
├── unified_scope.py       # Scope factory, memory wiring
├── tracked_agent.py       # tracked_spawn with auto-wiring
├── memory_service.py      # SQLite backend
├── memory_service_pg.py   # PostgreSQL backend
├── memory_block.py        # Block and BlockManager
├── memory_factory.py      # Backend factory
├── memory_protocol.py     # MemoryBackend Protocol
├── message_memory.py      # Conversation search service
├── embedding_service.py   # Embedding providers
├── reranker.py           # Cross-encoder reranking
└── postgres_pool.py      # Connection pooling
```

## Related Documentation

- [Memory System Guide](/docs/memory-system-guide.md) - User guide with examples
- [Memory Backend](/docs/memory-backend.md) - Backend comparison and configuration
- [Migration Guide](/docs/migration/memory-auto-wiring.md) - Migration from manual setup

# Temporal Memory Backend Architecture

**Document Version:** 1.0
**Last Updated:** 2025-12-31
**Branch:** feature/agentica-integration

---

## 1. Overview

The temporal memory system provides session-scoped fact storage with change tracking, confidence calibration, and optional vector similarity search. It supports dual backends:

| Backend | Use Case | Features |
|---------|----------|----------|
| **SQLite** | Local development, single agent | Zero setup, file-based, FTS5 search |
| **PostgreSQL** | Production, multi-agent | Concurrent access, pgvector, connection pooling |

### Key Capabilities

- **Temporal tracking** - Facts maintain turn history (when established, when changed)
- **Inertia rule** - Facts persist across turns unless explicitly revised
- **Erotetic integration** - Track open questions and unknowns per turn
- **Confidence calibration** - Adjust fact confidence based on session outcomes
- **Vector search** - Semantic similarity search via pgvector (PostgreSQL only)

---

## 2. Dual-Backend Architecture

### Design Principle

The temporal memory uses a **Protocol-based abstraction** that allows seamless switching between backends without changing application code.

```
                    ┌─────────────────────────────────┐
                    │       Application Layer          │
                    │  (Backfill, Hooks, Skills, etc.) │
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │         Factory Layer            │
                    │  create_temporal_store()         │
                    │  create_temporal_writer()        │
                    │  get_temporal_backend()          │
                    └────────────────┬────────────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           │                                                   │
           ▼                                                   ▼
┌─────────────────────────┐                     ┌─────────────────────────┐
│   TemporalMemoryStore   │                     │  TemporalMemoryStorePG  │
│   (SQLite Backend)      │                     │  (PostgreSQL Backend)   │
├─────────────────────────┤                     ├─────────────────────────┤
│  • aiosqlite driver     │                     │  • asyncpg driver       │
│  • File-based storage   │                     │  • Connection pooling   │
│  • FTS5 text search     │                     │  • pgvector support     │
│  • Single-writer        │                     │  • Multi-writer         │
└─────────────────────────┘                     └─────────────────────────┘
```

### Protocol Definition

Both backends implement the same Protocol for interoperability:

```python
# scripts/temporal_memory/protocol.py

from typing import Protocol, Any

class TemporalStoreProtocol(Protocol):
    """Protocol for temporal memory stores."""

    session_id: str

    async def connect(self) -> None:
        """Initialize connection and restore state."""
        ...

    async def record(self, turn: int, facts: dict[str, Any]) -> None:
        """Record facts at a turn with change tracking."""
        ...

    async def get_trace(self) -> list[dict[str, Any]]:
        """Get full temporal trace ordered by turn."""
        ...

    async def get_current_state(self) -> dict[str, Any]:
        """Get current values of all facts."""
        ...

    async def get_invariants(self) -> dict[str, Any]:
        """Get facts that never changed (change_count == 0)."""
        ...

    async def advance_turn(
        self,
        new_facts: dict[str, Any] | None = None
    ) -> list["RevisionEvent"]:
        """Advance turn, applying inertia rule."""
        ...


class TemporalWriterProtocol(Protocol):
    """Protocol for temporal fact writers (backfill pipeline)."""

    async def connect(self) -> None:
        """Initialize connection."""
        ...

    async def close(self) -> None:
        """Close connection."""
        ...

    async def write_facts(
        self,
        session_id: str,
        facts: list["SpanFact"],
        outcome: "SessionOutcome",
    ) -> int:
        """Write facts with calibrated confidence. Returns count."""
        ...

    async def write_traces(
        self,
        session_id: str,
        traces: list["TurnTrace"],
    ) -> int:
        """Write turn-level trace snapshots. Returns count."""
        ...

    async def get_facts(self, session_id: str) -> list[dict[str, Any]]:
        """Get all facts for a session."""
        ...

    async def get_traces(self, session_id: str) -> list[dict[str, Any]]:
        """Get all traces for a session."""
        ...
```

---

## 3. When to Use Which Backend

### SQLite (Default)

**Best for:**
- Local development and prototyping
- Single-agent workflows
- Quick setup without external dependencies
- Testing and CI environments
- Portable, file-based storage

**Limitations:**
- Single writer at a time (no concurrent writes)
- No vector similarity search
- Limited connection pooling

```bash
# SQLite is default - no configuration needed
# Or explicitly:
export TEMPORAL_BACKEND=sqlite
```

### PostgreSQL

**Best for:**
- Production deployments
- Multi-agent concurrent workflows
- Semantic/vector similarity search
- High-volume fact storage
- Shared state across processes

**Requirements:**
- PostgreSQL server with pgvector extension
- Connection URL configuration
- Docker container or managed service

```bash
# Enable PostgreSQL backend
export TEMPORAL_BACKEND=postgres
export AGENTICA_POSTGRES_URL=postgresql://user:pass@localhost:5433/db
```

### Decision Matrix

| Requirement | SQLite | PostgreSQL |
|-------------|--------|------------|
| Zero setup | Yes | No |
| Concurrent writes | No | Yes |
| Vector search | No | Yes |
| Multi-agent | Limited | Yes |
| Production-ready | No | Yes |
| File-based | Yes | No |
| Connection pooling | Basic | Advanced |

---

## 4. Unified Schema

The PostgreSQL schema is a **superset** that supports both temporal implementations:

### Why Unified?

The codebase has two temporal implementations:
1. **TemporalWriter** - Batch backfill from Braintrust spans
2. **TemporalMemoryStore** - Session-scoped interactive storage

They share the same database but use slightly different schemas. The unified PostgreSQL schema accommodates both.

### temporal_facts Table

```sql
CREATE TABLE IF NOT EXISTS temporal_facts (
    -- Primary key: UUID for PostgreSQL
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core fields (both implementations)
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 1.0,

    -- Turn tracking (TemporalWriter uses 'turn', Store uses established/changed)
    turn INTEGER,                      -- TemporalWriter: single turn
    turn_established INTEGER,          -- TemporalMemoryStore: when first set
    turn_last_changed INTEGER,         -- TemporalMemoryStore: last modification

    -- Change tracking (TemporalMemoryStore only)
    change_count INTEGER DEFAULT 0,

    -- Deduplication (TemporalWriter)
    content_hash TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Vector embedding (1024 native Voyage dimension)
    embedding vector(1024),

    -- Constraints
    CONSTRAINT uq_temporal_facts_hash UNIQUE (content_hash),
    CONSTRAINT uq_temporal_facts_session_key UNIQUE (session_id, key)
        DEFERRABLE INITIALLY DEFERRED
);
```

### temporal_traces Table

```sql
CREATE TABLE IF NOT EXISTS temporal_traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    turn INTEGER NOT NULL,

    -- TemporalWriter fields
    fact_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 1.0,

    -- TemporalMemoryStore fields
    facts_json JSONB,                  -- Snapshot of facts at turn
    erotetic_json JSONB,               -- E(X,Q) evocation data

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Indexes

```sql
-- Performance indexes
CREATE INDEX idx_temporal_facts_session ON temporal_facts(session_id);
CREATE INDEX idx_temporal_facts_session_key ON temporal_facts(session_id, key);
CREATE INDEX idx_temporal_facts_turn ON temporal_facts(session_id, turn);
CREATE INDEX idx_temporal_facts_turn_established ON temporal_facts(session_id, turn_established);
CREATE INDEX idx_temporal_facts_hash ON temporal_facts(content_hash) WHERE content_hash IS NOT NULL;
CREATE INDEX idx_temporal_traces_session ON temporal_traces(session_id);
CREATE INDEX idx_temporal_traces_turn ON temporal_traces(session_id, turn);

-- Full-text search on fact values
CREATE INDEX idx_temporal_facts_value_fts ON temporal_facts
    USING gin(to_tsvector('english', value));

-- Vector similarity index (create after initial data load)
-- CREATE INDEX idx_temporal_facts_embedding ON temporal_facts
--     USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

---

## 5. Vector Embedding Support

PostgreSQL backend supports semantic search via pgvector:

### Embedding Storage

Facts can include vector embeddings for similarity search:

```python
async def write_facts_with_embeddings(
    session_id: str,
    facts: list[SpanFact],
    embedding_fn: Callable[[str], list[float]] | None = None,
) -> int:
    """Write facts with optional vector embeddings."""
    for fact in facts:
        if embedding_fn:
            # Generate embedding from fact content
            embedding = embedding_fn(f"{fact.key}: {fact.value}")
            # Pad to target dimension (4096)
            if len(embedding) < 4096:
                embedding.extend([0.0] * (4096 - len(embedding)))
        # Insert with embedding
        ...
```

### Vector Search

Query facts by semantic similarity:

```python
async def search_similar(
    self,
    query_embedding: list[float],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search facts by vector similarity."""
    async with get_connection() as conn:
        await init_pgvector(conn)
        rows = await conn.fetch(
            """
            SELECT key, value, confidence,
                   1 - (embedding <=> $2::vector) as similarity
            FROM temporal_facts
            WHERE session_id = $1 AND embedding IS NOT NULL
            ORDER BY embedding <=> $2::vector
            LIMIT $3
            """,
            self.session_id, query_embedding, limit
        )
        return [dict(r) for r in rows]
```

### When to Use Vector Search

| Scenario | Text Search (FTS5/tsvector) | Vector Search (pgvector) |
|----------|------------------------------|--------------------------|
| Exact keyword match | Yes | No |
| Semantic similarity | No | Yes |
| "Find facts about X" | Partial | Yes |
| Fuzzy matching | Limited | Yes |
| Cross-language | No | Yes |

---

## 6. Concurrent Access Patterns

### SQLite Limitations

SQLite uses file-level locking:
- Single writer at a time
- Multiple concurrent readers OK
- SQLITE_BUSY errors on contention

```python
# SQLite handles contention via busy timeout
async with aiosqlite.connect(path, timeout=30.0) as conn:
    # 30 second timeout before SQLITE_BUSY
    await conn.execute(...)
```

### PostgreSQL Concurrency

PostgreSQL provides full MVCC concurrency:
- Multiple writers simultaneously
- Row-level locking
- Connection pooling via asyncpg

```python
# PostgreSQL connection pool
from scripts.agentica_patterns.postgres_pool import get_connection

async with get_connection() as conn:
    # Connection from pool (max 20 default)
    await conn.execute(...)
    # Connection returned to pool on exit
```

### Multi-Agent Pattern

With PostgreSQL, multiple agents can share temporal memory:

```python
# Agent 1
store1 = await create_temporal_store(backend="postgres", session_id="shared")
await store1.record(turn=1, facts={"agent": "agent1", "status": "started"})

# Agent 2 (concurrent)
store2 = await create_temporal_store(backend="postgres", session_id="shared")
await store2.record(turn=1, facts={"agent": "agent2", "status": "started"})

# Both writes succeed - PostgreSQL handles concurrency
```

---

## 7. Factory Pattern Usage

### Basic Usage

```python
from scripts.temporal_memory.factory import (
    create_temporal_store,
    create_temporal_writer,
    get_temporal_backend,
)

# Get current backend from environment
backend = get_temporal_backend()  # "sqlite" or "postgres"

# Create store (connects automatically)
store = await create_temporal_store(
    backend=backend,
    session_id="my-session",
    db_path=Path(".claude/cache/temporal.db"),  # SQLite only
)

# Create writer (for backfill pipeline)
writer = await create_temporal_writer(
    backend=backend,
    db_path=Path(".claude/cache/temporal.db"),  # SQLite only
)
```

### Environment-Driven Selection

```python
import os

# Set backend via environment
os.environ["TEMPORAL_BACKEND"] = "postgres"

# Factory reads environment
store = await create_temporal_store(session_id="auto-select")
# Returns TemporalMemoryStorePG instance

# Or override explicitly
sqlite_store = await create_temporal_store(
    backend="sqlite",  # Ignore environment
    session_id="force-sqlite"
)
```

### Context Manager Pattern

```python
async with await create_temporal_store(session_id="ctx") as store:
    await store.record(turn=1, facts={"key": "value"})
    state = await store.get_current_state()
# Connection closed automatically
```

---

## 8. Code Examples

### Recording Facts

```python
from scripts.temporal_memory.factory import create_temporal_store

async def record_session_facts():
    store = await create_temporal_store(
        backend="postgres",
        session_id="research-session-001"
    )

    # Turn 1: Initial facts
    await store.record(turn=1, facts={
        "topic": "PostgreSQL migration",
        "status": "researching",
        "confidence": 0.8,
    })

    # Turn 2: Updated facts (triggers change tracking)
    await store.record(turn=2, facts={
        "topic": "PostgreSQL migration",
        "status": "implementing",  # Changed
        "progress": "50%",  # New fact
    })

    # Get current state
    state = await store.get_current_state()
    # {'topic': 'PostgreSQL migration', 'status': 'implementing', 'progress': '50%'}

    # Get invariants (facts that never changed)
    invariants = await store.get_invariants()
    # {'topic': 'PostgreSQL migration'}  # status changed, so not invariant
```

### Inertia Rule

```python
async def demonstrate_inertia():
    store = await create_temporal_store(backend="postgres", session_id="inertia-demo")

    # Turn 1: Set initial facts
    await store.record(turn=1, facts={
        "user_name": "Alice",
        "project": "Demo",
    })

    # Advance turn without providing facts
    revisions = await store.advance_turn()
    # Returns empty list - no revisions

    # Both facts persist due to inertia
    state = await store.get_current_state()
    # {'user_name': 'Alice', 'project': 'Demo'}

    # Turn 3: Update one fact
    revisions = await store.advance_turn(new_facts={"project": "Production"})
    # Returns [RevisionEvent(key='project', old='Demo', new='Production')]

    state = await store.get_current_state()
    # {'user_name': 'Alice', 'project': 'Production'}
```

### Backfill Writer Usage

```python
from scripts.temporal_memory.factory import create_temporal_writer
from scripts.backfill.span_parser import SpanFact
from scripts.backfill.outcome_tagger import SessionOutcome

async def backfill_session():
    writer = await create_temporal_writer(backend="postgres")

    # Parse facts from Braintrust spans
    facts = [
        SpanFact(key="skill_activated", value="commit", turn=5),
        SpanFact(key="tool_used", value="Write", turn=3),
        SpanFact(key="task_completed", value="true", turn=10),
    ]

    # Write with outcome-based calibration
    count = await writer.write_facts(
        session_id="braintrust-session-abc123",
        facts=facts,
        outcome=SessionOutcome.SUCCEEDED,
    )
    print(f"Wrote {count} facts")

    await writer.close()
```

### Vector Similarity Search

```python
from scripts.temporal_memory.store_pg import TemporalMemoryStorePG

async def semantic_search():
    store = TemporalMemoryStorePG(session_id="search-demo")
    await store.connect()

    # Assume facts were stored with embeddings
    # Query embedding for "database optimization"
    query_embedding = get_embedding("database optimization")  # Your embedding fn

    # Find semantically similar facts
    results = await store.search_similar(
        query_embedding=query_embedding,
        limit=5,
    )

    for result in results:
        print(f"{result['key']}: {result['value']} (similarity: {result['similarity']:.3f})")
```

---

## 9. Testing

### Running Backend-Specific Tests

```bash
# SQLite tests (default)
uv run pytest tests/unit/test_temporal_store.py -v

# PostgreSQL tests (requires running container)
TEMPORAL_BACKEND=postgres uv run pytest tests/unit/test_temporal_store_pg.py -v

# Factory tests (both backends)
uv run pytest tests/unit/test_temporal_factory.py -v

# All temporal tests
uv run pytest -k temporal -v
```

### Test Fixtures

```python
# tests/conftest.py

import pytest
from scripts.agentica_patterns.postgres_pool import get_connection, reset_pool

@pytest.fixture(scope="function")
async def clean_pg_temporal():
    """Clean temporal tables before each test."""
    async with get_connection() as conn:
        await conn.execute("TRUNCATE temporal_facts, temporal_traces CASCADE")
    yield
    async with get_connection() as conn:
        await conn.execute("TRUNCATE temporal_facts, temporal_traces CASCADE")

@pytest.fixture(scope="session", autouse=True)
def reset_pool_after_tests():
    """Reset pool after test session."""
    yield
    reset_pool()
```

---

## 10. File Reference

### Core Implementation

| File | Purpose |
|------|---------|
| `scripts/temporal_memory/store.py` | SQLite-backed TemporalMemoryStore |
| `scripts/temporal_memory/store_pg.py` | PostgreSQL-backed TemporalMemoryStorePG |
| `scripts/temporal_memory/factory.py` | Backend factory and environment selection |
| `scripts/temporal_memory/protocol.py` | Protocol definitions |
| `scripts/backfill/temporal_writer.py` | SQLite-backed TemporalWriter |
| `scripts/backfill/temporal_writer_pg.py` | PostgreSQL-backed TemporalWriterPG |
| `scripts/agentica_patterns/postgres_pool.py` | Connection pool utilities |

### Configuration

| File | Purpose |
|------|---------|
| `docker/init.sql` | PostgreSQL schema DDL |
| `.env.example` | Environment variable template |
| `docker/start-postgres.sh` | Container startup script |
| `docker/stop-postgres.sh` | Container shutdown script |

### Tests

| File | Purpose |
|------|---------|
| `tests/unit/test_temporal_store.py` | SQLite store tests (39 tests) |
| `tests/unit/test_temporal_store_pg.py` | PostgreSQL store tests (39 tests) |
| `tests/unit/test_temporal_factory.py` | Factory tests |
| `tests/unit/test_backfill_temporal_writer.py` | SQLite writer tests (10 tests) |
| `tests/unit/test_backfill_temporal_writer_pg.py` | PostgreSQL writer tests (10 tests) |
| `tests/unit/test_temporal_vector_search.py` | Vector search tests |
| `tests/unit/test_migrate_temporal_to_postgres.py` | Migration tests |

---

## 11. Related Documentation

- [Migration Runbook](../operations/temporal-memory-postgres-migration.md) - Step-by-step migration guide
- [Architecture Evolution](./EVOLUTION.md) - How the system evolved
- [Memory Backend Design](../memory-backend.md) - Full memory layer architecture
- [Implementation Plan](../../thoughts/shared/handoffs/temporal-postgres/plan.md) - Detailed implementation phases

---

**Document Status:** Complete
**Next Update:** After production deployment metrics

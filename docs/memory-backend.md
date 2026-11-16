# Memory Backend System

## Overview

The Memory Backend system provides a protocol-based abstraction layer for multi-agent persistent memory, enabling seamless switching between SQLite (for development) and PostgreSQL (for production) backends. This architecture ensures the same code works across different deployment scenarios while supporting both simple local development and concurrent multi-agent production workloads.

The system implements a three-layer memory architecture inspired by Letta/MemGPT:
- **Core Memory**: Key-value blocks for current session facts (always in context)
- **Archival Memory**: Long-term searchable storage (retrieved on demand)
- **Recall Memory**: Cross-source query interface combining all memory types

## Why This Architecture?

### The Problem

Multi-agent systems face several memory persistence challenges:

1. **Deployment Variability**: Different deployment scenarios require different backends
   - Local development: Quick start, zero configuration
   - Production: Concurrent writes, multi-agent coordination

2. **SQLite Limitations Under Concurrency**: SQLite's file-based locking causes write serialization
   - WAL mode helps but doesn't eliminate bottlenecks
   - Connection pooling provides minimal benefit for file-based databases
   - Not suitable for high-concurrency agent swarms

3. **Code Duplication**: Maintaining separate implementations leads to API drift
   - Same logic implemented twice (SQLite + Postgres)
   - Test coverage becomes fragmented
   - Bug fixes must be applied to both backends

4. **Migration Complexity**: Moving from dev to production requires code changes
   - Hard-coded backend selection in application code
   - No way to test production backend locally
   - Environment-specific deployment complexity

### The Solution

A Protocol-based factory pattern with environment-driven backend selection:

```
┌─────────────────────────────────────────────────┐
│           User Code (Agent/Script)              │
└───────────────────┬─────────────────────────────┘
                    │ await create_memory_service()
                    ▼
┌─────────────────────────────────────────────────┐
│         Factory (memory_factory.py)             │
│  ┌─────────────────────────────────────────┐   │
│  │ Backend Selection Logic                 │   │
│  │ - Explicit: backend="sqlite"            │   │
│  │ - Environment: AGENTICA_MEMORY_BACKEND  │   │
│  │ - Dependency Validation                 │   │
│  └─────────────────────────────────────────┘   │
└───────────┬──────────────────────┬──────────────┘
            │                      │
    backend="sqlite"       backend="postgres"
            │                      │
            ▼                      ▼
┌─────────────────────┐  ┌──────────────────────┐
│  MemoryService      │  │  MemoryServicePG     │
│  (SQLite + FTS5)    │  │  (Postgres+pgvector) │
│                     │  │                      │
│  - aiosqlite        │  │  - asyncpg           │
│  - No pooling       │  │  - Connection pool   │
│  - FTS5 search      │  │  - FTS + vector      │
│  - WAL mode         │  │  - MVCC concurrency  │
└─────────────────────┘  └──────────────────────┘
         │                         │
         └────────┬────────────────┘
                  ▼
         MemoryBackend Protocol
         (Structural Typing)
```

### Key Design Decisions

#### 1. Protocol over ABC - Structural Typing

**Choice**: Use `typing.Protocol` instead of Abstract Base Classes (ABC).

**Rationale**:
- **Structural subtyping**: Implementations don't need to inherit from a base class
- **Duck typing with type safety**: mypy validates at compile time, no runtime overhead
- **Backward compatibility**: Can retrofit existing implementations without modifying them
- **Better for gradual typing**: Existing code can satisfy Protocol without refactoring

**Example**:
```python
# Protocol definition (no inheritance required)
class MemoryBackend(Protocol):
    async def set_core(self, key: str, value: str) -> None: ...
    async def get_core(self, key: str) -> str | None: ...

# Implementation satisfies Protocol implicitly
class MemoryService:
    async def set_core(self, key: str, value: str) -> None:
        # Implementation here
        pass

# mypy validates this automatically - no inheritance needed
```

#### 2. Async-Only API - Why aiosqlite?

**Choice**: Convert SQLite implementation to async using `aiosqlite` instead of maintaining dual sync/async APIs.

**Rationale**:
- **API consistency**: Both backends expose identical async interface
- **Simplifies testing**: Single test suite validates both backends
- **Future-proof**: Async is the standard for I/O-bound operations in modern Python
- **Performance acceptable**: ~200μs overhead per call is negligible for most use cases
- **Eliminates complexity**: No need for `run_in_executor()` wrappers or separate sync methods

**Trade-off**: Breaks backward compatibility with synchronous code, but migration is straightforward:
```python
# Before (sync)
memory.set_core("key", "value")

# After (async)
await memory.set_core("key", "value")
```

#### 3. pgvector for Vectors - In-Database Storage

**Choice**: Store embeddings directly in PostgreSQL using pgvector extension instead of external vector databases (Chroma, Pinecone).

**Rationale**:
- **Simplicity**: No additional infrastructure to deploy
- **Consistency**: Vectors stored alongside metadata in same transaction
- **Performance**: Native PostgreSQL indexes (HNSW, IVFFlat)
- **Cost**: No external service fees
- **ACID guarantees**: Full transaction support for hybrid queries

**Vector Operations Supported**:
- Cosine similarity search (`<=>` operator)
- Hybrid search (FTS + vector)
- Metadata filtering with vector search
- Threshold filtering

#### 4. RRF for Hybrid Search - Rank Fusion

**Choice**: Implement Reciprocal Rank Fusion (RRF) for combining full-text and vector search instead of weighted score combination.

**Rationale**:
- **Solves normalization issues**: Rank-based, not score-based
- **Less sensitive to tuning**: No need to carefully balance weights
- **Robust to missing results**: Works well when one modality has no matches
- **Production-proven**: Used by major search engines (Elasticsearch, etc.)

**RRF Formula**:
```
score = 1/(k + rank_fts) + 1/(k + rank_vector)
```
where `k=60` (default constant, higher = more weight to lower ranks)

**Implementation** (PostgreSQL CTE):
```sql
WITH fts_ranked AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY ts_rank(...) DESC) as fts_rank
    FROM archival_memory WHERE <fts_match>
),
vector_ranked AS (
    SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> $query) as vec_rank
    FROM archival_memory WHERE embedding IS NOT NULL
)
SELECT id, (1.0 / (k + fts_rank)) + (1.0 / (k + vec_rank)) as rrf_score
FROM fts_ranked FULL OUTER JOIN vector_ranked USING (id)
ORDER BY rrf_score DESC
```

## Quick Start

### SQLite (Default - Zero Config)

Perfect for local development, single-agent prototypes, and testing.

```python
from scripts.agentica.memory_factory import create_memory_service

# Create SQLite backend (no dependencies beyond aiosqlite)
memory = await create_memory_service("sqlite", session_id="my-session")

# Core memory (always in context)
await memory.set_core("persona", "You are a helpful coding assistant")
await memory.set_core("task", "Help user debug Python code")

# Archival memory (searchable long-term storage)
mem_id = await memory.store("User prefers pytest over unittest")
await memory.store("Project uses FastAPI framework")

# Search archival memory (FTS5 full-text search)
results = await memory.search("testing framework", limit=5)
for result in results:
    print(f"Found: {result['content']} (rank: {result['rank']})")

# Recall - cross-source query combining core + archival
context = await memory.recall("What framework?", limit=3)
print(context)  # Returns formatted string with core and archival results

# Generate prompt context
full_context = await memory.to_context(max_archival=10)
# Output:
# ## Core Memory
# **persona:** You are a helpful coding assistant
# **task:** Help user debug Python code
#
# ## Recent Archival Memory
# - Project uses FastAPI framework
# - User prefers pytest over unittest

# Cleanup
await memory.close()
```

**Database Location**: `.claude/cache/agentica-memory/memory.db` (auto-created)

### PostgreSQL (Production)

For multi-agent systems, concurrent workloads, and production deployments.

#### Setup

```bash
# 1. Start Postgres with pgvector extension
./docker/start-postgres.sh

# 2. Set environment variables
export AGENTICA_MEMORY_BACKEND=postgres
export AGENTICA_POSTGRES_URL=postgresql://user:password@localhost:5432/agentica

# 3. Install dependencies
uv pip install asyncpg pgvector
```

#### Usage

```python
from scripts.agentica.memory_factory import create_memory_service

# Create Postgres backend (uses connection pool)
memory = await create_memory_service(
    "postgres",
    session_id="prod-session",
    agent_id="agent-coordinator"  # Optional: for agent-specific memory
)

# Same API as SQLite
await memory.set_core("persona", "Production coordinator agent")
mem_id = await memory.store("Deployment completed successfully")

# Additional: Vector search (Postgres only)
if hasattr(memory, 'search_vector'):
    embedding = await get_embedding("deployment status")  # Your embedding provider
    results = await memory.search_vector(embedding, limit=5)
    for result in results:
        print(f"Similarity: {result['similarity']:.3f} - {result['content']}")

# Hybrid search (FTS + vector with RRF)
if hasattr(memory, 'search_hybrid_rrf'):
    results = await memory.search_hybrid_rrf(
        text_query="deployment",
        query_embedding=embedding,
        limit=10,
        k=60  # RRF constant
    )

await memory.close()
```

### Environment-Based Selection

**Recommended pattern for production code**: Let the environment determine the backend.

```bash
# Development (.env.development)
AGENTICA_MEMORY_BACKEND=sqlite

# Production (.env.production)
AGENTICA_MEMORY_BACKEND=postgres
AGENTICA_POSTGRES_URL=postgresql://user:password@prod-db:5432/agentica
```

```python
from scripts.agentica.memory_factory import create_default_memory_service

# Automatically uses backend from AGENTICA_MEMORY_BACKEND
memory = await create_default_memory_service(session_id="my-session")

# Same code works in dev (SQLite) and prod (Postgres)
await memory.set_core("task", "Process user request")
results = await memory.search("user preferences", limit=5)

await memory.close()
```

## API Reference

### MemoryBackend Protocol

All methods are async. Both SQLite and PostgreSQL implementations satisfy this protocol.

#### Core Memory Operations

**Core memory blocks are always in context** - use for session state, agent persona, current task.

```python
async def set_core(key: str, value: str) -> None:
    """Set a core memory block.

    Args:
        key: Memory block identifier (e.g., "persona", "task", "context")
        value: Memory block content

    Raises:
        ConnectionError: If database unavailable
    """

async def get_core(key: str) -> str | None:
    """Get a core memory block.

    Args:
        key: Memory block identifier

    Returns:
        Memory block content if exists, None otherwise
    """

async def list_core_keys() -> list[str]:
    """List all core memory block keys.

    Returns:
        List of core memory keys
    """

async def delete_core(key: str) -> None:
    """Delete a core memory block.

    Args:
        key: Memory block identifier
    """

async def get_all_core() -> dict[str, str]:
    """Get all core memory blocks.

    Returns:
        Dictionary mapping keys to values
    """
```

**Example**:
```python
# Store agent configuration
await memory.set_core("persona", "Senior Python developer")
await memory.set_core("code_style", "Prefer type hints and docstrings")
await memory.set_core("current_task", "Debug authentication module")

# Retrieve specific block
persona = await memory.get_core("persona")

# List all keys
keys = await memory.list_core_keys()  # ["persona", "code_style", "current_task"]

# Get everything
all_core = await memory.get_all_core()
```

#### Archival Memory Operations

**Archival memory is retrieved on demand** - use for long-term facts, conversation history, learned patterns.

```python
async def store(
    content: str,
    metadata: dict[str, Any] | None = None,
    embedding: list[float] | None = None
) -> str:
    """Store content in archival memory.

    Args:
        content: Content to store
        metadata: Optional metadata dictionary
        embedding: Optional embedding vector (used by Postgres, ignored by SQLite)

    Returns:
        Memory ID (UUID)

    Raises:
        ValueError: If content is empty
    """

async def search(query: str, limit: int = 10) -> list[dict[str, Any]]:
    """Search archival memory (full-text search).

    Args:
        query: Search query string
        limit: Maximum number of results

    Returns:
        List of dictionaries with keys:
        - id: Memory ID
        - content: Memory content
        - metadata: Metadata dictionary
        - created_at: Timestamp
        - rank: Search relevance score (FTS rank)
    """

async def delete_archival(memory_id: str) -> None:
    """Delete an archival memory entry.

    Args:
        memory_id: Memory ID to delete
    """
```

**Example**:
```python
# Store facts with metadata
mem_id = await memory.store(
    "User reported bug in login flow",
    metadata={"severity": "high", "module": "auth"}
)

# Store with embedding (for vector search later)
embedding = await embedding_service.embed("Database schema updated")
await memory.store(
    "Database schema updated to include user_preferences table",
    embedding=embedding,
    metadata={"type": "schema_change"}
)

# Search (FTS)
results = await memory.search("login bug", limit=5)
for result in results:
    print(f"ID: {result['id']}")
    print(f"Content: {result['content']}")
    print(f"Rank: {result['rank']}")
    print(f"Metadata: {result['metadata']}")

# Delete old entry
await memory.delete_archival(mem_id)
```

#### Recall Operations

**Recall combines core and archival memory** - use for context generation, agent prompts.

```python
async def recall(
    query: str,
    include_core: bool = True,
    limit: int = 5
) -> str:
    """Recall relevant memories for a query.

    Combines archival search with optional core memory inclusion.

    Args:
        query: Query string
        include_core: Whether to include core memory in results
        limit: Max archival memories to retrieve

    Returns:
        Formatted context string
    """

async def to_context(max_archival: int = 10) -> str:
    """Convert memory state to context string.

    Args:
        max_archival: Maximum archival memories to include

    Returns:
        Formatted context string with core and archival memory
    """
```

**Example**:
```python
# Recall specific information
result = await memory.recall("What is the current task?", limit=3)
print(result)
# Output:
# [Core/current_task]: Debug authentication module
# [Archival]: User reported bug in login flow

# Generate full context for agent prompt
context = await memory.to_context(max_archival=10)
# Include this in your agent's system prompt
agent_prompt = f"{base_prompt}\n\n{context}"
```

#### Lifecycle Management

```python
async def connect() -> None:
    """Initialize backend connection.

    Idempotent - safe to call multiple times.
    Initializes schema if needed.

    Raises:
        ConnectionError: If connection fails
    """

async def close() -> None:
    """Close backend connection and cleanup resources.

    Idempotent - safe to call multiple times.
    """
```

**Example**:
```python
# Explicit lifecycle management
memory = await create_memory_service("sqlite", session_id="test")
await memory.connect()  # Idempotent - creates schema if needed
try:
    await memory.set_core("key", "value")
finally:
    await memory.close()  # Always cleanup

# Context manager pattern (recommended)
async with await create_memory_service("sqlite", session_id="test") as memory:
    await memory.set_core("key", "value")
    # Automatically calls close() on exit
```

### Factory Functions

#### create_memory_service

```python
async def create_memory_service(
    backend: Literal["sqlite", "postgres"] = "sqlite",
    session_id: str = "default",
    agent_id: str | None = None,
    **kwargs: Any
) -> MemoryBackend:
    """Create a memory service with the specified backend.

    Args:
        backend: "sqlite" or "postgres"
        session_id: Session identifier for isolation
        agent_id: Optional agent identifier within session (Postgres only)
        **kwargs: Backend-specific options
            - db_path: For SQLite (Path) - custom database location
            - connection_string: For Postgres (str) - overrides AGENTICA_POSTGRES_URL

    Returns:
        MemoryBackend implementation (satisfies Protocol)

    Raises:
        ValueError: If backend type is unknown
        ImportError: If required backend dependencies not installed

    Examples:
        # SQLite with custom path
        memory = await create_memory_service(
            "sqlite",
            session_id="test-123",
            db_path=Path("/tmp/test.db")
        )

        # PostgreSQL with agent scoping
        memory = await create_memory_service(
            "postgres",
            session_id="prod-abc",
            agent_id="agent-1"
        )
    """
```

#### get_default_backend

```python
def get_default_backend() -> Literal["sqlite", "postgres"]:
    """Get default backend from environment.

    Reads from AGENTICA_MEMORY_BACKEND environment variable.

    Defaults:
        AGENTICA_MEMORY_BACKEND=sqlite (default, development)
        AGENTICA_MEMORY_BACKEND=postgres (production)

    Returns:
        Backend type

    Raises:
        ValueError: If invalid backend specified
        ImportError: If backend dependencies not available
    """
```

#### create_default_memory_service

```python
async def create_default_memory_service(
    session_id: str = "default",
    agent_id: str | None = None
) -> MemoryBackend:
    """Create memory service using environment config.

    Automatically selects backend based on AGENTICA_MEMORY_BACKEND env var.

    Args:
        session_id: Session identifier for isolation
        agent_id: Optional agent identifier within session

    Returns:
        MemoryBackend implementation

    Raises:
        ValueError: If invalid backend specified in environment
        ImportError: If required backend dependencies not installed

    Example:
        # Set in environment or .env
        AGENTICA_MEMORY_BACKEND=postgres

        # In code
        memory = await create_default_memory_service(session_id="my-session")
    """
```

## Backend Comparison

| Feature | SQLite | PostgreSQL |
|---------|--------|------------|
| **Setup** | Zero config | Docker/managed service required |
| **Dependencies** | `aiosqlite` | `asyncpg`, `pgvector` |
| **Concurrent writes** | Limited (WAL mode) | Full MVCC (unlimited) |
| **Connection pooling** | Not used (file-based) | Global asyncpg pool |
| **Full-text search** | FTS5 (BM25 ranking) | PostgreSQL FTS (ts_rank) |
| **Vector search** | Not supported | pgvector (cosine similarity) |
| **Hybrid search** | Not supported | FTS + vector + RRF |
| **Metadata queries** | JSON text field | JSONB with indexing |
| **Agent scoping** | Session only | Session + agent_id |
| **Database file** | `.claude/cache/agentica-memory/memory.db` | PostgreSQL database |
| **Performance (single agent)** | Fast (in-process) | Slightly slower (network) |
| **Performance (multi-agent)** | Bottleneck under concurrency | Scales linearly |
| **Best for** | Development, single agent, testing | Production, multi-agent swarms |
| **Cost** | Free | Infrastructure cost |

### When to Use Each Backend

**Use SQLite when**:
- Local development and testing
- Single-agent prototypes
- Demos and examples
- No concurrent write operations
- Zero infrastructure is a requirement

**Use PostgreSQL when**:
- Production deployments
- Multi-agent systems (agent swarms)
- High concurrency workloads
- Vector search is needed
- Agent-specific memory scoping required
- Infrastructure is already available

### Migration Path: SQLite → PostgreSQL

**Development workflow**:
```python
# .env.development
AGENTICA_MEMORY_BACKEND=sqlite

# Code (no changes needed)
memory = await create_default_memory_service(session_id="dev")
```

**Production deployment**:
```python
# .env.production
AGENTICA_MEMORY_BACKEND=postgres
AGENTICA_POSTGRES_URL=postgresql://user:pass@prod-db:5432/agentica

# Same code (no changes needed)
memory = await create_default_memory_service(session_id="prod")
```

**Data migration** (if needed):
```bash
# Export from SQLite
uv run python scripts/export_sqlite_memory.py > backup.json

# Import to Postgres
uv run python scripts/import_postgres_memory.py < backup.json
```

## Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                      Application Layer                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Agent Code / Scripts                                    │  │
│  │  - Uses MemoryBackend Protocol methods                   │  │
│  │  - No backend-specific logic                             │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────┬───────────────────────────────────────────┘
                     │ await create_memory_service(backend, ...)
                     ▼
┌────────────────────────────────────────────────────────────────┐
│                      Factory Layer                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  memory_factory.py                                       │  │
│  │  - Backend selection (explicit or env-based)             │  │
│  │  - Dependency validation                                 │  │
│  │  - Helpful error messages                                │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────┬─────────────────────────┬─────────────────────────┬─┘
           │                         │                         │
    backend="sqlite"          backend="postgres"    AGENTICA_MEMORY_BACKEND
           │                         │
           ▼                         ▼
┌─────────────────────┐    ┌──────────────────────────┐
│  SQLite Backend     │    │  PostgreSQL Backend      │
│  ┌───────────────┐  │    │  ┌────────────────────┐  │
│  │MemoryService  │  │    │  │MemoryServicePG     │  │
│  │               │  │    │  │                    │  │
│  │ - aiosqlite   │  │    │  │ - asyncpg          │  │
│  │ - FTS5        │  │    │  │ - pgvector         │  │
│  │ - WAL mode    │  │    │  │ - Connection pool  │  │
│  └───────────────┘  │    │  └────────────────────┘  │
└──────────┬──────────┘    └────────────┬─────────────┘
           │                            │
           │   Satisfies Protocol       │
           └────────────┬───────────────┘
                        ▼
         ┌──────────────────────────────┐
         │   MemoryBackend Protocol     │
         │   (memory_protocol.py)       │
         │                              │
         │   Defines async interface:   │
         │   - set_core / get_core      │
         │   - store / search           │
         │   - recall / to_context      │
         │   - connect / close          │
         └──────────────────────────────┘

         ┌──────────────────────────────┐
         │   PostgreSQL Connection      │
         │   Pool (postgres_pool.py)    │
         │                              │
         │   - Global singleton pool    │
         │   - asyncio.Lock protection  │
         │   - Lazy initialization      │
         │   - Context managers         │
         │   - Transaction support      │
         └──────────────────────────────┘
```

### Connection Management

**SQLite** (Direct Connection per Operation):
```
Operation → _get_conn() → aiosqlite.connect() → Execute → Commit → Close
                           ↓
                    WAL mode enabled
                    Row factory set
```

**PostgreSQL** (Global Connection Pool):
```
Application Start
    ↓
get_pool() → Create asyncpg.Pool (lazy, singleton)
    ↓
[Global pool with asyncio.Lock]
    ↓
Operation → get_connection() → Pool.acquire() → Execute → Release
                                    ↓
                            Connection reused across operations
```

## PostgreSQL-Specific Features

### Vector Search Methods

These methods are **extensions** not in the core `MemoryBackend` Protocol. Available only on PostgreSQL backend.

#### search_vector

Pure vector similarity search using cosine distance.

```python
async def search_vector(
    query_embedding: list[float],
    limit: int = 10
) -> list[dict[str, Any]]:
    """Search archival memory with vector similarity.

    Args:
        query_embedding: Query embedding (will be padded to 4096)
        limit: Max results to return

    Returns:
        List of matching facts with similarity scores (0.0 to 1.0)
    """
```

**Example**:
```python
# Check if backend supports vector search
if hasattr(memory, 'search_vector'):
    # Get embedding from your provider (OpenAI, Voyage, etc.)
    query_embedding = await embedding_service.embed("authentication errors")

    results = await memory.search_vector(query_embedding, limit=5)
    for result in results:
        print(f"Similarity: {result['similarity']:.3f}")
        print(f"Content: {result['content']}")
```

#### search_hybrid

Weighted combination of FTS and vector search.

```python
async def search_hybrid(
    text_query: str,
    query_embedding: list[float],
    limit: int = 10,
    text_weight: float = 0.3,
    vector_weight: float = 0.7
) -> list[dict[str, Any]]:
    """Hybrid search combining full-text search and vector similarity.

    Combined score = (text_weight * fts_rank) + (vector_weight * similarity)

    Args:
        text_query: Text query for FTS
        query_embedding: Query embedding for vector search
        limit: Max results to return
        text_weight: Weight for text search score
        vector_weight: Weight for vector similarity

    Returns:
        List with text_rank, similarity, and combined_score
    """
```

#### search_hybrid_rrf (Recommended)

Reciprocal Rank Fusion - more robust than weighted combination.

```python
async def search_hybrid_rrf(
    text_query: str,
    query_embedding: list[float],
    limit: int = 10,
    k: int = 60
) -> list[dict[str, Any]]:
    """Hybrid search using Reciprocal Rank Fusion.

    RRF score = 1/(k + rank_fts) + 1/(k + rank_vector)

    More robust than weighted combination because:
    - Rank-based, not score-based (solves normalization)
    - Less sensitive to weight tuning
    - Works when one modality has no results

    Args:
        text_query: Text query for FTS
        query_embedding: Query embedding for vector search
        limit: Max results to return
        k: RRF constant (default 60)

    Returns:
        List with rrf_score
    """
```

**Example**:
```python
# RRF hybrid search (recommended)
results = await memory.search_hybrid_rrf(
    text_query="authentication bug",
    query_embedding=await embedding_service.embed("authentication bug"),
    limit=10,
    k=60  # Standard RRF constant
)

for result in results:
    print(f"RRF Score: {result['rrf_score']:.4f}")
    print(f"Content: {result['content']}")
```

### Advanced Vector Operations

#### search_vector_with_threshold

Filter by minimum similarity threshold.

```python
results = await memory.search_vector_with_threshold(
    query_embedding=embedding,
    threshold=0.7,  # Only return results with similarity >= 0.7
    limit=10
)
```

#### search_vector_with_filter

Filter by metadata before vector search.

```python
results = await memory.search_vector_with_filter(
    query_embedding=embedding,
    metadata_filter={"severity": "high", "module": "auth"},
    limit=10
)
```

### Agent Scoping

PostgreSQL supports agent-specific memory within a session:

```python
# Coordinator agent
coordinator = await create_memory_service(
    "postgres",
    session_id="swarm-001",
    agent_id="coordinator"
)
await coordinator.set_core("role", "Coordinate tasks")

# Worker agent
worker = await create_memory_service(
    "postgres",
    session_id="swarm-001",
    agent_id="worker-1"
)
await worker.set_core("role", "Execute task")

# Each agent has isolated core memory
# Archival memory can be shared (same session_id)
```

## Extending the System

### Adding a New Backend

To add support for a new backend (e.g., Redis, DynamoDB):

**Step 1**: Implement the `MemoryBackend` Protocol

```python
# scripts/agentica/memory_service_redis.py
from scripts.agentica.memory_protocol import MemoryBackend

class MemoryServiceRedis:
    """Redis-backed memory service."""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self._redis = None

    async def connect(self) -> None:
        import aioredis
        self._redis = await aioredis.create_redis_pool("redis://localhost")

    async def close(self) -> None:
        if self._redis:
            self._redis.close()
            await self._redis.wait_closed()

    # Implement all Protocol methods...
    async def set_core(self, key: str, value: str) -> None:
        await self._redis.hset(f"core:{self.session_id}", key, value)

    async def get_core(self, key: str) -> str | None:
        value = await self._redis.hget(f"core:{self.session_id}", key)
        return value.decode() if value else None

    # ... implement remaining methods
```

**Step 2**: Add to factory

```python
# scripts/agentica/memory_factory.py
BackendType = Literal["sqlite", "postgres", "redis"]

async def create_memory_service(
    backend: BackendType = "sqlite",
    session_id: str = "default",
    agent_id: str | None = None,
    **kwargs: Any
) -> MemoryBackend:
    # ... existing backends

    elif backend == "redis":
        try:
            from .memory_service_redis import MemoryServiceRedis
        except ImportError as e:
            raise ImportError(
                "Redis backend requires: uv pip install aioredis\n"
                f"Original error: {e}"
            ) from e

        service = MemoryServiceRedis(session_id=session_id)
        await service.connect()
        return service
```

**Step 3**: Validate with mypy

```bash
uv run mypy scripts/agentica/memory_service_redis.py --strict
```

**Step 4**: Add tests

```python
# tests/unit/test_memory_backend_factory.py
@pytest.mark.asyncio
async def test_factory_creates_redis_backend(tmp_path):
    memory = await create_memory_service("redis", session_id="test")
    assert isinstance(memory, MemoryServiceRedis)
    await memory.close()
```

### Custom Embedding Providers

PostgreSQL backend uses the `EmbeddingProvider` Protocol for embedding generation.

**Define custom provider**:

```python
from scripts.agentica.memory_service_pg import EmbeddingProvider

class VoyageEmbedder:
    """Voyage AI embedding provider."""

    def __init__(self, api_key: str):
        import voyageai
        self.client = voyageai.Client(api_key=api_key)

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        result = await self.client.embed([text], model="voyage-2")
        return result.embeddings[0]

    @property
    def dimension(self) -> int:
        """Voyage-2 dimension."""
        return 1024
```

**Use with memory service**:

```python
embedder = VoyageEmbedder(api_key=os.environ["VOYAGE_API_KEY"])

# Store with auto-generated embedding
memory_id = await memory.store_with_embedding(
    "User prefers asynchronous code",
    metadata={"category": "preference"},
    embedder=embedder
)

# Search with vector similarity
query_embedding = await embedder.embed("code preferences")
results = await memory.search_vector(query_embedding, limit=5)
```

**Supported embedding providers**:
- OpenAI (`text-embedding-3-small`, `text-embedding-3-large`)
- Voyage AI (`voyage-2`, `voyage-code-2`)
- Local models (sentence-transformers)
- Custom providers (implement `EmbeddingProvider` Protocol)

## Troubleshooting

### Common Issues

#### "ModuleNotFoundError: No module named 'aiosqlite'"

**Cause**: SQLite backend dependencies not installed.

**Solution**:
```bash
uv pip install aiosqlite
```

#### "ModuleNotFoundError: No module named 'asyncpg'"

**Cause**: PostgreSQL backend dependencies not installed.

**Solution**:
```bash
uv pip install asyncpg pgvector
```

#### "ValueError: Invalid AGENTICA_MEMORY_BACKEND: xyz"

**Cause**: Environment variable set to unsupported backend.

**Solution**: Set to either `sqlite` or `postgres`:
```bash
export AGENTICA_MEMORY_BACKEND=sqlite  # or postgres
```

#### "Connection refused" (PostgreSQL)

**Cause**: PostgreSQL server not running or connection URL incorrect.

**Solution**:
```bash
# Check if Postgres is running
docker ps | grep postgres

# Start Postgres if needed
./docker/start-postgres.sh

# Verify connection URL
echo $AGENTICA_POSTGRES_URL
```

#### "database is locked" (SQLite)

**Cause**: Multiple processes trying to write simultaneously. SQLite WAL mode helps but doesn't eliminate the issue.

**Solution**: Switch to PostgreSQL for concurrent workloads:
```bash
export AGENTICA_MEMORY_BACKEND=postgres
```

#### "Vector dimension mismatch"

**Cause**: Embedding dimension doesn't match database column (expects 4096).

**Solution**: Embeddings are automatically padded to 4096 dimensions. No action needed.

#### "No search results" with vector search

**Cause**: Memories stored without embeddings.

**Solution**: Store memories with embeddings:
```python
embedding = await embedder.embed(content)
await memory.store(content, embedding=embedding)
```

### Debug Tips

**Enable SQL logging** (SQLite):
```python
# Add to memory_service.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Check database file** (SQLite):
```bash
# Verify file exists
ls -lh .claude/cache/agentica-memory/memory.db

# Inspect schema
sqlite3 .claude/cache/agentica-memory/memory.db ".schema"

# Count records
sqlite3 .claude/cache/agentica-memory/memory.db "SELECT COUNT(*) FROM archival_memory;"
```

**Check Postgres connection**:
```bash
# Test connection
psql $AGENTICA_POSTGRES_URL -c "SELECT version();"

# Check tables
psql $AGENTICA_POSTGRES_URL -c "\dt"

# Inspect data
psql $AGENTICA_POSTGRES_URL -c "SELECT COUNT(*) FROM archival_memory;"
```

## Testing

### Running Tests

**All factory tests**:
```bash
uv run pytest tests/unit/test_memory_backend_factory.py -v
```

**SQLite-specific tests**:
```bash
uv run pytest tests/unit/test_memory_service.py -v
```

**PostgreSQL-specific tests** (requires running Postgres):
```bash
# Start Postgres first
./docker/start-postgres.sh

# Run tests
uv run pytest tests/unit/test_memory_service_pg.py -v
```

### Test Strategy

**Protocol validation**: Tests verify both backends satisfy `MemoryBackend` Protocol
**Mock strategy**:
- SQLite: Uses real `aiosqlite` with `tmp_path` (lightweight, fast)
- Postgres: Skipped if dependencies unavailable (graceful degradation)

**Example test**:
```python
@pytest.mark.asyncio
async def test_protocol_core_memory_sqlite(tmp_path):
    """Verify SQLite backend satisfies MemoryBackend Protocol."""
    memory = await create_memory_service(
        "sqlite",
        session_id="test",
        db_path=tmp_path / "test.db"
    )

    # Test core memory operations
    await memory.set_core("key", "value")
    assert await memory.get_core("key") == "value"

    # Test archival memory
    mem_id = await memory.store("Test fact")
    results = await memory.search("Test", limit=5)
    assert len(results) > 0

    await memory.close()
```

### Mock Strategy for Postgres

For unit tests that don't require a real database:

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_postgres_mock():
    """Test Postgres backend with mocked pool."""
    with patch('scripts.agentica.postgres_pool.get_pool') as mock_pool, \
         patch('scripts.agentica.postgres_pool.get_connection') as mock_conn:

        # Setup mock connection
        mock_connection = AsyncMock()
        mock_conn.return_value.__aenter__.return_value = mock_connection
        mock_connection.fetchrow.return_value = {"value": "test"}

        # Create service (uses mocked pool)
        memory = await create_memory_service("postgres", session_id="test")
        result = await memory.get_core("key")
        assert result == "test"
```

## Performance Characteristics

### SQLite Performance

**Single agent workload**:
- Core memory operations: ~1-2ms
- Archival store: ~2-5ms
- FTS5 search: ~5-20ms (depends on dataset size)
- Recall (combined): ~10-30ms

**Concurrent agents** (bottleneck):
- Write serialization due to file locking
- WAL mode helps but doesn't eliminate contention
- Recommended: < 5 concurrent agents

### PostgreSQL Performance

**Single agent workload**:
- Core memory operations: ~3-5ms (network overhead)
- Archival store: ~5-10ms
- FTS search: ~10-30ms
- Vector search: ~20-50ms (depends on index)
- Hybrid RRF: ~30-80ms

**Concurrent agents** (scales well):
- No write serialization (MVCC)
- Connection pool reduces overhead
- Scales linearly with agent count
- Recommended: 10-100+ concurrent agents

### Optimization Tips

**SQLite**:
- Use WAL mode (enabled by default)
- Keep database file on SSD
- Limit concurrent writes
- Consider sharding by session_id for multi-agent systems

**PostgreSQL**:
- Tune connection pool size (`max_size` in `postgres_pool.py`)
- Create indexes on frequently queried metadata fields
- Use vector indexes for large embedding datasets (HNSW or IVFFlat)
- Monitor query performance with `EXPLAIN ANALYZE`

## References

### Related Documentation

- [Agentica Memory Service](../scripts/agentica/README.md) - Implementation details
- [PostgreSQL Pool](../scripts/agentica/postgres_pool.py) - Connection pooling
- [MCP Scripts](../scripts/README.md) - Integration with MCP tools

### External Resources

- [Protocol (PEP 544)](https://peps.python.org/pep-0544/) - Structural subtyping
- [aiosqlite](https://aiosqlite.omnilib.dev/) - Async SQLite wrapper
- [asyncpg](https://magicstack.github.io/asyncpg/) - Async PostgreSQL driver
- [pgvector](https://github.com/pgvector/pgvector) - Vector similarity search
- [SQLite FTS5](https://www.sqlite.org/fts5.html) - Full-text search
- [Letta Memory Architecture](https://github.com/cpacker/Letta) - Inspiration for three-layer memory

### Research Documents

- [Backend Factory Research](../thoughts/shared/work/backend-factory/research.md) - Why Protocol pattern
- [Implementation Plan](../thoughts/shared/work/backend-factory/plan.md) - Design decisions
- [Implementation Summary](../thoughts/shared/work/backend-factory/implementation.md) - What was built
- [Review](../thoughts/shared/work/backend-factory/review.md) - Final assessment

---

**Last Updated**: 2025-12-27
**Version**: 1.0
**Status**: Stable

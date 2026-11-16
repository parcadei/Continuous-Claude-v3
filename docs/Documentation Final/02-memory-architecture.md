# Memory Architecture

The Agentica memory system provides a Letta/MemGPT-inspired architecture for agent memory management, supporting both development (SQLite) and production (PostgreSQL with pgvector) backends.

## Overview

The memory architecture implements a three-tier memory model:

1. **Core Memory** - Key-value store for in-context persistent facts (persona, task, context)
2. **Archival Memory** - Long-term searchable storage with full-text search and vector similarity
3. **Recall Memory** - Query interface that combines both sources for retrieval

This design is inspired by [Letta/MemGPT](https://docs.letta.com/memory), where agents maintain persistent state across conversations through structured memory tiers.

## Architecture Diagram

```
                    +-------------------+
                    |   Memory Factory  |
                    | create_memory_    |
                    | service()         |
                    +--------+----------+
                             |
              +--------------+--------------+
              |                             |
    +---------v---------+        +----------v----------+
    |   MemoryService   |        |  MemoryServicePG    |
    |     (SQLite)      |        |   (PostgreSQL)      |
    +-------------------+        +---------------------+
    | - aiosqlite       |        | - asyncpg           |
    | - FTS5 search     |        | - pgvector          |
    | - WAL mode        |        | - Hybrid search     |
    +-------------------+        +---------------------+
              |                             |
              +-------------+---------------+
                            |
                  +---------v---------+
                  |  MemoryBackend    |
                  |    (Protocol)     |
                  +-------------------+
                  | Core Memory Ops   |
                  | Archival Ops      |
                  | Recall Ops        |
                  | Lifecycle Ops     |
                  +-------------------+
```

## Components

### Memory Protocol (`memory_protocol.py`)

Defines the `MemoryBackend` Protocol that all implementations must satisfy:

```python
class MemoryBackend(Protocol):
    """Protocol for memory service backends."""

    # Core Memory Operations
    async def set_core(self, key: str, value: str) -> None: ...
    async def get_core(self, key: str) -> str | None: ...
    async def list_core_keys(self) -> list[str]: ...
    async def delete_core(self, key: str) -> None: ...
    async def get_all_core(self) -> dict[str, str]: ...

    # Archival Memory Operations
    async def store(self, content: str, metadata: dict | None = None,
                   embedding: list[float] | None = None) -> str: ...
    async def search(self, query: str, limit: int = 10) -> list[dict]: ...
    async def delete_archival(self, memory_id: str) -> None: ...

    # Recall Operations
    async def recall(self, query: str, include_core: bool = True,
                    limit: int = 5) -> str: ...
    async def to_context(self, max_archival: int = 10) -> str: ...

    # Lifecycle Management
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
```

### Memory Service - SQLite (`memory_service.py`)

Development-optimized implementation using SQLite with FTS5 for full-text search.

**Features:**
- **WAL Mode** - Write-ahead logging for concurrent reads
- **FTS5 Search** - Porter-stemmed full-text indexing with BM25 ranking
- **Session Isolation** - Each session gets its own memory namespace
- **Automatic Triggers** - FTS index stays in sync with content tables

**Database Schema:**
```sql
-- Core Memory (key-value)
CREATE TABLE core_memory (
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (session_id, key)
);

-- Archival Memory
CREATE TABLE archival_memory (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT,
    created_at REAL NOT NULL
);

-- FTS5 Virtual Table
CREATE VIRTUAL TABLE archival_fts USING fts5(
    content,
    content='archival_memory',
    content_rowid='rowid',
    tokenize='porter'
);
```

### Memory Service - PostgreSQL (`memory_service_pg.py`)

Production-optimized implementation with PostgreSQL and pgvector for vector similarity search.

**Features:**
- **Connection Pooling** - Shared asyncpg pool with 2-10 connections
- **Vector Search** - pgvector extension with cosine similarity
- **Hybrid Search** - Combines FTS and vector similarity with configurable weights
- **RRF Fusion** - Reciprocal Rank Fusion for robust result merging
- **Agent Scoping** - Optional agent_id for per-agent memory isolation

**Additional Search Methods:**
```python
# Full-text search
results = await memory.search_text(query, limit=10)

# Vector similarity search
results = await memory.search_vector(query_embedding, limit=10)

# Hybrid search (weighted combination)
results = await memory.search_hybrid(
    text_query="Python framework",
    query_embedding=embedding,
    limit=10,
    text_weight=0.3,
    vector_weight=0.7
)

# Hybrid search with Reciprocal Rank Fusion
results = await memory.search_hybrid_rrf(
    text_query="Python framework",
    query_embedding=embedding,
    limit=10,
    k=60  # RRF constant
)
```

**R-Flow Scoping Model:**
- `session_id` - Claude Code session identifier
- `agent_id` - Optional agent within session (for multi-agent scenarios)

### Memory Factory (`memory_factory.py`)

Factory pattern for backend instantiation with environment-based configuration.

```python
from scripts.agentica.memory_factory import (
    create_memory_service,
    create_default_memory_service,
    get_default_backend
)

# Explicit backend selection
memory = await create_memory_service(
    backend="sqlite",  # or "postgres"
    session_id="my-session",
    agent_id="agent-1"  # optional
)

# Environment-based selection (reads AGENTICA_MEMORY_BACKEND)
memory = await create_default_memory_service(session_id="my-session")
```

**Environment Variables:**
- `AGENTICA_MEMORY_BACKEND` - "sqlite" (default) or "postgres"
- `AGENTICA_POSTGRES_URL` - PostgreSQL connection string (required in production)
- `AGENTICA_ENV` - Set to "production" to require explicit config

## Embedding Service (`embedding_service.py`)

Provides embedding generation for archival memory with multiple provider support.

### Supported Providers

| Provider | Model | Dimension | Notes |
|----------|-------|-----------|-------|
| **OpenAI** | text-embedding-3-small | 1536 | Production default |
| **Voyage** | voyage-3, voyage-code-3 | 1024 | Code-optimized variant |
| **Local** | all-MiniLM-L6-v2 | 384 | No API calls, offline |
| **Mock** | Deterministic hash | 1536 | Testing only |

### Usage

```python
from scripts.agentica.embedding_service import EmbeddingService

# OpenAI embeddings (requires OPENAI_API_KEY)
embedder = EmbeddingService(provider="openai")
embedding = await embedder.embed("Some text to embed")

# Voyage embeddings (requires VOYAGE_API_KEY)
embedder = EmbeddingService(provider="voyage-code-3")

# Local embeddings (no API key needed)
embedder = EmbeddingService(provider="local")

# Batch embedding with caching
embeddings = await embedder.embed_batch(["Text 1", "Text 2", "Text 3"])

# Check cache stats
print(f"Cached: {embedder.cache_size()}")
embedder.clear_cache()
```

### Features

- **Content-based Caching** - SHA-256 hash of text prevents duplicate API calls
- **Batch Processing** - Automatic chunking for API rate limits
- **Retry Logic** - Exponential backoff on transient failures
- **Thread-safe** - AsyncIO lock for cache access

## Vector Search and Reranking (`reranker.py`)

Two-stage retrieval pattern for precise semantic search:

1. **Fast Retrieval** - Vector search returns broad candidate set (50-100 documents)
2. **Precise Reranking** - Cross-encoder scores top candidates (5-20 final results)

### Reranker Providers

| Provider | Model | Speed | Notes |
|----------|-------|-------|-------|
| **Local** | cross-encoder/ms-marco-MiniLM-L-12-v2 | ~250ms/100 docs | CPU-based |
| **Cohere** | rerank-english-v3.0 | API call | Higher quality |

### Usage

```python
from scripts.agentica.reranker import get_reranker, RankedDocument

# Local reranker (no API key)
reranker = get_reranker("local")
results = await reranker.rerank(
    query="Python web framework",
    documents=["FastAPI is modern...", "Django is batteries..."],
    top_k=10
)

# Cohere API reranker
reranker = get_reranker("cohere", api_key="...")
results = await reranker.rerank(query, documents, top_k=10)

# Access results
for doc in results:
    print(f"Score: {doc.score:.3f} | {doc.content[:50]}...")
```

## Memory Backfill (`memory_backfill.py`)

Populates memory from Braintrust session traces using a 6-stage pipeline:

```
1. Fetch    - Raw spans from Braintrust API
2. Parse    - Extract structured facts from spans
3. Dedupe   - Filter to novel facts (content hash)
4. Enrich   - Add type metadata
5. Embed    - Generate embeddings (cached)
6. Store    - Upsert to memory service
```

### Fact Types

| Type | Source | Example |
|------|--------|---------|
| `GOAL` | Turn 1 input, ledger | Session goal from user prompt |
| `DECISION` | LLM spans, handoff | "Chose FastAPI over Flask because..." |
| `FILE_CHANGE` | Write/Edit tools | "Modified src/api.py" |
| `OUTCOME` | Ledger, context.db | "SUCCEEDED" or "FAILED" |
| `ERROR` | Bash span output | "ModuleNotFoundError: numpy" |
| `LEARNING` | LLM extraction | General learnings |

### LLM Span Memory Model

Fine-grained memory per LLM span for per-turn granularity:

```python
@dataclass
class LLMSpanMemory:
    span_id: str
    turn_number: int
    session_id: str
    user_intent: str      # What user asked
    decision: str         # What agent decided
    tools_called: list[str]
    files_touched: list[str]
    outcome: str | None
    error_summary: str | None
    embedding: list[float] | None
```

### CLI Usage

```bash
# Single session
uv run python -m runtime.harness scripts/agentica/memory_backfill.py \
    --session-id abc123

# Date range
uv run python -m runtime.harness scripts/agentica/memory_backfill.py \
    --start-date 2025-12-20 --end-date 2025-12-27

# With two-pass extraction for large sessions
uv run python -m runtime.harness scripts/agentica/memory_backfill.py \
    --session-id abc123 --use-two-pass

# Resume interrupted backfill
uv run python -m runtime.harness scripts/agentica/memory_backfill.py \
    --resume
```

## PostgreSQL Pool (`postgres_pool.py`)

Connection pooling layer for PostgreSQL backend.

### Features

- **Global Singleton** - Thread-safe pool shared across services
- **Lazy Initialization** - Pool created on first use
- **Health Checks** - Verify pool connectivity
- **Transaction Support** - Context manager with auto-commit/rollback
- **Retry with Backoff** - Handles transient connection failures

### Usage

```python
from scripts.agentica.postgres_pool import (
    get_pool,
    get_connection,
    get_transaction,
    health_check,
    close_pool
)

# Raw pool access
pool = await get_pool()
async with pool.acquire() as conn:
    rows = await conn.fetch("SELECT * FROM core_memory")

# Convenience context manager
async with get_connection() as conn:
    await conn.fetch(...)

# Transaction with auto-commit/rollback
async with get_transaction() as conn:
    await conn.execute("INSERT INTO ...")
    await conn.execute("UPDATE ...")
    # Auto-commits on success

# Health check
is_healthy, error = await health_check(log_errors=True)

# Cleanup
await close_pool()
```

### Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `AGENTICA_POSTGRES_URL` | Connection string | `postgresql://agentica:agentica_dev@localhost:5433/agentica_memory` |
| `AGENTICA_ENV` | Set to "production" to require explicit URL | development |

## Integration with Agents

### Basic Memory Usage

```python
from scripts.agentica.memory_factory import create_memory_service
from scripts.agentica.embedding_service import EmbeddingService

# Initialize
memory = await create_memory_service("postgres", session_id="agent-session")
embedder = EmbeddingService(provider="openai")

# Set core context
await memory.set_core("persona", "You are an expert Python developer")
await memory.set_core("task", "Build a REST API with FastAPI")

# Store learnings with embeddings
content = "User prefers type hints and async/await patterns"
embedding = await embedder.embed(content)
await memory.store(content, metadata={"source": "conversation"}, embedding=embedding)

# Recall for context injection
context = await memory.recall("What are the user's preferences?")
# Returns: "[Core/task]: Build a REST API...\n[Archival]: User prefers type hints..."

# Generate full context for prompt
full_context = await memory.to_context(max_archival=10)
# Returns formatted markdown with Core Memory and Recent Archival
```

### With LLM Span Memory

```python
from scripts.agentica.memory_backfill import (
    extract_llm_span_memories,
    store_llm_span_memory
)

# Extract memories from Braintrust spans
spans = await fetch_session_spans(session_id, project_id, api_key)
memories = extract_llm_span_memories(spans, session_id)

# Embed and store
for mem in memories:
    mem.embedding = await embedder.embed(mem.embedding_text)
    await store_llm_span_memory(memory, mem)
```

### Two-Pass Span Processing

For large sessions (>50 spans), use the SpanProcessor for efficient extraction:

```python
from scripts.agentica.span_processor import SpanProcessor

processor = SpanProcessor(
    session_id="abc123",
    embedding_provider="openai",
    num_mappers=4,
    max_chunk_size=50
)
result = await processor.process(spans)

print(f"Summaries: {result.summaries_persisted}")
print(f"Decisions: {result.decisions_persisted}")
```

## Best Practices

### 1. Choose the Right Backend

- **SQLite** - Development, testing, single-agent scenarios
- **PostgreSQL** - Production, multi-agent, vector search requirements

### 2. Use Embeddings for Semantic Search

```python
# Without embeddings - keyword matching only
results = await memory.search("Python framework")

# With embeddings - semantic similarity
embedding = await embedder.embed("Python framework")
results = await memory.search_vector(embedding, limit=10)

# Best of both - hybrid search
results = await memory.search_hybrid(
    "Python framework", embedding,
    text_weight=0.3, vector_weight=0.7
)
```

### 3. Deduplicate with Content Hashes

The backfill system uses content hashes for deduplication:

```python
from scripts.agentica.memory_backfill import content_hash

# Same semantic content = same hash
hash1 = content_hash("User prefers Python", {"type": "preference"})
hash2 = content_hash("user prefers python", {"type": "preference"})
assert hash1 == hash2  # Normalized content
```

### 4. Scope Memory Appropriately

```python
# Session-level memory (shared across agents)
memory = await create_memory_service("postgres", session_id="session-123")

# Agent-specific memory (isolated)
memory = await create_memory_service(
    "postgres",
    session_id="session-123",
    agent_id="research-agent"
)
```

### 5. Use Reranking for Precision

```python
# Broad retrieval
candidates = await memory.search_vector(embedding, limit=50)

# Precise reranking
reranker = get_reranker("local")
top_results = await reranker.rerank(
    query="Python async patterns",
    documents=[c["content"] for c in candidates],
    top_k=5
)
```

## Related Files

- `scripts/agentica/memory_service.py` - SQLite implementation
- `scripts/agentica/memory_service_pg.py` - PostgreSQL implementation
- `scripts/agentica/memory_factory.py` - Factory and backend selection
- `scripts/agentica/memory_protocol.py` - Protocol definition
- `scripts/agentica/embedding_service.py` - Embedding generation
- `scripts/agentica/memory_backfill.py` - Braintrust trace extraction
- `scripts/agentica/reranker.py` - Cross-encoder reranking
- `scripts/agentica/postgres_pool.py` - Connection pooling
- `scripts/agentica/span_processor.py` - Two-pass span extraction

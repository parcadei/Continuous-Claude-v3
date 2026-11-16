# Memory System User Guide

## Overview

The Agentica memory system provides agents with persistent memory capabilities across sessions. It implements a three-tier architecture inspired by Letta/MemGPT:

- **Core Memory**: Key-value blocks for current session context (persona, task, state)
- **Archival Memory**: Long-term searchable storage with full-text search and vector similarity
- **Recall Memory**: Query interface combining both sources for context retrieval

The system supports:
- Memory auto-wiring via `tracked_spawn()` (enabled by default)
- Datetime filtering for temporal queries
- Tag filtering with "any" or "all" match modes
- Conversation search across message history
- Block dataclass for structured core memory (Letta-compatible)
- RRF hybrid search combining FTS and vector similarity

## Quick Start

### Automatic Memory (Default)

Agents spawned via `tracked_spawn()` automatically have memory functions injected into their scope:

```python
from scripts.agentica_patterns.tracked_agent import tracked_spawn
from scripts.agentica_patterns.coordination import CoordinationDB

# Memory is automatically wired - no additional setup needed
agent = await tracked_spawn(db=db, premise="Research Python web frameworks")

# Agent scope now has these functions available:
# scope["remember"](key, value)       - Store in core memory
# scope["recall"](query)              - Search all memory sources
# scope["store_fact"](content, tags)  - Store in archival memory
# scope["search_memory"](query, ...)  - Full-text search with filtering
```

The auto-wiring uses `CLAUDE_SESSION_ID` from environment for session isolation, falling back to an agent-based ID if not set.

### Manual Memory Setup

For fine-grained control, create a unified scope directly:

```python
from scripts.agentica_patterns.unified_scope import create_unified_scope
from agentica import spawn

scope = create_unified_scope(
    session_id="my-session",
    enable_memory=True,
    enable_tasks=True,
)

agent = await spawn(premise="...", scope=scope)
```

## Core Memory Operations

Core memory stores key-value pairs that are always available in context. Use for persona, current task, and session state.

### remember(key, value)

Store a key-value pair in core memory:

```python
scope["remember"]("persona", "You are a senior Python developer")
scope["remember"]("current_task", "Build a REST API with FastAPI")
scope["remember"]("code_style", "Use type hints and docstrings")
```

### recall(query, start_date=None, end_date=None)

Query all memory sources (core + archival):

```python
# Basic recall
context = scope["recall"]("What is my current task?")

# With datetime filtering
context = scope["recall"](
    "meeting notes",
    start_date="2025-01-01",
    end_date="2025-12-31"
)

# Returns formatted string combining:
# [Core/current_task]: Build a REST API with FastAPI
# [Archival]: User requested async endpoints
```

Dates can be provided in ISO format: `YYYY-MM-DD` or full ISO 8601 (`2025-12-31T10:30:00`).

## Archival Memory Operations

Archival memory provides long-term searchable storage with optional tags and embeddings.

### store_fact(content, tags=None)

Store a fact in archival memory:

```python
# Simple storage
mem_id = scope["store_fact"]("User prefers pytest over unittest")

# With tags for categorization
mem_id = scope["store_fact"](
    "Important decision: chose FastAPI for the API framework",
    tags=["important", "decision", "api"]
)

# Multiple tags enable flexible filtering later
mem_id = scope["store_fact"](
    "Bug found in authentication module",
    tags=["bug", "auth", "high-priority"]
)
```

### search_memory(query, limit=10, start_date=None, end_date=None, tags=None, tag_match_mode="any")

Full-text search with optional filtering:

```python
# Basic search
results = scope["search_memory"]("API framework", limit=5)

# Search with date range
results = scope["search_memory"](
    "meeting notes",
    start_date="2025-01-01",
    end_date="2025-06-30",
    limit=10
)

# Search with tag filtering - "any" mode (OR logic)
results = scope["search_memory"](
    "authentication",
    tags=["bug", "security"],
    tag_match_mode="any"  # Match facts with bug OR security tag
)

# Search with tag filtering - "all" mode (AND logic)
results = scope["search_memory"](
    "authentication",
    tags=["bug", "high-priority"],
    tag_match_mode="all"  # Match facts with BOTH tags
)
```

Results are returned as a list of dicts:

```python
[
    {
        "id": "uuid-string",
        "content": "Important decision: chose FastAPI...",
        "metadata": {"source": "conversation"},
        "created_at": datetime(...),
        "score": 0.85  # FTS relevance score
    },
    ...
]
```

## Conversation Search

For agents with conversation history, enable message search:

```python
scope = create_unified_scope(
    session_id="my-session",
    enable_memory=True,
    enable_messages=True,  # Enable conversation search
)
```

### store_message(content, role, metadata=None)

Store a conversation message:

```python
scope["store_message"]("How do I use async/await?", role="user")
scope["store_message"]("Async/await is used for...", role="assistant")
scope["store_message"]("Tool output: file written", role="tool")
```

### conversation_search(query, limit=10, roles=None, start_date=None, end_date=None)

Search conversation history:

```python
# Search all messages
results = scope["conversation_search"]("async programming", limit=10)

# Filter by role
results = scope["conversation_search"](
    "debugging",
    roles=["user", "assistant"],  # Exclude tool messages
    limit=10
)

# With date range
results = scope["conversation_search"](
    "API design",
    start_date="2025-12-01",
    end_date="2025-12-31",
    limit=20
)
```

## Block-Based Core Memory

For Letta-compatible structured core memory, use the Block dataclass:

```python
from scripts.agentica_patterns.memory_block import Block, BlockManager

# Create blocks with character limits
persona = Block(
    label="persona",
    value="I am a helpful Python developer assistant",
    limit=5000  # Default Letta limit
)

human = Block(
    label="human",
    value="User is Alice, a senior engineer at TechCorp",
    limit=5000
)

# Update blocks (enforces limit)
persona.update("I am an expert Python developer specializing in async code")

# Append to blocks
persona.append("\nI prefer type hints and docstrings.")

# Check remaining capacity
print(f"Remaining: {persona.remaining} characters")

# Use BlockManager for multiple blocks
manager = BlockManager()
manager.add_block(persona)
manager.add_block(human)

# Render for prompt injection (XML format)
core_memory_text = manager.to_core_memory_string()
# <persona>
# I am an expert Python developer...
# </persona>
#
# <human>
# User is Alice...
# </human>

# Serialize for storage
data = manager.to_dict()
restored = BlockManager.from_dict(data)
```

With PostgreSQL backend, blocks can be persisted:

```python
# Store block in core memory
await memory.set_block(persona)

# Retrieve block
restored = await memory.get_block("persona")

# Get all blocks
all_blocks = await memory.get_all_blocks()
```

## Vector-Enhanced Memory

For semantic search capabilities, enable vector memory:

```python
scope = create_unified_scope(
    session_id="my-session",
    enable_memory=True,
    enable_vector_memory=True,
    embedding_provider="openai",  # or "voyage", "local", "mock"
    enable_reranking=True,        # Optional: cross-encoder reranking
    reranker_provider="local",    # or "cohere"
)
```

### recall_vector(query, top_k=5, use_reranking=None)

Vector similarity search with optional reranking:

```python
# Basic vector recall
results = scope["recall_vector"]("Python async patterns", top_k=5)

# Override reranking setting
results = scope["recall_vector"](
    "authentication implementation",
    top_k=10,
    use_reranking=True  # Force reranking even if disabled by default
)
```

### remember_with_embedding(content, metadata=None)

Store facts with embeddings for vector search:

```python
mem_id = scope["remember_with_embedding"](
    "FastAPI uses Starlette for the web parts and Pydantic for data validation",
    metadata={"topic": "framework", "source": "documentation"}
)
```

## Advanced: Direct Memory Service Access

For advanced operations, access the underlying memory service:

```python
# Access memory service directly
memory = scope["_memory_service"]

# PostgreSQL-specific operations (if using postgres backend)
if hasattr(memory, "search_hybrid_rrf"):
    # RRF hybrid search
    embedding = await scope["_embedding_service"].embed("query")
    results = await memory.search_hybrid_rrf(
        text_query="Python framework",
        query_embedding=embedding,
        limit=10,
        k=60  # RRF constant
    )

# Tag operations
tags = await memory.get_tags(memory_id)
await memory.add_tag(memory_id, "reviewed")
await memory.remove_tag(memory_id, "draft")
all_tags = await memory.get_all_session_tags()
```

## Opting Out of Memory Auto-Wiring

To disable automatic memory injection:

```python
# Disable memory auto-wiring
agent = await tracked_spawn(
    db=db,
    premise="...",
    inject_memory=False  # No memory functions in scope
)

# Or provide custom scope (memory keys are protected)
agent = await tracked_spawn(
    db=db,
    premise="...",
    scope={"custom_tool": my_tool},  # Memory still added
    inject_memory=True  # Default
)
```

Note: Protected keys (`remember`, `recall`, `search_memory`, `store_fact`, `_memory_service`) cannot be overridden by user-provided scope.

## Backend Selection

The memory system supports two backends:

| Backend | Best For | Features |
|---------|----------|----------|
| **SQLite** | Development, testing | FTS5 search, WAL mode, zero config |
| **PostgreSQL** | Production, multi-agent | pgvector, hybrid search, RRF, connection pooling |

Configure via environment:

```bash
# Development (default)
export AGENTICA_MEMORY_BACKEND=sqlite

# Production
export AGENTICA_MEMORY_BACKEND=postgres
export AGENTICA_POSTGRES_URL=postgresql://user:pass@localhost:5432/agentica
```

## Session Isolation

Memory is isolated by session ID:

- **`CLAUDE_SESSION_ID`** environment variable (preferred)
- Falls back to `agent-{agent_id}` if not set

For multi-agent systems, each agent can have its own memory namespace:

```python
# Shared session, agent-specific memory (PostgreSQL only)
memory = await create_memory_service(
    "postgres",
    session_id="swarm-001",
    agent_id="worker-1"  # Isolated from other agents
)
```

## Error Handling

Memory operations fail gracefully:

```python
try:
    scope["remember"]("key", "value")
except Exception as e:
    # Connection errors, schema issues, etc.
    logger.error(f"Memory operation failed: {e}")
```

If memory auto-wiring fails during spawn, the agent still starts but without memory functions (graceful degradation).

## Observing Agents from Main Claude

While agents run in the background (swarms, hierarchical patterns, etc.), the main Claude session can query all agent data sources using the observer script.

### Quick Observation

```bash
# See everything: memory, blackboard, tasks, outputs
uv run python scripts/observe_agents.py --what all
```

### Data Sources

| Source | What's There | Command |
|--------|--------------|---------|
| **Memory** | PostgreSQL archival_memory (persistent) | `--what memory` |
| **Blackboard** | HOT tier JSON files (inter-agent communication) | `--what blackboard` |
| **Tasks** | Task graph SQLite (coordination state) | `--what tasks` |
| **Outputs** | Agent markdown files (work products) | `--what outputs` |

### Common Patterns

```bash
# Monitor swarm research progress
uv run python scripts/observe_agents.py --what memory --query "research"

# Debug blackboard communication
uv run python scripts/observe_agents.py --what blackboard

# Track task completion for a specific session
uv run python scripts/observe_agents.py --what tasks --session-id abc123

# JSON output for parsing
uv run python scripts/observe_agents.py --what all --json
```

### Architecture

```
Main Claude (observer)
    |
    +-- PostgreSQL -------- archival_memory, tags, temporal
    |   \-- GLOBAL VIEW across all sessions/agents
    |
    +-- Blackboard -------- /tmp/claude-blackboard/*.json
    |   \-- Live inter-agent state (HOT tier)
    |
    +-- Task Graph -------- .claude/cache/agentica-coordination/tasks.db
    |   \-- Task dependencies and status
    |
    \-- Agent Outputs ----- .claude/cache/agents/*/
        \-- Summaries, handoffs, work products
```

Use the `/observe-agents` skill for quick access to these commands.

## Related Documentation

- [Memory Architecture](/docs/architecture/memory-system.md) - Technical architecture details
- [Migration Guide](/docs/migration/memory-auto-wiring.md) - Migrating from manual to auto-wired memory
- [Memory Backend](/docs/memory-backend.md) - Backend comparison and configuration

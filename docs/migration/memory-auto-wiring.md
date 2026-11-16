# Migration Guide: Memory Auto-Wiring

## What Changed

The memory system now auto-wires memory functions into agent scope by default via `tracked_spawn()`. This eliminates boilerplate code while preserving flexibility for advanced use cases.

## Before: Manual Setup Required

Previously, using memory with agents required explicit scope creation:

```python
from scripts.agentica_patterns.unified_scope import create_unified_scope
from agentica import spawn

# Step 1: Create unified scope with memory enabled
scope = create_unified_scope(
    session_id="my-session",
    enable_memory=True,
    enable_tasks=True,
)

# Step 2: Pass scope to spawn
agent = await spawn(premise="Research Python web frameworks", scope=scope)

# Step 3: Agent can now use memory
# scope["remember"]("key", "value")
# scope["recall"]("query")
```

This approach required:
- Knowing about `create_unified_scope()`
- Managing session IDs manually
- Passing scope explicitly to every agent

## After: Memory Auto-Wiring

Now, `tracked_spawn()` handles memory setup automatically:

```python
from scripts.agentica_patterns.tracked_agent import tracked_spawn

# One line - memory is automatically included
agent = await tracked_spawn(db=db, premise="Research Python web frameworks")

# Agent scope already has memory functions:
# scope["remember"](key, value)       - Store in core memory
# scope["recall"](query)              - Search all memory
# scope["store_fact"](content, tags)  - Store in archival
# scope["search_memory"](query, ...)  - Full-text search
```

## How It Works

When `inject_memory=True` (the default):

1. **Session ID Resolution**
   - Uses `CLAUDE_SESSION_ID` environment variable if set
   - Falls back to `f"agent-{agent_id}"` for session isolation

2. **Scope Creation**
   - Calls `create_unified_scope(session_id=..., enable_memory=True, enable_tasks=False)`
   - Creates memory service with appropriate session isolation

3. **Scope Merging**
   - If user provides custom scope, it's merged with memory scope
   - Protected keys (`remember`, `recall`, `search_memory`, `store_fact`, `_memory_service`) cannot be overridden
   - User-provided functions for non-protected keys are preserved

4. **Graceful Degradation**
   - If memory initialization fails (e.g., database unavailable), agent still spawns
   - Warning is logged but agent continues without memory functions

## Migration Scenarios

### Scenario 1: Basic Memory Usage

**Before:**
```python
scope = create_unified_scope(session_id="abc", enable_memory=True)
agent = await spawn(premise="...", scope=scope)
```

**After:**
```python
agent = await tracked_spawn(db=db, premise="...")
# Memory is automatically available
```

### Scenario 2: Custom Scope with Memory

**Before:**
```python
scope = create_unified_scope(session_id="abc", enable_memory=True)
scope["my_tool"] = my_custom_tool
agent = await spawn(premise="...", scope=scope)
```

**After:**
```python
agent = await tracked_spawn(
    db=db,
    premise="...",
    scope={"my_tool": my_custom_tool}  # Custom tools merged with memory
)
```

### Scenario 3: No Memory Needed

If you explicitly don't want memory:

```python
agent = await tracked_spawn(
    db=db,
    premise="...",
    inject_memory=False  # Disable auto-wiring
)
```

### Scenario 4: Custom Memory Database Path

```python
from pathlib import Path

agent = await tracked_spawn(
    db=db,
    premise="...",
    memory_db_path=Path("/custom/path/memory.db")
)
```

### Scenario 5: Using agentica.spawn() Directly

If you're using `agentica.spawn()` directly (without tracking), the original manual approach still works:

```python
from scripts.agentica_patterns.unified_scope import create_unified_scope
from agentica import spawn

scope = create_unified_scope(
    session_id="my-session",
    enable_memory=True,
    enable_vector_memory=True,  # Advanced features
    embedding_provider="openai",
)

agent = await spawn(premise="...", scope=scope)
```

## Breaking Changes

**None** - This is a backward-compatible enhancement:

- `create_unified_scope()` still works exactly as before
- `agentica.spawn()` is unchanged
- `tracked_spawn()` gains new default behavior but respects `inject_memory=False`

## Protected Keys

These scope keys are protected and cannot be overridden by user-provided scope:

| Key | Type | Description |
|-----|------|-------------|
| `remember` | Function | Store key-value in core memory |
| `recall` | Function | Query all memory sources |
| `search_memory` | Function | Full-text search with filtering |
| `store_fact` | Function | Store in archival memory |
| `_memory_service` | MemoryService | Direct access to service |

If user scope attempts to override these, a warning is logged and the protected version is used.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDE_SESSION_ID` | Session identifier for memory isolation | Generated from agent_id |
| `AGENTICA_MEMORY_BACKEND` | Backend type ("sqlite" or "postgres") | "sqlite" |
| `AGENTICA_POSTGRES_URL` | PostgreSQL connection string | Required if backend=postgres |

## Recommendations

### For New Code

Use `tracked_spawn()` with defaults:

```python
agent = await tracked_spawn(db=db, premise="...")
```

### For Existing Code

No immediate changes required. Consider migrating when:
- You're refactoring the code anyway
- You want simpler agent creation
- You want automatic session isolation

### For Advanced Memory Features

Continue using `create_unified_scope()` for:
- Vector memory with embeddings
- Reranking support
- Conversation search (message memory)
- Custom embedding providers

```python
scope = create_unified_scope(
    session_id="advanced-session",
    enable_memory=True,
    enable_vector_memory=True,
    embedding_provider="openai",
    enable_reranking=True,
    reranker_provider="local",
    enable_messages=True,
)

agent = await tracked_spawn(
    db=db,
    premise="...",
    scope=scope,
    inject_memory=False  # Use our custom scope instead
)
```

## FAQ

### Q: What if I don't have a CoordinationDB?

Pass `db=None`:

```python
agent = await tracked_spawn(db=None, premise="...")
# Memory still works, coordination tracking is skipped
```

### Q: How do I use a specific session ID?

Set the environment variable:

```bash
export CLAUDE_SESSION_ID="my-specific-session"
```

Or use the manual approach with `create_unified_scope()`.

### Q: Will this affect my existing tests?

No. Tests that use `create_unified_scope()` directly continue to work. Tests using `tracked_spawn()` will now have memory automatically available.

### Q: How do I verify memory is working?

Check the scope keys:

```python
agent = await tracked_spawn(db=db, premise="...")
assert "remember" in agent._agent.scope
assert "recall" in agent._agent.scope
```

Or use memory and verify:

```python
scope["remember"]("test_key", "test_value")
result = scope["recall"]("test_key")
assert "test_value" in result
```

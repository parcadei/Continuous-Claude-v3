# Agentica Quick Reference

## TL;DR

- **Patterns are primitives** - They accept scope, distribute to agents
- **Scope is explicit** - You pass what you want agents to have
- **Memory sharing** - Same `session_id` = shared memory
- **Extensible** - Add any function to scope, agents can call it

## The Stack

```
Your Code → spawn(scope={...}) → Agentica Server → Claude Proxy → Claude CLI
                                                                      ↓
                                                               Agent's "brain"
                                                               (has all tools)
```

## Passing Scope

```python
# Create scope with whatever you want
scope = {
    "read_file": read_file,
    "remember": memory.store,
    "my_custom_fn": my_function,
}

# Pass to pattern
Hierarchical(coordinator_scope=scope, specialist_scope=scope)

# Or direct spawn
agent = await spawn(premise="...", scope=scope)
```

## Memory Wiring (TODO)

Currently missing. To enable:

```python
memory = MemoryService(session_id="my-session")

scope["remember"] = memory.store
scope["recall"] = memory.query
```

## Pattern → Scope Matrix

| Pattern | Coordinator Scope | Worker Scope |
|---------|-------------------|--------------|
| Hierarchical | `coordinator_scope` | `specialist_scope` |
| Swarm | N/A | All workers get same scope |
| Pipeline | Per-stage configurable | Per-stage configurable |

## Key Files

| File | Purpose |
|------|---------|
| `claude_proxy.py` | Claude CLI as OpenAI API |
| `run_claude.py` | Scope function wrappers |
| `memory_service.py` | Memory backend |
| `patterns/*.py` | Pattern primitives |

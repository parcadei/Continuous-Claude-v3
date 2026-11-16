# Async REPL Protocol

When working with Agentica's async REPL harness for testing.

## Rules

### 1. Use `await` for Future-returning tools

```python
content = await view_file(path)  # NOT view_file(path)
answer = await ask_memory("...")
```

### 2. Single code block per response

Compute AND return in ONE block. Multiple blocks means only first executes.

```python
# GOOD: Single block
content = await view_file(path)
return any(c.isdigit() for c in content)

# BAD: Split blocks (second block never runs)
content = await view_file(path)
---
return result
```

### 3. Always `return` for non-str types

If `expected_return_type` is `bool`, `int`, etc., you must explicitly return:

```python
return any(c.isdigit() for c in content)  # NOT just the expression
```

### 4. File path fidelity

Use the EXACT path from the task:

```python
# Task asks about ~/secret.md
await view_file('~/secret.md')  # NOT ~/secret.txt
```

### 5. Raise, don't construct errors

```python
# GOOD
raise AgentError(RuntimeError("Cannot complete task"))

# BAD (does nothing)
AgentError(RuntimeError("..."))
```

### 6. Leverage REPL persistence

Once you have `content`, reuse it across tasks without re-reading:

```python
# Turn 1
content = await view_file(path)

# Turn 2 (no new tool call needed)
return "Jeff" in content
```

## Source Sessions

- 3487e5cb, a018d8ba, 9ae30ed1, 32635cf7: Same mistakes repeated across 4 sessions

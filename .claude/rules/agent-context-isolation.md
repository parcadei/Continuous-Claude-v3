# Agent Context Isolation

Always use background agents to prevent context flooding.

## Rule: Always `run_in_background=true`

```python
# RIGHT - silent, only completion notification
Task(subagent_type="...", run_in_background=true)

# WRONG - streams 50-100k tokens into context
Task(subagent_type="...", run_in_background=false)
```

## Never Use TaskOutput

```python
# WRONG - dumps entire transcript into context
TaskOutput(task_id="...")

# RIGHT - verify with tests instead
Bash("uv run pytest tests/")
```

## Why

- Background agents run silently (completion notification only)
- TaskOutput reads full transcript (50-100k tokens) into context
- This causes mid-conversation compaction and lost context

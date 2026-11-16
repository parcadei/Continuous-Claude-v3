# Never Use TaskOutput

TaskOutput floods the main context window with agent transcripts (70k+ tokens).

## Rule

NEVER use `TaskOutput` tool. Use `Task` tool with synchronous mode instead.

## Why

- TaskOutput reads full agent transcript into context
- This causes mid-conversation compaction
- Defeats the purpose of agent context isolation

## Pattern

```
# WRONG - floods context
Task(run_in_background=true)
TaskOutput(task_id="...")  // 70k tokens dumped

# RIGHT - isolated context, returns summary
Task(run_in_background=false)  // Agent runs, returns summary
```

## Source
- Session where TaskOutput caused context overflow

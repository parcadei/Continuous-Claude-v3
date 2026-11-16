# Index at Creation Time

Index artifacts when they're created, not at batch boundaries.

## Pattern

If downstream logic depends on artifacts being queryable, index immediately at write time.

## DO
- Index handoffs in PostToolUse Write hook (immediately after creation)
- Use `--file` flag for fast single-file indexing
- Trigger indexing from the same event that creates the artifact

## DON'T
- Wait for SessionEnd to batch-index
- Rely on cron/scheduled jobs for time-sensitive data
- Assume data will be available "soon enough"

## Source Sessions
- a541f08a: "Index at artifact creation time, not at SessionEnd"
- 1c21e6c8: "If downstream logic depends on artifacts, index at the moment they're created"

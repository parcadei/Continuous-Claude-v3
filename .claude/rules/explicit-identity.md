# Explicit Identity Across Boundaries

Never rely on "latest" or "current" when crossing process or async boundaries.

## Pattern

Pass explicit identifiers through the entire pipeline. "Most recent" is a race condition.

## DO

- Pass `--session-id $ID` when spawning processes
- Store IDs in state files for later correlation
- Use full UUIDs, not partial matches
- Keep different ID types separate (don't collapse concepts)

## DON'T

- Query for "most recent session" at execution time
- Assume the current context will still be current after await/spawn
- Collapse different ID types:
  - `session_id` = Claude Code session (human-facing)
  - `root_span_id` = Braintrust trace (query key)
  - `turn_span_id` = Braintrust turn within session

## Example

```typescript
// BAD: race condition at session boundaries
spawn('analyzer', ['--learn'])  // defaults to "most recent"

// GOOD: explicit identity
spawn('analyzer', ['--learn', '--session-id', input.session_id])
```

## Source Sessions

- 1c21e6c8: Defined session_id vs root_span_id distinction
- 6a9f2d7a: Fixed wrong-session attribution via explicit passing
- a541f08a: Confirmed pattern prevents race at session boundaries

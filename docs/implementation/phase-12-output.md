# Phase 12: Add --orphans Flag to watch_agents.py

## Summary

Added `--orphans` CLI flag to `watch_agents.py` to display orphan agent candidates using the three-tier detection system implemented in Phase 8.

## TDD Process

### 1. Tests Written First

Created `tests/unit/test_watch_agents_orphans.py` with 10 test cases:

| Test | Purpose |
|------|---------|
| `test_argparse_accepts_orphans_flag` | Verify `--orphans` flag is recognized |
| `test_argparse_accepts_short_orphans_flag` | Verify `-o` short flag works |
| `test_orphans_flag_via_cli` | End-to-end CLI test |
| `test_orphans_flag_calls_find_orphans` | Verify `db.find_orphans()` is called |
| `test_orphans_display_shows_tier_and_reason` | Verify output format |
| `test_orphans_json_flag_outputs_json` | Verify `--json` produces valid JSON |
| `test_orphans_json_contains_required_fields` | Verify JSON has tier, agent_id, reason |
| `test_orphans_creates_rich_table_when_available` | Verify Rich table creation |
| `test_orphans_empty_returns_cleanly` | Verify graceful handling of no orphans |
| `test_orphans_empty_message_shown` | Verify informative message for empty results |

### 2. Initial Test Run (All Failed)

```
FAILED tests/unit/test_watch_agents_orphans.py::TestWatchAgentsOrphansFlag::test_orphans_flag_via_cli
FAILED tests/unit/test_watch_agents_orphans.py::TestWatchAgentsOrphansFlag::test_orphans_flag_calls_find_orphans
... (8 failures total)
```

Error: `unrecognized arguments: --orphans`

### 3. Implementation

Modified `scripts/agentica/watch_agents.py`:

1. Added imports:
   ```python
   import json
   from scripts.agentica.coordination import OrphanCandidate
   ```

2. Added argparse flags:
   ```python
   parser.add_argument("--orphans", "-o", action="store_true", help="Show orphan candidates")
   parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format")
   ```

3. Added `create_orphan_table()` function for Rich output:
   ```python
   def create_orphan_table(orphans: list[OrphanCandidate]) -> Table:
       table = Table(title="Orphan Candidates")
       table.add_column("Tier", style="red")
       table.add_column("Agent ID", style="cyan")
       table.add_column("Age", style="magenta")
       table.add_column("Reason", style="white")
       for orphan in orphans:
           age = format_elapsed(orphan.spawned_at)
           table.add_row(str(orphan.tier), orphan.agent_id, age, orphan.reason)
       return table
   ```

4. Added handler in `main()`:
   ```python
   if args.orphans:
       orphans = db.find_orphans()
       if args.json:
           # JSON output with all fields
           orphan_dicts = [...]
           print(json.dumps(orphan_dicts, indent=2))
       elif RICH_AVAILABLE:
           console.print(create_orphan_table(orphans))
       else:
           for o in orphans:
               print(f"Tier {o.tier}: {o.agent_id} - {o.reason} ({age})")
       return
   ```

### 4. Final Test Run (All Passed)

```
tests/unit/test_watch_agents_orphans.py::TestWatchAgentsOrphansFlag::test_argparse_accepts_orphans_flag PASSED
tests/unit/test_watch_agents_orphans.py::TestWatchAgentsOrphansFlag::test_argparse_accepts_short_orphans_flag PASSED
tests/unit/test_watch_agents_orphans.py::TestWatchAgentsOrphansFlag::test_orphans_flag_via_cli PASSED
tests/unit/test_watch_agents_orphans.py::TestWatchAgentsOrphansFlag::test_orphans_flag_calls_find_orphans PASSED
tests/unit/test_watch_agents_orphans.py::TestWatchAgentsOrphansFlag::test_orphans_display_shows_tier_and_reason PASSED
tests/unit/test_watch_agents_orphans.py::TestOrphansJsonOutput::test_orphans_json_flag_outputs_json PASSED
tests/unit/test_watch_agents_orphans.py::TestOrphansJsonOutput::test_orphans_json_contains_required_fields PASSED
tests/unit/test_watch_agents_orphans.py::TestOrphansRichTable::test_orphans_creates_rich_table_when_available PASSED
tests/unit/test_watch_agents_orphans.py::TestOrphansEmpty::test_orphans_empty_returns_cleanly PASSED
tests/unit/test_watch_agents_orphans.py::TestOrphansEmpty::test_orphans_empty_message_shown PASSED

============================== 10 passed in 0.14s ==============================
```

## Usage

```bash
# Show orphan candidates with Rich table
uv run python scripts/agentica/watch_agents.py --orphans

# Short form
uv run python scripts/agentica/watch_agents.py -o

# JSON output for scripting
uv run python scripts/agentica/watch_agents.py --orphans --json
```

## Output Formats

### Rich Table (default)
```
               Orphan Candidates
+------+-----------------+------+---------------------------+
| Tier | Agent ID        | Age  | Reason                    |
+------+-----------------+------+---------------------------+
| 1    | orphan-abc-123  | 2h   | ppid=1 (parent died)      |
| 2    | stale-def-456   | 45m  | Parent agent completed    |
+------+-----------------+------+---------------------------+
```

### JSON Output
```json
[
  {
    "tier": 1,
    "agent_id": "orphan-abc-123",
    "reason": "ppid=1 (parent process died)",
    "age": "2h 15m",
    "spawned_at": "2025-12-28T15:00:00",
    "ppid": 1,
    "parent_agent_id": null
  }
]
```

### Plain Text (no Rich)
```
Tier 1: orphan-abc-123 - ppid=1 (parent process died) (2h 15m)
```

## Files Modified

| File | Change |
|------|--------|
| `scripts/agentica/watch_agents.py` | Added `--orphans` and `--json` flags, `create_orphan_table()` function |
| `tests/unit/test_watch_agents_orphans.py` | **New**: 10 test cases for orphans functionality |

## Integration with Phase 8

This phase uses the `find_orphans()` method added in Phase 8 which implements three-tier orphan detection:
- Tier 1: Unix orphans (ppid == 1)
- Tier 2: Parent agent completed/failed (30min grace expired)
- Tier 3: Running > 24h without completion

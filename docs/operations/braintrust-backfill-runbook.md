# Braintrust Backfill Operations Runbook

## 1. Overview

### What the Backfill Does

The Braintrust backfill pipeline extracts temporal facts from Claude Code sessions stored in Braintrust and writes them to the local temporal memory database. This enables:

- **Fact extraction**: Parse tool calls, skill activations, and agent activities from session spans
- **Turn inference**: Determine conversational turn boundaries within sessions
- **Outcome tagging**: Link sessions to outcomes (SUCCEEDED, FAILED, PARTIAL) from context.db
- **Calibration analysis**: Correlate fact patterns with session outcomes for confidence scoring

### Expected Data

| Metric | Expected |
|--------|----------|
| SUCCEEDED sessions | ~87 |
| PARTIAL sessions | ~10 |
| Total sessions with marked outcomes | ~97 |
| Minimum spans per session | 5 |

### Target Output

- **Primary**: `.claude/cache/temporal-memory/temporal.db` with calibrated facts
- **Checkpoint**: `.claude/cache/backfill-checkpoint.json`
- **Gap log**: `.claude/cache/backfill-gaps.jsonl`

---

## 2. Pre-flight Checklist

Before running the backfill, verify all prerequisites:

```bash
# Run from project root
cd /Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit
```

### Required Checks

- [ ] **API Key**: Set `BRAINTRUST_API_KEY` in environment or `.env`
  ```bash
  # Check if API key is available
  grep -q "BRAINTRUST_API_KEY" .env && echo "OK: API key found in .env" || echo "MISSING: Add BRAINTRUST_API_KEY to .env"

  # Or check environment
  [ -n "$BRAINTRUST_API_KEY" ] && echo "OK: API key in environment" || echo "MISSING: Export BRAINTRUST_API_KEY"
  ```

- [ ] **Temporal DB directory exists**:
  ```bash
  mkdir -p .claude/cache/temporal-memory
  ls -la .claude/cache/temporal-memory/
  ```

- [ ] **Context DB exists** (required for outcome tagging):
  ```bash
  ls -la .claude/cache/artifact-index/context.db
  # If missing, run artifact indexing first
  ```

- [ ] **Backup temporal.db** (if it exists):
  ```bash
  [ -f .claude/cache/temporal-memory/temporal.db ] && \
    cp .claude/cache/temporal-memory/temporal.db \
       .claude/cache/temporal-memory/temporal.db.bak.$(date +%Y%m%d-%H%M%S) && \
    echo "Backup created" || echo "No existing DB to backup"
  ```

- [ ] **Python environment ready**:
  ```bash
  uv run python --version  # Should be 3.11+
  uv run python -c "import requests; print('requests OK')"
  ```

---

## 3. Execution Steps

### Step 1: Dry Run Validation

First, validate the pipeline without writing to the database:

```bash
# Validate with a small sample
uv run python scripts/backfill/run_backfill.py --all --dry-run --limit 10
```

Expected output:
- No errors
- Sessions validated count > 0
- "Facts written" shows what would be written

### Step 2: Small Batch Test

Test with a real batch to verify database writes:

```bash
# Process first 50 sessions
uv run python scripts/backfill/run_backfill.py --all --limit 50
```

Verify results:
```bash
# Check facts were written
sqlite3 .claude/cache/temporal-memory/temporal.db "SELECT COUNT(*) FROM temporal_facts;"

# Check session coverage
sqlite3 .claude/cache/temporal-memory/temporal.db "SELECT COUNT(DISTINCT session_id) FROM temporal_facts;"
```

### Step 3: Full Backfill

Once validation passes, run the full backfill:

```bash
# Process all unprocessed sessions
uv run python scripts/backfill/run_backfill.py --all
```

This will:
1. Query Braintrust for all sessions with 5+ spans
2. Skip already-processed sessions (from checkpoint)
3. Process each session through the pipeline
4. Run calibration analysis at the end

### Step 4: Resume if Interrupted

If the backfill is interrupted (Ctrl+C, network error, etc.):

```bash
# Resume from last checkpoint
uv run python scripts/backfill/run_backfill.py --resume
```

The checkpoint file tracks:
- `processed`: Sessions already completed
- `pending`: Sessions still to process
- `updated_at`: Last update timestamp

---

## 4. Progress Monitoring

### Real-time Progress

The CLI outputs progress as it runs:
```
Processing 87 new sessions...
  [1/87] Processing abc123def456...
  [2/87] Processing 789xyz012345...
```

### Checkpoint File

Monitor the checkpoint for detailed state:

```bash
# View checkpoint
cat .claude/cache/backfill-checkpoint.json | jq .

# Count progress
jq '.processed | length' .claude/cache/backfill-checkpoint.json  # Completed
jq '.pending | length' .claude/cache/backfill-checkpoint.json    # Remaining
```

### Gap Log

Track skipped sessions:

```bash
# View recent gaps
tail -20 .claude/cache/backfill-gaps.jsonl

# Summarize by reason
cat .claude/cache/backfill-gaps.jsonl | jq -r '.reason' | sort | uniq -c
```

### Expected Duration

| Sessions | Estimated Time |
|----------|----------------|
| 10 | ~30 seconds |
| 50 | ~2-3 minutes |
| 100 | ~5-10 minutes |
| 500 | ~30-60 minutes |

Times vary based on API latency and session complexity.

---

## 5. Error Recovery

### API Errors

**Symptom**: "Braintrust API error: 401" or "403"

**Fix**:
```bash
# Verify API key
echo $BRAINTRUST_API_KEY | head -c 10

# Re-export if needed
export BRAINTRUST_API_KEY="sk-..."

# Or add to .env
echo 'BRAINTRUST_API_KEY="sk-..."' >> .env
```

### Database Locked

**Symptom**: "database is locked" or "SQLITE_BUSY"

**Fix**:
```bash
# Wait for other processes to finish
sleep 5

# Check for processes using the DB
lsof .claude/cache/temporal-memory/temporal.db

# Resume
uv run python scripts/backfill/run_backfill.py --resume
```

### Resume from Checkpoint

**Symptom**: Backfill interrupted (Ctrl+C, crash, etc.)

**Fix**:
```bash
# Just resume - progress is saved
uv run python scripts/backfill/run_backfill.py --resume
```

### Fresh Start

**Symptom**: Checkpoint corrupted or want to reprocess everything

**Fix**:
```bash
# Delete checkpoint to start fresh
rm .claude/cache/backfill-checkpoint.json

# Optionally clear gaps log
rm .claude/cache/backfill-gaps.jsonl

# Run full backfill
uv run python scripts/backfill/run_backfill.py --all
```

### Single Session Debug

**Symptom**: One session failing repeatedly

**Fix**:
```bash
# Process just that session with verbose output
uv run python scripts/backfill/run_backfill.py --session <session-id>

# Check gaps for that session
grep "<session-id>" .claude/cache/backfill-gaps.jsonl
```

---

## 6. Calibration Analysis

After backfill completes, analyze fact-outcome correlations:

### Run Analysis

```bash
# Calibration runs automatically at end of backfill
# To run manually:
uv run python -c "
from pathlib import Path
from scripts.backfill.calibration import CalibrationAnalyzer

analyzer = CalibrationAnalyzer(
    temporal_db=Path('.claude/cache/temporal-memory/temporal.db'),
    context_db=Path('.claude/cache/artifact-index/context.db'),
)

# Get correlation report
report = analyzer.analyze()
print(f'Sessions analyzed: {report[\"sessions_analyzed\"]}')
print(f'Success patterns: {len(report[\"success_patterns\"])}')
print(f'Failure patterns: {len(report[\"failure_patterns\"])}')

# Get calibration table
table = analyzer.get_calibration_table()
print(f'\\nCalibration entries: {len(table)}')

# Show top success-correlated facts
sorted_facts = sorted(table.items(), key=lambda x: x[1]['success_rate'], reverse=True)
print('\\nTop success-correlated facts:')
for key, info in sorted_facts[:10]:
    print(f'  {key}: {info[\"success_rate\"]:.0%} ({info[\"count\"]} sessions)')
"
```

### Calibration Table Output

The calibration table provides:

| Field | Description |
|-------|-------------|
| `success_rate` | 0.0 to 1.0 - fraction of sessions with this fact that SUCCEEDED |
| `count` | Total sessions where this fact appeared |
| `recommended_multiplier` | 0.7 to 1.2 - suggested confidence adjustment |

### Multiplier Interpretation

| Multiplier | Meaning |
|------------|---------|
| 0.7 | Fact correlates strongly with FAILED sessions |
| 1.0 | Neutral - no correlation |
| 1.2 | Fact correlates strongly with SUCCEEDED sessions |

---

## 7. Interpreting Results

### Success Patterns

Facts that appear more in SUCCEEDED sessions:
- `skill_activated: commit` - Completed work with commit
- `skill_activated: create_handoff` - Created proper handoff
- High `tool_call_count` - More thorough sessions

### Failure Patterns

Facts that appear more in FAILED sessions:
- Early session termination (low turn count)
- Missing handoff or commit skills
- Parse errors in spans

### Gap Reasons

| Reason | Description | Action |
|--------|-------------|--------|
| `insufficient_spans` | Session has < 5 spans | Skip - not enough data |
| `no_tool_spans` | No tool calls found | Skip - nothing to extract |
| `already_processed` | In checkpoint | Skip - already done |
| `api_error` | Braintrust API failed | Retry later |
| `parse_error` | Span parsing failed | Check span format |
| `timeout` | Request timed out | Retry with `--resume` |

---

## 8. Rollback Procedure

### Restore from Backup

```bash
# Find most recent backup
ls -lt .claude/cache/temporal-memory/temporal.db.bak.*

# Restore (replace timestamp with actual)
cp .claude/cache/temporal-memory/temporal.db.bak.20250101-120000 \
   .claude/cache/temporal-memory/temporal.db

# Verify
sqlite3 .claude/cache/temporal-memory/temporal.db "SELECT COUNT(*) FROM temporal_facts;"
```

### Full Reset

```bash
# Remove all backfill artifacts
rm .claude/cache/temporal-memory/temporal.db
rm .claude/cache/backfill-checkpoint.json
rm .claude/cache/backfill-gaps.jsonl

# Reinitialize from scratch
uv run python scripts/backfill/run_backfill.py --all
```

---

## 9. Post-Backfill Verification

### Fact Counts

```bash
# Total facts
sqlite3 .claude/cache/temporal-memory/temporal.db "SELECT COUNT(*) FROM temporal_facts;"

# Facts by key
sqlite3 .claude/cache/temporal-memory/temporal.db "
SELECT key, COUNT(*) as count
FROM temporal_facts
GROUP BY key
ORDER BY count DESC
LIMIT 10;
"
```

### Session Coverage

```bash
# Unique sessions
sqlite3 .claude/cache/temporal-memory/temporal.db "SELECT COUNT(DISTINCT session_id) FROM temporal_facts;"

# Sessions with outcomes
sqlite3 .claude/cache/temporal-memory/temporal.db "
SELECT outcome, COUNT(DISTINCT session_id)
FROM temporal_facts
WHERE outcome IS NOT NULL
GROUP BY outcome;
"
```

### Calibration Validation

```bash
# Check calibration data exists
sqlite3 .claude/cache/temporal-memory/temporal.db "
SELECT
  (SELECT COUNT(*) FROM temporal_facts WHERE outcome = 'SUCCEEDED') as succeeded_facts,
  (SELECT COUNT(*) FROM temporal_facts WHERE outcome = 'FAILED') as failed_facts,
  (SELECT COUNT(*) FROM temporal_facts WHERE outcome = 'PARTIAL') as partial_facts;
"
```

---

## 10. Pipeline Components Reference

| Component | File | Purpose |
|-----------|------|---------|
| CLI Orchestrator | `run_backfill.py` | Main entry point, coordinates pipeline |
| Session Validator | `session_validator.py` | Validates session has sufficient data |
| Span Parser | `span_parser.py` | Extracts facts from Braintrust spans |
| Turn Inference | `turn_inference.py` | Determines turn boundaries |
| Outcome Tagger | `outcome_tagger.py` | Links sessions to context.db outcomes |
| Temporal Writer | `temporal_writer.py` | Writes facts to temporal.db |
| Gap Logger | `gap_logger.py` | Tracks skipped sessions |
| Checkpoint Manager | `checkpoint.py` | Resume interrupted backfills |
| Calibration Analyzer | `calibration.py` | Correlates facts to outcomes |

---

## 11. Troubleshooting Quick Reference

| Symptom | Likely Cause | Quick Fix |
|---------|--------------|-----------|
| "API key not found" | Missing BRAINTRUST_API_KEY | Add to .env or export |
| "database is locked" | Concurrent access | Wait and retry |
| "No sessions found" | Wrong project name | Check Braintrust project |
| Zero facts written | No valid sessions | Check gap log |
| Calibration empty | No outcomes in context.db | Run artifact indexing |
| Resume not working | Checkpoint corrupted | Delete checkpoint, restart |

---

## Version Information

- **Pipeline Version**: Phase 4 (CLI Orchestrator)
- **Components**: 9 Python modules
- **Tests**: 11 test files
- **Last Updated**: 2025-12-31

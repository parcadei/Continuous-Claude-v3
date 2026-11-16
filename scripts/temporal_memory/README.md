# Temporal Memory System

Token-efficient memory summarization for Claude Code sessions using Temporal Epistemic Logic (TEL).

## Overview

The temporal memory system tracks facts across turns in a Claude Code session and provides:
- **Invariant detection**: Facts that never changed (stable anchors)
- **Transition tracking**: State changes with utility scoring
- **Erotetic analysis**: Open questions (unknowns) with Q-value ranking
- **Token budgeting**: Summaries fit within specified token limits
- **Inertia rules**: Facts persist unless explicitly changed (TEL semantics)
- **Agent handoffs**: Structured state transfer between agents

## Architecture

```
scripts/temporal_memory/
  store.py        # TemporalMemoryStore - SQLite-backed fact storage
  summarizer.py   # TemporalSummarizer - Token-efficient summaries
  handoff.py      # TemporalHandoffState - Agent handoff format
  inertia.py      # TEL inertia rules and revision handling
  atoms.py        # TemporalAtom - TEL atomic propositions
  cli.py          # Command-line interface
```

### Data Flow

```
Record Facts (per turn)
    |
    v
TemporalMemoryStore (SQLite)
    |
    +---> Invariant Detection (facts that never changed)
    +---> Transition Extraction (state changes, utility-ranked)
    +---> Erotetic Analysis (open questions via E(X,Q))
    +---> Pending Goals (goal_* not achieved)
    |
    v
TemporalSummarizer (token-budgeted output)
    |
    v
TemporalHandoffState (agent transfer format)
```

## CLI Usage

### Record Facts

Store facts at a specific turn:

```bash
uv run python -m scripts.temporal_memory.cli record \
    --session-id "$SESSION_ID" \
    --turn 1 \
    --facts '{"phase": "testing", "db": "sqlite"}'
```

**Options:**
- `--session-id` (required): Unique session identifier
- `--turn` (required): Turn number (integer)
- `--facts` (required): JSON string of key-value facts
- `--db-path` (optional): Custom database path

**Output (JSON):**
```json
{"status": "ok", "turn": 1}
```

### Summarize Session

Generate a temporal summary:

```bash
# JSON output (default)
uv run python -m scripts.temporal_memory.cli summarize \
    --session-id "$SESSION_ID" \
    --output json

# Markdown output
uv run python -m scripts.temporal_memory.cli summarize \
    --session-id "$SESSION_ID" \
    --output markdown

# With custom token budget
uv run python -m scripts.temporal_memory.cli summarize \
    --session-id "$SESSION_ID" \
    --budget 500 \
    --output json
```

**Options:**
- `--session-id` (required): Session identifier to summarize
- `--output` (optional): `json` (default) or `markdown`
- `--budget` (optional): Token budget for summary (default: 2000)
- `--db-path` (optional): Custom database path

**JSON Output:**
```json
{
  "open_questions": ["auth_method"],
  "invariants": ["ALWAYS(db=sqlite)"],
  "pending_goals": ["goal_tests"],
  "transitions": ["T=2: phase=planning -> phase=coding"],
  "current_state": {"db": "sqlite", "phase": "testing"},
  "turn_count": 3,
  "token_estimate": 45
}
```

**Markdown Output:**
```markdown
# Temporal Summary (Turn 3)

## Open Questions
- auth_method

## Invariants
- ALWAYS(db=sqlite)

## Pending Goals
- [ ] goal_tests

## Transitions
- T=2: phase=planning -> phase=coding

*Token estimate: 45*
```

## Python API

### Basic Usage

```python
import asyncio
from scripts.temporal_memory import TemporalMemoryStore, TemporalSummarizer

async def main():
    store = TemporalMemoryStore(session_id="my-session")
    await store.connect()

    # Record facts
    await store.record(turn=1, facts={"phase": "planning", "db": "sqlite"})
    await store.record(turn=2, facts={"phase": "coding", "db": "sqlite"})

    # Summarize
    summarizer = TemporalSummarizer()
    summary = await summarizer.summarize(store, budget_tokens=500)
    print(summary)

asyncio.run(main())
```

### Erotetic Analysis (Open Questions)

Track unresolved questions using `UNKNOWN` marker:

```python
# Record with erotetic tracking
result = await store.record_with_erotetic(turn=1, facts={
    "db": "sqlite",           # Known
    "auth": "UNKNOWN",        # Open question
    "framework": "UNKNOWN",   # Open question
})

print(result["unknowns"])  # ["auth", "framework"]
print(result["count"])     # 2

# Later, resolve one question
await store.record_with_erotetic(turn=2, facts={
    "db": "sqlite",
    "auth": "jwt",            # Now resolved
    "framework": "UNKNOWN",   # Still open
})

# Query open questions
open_qs = await store.get_open_questions()  # ["framework"]
```

### Inertia and Revision Tracking

Facts persist via inertia unless explicitly updated:

```python
from scripts.temporal_memory.inertia import RevisionPriority

# Initial state
await store.record(turn=1, facts={"db": "sqlite", "phase": "planning"})

# Advance with partial update (db persists via inertia)
revisions = await store.advance_turn(
    updates={"phase": "testing"},
    priority=RevisionPriority.RECENT_OBSERVATION
)

# Revision events track what changed
for rev in revisions:
    print(f"{rev.key}: {rev.old_value} -> {rev.new_value}")

# Current state includes persisted facts
state = await store.get_current_state()
# {"db": "sqlite", "phase": "testing"}
```

### Agent Handoffs

Generate structured handoffs for agent-to-agent transfer:

```python
from scripts.temporal_memory.handoff import (
    TemporalHandoffState,
    parse_temporal_handoff,
    load_temporal_handoff,
)

# Create handoff from summary
handoff = TemporalHandoffState.from_summary(
    summary={
        "open_questions_ranked": [("auth", "HIGH", "Blocking decision")],
        "pending_goals": ["goal_tests"],
        "transitions": ["T=2: phase=planning -> phase=coding"],
        "current_state": {"db": "sqlite"},
        "turn_count": 3,
    },
    context="Working on Phase 5",
    instruction="Complete the parser tests"
)

# Generate markdown
md = handoff.to_markdown()

# Parse back (for receiving agent)
parsed = parse_temporal_handoff(md)

# Load from filesystem
loaded = load_temporal_handoff("session-name")
```

## Hook Integration

The CLI can be called from TypeScript hooks:

```typescript
// In .claude/hooks/src/pre-compact-continuity.ts
import { execSync } from 'child_process';

function triggerTemporalSummarization(sessionId: string): string | null {
    try {
        const result = execSync(
            `uv run python -m scripts.temporal_memory.cli summarize ` +
            `--session-id "${sessionId}" --output json`,
            { encoding: 'utf-8', timeout: 10000, cwd: process.env.CLAUDE_PROJECT_DIR }
        );
        return result.trim();
    } catch {
        return null;
    }
}

function recordFacts(sessionId: string, turn: number, facts: object): boolean {
    try {
        execSync(
            `uv run python -m scripts.temporal_memory.cli record ` +
            `--session-id "${sessionId}" --turn ${turn} ` +
            `--facts '${JSON.stringify(facts)}'`,
            { encoding: 'utf-8', timeout: 5000, cwd: process.env.CLAUDE_PROJECT_DIR }
        );
        return true;
    } catch {
        return false;
    }
}
```

## Database

By default, data is stored in:
```
.claude/cache/temporal-memory/temporal.db
```

The database uses SQLite with WAL mode for concurrent access. Sessions are isolated - each session_id has its own namespace.

### Schema

```sql
-- Facts with temporal metadata
CREATE TABLE temporal_facts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    turn_established INTEGER NOT NULL,
    turn_last_changed INTEGER NOT NULL,
    change_count INTEGER DEFAULT 0,
    confidence REAL DEFAULT 1.0,
    created_at REAL NOT NULL,
    UNIQUE(session_id, key)
);

-- Turn-by-turn snapshots
CREATE TABLE temporal_trace (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn INTEGER NOT NULL,
    facts_json TEXT NOT NULL,
    erotetic_json TEXT,
    created_at REAL NOT NULL
);
```

## Concepts

### Invariants

Facts that never changed across all recorded turns. These represent stable architectural decisions or environment constants.

Example: If `db=sqlite` appears in every turn and never changes, it becomes an invariant: `ALWAYS(db=sqlite)`

Detection criteria:
- Present in >= 80% of turns (configurable via `confidence_threshold`)
- Consistent value >= 90% of appearances

### Transitions

State changes detected between consecutive turns, ranked by utility:

```
U(event) = importance * recency * frequency
```

- **Recency**: 15-turn half-life decay (events 15 turns ago have 0.5x weight)
- **Importance**: From erotetic Q-value ranking (HIGH=1.5, MED=1.0, LOW=0.5)
- **Frequency**: Based on access count (0.5 to 1.0 scale)

### Open Questions (Erotetic Analysis)

Propositions marked as `UNKNOWN` in the facts. These represent unresolved decisions or missing information.

The E(X,Q) model identifies which propositions cannot be entailed from context X:
- `UNKNOWN` string value = open question
- `None` value = open question
- Any other value = resolved

### Pending Goals

Facts with keys starting with `goal_` that don't have value `"achieved"`.

Example:
```python
{"goal_tests": "pending"}  # Listed as pending
{"goal_docs": "achieved"}  # Not listed
```

### TEL Inertia Rule

The system implements the Temporal Epistemic Logic inertia rule:

```
holds(P, T+1) :- holds(P, T), not -holds(P, T+1)
```

Translation: A fact persists from turn T to T+1 unless explicitly negated or updated.

Revision priority hierarchy:
1. `EXPLICIT_NEGATION` (highest) - User explicitly removed/negated
2. `RECENT_OBSERVATION` - New observation from current turn
3. `INVARIANT` - Established invariant fact
4. `HISTORICAL` (lowest) - Previously recorded fact

## Testing

```bash
# Run E2E integration tests
uv run pytest tests/integration/test_temporal_memory_e2e.py -v

# Run unit tests
uv run pytest tests/unit/test_temporal*.py -v

# Run all temporal memory tests
uv run pytest -k temporal -v
```

### Test Coverage

| Component | Tests | Coverage |
|-----------|-------|----------|
| Store (record, trace, state) | 9 | Full CRUD, reconnect |
| Summarizer (invariants, transitions) | 5 | Detection accuracy, utility ranking |
| Handoff (generate, parse, load) | 4 | Round-trip integrity |
| Inertia (revision, conflict) | 3 | Priority resolution |
| CLI (record, summarize) | 5 | JSON/markdown output |
| Edge Cases | 6 | Empty, unicode, concurrent |

**Total: 32 tests (12 unit + 20 E2E)**

## Token Efficiency

The temporal format achieves significant token reduction compared to prose:

| Format | Example (5 facts) | Tokens |
|--------|-------------------|--------|
| Verbose prose | "The database is sqlite. The phase is testing..." | ~40 |
| Temporal format | `{"db":"sqlite","phase":"testing",...}` + invariants | ~15 |

Reduction: ~60-70% fewer tokens for equivalent information.

The token budget system further constrains output by:
1. Limiting transitions (most important first)
2. Compact TEL format for invariants (`ALWAYS(db=sqlite)`)
3. Structured sections instead of prose

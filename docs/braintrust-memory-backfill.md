# Braintrust Memory Backfill: Complete Technical Documentation

## Overview

The Memory Backfill Service (`scripts/agentica/memory_backfill.py`) extracts learnings from historical Braintrust traces and populates the MemoryService. This enables knowledge retrieval from past sessions without requiring real-time capture during those sessions.

### Why This Exists

When using Claude Code with Braintrust tracing enabled, every session generates detailed traces containing:
- Goals and objectives
- Key decisions with rationale
- Files modified
- Errors encountered and resolutions
- Agent outputs and task completions

This rich historical data sits unused in Braintrust unless explicitly extracted. The backfill service bridges this gap by:
1. Fetching traces from Braintrust's BTQL API
2. Parsing structured facts from spans and context
3. Deduplicating to avoid storage bloat
4. Generating embeddings for semantic search
5. Storing to the persistent memory backend

### Key Design Principles

- **Idempotent**: Re-running backfill on the same sessions produces no duplicates
- **Resumable**: Batch processing can resume from checkpoint after interruption
- **Deterministic**: Same input produces same output (except for embedding variance)
- **Write-Behind**: Agents don't call `remember()` - backfill extracts from traces

## Architecture

```
+------------------+     +------------------+     +------------------+
|    Braintrust    |     |   Memory Backfill|     |   MemoryService  |
|    Traces API    | --> |   Pipeline       | --> |   (SQLite/PG)    |
+------------------+     +------------------+     +------------------+
        |                        |                        |
        |                        |                        |
   BTQL Queries             6-Stage Pipeline         Searchable Facts
   (project_logs)                                    with Embeddings
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     BACKFILL PIPELINE                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Stage 1: FETCH         Stage 2: PARSE         Stage 3: DEDUPE      │
│  ┌───────────┐          ┌───────────┐          ┌───────────┐        │
│  │ BTQL API  │    -->   │ Spans to  │    -->   │ Content   │        │
│  │ raw spans │          │ Facts     │          │ Hash Check│        │
│  └───────────┘          └───────────┘          └───────────┘        │
│       |                      |                      |                │
│       v                      v                      v                │
│  Root spans +           ExtractedFact          Novel facts          │
│  Hierarchical           dataclass              only                  │
│  context                                                             │
│                                                                      │
│  Stage 4: ENRICH        Stage 5: EMBED         Stage 6: STORE       │
│  ┌───────────┐          ┌───────────┐          ┌───────────┐        │
│  │ Add type  │    -->   │ Voyage/   │    -->   │ Upsert to │        │
│  │ metadata  │          │ OpenAI    │          │ Memory DB │        │
│  └───────────┘          └───────────┘          └───────────┘        │
│       |                      |                      |                │
│       v                      v                      v                │
│  fact_type,              1536-dim vectors      Searchable           │
│  source_session                                archival memory       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## What We Tried

### Approach 1: Direct Span Import
- **What**: Read all spans from BTQL, store raw content directly
- **Result**: Failed
- **Why**: Raw spans contain too much noise (tool inputs/outputs, system messages). Storage bloat without semantic value.

### Approach 2: LLM-Only Extraction
- **What**: Send all spans to LLM with "extract learnings" prompt
- **Result**: Partially worked but expensive
- **Why**: Works for small sessions but context limits prevent processing large sessions (200-1500 spans, 1M+ tokens). Also expensive at scale.

### Approach 3: Hierarchical Context First (Final Implementation)
- **What**: Extract from existing handoffs/ledgers first, then supplement with span parsing
- **Result**: Worked
- **Why**: Handoffs and ledgers already contain curated summaries. Span parsing adds file changes and errors that weren't in handoffs.

### Approach 4: Two-Pass Map/Reduce for Decision Extraction
- **What**: Pre-scan for references, map spans to summaries, inject context for decision extraction
- **Result**: Designed but not yet implemented
- **Why**: Needed for cross-referential context in large sessions. See "Future Work" section.

## What Didn't Work

### API Key Location Confusion

**Problem**: 401 errors when calling Braintrust API.

**Root Cause**: The `BRAINTRUST_API_KEY` was expected in project `.env` but was actually stored in `~/.claude/.env`.

**Solution**: The `load_api_key()` function now searches multiple locations:
```python
for path in [Path.home() / ".claude", Path.cwd(), *Path.cwd().parents]:
    env_file = path / ".env"
    if env_file.exists():
        # Parse and load BRAINTRUST_API_KEY
```

**Lesson**: Always check global config locations first when API auth fails.

### span_attributes vs metadata for tool_name

**Problem**: File change extraction returned zero facts despite spans containing Write/Edit tool calls.

**Root Cause**: Initial implementation looked for `tool_name` in `span_attributes`:
```python
# WRONG
tool_name = attrs.get("tool_name")
```

But Braintrust actually stores it in `metadata`:
```python
# CORRECT
tool_name = metadata.get("tool_name") or attrs.get("name", "")
```

**Solution**: Fixed in `extract_facts_from_spans()` to check both locations.

**Lesson**: The TDD approach caught this - tests that used real Braintrust structure revealed the mismatch.

### BTQL Session Access (403 Errors)

**Problem**: `list_sessions_in_range()` query returned sessions, but fetching some sessions returned 403 errors.

**Root Cause**: BTQL aggregation queries (`GROUP BY root_span_id`) can return sessions from other users in the same project. Individual span fetches then fail with 403 due to access control.

**Workaround**: Use try/except around session fetches and continue to next session on 403:
```python
try:
    spans = await fetch_session_spans(session_id, project_id, api_key)
except RuntimeError as e:
    if "403" in str(e):
        result.errors.append(f"Access denied for session {session_id}")
        continue
```

**Lesson**: Multi-user projects require defensive error handling for cross-user session access.

### Background Bash Output Issues

**Problem**: Commands run in background produced no visible output.

**Root Cause**: Shell redirection issues when piping to background processes.

**Solution**: Use foreground execution for debugging, background only for known-working commands.

## What Worked

### TDD Approach with 27 Tests

Writing tests first (before implementation) caught several issues:
- Content hash determinism
- Whitespace normalization
- Span attribute location
- Duplicate detection logic

Tests cover:
- `TestFactTypeEnum` - Enum value validation
- `TestExtractedFactDataclass` - Dataclass structure
- `TestContentHashing` - Hash determinism and normalization
- `TestBraintrustQueries` - BTQL query generation
- `TestFactExtraction` - Span parsing
- `TestStoreIfNovel` - Deduplication logic
- `TestEmbeddingIntegration` - Batch embedding
- `TestCLI` - Argument parsing
- `TestBatchProcessing` - Checkpointing
- `TestFullPipeline` - End-to-end mock

### Real Data Validation

Testing against actual Braintrust API (470 sessions) revealed:
- Span structure mismatches (metadata vs span_attributes)
- Session access control issues
- Optimal batch sizes (50 sessions)

### Content-Hash Deduplication

```python
def content_hash(content: str, metadata: dict[str, Any] | None = None) -> str:
    """Generate deterministic hash for deduplication."""
    normalized = {
        "content": content.strip().lower(),
        "type": metadata.get("type") if metadata else None,
        "source_session": metadata.get("source_session") if metadata else None,
    }
    return hashlib.sha256(
        json.dumps(normalized, sort_keys=True).encode()
    ).hexdigest()[:16]
```

Key design decisions:
- **Normalized content**: Strip whitespace, lowercase for consistent matching
- **Include type**: Same text as "goal" vs "decision" should be different facts
- **Include source_session**: Same fact from different sessions are distinct
- **Exclude timestamps**: Not semantic - allow dedup across re-runs

## Key Decisions & Rationale

### Decision 1: Content-Hash Deduplication (SHA256)

**Alternatives Considered**:
- Timestamp-based: Compare created_at to avoid duplicates
- UUID per fact: Generate new ID every time

**Chosen**: Content hash

**Rationale**: Enables idempotent backfill. Same content always produces same hash. Re-running backfill after partial failure just skips already-stored facts without creating duplicates.

### Decision 2: Dedicated "backfill" Session ID

**Alternatives Considered**:
- Use original session_id for each fact
- Create unique session per backfill run

**Chosen**: All backfill data under `session_id="backfill"`

**Rationale**: Easy identification of backfilled vs real-time data. Enables bulk operations on backfill data. Original session stored in metadata.

### Decision 3: Batch Embed After Extraction Complete

**Alternatives Considered**:
- Embed per-fact as extracted (N API calls)
- Embed inline during extraction

**Chosen**: Batch embed entire fact list

**Rationale**: Single API call to embedding provider is more efficient. Reduces rate limit hits. Summaries are final after extraction pass.

### Decision 4: Six-Stage Pipeline with Checkpoints

**Alternatives Considered**:
- Single-pass: Fetch-parse-store all at once
- Two-pass: Extract then enrich

**Chosen**: Six-stage with each stage idempotent and checkpointed

**Rationale**:
- Each stage can be retried independently
- Partial failures don't require full restart
- Clear separation of concerns
- Easy debugging (inspect output at each stage)

### Decision 5: SQLite Default, PostgreSQL for Production

**Alternatives Considered**:
- PostgreSQL only
- In-memory for speed

**Chosen**: SQLite default with `--backend postgres` option

**Rationale**: Zero-config for local development. PostgreSQL for multi-agent coordination and production scale.

## Data Structures

### FactType Enum

```python
class FactType(Enum):
    """Type of extracted fact."""
    GOAL = "goal"              # Session goal from ledger
    DECISION = "decision"      # Key decision with rationale
    FILE_CHANGE = "file_change"  # Files modified
    OUTCOME = "outcome"        # Session outcome (success/failure)
    LEARNING = "learning"      # General learning extracted by LLM
    ERROR = "error"            # Error encountered and resolution
    AGENT_OUTPUT = "agent_output"  # Agent task output
```

### ExtractedFact Dataclass

```python
@dataclass
class ExtractedFact:
    """A fact extracted from a session trace."""
    content: str              # The fact text
    fact_type: FactType       # Type categorization
    source_session: str       # Original session ID
    metadata: dict[str, Any]  # Additional context
    content_hash: str         # SHA256 hash for dedup (auto-generated)
    embedding: list[float] | None  # Vector embedding (populated in Stage 5)
```

### BackfillResult Dataclass

```python
@dataclass
class BackfillResult:
    """Result of backfill operation."""
    session_id: str
    facts_extracted: int
    facts_stored: int
    facts_skipped_duplicate: int
    errors: list[str]
    duration_seconds: float
```

### Braintrust Span Structure

Spans from BTQL have this structure:
```python
{
    "span_id": "abc123",
    "created": "2025-12-27T10:00:00Z",
    "input": {...} or "string",
    "output": {...} or "string",
    "span_attributes": {
        "type": "tool" | "task" | "llm",
        "name": "Write" | "Read" | "Claude Code: ..."
    },
    "metadata": {
        "tool_name": "Write",  # <-- IMPORTANT: tool_name is here, not in span_attributes
        "session_id": "...",
        ...
    }
}
```

### Hierarchical Context Structure

From `get_hierarchical_context()`:
```python
{
    "handoff": {
        "key_decisions": ["- Decision 1", "- Decision 2"],
        "files_modified": ["/path/to/file.py"],
        ...
    },
    "ledger": {
        "goal": "Build feature X",
        "outcome": "SUCCESS",
        ...
    }
}
```

## API Reference

### CLI Usage

```bash
# Single session backfill
uv run python scripts/agentica/memory_backfill.py \
    --session-id <session-id>

# Date range backfill
uv run python scripts/agentica/memory_backfill.py \
    --start-date 2025-12-20 \
    --end-date 2025-12-27

# Resume interrupted backfill
uv run python scripts/agentica/memory_backfill.py \
    --resume

# Dry run (extract but don't store)
uv run python scripts/agentica/memory_backfill.py \
    --start-date 2025-12-27 \
    --dry-run \
    --embedding-provider mock
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `--session-id` | - | Backfill single session by ID |
| `--start-date` | - | Start date (YYYY-MM-DD) for batch |
| `--end-date` | - | End date (YYYY-MM-DD) for batch |
| `--resume` | false | Resume from checkpoint |
| `--batch-size` | 50 | Sessions per batch |
| `--concurrency` | 5 | Parallel workers |
| `--project` | claude-continuity-kit | Braintrust project name |
| `--backend` | sqlite | Memory backend (sqlite/postgres) |
| `--embedding-provider` | openai | Embedding model (openai/voyage/mock) |
| `--dry-run` | false | Extract without storing |

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BRAINTRUST_API_KEY` | Yes | Braintrust API key |
| `OPENAI_API_KEY` | If using openai embeddings | OpenAI API key |
| `VOYAGE_API_KEY` | If using voyage embeddings | Voyage AI API key |

### Key Functions

```python
# Main entry points
async def backfill_session(
    session_id: str,
    project_id: str,
    api_key: str,
    memory_backend: str = "sqlite",
    db_path: Path | None = None,
    embedding_provider: str = "openai",
    dry_run: bool = False,
) -> BackfillResult

async def backfill_range(
    start_date: str,
    end_date: str,
    project_id: str,
    api_key: str,
    config: BatchConfig | None = None,
    memory_backend: str = "sqlite",
    db_path: Path | None = None,
    embedding_provider: str = "openai",
    checkpoint_path: Path | None = None,
    resume: bool = False,
) -> list[BackfillResult]

# Extraction
def extract_facts_from_context(
    context: dict[str, Any],
    session_id: str,
) -> list[ExtractedFact]

def extract_facts_from_spans(
    spans: list[dict[str, Any]],
    session_id: str,
) -> list[ExtractedFact]

# Deduplication
async def store_if_novel(
    memory: Any,
    fact: ExtractedFact,
) -> tuple[str | None, bool]

# Embedding
async def embed_facts(
    facts: list[ExtractedFact],
    embedding_service: Any,
) -> list[ExtractedFact]
```

## Testing

### Run All Unit Tests

```bash
uv run pytest tests/unit/test_memory_backfill.py -v
```

### Run Specific Test Classes

```bash
# Data structures
uv run pytest tests/unit/test_memory_backfill.py::TestFactTypeEnum -v
uv run pytest tests/unit/test_memory_backfill.py::TestContentHashing -v

# Braintrust queries
uv run pytest tests/unit/test_memory_backfill.py::TestBraintrustQueries -v

# Fact extraction
uv run pytest tests/unit/test_memory_backfill.py::TestFactExtraction -v

# Storage
uv run pytest tests/unit/test_memory_backfill.py::TestStoreIfNovel -v

# CLI
uv run pytest tests/unit/test_memory_backfill.py::TestCLI -v

# Full pipeline
uv run pytest tests/unit/test_memory_backfill.py::TestFullPipeline -v
```

### Test Coverage by Component

| Test Class | Tests | What It Validates |
|------------|-------|-------------------|
| `TestFactTypeEnum` | 1 | Enum values exist and match expected strings |
| `TestExtractedFactDataclass` | 1 | Dataclass fields and auto-hash generation |
| `TestContentHashing` | 5 | Hash determinism, normalization, exclusions |
| `TestBraintrustQueries` | 4 | BTQL query format, mocked API responses |
| `TestFactExtraction` | 6 | Goal, decision, file, error extraction |
| `TestStoreIfNovel` | 2 | Novel vs duplicate detection |
| `TestEmbeddingIntegration` | 1 | Batch embedding with mock provider |
| `TestCLI` | 4 | Argument parsing for all modes |
| `TestBatchProcessing` | 2 | Checkpoint save/load |
| `TestFullPipeline` | 1 | End-to-end with mocks |

### Integration Testing

For tests requiring real Braintrust access:

```bash
# Set API key
export BRAINTRUST_API_KEY=<your-key>

# Run with real data
uv run python scripts/agentica/memory_backfill.py \
    --project agentica \
    --start-date 2025-12-27 \
    --dry-run \
    --embedding-provider mock
```

## Future Work: Two-Pass Map/Reduce

### Problem

Large sessions (200-1500 spans, 1M+ tokens) exceed LLM context limits. Decisions at span N may reference context from span M. Single-pass processing cannot handle cross-referential relationships.

### Proposed Solution

```
Phase 0: Pre-scan - Build reference graph
Phase 1: Map - Summarize each span (2 sentences), store in Blackboard
Phase 2: Batch embed - Persist summaries to MemoryService
Phase 3: Map - Extract decisions, inject referenced summaries
Phase 4: Reduce - Synthesize decision report
```

### Key Integration Points

- `patterns/blackboard.py` - Ephemeral shared state during run
- `memory_service_pg.py` - Persistent storage after Pass 1
- `embedding_service.py` - Batch embed summaries
- `claude_scope.py` - Cross-agent queries

### Token Economics

| Phase | Estimated Tokens |
|-------|-----------------|
| Pre-scan | ~50k |
| Pass 1 (summarize) | ~1M across mappers |
| Pass 2 (decisions) | ~400k (summaries, not full spans) |
| Reducer | ~50k |
| **Total** | ~1.5M distributed |

### Implementation Skeleton

```python
async def extract_decisions_two_pass(session_id: str):
    """Two-pass decision extraction for large sessions."""

    # Phase 0: Build reference graph
    spans = await fetch_session_spans(session_id)
    ref_graph = build_reference_graph(spans)

    # Phase 1: Summarize with MapReduce
    blackboard = BlackboardState()
    chunks = chunk_by_references(spans, ref_graph)

    for chunk in chunks:
        summaries = await mapper.summarize(chunk)
        for span_id, summary in summaries.items():
            blackboard[f"summary:{span_id}"] = summary

    # Phase 2: Persist summaries
    await batch_embed_and_store(blackboard.summaries)

    # Phase 3: Extract decisions with context
    decision_chunks = enrich_with_references(chunks, ref_graph, blackboard)
    decisions = await decision_mapper.extract(decision_chunks)

    # Phase 4: Reduce
    report = await reducer.synthesize(decisions)
    return report
```

## Troubleshooting

### Error: BRAINTRUST_API_KEY not found

**Symptom**: Script exits with "BRAINTRUST_API_KEY not found"

**Fix**:
```bash
# Option 1: Export in shell
export BRAINTRUST_API_KEY=<your-key>

# Option 2: Add to ~/.claude/.env
echo "BRAINTRUST_API_KEY=<your-key>" >> ~/.claude/.env

# Option 3: Source from global config
source ~/.claude/.env
```

### Error: 401 Unauthorized from Braintrust

**Symptom**: BTQL queries return 401

**Fix**:
1. Verify API key is valid in Braintrust dashboard
2. Check key hasn't expired
3. Ensure key has read access to project

### Error: 403 on specific sessions

**Symptom**: Some sessions return 403, others work

**Cause**: Multi-user project, session belongs to different user

**Fix**: This is expected. The script logs the error and continues to next session.

### No facts extracted from session

**Symptom**: `facts_extracted: 0` for sessions that should have data

**Debug steps**:
1. Verify session has spans: Check Braintrust dashboard
2. Check hierarchical context: `get_hierarchical_context(session_id)`
3. Verify span structure: Print raw spans to confirm `metadata.tool_name`

### Embeddings failing

**Symptom**: Store succeeds but embeddings are None

**Fix**:
1. Verify embedding provider API key is set
2. Use `--embedding-provider mock` for testing
3. Check embedding service logs for rate limit errors

### Resume not working

**Symptom**: `--resume` starts from beginning

**Fix**:
1. Check checkpoint file exists: `ls .claude/cache/backfill_checkpoint.json`
2. Verify checkpoint format: `cat .claude/cache/backfill_checkpoint.json`
3. Delete corrupt checkpoint to start fresh

## File References

| File | Purpose |
|------|---------|
| `scripts/agentica/memory_backfill.py` | Main implementation (933 lines) |
| `tests/unit/test_memory_backfill.py` | Unit tests (27 tests) |
| `thoughts/shared/plans/2025-12-27-memory-backfill.md` | Implementation plan |
| `thoughts/shared/plans/2025-12-27-memory-backfill-validation.md` | Plan validation |
| `thoughts/shared/handoffs/open-source-release/research-backfill-best-practices.md` | Initial research |
| `thoughts/shared/handoffs/open-source-release/codebase-analysis-backfill.md` | Codebase analysis |
| `thoughts/shared/handoffs/open-source-release/research-span-processing.md` | Two-pass research |
| `thoughts/shared/handoffs/open-source-release/integration-span-memory.md` | Integration design |
| `thoughts/shared/handoffs/open-source-release/2025-12-27_18-52-00_memory-backfill-two-pass-mapreduce.md` | Session handoff |

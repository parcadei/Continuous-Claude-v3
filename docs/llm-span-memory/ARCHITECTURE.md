# LLMSpanMemory Architecture

## 1. System Overview

LLMSpanMemory provides per-LLM-span granularity for memory extraction from Braintrust session traces. Unlike the session-level `ExtractedFact` model, it captures the decision-making process at each LLM invocation within a conversation.

```
+---------------------------------------------------------------------+
|                      BRAINTRUST SESSION                              |
+---------------------------------------------------------------------+
|  Session Root (root_span_id)                                        |
|    |                                                                 |
|    +-- Turn 1 (task span) -+-- LLM Span 1 --> LLMSpanMemory        |
|    |                       +-- LLM Span 2 --> LLMSpanMemory        |
|    |                       +-- LLM Span 3 --> LLMSpanMemory        |
|    |                       +-- Tool Spans (Read, Write, Bash...)   |
|    |                                                                 |
|    +-- Turn 2 (task span) -+-- LLM Span 4 --> LLMSpanMemory        |
|    |                       +-- LLM Span 5 --> LLMSpanMemory        |
|    |                       +-- Tool Spans                           |
|    |                                                                 |
|    +-- Turn 3 (task span) -+-- LLM Span 6 --> LLMSpanMemory        |
|    |                       +-- ...                                  |
|    |                                                                 |
|    +-- Turn N ...                                                   |
+---------------------------------------------------------------------+
```

### Key Insight

A single user turn can generate multiple LLM spans as Claude Code iterates through tool calls, retries, and reasoning steps. The `LLMSpanMemory` model captures each of these decision points individually, enabling:

- Fine-grained retrieval for similar past decisions
- Dataset construction for DLLM/RRF evaluation
- Error pattern correlation with specific reasoning steps

---

## 2. Data Flow

```
                    Braintrust API
                         |
                         v
              +---------------------+
              | fetch_session_spans |
              +---------------------+
                         |
                         v
             +------------------------+
             | build_turn_llm_hierarchy|
             +------------------------+
                         |
                         v
    +------------------------------------------+
    |       extract_llm_span_memories()        |
    +------------------------------------------+
    |                                          |
    |  Per-Turn Extraction:                    |
    |  +----------------------------------+    |
    |  | extract_user_intent_raw()        |    |
    |  | (from Turn span input, 500 char) |    |
    |  +----------------------------------+    |
    |                                          |
    |  Per-LLM-Span Extraction:               |
    |  +----------------------------------+    |
    |  | extract_llm_decision()           |    |
    |  | (from output.content, 300 char)  |    |
    |  +----------------------------------+    |
    |  +----------------------------------+    |
    |  | extract_tools_from_llm_span()    |    |
    |  | (from output.tool_calls)         |    |
    |  +----------------------------------+    |
    |                                          |
    |  Per-Turn (shared by all spans):        |
    |  +----------------------------------+    |
    |  | extract_files_from_turn()        |    |
    |  | (from sibling tool spans)        |    |
    |  +----------------------------------+    |
    |  +----------------------------------+    |
    |  | detect_error_in_turn()           |    |
    |  | (from Bash span stdout/stderr)   |    |
    |  +----------------------------------+    |
    |                                          |
    |  Per-Session (shared by all memories):  |
    |  +----------------------------------+    |
    |  | lookup_session_outcome()         |    |
    |  | (from context.db handoffs table) |    |
    |  +----------------------------------+    |
    |                                          |
    +------------------------------------------+
                         |
                         v
              +---------------------+
              | EmbeddingService    |
              | (embed_batch)       |
              +---------------------+
                         |
                         v
            +------------------------+
            | store_llm_span_memory  |
            | (dedupe by hash)       |
            +------------------------+
                         |
                         v
              +---------------------+
              |   Memory Backend    |
              | (SQLite or Postgres)|
              +---------------------+
```

---

## 3. Component Descriptions

### 3.1 Data Structures

#### LLMSpanMemory (dataclass)

**Location:** `scripts/agentica_patterns/memory_backfill.py` lines 90-157

**Purpose:** Represents a single LLM span's memory entry for vector search and retrieval.

| Field | Type | Description |
|-------|------|-------------|
| `span_id` | `str` | Unique identifier from Braintrust |
| `turn_number` | `int` | Conversation turn (1, 2, 3...) |
| `session_id` | `str` | root_span_id from Braintrust |
| `user_intent` | `str` | Extracted/truncated user request |
| `decision` | `str` | Claude's reasoning/output |
| `tools_called` | `list[str]` | Tool names invoked (deduplicated) |
| `files_touched` | `list[str]` | File paths from turn's tool spans |
| `outcome` | `str \| None` | Session outcome (SUCCEEDED, FAILED) |
| `error_summary` | `str \| None` | Error context if detected |
| `embedding_text` | `str` | Auto-computed: `{user_intent}\n{decision}` |
| `content_hash` | `str` | SHA256[:16] for deduplication |
| `embedding` | `list[float] \| None` | Vector representation |

**Auto-computed fields (in `__post_init__`):**
- `embedding_text`: Concatenation of user_intent and decision
- `content_hash`: Deterministic hash including span_id + session_id

---

### 3.2 Hierarchy Parser

#### build_turn_llm_hierarchy()

**Location:** `scripts/agentica_patterns/memory_backfill.py` lines 480-563

**Input:** `list[dict[str, Any]]` - Raw spans from BTQL query

**Output:**
```python
{
    "Turn 1": {
        "span_id": "abc123",
        "input": "user prompt...",
        "llm_spans": [span_dict1, span_dict2, ...],
    },
    "Turn 2": {...},
}
```

**Logic:**
1. Build span lookup by `span_id`
2. Find Turn spans: `span_attributes.type == "task"` AND `name.startswith("Turn ")`
3. For each Turn, find LLM spans where `span_parents` includes Turn's `span_id`
4. Return structured hierarchy

---

### 3.3 Extraction Functions

#### extract_user_intent_raw()

**Location:** lines 566-604

**Input:** Turn span dict, max_chars (default: 500)

**Output:** Raw user intent string

**Logic:**
1. Get `input` field from Turn span
2. Handle string, dict (with `content`/`text`/`message` keys), or None
3. Truncate with "..." suffix if exceeding max_chars

---

#### extract_llm_decision()

**Location:** lines 607-647

**Input:** LLM span dict, max_chars (default: 300)

**Output:** Decision/reasoning string

**Logic:**
1. Get `output` field from LLM span
2. If dict, extract `content` field
3. Strip and truncate with "..." suffix

---

#### extract_tools_from_llm_span()

**Location:** lines 650-697

**Input:** LLM span dict

**Output:** `list[str]` - Deduplicated tool names

**Logic:**
1. Get `output.tool_calls` array
2. For each tool_call, extract `function.name`
3. Preserve order, deduplicate

---

#### extract_files_from_turn()

**Location:** lines 700-757

**Input:** turn_span_id, all_spans

**Output:** `list[str]` - File paths

**Logic:**
1. Find tool spans (Read, Write, Edit) where `span_parents` includes turn_span_id
2. Extract `file_path` from input (handle string or dict)
3. Deduplicate paths

---

#### detect_error_in_turn()

**Location:** lines 807-886

**Input:** turn_span_id, all_spans

**Output:** Error summary string or None

**Logic:**
1. Find Bash spans under turn
2. Check stdout/stderr for error patterns:
   - Python tracebacks
   - Pytest failures (FAILED tests/)
   - TypeScript errors (error TS)
   - Common exception types
3. Return first error context (max 500 chars)

---

#### lookup_session_outcome()

**Location:** lines 760-804

**Input:** root_span_id

**Output:** `tuple[str | None, str | None]` - (outcome, outcome_notes)

**Logic:**
1. Check `CONTEXT_DB_PATH` env or default `.claude/cache/context.db`
2. Query: `SELECT outcome, outcome_notes FROM handoffs WHERE root_span_id = ?`
3. Return (None, None) if not found or DB doesn't exist

---

### 3.4 Main Extraction

#### extract_llm_span_memories()

**Location:** lines 979-1059

**Input:** spans list, session_id

**Output:** `list[LLMSpanMemory]`

**Logic:**
1. Build turn->LLM span hierarchy
2. Lookup session outcome once (shared)
3. For each turn:
   - Parse turn_number from name ("Turn 1" -> 1)
   - Extract user_intent from turn input
   - Detect errors in turn
   - Extract files from turn
   - For each LLM span:
     - Extract decision
     - Extract tools_called
     - Create LLMSpanMemory with all fields

---

### 3.5 Storage

#### store_llm_span_memory()

**Location:** lines 1316-1378

**Input:** memory backend, LLMSpanMemory

**Output:** `tuple[str | None, bool]` - (memory_id, was_novel)

**Logic:**
1. Check for duplicate by content_hash search
2. Build metadata dict with structured fields
3. Store with embedding_text as content
4. Return (None, False) for duplicates

**Metadata structure:**
```python
{
    "span_id": "...",
    "session_id": "...",
    "turn_number": 1,
    "content_hash": "...",
    "tools_called": ["Read", "Write"],
    "files_touched": ["/path/to/file.py"],
    "outcome": "SUCCEEDED",
    "error_summary": None,
    "memory_type": "llm_span_memory",  # Distinguishes from ExtractedFact
}
```

---

## 4. Design Decisions

### 4.1 Per-LLM-Span Granularity (not per-turn)

**Decision:** Create one `LLMSpanMemory` per LLM span, not per turn.

**Rationale:**
- A single turn can have 11+ LLM spans (observed in real data: Turn 1 had 11 LLM spans)
- Each LLM span represents a distinct reasoning/decision step
- Enables retrieval of specific decision patterns (e.g., "how did Claude handle file not found?")
- Supports DLLM dataset construction at correct granularity

**Alternative rejected:** Per-turn aggregation would lose decision-level fidelity.

---

### 4.2 content_hash Includes span_id + session_id

**Decision:** Hash includes both span_id and session_id, not just content.

**Rationale:**
- **Same decision in different spans:** Claude might make similar decisions in multiple spans within a turn. Each should be stored separately.
- **Same content across sessions:** If two sessions have identical user requests and responses, they're still separate memory entries.
- **Deduplication target:** Only exact re-processing of the same span should be deduplicated.

**Hash computation (lines 141-156):**
```python
hash_input = {
    "span_id": self.span_id,
    "session_id": self.session_id,
    "user_intent": self.user_intent,
    "decision": self.decision,
}
return hashlib.sha256(json.dumps(hash_input, sort_keys=True).encode()).hexdigest()[:16]
```

---

### 4.3 Truncation Limits (500/300 chars)

**Decision:**
- User intent: max 500 characters
- Decision: max 300 characters

**Rationale:**
- **Token budget:** Each memory entry should be ~100-150 tokens for embedding
- **Retrieval quality:** Longer text dilutes embedding signal
- **Storage efficiency:** SQLite/Postgres row size optimization
- **Asymmetry:** User prompts often contain context that's less critical than Claude's decision

**Truncation behavior:** Smart truncation at word boundaries with "..." suffix.

---

### 4.4 Outcome Lookup from context.db (not Braintrust)

**Decision:** Session outcome comes from local `context.db` handoffs table, not Braintrust metadata.

**Rationale:**
- Braintrust doesn't reliably store session outcome in span metadata
- The `SessionEnd` hook writes outcome to `handoffs` table
- This creates a dependency on the continuity kit's local state

**Graceful degradation:** Returns (None, None) if DB doesn't exist or query fails.

---

### 4.5 Coexistence with ExtractedFact

**Decision:** LLMSpanMemory coexists with ExtractedFact, not replaces it.

**Rationale:**
- `ExtractedFact`: Session-level facts (goals, outcomes, file changes)
- `LLMSpanMemory`: Per-span decision records
- Different retrieval use cases:
  - "What files were modified in session X?" -> ExtractedFact
  - "How did Claude reason about file permission errors?" -> LLMSpanMemory

**Integration:** `backfill_session()` extracts both models when `--extract-span-memories` flag is set.

---

## 5. Dependencies

### Internal Dependencies

| Module | Purpose |
|--------|---------|
| `embedding_service.py` | Generate vector embeddings |
| `memory_factory.py` | Create memory backend instance |
| `span_processor.py` | Two-pass extraction (optional) |

### External Dependencies

| Service | Purpose |
|---------|---------|
| Braintrust API | Fetch session spans (BTQL) |
| context.db | Lookup session outcome |
| OpenAI/Voyage API | Generate embeddings |

### Database Schema

**Memory Backend table (conceptual):**
```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    content TEXT,          -- embedding_text
    embedding BLOB,        -- vector
    metadata JSON,         -- structured fields
    created_at TIMESTAMP
);
```

---

## 6. Usage

### CLI

```bash
# Single session with span memories
uv run python -m runtime.harness scripts/agentica_patterns/memory_backfill.py \
    --session-id <session-id> \
    --extract-span-memories

# Dry run (extract but don't store)
uv run python -m runtime.harness scripts/agentica_patterns/memory_backfill.py \
    --session-id <session-id> \
    --extract-span-memories \
    --dry-run
```

### Programmatic

```python
from scripts.agentica.memory_backfill import (
    fetch_session_spans,
    extract_llm_span_memories,
    store_llm_span_memory,
)

# Fetch spans
spans = await fetch_session_spans(session_id, project_id, api_key)

# Extract memories
memories = extract_llm_span_memories(spans, session_id)

# Store (with deduplication)
for mem in memories:
    memory_id, was_novel = await store_llm_span_memory(backend, mem)
```

---

## 7. Related Files

| File | Purpose |
|------|---------|
| `/scripts/agentica_patterns/memory_backfill.py` | Core implementation |
| `/scripts/agentica_patterns/embedding_service.py` | Embedding generation |
| `/scripts/agentica_patterns/memory_factory.py` | Backend instantiation |
| `/tests/unit/test_memory_backfill.py` | Unit tests |
| `/thoughts/shared/plans/2025-12-28-llm-span-memory-model.md` | Original plan |

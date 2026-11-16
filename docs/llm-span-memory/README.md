# LLMSpanMemory

Per-LLM-span memory extraction for fine-grained retrieval from Claude Code sessions.

## Problem Statement

### What Was Broken

The original memory extraction pipeline (`extract_facts_from_spans()`) had fundamental limitations:

1. **Turn 1 Tunnel Vision**: Only extracted the goal from Turn 1's input, completely missing user prompts from turns 2-6+.

2. **Session-Level Granularity**: Facts were extracted at the session level, losing the multi-step reasoning chains that happen within each turn.

3. **Missed LLM Decision Points**: A single turn can have 11+ LLM interactions (observed in real sessions), each representing a distinct reasoning step. These were collapsed into nothing.

4. **No Outcome Correlation**: Extracted facts had no link to whether the session succeeded or failed, making it impossible to learn from outcomes.

### The Multi-Turn, Multi-LLM-Span Reality

Real Claude Code sessions have a hierarchical structure:

```
Session Root (root_span_id)
  |
  +-- Turn 1 (user prompt #1)
  |     +-- LLM span 1.1 (initial reasoning)
  |     +-- LLM span 1.2 (tool planning)
  |     +-- LLM span 1.3 (follow-up)
  |     +-- ... (11 LLM spans in one turn)
  |
  +-- Turn 2 (user prompt #2)
  |     +-- LLM span 2.1
  |     +-- LLM span 2.2
  |
  +-- Turn 3-6...
```

A 6-turn session analyzed from Braintrust showed:
- Turn 1: 11 LLM spans
- Turn 2: 2 LLM spans
- Turn 3: 1 LLM span
- Turn 4: 2 LLM spans
- Turn 5: 13 LLM spans
- Turn 6: 0 LLM spans (tool-only turn)

**29 reasoning steps** that the old extraction completely ignored.

### Why Session-Level Facts Weren't Enough

| Old Approach | Problem |
|--------------|---------|
| Extract goal from Turn 1 only | Misses multi-turn conversations |
| One fact per session | Collapses 29 reasoning steps into 1 |
| No LLM output parsing | Misses decisions, tool choices, file touches |
| No outcome link | Can't learn "what worked" vs "what failed" |

## Solution

### Per-LLM-Span Granularity

LLMSpanMemory extracts one memory unit per LLM span, preserving:
- The user's intent for that turn
- Claude's decision/reasoning
- Which tools were called
- Which files were touched
- Session outcome (from handoffs table)
- Any errors encountered

### What Each Field Captures

| Field | Source | Purpose |
|-------|--------|---------|
| `span_id` | LLM span from Braintrust | Unique identifier |
| `turn_number` | Parent turn span name | Position in conversation |
| `session_id` | root_span_id | Links to session |
| `user_intent` | Turn input (LLM-summarized) | What the user asked |
| `decision` | LLM output.content | Claude's reasoning |
| `tools_called` | output.tool_calls[].function.name | Actions taken |
| `files_touched` | Write/Edit tool inputs | Files modified |
| `outcome` | context.db handoffs table | SUCCEEDED/FAILED/etc |
| `error_summary` | Bash stdout/stderr | Runtime errors |
| `embedding_text` | user_intent + decision | Vector search target |
| `content_hash` | Hash of embedding_text | Deduplication |

### How It Enables Better Retrieval

1. **Semantic Search**: Query "how did I fix the async race condition?" and retrieve the specific LLM span where that decision was made.

2. **Outcome Filtering**: "Show me decisions from successful sessions" - filter by outcome before retrieval.

3. **Tool Pattern Matching**: "Find spans where I used Task + Write together" - structured queries on tools_called.

4. **Error Learning**: "What errors have I seen with pytest?" - search error_summary field.

## Use Cases

### Finding Past Decisions That Worked

Query memories where `outcome = "SUCCEEDED"` and semantic match on your current problem:

```python
# Pseudocode
memories = await memory.search(
    query="implement webhook handler with retry logic",
    filter={"outcome": "SUCCEEDED"},
    top_k=5
)
```

Returns LLM spans from successful sessions that dealt with similar problems.

### Learning from Errors

Query memories with `error_summary IS NOT NULL`:

```python
# Find common errors
memories = await memory.search(
    query="ModuleNotFoundError",
    filter={"error_summary": {"$ne": None}},
    top_k=10
)
```

Surfaces past errors and how they were resolved (by looking at subsequent spans).

### Building DLLM/RRF Datasets

LLMSpanMemory provides the raw data needed for:

- **DLLM (Distilled LLM)**: Training data for smaller models from Claude's reasoning
- **RRF (Reciprocal Rank Fusion)**: Multiple retrieval signals to rank relevance

Each span memory is a `(input, output)` pair with structured metadata for filtering and weighting.

## Quick Start

### Extract Span Memories from a Session

```bash
# Extract and store span memories
uv run python -m runtime.harness scripts/agentica_patterns/memory_backfill.py \
  --session-id <SESSION_ID> \
  --extract-span-memories
```

### Dry Run (Preview Without Storing)

```bash
# Preview what would be extracted
uv run python -m runtime.harness scripts/agentica_patterns/memory_backfill.py \
  --session-id <SESSION_ID> \
  --extract-span-memories \
  --dry-run
```

### Batch Process Recent Sessions

```bash
# Process last 10 sessions
uv run python -m runtime.harness scripts/agentica_patterns/memory_backfill.py \
  --recent 10 \
  --extract-span-memories
```

## Data Model

### LLMSpanMemory Dataclass

```python
@dataclass
class LLMSpanMemory:
    """Per-LLM-span memory unit for fine-grained retrieval."""

    # Identity
    span_id: str           # Unique LLM span ID from Braintrust
    turn_number: int       # Which turn this belongs to (1, 2, 3...)
    session_id: str        # root_span_id from Braintrust

    # Content (summarized, ~50-100 tokens each)
    user_intent: str       # LLM-summarized from turn input
    decision: str          # Claude's output.content (truncated/summarized)

    # Actions (structured, minimal tokens)
    tools_called: list[str]       # ["Task", "Write", "Bash"]
    files_touched: list[str]      # paths only, no content

    # Outcome (from context.db correlation)
    outcome: str | None    # SUCCEEDED, FAILED, PARTIAL_PLUS, PARTIAL_MINUS, UNKNOWN
    error_summary: str | None  # Only if error detected in Bash stdout

    # Embedding target
    embedding_text: str    # Concat of user_intent + decision (for vector search)
    content_hash: str      # For deduplication
    embedding: list[float] | None = None  # Vector embedding (generated)
```

### Example JSON Output

```json
{
  "span_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "turn_number": 1,
  "session_id": "22331a58-ccc4-4fde-a760-795783db195c",
  "user_intent": "Implement webhook handler with retry logic for failed deliveries",
  "decision": "I'll create a WebhookHandler class with exponential backoff. First, let me check existing patterns in the codebase...",
  "tools_called": ["Grep", "Read", "Write"],
  "files_touched": [
    "src/handlers/webhook.py",
    "tests/test_webhook.py"
  ],
  "outcome": "SUCCEEDED",
  "error_summary": null,
  "embedding_text": "Implement webhook handler with retry logic for failed deliveries\nI'll create a WebhookHandler class with exponential backoff...",
  "content_hash": "sha256:7f8a9b0c..."
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `span_id` | `str` | UUID from Braintrust identifying this specific LLM interaction |
| `turn_number` | `int` | 1-indexed position in the conversation (Turn 1, Turn 2, etc.) |
| `session_id` | `str` | Root span ID that groups all turns in a session |
| `user_intent` | `str` | LLM-summarized version of user's request (50-100 tokens) |
| `decision` | `str` | Claude's reasoning from output.content (truncated to ~300 chars) |
| `tools_called` | `list[str]` | Deduplicated list of tools used in this span |
| `files_touched` | `list[str]` | Paths written or edited (not reads) |
| `outcome` | `str \| None` | Session outcome from handoffs table, applied to all spans |
| `error_summary` | `str \| None` | First error detected in Bash output, if any |
| `embedding_text` | `str` | Concatenation of user_intent + decision for vector embedding |
| `content_hash` | `str` | SHA256 hash for deduplication |
| `embedding` | `list[float] \| None` | Vector embedding (populated during storage) |

### Outcome Values

| Value | Meaning |
|-------|---------|
| `SUCCEEDED` | Task completed successfully |
| `PARTIAL_PLUS` | Mostly succeeded with minor issues |
| `PARTIAL_MINUS` | Partially completed with significant gaps |
| `FAILED` | Task failed to complete |
| `UNKNOWN` | Outcome not recorded (default) |

## Architecture

### Session Hierarchy

```
Braintrust Session
      |
      v
   root_span_id ──────────────────────────────────────┐
      |                                               |
      +── Turn 1 (span_parents: [root])               |
      |     +── LLM span (span_parents: [turn1])  ◄───┼── LLMSpanMemory
      |     +── LLM span                          ◄───┼── LLMSpanMemory
      |     +── Tool span (Read)                      |
      |     +── Tool span (Write)                     |
      |                                               |
      +── Turn 2 (span_parents: [root])               |
            +── LLM span                          ◄───┼── LLMSpanMemory
            +── Tool span (Bash)                      |
                                                      |
context.db ─────────────────────────────────────────┘
   handoffs table (root_span_id -> outcome)
```

### Extraction Pipeline

```
1. Fetch spans from Braintrust API
         |
         v
2. Build turn->LLM span hierarchy
         |
         v
3. For each turn:
   - Extract user_intent from turn input
   - For each LLM span in turn:
     - Extract decision from output.content
     - Extract tools_called from tool_calls
     - Extract files_touched from sibling tool spans
     - Detect errors from Bash spans
         |
         v
4. Lookup outcome from context.db
         |
         v
5. Generate embeddings
         |
         v
6. Store to memory backend (deduplicated by content_hash)
```

## Related Documentation

- [Memory Backend Architecture](../memory-backend.md) - Storage layer
- [Braintrust Memory Backfill](../braintrust-memory-backfill.md) - Full backfill pipeline
- [Agentica Integration](../AGENTICA_INTEGRATION_JOURNEY.md) - Agent framework context

## References

- Implementation plan: `thoughts/shared/plans/2025-12-28-llm-span-memory-model.md`
- Handoff document: `thoughts/shared/handoffs/open-source-release/2025-12-28_12-50-43_llm-span-memory-design.md`
- Source code: `scripts/agentica_patterns/memory_backfill.py`

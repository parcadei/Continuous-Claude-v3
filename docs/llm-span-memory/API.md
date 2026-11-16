# LLMSpanMemory API Reference

This document provides API reference for all functions in the LLMSpanMemory module (`scripts/agentica_patterns/memory_backfill.py`).

---

## LLMSpanMemory

**Signature:**
```python
@dataclass
class LLMSpanMemory:
    span_id: str
    turn_number: int
    session_id: str
    user_intent: str
    decision: str
    tools_called: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    outcome: str | None = None
    error_summary: str | None = None
    embedding: list[float] | None = None
    embedding_text: str = ""
    content_hash: str = ""
```

**Description:** Dataclass representing a memory entry for an LLM span decision. Stores the user intent and decision from an LLM span, with auto-computed fields for embedding and deduplication.

**Attributes:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| span_id | str | required | Unique identifier for this span |
| turn_number | int | required | Turn number in the conversation |
| session_id | str | required | Session this span belongs to |
| user_intent | str | required | What the user asked or intended |
| decision | str | required | The decision or action taken |
| tools_called | list[str] | [] | List of tools invoked during this span |
| files_touched | list[str] | [] | List of files read/written during this span |
| outcome | str \| None | None | Optional outcome description |
| error_summary | str \| None | None | Optional error summary if errors occurred |
| embedding | list[float] \| None | None | Optional vector representation |
| embedding_text | str | "" | Auto-computed from user_intent + decision |
| content_hash | str | "" | SHA256 hash for deduplication (16 chars) |

**Example:**
```python
memory = LLMSpanMemory(
    span_id="abc123",
    turn_number=1,
    session_id="session-xyz",
    user_intent="Create a new API endpoint",
    decision="I'll create a REST endpoint with FastAPI",
    tools_called=["Write", "Bash"],
    files_touched=["src/api.py"],
    outcome="SUCCEEDED",
)

# Auto-computed fields:
print(memory.embedding_text)  # "Intent: Create a new API endpoint\nDecision: I'll create..."
print(memory.content_hash)    # "a1b2c3d4e5f6g7h8" (16-char hex)
```

**Notes:**
- The `embedding_text` field is auto-computed from `user_intent` and `decision` in `__post_init__`
- The `content_hash` is computed from `span_id`, `session_id`, `user_intent`, and `decision` to ensure uniqueness

---

## build_turn_llm_hierarchy()

**Signature:**
```python
def build_turn_llm_hierarchy(
    spans: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
```

**Description:** Build mapping of turns to their LLM spans. Parses raw Braintrust spans to identify Turn task spans and their child LLM spans.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| spans | list[dict[str, Any]] | required | List of span dicts from BTQL query |

**Returns:** Dict mapping turn names to their info:
```python
{
    "Turn 1": {
        "span_id": "...",
        "input": "user prompt...",
        "llm_spans": [span1, span2, ...],
    },
    "Turn 2": {...},
}
```

**Example:**
```python
spans = await fetch_session_spans(session_id, project_id, api_key)
hierarchy = build_turn_llm_hierarchy(spans)

for turn_name, turn_data in hierarchy.items():
    print(f"{turn_name}: {len(turn_data['llm_spans'])} LLM spans")
```

**Notes:**
- Turn spans are identified by `span_attributes.type == "task"` and name starting with "Turn "
- LLM spans are identified by `span_attributes.type == "llm"` with `span_parents` containing the turn's `span_id`

---

## extract_user_intent_raw()

**Signature:**
```python
def extract_user_intent_raw(turn_span: dict[str, Any], max_chars: int = 500) -> str:
```

**Description:** Extract raw user intent from Turn span input. Truncates to max_chars, handles string/dict input formats.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| turn_span | dict[str, Any] | required | The Turn span dict from BTQL |
| max_chars | int | 500 | Maximum characters before truncation |

**Returns:** Raw user intent string, empty string if invalid/missing.

**Example:**
```python
turn_span = {"input": "Please refactor the authentication module"}
intent = extract_user_intent_raw(turn_span)
# Returns: "Please refactor the authentication module"

# With dict input:
turn_span = {"input": {"content": "Fix the bug in user.py"}}
intent = extract_user_intent_raw(turn_span)
# Returns: "Fix the bug in user.py"

# Truncation:
turn_span = {"input": "A" * 1000}
intent = extract_user_intent_raw(turn_span, max_chars=100)
# Returns: "AAA...AAA..." (100 chars + "...")
```

**Notes:**
- Handles `None`, string, and dict input formats
- For dict inputs, tries `content`, `text`, or `message` fields
- Returns empty string if no valid input found

---

## extract_llm_decision()

**Signature:**
```python
def extract_llm_decision(llm_span: dict[str, Any], max_chars: int = 300) -> str:
```

**Description:** Extract decision/reasoning from LLM span output. Parses output.content field, truncates to max_chars.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| llm_span | dict[str, Any] | required | The LLM span dict from BTQL |
| max_chars | int | 300 | Maximum characters before truncation |

**Returns:** Decision string, empty string if invalid/missing.

**Example:**
```python
llm_span = {
    "output": {
        "content": "I'll implement this using a factory pattern for flexibility."
    }
}
decision = extract_llm_decision(llm_span)
# Returns: "I'll implement this using a factory pattern for flexibility."

# String output:
llm_span = {"output": "Using SQLite for local storage"}
decision = extract_llm_decision(llm_span)
# Returns: "Using SQLite for local storage"
```

**Notes:**
- Handles both string and dict output formats
- For dict outputs, extracts the `content` field
- Strips whitespace from result

---

## extract_tools_from_llm_span()

**Signature:**
```python
def extract_tools_from_llm_span(llm_span: dict[str, Any]) -> list[str]:
```

**Description:** Extract tool names from LLM span output.tool_calls.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| llm_span | dict[str, Any] | required | The LLM span dict from BTQL |

**Returns:** Deduplicated list of tool names in order of first appearance.

**Example:**
```python
llm_span = {
    "output": {
        "tool_calls": [
            {"function": {"name": "Read"}},
            {"function": {"name": "Edit"}},
            {"function": {"name": "Read"}},  # duplicate
            {"function": {"name": "Bash"}},
        ]
    }
}
tools = extract_tools_from_llm_span(llm_span)
# Returns: ["Read", "Edit", "Bash"]  (deduplicated, order preserved)
```

**Notes:**
- Returns empty list if `output` is None or not a dict
- Returns empty list if `tool_calls` is missing or not a list
- Skips invalid tool call entries (None, non-dict, missing function/name)

---

## extract_files_from_turn()

**Signature:**
```python
def extract_files_from_turn(
    turn_span_id: str,
    all_spans: list[dict[str, Any]],
) -> list[str]:
```

**Description:** Extract file paths from Read/Write/Edit tool spans under a turn. Finds all tool spans where span_parents includes turn_span_id and extracts file_path from their input.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| turn_span_id | str | required | The span_id of the Turn span |
| all_spans | list[dict[str, Any]] | required | List of all spans in the session |

**Returns:** Deduplicated list of file paths.

**Example:**
```python
all_spans = [
    {"name": "Turn 1", "span_id": "turn-1"},
    {"name": "Read", "span_parents": ["turn-1"], "input": {"file_path": "/src/main.py"}},
    {"name": "Write", "span_parents": ["turn-1"], "input": {"file_path": "/src/utils.py"}},
    {"name": "Bash", "span_parents": ["turn-1"], "input": {"command": "ls"}},  # ignored
]

files = extract_files_from_turn("turn-1", all_spans)
# Returns: ["/src/main.py", "/src/utils.py"]
```

**Notes:**
- Only considers spans with names "Read", "Write", or "Edit"
- Handles both dict and JSON string input formats for `file_path`
- Returns empty list if `all_spans` is empty

---

## lookup_session_outcome()

**Signature:**
```python
def lookup_session_outcome(root_span_id: str) -> tuple[str | None, str | None]:
```

**Description:** Lookup outcome from context.db handoffs table. Queries the handoffs table by root_span_id to get the session outcome.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| root_span_id | str | required | The session's root span ID |

**Returns:** Tuple of `(outcome, outcome_notes)` - e.g., `("SUCCEEDED", None)`. Returns `(None, None)` if not found or on error.

**Example:**
```python
outcome, notes = lookup_session_outcome("session-abc123")
if outcome:
    print(f"Session outcome: {outcome}")
    if notes:
        print(f"Notes: {notes}")
else:
    print("No outcome recorded")
```

**Notes:**
- Database path is determined by `CONTEXT_DB_PATH` env var or defaults to `.claude/cache/context.db`
- Returns `(None, None)` if database doesn't exist or on any database error
- Outcome values are typically "SUCCEEDED", "FAILED", or "ABANDONED"

---

## detect_error_in_turn()

**Signature:**
```python
def detect_error_in_turn(
    turn_span_id: str,
    all_spans: list[dict[str, Any]],
) -> str | None:
```

**Description:** Detect error from Bash spans under a turn. Searches Bash tool span outputs for error patterns like tracebacks, pytest failures, and error messages.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| turn_span_id | str | required | The span_id of the Turn span |
| all_spans | list[dict[str, Any]] | required | List of all spans in the session |

**Returns:** First error summary found (truncated to 500 chars), or None.

**Example:**
```python
all_spans = [
    {"name": "Turn 1", "span_id": "turn-1"},
    {
        "name": "Bash",
        "span_parents": ["turn-1"],
        "output": {
            "stdout": "",
            "stderr": "Traceback (most recent call last):\n  File 'test.py'...\nValueError: invalid input"
        }
    },
]

error = detect_error_in_turn("turn-1", all_spans)
# Returns: "Traceback (most recent call last):\n  File 'test.py'...\nValueError: invalid input"
```

**Raises:** None - returns None on any error or if no errors detected.

**Notes:**
- Only searches Bash tool spans (name == "Bash")
- Detects patterns: Traceback, pytest failures, TypeScript errors, exit codes, Python exceptions
- Returns context around the error (up to 500 chars total)

---

## extract_llm_span_memories()

**Signature:**
```python
def extract_llm_span_memories(
    spans: list[dict[str, Any]],
    session_id: str,
) -> list[LLMSpanMemory]:
```

**Description:** Extract LLMSpanMemory objects from all spans in a session. Iterates through all turns and all LLM spans within each turn. Combines all helper functions to build complete memory objects.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| spans | list[dict[str, Any]] | required | List of span dicts from BTQL query |
| session_id | str | required | The root_span_id (session ID) for this session |

**Returns:** List of LLMSpanMemory objects, one per LLM span.

**Example:**
```python
spans = await fetch_session_spans(session_id, project_id, api_key)
memories = extract_llm_span_memories(spans, session_id)

for memory in memories:
    print(f"Turn {memory.turn_number}: {memory.user_intent[:50]}...")
    print(f"  Decision: {memory.decision[:50]}...")
    print(f"  Tools: {memory.tools_called}")
    print(f"  Files: {memory.files_touched}")
```

**Notes:**
- Returns empty list if spans is empty or no hierarchy found
- Looks up session outcome once and shares across all memories
- Each LLM span within a turn gets its own memory entry
- User intent and files_touched are shared within a turn; tools_called and decision are per-LLM-span

---

## summarize_user_intent()

**Signature:**
```python
async def summarize_user_intent(
    raw_intent: str,
    max_tokens: int = 50,
    use_llm: bool = True,
) -> str:
```

**Description:** Summarize user intent using LLM (optional). If use_llm=False or if LLM call fails, returns truncated raw intent.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| raw_intent | str | required | The raw user intent text |
| max_tokens | int | 50 | Maximum tokens for output (approx 4 chars/token) |
| use_llm | bool | True | Whether to attempt LLM summarization |

**Returns:** Summarized or truncated intent string.

**Example:**
```python
# Short intent - returned as-is
result = await summarize_user_intent("Fix the login bug")
# Returns: "Fix the login bug"

# Long intent with LLM disabled - truncated
long_intent = "Please implement a comprehensive authentication system with OAuth2..."
result = await summarize_user_intent(long_intent, max_tokens=20, use_llm=False)
# Returns: "Please implement a comprehensive..." (truncated at word boundary)

# Empty input
result = await summarize_user_intent("")
# Returns: ""
```

**Notes:**
- If intent is < 100 chars, returns as-is without summarization
- LLM summarization is not yet implemented; falls back to smart truncation
- Truncation attempts to break at word boundaries
- max_chars = max_tokens * 4 (approximate)

---

## store_llm_span_memory()

**Signature:**
```python
async def store_llm_span_memory(
    memory: Any,  # MemoryBackend protocol
    span_memory: LLMSpanMemory,
) -> tuple[str | None, bool]:
```

**Description:** Store LLMSpanMemory if novel. Similar to store_if_novel but for the new LLMSpanMemory model. Checks for duplicates by content_hash.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| memory | MemoryBackend | required | Memory backend instance (SQLite or Postgres) |
| span_memory | LLMSpanMemory | required | LLMSpanMemory to store |

**Returns:** Tuple of `(memory_id, was_novel)` - memory_id is None if duplicate or error.

**Example:**
```python
from scripts.agentica.memory_factory import create_memory_service

memory = await create_memory_service(backend="sqlite", session_id="backfill")

span_memory = LLMSpanMemory(
    span_id="span-123",
    turn_number=1,
    session_id="session-abc",
    user_intent="Create API endpoint",
    decision="Using FastAPI with Pydantic models",
    embedding=[0.1, 0.2, ...],  # Pre-computed embedding
)

memory_id, was_novel = await store_llm_span_memory(memory, span_memory)

if was_novel:
    print(f"Stored with ID: {memory_id}")
else:
    print("Duplicate - skipped")

await memory.close()
```

**Notes:**
- Checks for duplicates using `content_hash` field
- Stores `embedding_text` as the content field
- Metadata includes: span_id, session_id, turn_number, content_hash, tools_called, files_touched, outcome, error_summary, memory_type
- Returns `(None, False)` for duplicates or storage errors

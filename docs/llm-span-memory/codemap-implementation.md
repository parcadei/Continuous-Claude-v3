# LLMSpanMemory Implementation Codemap

**File:** `scripts/agentica_patterns/memory_backfill.py`
**Generated:** 2025-12-28
**Lines:** 2011

## Overview

Memory Backfill Service - Extracts LLMSpanMemory from Braintrust traces using a 6-stage pipeline:
1. Fetch - Raw spans from Braintrust (deterministic, API)
2. Parse - Structured facts from spans (deterministic, pure)
3. Dedupe - Filter to novel facts only (deterministic, hash)
4. Enrich - Add context/type metadata (deterministic, augment)
5. Embed - Generate embeddings (LLM, cache by hash)
6. Store - Write to MemoryService (deterministic, upsert)

---

## Core Data Structures

### Enums

```python
class FactType(Enum):                                    # L55-64
    """Type of extracted fact."""
    GOAL = "goal"
    DECISION = "decision"
    FILE_CHANGE = "file_change"
    OUTCOME = "outcome"
    LEARNING = "learning"
    ERROR = "error"
    AGENT_OUTPUT = "agent_output"
```

### Dataclasses

```python
@dataclass
class ExtractedFact:                                     # L67-87
    """A fact extracted from a session trace."""
    content: str
    fact_type: FactType
    source_session: str
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    embedding: list[float] | None = None
    def __post_init__(self): ...                         # L78-86

@dataclass
class LLMSpanMemory:                                     # L89-157
    """Memory entry for an LLM span decision."""
    # Required fields
    span_id: str
    turn_number: int
    session_id: str
    user_intent: str
    decision: str
    # List fields (factory defaults)
    tools_called: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)
    # Optional fields
    outcome: str | None = None
    error_summary: str | None = None
    embedding: list[float] | None = None
    # Auto-computed fields
    embedding_text: str = ""
    content_hash: str = ""
    def __post_init__(self): ...                         # L131-139
    def _compute_hash(self) -> str: ...                  # L141-156

@dataclass
class BackfillResult:                                    # L159-177
    """Result of backfill operation."""
    session_id: str
    facts_extracted: int
    facts_stored: int
    facts_skipped_duplicate: int
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    two_pass_used: bool = False
    summaries_from_two_pass: int = 0
    decisions_from_two_pass: int = 0
    span_memories_extracted: int = 0
    span_memories_stored: int = 0
    span_memories_skipped: int = 0

@dataclass
class BatchConfig:                                       # L1566-1574
    """Configuration for batch processing."""
    batch_size: int = 50
    concurrency: int = 5
    checkpoint_interval: int = 10
    retry_count: int = 3
    retry_delay: float = 1.0
```

---

## Helper Functions

### Hashing

```python
def content_hash(                                        # L179-203
    content: str,
    metadata: dict[str, Any] | None = None
) -> str:
    """Generate deterministic hash for deduplication."""
```

### Braintrust Query Layer

```python
def build_list_sessions_query(                           # L210-232
    start_date: str,
    end_date: str
) -> str:
    """Build BTQL query to list sessions in date range."""

def build_fetch_session_query(                           # L235-258
    session_id: str,
    limit: int = 200
) -> str:
    """Build BTQL query to fetch all spans for a session."""

def run_btql(                                            # L261-298
    project_id: str,
    query: str,
    api_key: str
) -> list[dict[str, Any]]:
    """Execute BTQL query against Braintrust."""

async def list_sessions_in_range(                        # L300-318
    project_id: str,
    start_date: str,
    end_date: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """List all sessions in date range."""

async def fetch_session_spans(                           # L321-339
    session_id: str,
    project_id: str,
    api_key: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Fetch all spans for a session."""
```

---

## Fact Extraction Pipeline

### Context Graph Integration

```python
def get_hierarchical_context(                            # L347-393
    root_span_id: str
) -> dict[str, Any]:
    """Get handoff + ledger from Context Graph for a session."""

def extract_facts_from_context(                          # L395-477
    context: dict[str, Any],
    session_id: str,
) -> list[ExtractedFact]:
    """Extract facts from hierarchical context (handoff + ledger)."""
```

### Turn/LLM Hierarchy Builder

```python
def build_turn_llm_hierarchy(                            # L480-563
    spans: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build mapping of turns to their LLM spans.

    Returns:
        {
            "Turn 1": {
                "span_id": "...",
                "input": "user prompt...",
                "llm_spans": [span1, span2, ...],
            },
            ...
        }
    """
```

### Field Extractors

```python
def extract_user_intent_raw(                             # L566-604
    turn_span: dict[str, Any],
    max_chars: int = 500
) -> str:
    """Extract raw user intent from Turn span input."""

def extract_llm_decision(                                # L607-647
    llm_span: dict[str, Any],
    max_chars: int = 300
) -> str:
    """Extract decision/reasoning from LLM span output."""

def extract_tools_from_llm_span(                         # L650-697
    llm_span: dict[str, Any]
) -> list[str]:
    """Extract tool names from LLM span output.tool_calls."""

def extract_files_from_turn(                             # L700-757
    turn_span_id: str,
    all_spans: list[dict[str, Any]],
) -> list[str]:
    """Extract file paths from Read/Write/Edit tool spans."""
```

### Session Context

```python
def lookup_session_outcome(                              # L760-804
    root_span_id: str
) -> tuple[str | None, str | None]:
    """Lookup outcome from context.db handoffs table."""

def detect_error_in_turn(                                # L807-886
    turn_span_id: str,
    all_spans: list[dict[str, Any]],
) -> str | None:
    """Detect error from Bash spans under a turn."""
```

---

## LLM Summarization (Phase 10)

```python
async def _call_llm_summarize(                           # L894-917
    raw_intent: str,
    max_tokens: int = 50
) -> str:
    """Call LLM to summarize user intent (internal helper)."""

async def summarize_user_intent(                         # L920-971
    raw_intent: str,
    max_tokens: int = 50,
    use_llm: bool = True,
) -> str:
    """Summarize user intent using LLM (optional)."""
```

---

## Main Extraction Functions

```python
def extract_llm_span_memories(                           # L979-1059
    spans: list[dict[str, Any]],
    session_id: str,
) -> list[LLMSpanMemory]:
    """Extract LLMSpanMemory objects from all spans in a session.

    Iterates through all turns and all LLM spans within each turn.
    Combines all helper functions to build complete memory objects.
    """

def extract_facts_from_spans(                            # L1062-1247
    spans: list[dict[str, Any]],
    session_id: str,
) -> list[ExtractedFact]:
    """Extract facts from raw spans."""
```

---

## Storage Functions

```python
async def store_if_novel(                                # L1255-1308
    memory: Any,
    fact: ExtractedFact,
) -> tuple[str | None, bool]:
    """Store fact only if content is novel."""

async def store_llm_span_memory(                         # L1316-1378
    memory: Any,
    span_memory: LLMSpanMemory,
) -> tuple[str | None, bool]:
    """Store LLMSpanMemory if novel."""

async def embed_facts(                                   # L1380-1416
    facts: list[ExtractedFact],
    embedding_service: Any,
) -> list[ExtractedFact]:
    """Generate embeddings for all facts."""
```

---

## Main Backfill Functions

```python
async def backfill_session(                              # L1419-1558
    session_id: str,
    project_id: str = "",
    api_key: str = "",
    memory_backend: str = "sqlite",
    db_path: Path | None = None,
    embedding_provider: str = "openai",
    dry_run: bool = False,
    use_two_pass: bool = False,
    two_pass_threshold: int = 50,
    extract_span_memories: bool = False,
) -> BackfillResult:
    """Backfill a single session into memory.

    6-stage pipeline:
    1. Fetch spans from Braintrust
    1.5. (Optional) SpanProcessor for two-pass extraction
    2. Parse into structured facts
    2.5. (Optional) LLMSpanMemory extraction
    3. Dedupe against existing memory
    4. Enrich with type metadata
    5. Generate embeddings
    6. Store to memory service
    """

async def save_checkpoint(                               # L1577-1598
    checkpoint_path: Path,
    last_session: str,
    last_timestamp: str,
    processed_count: int,
) -> None:
    """Save checkpoint for resume capability."""

async def load_checkpoint(                               # L1601-1612
    checkpoint_path: Path
) -> dict[str, Any] | None:
    """Load checkpoint if exists."""

async def get_resume_point(                              # L1615-1628
    checkpoint_path: Path
) -> str | None:
    """Get timestamp to resume from."""

async def backfill_range(                                # L1630-1735
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
) -> list[BackfillResult]:
    """Backfill all sessions in date range."""
```

---

## CLI Interface

```python
def parse_args(                                          # L1738-1848
    argv: list[str] | None = None
) -> argparse.Namespace:
    """Parse command line arguments."""

def load_api_key() -> str:                               # L1851-1876
    """Load API key from environment or .env file."""

def get_project_id(                                      # L1879-1913
    project_name: str,
    api_key: str
) -> str:
    """Get project ID from name."""

async def main() -> None:                                # L1916-2006
    """Main entry point."""
```

---

## Dependencies

```python
# Standard library
import argparse, asyncio, hashlib, json, os, re, sys, time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

# External
import requests

# Internal
from scripts.agentica.embedding_service import EmbeddingService
from scripts.agentica.memory_factory import create_memory_service
from scripts.agentica.span_processor import SpanProcessor
```

---

## Key Design Decisions

1. **Hash includes span_id + session_id**: Prevents same content from being deduplicated across different spans/sessions
2. **Auto-computed fields in `__post_init__`**: `embedding_text` and `content_hash` are computed automatically
3. **Deterministic hashing**: Uses `json.dumps(sort_keys=True)` for stable hash generation
4. **Truncation boundaries**: 500 chars for user_intent, 300 chars for decisions
5. **Error context window**: 50 chars before + 200 chars after error match, max 500 total

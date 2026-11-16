"""Memory Backfill Service - Populate memory from Braintrust traces.

USAGE:
    # Backfill a single session
    uv run python -m runtime.harness scripts/agentica/memory_backfill.py \
        --session-id <session-id>

    # Backfill date range
    uv run python -m runtime.harness scripts/agentica/memory_backfill.py \
        --start-date 2025-12-20 --end-date 2025-12-27

    # Resume interrupted backfill
    uv run python -m runtime.h arness scripts/agentica/memory_backfill.py \
        --resume

Requires: BRAINTRUST_API_KEY in environment

This service implements a 6-stage pipeline:
1. Fetch    - Raw spans from Braintrust (deterministic, API)
2. Parse    - Structured facts from spans (deterministic, pure)
3. Dedupe   - Filter to novel facts only (deterministic, hash)
4. Enrich   - Add context/type metadata (deterministic, augment)
5. Embed    - Generate embeddings (LLM, cache by hash)
6. Store    - Write to MemoryService (deterministic, upsert)
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import requests

# Embedding and memory imports (at module level for testability)
from scripts.agentica_patterns.embedding_service import EmbeddingService
from scripts.agentica_patterns.memory_factory import create_memory_service
from scripts.agentica_patterns.span_processor import SpanProcessor

# =============================================================================
# Phase 1: Core Data Structures
# =============================================================================


class FactType(Enum):
    """Type of extracted fact."""

    GOAL = "goal"  # Session goal from ledger
    DECISION = "decision"  # Key decision with rationale
    FILE_CHANGE = "file_change"  # Files modified
    OUTCOME = "outcome"  # Session outcome (success/failure)
    LEARNING = "learning"  # General learning extracted by LLM
    ERROR = "error"  # Error encountered and resolution
    AGENT_OUTPUT = "agent_output"  # Agent task output


@dataclass
class ExtractedFact:
    """A fact extracted from a session trace."""

    content: str
    fact_type: FactType
    source_session: str
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    embedding: list[float] | None = None

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = content_hash(
                self.content,
                {
                    "type": self.fact_type.value,
                    "source_session": self.source_session,
                },
            )


@dataclass
class LLMSpanMemory:
    """Memory entry for an LLM span decision.

    Stores the user intent and decision from an LLM span, with
    auto-computed fields for embedding and deduplication.

    Attributes:
        span_id: Unique identifier for this span
        turn_number: Turn number in the conversation
        session_id: Session this span belongs to
        user_intent: What the user asked or intended
        decision: The decision or action taken
        tools_called: List of tools invoked during this span
        files_touched: List of files read/written during this span
        outcome: Optional outcome description
        error_summary: Optional error summary if errors occurred
        embedding: Optional vector representation
        embedding_text: Auto-computed from user_intent + decision
        content_hash: SHA256 hash for deduplication (16 chars)
    """

    # Required fields - no defaults, must be provided
    span_id: str
    turn_number: int
    session_id: str
    user_intent: str
    decision: str

    # List fields with factory defaults (avoid mutable default)
    tools_called: list[str] = field(default_factory=list)
    files_touched: list[str] = field(default_factory=list)

    # Optional fields - explicit None defaults
    outcome: str | None = None
    error_summary: str | None = None
    embedding: list[float] | None = None

    # Auto-computed fields - empty defaults, computed in __post_init__
    embedding_text: str = ""
    content_hash: str = ""

    def __post_init__(self):
        """Compute derived fields after initialization."""
        # Compute embedding_text if not provided (allows override)
        if not self.embedding_text:
            self.embedding_text = f"Intent: {self.user_intent}\nDecision: {self.decision}"

        # Compute content_hash if not provided
        if not self.content_hash:
            self.content_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute deterministic hash including session for uniqueness.

        Includes session_id and span_id to prevent:
        - Same content in different spans within session
        - Same content across different sessions
        """
        hash_input = {
            "span_id": self.span_id,
            "session_id": self.session_id,
            "user_intent": self.user_intent,
            "decision": self.decision,
        }
        return hashlib.sha256(
            json.dumps(hash_input, sort_keys=True).encode()
        ).hexdigest()[:16]


@dataclass
class BackfillResult:
    """Result of backfill operation."""

    session_id: str
    facts_extracted: int
    facts_stored: int
    facts_skipped_duplicate: int
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    # Two-pass SpanProcessor metrics
    two_pass_used: bool = False
    summaries_from_two_pass: int = 0
    decisions_from_two_pass: int = 0
    # LLMSpanMemory metrics (Phase 13)
    span_memories_extracted: int = 0
    span_memories_stored: int = 0
    span_memories_skipped: int = 0


def content_hash(content: str, metadata: dict[str, Any] | None = None) -> str:
    """Generate deterministic hash for deduplication.

    Hash is based on:
    - Normalized content (stripped, lowercase)
    - type field (semantic meaning)
    - source_session field (per-session scoping)

    Excludes: timestamps, created_at, etc. (not semantic)

    Args:
        content: The fact content to hash
        metadata: Optional metadata dict (type and source_session are used)

    Returns:
        16-character hex hash string
    """
    normalized = {
        "content": content.strip().lower(),
        "type": metadata.get("type") if metadata else None,
        "source_session": metadata.get("source_session") if metadata else None,
    }
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()[
        :16
    ]


# =============================================================================
# Phase 2: Braintrust Query Layer
# =============================================================================


def build_list_sessions_query(start_date: str, end_date: str) -> str:
    """Build BTQL query to list sessions in date range.

    Args:
        start_date: ISO date (YYYY-MM-DD)
        end_date: ISO date (YYYY-MM-DD)

    Returns:
        BTQL query string
    """
    return f"""
    SELECT
        root_span_id as session_id,
        MIN(created) as start_time,
        MAX(created) as end_time,
        COUNT(*) as span_count
    FROM logs
    WHERE created >= '{start_date}T00:00:00Z'
      AND created < '{end_date}T23:59:59Z'
    GROUP BY root_span_id
    ORDER BY start_time DESC
    """


def build_fetch_session_query(session_id: str, limit: int = 200) -> str:
    """Build BTQL query to fetch all spans for a session.

    Args:
        session_id: The root_span_id of the session
        limit: Max spans to fetch (default 200)

    Returns:
        BTQL query string
    """
    return f"""
    SELECT
        span_id,
        span_parents,
        created,
        input,
        output,
        span_attributes,
        metadata
    FROM logs
    WHERE root_span_id = '{session_id}'
    ORDER BY created ASC
    LIMIT {limit}
    """


def run_btql(project_id: str, query: str, api_key: str) -> list[dict[str, Any]]:
    """Execute BTQL query against Braintrust.

    Reuses pattern from braintrust_analyze.py.

    Args:
        project_id: Braintrust project ID
        query: BTQL query string
        api_key: Braintrust API key

    Returns:
        List of result rows as dicts

    Raises:
        RuntimeError: If API returns error
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Replace "FROM logs" with the project-scoped source
    full_query = re.sub(
        r"\bFROM\s+logs\b",
        f"FROM project_logs('{project_id}')",
        query,
        flags=re.IGNORECASE,
    )

    resp = requests.post(
        "https://api.braintrust.dev/btql",
        headers=headers,
        json={"query": full_query, "fmt": "json"},
        timeout=30,
    )

    if resp.status_code == 200:
        return resp.json().get("data", [])
    else:
        raise RuntimeError(f"BTQL Error: {resp.status_code} - {resp.text}")


async def list_sessions_in_range(
    project_id: str,
    start_date: str,
    end_date: str,
    api_key: str,
) -> list[dict[str, Any]]:
    """List all sessions in date range.

    Args:
        project_id: Braintrust project ID
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        api_key: Braintrust API key

    Returns:
        List of dicts with session_id, start_time, end_time, span_count
    """
    query = build_list_sessions_query(start_date, end_date)
    return run_btql(project_id, query, api_key)


async def fetch_session_spans(
    session_id: str,
    project_id: str,
    api_key: str,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Fetch all spans for a session.

    Args:
        session_id: The root_span_id of the session
        project_id: Braintrust project ID
        api_key: Braintrust API key
        limit: Max spans to fetch (default 200)

    Returns:
        List of span dicts with input, output, span_attributes, etc.
    """
    query = build_fetch_session_query(session_id, limit)
    return run_btql(project_id, query, api_key)


# =============================================================================
# Phase 3: Fact Extraction Pipeline
# =============================================================================


def get_hierarchical_context(root_span_id: str) -> dict[str, Any]:
    """Get handoff + ledger from Context Graph for a session.

    This wraps the artifact_query.py script to fetch session context.

    Args:
        root_span_id: The session's root span ID

    Returns:
        Dict with 'handoff' and 'ledger' keys (may be None)
    """
    import subprocess

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    query_script = Path(project_dir) / "scripts" / "artifact_query.py"

    if not query_script.exists():
        return {"handoff": None, "ledger": None}

    try:
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                str(query_script),
                "--by-span-id",
                root_span_id,
                "--with-content",
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=project_dir,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            return {
                "handoff": data if data else None,
                "ledger": data.get("ledger") if data else None,
            }
    except Exception as e:
        print(f"  Context Graph query failed: {e}")

    return {"handoff": None, "ledger": None}


def extract_facts_from_context(
    context: dict[str, Any],
    session_id: str,
) -> list[ExtractedFact]:
    """Extract facts from hierarchical context (handoff + ledger).

    Args:
        context: Dict with "handoff" and "ledger" keys
        session_id: Source session ID

    Returns:
        List of ExtractedFact objects
    """
    facts: list[ExtractedFact] = []
    seen_hashes: set[str] = set()

    def add_fact(fact: ExtractedFact) -> None:
        if fact.content_hash not in seen_hashes:
            seen_hashes.add(fact.content_hash)
            facts.append(fact)

    # Extract goal from ledger
    ledger = context.get("ledger") or {}
    if goal := ledger.get("goal"):
        add_fact(
            ExtractedFact(
                content=f"Session goal: {goal}",
                fact_type=FactType.GOAL,
                source_session=session_id,
                metadata={"source": "ledger"},
            )
        )

    # Extract outcome from ledger
    if outcome := ledger.get("outcome"):
        add_fact(
            ExtractedFact(
                content=f"Session outcome: {outcome}",
                fact_type=FactType.OUTCOME,
                source_session=session_id,
                metadata={"source": "ledger"},
            )
        )

    # Extract decisions from handoff
    handoff = context.get("handoff") or {}
    if decisions_raw := handoff.get("key_decisions"):
        # Handle string (markdown list) or list
        if isinstance(decisions_raw, str):
            decisions = [
                line.strip().lstrip("- ")
                for line in decisions_raw.split("\n")
                if line.strip().startswith("-")
            ]
        else:
            decisions = decisions_raw

        for decision in decisions:
            if decision.strip():
                # Strip the leading "- " if present
                clean_decision = decision.strip().lstrip("- ")
                add_fact(
                    ExtractedFact(
                        content=f"Decision: {clean_decision}",
                        fact_type=FactType.DECISION,
                        source_session=session_id,
                        metadata={"source": "handoff"},
                    )
                )

    # Extract working files from handoff
    if files := handoff.get("files_modified"):
        for file_path in files:
            add_fact(
                ExtractedFact(
                    content=f"Modified file: {file_path}",
                    fact_type=FactType.FILE_CHANGE,
                    source_session=session_id,
                    metadata={"file_path": file_path, "source": "handoff"},
                )
            )

    return facts


def build_turn_llm_hierarchy(
    spans: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Build mapping of turns to their LLM spans.

    Parses raw Braintrust spans to identify Turn task spans and their
    child LLM spans.

    Args:
        spans: List of span dicts from BTQL query

    Returns:
        Dict mapping turn names to their info:
        {
            "Turn 1": {
                "span_id": "...",
                "input": "user prompt...",
                "llm_spans": [span1, span2, ...],
            },
            "Turn 2": {...},
        }
    """
    if not spans:
        return {}

    # Step 1: Build span lookup by span_id
    span_lookup: dict[str, dict[str, Any]] = {}
    for span in spans:
        span_id = span.get("span_id")
        if span_id:
            span_lookup[span_id] = span

    # Step 2: Find all Turn spans (type="task" and name starts with "Turn ")
    turn_spans: dict[str, dict[str, Any]] = {}
    for span in spans:
        attrs = span.get("span_attributes") or {}
        span_type = attrs.get("type")
        span_name = span.get("name", "")

        # Turn spans are tasks with names like "Turn 1", "Turn 2", etc.
        if span_type == "task" and span_name.startswith("Turn "):
            turn_spans[span_name] = span

    # Step 3: For each turn, find LLM spans where span_parents includes turn's span_id
    hierarchy: dict[str, dict[str, Any]] = {}

    for turn_name, turn_span in turn_spans.items():
        turn_span_id = turn_span.get("span_id")

        # Extract input from turn span
        raw_input = turn_span.get("input")
        # Handle string, dict, or None input
        if raw_input is None:
            input_value = None
        elif isinstance(raw_input, str):
            input_value = raw_input
        elif isinstance(raw_input, dict):
            # Keep as dict - the test expects the dict to be preserved
            input_value = raw_input
        else:
            input_value = None

        # Find LLM spans that are children of this turn
        llm_spans: list[dict[str, Any]] = []
        for span in spans:
            attrs = span.get("span_attributes") or {}
            span_type = attrs.get("type")

            # Only include LLM type spans
            if span_type != "llm":
                continue

            # Check if this span is a child of the turn
            span_parents = span.get("span_parents") or []
            if turn_span_id and turn_span_id in span_parents:
                llm_spans.append(span)

        hierarchy[turn_name] = {
            "span_id": turn_span_id,
            "input": input_value,
            "llm_spans": llm_spans,
        }

    return hierarchy


def extract_user_intent_raw(turn_span: dict[str, Any], max_chars: int = 500) -> str:
    """Extract raw user intent from Turn span input.

    Truncates to max_chars, handles string/dict input formats.

    Args:
        turn_span: The Turn span dict from BTQL
        max_chars: Maximum characters before truncation

    Returns:
        Raw user intent string, empty string if invalid/missing
    """
    raw_input = turn_span.get("input")

    # Handle missing or None input
    if raw_input is None:
        return ""

    # Handle string input directly
    if isinstance(raw_input, str):
        text = raw_input
    elif isinstance(raw_input, dict):
        # Try common dict formats: content, text, or message
        text = raw_input.get("content") or raw_input.get("text") or raw_input.get("message") or ""
        if not text:
            # No known field found, return empty
            return ""
    else:
        return ""

    # Handle empty string
    if not text:
        return ""

    # Truncate if too long
    if len(text) > max_chars:
        return text[:max_chars] + "..."

    return text


def extract_llm_decision(llm_span: dict[str, Any], max_chars: int = 300) -> str:
    """Extract decision/reasoning from LLM span output.

    Parses output.content field, truncates to max_chars.

    Args:
        llm_span: The LLM span dict from BTQL
        max_chars: Maximum characters before truncation

    Returns:
        Decision string, empty string if invalid/missing
    """
    output = llm_span.get("output")

    # Handle missing or None output
    if output is None:
        return ""

    # Handle string output directly
    if isinstance(output, str):
        text = output.strip()
    elif isinstance(output, dict):
        # Extract content field
        content = output.get("content")
        if content is None:
            return ""
        if not isinstance(content, str):
            return ""
        text = content.strip()
    else:
        return ""

    # Handle empty string
    if not text:
        return ""

    # Truncate if too long
    if len(text) > max_chars:
        return text[:max_chars] + "..."

    return text


def extract_tools_from_llm_span(llm_span: dict[str, Any]) -> list[str]:
    """Extract tool names from LLM span output.tool_calls.

    Args:
        llm_span: The LLM span dict from BTQL

    Returns:
        Deduplicated list of tool names in order of first appearance
    """
    output = llm_span.get("output")

    # Handle missing or None output
    if output is None:
        return []

    # Output must be a dict with tool_calls
    if not isinstance(output, dict):
        return []

    tool_calls = output.get("tool_calls")
    if tool_calls is None or not isinstance(tool_calls, list):
        return []

    # Extract tool names, preserving order but deduplicating
    seen: set[str] = set()
    result: list[str] = []

    for tool_call in tool_calls:
        # Skip None or non-dict entries
        if tool_call is None or not isinstance(tool_call, dict):
            continue

        # Get function dict
        function = tool_call.get("function")
        if function is None or not isinstance(function, dict):
            continue

        # Get tool name
        name = function.get("name")
        if name is None or not isinstance(name, str):
            continue

        # Add to result if not seen
        if name not in seen:
            seen.add(name)
            result.append(name)

    return result


def extract_files_from_turn(
    turn_span_id: str,
    all_spans: list[dict[str, Any]],
) -> list[str]:
    """Extract file paths from Read/Write/Edit tool spans under a turn.

    Finds all tool spans where span_parents includes turn_span_id and
    extracts file_path from their input.

    Args:
        turn_span_id: The span_id of the Turn span
        all_spans: List of all spans in the session

    Returns:
        Deduplicated list of file paths
    """
    if not all_spans:
        return []

    seen: set[str] = set()
    files: list[str] = []

    # File-related tool names
    file_tools = {"Read", "Write", "Edit"}

    for span in all_spans:
        # Check if this span is a child of the turn
        span_parents = span.get("span_parents") or []
        if turn_span_id not in span_parents:
            continue

        # Check if it's a file-related tool
        span_name = span.get("name", "")
        if span_name not in file_tools:
            continue

        # Extract file_path from input
        input_data = span.get("input")
        if input_data is None:
            continue

        file_path = None
        if isinstance(input_data, dict):
            file_path = input_data.get("file_path")
        elif isinstance(input_data, str):
            # Try to parse as JSON
            try:
                parsed = json.loads(input_data)
                if isinstance(parsed, dict):
                    file_path = parsed.get("file_path")
            except (json.JSONDecodeError, TypeError):
                pass

        if file_path and isinstance(file_path, str) and file_path not in seen:
            seen.add(file_path)
            files.append(file_path)

    return files


def lookup_session_outcome(root_span_id: str) -> tuple[str | None, str | None]:
    """Lookup outcome from context.db handoffs table.

    Queries the handoffs table by root_span_id to get the session outcome.

    Args:
        root_span_id: The session's root span ID

    Returns:
        Tuple of (outcome, outcome_notes) - e.g., ("SUCCEEDED", None)
        Returns (None, None) if not found or on error
    """
    import sqlite3

    # Get database path from environment or use default project location
    db_path_str = os.environ.get("CONTEXT_DB_PATH")
    if db_path_str:
        db_path = Path(db_path_str)
    else:
        # Default location: .claude/cache/context.db
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        db_path = Path(project_dir) / ".claude" / "cache" / "context.db"

    # Check if database exists
    if not db_path.exists():
        return (None, None)

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        cursor.execute(
            "SELECT outcome, outcome_notes FROM handoffs WHERE root_span_id = ?",
            (root_span_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return (row[0], row[1])
        return (None, None)

    except Exception:
        # Handle any database errors gracefully
        return (None, None)


def detect_error_in_turn(
    turn_span_id: str,
    all_spans: list[dict[str, Any]],
) -> str | None:
    """Detect error from Bash spans under a turn.

    Searches Bash tool span outputs for error patterns like tracebacks,
    pytest failures, and error messages.

    Args:
        turn_span_id: The span_id of the Turn span
        all_spans: List of all spans in the session

    Returns:
        First error summary found (truncated to 500 chars), or None
    """
    if not all_spans:
        return None

    # Error patterns to detect
    error_patterns = [
        r"Traceback \(most recent call last\):",
        r"FAILED\s+\S+",  # pytest failure
        r"Error:\s*.+",
        r"error\s+TS\d+:",  # TypeScript errors
        r"exit code \d+",
        r"AssertionError:",
        r"ModuleNotFoundError:",
        r"ImportError:",
        r"TypeError:",
        r"ValueError:",
        r"RuntimeError:",
        r"KeyError:",
        r"AttributeError:",
        r"FileNotFoundError:",
    ]

    for span in all_spans:
        # Check if this span is a child of the turn
        span_parents = span.get("span_parents") or []
        if turn_span_id not in span_parents:
            continue

        # Check if it's a Bash tool
        span_name = span.get("name", "")
        if span_name != "Bash":
            continue

        # Extract output
        output = span.get("output")
        if output is None:
            continue

        # Handle dict output with stdout/stderr
        stdout = ""
        stderr = ""
        if isinstance(output, dict):
            stdout = output.get("stdout", "") or ""
            stderr = output.get("stderr", "") or ""
        elif isinstance(output, str):
            stdout = output

        combined = f"{stdout}\n{stderr}"

        # Search for error patterns
        for pattern in error_patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                # Extract context around the error
                start = max(0, match.start() - 50)
                end = min(len(combined), match.end() + 200)
                error_context = combined[start:end].strip()

                # Truncate to max 500 chars
                if len(error_context) > 500:
                    error_context = error_context[:497] + "..."

                return error_context

    return None


# =============================================================================
# Phase 10: LLM Summarization for User Intent
# =============================================================================


async def _call_llm_summarize(raw_intent: str, max_tokens: int = 50) -> str:
    """Call LLM to summarize user intent.

    Internal helper function that can be mocked in tests.

    Args:
        raw_intent: Raw user intent text to summarize
        max_tokens: Maximum tokens for summary output

    Returns:
        Summarized intent string

    Raises:
        Exception: If LLM call fails
    """
    # For now, this is a placeholder that falls back to truncation
    # In a real implementation, this would call Claude or OpenAI API
    # Example prompt: "Summarize this user request in one sentence (max {max_tokens} tokens): {raw_intent}"
    #
    # To enable real LLM summarization:
    # 1. Import anthropic or openai client
    # 2. Call the API with the summarization prompt
    # 3. Return the summarized text
    raise NotImplementedError("LLM summarization not yet implemented - will fall back to truncation")


async def summarize_user_intent(
    raw_intent: str,
    max_tokens: int = 50,
    use_llm: bool = True,
) -> str:
    """Summarize user intent using LLM (optional).

    If use_llm=False or if LLM call fails, returns truncated raw intent.

    Args:
        raw_intent: The raw user intent text
        max_tokens: Maximum tokens for output (approx 4 chars/token)
        use_llm: Whether to attempt LLM summarization

    Returns:
        Summarized or truncated intent string
    """
    # Handle empty/whitespace input
    if not raw_intent or not raw_intent.strip():
        return ""

    # Clean the intent
    cleaned = raw_intent.strip()

    # If short enough (<100 chars), return as-is
    if len(cleaned) < 100:
        return cleaned

    # Calculate max chars based on tokens (approx 4 chars/token)
    max_chars = max_tokens * 4

    # Try LLM summarization if enabled
    if use_llm:
        try:
            result = await _call_llm_summarize(cleaned, max_tokens)
            return result
        except Exception:
            # Fall through to truncation on any LLM error
            pass

    # Fallback: smart truncation
    # Try to break at word boundary
    if len(cleaned) <= max_chars:
        return cleaned

    # Find last space before max_chars
    truncated = cleaned[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]

    return truncated + "..."


# =============================================================================
# Phase 9: Main Extraction Function
# =============================================================================


def extract_llm_span_memories(
    spans: list[dict[str, Any]],
    session_id: str,
) -> list[LLMSpanMemory]:
    """Extract LLMSpanMemory objects from all spans in a session.

    Iterates through all turns and all LLM spans within each turn.
    Combines all helper functions to build complete memory objects.

    Args:
        spans: List of span dicts from BTQL query
        session_id: The root_span_id (session ID) for this session

    Returns:
        List of LLMSpanMemory objects, one per LLM span
    """
    if not spans:
        return []

    # Step 1: Build turn->LLM span hierarchy
    hierarchy = build_turn_llm_hierarchy(spans)

    if not hierarchy:
        return []

    # Step 2: Lookup session outcome once (shared across all memories)
    outcome, _outcome_notes = lookup_session_outcome(session_id)

    # Step 3: Extract memories from each turn
    memories: list[LLMSpanMemory] = []

    for turn_name, turn_data in hierarchy.items():
        # Parse turn number from name: "Turn 1" -> 1, "Turn 5" -> 5
        try:
            turn_number = int(turn_name.split()[-1])
        except (ValueError, IndexError):
            turn_number = 0

        turn_span_id = turn_data.get("span_id", "")
        llm_spans = turn_data.get("llm_spans", [])

        # Skip turns with no LLM spans
        if not llm_spans:
            continue

        # Extract per-turn info (shared by all LLM spans in this turn)
        # Create a turn span dict for extract_user_intent_raw
        turn_span = {"input": turn_data.get("input")}
        user_intent = extract_user_intent_raw(turn_span)

        # Detect errors in this turn
        error_summary = detect_error_in_turn(turn_span_id, spans)

        # Extract files touched in this turn
        files_touched = extract_files_from_turn(turn_span_id, spans)

        # Step 4: Create memory for each LLM span
        for llm_span in llm_spans:
            llm_span_id = llm_span.get("span_id", "")

            # Extract decision from LLM output
            decision = extract_llm_decision(llm_span)

            # Extract tools called from LLM span
            tools_called = extract_tools_from_llm_span(llm_span)

            # Create LLMSpanMemory with all fields
            memory = LLMSpanMemory(
                span_id=llm_span_id,
                turn_number=turn_number,
                session_id=session_id,
                user_intent=user_intent,
                decision=decision,
                tools_called=tools_called,
                files_touched=files_touched,
                outcome=outcome,
                error_summary=error_summary,
            )
            memories.append(memory)

    return memories


def extract_facts_from_spans(
    spans: list[dict[str, Any]],
    session_id: str,
) -> list[ExtractedFact]:
    """Extract facts from raw spans.

    Parses tool calls, errors, and outputs to find learnable facts.

    Args:
        spans: List of span dicts from BTQL
        session_id: Source session ID

    Returns:
        List of ExtractedFact objects
    """
    facts: list[ExtractedFact] = []
    seen_hashes: set[str] = set()

    def add_fact(fact: ExtractedFact) -> None:
        if fact.content_hash not in seen_hashes:
            seen_hashes.add(fact.content_hash)
            facts.append(fact)

    # First pass: extract goal from Turn 1 task span
    # The session root span just has "Session: claude-continuity-kit"
    # The actual user prompt is in Turn 1's input field
    for span in spans:
        attrs = span.get("span_attributes") or {}
        span_type = attrs.get("type")
        span_name = attrs.get("name", "")

        # Goal: Turn 1 task span contains the user's actual request
        if span_type == "task" and span_name == "Turn 1":
            input_data = span.get("input", "")
            if input_data and isinstance(input_data, str) and len(input_data) > 20:
                # Extract first 500 chars as goal context
                goal_content = input_data[:500]
                add_fact(
                    ExtractedFact(
                        content=f"Session goal: {goal_content}",
                        fact_type=FactType.GOAL,
                        source_session=session_id,
                        metadata={"span_name": span_name, "turn": 1},
                    )
                )
                break  # Only one goal per session

    # Second pass: extract other facts
    for span in spans:
        attrs = span.get("span_attributes") or {}
        metadata = span.get("metadata") or {}
        span_type = attrs.get("type")
        # Tool name is in metadata, not span_attributes
        tool_name = metadata.get("tool_name") or attrs.get("name", "")

        # Extract file changes from Write tool
        if span_type == "tool" and tool_name == "Write":
            input_data = span.get("input")
            file_path = None

            if isinstance(input_data, dict):
                file_path = input_data.get("file_path")
            elif isinstance(input_data, str):
                # Try to parse JSON
                try:
                    parsed = json.loads(input_data)
                    file_path = parsed.get("file_path")
                except (json.JSONDecodeError, TypeError):
                    pass

            if file_path:
                add_fact(
                    ExtractedFact(
                        content=f"Modified file: {file_path}",
                        fact_type=FactType.FILE_CHANGE,
                        source_session=session_id,
                        metadata={"file_path": file_path, "tool": "Write"},
                    )
                )

        # Extract file changes from Edit tool
        if span_type == "tool" and (tool_name == "Edit" or "Edit" in tool_name):
            input_data = span.get("input")
            file_path = None

            if isinstance(input_data, dict):
                file_path = input_data.get("file_path")
            elif isinstance(input_data, str):
                try:
                    parsed = json.loads(input_data)
                    file_path = parsed.get("file_path")
                except (json.JSONDecodeError, TypeError):
                    pass

            if file_path:
                add_fact(
                    ExtractedFact(
                        content=f"Modified file: {file_path}",
                        fact_type=FactType.FILE_CHANGE,
                        source_session=session_id,
                        metadata={"file_path": file_path, "tool": "Edit"},
                    )
                )

        # Extract errors ONLY from Bash/Terminal tool spans
        # Avoid false positives from code comments or docstrings
        is_bash_span = (
            span_type == "tool"
            and (tool_name == "Bash" or attrs.get("name", "").startswith("Terminal"))
        )

        if is_bash_span:
            output = span.get("output")
            if output and isinstance(output, dict):
                # Bash spans have structured output: {stdout, stderr, interrupted}
                stdout = output.get("stdout", "")
                stderr = output.get("stderr", "")
                combined_output = f"{stdout}\n{stderr}"

                # Only match actual runtime errors, not code comments
                error_patterns = [
                    r"Traceback \(most recent call last\):",
                    r"AssertionError:",
                    r"FAILED\s+tests/",  # pytest failure
                    r"ERROR\s+tests/",  # pytest error
                    r"ModuleNotFoundError:\s*(.+)",
                    r"ImportError:\s*(.+)",
                    r"TypeError:\s*(.+)",
                    r"ValueError:\s*(.+)",
                    r"RuntimeError:\s*(.+)",
                    r"KeyError:\s*(.+)",
                    r"AttributeError:\s*(.+)",
                    r"FileNotFoundError:\s*(.+)",
                ]
                for pattern in error_patterns:
                    if match := re.search(pattern, combined_output):
                        # Extract context around the error (up to 300 chars)
                        match_start = max(0, match.start() - 50)
                        match_end = min(len(combined_output), match.end() + 200)
                        error_context = combined_output[match_start:match_end]
                        add_fact(
                            ExtractedFact(
                                content=f"Error encountered: {error_context}",
                                fact_type=FactType.ERROR,
                                source_session=session_id,
                                metadata={
                                    "error_pattern": pattern,
                                    "tool": tool_name,
                                    "command": (span.get("input", {}) or {}).get(
                                        "command", ""
                                    )[:200],
                                },
                            )
                        )
                        break  # Only one error per span

        # Extract Claude's reasoning/decisions from LLM spans
        if span_type == "llm":
            output = span.get("output")
            if output and isinstance(output, dict):
                content = output.get("content", "")
                if content and isinstance(content, str) and len(content) > 30:
                    # Look for decision-like phrases in Claude's output
                    # Match from phrase to end of sentence (period, newline) or max 200 chars
                    decision_patterns = [
                        r"I'll\s+(?:orchestrate|implement|create|add|fix|use|spawn)\s+[^.]{10,200}",
                        r"(?:The|This)\s+approach\s+(?:is|will)\s+[^.]{10,150}",
                        r"Spawning\s+\d+\s+\w+\s+agents?\s+[^.]{5,100}",
                        r"(?:Based on|After|Given)\s+[^,]{5,50},?\s+I\s+(?:will|should|need to)\s+[^.]{10,100}",
                    ]
                    for pattern in decision_patterns:
                        if match := re.search(pattern, content, re.IGNORECASE):
                            decision_text = match.group(0)[:300]
                            add_fact(
                                ExtractedFact(
                                    content=f"Decision: {decision_text}",
                                    fact_type=FactType.DECISION,
                                    source_session=session_id,
                                    metadata={
                                        "llm_span_id": span.get("span_id", ""),
                                    },
                                )
                            )
                            break  # One decision per LLM span

    return facts


# =============================================================================
# Phase 4: Deduplication and Storage
# =============================================================================


async def store_if_novel(
    memory: Any,  # MemoryBackend protocol
    fact: ExtractedFact,
) -> tuple[str | None, bool]:
    """Store fact only if content is novel.

    Checks for existing fact by content_hash in metadata.

    Args:
        memory: Memory backend instance
        fact: Fact to store

    Returns:
        (memory_id, was_novel) - memory_id is None if duplicate
    """
    # Search for existing fact with same hash
    # Use exact hash match via metadata search
    try:
        results = await memory.search(f"hash:{fact.content_hash}", limit=5)
    except Exception:
        results = []

    # Also check metadata field directly if search doesn't support hash prefix
    if not results:
        # Search by content similarity to double-check
        try:
            results = await memory.search(fact.content[:50], limit=5)
        except Exception:
            results = []

        for r in results:
            if r.get("metadata", {}).get("content_hash") == fact.content_hash:
                return None, False

    # Check if any result has matching hash
    if results and any(
        r.get("metadata", {}).get("content_hash") == fact.content_hash for r in results
    ):
        return None, False

    # Store with hash in metadata
    metadata = {
        **fact.metadata,
        "content_hash": fact.content_hash,
        "fact_type": fact.fact_type.value,
        "source_session": fact.source_session,
    }

    memory_id = await memory.store(
        content=fact.content,
        metadata=metadata,
        embedding=fact.embedding,
    )
    return memory_id, True


# =============================================================================
# Phase 11: Storage Function for LLMSpanMemory
# =============================================================================


async def store_llm_span_memory(
    memory: Any,  # MemoryBackend protocol
    span_memory: LLMSpanMemory,
) -> tuple[str | None, bool]:
    """Store LLMSpanMemory if novel.

    Similar to store_if_novel but for the new LLMSpanMemory model.
    Checks for duplicates by content_hash.

    Args:
        memory: Memory backend instance
        span_memory: LLMSpanMemory to store

    Returns:
        (memory_id, was_novel) - memory_id is None if duplicate or error
    """
    # Check for duplicate by content_hash
    try:
        results = await memory.search(f"hash:{span_memory.content_hash}", limit=5)
    except Exception:
        results = []

    def _has_hash_match(rows: list[dict[str, Any]]) -> bool:
        return any(
            (r.get("metadata", {}).get("content_hash") or r.get("content_hash"))
            == span_memory.content_hash
            for r in rows
            if isinstance(r, dict)
        )

    if results and _has_hash_match(results):
        return None, False

    # Also search by content if hash search not supported or yielded no matches
    if not results or not _has_hash_match(results):
        try:
            results = await memory.search(span_memory.embedding_text[:50], limit=5)
        except Exception:
            results = []

        if results and _has_hash_match(results):
            return None, False

    # Build metadata with all structured fields
    metadata = {
        "span_id": span_memory.span_id,
        "session_id": span_memory.session_id,
        "turn_number": span_memory.turn_number,
        "content_hash": span_memory.content_hash,
        "tools_called": span_memory.tools_called,
        "files_touched": span_memory.files_touched,
        "outcome": span_memory.outcome,
        "error_summary": span_memory.error_summary,
        "memory_type": "llm_span_memory",  # Distinguish from ExtractedFact
    }

    try:
        memory_id = await memory.store(
            content=span_memory.embedding_text,
            metadata=metadata,
            embedding=span_memory.embedding,
        )
        return memory_id, True
    except Exception:
        # Handle storage errors gracefully
        return None, False


async def embed_facts(
    facts: list[ExtractedFact],
    embedding_service: Any,  # EmbeddingService
) -> list[ExtractedFact]:
    """Generate embeddings for all facts.

    Uses batch embedding for efficiency.

    Args:
        facts: List of facts to embed
        embedding_service: Embedding provider

    Returns:
        Same facts with embedding field populated
    """
    if not facts:
        return facts

    # Prepare content with type prefixes for better clustering
    type_prefixes = {
        FactType.GOAL: "Goal: ",
        FactType.DECISION: "Decision: ",
        FactType.FILE_CHANGE: "Code change: ",
        FactType.OUTCOME: "Outcome: ",
        FactType.LEARNING: "Learning: ",
        FactType.ERROR: "Error: ",
        FactType.AGENT_OUTPUT: "Agent output: ",
    }

    texts = [type_prefixes.get(f.fact_type, "") + f.content for f in facts]

    embeddings = await embedding_service.embed_batch(texts)

    for fact, embedding in zip(facts, embeddings):
        fact.embedding = embedding

    return facts


async def backfill_session(
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
    1.5. (Optional) SpanProcessor for two-pass extraction on large sessions
    2. Parse into structured facts
    2.5. (Optional) LLMSpanMemory extraction for per-span granularity
    3. Dedupe against existing memory
    4. Enrich with type metadata (done in parse)
    5. Generate embeddings
    6. Store to memory service

    Args:
        session_id: Braintrust root_span_id
        project_id: Braintrust project ID
        api_key: Braintrust API key
        memory_backend: "sqlite" or "postgres"
        db_path: Path for SQLite DB (optional)
        embedding_provider: "openai", "voyage", "mock"
        dry_run: If True, don't actually store
        use_two_pass: If True, always use SpanProcessor for two-pass extraction
        two_pass_threshold: Auto-enable two-pass when span count exceeds this (default: 50)
        extract_span_memories: If True, extract per-LLM-span memories (Phase 12)

    Returns:
        BackfillResult with counts and any errors
    """
    start_time = time.time()

    result = BackfillResult(
        session_id=session_id,
        facts_extracted=0,
        facts_stored=0,
        facts_skipped_duplicate=0,
    )

    try:
        # Stage 1: Fetch
        spans = await fetch_session_spans(session_id, project_id, api_key)
        context = get_hierarchical_context(session_id)

        # Stage 1.5: SpanProcessor (two-pass extraction for large sessions)
        # Auto-enable two-pass for large sessions (> threshold spans)
        should_use_two_pass = use_two_pass or len(spans) > two_pass_threshold

        if should_use_two_pass and spans:
            try:
                processor = SpanProcessor(
                    session_id=session_id,
                    embedding_provider=embedding_provider,
                )
                sp_result = await processor.process(spans)
                result.two_pass_used = True
                result.summaries_from_two_pass = sp_result.summaries_persisted
                result.decisions_from_two_pass = sp_result.decisions_persisted
                result.errors.extend(sp_result.errors)
            except Exception as e:
                result.errors.append(f"SpanProcessor error: {e}")

        # Stage 2: Parse
        facts: list[ExtractedFact] = []
        facts.extend(extract_facts_from_context(context, session_id))
        facts.extend(extract_facts_from_spans(spans, session_id))
        result.facts_extracted = len(facts)

        # Stage 2.5: LLMSpanMemory extraction (Phase 12)
        span_memories: list[LLMSpanMemory] = []
        if extract_span_memories and spans:
            span_memories = extract_llm_span_memories(spans, session_id)
            result.span_memories_extracted = len(span_memories)

        # Early return if nothing to store
        if not facts and not span_memories:
            result.duration_seconds = time.time() - start_time
            return result

        # Stage 3-4: Dedupe (handled by store_if_novel)
        # Dedupe within session already done in extract functions

        # Stage 5: Embed
        embedder = EmbeddingService(provider=embedding_provider)
        if facts:
            facts = await embed_facts(facts, embedder)

        # Stage 5.5: Embed span memories
        if span_memories:
            span_texts = [sm.embedding_text for sm in span_memories]
            span_embeddings = await embedder.embed_batch(span_texts)
            for sm, emb in zip(span_memories, span_embeddings):
                sm.embedding = emb

        # Stage 6: Store
        if not dry_run:
            memory = await create_memory_service(
                backend=memory_backend,
                session_id="backfill",  # Dedicated session for backfill data
                **({"db_path": db_path} if db_path else {}),
            )

            # Store facts
            for fact in facts:
                try:
                    _, was_novel = await store_if_novel(memory, fact)
                    if was_novel:
                        result.facts_stored += 1
                    else:
                        result.facts_skipped_duplicate += 1
                except Exception as e:
                    result.errors.append(f"Store error for {fact.content[:50]}: {e}")

            # Store span memories (Phase 12)
            for sm in span_memories:
                try:
                    _, was_novel = await store_llm_span_memory(memory, sm)
                    if was_novel:
                        result.span_memories_stored += 1
                    else:
                        result.span_memories_skipped += 1
                except Exception as e:
                    result.errors.append(f"Store error for span {sm.span_id[:20]}: {e}")

            await memory.close()

    except Exception as e:
        result.errors.append(f"Pipeline error: {e}")

    result.duration_seconds = time.time() - start_time
    return result


# =============================================================================
# Phase 5: Batch Processing and CLI
# =============================================================================


@dataclass
class BatchConfig:
    """Configuration for batch processing."""

    batch_size: int = 50
    concurrency: int = 5
    checkpoint_interval: int = 10
    retry_count: int = 3
    retry_delay: float = 1.0


async def save_checkpoint(
    checkpoint_path: Path,
    last_session: str,
    last_timestamp: str,
    processed_count: int,
) -> None:
    """Save checkpoint for resume capability.

    Args:
        checkpoint_path: Path to checkpoint file
        last_session: Last processed session ID
        last_timestamp: Last processed timestamp
        processed_count: Total sessions processed so far
    """
    checkpoint = {
        "last_session": last_session,
        "last_timestamp": last_timestamp,
        "processed_count": processed_count,
        "saved_at": datetime.now().isoformat(),
    }
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2))


async def load_checkpoint(checkpoint_path: Path) -> dict[str, Any] | None:
    """Load checkpoint if exists.

    Args:
        checkpoint_path: Path to checkpoint file

    Returns:
        Checkpoint dict or None if not found
    """
    if checkpoint_path.exists():
        return json.loads(checkpoint_path.read_text())
    return None


async def get_resume_point(checkpoint_path: Path) -> str | None:
    """Get timestamp to resume from.

    Args:
        checkpoint_path: Path to checkpoint file

    Returns:
        Timestamp string or None if no checkpoint
    """
    checkpoint = await load_checkpoint(checkpoint_path)
    if checkpoint:
        return checkpoint.get("last_timestamp")
    return None


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
) -> list[BackfillResult]:
    """Backfill all sessions in date range.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        project_id: Braintrust project ID
        api_key: Braintrust API key
        config: Batch processing configuration
        memory_backend: "sqlite" or "postgres"
        db_path: Path for SQLite DB
        embedding_provider: Embedding provider name
        checkpoint_path: Path to save checkpoints
        resume: If True, resume from checkpoint

    Returns:
        List of BackfillResult for each session
    """
    config = config or BatchConfig()

    if checkpoint_path is None:
        checkpoint_path = Path(".claude/cache/backfill_checkpoint.json")

    # Check for resume
    resume_after = None
    if resume:
        resume_after = await get_resume_point(checkpoint_path)
        if resume_after:
            print(f"Resuming from {resume_after}")
            # Adjust start_date to resume point
            start_date = resume_after.split("T")[0]

    # List all sessions
    sessions = await list_sessions_in_range(project_id, start_date, end_date, api_key)
    print(f"Found {len(sessions)} sessions to process")

    # Filter if resuming
    if resume_after:
        sessions = [s for s in sessions if s.get("start_time", "") > resume_after]
        print(f"After resume filter: {len(sessions)} sessions")

    results: list[BackfillResult] = []
    semaphore = asyncio.Semaphore(config.concurrency)

    async def process_with_semaphore(session: dict) -> BackfillResult:
        async with semaphore:
            sess_id = session.get("session_id")
            for attempt in range(config.retry_count):
                try:
                    return await backfill_session(
                        session_id=sess_id,
                        project_id=project_id,
                        api_key=api_key,
                        memory_backend=memory_backend,
                        db_path=db_path,
                        embedding_provider=embedding_provider,
                    )
                except Exception as e:
                    if attempt == config.retry_count - 1:
                        return BackfillResult(
                            session_id=sess_id,
                            facts_extracted=0,
                            facts_stored=0,
                            facts_skipped_duplicate=0,
                            errors=[f"Failed after {config.retry_count} attempts: {e}"],
                        )
                    await asyncio.sleep(config.retry_delay * (2**attempt))
            # Should not reach here, but return error result just in case
            return BackfillResult(
                session_id=sess_id,
                facts_extracted=0,
                facts_stored=0,
                facts_skipped_duplicate=0,
                errors=["Unknown error"],
            )

    # Process in batches
    for i in range(0, len(sessions), config.batch_size):
        batch = sessions[i : i + config.batch_size]
        tasks = [process_with_semaphore(s) for s in batch]
        batch_results = await asyncio.gather(*tasks)
        results.extend(batch_results)

        # Checkpoint after batch
        if batch_results:
            last = batch[-1]
            await save_checkpoint(
                checkpoint_path,
                last_session=last.get("session_id", ""),
                last_timestamp=last.get("start_time", ""),
                processed_count=len(results),
            )
            print(f"Processed {len(results)}/{len(sessions)} sessions")

    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Memory Backfill Service - Populate memory from Braintrust traces",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single session
  %(prog)s --session-id abc123

  # Date range
  %(prog)s --start-date 2025-12-20 --end-date 2025-12-27

  # Resume interrupted backfill
  %(prog)s --resume
        """,
    )

    # Mode selection
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--session-id",
        help="Backfill a single session by ID",
    )
    mode.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint",
    )

    # Date range (for batch mode)
    parser.add_argument(
        "--start-date",
        help="Start date for batch backfill (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        help="End date for batch backfill (YYYY-MM-DD)",
    )

    # Configuration
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Sessions per batch (default: 50)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Parallel workers (default: 5)",
    )
    parser.add_argument(
        "--project",
        default="claude-continuity-kit",
        help="Braintrust project name (default: claude-continuity-kit)",
    )
    parser.add_argument(
        "--backend",
        choices=["sqlite", "postgres"],
        default="sqlite",
        help="Memory backend (default: sqlite)",
    )
    parser.add_argument(
        "--embedding-provider",
        choices=["openai", "voyage", "mock"],
        default="openai",
        help="Embedding provider (default: openai)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract but don't store",
    )
    parser.add_argument(
        "--use-two-pass",
        action="store_true",
        help="Enable SpanProcessor two-pass extraction (auto-enabled for >50 spans)",
    )
    parser.add_argument(
        "--two-pass-threshold",
        type=int,
        default=50,
        help="Auto-enable two-pass when span count exceeds this (default: 50)",
    )
    parser.add_argument(
        "--extract-span-memories",
        action="store_true",
        help="Extract per-LLM-span memories (new model, complements facts)",
    )

    # Batch mode shortcuts (Phase 14)
    mode.add_argument(
        "--all",
        action="store_true",
        help="Backfill all sessions in project",
    )
    parser.add_argument(
        "--since",
        help="Backfill sessions since date (YYYY-MM-DD)",
    )

    return parser.parse_args(argv)


def load_api_key() -> str:
    """Load API key from environment or .env file.

    Returns:
        Braintrust API key

    Raises:
        SystemExit: If key not found
    """
    # Try loading from .env files
    for path in [Path.home() / ".claude", Path.cwd(), *Path.cwd().parents]:
        env_file = path / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("BRAINTRUST_API_KEY="):
                        key = line.strip().split("=", 1)[1].strip("\"'")
                        os.environ["BRAINTRUST_API_KEY"] = key
                        break

    api_key = os.environ.get("BRAINTRUST_API_KEY")
    if not api_key:
        print("Error: BRAINTRUST_API_KEY not found.", file=sys.stderr)
        print("Set it in ~/.claude/.env or project .env", file=sys.stderr)
        sys.exit(1)
    return api_key


def get_project_id(project_name: str, api_key: str) -> str:
    """Get project ID from name.

    Args:
        project_name: Braintrust project name
        api_key: Braintrust API key

    Returns:
        Project ID

    Raises:
        SystemExit: If project not found
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(
        "https://api.braintrust.dev/v1/project",
        headers=headers,
        params={"project_name": project_name},
        timeout=30,
    )
    if resp.status_code == 200:
        projects = resp.json().get("objects", [])
        if projects:
            return projects[0]["id"]

    # Try listing all projects and matching by name
    resp = requests.get("https://api.braintrust.dev/v1/project", headers=headers, timeout=30)
    if resp.status_code == 200:
        projects = resp.json().get("objects", [])
        for p in projects:
            if p.get("name", "").lower() == project_name.lower():
                return p["id"]

    print(f"Error: Project '{project_name}' not found", file=sys.stderr)
    sys.exit(1)


async def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Load API key
    api_key = load_api_key()

    # Get project ID
    project_id = get_project_id(args.project, api_key)

    if args.session_id:
        # Single session mode
        print(f"Backfilling session: {args.session_id}")
        result = await backfill_session(
            session_id=args.session_id,
            project_id=project_id,
            api_key=api_key,
            memory_backend=args.backend,
            embedding_provider=args.embedding_provider,
            dry_run=args.dry_run,
            use_two_pass=args.use_two_pass,
            two_pass_threshold=args.two_pass_threshold,
            extract_span_memories=args.extract_span_memories,
        )
        print("\nResult:")
        print(f"  Facts extracted: {result.facts_extracted}")
        print(f"  Facts stored: {result.facts_stored}")
        print(f"  Duplicates skipped: {result.facts_skipped_duplicate}")
        print(f"  Duration: {result.duration_seconds:.2f}s")
        if result.two_pass_used:
            print(f"  Two-pass summaries: {result.summaries_from_two_pass}")
            print(f"  Two-pass decisions: {result.decisions_from_two_pass}")
        if args.extract_span_memories:
            print(f"  Span memories extracted: {result.span_memories_extracted}")
            print(f"  Span memories stored: {result.span_memories_stored}")
            print(f"  Span memories skipped: {result.span_memories_skipped}")
        if result.errors:
            print(f"  Errors: {result.errors}")

    elif args.resume or (args.start_date and args.end_date):
        # Batch mode
        if args.resume:
            # Get dates from checkpoint or use last 7 days
            checkpoint = await load_checkpoint(
                Path(".claude/cache/backfill_checkpoint.json")
            )
            if checkpoint:
                start_date = checkpoint.get("last_timestamp", "")[:10]
            else:
                start_date = (datetime.now(UTC) - timedelta(days=7)).strftime(
                    "%Y-%m-%d"
                )
            end_date = datetime.now(UTC).strftime("%Y-%m-%d")
        else:
            start_date = args.start_date
            end_date = args.end_date

        print(f"Backfilling sessions from {start_date} to {end_date}")

        config = BatchConfig(
            batch_size=args.batch_size,
            concurrency=args.concurrency,
        )

        results = await backfill_range(
            start_date=start_date,
            end_date=end_date,
            project_id=project_id,
            api_key=api_key,
            config=config,
            memory_backend=args.backend,
            embedding_provider=args.embedding_provider,
            resume=args.resume,
        )

        # Summary
        total_extracted = sum(r.facts_extracted for r in results)
        total_stored = sum(r.facts_stored for r in results)
        total_skipped = sum(r.facts_skipped_duplicate for r in results)
        total_errors = sum(len(r.errors) for r in results)

        print("\n=== Backfill Complete ===")
        print(f"Sessions processed: {len(results)}")
        print(f"Facts extracted: {total_extracted}")
        print(f"Facts stored: {total_stored}")
        print(f"Duplicates skipped: {total_skipped}")
        print(f"Errors: {total_errors}")

    else:
        print("Error: Specify --session-id, --resume, or date range", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Incremental Memory Extraction from JSONL Transcripts.

Extracts thinking blocks with perception signals from Claude session transcripts.
Supports incremental extraction (only new lines since last run) and deduplication.

Used by:
- pre-compact-extract.ts (PreCompact hook) - extract before context compression
- session-end-extract.ts (SessionEnd hook) - final sweep with dedup

Usage:
    # Extract from line 0 (full transcript)
    uv run python scripts/core/incremental_extract.py \
        --transcript /path/to/session.jsonl \
        --session-id abc123 \
        --project-dir /path/to/project

    # Extract incrementally (from line 100)
    uv run python scripts/core/incremental_extract.py \
        --transcript /path/to/session.jsonl \
        --session-id abc123 \
        --start-line 100 \
        --state-file /path/to/extraction-state.json

Output (JSON):
    {
        "learnings_stored": 3,
        "learnings_skipped": 1,
        "new_last_line": 250,
        "hashes": ["abc123", "def456", "ghi789"]
    }
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from dotenv import load_dotenv

# Load environment
global_env = Path.home() / ".claude" / ".env"
if global_env.exists():
    load_dotenv(global_env)
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Perception signal patterns (from lazy_memory.py)
PERCEPTION_SIGNALS = [
    # Discoveries
    r"(?i)I\s+(?:now\s+)?(?:realize|understand|see)\s+(?:that|why|how)",
    r"(?i)(?:Ah|Oh),?\s+(?:I\s+)?(?:see|got\s+it|understand)",
    r"(?i)(?:This|That)\s+(?:explains|clarifies|makes\s+sense)",
    # Pattern recognition
    r"(?i)(?:There(?:'s|\s+is)\s+a\s+pattern|I\s+notice(?:d)?)",
    r"(?i)(?:This|It)\s+(?:looks\s+like|appears\s+to\s+be|seems)",
    r"(?i)(?:The|This)\s+(?:common\s+)?(?:pattern|structure|approach)",
    # Learning moments
    r"(?i)(?:I\s+)?learn(?:ed|ing)\s+(?:that|from)",
    r"(?i)(?:Key|Important)\s+(?:insight|takeaway|learning)",
    r"(?i)(?:This|The)\s+lesson\s+(?:here\s+)?is",
    # Problem solving
    r"(?i)(?:The|Root)\s+(?:issue|problem|cause)\s+(?:is|was)",
    r"(?i)(?:This|It)\s+(?:works?|worked)\s+because",
    r"(?i)(?:The|A)\s+(?:fix|solution|answer)\s+(?:is|was)",
    # Failures/mistakes
    r"(?i)(?:I|We)\s+(?:made\s+a\s+)?mistake",
    r"(?i)(?:This|That)\s+(?:didn't|doesn't)\s+work",
    r"(?i)(?:Wrong|Bad)\s+(?:approach|assumption)",
    # Corrections
    r"(?i)(?:Actually|Wait),?\s+(?:I\s+)?(?:need\s+to|should)",
    r"(?i)(?:Let\s+me\s+)?(?:reconsider|rethink|revisit)",
    r"(?i)(?:I\s+was\s+)?(?:wrong|mistaken)\s+(?:about|when)",
]

COMPILED_PATTERNS = [re.compile(p) for p in PERCEPTION_SIGNALS]

# Error patterns for tool output extraction
ERROR_PATTERNS = [
    r"(?i)\berror\b",
    r"(?i)\bfailed\b",
    r"(?i)\bexception\b",
    r"(?i)\bfailure\b",
    r"(?i)\bcrashed?\b",
    r"(?i)\btimeout\b",
    r"(?i)Traceback\s+\(most recent",  # Python stack trace
    r"at\s+\S+\s+\(\S+:\d+:\d+\)",      # JS stack trace
    r"(?i)\bpanic:",                    # Go panic
    r"(?i)\bRuntimeError\b",
    r"(?i)\bTypeError\b",
    r"(?i)\bSyntaxError\b",
    r"(?i)\bImportError\b",
    r"(?i)\bModuleNotFoundError\b",
    r"(?i)\bConnectionRefused\b",
    r"(?i)\bENOENT\b",
    r"(?i)\bEPERM\b",
    r"(?i)\bEACCES\b",
]

COMPILED_ERROR_PATTERNS = [re.compile(p) for p in ERROR_PATTERNS]


def has_error_pattern(text: str) -> bool:
    """Check if text contains any error patterns."""
    return any(p.search(text) for p in COMPILED_ERROR_PATTERNS)


class ExtractionState(TypedDict, total=False):
    session_id: str
    last_extracted_line: int
    recent_hashes: list[str]
    last_extraction_time: str


class ExtractionResult(TypedDict):
    learnings_stored: int
    learnings_skipped: int
    learnings_deduped: int
    new_last_line: int
    hashes: list[str]
    errors: list[str]


def content_hash(content: str) -> str:
    """Generate hash of normalized content for deduplication."""
    normalized = content.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def has_perception_signal(text: str) -> bool:
    """Check if text contains any perception signal patterns."""
    return any(p.search(text) for p in COMPILED_PATTERNS)


def extract_thinking_blocks(line_data: dict) -> list[str]:
    """Extract thinking blocks from a JSONL line.

    Thinking blocks appear in assistant messages with content type 'thinking'.
    """
    thinking_blocks = []

    # Check for assistant message with content array
    if line_data.get("type") == "assistant":
        content = line_data.get("message", {}).get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "thinking":
                    thinking_text = block.get("thinking", "")
                    if thinking_text and has_perception_signal(thinking_text):
                        thinking_blocks.append(thinking_text)

    return thinking_blocks


def extract_tool_errors(line_data: dict) -> list[dict]:
    """Extract errors from tool outputs in a JSONL line.

    Tool outputs appear in assistant messages with tool_use content blocks,
    followed by tool_result blocks in subsequent lines.

    Returns list of dicts with 'tool_name', 'error_context', and 'input_summary'.
    """
    errors = []

    # Check for tool_result in assistant message
    if line_data.get("type") == "assistant":
        content = line_data.get("message", {}).get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    result_content = block.get("content", "")
                    if isinstance(result_content, str) and has_error_pattern(result_content):
                        # Extract error context (first 500 chars around error)
                        error_context = _extract_error_context(result_content)
                        if error_context:
                            errors.append({
                                "tool_name": block.get("tool_use_id", "unknown"),
                                "error_context": error_context,
                                "input_summary": "",  # We don't have input here
                            })

    # Also check for tool errors in tool_use responses
    if line_data.get("type") == "tool_result":
        content = line_data.get("content", "")
        tool_name = line_data.get("tool_use_id", "unknown")
        if isinstance(content, str) and has_error_pattern(content):
            error_context = _extract_error_context(content)
            if error_context:
                errors.append({
                    "tool_name": tool_name,
                    "error_context": error_context,
                    "input_summary": "",
                })

    return errors


def _extract_error_context(text: str, max_len: int = 500) -> str:
    """Extract the most relevant error portion from text."""
    lines = text.split("\n")

    # Look for lines with error patterns
    for i, line in enumerate(lines):
        if any(p.search(line) for p in COMPILED_ERROR_PATTERNS):
            # Include context: 2 lines before and 3 lines after
            start = max(0, i - 2)
            end = min(len(lines), i + 4)
            context = "\n".join(lines[start:end])
            return context[:max_len]

    # If no specific error found, return beginning
    return text[:max_len] if text else ""


def load_state(state_file: str | None) -> ExtractionState:
    """Load extraction state from file."""
    if not state_file or not os.path.exists(state_file):
        return ExtractionState(
            session_id="",
            last_extracted_line=0,
            recent_hashes=[],
            last_extraction_time=""
        )

    try:
        with open(state_file, "r") as f:
            data = json.load(f)
            return ExtractionState(
                session_id=data.get("session_id", ""),
                last_extracted_line=data.get("last_extracted_line", 0),
                recent_hashes=data.get("recent_hashes", []),
                last_extraction_time=data.get("last_extraction_time", "")
            )
    except (json.JSONDecodeError, IOError):
        return ExtractionState(
            session_id="",
            last_extracted_line=0,
            recent_hashes=[],
            last_extraction_time=""
        )


def save_state(state_file: str, state: ExtractionState) -> None:
    """Save extraction state to file."""
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


async def store_thinking_learning(
    content: str,
    session_id: str,
    project_dir: str | None,
) -> dict:
    """Store a thinking block as a learning."""
    try:
        from store_learning import store_learning_v2
    except ImportError:
        # Try relative import
        sys.path.insert(0, os.path.dirname(__file__))
        from store_learning import store_learning_v2

    # Determine learning type based on content
    learning_type = "CODEBASE_PATTERN"  # Default
    content_lower = content.lower()

    if any(kw in content_lower for kw in ["mistake", "wrong", "didn't work", "failed"]):
        learning_type = "FAILED_APPROACH"
    elif any(kw in content_lower for kw in ["fix", "solution", "works because"]):
        learning_type = "WORKING_SOLUTION"
    elif any(kw in content_lower for kw in ["decide", "chose", "choice"]):
        learning_type = "ARCHITECTURAL_DECISION"
    elif any(kw in content_lower for kw in ["error", "exception", "bug"]):
        learning_type = "ERROR_FIX"

    # Extract tags from content (simple keyword extraction)
    tags = ["auto_extracted", "thinking_block"]
    keywords = ["hook", "test", "build", "api", "database", "ui", "config"]
    for kw in keywords:
        if kw in content_lower:
            tags.append(kw)

    result = await store_learning_v2(
        session_id=session_id,
        content=content[:2000],  # Limit size
        learning_type=learning_type,
        context="extracted from thinking block",
        tags=tags,
        confidence="medium",
        project_dir=project_dir,
    )

    return result


async def store_tool_error_learning(
    error_info: dict,
    session_id: str,
    project_dir: str | None,
) -> dict:
    """Store a tool error as a FAILED_APPROACH learning."""
    try:
        from store_learning import store_learning_v2
    except ImportError:
        sys.path.insert(0, os.path.dirname(__file__))
        from store_learning import store_learning_v2

    tool_name = error_info.get("tool_name", "unknown")
    error_context = error_info.get("error_context", "")

    content = f"Tool '{tool_name}' failed with error: {error_context}"

    tags = [
        "auto_extracted",
        "tool_error",
        f"tool:{tool_name}",
        "scope:global",
    ]

    result = await store_learning_v2(
        session_id=session_id,
        content=content[:2000],
        learning_type="FAILED_APPROACH",
        context="extracted from tool error output",
        tags=tags,
        confidence="medium",
        project_dir=project_dir,
    )

    return result


async def extract_incremental(
    transcript_path: str,
    session_id: str,
    start_line: int = 0,
    state_file: str | None = None,
    project_dir: str | None = None,
    max_learnings: int = 10,
) -> ExtractionResult:
    """Extract learnings from JSONL transcript incrementally.

    Args:
        transcript_path: Path to session JSONL file
        session_id: Session identifier
        start_line: Line to start extraction from (0-indexed)
        state_file: Path to state file for tracking progress
        project_dir: Project directory for scoping
        max_learnings: Maximum learnings to extract per run

    Returns:
        ExtractionResult with counts and new state
    """
    result = ExtractionResult(
        learnings_stored=0,
        learnings_skipped=0,
        learnings_deduped=0,
        new_last_line=start_line,
        hashes=[],
        errors=[]
    )

    if not os.path.exists(transcript_path):
        result["errors"].append(f"Transcript not found: {transcript_path}")
        return result

    # Load existing state for dedup hashes
    state = load_state(state_file)
    existing_hashes = set(state.get("recent_hashes", []))

    # Read and process transcript
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except IOError as e:
        result["errors"].append(f"Failed to read transcript: {e}")
        return result

    # Process lines from start_line
    new_hashes: list[str] = []
    learnings_to_store: list[str] = []
    tool_errors_to_store: list[dict] = []

    for line_num, line in enumerate(lines[start_line:], start=start_line):
        if len(learnings_to_store) + len(tool_errors_to_store) >= max_learnings:
            break

        result["new_last_line"] = line_num + 1

        if not line.strip():
            continue

        try:
            line_data = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Extract thinking blocks (existing logic)
        thinking_blocks = extract_thinking_blocks(line_data)

        for thinking in thinking_blocks:
            h = content_hash(thinking)

            # Skip if already processed
            if h in existing_hashes or h in new_hashes:
                result["learnings_deduped"] += 1
                continue

            new_hashes.append(h)
            learnings_to_store.append(thinking)

        # Extract tool errors (new logic)
        tool_errors = extract_tool_errors(line_data)

        for error_info in tool_errors:
            h = content_hash(error_info.get("error_context", ""))

            # Skip if already processed
            if h in existing_hashes or h in new_hashes:
                result["learnings_deduped"] += 1
                continue

            new_hashes.append(h)
            tool_errors_to_store.append(error_info)

    # Store thinking learnings
    for thinking in learnings_to_store:
        try:
            store_result = await store_thinking_learning(
                content=thinking,
                session_id=session_id,
                project_dir=project_dir,
            )

            if store_result.get("success"):
                if store_result.get("skipped"):
                    result["learnings_skipped"] += 1
                else:
                    result["learnings_stored"] += 1
            else:
                result["errors"].append(store_result.get("error", "Unknown error"))
        except Exception as e:
            result["errors"].append(str(e))

    # Store tool error learnings
    for error_info in tool_errors_to_store:
        try:
            store_result = await store_tool_error_learning(
                error_info=error_info,
                session_id=session_id,
                project_dir=project_dir,
            )

            if store_result.get("success"):
                if store_result.get("skipped"):
                    result["learnings_skipped"] += 1
                else:
                    result["learnings_stored"] += 1
            else:
                result["errors"].append(store_result.get("error", "Unknown error"))
        except Exception as e:
            result["errors"].append(str(e))

    result["hashes"] = new_hashes

    # Update and save state if state_file provided
    if state_file:
        # Keep last 100 hashes to prevent unbounded growth
        all_hashes = list(existing_hashes) + new_hashes
        recent_hashes = all_hashes[-100:] if len(all_hashes) > 100 else all_hashes

        new_state = ExtractionState(
            session_id=session_id,
            last_extracted_line=result["new_last_line"],
            recent_hashes=recent_hashes,
            last_extraction_time=datetime.now(timezone.utc).isoformat()
        )
        save_state(state_file, new_state)

    return result


async def main():
    parser = argparse.ArgumentParser(description="Incremental memory extraction from JSONL")
    parser.add_argument("--transcript", required=True, help="Path to session JSONL file")
    parser.add_argument("--session-id", required=True, help="Session identifier")
    parser.add_argument("--start-line", type=int, default=0, help="Line to start from (0-indexed)")
    parser.add_argument("--state-file", help="Path to state file for tracking")
    parser.add_argument("--project-dir", help="Project directory")
    parser.add_argument("--max-learnings", type=int, default=20, help="Max learnings per run (keep <=50 to avoid memory issues)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    result = await extract_incremental(
        transcript_path=args.transcript,
        session_id=args.session_id,
        start_line=args.start_line,
        state_file=args.state_file,
        project_dir=args.project_dir,
        max_learnings=args.max_learnings,
    )

    if args.json:
        print(json.dumps(result))
    else:
        print(f"Extraction complete:")
        print(f"  Stored: {result['learnings_stored']}")
        print(f"  Skipped (semantic dedup): {result['learnings_skipped']}")
        print(f"  Skipped (hash dedup): {result['learnings_deduped']}")
        print(f"  New last line: {result['new_last_line']}")
        if result["errors"]:
            print(f"  Errors: {len(result['errors'])}")
            for err in result["errors"][:3]:
                print(f"    - {err}")


if __name__ == "__main__":
    asyncio.run(main())

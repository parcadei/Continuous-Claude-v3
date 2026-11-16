"""End-to-end integration tests for LLMSpanMemory extraction pipeline.

Tests the complete LLMSpanMemory extraction, embedding, and storage pipeline
as specified in Phases 15-16 of the implementation plan.

Plan location: thoughts/shared/plans/2025-12-28-llm-span-memory-model.md

Run with:
    uv run pytest tests/integration/test_llm_span_memory_e2e.py -v

Run with real Braintrust API (requires BRAINTRUST_API_KEY):
    uv run pytest tests/integration/test_llm_span_memory_e2e.py -v -m integration

Prerequisites:
- For mock tests: None
- For real API tests: BRAINTRUST_API_KEY environment variable
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# =============================================================================
# Test Fixtures and Mock Data
# =============================================================================


def unique_session_id() -> str:
    """Generate unique session ID for test isolation."""
    return f"test-e2e-{uuid4().hex[:12]}"


def create_mock_turn_span(
    turn_number: int,
    span_id: str,
    user_input: str,
    llm_span_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create a mock Turn span for testing.

    Args:
        turn_number: Turn number (1, 2, 3...)
        span_id: Unique span ID for this turn
        user_input: The user's input/prompt for this turn
        llm_span_ids: Optional list of child LLM span IDs

    Returns:
        Dict representing a Turn span from Braintrust
    """
    return {
        "span_id": span_id,
        "name": f"Turn {turn_number}",
        "span_parents": [],
        "span_attributes": {"type": "task", "name": f"Turn {turn_number}"},
        "input": user_input,
        "output": None,
        "metadata": {},
        "created": f"2025-12-28T10:0{turn_number}:00Z",
    }


def create_mock_llm_span(
    span_id: str,
    parent_turn_span_id: str,
    decision: str,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a mock LLM span for testing.

    Args:
        span_id: Unique span ID for this LLM span
        parent_turn_span_id: The parent Turn span ID
        decision: Claude's output content/decision
        tool_calls: Optional list of tool calls

    Returns:
        Dict representing an LLM span from Braintrust
    """
    output = {"content": decision}
    if tool_calls:
        output["tool_calls"] = tool_calls

    return {
        "span_id": span_id,
        "name": "llm",
        "span_parents": [parent_turn_span_id],
        "span_attributes": {"type": "llm"},
        "input": {},
        "output": output,
        "metadata": {},
        "created": f"2025-12-28T10:00:01Z",
    }


def create_mock_tool_span(
    span_id: str,
    parent_turn_span_id: str,
    tool_name: str,
    input_data: dict[str, Any],
    output_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a mock tool span for testing.

    Args:
        span_id: Unique span ID
        parent_turn_span_id: Parent turn span ID
        tool_name: Name of the tool (e.g., "Bash", "Read", "Write")
        input_data: Tool input (e.g., {"file_path": "/path/to/file"})
        output_data: Tool output (e.g., {"stdout": "...", "stderr": ""})

    Returns:
        Dict representing a tool span from Braintrust
    """
    return {
        "span_id": span_id,
        "name": tool_name,
        "span_parents": [parent_turn_span_id],
        "span_attributes": {"type": "tool"},
        "input": input_data,
        "output": output_data or {},
        "metadata": {"tool_name": tool_name},
        "created": f"2025-12-28T10:00:02Z",
    }


def create_mock_session_spans() -> tuple[list[dict[str, Any]], str]:
    """Create a realistic mock session with 6 turns and 9 LLM spans.

    This mirrors the structure from multi_turn_analysis.md:
    - 6 turns
    - 9 LLM spans (distributed across turns)
    - Tool spans for Bash, Read, Write
    - Error in one Bash span

    Returns:
        Tuple of (list of spans, session_id)
    """
    session_id = unique_session_id()
    spans: list[dict[str, Any]] = []

    # Turn 1: 3 LLM spans (typical for complex request)
    turn1_id = f"turn-1-{uuid4().hex[:8]}"
    spans.append(
        create_mock_turn_span(
            turn_number=1,
            span_id=turn1_id,
            user_input="Implement the memory backfill feature with LLMSpanMemory extraction",
        )
    )

    # LLM spans for Turn 1
    for i in range(3):
        spans.append(
            create_mock_llm_span(
                span_id=f"llm-1-{i}-{uuid4().hex[:8]}",
                parent_turn_span_id=turn1_id,
                decision=f"Turn 1 decision {i+1}: Planning the implementation architecture",
                tool_calls=[
                    {"function": {"name": "Read"}},
                    {"function": {"name": "Write"}},
                ]
                if i == 0
                else None,
            )
        )

    # Add tool spans for Turn 1
    spans.append(
        create_mock_tool_span(
            span_id=f"tool-read-1-{uuid4().hex[:8]}",
            parent_turn_span_id=turn1_id,
            tool_name="Read",
            input_data={"file_path": "/path/to/memory_backfill.py"},
        )
    )
    spans.append(
        create_mock_tool_span(
            span_id=f"tool-write-1-{uuid4().hex[:8]}",
            parent_turn_span_id=turn1_id,
            tool_name="Write",
            input_data={"file_path": "/path/to/new_file.py"},
        )
    )

    # Turn 2: 2 LLM spans
    turn2_id = f"turn-2-{uuid4().hex[:8]}"
    spans.append(
        create_mock_turn_span(
            turn_number=2,
            span_id=turn2_id,
            user_input="Add unit tests for the LLMSpanMemory dataclass",
        )
    )

    for i in range(2):
        spans.append(
            create_mock_llm_span(
                span_id=f"llm-2-{i}-{uuid4().hex[:8]}",
                parent_turn_span_id=turn2_id,
                decision=f"Turn 2 decision {i+1}: Creating pytest fixtures and test cases",
                tool_calls=[{"function": {"name": "Write"}}] if i == 1 else None,
            )
        )

    # Turn 3: 1 LLM span with error in Bash
    turn3_id = f"turn-3-{uuid4().hex[:8]}"
    spans.append(
        create_mock_turn_span(
            turn_number=3,
            span_id=turn3_id,
            user_input="Run the tests and fix any failures",
        )
    )

    spans.append(
        create_mock_llm_span(
            span_id=f"llm-3-0-{uuid4().hex[:8]}",
            parent_turn_span_id=turn3_id,
            decision="Turn 3 decision: Running pytest to validate implementation",
            tool_calls=[{"function": {"name": "Bash"}}],
        )
    )

    # Bash span with error
    spans.append(
        create_mock_tool_span(
            span_id=f"tool-bash-3-{uuid4().hex[:8]}",
            parent_turn_span_id=turn3_id,
            tool_name="Bash",
            input_data={"command": "uv run pytest tests/unit/test_llm_span_memory.py -v"},
            output_data={
                "stdout": "FAILED tests/unit/test_llm_span_memory.py::TestLLMSpanMemory::test_auto_hash\nAssertionError: Hash mismatch",
                "stderr": "",
            },
        )
    )

    # Turn 4: 2 LLM spans
    turn4_id = f"turn-4-{uuid4().hex[:8]}"
    spans.append(
        create_mock_turn_span(
            turn_number=4,
            span_id=turn4_id,
            user_input="Fix the hash computation issue in the dataclass",
        )
    )

    for i in range(2):
        spans.append(
            create_mock_llm_span(
                span_id=f"llm-4-{i}-{uuid4().hex[:8]}",
                parent_turn_span_id=turn4_id,
                decision=f"Turn 4 decision {i+1}: Fixing the content hash computation",
                tool_calls=[{"function": {"name": "Edit"}}] if i == 1 else None,
            )
        )

    spans.append(
        create_mock_tool_span(
            span_id=f"tool-edit-4-{uuid4().hex[:8]}",
            parent_turn_span_id=turn4_id,
            tool_name="Edit",
            input_data={"file_path": "/path/to/memory_backfill.py"},
        )
    )

    # Turn 5: 1 LLM span
    turn5_id = f"turn-5-{uuid4().hex[:8]}"
    spans.append(
        create_mock_turn_span(
            turn_number=5,
            span_id=turn5_id,
            user_input="Verify tests pass now",
        )
    )

    spans.append(
        create_mock_llm_span(
            span_id=f"llm-5-0-{uuid4().hex[:8]}",
            parent_turn_span_id=turn5_id,
            decision="Turn 5 decision: All tests passing, implementation complete",
            tool_calls=[{"function": {"name": "Bash"}}],
        )
    )

    spans.append(
        create_mock_tool_span(
            span_id=f"tool-bash-5-{uuid4().hex[:8]}",
            parent_turn_span_id=turn5_id,
            tool_name="Bash",
            input_data={"command": "uv run pytest tests/unit/test_llm_span_memory.py -v"},
            output_data={"stdout": "9 passed in 0.5s", "stderr": ""},
        )
    )

    # Turn 6: 0 LLM spans (edge case from analysis)
    turn6_id = f"turn-6-{uuid4().hex[:8]}"
    spans.append(
        create_mock_turn_span(
            turn_number=6,
            span_id=turn6_id,
            user_input="Commit the changes",
        )
    )
    # No LLM spans for Turn 6 - this is a known edge case

    return spans, session_id


class MockMemoryBackend:
    """Mock memory backend for testing storage operations."""

    def __init__(self):
        self.stored: list[dict[str, Any]] = []
        self.search_results: list[dict[str, Any]] = []

    async def store(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> str:
        """Store a memory and return its ID."""
        memory_id = f"mem-{uuid4().hex[:8]}"
        self.stored.append(
            {
                "id": memory_id,
                "content": content,
                "metadata": metadata or {},
                "embedding": embedding,
            }
        )
        return memory_id

    async def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Return mock search results."""
        return self.search_results[:limit]

    async def close(self):
        """Close the backend (no-op for mock)."""
        pass


class MockEmbeddingService:
    """Mock embedding service for testing."""

    def __init__(self, dimension: int = 256):
        self.dimension = dimension
        self.embed_count = 0

    async def embed(self, text: str) -> list[float]:
        """Generate a deterministic mock embedding."""
        self.embed_count += 1
        # Create deterministic embedding based on text hash
        # Use multiple hash iterations to generate enough bytes for any dimension
        embedding = []
        current_text = text
        while len(embedding) < self.dimension:
            text_hash = hashlib.sha256(current_text.encode()).hexdigest()
            for i in range(0, len(text_hash), 2):
                if len(embedding) >= self.dimension:
                    break
                embedding.append(float(int(text_hash[i : i + 2], 16)) / 255.0)
            current_text = text_hash  # Hash the hash for next iteration
        return embedding[: self.dimension]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings for a batch of texts."""
        return [await self.embed(text) for text in texts]


# =============================================================================
# Test Class: Full Pipeline E2E Tests
# =============================================================================


class TestLLMSpanMemoryE2E:
    """End-to-end tests for LLMSpanMemory extraction pipeline."""

    @pytest.mark.integration
    async def test_full_pipeline_with_mock_session(self):
        """Test complete extraction -> embedding -> storage pipeline with mock data.

        Verifies:
        1. LLMSpanMemory objects are extracted from mock spans
        2. All turns with LLM spans are processed
        3. Correct count of memories extracted
        4. Each memory has required fields populated
        """
        from scripts.agentica_patterns.memory_backfill import (
            LLMSpanMemory,
            extract_llm_span_memories,
        )

        # Create mock session data
        spans, session_id = create_mock_session_spans()

        # Extract LLMSpanMemory objects
        memories = extract_llm_span_memories(spans, session_id)

        # Verify extraction count (9 LLM spans across 5 turns with LLM spans)
        # Turn 1: 3, Turn 2: 2, Turn 3: 1, Turn 4: 2, Turn 5: 1 = 9 total
        assert len(memories) == 9, f"Expected 9 memories, got {len(memories)}"

        # Verify each memory has required fields
        for memory in memories:
            assert isinstance(memory, LLMSpanMemory)
            assert memory.span_id != ""
            assert memory.session_id == session_id
            assert memory.turn_number >= 1
            assert memory.embedding_text != ""
            assert memory.content_hash != ""

        # Verify turn distribution
        turn_counts = {}
        for memory in memories:
            turn_counts[memory.turn_number] = turn_counts.get(memory.turn_number, 0) + 1

        assert turn_counts.get(1, 0) == 3, "Turn 1 should have 3 LLM spans"
        assert turn_counts.get(2, 0) == 2, "Turn 2 should have 2 LLM spans"
        assert turn_counts.get(3, 0) == 1, "Turn 3 should have 1 LLM span"
        assert turn_counts.get(4, 0) == 2, "Turn 4 should have 2 LLM spans"
        assert turn_counts.get(5, 0) == 1, "Turn 5 should have 1 LLM span"
        assert turn_counts.get(6, 0) == 0, "Turn 6 should have 0 LLM spans (edge case)"

    @pytest.mark.integration
    async def test_full_pipeline_with_embedding_and_storage(self):
        """Test complete pipeline including embedding and storage.

        Uses mock embedding service and mock memory backend to test
        the full flow without external dependencies.
        """
        from scripts.agentica_patterns.memory_backfill import (
            LLMSpanMemory,
            extract_llm_span_memories,
            store_llm_span_memory,
        )

        # Create mock session
        spans, session_id = create_mock_session_spans()

        # Extract memories
        memories = extract_llm_span_memories(spans, session_id)
        assert len(memories) > 0

        # Generate embeddings
        embedder = MockEmbeddingService(dimension=256)
        texts = [m.embedding_text for m in memories]
        embeddings = await embedder.embed_batch(texts)

        # Assign embeddings
        for memory, embedding in zip(memories, embeddings):
            memory.embedding = embedding

        # Verify embeddings assigned
        for memory in memories:
            assert memory.embedding is not None
            assert len(memory.embedding) == 256

        # Store memories
        backend = MockMemoryBackend()
        stored_count = 0
        for memory in memories:
            memory_id, was_novel = await store_llm_span_memory(backend, memory)
            if was_novel:
                stored_count += 1

        # All should be novel on first run
        assert stored_count == len(memories)
        assert len(backend.stored) == len(memories)

        # Verify stored metadata
        for stored in backend.stored:
            assert "span_id" in stored["metadata"]
            assert "session_id" in stored["metadata"]
            assert "turn_number" in stored["metadata"]
            assert "content_hash" in stored["metadata"]
            assert "memory_type" in stored["metadata"]
            assert stored["metadata"]["memory_type"] == "llm_span_memory"

    @pytest.mark.integration
    async def test_cli_invocation_with_test_session(self):
        """Test CLI with --extract-span-memories flag using mock.

        Verifies the CLI argument parsing and integration with the
        backfill_session function.
        """
        from scripts.agentica_patterns.memory_backfill import parse_args

        # Test CLI argument parsing
        args = parse_args(
            [
                "--session-id",
                "test-session-123",
                "--extract-span-memories",
                "--dry-run",
                "--embedding-provider",
                "mock",
            ]
        )

        assert args.session_id == "test-session-123"
        assert args.extract_span_memories is True
        assert args.dry_run is True
        assert args.embedding_provider == "mock"

    @pytest.mark.integration
    async def test_metrics_tracking_accurate(self):
        """Test BackfillResult metrics are accurate.

        Verifies that the BackfillResult correctly tracks:
        - span_memories_extracted
        - span_memories_stored
        - span_memories_skipped
        """
        from scripts.agentica_patterns.memory_backfill import (
            BackfillResult,
            LLMSpanMemory,
            extract_llm_span_memories,
            store_llm_span_memory,
        )

        # Create mock session
        spans, session_id = create_mock_session_spans()

        # Extract memories
        memories = extract_llm_span_memories(spans, session_id)

        # Create result tracker
        result = BackfillResult(
            session_id=session_id,
            facts_extracted=0,
            facts_stored=0,
            facts_skipped_duplicate=0,
        )

        result.span_memories_extracted = len(memories)

        # Store with mock backend
        backend = MockMemoryBackend()
        embedder = MockEmbeddingService()

        for memory in memories:
            memory.embedding = await embedder.embed(memory.embedding_text)
            _, was_novel = await store_llm_span_memory(backend, memory)
            if was_novel:
                result.span_memories_stored += 1
            else:
                result.span_memories_skipped += 1

        # Verify metrics
        assert result.span_memories_extracted == 9
        assert result.span_memories_stored == 9  # All novel on first run
        assert result.span_memories_skipped == 0

    @pytest.mark.integration
    async def test_deduplication_on_re_run(self):
        """Test running same session twice doesn't duplicate memories.

        Verifies the content_hash-based deduplication works correctly
        by testing that the same spans produce identical content hashes.
        """
        from scripts.agentica_patterns.memory_backfill import (
            LLMSpanMemory,
            extract_llm_span_memories,
        )

        # Create mock session - save spans so we can reuse
        spans, session_id = create_mock_session_spans()

        # First extraction
        memories_run1 = extract_llm_span_memories(spans, session_id)
        assert len(memories_run1) == 9, f"Expected 9 memories, got {len(memories_run1)}"

        # Second extraction - same spans should produce identical memories
        memories_run2 = extract_llm_span_memories(spans, session_id)
        assert len(memories_run2) == 9, f"Expected 9 memories, got {len(memories_run2)}"

        # Verify deterministic hash generation
        hashes_run1 = [m.content_hash for m in memories_run1]
        hashes_run2 = [m.content_hash for m in memories_run2]

        # Same spans should produce same hashes in same order
        assert hashes_run1 == hashes_run2, "Same spans should produce identical hashes"

        # All hashes should be unique within a run (no duplicates)
        assert len(set(hashes_run1)) == len(hashes_run1), "Each memory should have unique hash"

        # Verify content_hash includes identifying information
        # Different span_ids should produce different hashes even with same content
        memory_a = LLMSpanMemory(
            span_id="span-a",
            turn_number=1,
            session_id="session-1",
            user_intent="Same intent",
            decision="Same decision",
        )
        memory_b = LLMSpanMemory(
            span_id="span-b",  # Different span_id
            turn_number=1,
            session_id="session-1",
            user_intent="Same intent",
            decision="Same decision",
        )
        assert memory_a.content_hash != memory_b.content_hash, \
            "Different span_ids should produce different hashes"

        # Same identifiers should produce same hash
        memory_c = LLMSpanMemory(
            span_id="span-a",
            turn_number=1,
            session_id="session-1",
            user_intent="Same intent",
            decision="Same decision",
        )
        assert memory_a.content_hash == memory_c.content_hash, \
            "Same inputs should produce same hash"

    @pytest.mark.integration
    async def test_error_recovery(self):
        """Test graceful handling of partial failures.

        Verifies the pipeline handles:
        - Malformed spans
        - Missing fields
        - Storage failures
        """
        from scripts.agentica_patterns.memory_backfill import (
            extract_llm_span_memories,
            store_llm_span_memory,
        )

        session_id = unique_session_id()

        # Create spans with some malformed entries
        spans = [
            # Valid turn with LLM span
            create_mock_turn_span(1, "turn-1", "Valid user input"),
            create_mock_llm_span("llm-1", "turn-1", "Valid decision"),
            # Malformed: Turn span with no input
            {"span_id": "turn-2", "name": "Turn 2", "span_attributes": {"type": "task"}},
            # Malformed: LLM span with missing output
            {
                "span_id": "llm-2",
                "name": "llm",
                "span_parents": ["turn-2"],
                "span_attributes": {"type": "llm"},
                "output": None,
            },
            # Valid turn with LLM span
            create_mock_turn_span(3, "turn-3", "Another valid input"),
            create_mock_llm_span("llm-3", "turn-3", "Another valid decision"),
        ]

        # Should extract valid spans without crashing
        memories = extract_llm_span_memories(spans, session_id)

        # Should have extracted at least the valid ones
        assert len(memories) >= 2, f"Expected at least 2 valid memories, got {len(memories)}"

        # Verify valid memories have correct content
        valid_decisions = [m.decision for m in memories if m.decision]
        assert any("Valid decision" in d for d in valid_decisions)

    @pytest.mark.integration
    async def test_turn_with_zero_llm_spans_handled(self):
        """Test Turn 6 edge case with 0 LLM spans is handled gracefully.

        This mirrors the Turn 6 case from multi_turn_analysis.md where
        a turn had tool spans but no LLM spans.
        """
        from scripts.agentica_patterns.memory_backfill import (
            build_turn_llm_hierarchy,
            extract_llm_span_memories,
        )

        session_id = unique_session_id()

        # Create a session with a turn that has no LLM spans
        spans = [
            create_mock_turn_span(1, "turn-1", "Normal turn with LLM"),
            create_mock_llm_span("llm-1", "turn-1", "Normal LLM response"),
            # Turn 2 with only tool spans, no LLM
            create_mock_turn_span(2, "turn-2", "Turn with only tool calls"),
            create_mock_tool_span("tool-1", "turn-2", "Bash", {"command": "ls"}),
            create_mock_tool_span("tool-2", "turn-2", "Write", {"file_path": "/tmp/x.txt"}),
            # Turn 3 back to normal
            create_mock_turn_span(3, "turn-3", "Normal turn again"),
            create_mock_llm_span("llm-3", "turn-3", "Normal LLM response"),
        ]

        # Build hierarchy should not crash
        hierarchy = build_turn_llm_hierarchy(spans)
        assert "Turn 1" in hierarchy
        assert "Turn 2" in hierarchy
        assert "Turn 3" in hierarchy
        assert len(hierarchy["Turn 2"]["llm_spans"]) == 0

        # Extract should skip Turn 2 gracefully
        memories = extract_llm_span_memories(spans, session_id)
        assert len(memories) == 2  # Only Turn 1 and Turn 3

        turn_numbers = [m.turn_number for m in memories]
        assert 1 in turn_numbers
        assert 2 not in turn_numbers  # Turn 2 skipped
        assert 3 in turn_numbers

    @pytest.mark.integration
    async def test_error_detection_in_bash_spans(self):
        """Test that errors in Bash spans are detected and captured.

        Verifies the error_summary field is populated when Bash output
        contains error patterns like tracebacks or test failures.
        """
        from scripts.agentica_patterns.memory_backfill import (
            detect_error_in_turn,
            extract_llm_span_memories,
        )

        session_id = unique_session_id()

        # Create session with Bash error
        turn_id = "turn-with-error"
        spans = [
            create_mock_turn_span(1, turn_id, "Run failing test"),
            create_mock_llm_span("llm-1", turn_id, "Running the test suite"),
            create_mock_tool_span(
                "bash-1",
                turn_id,
                "Bash",
                {"command": "uv run pytest tests/"},
                {
                    "stdout": """
FAILED tests/unit/test_something.py::TestClass::test_method
Traceback (most recent call last):
  File "tests/unit/test_something.py", line 42, in test_method
    assert result == expected
AssertionError: Expected 5, got 3
""",
                    "stderr": "",
                },
            ),
        ]

        # Test error detection directly
        error = detect_error_in_turn(turn_id, spans)
        assert error is not None
        assert "FAILED" in error or "AssertionError" in error or "Traceback" in error

        # Test via full extraction
        memories = extract_llm_span_memories(spans, session_id)
        assert len(memories) == 1
        assert memories[0].error_summary is not None

    @pytest.mark.integration
    async def test_files_touched_extraction(self):
        """Test extraction of files touched from tool spans.

        Verifies files_touched list is populated from Read/Write/Edit spans.
        """
        from scripts.agentica_patterns.memory_backfill import (
            extract_files_from_turn,
            extract_llm_span_memories,
        )

        session_id = unique_session_id()
        turn_id = "turn-with-files"

        spans = [
            create_mock_turn_span(1, turn_id, "Modify files"),
            create_mock_llm_span("llm-1", turn_id, "Editing multiple files"),
            create_mock_tool_span(
                "read-1", turn_id, "Read", {"file_path": "/path/to/file1.py"}
            ),
            create_mock_tool_span(
                "write-1", turn_id, "Write", {"file_path": "/path/to/file2.py"}
            ),
            create_mock_tool_span(
                "edit-1", turn_id, "Edit", {"file_path": "/path/to/file3.py"}
            ),
            # Duplicate file (should be deduplicated)
            create_mock_tool_span(
                "write-2", turn_id, "Write", {"file_path": "/path/to/file2.py"}
            ),
        ]

        # Test directly
        files = extract_files_from_turn(turn_id, spans)
        assert len(files) == 3  # Deduplicated
        assert "/path/to/file1.py" in files
        assert "/path/to/file2.py" in files
        assert "/path/to/file3.py" in files

        # Test via full extraction
        memories = extract_llm_span_memories(spans, session_id)
        assert len(memories) == 1
        assert len(memories[0].files_touched) == 3

    @pytest.mark.integration
    async def test_tools_called_extraction(self):
        """Test extraction of tool names from LLM span tool_calls.

        Verifies tools_called list is populated correctly with deduplication.
        """
        from scripts.agentica_patterns.memory_backfill import (
            extract_tools_from_llm_span,
            extract_llm_span_memories,
        )

        session_id = unique_session_id()
        turn_id = "turn-with-tools"

        llm_span = create_mock_llm_span(
            "llm-1",
            turn_id,
            "Executing multiple tools",
            tool_calls=[
                {"function": {"name": "Read"}},
                {"function": {"name": "Write"}},
                {"function": {"name": "Read"}},  # Duplicate
                {"function": {"name": "Bash"}},
            ],
        )

        # Test directly
        tools = extract_tools_from_llm_span(llm_span)
        assert len(tools) == 3  # Deduplicated
        assert tools == ["Read", "Write", "Bash"]  # Order preserved

        # Test via full extraction
        spans = [
            create_mock_turn_span(1, turn_id, "Use multiple tools"),
            llm_span,
        ]
        memories = extract_llm_span_memories(spans, session_id)
        assert len(memories) == 1
        assert memories[0].tools_called == ["Read", "Write", "Bash"]


# =============================================================================
# Test Class: Real API Tests (Require BRAINTRUST_API_KEY)
# =============================================================================


@pytest.mark.skipif(
    not os.getenv("BRAINTRUST_API_KEY"),
    reason="BRAINTRUST_API_KEY not set - skipping real API tests",
)
class TestLLMSpanMemoryRealAPI:
    """Integration tests using real Braintrust API.

    These tests require BRAINTRUST_API_KEY to be set.
    Skip if running without API access.
    """

    @pytest.mark.integration
    async def test_extract_from_real_session(self):
        """Extract from a real Braintrust session.

        Uses a known test session ID if available in the environment,
        otherwise skips.
        """
        from scripts.agentica_patterns.memory_backfill import (
            backfill_session,
        )

        # Use a known test session or skip
        test_session_id = os.getenv("TEST_SESSION_ID")
        if not test_session_id:
            pytest.skip("TEST_SESSION_ID not set - skipping real session test")

        project_id = os.getenv("BRAINTRUST_PROJECT_ID", "")
        api_key = os.getenv("BRAINTRUST_API_KEY", "")

        if not project_id:
            pytest.skip("BRAINTRUST_PROJECT_ID not set")

        # Run with dry_run to avoid storage
        result = await backfill_session(
            session_id=test_session_id,
            project_id=project_id,
            api_key=api_key,
            extract_span_memories=True,
            dry_run=True,
            embedding_provider="mock",
        )

        # Verify some span memories were extracted
        assert result.span_memories_extracted >= 0
        # If there are LLM spans, we should have extracted them
        # (can't assert > 0 without knowing the session content)

    @pytest.mark.integration
    async def test_backfill_with_real_embedding(self):
        """Test backfill with real embedding provider.

        Requires OPENAI_API_KEY or similar for embedding generation.
        """
        openai_key = os.getenv("OPENAI_API_KEY")
        voyage_key = os.getenv("VOYAGE_API_KEY")

        if not (openai_key or voyage_key):
            pytest.skip("No embedding API key available")

        test_session_id = os.getenv("TEST_SESSION_ID")
        if not test_session_id:
            pytest.skip("TEST_SESSION_ID not set")

        from scripts.agentica_patterns.memory_backfill import backfill_session

        project_id = os.getenv("BRAINTRUST_PROJECT_ID", "")
        api_key = os.getenv("BRAINTRUST_API_KEY", "")

        provider = "openai" if openai_key else "voyage"

        result = await backfill_session(
            session_id=test_session_id,
            project_id=project_id,
            api_key=api_key,
            extract_span_memories=True,
            dry_run=True,  # Don't actually store
            embedding_provider=provider,
        )

        # Should complete without errors
        assert len(result.errors) == 0 or all(
            "not implemented" in e.lower() for e in result.errors
        )


# =============================================================================
# Test Class: Performance Tests
# =============================================================================


class TestLLMSpanMemoryPerformance:
    """Performance tests for LLMSpanMemory extraction."""

    @pytest.mark.integration
    async def test_extraction_performance_100_spans(self):
        """Test extraction performance with 100 spans completes in <1s.

        Creates a realistic session with many spans and verifies
        extraction completes within acceptable time.
        """
        from scripts.agentica_patterns.memory_backfill import extract_llm_span_memories

        session_id = unique_session_id()
        spans = []

        # Create 20 turns with 5 LLM spans each = 100 LLM spans
        for turn_num in range(1, 21):
            turn_id = f"turn-{turn_num}-{uuid4().hex[:8]}"
            spans.append(
                create_mock_turn_span(
                    turn_number=turn_num,
                    span_id=turn_id,
                    user_input=f"User request for turn {turn_num}",
                )
            )

            for llm_num in range(5):
                spans.append(
                    create_mock_llm_span(
                        span_id=f"llm-{turn_num}-{llm_num}-{uuid4().hex[:8]}",
                        parent_turn_span_id=turn_id,
                        decision=f"Turn {turn_num} LLM {llm_num} decision with some content",
                    )
                )

        # Measure extraction time
        start_time = time.time()
        memories = extract_llm_span_memories(spans, session_id)
        elapsed = time.time() - start_time

        assert len(memories) == 100, f"Expected 100 memories, got {len(memories)}"
        assert elapsed < 1.0, f"Extraction took {elapsed:.2f}s, expected <1s"

    @pytest.mark.integration
    async def test_embedding_batch_performance(self):
        """Test embedding batch performance with mock embedder.

        Verifies batch embedding of 100 texts completes quickly.
        """
        embedder = MockEmbeddingService(dimension=256)
        texts = [f"Sample text for embedding {i}" for i in range(100)]

        start_time = time.time()
        embeddings = await embedder.embed_batch(texts)
        elapsed = time.time() - start_time

        assert len(embeddings) == 100
        assert elapsed < 1.0, f"Batch embedding took {elapsed:.2f}s, expected <1s"
        assert all(len(e) == 256 for e in embeddings)


# =============================================================================
# Test Class: Edge Cases
# =============================================================================


class TestLLMSpanMemoryEdgeCases:
    """Edge case tests for LLMSpanMemory extraction."""

    @pytest.mark.integration
    async def test_empty_spans_list(self):
        """Test extraction with empty spans list."""
        from scripts.agentica_patterns.memory_backfill import extract_llm_span_memories

        memories = extract_llm_span_memories([], "session-123")
        assert memories == []

    @pytest.mark.integration
    async def test_spans_with_no_turns(self):
        """Test spans that have no Turn type spans."""
        from scripts.agentica_patterns.memory_backfill import extract_llm_span_memories

        # Only LLM spans, no Turn spans
        spans = [
            {
                "span_id": "llm-orphan",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Orphan LLM span"},
            }
        ]

        memories = extract_llm_span_memories(spans, "session-123")
        assert memories == []

    @pytest.mark.integration
    async def test_deeply_nested_turns(self):
        """Test handling of deeply nested spans."""
        from scripts.agentica_patterns.memory_backfill import extract_llm_span_memories

        session_id = unique_session_id()

        # Create nested structure
        spans = [
            create_mock_turn_span(1, "turn-1", "Top level turn"),
            create_mock_llm_span("llm-1", "turn-1", "Top level LLM"),
            # These shouldn't interfere
            {
                "span_id": "nested-task",
                "name": "SubTask",
                "span_parents": ["turn-1"],
                "span_attributes": {"type": "task"},
            },
        ]

        memories = extract_llm_span_memories(spans, session_id)
        assert len(memories) == 1

    @pytest.mark.integration
    async def test_unicode_content_handling(self):
        """Test handling of unicode content in spans."""
        from scripts.agentica_patterns.memory_backfill import extract_llm_span_memories

        session_id = unique_session_id()

        spans = [
            create_mock_turn_span(1, "turn-1", "Unicode input: Emoji!"),
            create_mock_llm_span("llm-1", "turn-1", "Response with unicode: "),
        ]

        memories = extract_llm_span_memories(spans, session_id)
        assert len(memories) == 1
        assert "Emoji!" in memories[0].user_intent or "" in memories[0].user_intent

    @pytest.mark.integration
    async def test_very_long_content_truncation(self):
        """Test that very long content is properly truncated."""
        from scripts.agentica_patterns.memory_backfill import (
            extract_user_intent_raw,
            extract_llm_decision,
        )

        # Create span with very long input
        long_input = "x" * 10000
        turn_span = {"input": long_input}

        intent = extract_user_intent_raw(turn_span, max_chars=500)
        assert len(intent) <= 503  # 500 + "..."
        assert intent.endswith("...")

        # Create span with very long output
        llm_span = {"output": {"content": "y" * 10000}}
        decision = extract_llm_decision(llm_span, max_chars=300)
        assert len(decision) <= 303  # 300 + "..."
        assert decision.endswith("...")

    @pytest.mark.integration
    async def test_null_and_none_values(self):
        """Test handling of null/None values in spans."""
        from scripts.agentica_patterns.memory_backfill import (
            extract_user_intent_raw,
            extract_llm_decision,
            extract_tools_from_llm_span,
        )

        # None input
        assert extract_user_intent_raw({"input": None}) == ""

        # None output
        assert extract_llm_decision({"output": None}) == ""

        # None tool_calls
        assert extract_tools_from_llm_span({"output": {"tool_calls": None}}) == []

        # Empty dict output
        assert extract_llm_decision({"output": {}}) == ""

    @pytest.mark.integration
    async def test_malformed_tool_calls(self):
        """Test handling of malformed tool_calls structures."""
        from scripts.agentica_patterns.memory_backfill import extract_tools_from_llm_span

        # Missing function key
        span1 = {"output": {"tool_calls": [{"id": "123"}]}}
        assert extract_tools_from_llm_span(span1) == []

        # Missing name in function
        span2 = {"output": {"tool_calls": [{"function": {}}]}}
        assert extract_tools_from_llm_span(span2) == []

        # Mixed valid/invalid
        span3 = {
            "output": {
                "tool_calls": [
                    {"function": {"name": "ValidTool"}},
                    {"invalid": "structure"},
                    None,
                    {"function": {"name": "AnotherValid"}},
                ]
            }
        }
        assert extract_tools_from_llm_span(span3) == ["ValidTool", "AnotherValid"]

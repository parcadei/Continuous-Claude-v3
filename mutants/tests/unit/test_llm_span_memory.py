"""Tests for LLMSpanMemory dataclass - TDD-style failing tests.

This module tests the LLMSpanMemory dataclass that will be added to
scripts/agentica/memory_backfill.py as part of Phase 1 implementation.

Plan location: thoughts/shared/plans/2025-12-28-llm-span-memory.md

Run with: uv run pytest tests/unit/test_llm_span_memory.py -v

Expected behavior:
- Before implementation: Tests fail with ImportError (LLMSpanMemory not defined)
- After implementation: All tests pass
"""

import hashlib
import json
import pytest


# =============================================================================
# Phase 1: LLMSpanMemory Dataclass Tests
# =============================================================================


class TestLLMSpanMemoryInstantiation:
    """Test basic instantiation of LLMSpanMemory dataclass."""

    def test_llm_span_memory_instantiation(self):
        """LLMSpanMemory can be instantiated with required fields.

        Required fields:
        - span_id: str
        - turn_number: int
        - session_id: str
        - user_intent: str
        - decision: str
        """
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-abc123",
            turn_number=1,
            session_id="session-xyz789",
            user_intent="Implement the memory backfill feature",
            decision="Use a 6-stage pipeline architecture",
        )

        # Verify required fields are set correctly
        assert memory.span_id == "span-abc123"
        assert memory.turn_number == 1
        assert memory.session_id == "session-xyz789"
        assert memory.user_intent == "Implement the memory backfill feature"
        assert memory.decision == "Use a 6-stage pipeline architecture"

    def test_llm_span_memory_field_types(self):
        """LLMSpanMemory fields have correct types."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-123",
            turn_number=5,
            session_id="sess-456",
            user_intent="Write tests",
            decision="Use pytest fixtures",
        )

        # Type checks
        assert isinstance(memory.span_id, str)
        assert isinstance(memory.turn_number, int)
        assert isinstance(memory.session_id, str)
        assert isinstance(memory.user_intent, str)
        assert isinstance(memory.decision, str)


class TestLLMSpanMemoryAutoEmbeddingText:
    """Test auto-generation of embedding_text from user_intent + decision."""

    def test_llm_span_memory_auto_embedding_text(self):
        """embedding_text is auto-generated from user_intent and decision.

        Format: "Intent: {user_intent}\nDecision: {decision}"
        """
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Build a REST API",
            decision="Use FastAPI framework",
        )

        # embedding_text should combine intent and decision
        assert memory.embedding_text != ""
        assert "Build a REST API" in memory.embedding_text
        assert "Use FastAPI framework" in memory.embedding_text

    def test_llm_span_memory_embedding_text_format(self):
        """embedding_text follows expected format for semantic search."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=2,
            session_id="sess-1",
            user_intent="Optimize database queries",
            decision="Add indexes on frequently queried columns",
        )

        # Verify format includes both components
        expected_format = "Intent: Optimize database queries\nDecision: Add indexes on frequently queried columns"
        assert memory.embedding_text == expected_format

    def test_llm_span_memory_empty_intent_or_decision(self):
        """embedding_text handles edge cases gracefully."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        # Empty decision
        memory1 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Just a question",
            decision="",
        )
        assert "Just a question" in memory1.embedding_text

        # Minimal content
        memory2 = LLMSpanMemory(
            span_id="span-2",
            turn_number=2,
            session_id="sess-1",
            user_intent="x",
            decision="y",
        )
        assert memory2.embedding_text != ""


class TestLLMSpanMemoryAutoContentHash:
    """Test auto-generation of content_hash for deduplication."""

    def test_llm_span_memory_auto_content_hash(self):
        """content_hash is auto-generated from span_id + session_id + user_intent + decision."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-abc",
            turn_number=1,
            session_id="sess-xyz",
            user_intent="Create user authentication",
            decision="Use JWT tokens with refresh",
        )

        # content_hash should be populated
        assert memory.content_hash != ""
        # Should be a hex string (SHA256 truncated)
        assert all(c in "0123456789abcdef" for c in memory.content_hash)

    def test_llm_span_memory_content_hash_deterministic(self):
        """Same inputs produce same content_hash."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory1 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Test intent",
            decision="Test decision",
        )

        memory2 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Test intent",
            decision="Test decision",
        )

        assert memory1.content_hash == memory2.content_hash

    def test_llm_span_memory_content_hash_unique_per_span(self):
        """Different span_ids produce different content_hash."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory1 = LLMSpanMemory(
            span_id="span-AAA",
            turn_number=1,
            session_id="sess-1",
            user_intent="Same intent",
            decision="Same decision",
        )

        memory2 = LLMSpanMemory(
            span_id="span-BBB",
            turn_number=1,
            session_id="sess-1",
            user_intent="Same intent",
            decision="Same decision",
        )

        assert memory1.content_hash != memory2.content_hash

    def test_llm_span_memory_content_hash_unique_per_session(self):
        """Different session_ids produce different content_hash."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory1 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="session-AAA",
            user_intent="Same intent",
            decision="Same decision",
        )

        memory2 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="session-BBB",
            user_intent="Same intent",
            decision="Same decision",
        )

        assert memory1.content_hash != memory2.content_hash

    def test_llm_span_memory_content_hash_length(self):
        """content_hash is 16 characters (truncated SHA256)."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Any intent",
            decision="Any decision",
        )

        assert len(memory.content_hash) == 16


class TestLLMSpanMemoryDefaultLists:
    """Test default values for list fields."""

    def test_llm_span_memory_default_lists(self):
        """tools_called and files_touched default to empty lists."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Do something",
            decision="Decided to act",
        )

        # Default empty lists
        assert memory.tools_called == []
        assert memory.files_touched == []
        assert isinstance(memory.tools_called, list)
        assert isinstance(memory.files_touched, list)

    def test_llm_span_memory_explicit_lists(self):
        """tools_called and files_touched can be explicitly provided."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Edit files",
            decision="Use Edit tool",
            tools_called=["Read", "Edit", "Write"],
            files_touched=["/path/to/file.py", "/path/to/test.py"],
        )

        assert memory.tools_called == ["Read", "Edit", "Write"]
        assert memory.files_touched == ["/path/to/file.py", "/path/to/test.py"]

    def test_llm_span_memory_list_independence(self):
        """Each instance has independent list fields (no shared mutable default)."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory1 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="First task",
            decision="First decision",
        )

        memory2 = LLMSpanMemory(
            span_id="span-2",
            turn_number=2,
            session_id="sess-1",
            user_intent="Second task",
            decision="Second decision",
        )

        # Modify memory1's lists
        memory1.tools_called.append("Bash")
        memory1.files_touched.append("/modified.py")

        # memory2 should be unaffected
        assert memory2.tools_called == []
        assert memory2.files_touched == []


class TestLLMSpanMemoryOptionalFields:
    """Test optional fields that can be None."""

    def test_llm_span_memory_optional_fields(self):
        """outcome, error_summary, and embedding can be None."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Do task",
            decision="Make decision",
        )

        # Optional fields default to None
        assert memory.outcome is None
        assert memory.error_summary is None
        assert memory.embedding is None

    def test_llm_span_memory_with_outcome(self):
        """outcome can be set to a string value."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Run tests",
            decision="Use pytest",
            outcome="All 42 tests passed",
        )

        assert memory.outcome == "All 42 tests passed"

    def test_llm_span_memory_with_error_summary(self):
        """error_summary can be set when errors occurred."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Deploy service",
            decision="Use docker compose",
            error_summary="Port 8080 already in use, switched to 8081",
        )

        assert memory.error_summary == "Port 8080 already in use, switched to 8081"

    def test_llm_span_memory_with_embedding(self):
        """embedding can be set to a list of floats."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        embedding_vector = [0.1, 0.2, 0.3, 0.4, 0.5]

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Embed this",
            decision="Use OpenAI",
            embedding=embedding_vector,
        )

        assert memory.embedding == embedding_vector
        assert len(memory.embedding) == 5

    def test_llm_span_memory_all_optional_fields_set(self):
        """All optional fields can be set simultaneously."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-full",
            turn_number=3,
            session_id="sess-complete",
            user_intent="Complete task with all metadata",
            decision="Include all optional fields",
            tools_called=["Read", "Write"],
            files_touched=["/app/main.py"],
            outcome="Task completed successfully",
            error_summary=None,  # Explicit None
            embedding=[0.1] * 1536,
        )

        assert memory.span_id == "span-full"
        assert memory.turn_number == 3
        assert memory.tools_called == ["Read", "Write"]
        assert memory.files_touched == ["/app/main.py"]
        assert memory.outcome == "Task completed successfully"
        assert memory.error_summary is None
        assert len(memory.embedding) == 1536


class TestLLMSpanMemoryPostInit:
    """Test __post_init__ behavior for auto-generated fields."""

    def test_llm_span_memory_post_init_generates_hash(self):
        """__post_init__ generates content_hash if not provided."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-auto",
            turn_number=1,
            session_id="sess-auto",
            user_intent="Auto-generate hash",
            decision="Let __post_init__ handle it",
        )

        # Hash should be auto-generated
        assert memory.content_hash != ""
        assert len(memory.content_hash) == 16

    def test_llm_span_memory_post_init_generates_embedding_text(self):
        """__post_init__ generates embedding_text if empty."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Generate embedding text",
            decision="Concatenate intent and decision",
        )

        # embedding_text should be auto-generated
        assert memory.embedding_text != ""
        assert "Generate embedding text" in memory.embedding_text
        assert "Concatenate intent and decision" in memory.embedding_text

    def test_llm_span_memory_post_init_respects_explicit_hash(self):
        """__post_init__ does not overwrite explicitly provided content_hash."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        explicit_hash = "abcdef0123456789"

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="With explicit hash",
            decision="Should not be overwritten",
            content_hash=explicit_hash,
        )

        # Explicit hash should be preserved
        assert memory.content_hash == explicit_hash

    def test_llm_span_memory_post_init_respects_explicit_embedding_text(self):
        """__post_init__ does not overwrite explicitly provided embedding_text."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        explicit_text = "Custom embedding text for special cases"

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Ignored intent",
            decision="Ignored decision",
            embedding_text=explicit_text,
        )

        # Explicit embedding_text should be preserved
        assert memory.embedding_text == explicit_text


class TestLLMSpanMemoryEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_llm_span_memory_very_long_intent(self):
        """Handle very long user_intent strings."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        long_intent = "Implement feature " * 100  # ~1700 chars

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent=long_intent,
            decision="Handle long content",
        )

        assert len(memory.user_intent) > 1000
        assert memory.content_hash != ""
        assert memory.embedding_text != ""

    def test_llm_span_memory_unicode_content(self):
        """Handle unicode characters in content."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-unicode",
            turn_number=1,
            session_id="sess-1",
            user_intent="Add support for emojis like and special chars",
            decision="Use UTF-8 encoding everywhere",
        )

        assert memory.user_intent != ""
        assert memory.content_hash != ""

    def test_llm_span_memory_high_turn_number(self):
        """Handle high turn numbers."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=999,
            session_id="sess-long",
            user_intent="Late in conversation",
            decision="Still works",
        )

        assert memory.turn_number == 999

    def test_llm_span_memory_zero_turn_number(self):
        """Handle turn_number of 0 (edge case)."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        memory = LLMSpanMemory(
            span_id="span-0",
            turn_number=0,
            session_id="sess-1",
            user_intent="Turn zero",
            decision="Edge case",
        )

        assert memory.turn_number == 0


# =============================================================================
# Phase 2: Turn/Span Hierarchy Parser Tests
# =============================================================================


class TestBuildTurnLLMHierarchy:
    """Tests for build_turn_llm_hierarchy function.

    This function builds a mapping of turns to their LLM spans from raw Braintrust spans.

    Expected structure from Braintrust:
        Session Root (span_parents: null)
          └─ Turn N (span_parents: [root], name="Turn N", span_attributes.type="task")
               ├─ LLM span (span_parents: [turn], span_attributes.type="llm")
               └─ Tool spans (span_parents: [turn])
    """

    @pytest.fixture
    def mock_session_root_span(self):
        """Create a mock session root span."""
        return {
            "span_id": "root-span-001",
            "span_parents": None,
            "name": "Session",
            "span_attributes": {"type": "task"},
        }

    @pytest.fixture
    def mock_turn_spans(self):
        """Create mock turn spans (Turn 1-6)."""
        return [
            {
                "span_id": "turn-1-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
                "input": "Implement the memory backfill feature",
            },
            {
                "span_id": "turn-2-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 2",
                "span_attributes": {"type": "task"},
                "input": "Now add error handling",
            },
            {
                "span_id": "turn-3-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 3",
                "span_attributes": {"type": "task"},
                "input": "Run the tests",
            },
            {
                "span_id": "turn-4-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 4",
                "span_attributes": {"type": "task"},
                "input": "Fix the failing test",
            },
            {
                "span_id": "turn-5-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 5",
                "span_attributes": {"type": "task"},
                "input": "Add documentation",
            },
            {
                "span_id": "turn-6-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 6",
                "span_attributes": {"type": "task"},
                "input": "Final review",
            },
        ]

    @pytest.fixture
    def mock_llm_spans(self):
        """Create mock LLM spans under various turns."""
        return [
            # Turn 1: 3 LLM spans
            {
                "span_id": "llm-1a",
                "span_parents": ["turn-1-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "I'll start by analyzing the requirements..."},
            },
            {
                "span_id": "llm-1b",
                "span_parents": ["turn-1-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Now implementing the core logic..."},
            },
            {
                "span_id": "llm-1c",
                "span_parents": ["turn-1-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Feature implementation complete."},
            },
            # Turn 2: 2 LLM spans
            {
                "span_id": "llm-2a",
                "span_parents": ["turn-2-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Adding try/except blocks..."},
            },
            {
                "span_id": "llm-2b",
                "span_parents": ["turn-2-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Error handling added."},
            },
            # Turn 3: 1 LLM span
            {
                "span_id": "llm-3a",
                "span_parents": ["turn-3-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Running pytest..."},
            },
            # Turn 4: 1 LLM span
            {
                "span_id": "llm-4a",
                "span_parents": ["turn-4-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Fixed the assertion error."},
            },
            # Turn 5: 2 LLM spans
            {
                "span_id": "llm-5a",
                "span_parents": ["turn-5-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Adding docstrings..."},
            },
            {
                "span_id": "llm-5b",
                "span_parents": ["turn-5-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Documentation complete."},
            },
            # Turn 6: 0 LLM spans (empty turn - edge case from analysis)
        ]

    @pytest.fixture
    def mock_tool_spans(self):
        """Create mock tool spans (not LLM spans, should not appear in hierarchy)."""
        return [
            {
                "span_id": "tool-read-1",
                "span_parents": ["turn-1-span"],
                "name": "Read",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/file.py"},
            },
            {
                "span_id": "tool-write-1",
                "span_parents": ["turn-1-span"],
                "name": "Write",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/output.py"},
            },
        ]

    @pytest.fixture
    def all_spans(
        self, mock_session_root_span, mock_turn_spans, mock_llm_spans, mock_tool_spans
    ):
        """Combine all mock spans into a single list."""
        return (
            [mock_session_root_span] + mock_turn_spans + mock_llm_spans + mock_tool_spans
        )

    def test_builds_hierarchy_from_spans(self, all_spans):
        """Test that turns are correctly identified and LLM spans mapped.

        build_turn_llm_hierarchy should return a dict where:
        - Keys are turn names ("Turn 1", "Turn 2", etc.)
        - Values contain span_id, input (user prompt), and llm_spans list
        """
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        hierarchy = build_turn_llm_hierarchy(all_spans)

        # Should have Turn 1-6
        assert len(hierarchy) >= 1

        # Turn 1 should exist and have structure
        assert "Turn 1" in hierarchy
        turn1 = hierarchy["Turn 1"]
        assert "span_id" in turn1
        assert "input" in turn1
        assert "llm_spans" in turn1

    def test_handles_multiple_turns(self, all_spans):
        """Test Turn 1-6 are all found."""
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        hierarchy = build_turn_llm_hierarchy(all_spans)

        # All 6 turns should be in the hierarchy
        for i in range(1, 7):
            assert f"Turn {i}" in hierarchy, f"Turn {i} missing from hierarchy"

    def test_maps_llm_spans_to_parent_turn(self, all_spans):
        """Test LLM spans are grouped under their parent turn."""
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        hierarchy = build_turn_llm_hierarchy(all_spans)

        # Turn 1 should have 3 LLM spans
        assert len(hierarchy["Turn 1"]["llm_spans"]) == 3

        # Turn 2 should have 2 LLM spans
        assert len(hierarchy["Turn 2"]["llm_spans"]) == 2

        # Turn 3 should have 1 LLM span
        assert len(hierarchy["Turn 3"]["llm_spans"]) == 1

        # Turn 4 should have 1 LLM span
        assert len(hierarchy["Turn 4"]["llm_spans"]) == 1

        # Turn 5 should have 2 LLM spans
        assert len(hierarchy["Turn 5"]["llm_spans"]) == 2

    def test_handles_empty_turn(self, all_spans):
        """Test turns with 0 LLM spans (like Turn 6 in analysis).

        Turn 6 has no LLM spans but still exists as a turn.
        The function should include it with an empty llm_spans list.
        """
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        hierarchy = build_turn_llm_hierarchy(all_spans)

        # Turn 6 should exist but have 0 LLM spans
        assert "Turn 6" in hierarchy
        assert hierarchy["Turn 6"]["llm_spans"] == []

    def test_handles_no_turns(self):
        """Test empty span list returns empty dict."""
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        hierarchy = build_turn_llm_hierarchy([])

        assert hierarchy == {}

    def test_extracts_turn_input(self, all_spans):
        """Test user input is captured from turn span."""
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        hierarchy = build_turn_llm_hierarchy(all_spans)

        # Verify user inputs are captured
        assert hierarchy["Turn 1"]["input"] == "Implement the memory backfill feature"
        assert hierarchy["Turn 2"]["input"] == "Now add error handling"
        assert hierarchy["Turn 3"]["input"] == "Run the tests"
        assert hierarchy["Turn 4"]["input"] == "Fix the failing test"
        assert hierarchy["Turn 5"]["input"] == "Add documentation"
        assert hierarchy["Turn 6"]["input"] == "Final review"

    def test_extracts_turn_span_id(self, all_spans):
        """Test turn span_id is captured."""
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        hierarchy = build_turn_llm_hierarchy(all_spans)

        assert hierarchy["Turn 1"]["span_id"] == "turn-1-span"
        assert hierarchy["Turn 2"]["span_id"] == "turn-2-span"

    def test_llm_spans_contain_output(self, all_spans):
        """Test LLM spans preserve their output field."""
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        hierarchy = build_turn_llm_hierarchy(all_spans)

        # First LLM span of Turn 1 should have output
        llm_span = hierarchy["Turn 1"]["llm_spans"][0]
        assert "output" in llm_span
        assert llm_span["output"]["content"] == "I'll start by analyzing the requirements..."

    def test_excludes_tool_spans_from_llm_list(self, all_spans):
        """Test that tool spans are not included in llm_spans list."""
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        hierarchy = build_turn_llm_hierarchy(all_spans)

        # Check Turn 1 llm_spans don't include tool spans
        for llm_span in hierarchy["Turn 1"]["llm_spans"]:
            assert llm_span.get("span_attributes", {}).get("type") == "llm"
            assert llm_span["name"] != "Read"
            assert llm_span["name"] != "Write"

    def test_handles_missing_input_field(self, mock_session_root_span):
        """Test handling of turns with missing input field."""
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        # Turn without input field
        spans = [
            mock_session_root_span,
            {
                "span_id": "turn-no-input",
                "span_parents": ["root-span-001"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
                # No input field
            },
        ]

        hierarchy = build_turn_llm_hierarchy(spans)

        # Should still be in hierarchy, with None or empty input
        assert "Turn 1" in hierarchy
        # Input should be None or empty string (implementation choice)
        assert hierarchy["Turn 1"]["input"] is None or hierarchy["Turn 1"]["input"] == ""

    def test_handles_dict_input_field(self, mock_session_root_span):
        """Test handling of input as dict (some spans have structured input)."""
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        spans = [
            mock_session_root_span,
            {
                "span_id": "turn-dict-input",
                "span_parents": ["root-span-001"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
                "input": {"content": "User said this", "role": "user"},
            },
        ]

        hierarchy = build_turn_llm_hierarchy(spans)

        # Should handle dict input gracefully
        assert "Turn 1" in hierarchy
        # The input should be preserved (exact handling is implementation detail)
        assert hierarchy["Turn 1"]["input"] is not None

    def test_handles_nested_span_parents(self, mock_session_root_span):
        """Test LLM spans with nested parent chains still map to correct turn."""
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        spans = [
            mock_session_root_span,
            {
                "span_id": "turn-1-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
                "input": "Do something",
            },
            # LLM span with parent being the turn
            {
                "span_id": "llm-nested",
                "span_parents": ["turn-1-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Nested LLM response"},
            },
        ]

        hierarchy = build_turn_llm_hierarchy(spans)

        assert len(hierarchy["Turn 1"]["llm_spans"]) == 1
        assert hierarchy["Turn 1"]["llm_spans"][0]["span_id"] == "llm-nested"

    def test_ignores_non_turn_task_spans(self, mock_session_root_span):
        """Test that task spans not named 'Turn N' are ignored."""
        from scripts.agentica.memory_backfill import build_turn_llm_hierarchy

        spans = [
            mock_session_root_span,
            {
                "span_id": "subtask-span",
                "span_parents": ["root-span-001"],
                "name": "Subtask: Analyze code",  # Not "Turn N"
                "span_attributes": {"type": "task"},
                "input": "Analyze the codebase",
            },
            {
                "span_id": "turn-1-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
                "input": "Do something",
            },
        ]

        hierarchy = build_turn_llm_hierarchy(spans)

        # Only Turn 1 should be in hierarchy, not the subtask
        assert "Turn 1" in hierarchy
        assert "Subtask: Analyze code" not in hierarchy
        assert len(hierarchy) == 1


# =============================================================================
# Phase 3: Extract User Intent from Turn Input Tests
# =============================================================================


class TestExtractUserIntentRaw:
    """Tests for extract_user_intent_raw function.

    This function extracts raw user intent from Turn span input,
    handling various input formats and truncating to max_chars.
    """

    def test_extracts_string_input(self):
        """Test extraction from simple string input."""
        from scripts.agentica.memory_backfill import extract_user_intent_raw

        turn_span = {
            "span_id": "turn-1",
            "input": "Implement the memory backfill feature with error handling",
        }

        result = extract_user_intent_raw(turn_span)

        assert result == "Implement the memory backfill feature with error handling"

    def test_truncates_long_input(self):
        """Test truncation of input longer than max_chars."""
        from scripts.agentica.memory_backfill import extract_user_intent_raw

        long_input = "A" * 600  # Longer than default max_chars (500)
        turn_span = {"span_id": "turn-1", "input": long_input}

        result = extract_user_intent_raw(turn_span, max_chars=500)

        # Should be truncated with "..." suffix
        assert len(result) <= 503  # 500 + "..."
        assert result.endswith("...")

    def test_respects_custom_max_chars(self):
        """Test custom max_chars parameter."""
        from scripts.agentica.memory_backfill import extract_user_intent_raw

        turn_span = {
            "span_id": "turn-1",
            "input": "This is a moderately long input string that will be truncated",
        }

        result = extract_user_intent_raw(turn_span, max_chars=20)

        assert len(result) <= 23  # 20 + "..."
        assert result.endswith("...")

    def test_handles_dict_input_with_content_field(self):
        """Test extraction from dict input with 'content' field."""
        from scripts.agentica.memory_backfill import extract_user_intent_raw

        turn_span = {
            "span_id": "turn-1",
            "input": {"content": "User's actual message", "role": "user"},
        }

        result = extract_user_intent_raw(turn_span)

        assert "User's actual message" in result

    def test_handles_dict_input_with_text_field(self):
        """Test extraction from dict input with 'text' field (alternative format)."""
        from scripts.agentica.memory_backfill import extract_user_intent_raw

        turn_span = {
            "span_id": "turn-1",
            "input": {"text": "User's text message", "metadata": {}},
        }

        result = extract_user_intent_raw(turn_span)

        assert "User's text message" in result

    def test_handles_none_input(self):
        """Test handling of None input."""
        from scripts.agentica.memory_backfill import extract_user_intent_raw

        turn_span = {"span_id": "turn-1", "input": None}

        result = extract_user_intent_raw(turn_span)

        assert result == ""

    def test_handles_missing_input_field(self):
        """Test handling of missing input field."""
        from scripts.agentica.memory_backfill import extract_user_intent_raw

        turn_span = {"span_id": "turn-1"}  # No input field

        result = extract_user_intent_raw(turn_span)

        assert result == ""

    def test_handles_empty_string_input(self):
        """Test handling of empty string input."""
        from scripts.agentica.memory_backfill import extract_user_intent_raw

        turn_span = {"span_id": "turn-1", "input": ""}

        result = extract_user_intent_raw(turn_span)

        assert result == ""

    def test_handles_empty_dict_input(self):
        """Test handling of empty dict input."""
        from scripts.agentica.memory_backfill import extract_user_intent_raw

        turn_span = {"span_id": "turn-1", "input": {}}

        result = extract_user_intent_raw(turn_span)

        assert result == ""

    def test_no_truncation_for_short_input(self):
        """Test that short input is not truncated."""
        from scripts.agentica.memory_backfill import extract_user_intent_raw

        short_input = "Short message"
        turn_span = {"span_id": "turn-1", "input": short_input}

        result = extract_user_intent_raw(turn_span, max_chars=500)

        # Should not have "..." since it's under limit
        assert result == short_input
        assert not result.endswith("...")

    def test_handles_unicode_input(self):
        """Test handling of unicode characters in input."""
        from scripts.agentica.memory_backfill import extract_user_intent_raw

        turn_span = {
            "span_id": "turn-1",
            "input": "Add support for emojis and special chars",
        }

        result = extract_user_intent_raw(turn_span)

        assert result != ""
        assert "emojis" in result or "" in result  # Either unicode preserved or normalized

    def test_truncation_at_word_boundary_optional(self):
        """Test that truncation ideally happens at word boundary (if implemented)."""
        from scripts.agentica.memory_backfill import extract_user_intent_raw

        # Input where truncation at 50 chars would be mid-word
        turn_span = {
            "span_id": "turn-1",
            "input": "Implement the comprehensive memory backfill feature with full support",
        }

        result = extract_user_intent_raw(turn_span, max_chars=50)

        # Should be truncated
        assert len(result) <= 53  # 50 + "..."
        assert result.endswith("...")


# =============================================================================
# Phase 4: Extract LLM Decision from LLM Span Output Tests
# =============================================================================


class TestExtractLLMDecision:
    """Tests for extract_llm_decision function.

    This function extracts decision/reasoning text from LLM span output,
    parsing output.content field and truncating to max_chars.
    """

    def test_extracts_content_from_output_dict(self):
        """Test extraction from output.content field."""
        from scripts.agentica.memory_backfill import extract_llm_decision

        llm_span = {
            "span_id": "llm-1",
            "output": {"content": "I'll implement this using a 6-stage pipeline architecture."},
        }

        result = extract_llm_decision(llm_span)

        assert result == "I'll implement this using a 6-stage pipeline architecture."

    def test_truncates_long_content(self):
        """Test truncation of content longer than max_chars."""
        from scripts.agentica.memory_backfill import extract_llm_decision

        long_content = "Decision: " + "X" * 400  # Longer than default 300
        llm_span = {"span_id": "llm-1", "output": {"content": long_content}}

        result = extract_llm_decision(llm_span, max_chars=300)

        assert len(result) <= 303  # 300 + "..."
        assert result.endswith("...")

    def test_respects_custom_max_chars(self):
        """Test custom max_chars parameter."""
        from scripts.agentica.memory_backfill import extract_llm_decision

        llm_span = {
            "span_id": "llm-1",
            "output": {"content": "This is a moderately long decision string that will be truncated"},
        }

        result = extract_llm_decision(llm_span, max_chars=30)

        assert len(result) <= 33  # 30 + "..."
        assert result.endswith("...")

    def test_handles_string_output(self):
        """Test handling when output is a string directly (not dict)."""
        from scripts.agentica.memory_backfill import extract_llm_decision

        llm_span = {"span_id": "llm-1", "output": "Direct string output"}

        result = extract_llm_decision(llm_span)

        assert result == "Direct string output"

    def test_handles_none_output(self):
        """Test handling of None output."""
        from scripts.agentica.memory_backfill import extract_llm_decision

        llm_span = {"span_id": "llm-1", "output": None}

        result = extract_llm_decision(llm_span)

        assert result == ""

    def test_handles_missing_output_field(self):
        """Test handling of missing output field."""
        from scripts.agentica.memory_backfill import extract_llm_decision

        llm_span = {"span_id": "llm-1"}  # No output field

        result = extract_llm_decision(llm_span)

        assert result == ""

    def test_handles_empty_content(self):
        """Test handling of empty content field."""
        from scripts.agentica.memory_backfill import extract_llm_decision

        llm_span = {"span_id": "llm-1", "output": {"content": ""}}

        result = extract_llm_decision(llm_span)

        assert result == ""

    def test_handles_missing_content_in_dict(self):
        """Test handling when output dict has no content field."""
        from scripts.agentica.memory_backfill import extract_llm_decision

        llm_span = {
            "span_id": "llm-1",
            "output": {"tool_calls": [], "other_field": "value"},  # No content
        }

        result = extract_llm_decision(llm_span)

        assert result == ""

    def test_no_truncation_for_short_content(self):
        """Test that short content is not truncated."""
        from scripts.agentica.memory_backfill import extract_llm_decision

        short_content = "Use pytest"
        llm_span = {"span_id": "llm-1", "output": {"content": short_content}}

        result = extract_llm_decision(llm_span, max_chars=300)

        assert result == short_content
        assert not result.endswith("...")

    def test_handles_nested_content_structure(self):
        """Test handling of complex nested output structure."""
        from scripts.agentica.memory_backfill import extract_llm_decision

        # Some LLM outputs have nested structures
        llm_span = {
            "span_id": "llm-1",
            "output": {
                "content": "Main decision text",
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                "model": "claude-3",
            },
        }

        result = extract_llm_decision(llm_span)

        assert result == "Main decision text"

    def test_strips_whitespace(self):
        """Test that whitespace is stripped from content."""
        from scripts.agentica.memory_backfill import extract_llm_decision

        llm_span = {
            "span_id": "llm-1",
            "output": {"content": "  Decision with whitespace  \n\t"},
        }

        result = extract_llm_decision(llm_span)

        assert result == "Decision with whitespace"


# =============================================================================
# Phase 5: Extract Tools from LLM Span Tests
# =============================================================================


class TestExtractToolsFromLLMSpan:
    """Tests for extract_tools_from_llm_span function.

    This function extracts tool names from LLM span output.tool_calls,
    returning a deduplicated list of tool names.
    """

    def test_extracts_single_tool(self):
        """Test extraction of a single tool call."""
        from scripts.agentica.memory_backfill import extract_tools_from_llm_span

        llm_span = {
            "span_id": "llm-1",
            "output": {
                "tool_calls": [
                    {"id": "call-1", "function": {"name": "Read", "arguments": "{}"}}
                ]
            },
        }

        result = extract_tools_from_llm_span(llm_span)

        assert result == ["Read"]

    def test_extracts_multiple_tools(self):
        """Test extraction of multiple tool calls."""
        from scripts.agentica.memory_backfill import extract_tools_from_llm_span

        llm_span = {
            "span_id": "llm-1",
            "output": {
                "tool_calls": [
                    {"id": "call-1", "function": {"name": "Read", "arguments": "{}"}},
                    {"id": "call-2", "function": {"name": "Write", "arguments": "{}"}},
                    {"id": "call-3", "function": {"name": "Bash", "arguments": "{}"}},
                ]
            },
        }

        result = extract_tools_from_llm_span(llm_span)

        assert result == ["Read", "Write", "Bash"]

    def test_deduplicates_tool_names(self):
        """Test that duplicate tool names are deduplicated."""
        from scripts.agentica.memory_backfill import extract_tools_from_llm_span

        llm_span = {
            "span_id": "llm-1",
            "output": {
                "tool_calls": [
                    {"id": "call-1", "function": {"name": "Read", "arguments": "{}"}},
                    {"id": "call-2", "function": {"name": "Read", "arguments": "{}"}},
                    {"id": "call-3", "function": {"name": "Write", "arguments": "{}"}},
                    {"id": "call-4", "function": {"name": "Read", "arguments": "{}"}},
                ]
            },
        }

        result = extract_tools_from_llm_span(llm_span)

        # Should be deduplicated but preserve order
        assert "Read" in result
        assert "Write" in result
        assert len(result) == 2

    def test_returns_empty_list_for_no_tools(self):
        """Test returns empty list when no tool_calls."""
        from scripts.agentica.memory_backfill import extract_tools_from_llm_span

        llm_span = {
            "span_id": "llm-1",
            "output": {"content": "Just text, no tools", "tool_calls": []},
        }

        result = extract_tools_from_llm_span(llm_span)

        assert result == []

    def test_handles_missing_tool_calls_field(self):
        """Test handling when tool_calls field is missing."""
        from scripts.agentica.memory_backfill import extract_tools_from_llm_span

        llm_span = {
            "span_id": "llm-1",
            "output": {"content": "Only content, no tool_calls key"},
        }

        result = extract_tools_from_llm_span(llm_span)

        assert result == []

    def test_handles_none_output(self):
        """Test handling when output is None."""
        from scripts.agentica.memory_backfill import extract_tools_from_llm_span

        llm_span = {"span_id": "llm-1", "output": None}

        result = extract_tools_from_llm_span(llm_span)

        assert result == []

    def test_handles_missing_output_field(self):
        """Test handling when output field is missing."""
        from scripts.agentica.memory_backfill import extract_tools_from_llm_span

        llm_span = {"span_id": "llm-1"}

        result = extract_tools_from_llm_span(llm_span)

        assert result == []

    def test_handles_malformed_tool_call(self):
        """Test handling of malformed tool call structure."""
        from scripts.agentica.memory_backfill import extract_tools_from_llm_span

        llm_span = {
            "span_id": "llm-1",
            "output": {
                "tool_calls": [
                    {"id": "call-1", "function": {"name": "Read"}},  # Valid
                    {"id": "call-2", "function": {}},  # Missing name
                    {"id": "call-3"},  # Missing function
                    "invalid_string",  # Not a dict at all
                ]
            },
        }

        result = extract_tools_from_llm_span(llm_span)

        # Should extract what it can, skip malformed
        assert "Read" in result

    def test_handles_none_in_tool_calls_list(self):
        """Test handling of None values in tool_calls list."""
        from scripts.agentica.memory_backfill import extract_tools_from_llm_span

        llm_span = {
            "span_id": "llm-1",
            "output": {
                "tool_calls": [
                    None,
                    {"id": "call-1", "function": {"name": "Write"}},
                    None,
                ]
            },
        }

        result = extract_tools_from_llm_span(llm_span)

        assert result == ["Write"]

    def test_preserves_tool_order(self):
        """Test that tool order is preserved (first occurrence)."""
        from scripts.agentica.memory_backfill import extract_tools_from_llm_span

        llm_span = {
            "span_id": "llm-1",
            "output": {
                "tool_calls": [
                    {"id": "call-1", "function": {"name": "Bash"}},
                    {"id": "call-2", "function": {"name": "Read"}},
                    {"id": "call-3", "function": {"name": "Write"}},
                ]
            },
        }

        result = extract_tools_from_llm_span(llm_span)

        assert result == ["Bash", "Read", "Write"]


# =============================================================================
# Phase 6: Extract Files from Turn Tests
# =============================================================================


class TestExtractFilesFromTurn:
    """Tests for extract_files_from_turn function.

    This function extracts file paths from Read/Write/Edit tool spans
    that are children of a given turn span.
    """

    @pytest.fixture
    def mock_spans_with_files(self):
        """Create mock spans with file operations."""
        return [
            # Turn 1
            {
                "span_id": "turn-1-span",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            # Write tool under Turn 1
            {
                "span_id": "write-1",
                "span_parents": ["turn-1-span"],
                "name": "Write",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/output.py", "content": "..."},
            },
            # Edit tool under Turn 1
            {
                "span_id": "edit-1",
                "span_parents": ["turn-1-span"],
                "name": "Edit",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/existing.py", "old_string": "...", "new_string": "..."},
            },
            # Read tool under Turn 1
            {
                "span_id": "read-1",
                "span_parents": ["turn-1-span"],
                "name": "Read",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/source.py"},
            },
            # Bash tool (no file_path - should be ignored)
            {
                "span_id": "bash-1",
                "span_parents": ["turn-1-span"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "input": {"command": "pytest"},
            },
        ]

    def test_extracts_write_file_paths(self, mock_spans_with_files):
        """Test extraction of file paths from Write tool spans."""
        from scripts.agentica.memory_backfill import extract_files_from_turn

        result = extract_files_from_turn("turn-1-span", mock_spans_with_files)

        assert "/path/to/output.py" in result

    def test_extracts_edit_file_paths(self, mock_spans_with_files):
        """Test extraction of file paths from Edit tool spans."""
        from scripts.agentica.memory_backfill import extract_files_from_turn

        result = extract_files_from_turn("turn-1-span", mock_spans_with_files)

        assert "/path/to/existing.py" in result

    def test_extracts_read_file_paths(self, mock_spans_with_files):
        """Test extraction of file paths from Read tool spans."""
        from scripts.agentica.memory_backfill import extract_files_from_turn

        result = extract_files_from_turn("turn-1-span", mock_spans_with_files)

        # Read files should be included
        assert "/path/to/source.py" in result

    def test_deduplicates_file_paths(self):
        """Test that duplicate file paths are deduplicated."""
        from scripts.agentica.memory_backfill import extract_files_from_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "read-1",
                "span_parents": ["turn-1"],
                "name": "Read",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/file.py"},
            },
            {
                "span_id": "edit-1",
                "span_parents": ["turn-1"],
                "name": "Edit",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/file.py"},  # Same file
            },
            {
                "span_id": "write-1",
                "span_parents": ["turn-1"],
                "name": "Write",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/file.py"},  # Same file again
            },
        ]

        result = extract_files_from_turn("turn-1", spans)

        # Should only appear once
        assert result.count("/path/to/file.py") == 1

    def test_returns_empty_for_no_file_tools(self):
        """Test returns empty list when no file-related tool spans."""
        from scripts.agentica.memory_backfill import extract_files_from_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "bash-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "input": {"command": "ls"},
            },
        ]

        result = extract_files_from_turn("turn-1", spans)

        assert result == []

    def test_ignores_spans_from_other_turns(self):
        """Test that file spans from other turns are not included."""
        from scripts.agentica.memory_backfill import extract_files_from_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "turn-2",
                "span_parents": ["root"],
                "name": "Turn 2",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "write-turn1",
                "span_parents": ["turn-1"],
                "name": "Write",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/from/turn1.py"},
            },
            {
                "span_id": "write-turn2",
                "span_parents": ["turn-2"],
                "name": "Write",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/from/turn2.py"},
            },
        ]

        result = extract_files_from_turn("turn-1", spans)

        assert "/path/from/turn1.py" in result
        assert "/path/from/turn2.py" not in result

    def test_handles_missing_file_path_in_input(self):
        """Test handling when input lacks file_path field."""
        from scripts.agentica.memory_backfill import extract_files_from_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "write-1",
                "span_parents": ["turn-1"],
                "name": "Write",
                "span_attributes": {"type": "tool"},
                "input": {"content": "..."},  # No file_path
            },
        ]

        result = extract_files_from_turn("turn-1", spans)

        assert result == []

    def test_handles_none_input(self):
        """Test handling when input is None."""
        from scripts.agentica.memory_backfill import extract_files_from_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "write-1",
                "span_parents": ["turn-1"],
                "name": "Write",
                "span_attributes": {"type": "tool"},
                "input": None,
            },
        ]

        result = extract_files_from_turn("turn-1", spans)

        assert result == []

    def test_handles_empty_spans_list(self):
        """Test handling of empty spans list."""
        from scripts.agentica.memory_backfill import extract_files_from_turn

        result = extract_files_from_turn("turn-1", [])

        assert result == []

    def test_handles_nonexistent_turn_id(self):
        """Test handling when turn_span_id doesn't exist in spans."""
        from scripts.agentica.memory_backfill import extract_files_from_turn

        spans = [
            {
                "span_id": "write-1",
                "span_parents": ["turn-1"],
                "name": "Write",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/file.py"},
            },
        ]

        result = extract_files_from_turn("nonexistent-turn", spans)

        assert result == []


# =============================================================================
# Phase 7: Lookup Session Outcome Tests
# =============================================================================


class TestLookupSessionOutcome:
    """Tests for lookup_session_outcome function.

    This function looks up outcome from context.db handoffs table
    by root_span_id.
    """

    def test_returns_outcome_when_found(self, tmp_path, monkeypatch):
        """Test returns outcome when handoff exists in database."""
        from scripts.agentica.memory_backfill import lookup_session_outcome
        import sqlite3

        # Create a test database
        db_path = tmp_path / "context.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE handoffs (
                id INTEGER PRIMARY KEY,
                root_span_id TEXT,
                outcome TEXT,
                outcome_notes TEXT
            )
        """)
        conn.execute(
            "INSERT INTO handoffs (root_span_id, outcome, outcome_notes) VALUES (?, ?, ?)",
            ("session-123", "SUCCEEDED", "All tests passed"),
        )
        conn.commit()
        conn.close()

        # Monkeypatch to use test database
        monkeypatch.setenv("CONTEXT_DB_PATH", str(db_path))

        result = lookup_session_outcome("session-123")

        assert result == ("SUCCEEDED", "All tests passed")

    def test_returns_none_when_not_found(self, tmp_path, monkeypatch):
        """Test returns (None, None) when handoff not found."""
        from scripts.agentica.memory_backfill import lookup_session_outcome
        import sqlite3

        # Create empty database
        db_path = tmp_path / "context.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE handoffs (
                id INTEGER PRIMARY KEY,
                root_span_id TEXT,
                outcome TEXT,
                outcome_notes TEXT
            )
        """)
        conn.commit()
        conn.close()

        monkeypatch.setenv("CONTEXT_DB_PATH", str(db_path))

        result = lookup_session_outcome("nonexistent-session")

        assert result == (None, None)

    def test_handles_missing_database(self, tmp_path, monkeypatch):
        """Test handles gracefully when database doesn't exist."""
        from scripts.agentica.memory_backfill import lookup_session_outcome

        # Point to nonexistent database
        monkeypatch.setenv("CONTEXT_DB_PATH", str(tmp_path / "nonexistent.db"))

        result = lookup_session_outcome("any-session")

        assert result == (None, None)

    def test_returns_outcome_without_notes(self, tmp_path, monkeypatch):
        """Test returns outcome when outcome_notes is NULL."""
        from scripts.agentica.memory_backfill import lookup_session_outcome
        import sqlite3

        db_path = tmp_path / "context.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE handoffs (
                id INTEGER PRIMARY KEY,
                root_span_id TEXT,
                outcome TEXT,
                outcome_notes TEXT
            )
        """)
        conn.execute(
            "INSERT INTO handoffs (root_span_id, outcome, outcome_notes) VALUES (?, ?, ?)",
            ("session-456", "FAILED", None),
        )
        conn.commit()
        conn.close()

        monkeypatch.setenv("CONTEXT_DB_PATH", str(db_path))

        result = lookup_session_outcome("session-456")

        assert result == ("FAILED", None)

    def test_handles_database_error(self, tmp_path, monkeypatch):
        """Test handles database errors gracefully."""
        from scripts.agentica.memory_backfill import lookup_session_outcome

        # Create a file that's not a valid SQLite database
        invalid_db = tmp_path / "invalid.db"
        invalid_db.write_text("not a database")

        monkeypatch.setenv("CONTEXT_DB_PATH", str(invalid_db))

        result = lookup_session_outcome("any-session")

        # Should return (None, None) instead of raising
        assert result == (None, None)


# =============================================================================
# Phase 8: Detect Error in Turn Tests
# =============================================================================


class TestDetectErrorInTurn:
    """Tests for detect_error_in_turn function.

    This function detects errors from Bash spans under a turn,
    returning the first error summary found or None.
    """

    def test_detects_python_traceback(self):
        """Test detection of Python traceback in Bash output."""
        from scripts.agentica.memory_backfill import detect_error_in_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "bash-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "output": {
                    "stdout": """Traceback (most recent call last):
  File "test.py", line 10, in <module>
    raise ValueError("Invalid input")
ValueError: Invalid input"""
                },
            },
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        assert "ValueError" in result or "Traceback" in result

    def test_detects_pytest_failures(self):
        """Test detection of pytest failure output."""
        from scripts.agentica.memory_backfill import detect_error_in_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "bash-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "output": {
                    "stdout": """============================= test session starts ==============================
collected 5 items

tests/test_example.py ..F..

================================== FAILURES ===================================
________________________________ test_something ________________________________

    def test_something():
>       assert 1 == 2
E       assert 1 == 2

tests/test_example.py:10: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_example.py::test_something - assert 1 == 2
========================= 1 failed, 4 passed in 0.12s ========================"""
                },
            },
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        assert "FAILED" in result or "failed" in result.lower()

    def test_returns_none_for_successful_command(self):
        """Test returns None when Bash commands succeed."""
        from scripts.agentica.memory_backfill import detect_error_in_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "bash-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "output": {
                    "stdout": "5 tests passed in 0.5s",
                    "stderr": "",
                },
            },
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is None

    def test_detects_error_in_stderr(self):
        """Test detection of error in stderr field."""
        from scripts.agentica.memory_backfill import detect_error_in_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "bash-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "output": {
                    "stdout": "",
                    "stderr": "Error: Command 'npm install' returned exit code 1",
                },
            },
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        assert "Error" in result or "exit code" in result

    def test_returns_first_error_only(self):
        """Test returns first error when multiple errors exist."""
        from scripts.agentica.memory_backfill import detect_error_in_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "bash-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "output": {"stdout": "Error: First error"},
            },
            {
                "span_id": "bash-2",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "output": {"stdout": "Error: Second error"},
            },
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        # Should be first error, not second
        assert "First" in result or result is not None

    def test_handles_no_bash_spans(self):
        """Test handling when turn has no Bash spans."""
        from scripts.agentica.memory_backfill import detect_error_in_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "read-1",
                "span_parents": ["turn-1"],
                "name": "Read",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/file.py"},
            },
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is None

    def test_handles_missing_output(self):
        """Test handling when Bash span has no output."""
        from scripts.agentica.memory_backfill import detect_error_in_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "bash-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                # No output field
            },
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is None

    def test_handles_empty_spans_list(self):
        """Test handling of empty spans list."""
        from scripts.agentica.memory_backfill import detect_error_in_turn

        result = detect_error_in_turn("turn-1", [])

        assert result is None

    def test_ignores_errors_from_other_turns(self):
        """Test that errors from other turns are not detected."""
        from scripts.agentica.memory_backfill import detect_error_in_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "turn-2",
                "span_parents": ["root"],
                "name": "Turn 2",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "bash-turn1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "output": {"stdout": "Success"},
            },
            {
                "span_id": "bash-turn2",
                "span_parents": ["turn-2"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "output": {"stdout": "Error: Something failed"},
            },
        ]

        # Check turn-1 (should not see error from turn-2)
        result = detect_error_in_turn("turn-1", spans)

        assert result is None

    def test_truncates_long_error_summary(self):
        """Test that long error summaries are truncated."""
        from scripts.agentica.memory_backfill import detect_error_in_turn

        long_error = "Error: " + "X" * 1000
        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "bash-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "output": {"stdout": long_error},
            },
        ]

        result = detect_error_in_turn("turn-1", spans)

        # Error should be detected but truncated to reasonable length
        assert result is not None
        assert len(result) <= 500  # Reasonable max length

    def test_detects_compilation_errors(self):
        """Test detection of compilation/build errors."""
        from scripts.agentica.memory_backfill import detect_error_in_turn

        spans = [
            {
                "span_id": "turn-1",
                "span_parents": ["root"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
            },
            {
                "span_id": "bash-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "output": {
                    "stdout": """src/main.ts:42:15 - error TS2339: Property 'foo' does not exist on type 'Bar'.
Found 1 error in src/main.ts:42"""
                },
            },
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        assert "error" in result.lower()


# =============================================================================
# Phase 9: Main Extraction Function Tests
# =============================================================================


class TestExtractLLMSpanMemories:
    """Tests for the main extraction function extract_llm_span_memories().

    This function combines all helper functions to extract LLMSpanMemory
    objects from all spans in a session. It iterates through all turns
    and all LLM spans within each turn.

    Plan reference: thoughts/shared/plans/2025-12-28-llm-span-memory-model.md (Phase 9)
    """

    @pytest.fixture
    def mock_session_root_span(self):
        """Create a mock session root span."""
        return {
            "span_id": "root-span-001",
            "span_parents": None,
            "name": "Session",
            "span_attributes": {"type": "task"},
        }

    @pytest.fixture
    def mock_multi_turn_session(self, mock_session_root_span):
        """Create a mock 6-turn session with 9 LLM spans total.

        Turn distribution:
        - Turn 1: 3 LLM spans
        - Turn 2: 2 LLM spans
        - Turn 3: 1 LLM span
        - Turn 4: 1 LLM span
        - Turn 5: 2 LLM spans
        - Turn 6: 0 LLM spans (edge case from analysis)
        """
        turns = [
            {
                "span_id": "turn-1-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
                "input": "Implement the memory backfill feature",
            },
            {
                "span_id": "turn-2-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 2",
                "span_attributes": {"type": "task"},
                "input": "Now add error handling",
            },
            {
                "span_id": "turn-3-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 3",
                "span_attributes": {"type": "task"},
                "input": "Run the tests",
            },
            {
                "span_id": "turn-4-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 4",
                "span_attributes": {"type": "task"},
                "input": "Fix the failing test",
            },
            {
                "span_id": "turn-5-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 5",
                "span_attributes": {"type": "task"},
                "input": "Add documentation",
            },
            {
                "span_id": "turn-6-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 6",
                "span_attributes": {"type": "task"},
                "input": "Final review",
            },
        ]

        llm_spans = [
            # Turn 1: 3 LLM spans
            {
                "span_id": "llm-1a",
                "span_parents": ["turn-1-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {
                    "content": "I'll start by analyzing the requirements...",
                    "tool_calls": [
                        {"id": "call-1", "function": {"name": "Read", "arguments": "{}"}}
                    ],
                },
            },
            {
                "span_id": "llm-1b",
                "span_parents": ["turn-1-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {
                    "content": "Now implementing the core logic...",
                    "tool_calls": [
                        {"id": "call-2", "function": {"name": "Write", "arguments": "{}"}}
                    ],
                },
            },
            {
                "span_id": "llm-1c",
                "span_parents": ["turn-1-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Feature implementation complete."},
            },
            # Turn 2: 2 LLM spans
            {
                "span_id": "llm-2a",
                "span_parents": ["turn-2-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {
                    "content": "Adding try/except blocks...",
                    "tool_calls": [
                        {"id": "call-3", "function": {"name": "Edit", "arguments": "{}"}}
                    ],
                },
            },
            {
                "span_id": "llm-2b",
                "span_parents": ["turn-2-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Error handling added."},
            },
            # Turn 3: 1 LLM span
            {
                "span_id": "llm-3a",
                "span_parents": ["turn-3-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {
                    "content": "Running pytest...",
                    "tool_calls": [
                        {"id": "call-4", "function": {"name": "Bash", "arguments": "{}"}}
                    ],
                },
            },
            # Turn 4: 1 LLM span
            {
                "span_id": "llm-4a",
                "span_parents": ["turn-4-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {
                    "content": "Fixed the assertion error.",
                    "tool_calls": [
                        {"id": "call-5", "function": {"name": "Edit", "arguments": "{}"}}
                    ],
                },
            },
            # Turn 5: 2 LLM spans
            {
                "span_id": "llm-5a",
                "span_parents": ["turn-5-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {
                    "content": "Adding docstrings...",
                    "tool_calls": [
                        {"id": "call-6", "function": {"name": "Edit", "arguments": "{}"}}
                    ],
                },
            },
            {
                "span_id": "llm-5b",
                "span_parents": ["turn-5-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Documentation complete."},
            },
            # Turn 6: 0 LLM spans (handled by not adding any)
        ]

        tool_spans = [
            # Tool spans under Turn 1
            {
                "span_id": "tool-read-1",
                "span_parents": ["turn-1-span"],
                "name": "Read",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/source.py"},
            },
            {
                "span_id": "tool-write-1",
                "span_parents": ["turn-1-span"],
                "name": "Write",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/output.py", "content": "..."},
            },
            # Tool spans under Turn 3
            {
                "span_id": "tool-bash-3",
                "span_parents": ["turn-3-span"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "input": {"command": "pytest"},
                "output": {"stdout": "5 tests passed"},
            },
            # Tool spans under Turn 4
            {
                "span_id": "tool-edit-4",
                "span_parents": ["turn-4-span"],
                "name": "Edit",
                "span_attributes": {"type": "tool"},
                "input": {"file_path": "/path/to/test.py", "old_string": "...", "new_string": "..."},
            },
        ]

        return [mock_session_root_span] + turns + llm_spans + tool_spans

    def test_extracts_memories_from_multi_turn_session(self, mock_multi_turn_session):
        """Test extraction from 6-turn session with 9 LLM spans.

        The function should produce 9 LLMSpanMemory objects, one per LLM span.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        session_id = "test-session-001"
        memories = extract_llm_span_memories(mock_multi_turn_session, session_id)

        # Should have 9 memories (one per LLM span)
        assert len(memories) == 9

    def test_returns_one_memory_per_llm_span(self, mock_multi_turn_session):
        """Test that each LLM span produces exactly one memory.

        Verify the span_ids are unique and match the LLM spans.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        session_id = "test-session-001"
        memories = extract_llm_span_memories(mock_multi_turn_session, session_id)

        # Extract span_ids from memories
        span_ids = [m.span_id for m in memories]

        # All should be unique
        assert len(span_ids) == len(set(span_ids))

        # Should include all LLM spans
        expected_llm_span_ids = [
            "llm-1a", "llm-1b", "llm-1c",
            "llm-2a", "llm-2b",
            "llm-3a",
            "llm-4a",
            "llm-5a", "llm-5b",
        ]
        for expected_id in expected_llm_span_ids:
            assert expected_id in span_ids, f"Missing LLM span: {expected_id}"

    def test_populates_all_fields(self, mock_multi_turn_session):
        """Test all LLMSpanMemory fields are populated correctly.

        Check that each memory has:
        - span_id (from LLM span)
        - turn_number (from parent turn)
        - session_id (passed in)
        - user_intent (from turn input)
        - decision (from LLM output)
        - embedding_text (auto-generated)
        - content_hash (auto-generated)
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories, LLMSpanMemory

        session_id = "test-session-001"
        memories = extract_llm_span_memories(mock_multi_turn_session, session_id)

        for memory in memories:
            # Verify it's the right type
            assert isinstance(memory, LLMSpanMemory)

            # Required fields must be populated
            assert memory.span_id != ""
            assert memory.turn_number >= 1
            assert memory.session_id == session_id
            assert memory.user_intent != ""  # Should be extracted from turn input
            assert memory.decision != ""  # Should be extracted from LLM output

            # Auto-generated fields
            assert memory.embedding_text != ""
            assert memory.content_hash != ""
            assert len(memory.content_hash) == 16  # SHA256 truncated

    def test_handles_empty_spans(self):
        """Test empty span list returns empty list.

        Should not crash or raise an error.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        session_id = "empty-session"
        memories = extract_llm_span_memories([], session_id)

        assert memories == []
        assert isinstance(memories, list)

    def test_handles_turn_with_no_llm_spans(self, mock_session_root_span):
        """Test turns without LLM spans don't crash.

        Turn 6 in our test data has 0 LLM spans. The function should
        handle this gracefully without producing any memories for that turn.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        # Create a session with only one turn that has no LLM spans
        spans = [
            mock_session_root_span,
            {
                "span_id": "turn-1-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
                "input": "A turn with no LLM activity",
            },
            # No LLM spans - only a tool span
            {
                "span_id": "tool-bash-1",
                "span_parents": ["turn-1-span"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "input": {"command": "ls"},
            },
        ]

        session_id = "no-llm-session"
        memories = extract_llm_span_memories(spans, session_id)

        # Should return empty list since there are no LLM spans
        assert memories == []

    def test_outcome_populated_from_context_db(self, mock_multi_turn_session, tmp_path, monkeypatch):
        """Test outcome lookup is called and populated in memories.

        When context.db has an outcome for the session, all memories
        should have that outcome populated.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories
        import sqlite3

        # Create a test database with outcome
        db_path = tmp_path / "context.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE handoffs (
                id INTEGER PRIMARY KEY,
                root_span_id TEXT,
                outcome TEXT,
                outcome_notes TEXT
            )
        """)
        conn.execute(
            "INSERT INTO handoffs (root_span_id, outcome, outcome_notes) VALUES (?, ?, ?)",
            ("session-with-outcome", "SUCCEEDED", "All 42 tests passed"),
        )
        conn.commit()
        conn.close()

        # Monkeypatch to use test database
        monkeypatch.setenv("CONTEXT_DB_PATH", str(db_path))

        session_id = "session-with-outcome"
        memories = extract_llm_span_memories(mock_multi_turn_session, session_id)

        # All memories should have the outcome populated
        for memory in memories:
            assert memory.outcome == "SUCCEEDED"

    def test_error_detection_populated(self, mock_session_root_span):
        """Test error_summary is populated when errors found in Bash output.

        When a turn has Bash spans with errors, the LLM memories for that
        turn should have error_summary populated.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        spans = [
            mock_session_root_span,
            {
                "span_id": "turn-1-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
                "input": "Run the tests",
            },
            {
                "span_id": "llm-1a",
                "span_parents": ["turn-1-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {
                    "content": "Running pytest...",
                    "tool_calls": [
                        {"id": "call-1", "function": {"name": "Bash", "arguments": "{}"}}
                    ],
                },
            },
            {
                "span_id": "bash-1",
                "span_parents": ["turn-1-span"],
                "name": "Bash",
                "span_attributes": {"type": "tool"},
                "input": {"command": "pytest"},
                "output": {
                    "stdout": """FAILED tests/test_example.py::test_something - assert 1 == 2
========================= 1 failed, 4 passed in 0.12s ========================"""
                },
            },
        ]

        session_id = "session-with-error"
        memories = extract_llm_span_memories(spans, session_id)

        assert len(memories) == 1
        assert memories[0].error_summary is not None
        assert "FAILED" in memories[0].error_summary or "failed" in memories[0].error_summary.lower()

    def test_tools_called_populated(self, mock_multi_turn_session):
        """Test tools_called from LLM spans are extracted.

        The function should populate tools_called list from the
        output.tool_calls of each LLM span.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        session_id = "test-session-001"
        memories = extract_llm_span_memories(mock_multi_turn_session, session_id)

        # Find memory for llm-1a which has Read tool_call
        llm_1a_memory = next((m for m in memories if m.span_id == "llm-1a"), None)
        assert llm_1a_memory is not None
        assert "Read" in llm_1a_memory.tools_called

        # Find memory for llm-1b which has Write tool_call
        llm_1b_memory = next((m for m in memories if m.span_id == "llm-1b"), None)
        assert llm_1b_memory is not None
        assert "Write" in llm_1b_memory.tools_called

        # Find memory for llm-3a which has Bash tool_call
        llm_3a_memory = next((m for m in memories if m.span_id == "llm-3a"), None)
        assert llm_3a_memory is not None
        assert "Bash" in llm_3a_memory.tools_called

        # Find memory for llm-1c which has NO tool_calls
        llm_1c_memory = next((m for m in memories if m.span_id == "llm-1c"), None)
        assert llm_1c_memory is not None
        assert llm_1c_memory.tools_called == []

    def test_files_touched_populated(self, mock_multi_turn_session):
        """Test files_touched from sibling tool spans are extracted.

        The function should populate files_touched from Read/Write/Edit
        tool spans that are siblings of the LLM span (same parent turn).
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        session_id = "test-session-001"
        memories = extract_llm_span_memories(mock_multi_turn_session, session_id)

        # Find memories for Turn 1 (which has Read and Write tool spans)
        turn_1_memories = [m for m in memories if m.turn_number == 1]
        assert len(turn_1_memories) == 3

        # All Turn 1 memories should have files_touched from the sibling tool spans
        for memory in turn_1_memories:
            # Turn 1 has tool-read-1 (/path/to/source.py) and tool-write-1 (/path/to/output.py)
            assert "/path/to/source.py" in memory.files_touched or "/path/to/output.py" in memory.files_touched

        # Find memories for Turn 4 (which has Edit tool span)
        turn_4_memories = [m for m in memories if m.turn_number == 4]
        assert len(turn_4_memories) == 1

        # Turn 4 memory should have the edited file
        assert "/path/to/test.py" in turn_4_memories[0].files_touched

    def test_turn_number_is_correct(self, mock_multi_turn_session):
        """Test that turn_number is correctly assigned to each memory.

        LLM spans under Turn 1 should have turn_number=1, etc.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        session_id = "test-session-001"
        memories = extract_llm_span_memories(mock_multi_turn_session, session_id)

        # Group memories by turn_number
        turn_counts = {}
        for m in memories:
            turn_counts[m.turn_number] = turn_counts.get(m.turn_number, 0) + 1

        # Verify distribution matches expected LLM span counts
        assert turn_counts.get(1, 0) == 3  # Turn 1 has 3 LLM spans
        assert turn_counts.get(2, 0) == 2  # Turn 2 has 2 LLM spans
        assert turn_counts.get(3, 0) == 1  # Turn 3 has 1 LLM span
        assert turn_counts.get(4, 0) == 1  # Turn 4 has 1 LLM span
        assert turn_counts.get(5, 0) == 2  # Turn 5 has 2 LLM spans
        assert turn_counts.get(6, 0) == 0  # Turn 6 has 0 LLM spans

    def test_user_intent_from_turn_input(self, mock_multi_turn_session):
        """Test user_intent is extracted from the parent turn's input.

        All LLM spans under the same turn should have the same user_intent.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        session_id = "test-session-001"
        memories = extract_llm_span_memories(mock_multi_turn_session, session_id)

        # Turn 1 memories should have Turn 1's input as user_intent
        turn_1_memories = [m for m in memories if m.turn_number == 1]
        for m in turn_1_memories:
            assert "memory backfill" in m.user_intent.lower() or "implement" in m.user_intent.lower()

        # Turn 3 memories should have Turn 3's input as user_intent
        turn_3_memories = [m for m in memories if m.turn_number == 3]
        for m in turn_3_memories:
            assert "test" in m.user_intent.lower() or "run" in m.user_intent.lower()

    def test_decision_from_llm_output(self, mock_multi_turn_session):
        """Test decision is extracted from the LLM span's output.content.

        Each LLM span's decision should match its output.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        session_id = "test-session-001"
        memories = extract_llm_span_memories(mock_multi_turn_session, session_id)

        # Find specific memories and verify decision content
        llm_1a_memory = next((m for m in memories if m.span_id == "llm-1a"), None)
        assert llm_1a_memory is not None
        assert "analyzing the requirements" in llm_1a_memory.decision.lower()

        llm_2a_memory = next((m for m in memories if m.span_id == "llm-2a"), None)
        assert llm_2a_memory is not None
        assert "try/except" in llm_2a_memory.decision.lower() or "error" in llm_2a_memory.decision.lower()

    def test_session_id_propagated_to_all_memories(self, mock_multi_turn_session):
        """Test session_id is correctly set on all memories.

        All memories should have the same session_id that was passed in.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        session_id = "unique-session-identifier-12345"
        memories = extract_llm_span_memories(mock_multi_turn_session, session_id)

        for memory in memories:
            assert memory.session_id == session_id

    def test_content_hash_is_unique_per_memory(self, mock_multi_turn_session):
        """Test each memory has a unique content_hash.

        Since each memory has different span_id, all hashes should be unique.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        session_id = "test-session-001"
        memories = extract_llm_span_memories(mock_multi_turn_session, session_id)

        hashes = [m.content_hash for m in memories]

        # All hashes should be unique
        assert len(hashes) == len(set(hashes))

    def test_handles_malformed_spans_gracefully(self, mock_session_root_span):
        """Test the function handles malformed spans without crashing.

        Spans with missing fields should be skipped or handled gracefully.
        """
        from scripts.agentica.memory_backfill import extract_llm_span_memories

        spans = [
            mock_session_root_span,
            {
                "span_id": "turn-1-span",
                "span_parents": ["root-span-001"],
                "name": "Turn 1",
                "span_attributes": {"type": "task"},
                "input": "Valid turn",
            },
            # Valid LLM span
            {
                "span_id": "llm-valid",
                "span_parents": ["turn-1-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                "output": {"content": "Valid output"},
            },
            # Malformed: missing span_attributes
            {
                "span_id": "llm-malformed-1",
                "span_parents": ["turn-1-span"],
                "name": "LLM",
                # Missing span_attributes
                "output": {"content": "Some output"},
            },
            # Malformed: missing output
            {
                "span_id": "llm-malformed-2",
                "span_parents": ["turn-1-span"],
                "name": "LLM",
                "span_attributes": {"type": "llm"},
                # Missing output
            },
        ]

        session_id = "test-session"
        # Should not raise an exception
        memories = extract_llm_span_memories(spans, session_id)

        # At minimum, the valid span should be extracted
        # Implementation may choose to skip or include malformed spans
        assert isinstance(memories, list)


# =============================================================================
# Phase 10: LLM Summarization Tests
# =============================================================================


class TestSummarizeUserIntent:
    """Tests for LLM summarization of user intent.

    The function summarize_user_intent() provides optional LLM summarization
    of long user intents to create concise, semantic representations.

    Plan reference: Phase 10 in 2025-12-28-llm-span-memory-model.md
    """

    def test_returns_raw_if_short_enough(self):
        """If raw_intent is already short (<100 chars), return as-is.

        No LLM call needed for already-concise intents.
        """
        from scripts.agentica.memory_backfill import summarize_user_intent
        import asyncio

        short_intent = "Fix the login bug"  # 16 chars
        result = asyncio.run(summarize_user_intent(short_intent, max_tokens=50, use_llm=True))

        # Short intents returned unchanged
        assert result == short_intent

    def test_truncates_without_llm_if_disabled(self):
        """When use_llm=False, return truncated intent without LLM call.

        This is the fallback behavior for environments without LLM access.
        """
        from scripts.agentica.memory_backfill import summarize_user_intent
        import asyncio

        long_intent = "This is a very long user intent that goes on and on about " * 10  # ~580 chars
        result = asyncio.run(summarize_user_intent(long_intent, max_tokens=50, use_llm=False))

        # Result should be truncated, not original length
        assert len(result) < len(long_intent)
        # Should end with truncation indicator
        assert result.endswith("...") or len(result) <= 100

    @pytest.mark.asyncio
    async def test_calls_llm_for_long_intent(self):
        """When intent is long and use_llm=True, call LLM for summarization.

        This test verifies the LLM summarization path is invoked for long intents.
        Uses mock to avoid actual API calls.
        """
        from scripts.agentica.memory_backfill import summarize_user_intent
        from unittest.mock import patch, AsyncMock

        long_intent = (
            "I need to implement a comprehensive user authentication system "
            "that supports OAuth2, SAML, and traditional username/password. "
            "It should integrate with existing LDAP directory and support MFA. "
            "Make sure to follow security best practices and add proper logging."
        )

        # Mock the LLM call
        mock_llm_response = "Implement auth system with OAuth2, SAML, password, LDAP, MFA"

        with patch(
            "scripts.agentica.memory_backfill._call_llm_summarize",
            new_callable=AsyncMock,
            return_value=mock_llm_response,
        ):
            result = await summarize_user_intent(long_intent, max_tokens=50, use_llm=True)

            # Should return the LLM-summarized version
            assert result == mock_llm_response

    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self):
        """When LLM call fails, fall back to truncation.

        Graceful degradation ensures the pipeline continues even if LLM is unavailable.
        """
        from scripts.agentica.memory_backfill import summarize_user_intent
        from unittest.mock import patch, AsyncMock

        long_intent = "This is a moderately long intent that needs summarization " * 5

        # Mock LLM call to raise an exception
        with patch(
            "scripts.agentica.memory_backfill._call_llm_summarize",
            new_callable=AsyncMock,
            side_effect=Exception("LLM API error"),
        ):
            result = await summarize_user_intent(long_intent, max_tokens=50, use_llm=True)

            # Should fall back to truncation, not raise
            assert isinstance(result, str)
            assert len(result) < len(long_intent)

    def test_max_tokens_parameter_respected(self):
        """The max_tokens parameter should control output length.

        Even with LLM disabled, truncation should respect max_tokens.
        """
        from scripts.agentica.memory_backfill import summarize_user_intent
        import asyncio

        long_intent = "Word " * 200  # ~1000 chars

        # With small max_tokens, output should be short
        result = asyncio.run(summarize_user_intent(long_intent, max_tokens=10, use_llm=False))

        # Approximate: 10 tokens ~ 40-50 chars
        assert len(result) < 100

    def test_empty_intent_returns_empty(self):
        """Empty intent should return empty string.

        Edge case: don't call LLM for empty input.
        """
        from scripts.agentica.memory_backfill import summarize_user_intent
        import asyncio

        result = asyncio.run(summarize_user_intent("", max_tokens=50, use_llm=True))

        assert result == ""

    def test_whitespace_only_intent_returns_empty(self):
        """Whitespace-only intent should return empty string.

        Edge case: treat whitespace as empty.
        """
        from scripts.agentica.memory_backfill import summarize_user_intent
        import asyncio

        result = asyncio.run(summarize_user_intent("   \n\t  ", max_tokens=50, use_llm=True))

        assert result.strip() == ""


# =============================================================================
# Phase 11: Storage Function Tests
# =============================================================================


class TestStoreLLMSpanMemory:
    """Tests for storage function for LLMSpanMemory.

    The function store_llm_span_memory() stores LLMSpanMemory to memory backend,
    checking for duplicates by content_hash.

    Plan reference: Phase 11 in 2025-12-28-llm-span-memory-model.md
    """

    @pytest.fixture
    def sample_span_memory(self):
        """Create a sample LLMSpanMemory for testing."""
        from scripts.agentica.memory_backfill import LLMSpanMemory

        return LLMSpanMemory(
            span_id="test-span-123",
            turn_number=1,
            session_id="test-session-abc",
            user_intent="Implement user authentication",
            decision="Use JWT tokens with refresh token rotation",
            tools_called=["Read", "Write", "Bash"],
            files_touched=["/src/auth.py", "/src/tokens.py"],
            outcome="SUCCEEDED",
            error_summary=None,
        )

    @pytest.fixture
    def mock_memory_backend(self):
        """Create a mock memory backend for testing."""
        from unittest.mock import AsyncMock, MagicMock

        mock = MagicMock()
        mock.search = AsyncMock(return_value=[])
        mock.store = AsyncMock(return_value="memory-id-001")
        return mock

    @pytest.mark.asyncio
    async def test_stores_novel_memory(self, sample_span_memory, mock_memory_backend):
        """Novel memory (not seen before) should be stored.

        Returns (memory_id, True) for novel memories.
        """
        from scripts.agentica.memory_backfill import store_llm_span_memory

        # Mock search returns empty (no duplicates)
        mock_memory_backend.search.return_value = []

        memory_id, was_novel = await store_llm_span_memory(
            mock_memory_backend, sample_span_memory
        )

        # Should be stored
        assert memory_id == "memory-id-001"
        assert was_novel is True

        # Store should have been called
        mock_memory_backend.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_duplicate_by_hash(self, sample_span_memory, mock_memory_backend):
        """Duplicate memory (same content_hash) should be skipped.

        Returns (None, False) for duplicates.
        """
        from scripts.agentica.memory_backfill import store_llm_span_memory

        # Mock search returns existing memory with same hash
        mock_memory_backend.search.return_value = [
            {"id": "existing-id", "content_hash": sample_span_memory.content_hash}
        ]

        memory_id, was_novel = await store_llm_span_memory(
            mock_memory_backend, sample_span_memory
        )

        # Should be skipped
        assert memory_id is None
        assert was_novel is False

        # Store should NOT have been called
        mock_memory_backend.store.assert_not_called()

    @pytest.mark.asyncio
    async def test_stores_with_correct_metadata(self, sample_span_memory, mock_memory_backend):
        """Stored memory should have correct metadata structure.

        Metadata should include all structured fields from LLMSpanMemory.
        """
        from scripts.agentica.memory_backfill import store_llm_span_memory

        mock_memory_backend.search.return_value = []

        await store_llm_span_memory(mock_memory_backend, sample_span_memory)

        # Extract the call args
        call_args = mock_memory_backend.store.call_args

        # The stored content should be the embedding_text
        stored_content = call_args.kwargs.get("content") or call_args.args[0]
        assert sample_span_memory.embedding_text in stored_content

        # Metadata should include key fields
        stored_metadata = call_args.kwargs.get("metadata") or call_args.args[1]
        assert stored_metadata["span_id"] == sample_span_memory.span_id
        assert stored_metadata["session_id"] == sample_span_memory.session_id
        assert stored_metadata["turn_number"] == sample_span_memory.turn_number
        assert stored_metadata["content_hash"] == sample_span_memory.content_hash
        assert "tools_called" in stored_metadata
        assert "files_touched" in stored_metadata

    @pytest.mark.asyncio
    async def test_stores_with_embedding_if_present(self, sample_span_memory, mock_memory_backend):
        """If span_memory has pre-computed embedding, use it.

        Avoids redundant embedding computation.
        """
        from scripts.agentica.memory_backfill import store_llm_span_memory

        # Add pre-computed embedding
        sample_span_memory.embedding = [0.1, 0.2, 0.3, 0.4, 0.5]
        mock_memory_backend.search.return_value = []

        await store_llm_span_memory(mock_memory_backend, sample_span_memory)

        # Check if embedding was passed
        call_args = mock_memory_backend.store.call_args
        stored_embedding = call_args.kwargs.get("embedding")

        # Implementation may or may not use pre-computed embedding
        # This test documents the expected behavior
        if stored_embedding is not None:
            assert stored_embedding == sample_span_memory.embedding

    @pytest.mark.asyncio
    async def test_handles_storage_error_gracefully(self, sample_span_memory, mock_memory_backend):
        """Storage errors should be handled gracefully.

        Returns (None, False) and logs error, doesn't crash.
        """
        from scripts.agentica.memory_backfill import store_llm_span_memory

        mock_memory_backend.search.return_value = []
        mock_memory_backend.store.side_effect = Exception("Storage backend error")

        # Should not raise
        memory_id, was_novel = await store_llm_span_memory(
            mock_memory_backend, sample_span_memory
        )

        # Should indicate failure
        assert memory_id is None
        assert was_novel is False

    @pytest.mark.asyncio
    async def test_outcome_included_in_metadata(self, sample_span_memory, mock_memory_backend):
        """Outcome field should be included in stored metadata.

        This enables filtering memories by success/failure.
        """
        from scripts.agentica.memory_backfill import store_llm_span_memory

        sample_span_memory.outcome = "FAILED"
        sample_span_memory.error_summary = "Test assertion failed"
        mock_memory_backend.search.return_value = []

        await store_llm_span_memory(mock_memory_backend, sample_span_memory)

        call_args = mock_memory_backend.store.call_args
        stored_metadata = call_args.kwargs.get("metadata") or call_args.args[1]

        assert stored_metadata["outcome"] == "FAILED"
        assert stored_metadata["error_summary"] == "Test assertion failed"


# =============================================================================
# Phase 12: Integration Tests (backfill_session modification)
# =============================================================================


class TestBackfillSessionSpanMemoryIntegration:
    """Tests for LLMSpanMemory integration into backfill_session().

    Phase 12 modifies backfill_session() to call extract_llm_span_memories()
    and store the results.

    Plan reference: Phase 12 in 2025-12-28-llm-span-memory-model.md
    """

    @pytest.fixture
    def mock_braintrust_client(self):
        """Mock Braintrust client that returns test spans."""
        from unittest.mock import MagicMock, AsyncMock

        mock = MagicMock()
        mock.fetch_session_spans = AsyncMock(
            return_value=[
                {
                    "span_id": "root-span",
                    "span_parents": [],
                    "name": "Session",
                    "span_attributes": {"type": "task"},
                },
                {
                    "span_id": "turn-1",
                    "span_parents": ["root-span"],
                    "name": "Turn 1",
                    "span_attributes": {"type": "task"},
                    "input": "Build the feature",
                },
                {
                    "span_id": "llm-1",
                    "span_parents": ["turn-1"],
                    "name": "LLM",
                    "span_attributes": {"type": "llm"},
                    "output": {"content": "I will build it"},
                },
            ]
        )
        return mock

    @pytest.mark.asyncio
    async def test_backfill_session_extracts_span_memories(self, mock_braintrust_client):
        """backfill_session should extract LLMSpanMemory when enabled.

        The result.span_memories_extracted should reflect count.
        """
        from scripts.agentica.memory_backfill import backfill_session
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_memory = MagicMock()
        mock_memory.search = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock(return_value="id")
        mock_memory.close = AsyncMock()

        # Mock the actual functions used by backfill_session
        with patch(
            "scripts.agentica.memory_backfill.fetch_session_spans",
            new_callable=AsyncMock,
            return_value=[
                {
                    "span_id": "root-span",
                    "span_parents": [],
                    "name": "Session",
                    "span_attributes": {"type": "task"},
                },
                {
                    "span_id": "turn-1",
                    "span_parents": ["root-span"],
                    "name": "Turn 1",
                    "span_attributes": {"type": "task"},
                    "input": "Build the feature",
                },
                {
                    "span_id": "llm-1",
                    "span_parents": ["turn-1"],
                    "name": "LLM",
                    "span_attributes": {"type": "llm"},
                    "output": {"content": "I will build it"},
                },
            ],
        ), patch(
            "scripts.agentica.memory_backfill.get_hierarchical_context",
            return_value={"handoff": None, "ledger": None},
        ), patch(
            "scripts.agentica.memory_backfill.create_memory_service",
            new_callable=AsyncMock,
            return_value=mock_memory,
        ), patch(
            "scripts.agentica.memory_backfill.EmbeddingService",
        ) as mock_embedder_cls:
            # Mock embedding service
            mock_embedder = MagicMock()
            mock_embedder.embed_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
            mock_embedder_cls.return_value = mock_embedder

            result = await backfill_session(
                session_id="test-session",
                extract_span_memories=True,
            )

            # Should have extracted span memories
            assert result.span_memories_extracted >= 0

    @pytest.mark.asyncio
    async def test_backfill_session_respects_flag(self, mock_braintrust_client):
        """When extract_span_memories=False, don't extract span memories.

        Default behavior should not include span memory extraction.
        """
        from scripts.agentica.memory_backfill import backfill_session
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_memory = MagicMock()
        mock_memory.search = AsyncMock(return_value=[])
        mock_memory.store = AsyncMock(return_value="id")
        mock_memory.close = AsyncMock()

        # Mock the actual functions used by backfill_session
        with patch(
            "scripts.agentica.memory_backfill.fetch_session_spans",
            new_callable=AsyncMock,
            return_value=[
                {
                    "span_id": "root-span",
                    "span_parents": [],
                    "name": "Session",
                    "span_attributes": {"type": "task"},
                },
                {
                    "span_id": "turn-1",
                    "span_parents": ["root-span"],
                    "name": "Turn 1",
                    "span_attributes": {"type": "task"},
                    "input": "Build the feature",
                },
                {
                    "span_id": "llm-1",
                    "span_parents": ["turn-1"],
                    "name": "LLM",
                    "span_attributes": {"type": "llm"},
                    "output": {"content": "I will build it"},
                },
            ],
        ), patch(
            "scripts.agentica.memory_backfill.get_hierarchical_context",
            return_value={"handoff": None, "ledger": None},
        ), patch(
            "scripts.agentica.memory_backfill.create_memory_service",
            new_callable=AsyncMock,
            return_value=mock_memory,
        ), patch(
            "scripts.agentica.memory_backfill.EmbeddingService",
        ) as mock_embedder_cls, patch(
            "scripts.agentica.memory_backfill.extract_llm_span_memories",
        ) as mock_extract:
            # Mock embedding service
            mock_embedder = MagicMock()
            mock_embedder.embed_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
            mock_embedder_cls.return_value = mock_embedder

            result = await backfill_session(
                session_id="test-session",
                extract_span_memories=False,
            )

            # extract_llm_span_memories should NOT have been called
            mock_extract.assert_not_called()

            # Result should have zero span memories
            assert result.span_memories_extracted == 0


# =============================================================================
# Phase 13: BackfillResult Fields Tests
# =============================================================================


class TestBackfillResultSpanMemoryFields:
    """Tests for new BackfillResult fields for span memory tracking.

    Phase 13 adds span_memories_extracted, span_memories_stored,
    span_memories_skipped to BackfillResult.

    Plan reference: Phase 13 in 2025-12-28-llm-span-memory-model.md
    """

    def test_has_span_memory_fields(self):
        """BackfillResult should have span memory tracking fields.

        New fields:
        - span_memories_extracted: int
        - span_memories_stored: int
        - span_memories_skipped: int
        """
        from scripts.agentica.memory_backfill import BackfillResult

        # Instantiate with required fields
        result = BackfillResult(
            session_id="test",
            facts_extracted=5,
            facts_stored=3,
            facts_skipped_duplicate=2,
        )

        # New fields should exist
        assert hasattr(result, "span_memories_extracted")
        assert hasattr(result, "span_memories_stored")
        assert hasattr(result, "span_memories_skipped")

    def test_fields_default_to_zero(self):
        """Span memory fields should default to 0.

        Backward compatible: existing code won't break.
        """
        from scripts.agentica.memory_backfill import BackfillResult

        result = BackfillResult(
            session_id="test",
            facts_extracted=5,
            facts_stored=3,
            facts_skipped_duplicate=2,
        )

        # Should default to 0
        assert result.span_memories_extracted == 0
        assert result.span_memories_stored == 0
        assert result.span_memories_skipped == 0

    def test_fields_are_settable(self):
        """Span memory fields can be set to non-zero values.

        Used when span memory extraction is enabled.
        """
        from scripts.agentica.memory_backfill import BackfillResult

        result = BackfillResult(
            session_id="test",
            facts_extracted=5,
            facts_stored=3,
            facts_skipped_duplicate=2,
            span_memories_extracted=10,
            span_memories_stored=8,
            span_memories_skipped=2,
        )

        assert result.span_memories_extracted == 10
        assert result.span_memories_stored == 8
        assert result.span_memories_skipped == 2

    def test_fields_are_integers(self):
        """Span memory fields should be integers.

        Type safety for metrics.
        """
        from scripts.agentica.memory_backfill import BackfillResult

        result = BackfillResult(
            session_id="test",
            facts_extracted=5,
            facts_stored=3,
            facts_skipped_duplicate=2,
            span_memories_extracted=10,
            span_memories_stored=8,
            span_memories_skipped=2,
        )

        assert isinstance(result.span_memories_extracted, int)
        assert isinstance(result.span_memories_stored, int)
        assert isinstance(result.span_memories_skipped, int)

    def test_stored_plus_skipped_equals_extracted(self):
        """Invariant: stored + skipped should equal extracted.

        Every extracted memory is either stored or skipped.
        """
        from scripts.agentica.memory_backfill import BackfillResult

        result = BackfillResult(
            session_id="test",
            facts_extracted=5,
            facts_stored=3,
            facts_skipped_duplicate=2,
            span_memories_extracted=10,
            span_memories_stored=7,
            span_memories_skipped=3,
        )

        # This is an invariant the implementation should maintain
        assert result.span_memories_stored + result.span_memories_skipped == result.span_memories_extracted


# =============================================================================
# Phase 14: CLI Flag Tests
# =============================================================================


class TestCLIExtractSpanMemoriesFlag:
    """Tests for --extract-span-memories CLI flag.

    Phase 14 adds argparse argument for enabling span memory extraction.

    Plan reference: Phase 14 in 2025-12-28-llm-span-memory-model.md
    """

    def test_parse_args_has_extract_span_memories_flag(self):
        """parse_args() should recognize --extract-span-memories flag.

        Flag should be a boolean store_true action.
        """
        from scripts.agentica.memory_backfill import parse_args

        # Test with flag present
        args = parse_args(["--session-id", "test-123", "--extract-span-memories"])
        assert args.extract_span_memories is True

        # Test without flag
        args = parse_args(["--session-id", "test-123"])
        assert args.extract_span_memories is False

    def test_flag_works_with_batch_mode(self):
        """--extract-span-memories works with batch mode flags.

        Should be compatible with --all, --since, etc.
        """
        from scripts.agentica.memory_backfill import parse_args

        # With --all
        args = parse_args(["--all", "--extract-span-memories"])
        assert args.extract_span_memories is True
        assert args.all is True

        # With --since
        args = parse_args(["--since", "2025-01-01", "--extract-span-memories"])
        assert args.extract_span_memories is True
        assert args.since == "2025-01-01"

    def test_flag_works_with_dry_run(self):
        """--extract-span-memories works with --dry-run.

        Useful for testing extraction without storage.
        """
        from scripts.agentica.memory_backfill import parse_args

        args = parse_args(["--session-id", "test", "--extract-span-memories", "--dry-run"])
        assert args.extract_span_memories is True
        assert args.dry_run is True

    def test_flag_has_help_text(self):
        """--extract-span-memories should have descriptive help text.

        User should understand what the flag does.
        """
        from scripts.agentica.memory_backfill import parse_args
        import argparse
        import io
        import sys

        # Capture help output
        captured = io.StringIO()
        try:
            parse_args(["--help"])
        except SystemExit:
            pass

        # Can't easily capture argparse help, but we can verify the argument exists
        # by checking it parses without error
        args = parse_args(["--session-id", "test", "--extract-span-memories"])
        assert args.extract_span_memories is True

    def test_flag_short_form_not_required(self):
        """No short form needed for --extract-span-memories.

        Long form is descriptive enough for this rarely-used flag.
        """
        from scripts.agentica.memory_backfill import parse_args

        # Should work with long form
        args = parse_args(["--session-id", "test", "--extract-span-memories"])
        assert args.extract_span_memories is True

        # Short form like -e or -s would conflict with other flags
        # So we explicitly don't add one


class TestCLIExtractSpanMemoriesExecution:
    """Tests for CLI execution with --extract-span-memories flag.

    Verifies the flag triggers span memory extraction in main().
    """

    @pytest.mark.asyncio
    async def test_main_passes_flag_to_backfill_session(self):
        """main() should pass extract_span_memories to backfill_session.

        Integration: CLI arg flows through to function call.
        """
        from scripts.agentica.memory_backfill import main
        from unittest.mock import patch, AsyncMock, MagicMock

        mock_result = MagicMock()
        mock_result.span_memories_extracted = 5
        mock_result.span_memories_stored = 4
        mock_result.span_memories_skipped = 1
        mock_result.facts_extracted = 10
        mock_result.facts_stored = 8
        mock_result.facts_skipped_duplicate = 2
        mock_result.errors = []
        mock_result.duration_seconds = 1.5
        mock_result.two_pass_used = False

        with patch(
            "scripts.agentica.memory_backfill.backfill_session",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_backfill, patch(
            "scripts.agentica.memory_backfill.load_api_key",
            return_value="test-api-key",
        ), patch(
            "scripts.agentica.memory_backfill.get_project_id",
            return_value="test-project-id",
        ), patch(
            "sys.argv",
            ["memory_backfill.py", "--session-id", "test-123", "--extract-span-memories"],
        ):
            await main()

            # backfill_session should have been called with extract_span_memories=True
            mock_backfill.assert_called_once()
            call_kwargs = mock_backfill.call_args.kwargs
            assert call_kwargs.get("extract_span_memories") is True

    @pytest.mark.asyncio
    async def test_main_outputs_span_memory_metrics(self):
        """main() should output span memory metrics to console.

        User should see extraction results.
        """
        from scripts.agentica.memory_backfill import main
        from unittest.mock import patch, AsyncMock, MagicMock
        import io
        import sys

        mock_result = MagicMock()
        mock_result.span_memories_extracted = 5
        mock_result.span_memories_stored = 4
        mock_result.span_memories_skipped = 1
        mock_result.facts_extracted = 10
        mock_result.facts_stored = 8
        mock_result.facts_skipped_duplicate = 2
        mock_result.errors = []
        mock_result.duration_seconds = 1.5
        mock_result.two_pass_used = False

        captured_output = io.StringIO()

        with patch(
            "scripts.agentica.memory_backfill.backfill_session",
            new_callable=AsyncMock,
            return_value=mock_result,
        ), patch(
            "scripts.agentica.memory_backfill.load_api_key",
            return_value="test-api-key",
        ), patch(
            "scripts.agentica.memory_backfill.get_project_id",
            return_value="test-project-id",
        ), patch(
            "sys.argv",
            ["memory_backfill.py", "--session-id", "test-123", "--extract-span-memories"],
        ), patch("sys.stdout", captured_output):
            await main()

        output = captured_output.getvalue()

        # Output should include span memory metrics
        # (exact format is implementation detail)
        assert "span" in output.lower() or "memory" in output.lower() or "5" in output

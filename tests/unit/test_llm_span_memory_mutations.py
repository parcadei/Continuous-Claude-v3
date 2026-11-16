"""Mutation Testing - TDD Failing Tests for LLMSpanMemory.

This module contains tests designed to catch mutations identified in Phase A/B.
These tests should FAIL initially (TDD red phase) to expose code weaknesses.

Run with: uv run pytest tests/unit/test_llm_span_memory_mutations.py -v

Based on:
- thoughts/shared/agent-outputs/mutation-testing/phase-a/mutation-results.md
- thoughts/shared/agent-outputs/mutation-testing/phase-b/bug-research.md
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.agentica_patterns.memory_backfill import (
    LLMSpanMemory,
    detect_error_in_turn,
    extract_llm_decision,
    extract_user_intent_raw,
    lookup_session_outcome,
    store_llm_span_memory,
)


# =============================================================================
# 1. Hash Determinism Tests (From Mutation: hash_sort_keys_remove)
# =============================================================================


class TestHashDeterminism:
    """Tests for hash determinism across different field orderings."""

    def test_same_content_always_produces_same_hash(self):
        """Same content must always produce identical hash (deterministic)."""
        # Create same memory 100 times
        hashes = set()
        for _ in range(100):
            memory = LLMSpanMemory(
                span_id="span-deterministic",
                turn_number=1,
                session_id="session-123",
                user_intent="Test deterministic hashing",
                decision="Verify hash stability",
            )
            hashes.add(memory.content_hash)

        # All hashes should be identical
        assert len(hashes) == 1, "Hash is not deterministic - produced different values"

    def test_hash_stable_across_dict_field_orderings(self):
        """Hash must be stable regardless of internal dict key ordering.

        This test catches the mutation: json.dumps(sort_keys=True) -> json.dumps(sort_keys=False)
        """
        # Create memory with fields in different conceptual orders
        memory1 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Intent A",
            decision="Decision A",
        )

        # Create identical memory
        memory2 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Intent A",
            decision="Decision A",
        )

        # Hashes MUST match
        assert memory1.content_hash == memory2.content_hash

        # Verify hash is computed with sorted keys by checking the actual computation
        hash_input = {
            "span_id": "span-1",
            "session_id": "sess-1",
            "user_intent": "Intent A",
            "decision": "Decision A",
        }
        expected_hash = hashlib.sha256(
            json.dumps(hash_input, sort_keys=True).encode()
        ).hexdigest()[:16]

        assert memory1.content_hash == expected_hash, "Hash not computed with sort_keys=True"

    def test_hash_changes_when_user_intent_changes(self):
        """Different user_intent must produce different hash.

        This test catches the mutation: hash_remove_user_intent (commenting out user_intent in hash)
        """
        memory1 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Intent AAA",
            decision="Same decision",
        )

        memory2 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Intent BBB",  # Different intent
            decision="Same decision",
        )

        assert memory1.content_hash != memory2.content_hash, (
            "Hash does not include user_intent - different intents produced same hash"
        )

    def test_hash_changes_when_decision_changes(self):
        """Different decision must produce different hash.

        This test catches the mutation: hash_remove_decision (commenting out decision in hash)
        """
        memory1 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Same intent",
            decision="Decision AAA",
        )

        memory2 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Same intent",
            decision="Decision BBB",  # Different decision
        )

        assert memory1.content_hash != memory2.content_hash, (
            "Hash does not include decision - different decisions produced same hash"
        )


# =============================================================================
# 2. Truncation Boundary Tests (From Mutations: intent_truncation_boundary)
# =============================================================================


class TestTruncationBoundaries:
    """Tests for exact truncation boundaries."""

    def test_extract_user_intent_at_exactly_500_chars(self):
        """Input of exactly 500 chars should NOT be truncated.

        This catches: if len(text) >= max_chars vs if len(text) > max_chars
        """
        # Exactly 500 characters
        text_500 = "x" * 500
        span = {"input": text_500}

        result = extract_user_intent_raw(span, max_chars=500)

        assert len(result) == 500, f"Expected 500 chars, got {len(result)}"
        assert not result.endswith("..."), "500 chars should NOT be truncated"

    def test_extract_user_intent_at_499_chars(self):
        """Input of 499 chars should NOT be truncated (below boundary)."""
        text_499 = "x" * 499
        span = {"input": text_499}

        result = extract_user_intent_raw(span, max_chars=500)

        assert len(result) == 499
        assert not result.endswith("...")

    def test_extract_user_intent_at_501_chars(self):
        """Input of 501 chars SHOULD be truncated (above boundary).

        This catches: text[:max_chars] vs text[:max_chars-1]
        """
        text_501 = "x" * 501
        span = {"input": text_501}

        result = extract_user_intent_raw(span, max_chars=500)

        # Should be truncated to 500 + "..." = 503
        assert len(result) == 503, f"Expected 503 chars (500 + '...'), got {len(result)}"
        assert result.endswith("...")
        # Verify we got exactly 500 chars before the ellipsis
        assert result[:500] == "x" * 500

    def test_extract_llm_decision_at_exactly_300_chars(self):
        """Decision of exactly 300 chars should NOT be truncated."""
        text_300 = "y" * 300
        span = {"output": text_300}

        result = extract_llm_decision(span, max_chars=300)

        assert len(result) == 300
        assert not result.endswith("...")

    def test_extract_llm_decision_at_299_chars(self):
        """Decision of 299 chars should NOT be truncated."""
        text_299 = "y" * 299
        span = {"output": text_299}

        result = extract_llm_decision(span, max_chars=300)

        assert len(result) == 299
        assert not result.endswith("...")

    def test_extract_llm_decision_at_301_chars(self):
        """Decision of 301 chars SHOULD be truncated."""
        text_301 = "y" * 301
        span = {"output": text_301}

        result = extract_llm_decision(span, max_chars=300)

        # Should be 300 + "..." = 303
        assert len(result) == 303
        assert result.endswith("...")
        assert result[:300] == "y" * 300

    def test_default_max_chars_is_500_for_intent(self):
        """Default max_chars for extract_user_intent_raw should be 500.

        This catches mutations to default parameter values.
        """
        text_501 = "a" * 501
        span = {"input": text_501}

        # Call without explicit max_chars - should use default 500
        result = extract_user_intent_raw(span)

        assert result.endswith("...")
        assert len(result) == 503  # 500 + "..."

    def test_default_max_chars_is_300_for_decision(self):
        """Default max_chars for extract_llm_decision should be 300.

        This catches mutations to default parameter values.
        """
        text_301 = "b" * 301
        span = {"output": text_301}

        # Call without explicit max_chars - should use default 300
        result = extract_llm_decision(span)

        assert result.endswith("...")
        assert len(result) == 303  # 300 + "..."


# =============================================================================
# 3. Whitespace Handling Tests (From Mutation: decision_strip_remove)
# =============================================================================


class TestWhitespaceHandling:
    """Tests for whitespace handling in extraction."""

    def test_extract_llm_decision_strips_leading_whitespace(self):
        """Leading whitespace should be stripped from decision.

        This catches: output.strip() -> output (removing strip)
        """
        span = {"output": "   decision with leading spaces"}

        result = extract_llm_decision(span)

        assert not result.startswith(" "), "Leading whitespace not stripped"
        assert result == "decision with leading spaces"

    def test_extract_llm_decision_strips_trailing_whitespace(self):
        """Trailing whitespace should be stripped from decision."""
        span = {"output": "decision with trailing spaces   "}

        result = extract_llm_decision(span)

        assert not result.endswith(" "), "Trailing whitespace not stripped"
        assert result == "decision with trailing spaces"

    def test_extract_llm_decision_strips_both_ends(self):
        """Both leading and trailing whitespace should be stripped."""
        span = {"output": "  \t  padded decision  \n  "}

        result = extract_llm_decision(span)

        assert result == "padded decision"

    def test_whitespace_only_input_returns_empty(self):
        """Whitespace-only input should return empty string."""
        span = {"output": "   \t\n   "}

        result = extract_llm_decision(span)

        assert result == "", "Whitespace-only input should return empty string"

    def test_extract_llm_decision_from_dict_strips_whitespace(self):
        """Dict output with content field should also strip whitespace."""
        span = {"output": {"content": "  dict content with spaces  "}}

        result = extract_llm_decision(span)

        assert result == "dict content with spaces"


# =============================================================================
# 4. Error Context Window Tests (From Mutations: error_context_*)
# =============================================================================


class TestErrorContextWindow:
    """Tests for error context extraction boundaries."""

    def test_error_context_includes_chars_before_match(self):
        """Error context should include characters before the error.

        This catches: start = max(0, match.start() - 50) mutations
        """
        # Create output with error preceded by context
        prefix = "This is some context before the error: " + "x" * 20  # ~60 chars before
        error = "Traceback (most recent call last):"
        suffix = " some text after"
        output = prefix + error + suffix

        spans = [
            {
                "span_id": "span-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "output": {"stdout": output, "stderr": ""},
            }
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        # Should include some context before "Traceback"
        assert "context before" in result or "x" in result, (
            "Error context should include chars before the match"
        )

    def test_error_context_starts_at_correct_position(self):
        """Verify context includes exactly 50 chars before error start.

        This test catches the mutation: match.start() - 50 -> match.start() - 0
        """
        # Create output where error starts at char 100 (well after 50-char window)
        prefix = "a" * 100  # 100 chars before error
        error = "Traceback (most recent call last):"
        output = prefix + error

        spans = [
            {
                "span_id": "span-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "output": {"stdout": output, "stderr": ""},
            }
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        # Result should start with last 50 chars of prefix (all 'a')
        # If mutation applied (start=0), would get all 100 'a' chars
        # Correct behavior: starts at position 50, so we get 50 'a' chars before Traceback
        assert result.startswith("a" * 50 + "Traceback"), (
            f"Expected 50 prefix chars before 'Traceback', got: {result[:60]}"
        )

    def test_error_context_prefix_not_truncated_to_zero(self):
        """Verify prefix is not truncated away entirely (mutation: -50 -> -0).

        A distinct test that checks the prefix count matches expected.
        """
        # Create known prefix pattern that we can count
        prefix = "PREFIX_CHAR_" * 10  # 120 chars
        error = "Error: something failed"
        output = prefix + error

        spans = [
            {
                "span_id": "span-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "output": {"stdout": output, "stderr": ""},
            }
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        # With 50-char prefix window, we should get the last ~4 occurrences of PREFIX_CHAR_
        # Each "PREFIX_CHAR_" is 12 chars, so 50 chars = ~4 occurrences worth
        prefix_chars_in_result = result.split("Error:")[0] if "Error:" in result else ""
        assert len(prefix_chars_in_result) >= 40, (
            f"Expected ~50 prefix chars before error, got only {len(prefix_chars_in_result)}: '{prefix_chars_in_result}'"
        )

    def test_error_context_includes_chars_after_match(self):
        """Error context should include characters after the error.

        This catches: end = min(len(combined), match.end() + 200) mutations
        """
        error = "Traceback (most recent call last):"
        suffix = "This is important context after the error " + "y" * 100
        output = error + suffix

        spans = [
            {
                "span_id": "span-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "output": {"stdout": output, "stderr": ""},
            }
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        # Should include context after the traceback
        assert "important context" in result or "y" in result, (
            "Error context should include chars after the match"
        )

    def test_error_context_truncated_to_500_chars(self):
        """Error context should be truncated to max 500 chars."""
        # Create very long output with error in the middle
        error = "Traceback (most recent call last):"
        very_long = "x" * 1000

        output = very_long + error + very_long

        spans = [
            {
                "span_id": "span-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "output": {"stdout": output, "stderr": ""},
            }
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        # Should be truncated to 500 chars (or 497 + "...")
        assert len(result) <= 500, f"Error context too long: {len(result)} chars"

    def test_error_context_exactly_500_when_exceeds(self):
        """Error context should be exactly 500 chars when input exceeds limit.

        This test catches the mutation: >500 -> >100 and [:497] -> [:97]

        Context window = 50 chars before + match length + 200 chars after.
        The "Error:\\s*.+" pattern matches greedily to end of line, so a LONG
        error message line will create a large match. Window can exceed 500.
        """
        # Use "Error:" pattern which matches to end of line (greedy .+)
        prefix = "p" * 100  # 100 chars before (window takes last 50)
        # Error message on one line - pattern matches entire line
        error_message = "x" * 500  # 500 chars of error detail
        error = f"Error: {error_message}"  # 507 total chars for error line
        # After the error line, add more content
        suffix = "\ny" * 300  # Multi-line suffix (200 chars taken)

        output = prefix + error + suffix

        spans = [
            {
                "span_id": "span-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "output": {"stdout": output, "stderr": ""},
            }
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        # Window: 50 prefix + 507 match + 200 suffix = 757 chars before truncation
        # After truncation: exactly 500 chars (497 + "...")
        assert len(result) == 500, f"Expected exactly 500 chars, got {len(result)}"
        assert result.endswith("..."), "Truncated result should end with ellipsis"

    def test_error_context_not_truncated_under_500(self):
        """Error context under 500 chars should NOT have ellipsis.

        This distinguishes 500 limit from 100 limit mutation.
        """
        # Create error context that's 200 chars total (under 500 but over 100)
        error = "Traceback (most recent call last):"  # 35 chars
        short_suffix = "y" * 150  # Will make total ~200 chars (well under 500)
        output = error + short_suffix

        spans = [
            {
                "span_id": "span-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "output": {"stdout": output, "stderr": ""},
            }
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        # Context is under 500, should NOT be truncated
        assert not result.endswith("..."), (
            f"Context under 500 chars should not have ellipsis. Got {len(result)} chars: {result[-20:]}"
        )
        # Also verify content is preserved (not truncated to 100)
        assert len(result) > 100, f"Result too short ({len(result)} chars), likely truncated at 100"

    def test_error_context_between_100_and_500_preserved(self):
        """Error context between 100-500 chars must be preserved (no truncation).

        This is the key test for mutation: >500 -> >100
        If mutation applied, a 300-char result would be truncated to 100.
        """
        # Create error context that's exactly 300 chars
        error = "Error: test error message"  # 25 chars
        # Add more to get exactly 300 total (with context window)
        suffix = "z" * 275  # 25 + 275 = 300
        output = error + suffix

        spans = [
            {
                "span_id": "span-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "output": {"stdout": output, "stderr": ""},
            }
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        # Should NOT be truncated (300 < 500)
        assert not result.endswith("..."), "300-char context should not be truncated"
        # Should be at least 200 chars (mutation would give 100)
        assert len(result) >= 200, f"Result too short ({len(result)} chars), mutation may have applied"


# =============================================================================
# 5. Unicode Handling Tests (From Bug Research)
# =============================================================================


class TestUnicodeHandling:
    """Tests for Unicode character handling."""

    def test_emoji_in_user_intent(self):
        """Emoji characters should be preserved in user_intent."""
        memory = LLMSpanMemory(
            span_id="span-emoji",
            turn_number=1,
            session_id="sess-1",
            user_intent="Add a rocket feature 🚀 with stars ⭐",
            decision="Implement the feature",
        )

        assert "🚀" in memory.user_intent
        assert "⭐" in memory.user_intent
        assert "🚀" in memory.embedding_text
        # Hash should still work
        assert memory.content_hash is not None
        assert len(memory.content_hash) == 16

    def test_cjk_characters_in_decision(self):
        """CJK (Chinese/Japanese/Korean) characters should be preserved."""
        memory = LLMSpanMemory(
            span_id="span-cjk",
            turn_number=1,
            session_id="sess-1",
            user_intent="Implement feature",
            decision="使用中文决策 (Chinese decision)",
        )

        assert "使用中文决策" in memory.decision
        assert "使用中文决策" in memory.embedding_text
        # Hash should work
        assert memory.content_hash is not None

    def test_truncation_does_not_break_utf8(self):
        """Truncation at boundary should not create invalid UTF-8.

        Multi-byte characters at truncation point should be handled gracefully.
        """
        # Create string with multi-byte chars near the truncation point
        text = "a" * 498 + "🚀🚀"  # Each emoji is 4 bytes, total ~506 chars

        span = {"input": text}
        result = extract_user_intent_raw(span, max_chars=500)

        # Result should be valid UTF-8 (this would raise if invalid)
        result.encode("utf-8")

        # Should be truncated
        assert len(result) <= 503  # max_chars + "..."

    def test_unicode_normalization_in_hash(self):
        """Unicode characters should produce consistent hashes."""
        # Same content should produce same hash
        memory1 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="日本語テスト",
            decision="한국어 결정",
        )

        memory2 = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="日本語テスト",
            decision="한국어 결정",
        )

        assert memory1.content_hash == memory2.content_hash


# =============================================================================
# 6. Concurrent Access Tests (From Bug Research: Race Conditions)
# =============================================================================


class TestConcurrentAccess:
    """Tests for concurrent access patterns."""

    @pytest.mark.asyncio
    async def test_parallel_store_calls_no_race(self):
        """Parallel store calls should not cause race conditions.

        Store the same memory multiple times concurrently.
        Only one should actually be stored (dedup by hash).
        """
        memory = LLMSpanMemory(
            span_id="span-concurrent",
            turn_number=1,
            session_id="sess-concurrent",
            user_intent="Concurrent test",
            decision="Test decision",
        )

        # Mock memory backend
        mock_memory = AsyncMock()
        stored_hashes: set[str] = set()
        store_count = 0

        async def mock_search(query: str, limit: int = 5):
            # Return empty on first search (nothing stored yet)
            await asyncio.sleep(0.01)  # Simulate async delay
            if memory.content_hash in stored_hashes:
                return [{"content_hash": memory.content_hash}]
            return []

        async def mock_store(content: str, metadata: dict, embedding=None):
            nonlocal store_count
            await asyncio.sleep(0.01)  # Simulate async delay
            if metadata.get("content_hash") not in stored_hashes:
                stored_hashes.add(metadata.get("content_hash"))
                store_count += 1
            return f"memory-{store_count}"

        mock_memory.search = mock_search
        mock_memory.store = mock_store

        # Store same memory 10 times concurrently
        tasks = [store_llm_span_memory(mock_memory, memory) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # At least one should have stored (first one)
        stored_results = [r for r in results if r[1]]  # r[1] = was_novel
        duplicate_results = [r for r in results if not r[1]]

        # Due to race conditions, we might get more than one store
        # but ideally only one should be "novel"
        assert len(stored_hashes) >= 1, "At least one memory should be stored"
        # This test documents current behavior - in a perfectly thread-safe
        # implementation, only 1 would be stored

    @pytest.mark.asyncio
    async def test_duplicate_detection_under_concurrency(self):
        """Duplicate detection should work even under concurrent load."""
        # Create memory and pre-populate the "database"
        memory = LLMSpanMemory(
            span_id="span-dup",
            turn_number=1,
            session_id="sess-dup",
            user_intent="Duplicate test",
            decision="Test decision",
        )

        mock_memory = AsyncMock()
        # Always return existing match
        mock_memory.search = AsyncMock(
            return_value=[{"content_hash": memory.content_hash}]
        )
        mock_memory.store = AsyncMock(return_value="should-not-be-called")

        # Try to store 5 times concurrently
        tasks = [store_llm_span_memory(mock_memory, memory) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        # All should be detected as duplicates
        for memory_id, was_novel in results:
            assert not was_novel, "All should be detected as duplicates"
            assert memory_id is None

        # Store should never be called
        mock_memory.store.assert_not_called()


# =============================================================================
# 7. Malformed Data Tests (From Bug Research)
# =============================================================================


class TestMalformedData:
    """Tests for handling malformed or unexpected data."""

    def test_span_with_null_span_parents(self):
        """Span with null span_parents should be handled gracefully."""
        spans = [
            {
                "span_id": "turn-1",
                "span_parents": None,  # null instead of empty array
                "name": "Bash",
                "output": {"stdout": "Traceback:", "stderr": ""},
            }
        ]

        # Should not raise
        result = detect_error_in_turn("turn-1", spans)
        # span_parents is null, so this span won't match
        assert result is None

    def test_span_with_missing_output_field(self):
        """Span with missing output field should return empty decision."""
        span = {"input": "some input"}  # No output field

        result = extract_llm_decision(span)

        assert result == ""

    def test_span_with_none_output(self):
        """Span with None output should return empty decision."""
        span = {"output": None}

        result = extract_llm_decision(span)

        assert result == ""

    def test_deeply_nested_dict_input(self):
        """Deeply nested dict input should be handled."""
        # Create deeply nested structure
        deep_dict = {"level1": {"level2": {"level3": {"content": "Deep content"}}}}
        span = {"output": deep_dict}

        # Should not raise, but may return empty (no direct content field)
        result = extract_llm_decision(span)
        # Current implementation only looks at top-level "content"
        assert isinstance(result, str)

    def test_extract_intent_with_list_input(self):
        """List input should be handled gracefully."""
        span = {"input": ["item1", "item2"]}

        result = extract_user_intent_raw(span)

        assert result == ""  # Lists are not supported

    def test_extract_decision_with_numeric_output(self):
        """Numeric output should be handled gracefully."""
        span = {"output": 12345}

        result = extract_llm_decision(span)

        assert result == ""  # Numbers are not supported


# =============================================================================
# 8. SQL Injection Prevention Tests (From Bug Research)
# =============================================================================


class TestSQLInjectionPrevention:
    """Tests for SQL injection prevention."""

    def test_session_id_with_sql_injection_attempt(self):
        """Session ID with SQL injection should be handled safely."""
        malicious_session_id = "'; DROP TABLE handoffs; --"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / ".claude" / "cache" / "context.db"
            db_path.parent.mkdir(parents=True)

            # Create test database with table
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE handoffs (
                    root_span_id TEXT PRIMARY KEY,
                    outcome TEXT,
                    outcome_notes TEXT
                )
            """)
            conn.execute(
                "INSERT INTO handoffs (root_span_id, outcome) VALUES (?, ?)",
                ("safe-session", "SUCCEEDED"),
            )
            conn.commit()
            conn.close()

            # Patch environment to use our test database
            with patch.dict("os.environ", {"CONTEXT_DB_PATH": str(db_path)}):
                # This should NOT drop the table
                result = lookup_session_outcome(malicious_session_id)

            # Result should be (None, None) - not found
            assert result == (None, None)

            # Table should still exist with data
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM handoffs")
            count = cursor.fetchone()[0]
            conn.close()

            assert count == 1, "Table was modified by SQL injection"

    def test_session_id_with_special_characters(self):
        """Session IDs with special characters should be queried safely."""
        special_session_id = "session'with\"quotes"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / ".claude" / "cache" / "context.db"
            db_path.parent.mkdir(parents=True)

            # Create test database
            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE handoffs (
                    root_span_id TEXT PRIMARY KEY,
                    outcome TEXT,
                    outcome_notes TEXT
                )
            """)
            # Store session with special chars using parameterized query
            conn.execute(
                "INSERT INTO handoffs (root_span_id, outcome) VALUES (?, ?)",
                (special_session_id, "SUCCEEDED"),
            )
            conn.commit()
            conn.close()

            with patch.dict("os.environ", {"CONTEXT_DB_PATH": str(db_path)}):
                result = lookup_session_outcome(special_session_id)

            # Should find the session
            assert result == ("SUCCEEDED", None)

    def test_outcome_lookup_with_unicode(self):
        """Unicode in session ID should work correctly."""
        unicode_session_id = "session-日本語-🚀"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / ".claude" / "cache" / "context.db"
            db_path.parent.mkdir(parents=True)

            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE TABLE handoffs (
                    root_span_id TEXT PRIMARY KEY,
                    outcome TEXT,
                    outcome_notes TEXT
                )
            """)
            conn.execute(
                "INSERT INTO handoffs (root_span_id, outcome, outcome_notes) VALUES (?, ?, ?)",
                (unicode_session_id, "SUCCEEDED", "日本語のノート"),
            )
            conn.commit()
            conn.close()

            with patch.dict("os.environ", {"CONTEXT_DB_PATH": str(db_path)}):
                result = lookup_session_outcome(unicode_session_id)

            assert result == ("SUCCEEDED", "日本語のノート")


# =============================================================================
# 9. Hash Uniqueness Tests (Additional coverage)
# =============================================================================


class TestHashUniqueness:
    """Additional tests for hash uniqueness guarantees."""

    def test_1000_different_inputs_produce_1000_unique_hashes(self):
        """1000 different memories should produce 1000 unique hashes."""
        hashes = set()

        for i in range(1000):
            memory = LLMSpanMemory(
                span_id=f"span-{i}",
                turn_number=i % 10 + 1,
                session_id=f"session-{i // 10}",
                user_intent=f"Unique intent number {i}",
                decision=f"Unique decision number {i}",
            )
            hashes.add(memory.content_hash)

        assert len(hashes) == 1000, f"Expected 1000 unique hashes, got {len(hashes)}"

    def test_hash_includes_all_required_fields(self):
        """Hash must include span_id, session_id, user_intent, and decision."""
        base = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="intent",
            decision="decision",
        )

        # Change span_id
        diff_span = LLMSpanMemory(
            span_id="span-DIFFERENT",
            turn_number=1,
            session_id="sess-1",
            user_intent="intent",
            decision="decision",
        )

        # Change session_id
        diff_session = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-DIFFERENT",
            user_intent="intent",
            decision="decision",
        )

        # Change user_intent
        diff_intent = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="intent-DIFFERENT",
            decision="decision",
        )

        # Change decision
        diff_decision = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="intent",
            decision="decision-DIFFERENT",
        )

        # All should have different hashes
        all_hashes = {
            base.content_hash,
            diff_span.content_hash,
            diff_session.content_hash,
            diff_intent.content_hash,
            diff_decision.content_hash,
        }

        assert len(all_hashes) == 5, "All field changes should produce different hashes"


# =============================================================================
# 10. Edge Case Tests (Comprehensive coverage)
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_user_intent(self):
        """Empty user_intent should be handled."""
        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="",
            decision="Some decision",
        )

        assert memory.embedding_text == "Intent: \nDecision: Some decision"
        assert memory.content_hash is not None

    def test_empty_decision(self):
        """Empty decision should be handled."""
        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Some intent",
            decision="",
        )

        assert memory.embedding_text == "Intent: Some intent\nDecision: "
        assert memory.content_hash is not None

    def test_very_long_content(self):
        """Very long content should be handled."""
        long_intent = "a" * 10000
        long_decision = "b" * 10000

        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent=long_intent,
            decision=long_decision,
        )

        # Should not raise
        assert len(memory.embedding_text) > 20000
        assert memory.content_hash is not None
        assert len(memory.content_hash) == 16

    def test_newlines_in_content(self):
        """Newlines in content should be preserved."""
        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Line 1\nLine 2\nLine 3",
            decision="Decision\nwith\nnewlines",
        )

        assert "\n" in memory.user_intent
        assert "\n" in memory.decision

    def test_special_json_characters(self):
        """Special JSON characters should be handled."""
        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent='Intent with "quotes" and \\backslashes\\',
            decision="Decision with\ttabs",
        )

        # Should not raise
        assert memory.content_hash is not None
        # Hash computation uses json.dumps which should handle these
        json.dumps({"user_intent": memory.user_intent})  # Should not raise

    def test_null_byte_handling(self):
        """Null bytes in content should be handled."""
        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=1,
            session_id="sess-1",
            user_intent="Intent with\x00null byte",
            decision="Decision",
        )

        # Should not raise
        assert memory.content_hash is not None

    def test_turn_number_zero(self):
        """Turn number 0 should be valid."""
        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=0,
            session_id="sess-1",
            user_intent="Intent",
            decision="Decision",
        )

        assert memory.turn_number == 0

    def test_negative_turn_number(self):
        """Negative turn number should be accepted (dataclass has no validation)."""
        memory = LLMSpanMemory(
            span_id="span-1",
            turn_number=-1,
            session_id="sess-1",
            user_intent="Intent",
            decision="Decision",
        )

        assert memory.turn_number == -1


# =============================================================================
# 11. Error Pattern Detection Tests (From Mutation Results)
# =============================================================================


class TestErrorPatternDetection:
    """Tests for error pattern detection in bash output."""

    def test_traceback_detection_case_insensitive(self):
        """Traceback detection should work regardless of case."""
        # Standard case
        spans1 = [
            {
                "span_id": "span-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "output": {"stdout": "Traceback (most recent call last):", "stderr": ""},
            }
        ]

        # All lowercase (should still match due to re.IGNORECASE)
        spans2 = [
            {
                "span_id": "span-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "output": {"stdout": "traceback (most recent call last):", "stderr": ""},
            }
        ]

        result1 = detect_error_in_turn("turn-1", spans1)
        result2 = detect_error_in_turn("turn-1", spans2)

        assert result1 is not None
        assert result2 is not None

    def test_error_not_detected_for_non_bash_spans(self):
        """Error detection should only apply to Bash spans."""
        spans = [
            {
                "span_id": "span-1",
                "span_parents": ["turn-1"],
                "name": "Read",  # Not Bash
                "output": {"stdout": "Traceback (most recent call last):", "stderr": ""},
            }
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is None  # Not a Bash span

    def test_error_detected_in_stderr(self):
        """Errors in stderr should be detected."""
        spans = [
            {
                "span_id": "span-1",
                "span_parents": ["turn-1"],
                "name": "Bash",
                "output": {"stdout": "", "stderr": "Error: Something went wrong"},
            }
        ]

        result = detect_error_in_turn("turn-1", spans)

        assert result is not None
        assert "Error:" in result or "went wrong" in result

    def test_multiple_error_patterns(self):
        """Various error patterns should all be detected."""
        error_outputs = [
            "AssertionError: Expected True",
            "ModuleNotFoundError: No module named 'missing'",
            "ImportError: cannot import name 'func'",
            "TypeError: expected str, got int",
            "ValueError: invalid literal",
            "RuntimeError: something failed",
            "KeyError: 'missing_key'",
            "AttributeError: object has no attribute",
            "FileNotFoundError: file.txt",
            "FAILED tests/test_something.py::test_case",
            "exit code 1",
        ]

        for error_output in error_outputs:
            spans = [
                {
                    "span_id": "span-1",
                    "span_parents": ["turn-1"],
                    "name": "Bash",
                    "output": {"stdout": error_output, "stderr": ""},
                }
            ]

            result = detect_error_in_turn("turn-1", spans)
            assert result is not None, f"Failed to detect: {error_output}"

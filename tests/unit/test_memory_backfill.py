"""Tests for Memory Backfill Service - TDD-style failing tests.

Tests follow the plan at: thoughts/shared/plans/2025-12-27-memory-backfill.md

Run with: uv run pytest tests/unit/test_memory_backfill.py -v
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# Phase 1: Data Structures and Content Hashing
# =============================================================================


class TestFactTypeEnum:
    """Test FactType enum values."""

    def test_fact_type_enum_values(self):
        """FactType has GOAL, DECISION, FILE_CHANGE, AGENT_OUTPUT, ERROR_FIX."""
        from scripts.agentica_patterns.memory_backfill import FactType

        # Check all required enum values exist
        assert hasattr(FactType, "GOAL")
        assert hasattr(FactType, "DECISION")
        assert hasattr(FactType, "FILE_CHANGE")
        assert hasattr(FactType, "AGENT_OUTPUT")
        assert hasattr(FactType, "ERROR")  # ERROR_FIX maps to ERROR in plan

        # Verify they're valid enum members
        assert FactType.GOAL.value == "goal"
        assert FactType.DECISION.value == "decision"
        assert FactType.FILE_CHANGE.value == "file_change"


class TestExtractedFactDataclass:
    """Test ExtractedFact dataclass structure."""

    def test_extracted_fact_dataclass(self):
        """ExtractedFact has content, fact_type, source_session, content_hash."""
        from scripts.agentica_patterns.memory_backfill import ExtractedFact, FactType

        fact = ExtractedFact(
            content="Test content",
            fact_type=FactType.GOAL,
            source_session="session-123",
        )

        # Required fields
        assert fact.content == "Test content"
        assert fact.fact_type == FactType.GOAL
        assert fact.source_session == "session-123"
        # Auto-generated content_hash
        assert fact.content_hash is not None
        assert len(fact.content_hash) > 0


class TestContentHashing:
    """Content-based deduplication via hashing."""

    def test_content_hash_deterministic(self):
        """Same content produces same hash."""
        from scripts.agentica_patterns.memory_backfill import content_hash

        h1 = content_hash("User prefers Python", {"type": "preference"})
        h2 = content_hash("User prefers Python", {"type": "preference"})
        assert h1 == h2

    def test_content_hash_different_content(self):
        """Different content produces different hash."""
        from scripts.agentica_patterns.memory_backfill import content_hash

        h1 = content_hash("User prefers Python", {"type": "preference"})
        h2 = content_hash("User prefers Rust", {"type": "preference"})
        assert h1 != h2

    def test_content_hash_whitespace_normalized(self):
        """Whitespace is normalized for consistent hashing."""
        from scripts.agentica_patterns.memory_backfill import content_hash

        h1 = content_hash("  User prefers Python  ", {"type": "preference"})
        h2 = content_hash("User prefers Python", {"type": "preference"})
        assert h1 == h2

    def test_content_hash_excludes_timestamp(self):
        """Timestamps are excluded from hash (not semantic)."""
        from scripts.agentica_patterns.memory_backfill import content_hash

        h1 = content_hash("fact", {"type": "x", "timestamp": "2025-01-01"})
        h2 = content_hash("fact", {"type": "x", "timestamp": "2025-12-27"})
        assert h1 == h2

    def test_content_hash_includes_source_session(self):
        """Source session affects hash (same fact from different session is distinct)."""
        from scripts.agentica_patterns.memory_backfill import content_hash

        h1 = content_hash("fact", {"type": "x", "source_session": "abc"})
        h2 = content_hash("fact", {"type": "x", "source_session": "def"})
        assert h1 != h2


# =============================================================================
# Phase 2: Braintrust Queries
# =============================================================================


class TestBraintrustQueries:
    """BTQL query generation and execution (mocked)."""

    def test_list_sessions_query_format(self):
        """Query for listing sessions in date range is correct."""
        from scripts.agentica_patterns.memory_backfill import build_list_sessions_query

        query = build_list_sessions_query("2025-12-20", "2025-12-27")
        assert "root_span_id" in query
        assert "2025-12-20" in query
        assert "GROUP BY" in query

    def test_fetch_session_spans_query(self):
        """Query for fetching session spans is correct."""
        from scripts.agentica_patterns.memory_backfill import build_fetch_session_query

        query = build_fetch_session_query("abc123")
        assert "abc123" in query
        assert "order by" in query.lower() and "created" in query.lower()

    @pytest.mark.asyncio
    async def test_list_sessions_mock(self):
        """Returns session IDs from BTQL response."""
        from scripts.agentica_patterns.memory_backfill import list_sessions_in_range

        with patch("scripts.agentica_patterns.memory_backfill.run_btql") as mock_btql:
            mock_btql.return_value = [
                {"session_id": "s1", "start_time": "2025-12-26T10:00:00Z", "span_count": 10},
                {"session_id": "s2", "start_time": "2025-12-26T11:00:00Z", "span_count": 5},
            ]

            sessions = await list_sessions_in_range(
                "project-id", "2025-12-26", "2025-12-27", "api-key"
            )

            assert len(sessions) == 2
            assert sessions[0]["session_id"] == "s1"
            assert sessions[1]["session_id"] == "s2"

    @pytest.mark.asyncio
    async def test_fetch_session_spans_mock(self):
        """Returns spans for a session."""
        from scripts.agentica_patterns.memory_backfill import fetch_session_spans

        with patch("scripts.agentica_patterns.memory_backfill.run_btql") as mock_btql:
            mock_btql.return_value = [
                {"span_id": "s1", "input": "Hello"},
                {"span_id": "s2", "output": "Hi there"},
            ]

            spans = await fetch_session_spans("abc123", "proj-id", "api-key")

            assert len(spans) == 2
            assert spans[0]["span_id"] == "s1"


# =============================================================================
# Phase 3: Fact Extraction
# =============================================================================


class TestFactExtraction:
    """Parse spans into structured facts."""

    def test_extract_goal_from_first_task(self):
        """First task span extracts as GOAL fact."""
        from scripts.agentica_patterns.memory_backfill import (
            extract_facts_from_context,
            FactType,
        )

        context = {
            "ledger": {"goal": "Build memory backfill service"},
            "handoff": {},
        }

        facts = extract_facts_from_context(context, "session-123")
        goals = [f for f in facts if f.fact_type == FactType.GOAL]

        assert len(goals) == 1
        assert "memory backfill" in goals[0].content.lower()

    def test_extract_agent_outputs(self):
        """Task outputs extract as AGENT_OUTPUT facts (or OUTCOME)."""
        from scripts.agentica_patterns.memory_backfill import (
            extract_facts_from_context,
            FactType,
        )

        context = {
            "ledger": {"outcome": "Successfully implemented feature X"},
            "handoff": {},
        }

        facts = extract_facts_from_context(context, "session-123")
        outcomes = [f for f in facts if f.fact_type == FactType.OUTCOME]

        assert len(outcomes) >= 1
        assert "successfully" in outcomes[0].content.lower()

    def test_extract_file_changes(self):
        """Edit spans extract as FILE_CHANGE facts."""
        from scripts.agentica_patterns.memory_backfill import (
            extract_facts_from_spans,
            FactType,
        )

        # Real Braintrust structure: tool_name in metadata, not span_attributes
        spans = [
            {
                "span_attributes": {"type": "tool", "name": "Write"},
                "metadata": {"tool_name": "Write"},
                "input": {"file_path": "/path/to/file.py"},
            },
        ]

        facts = extract_facts_from_spans(spans, "session-123")
        files = [f for f in facts if f.fact_type == FactType.FILE_CHANGE]

        assert len(files) == 1
        assert "file.py" in files[0].content

    def test_extract_decisions_from_handoff(self):
        """Extracts decisions from handoff."""
        from scripts.agentica_patterns.memory_backfill import (
            extract_facts_from_context,
            FactType,
        )

        context = {
            "ledger": {},
            "handoff": {
                "key_decisions": [
                    "- Use content-hash for deduplication",
                    "- PostgreSQL backend for production",
                ]
            },
        }

        facts = extract_facts_from_context(context, "session-123")
        decisions = [f for f in facts if f.fact_type == FactType.DECISION]

        assert len(decisions) == 2

    def test_extract_error_patterns(self):
        """Extracts error patterns from Bash spans only (not code comments)."""
        from scripts.agentica_patterns.memory_backfill import (
            extract_facts_from_spans,
            FactType,
        )

        # Real Braintrust Bash span structure with structured output
        spans = [
            {
                "span_attributes": {"type": "tool", "name": "Terminal: uv run pytest"},
                "metadata": {"tool_name": "Bash"},
                "input": {"command": "uv run pytest tests/test_foo.py"},
                "output": {
                    "stdout": "ModuleNotFoundError: No module named 'xyz'\nTraceback (most recent call last):\n  File...",
                    "stderr": "",
                    "interrupted": False,
                },
            },
        ]

        facts = extract_facts_from_spans(spans, "session-123")
        errors = [f for f in facts if f.fact_type == FactType.ERROR]

        assert len(errors) >= 1
        # Verify it captured the error context
        assert "ModuleNotFoundError" in errors[0].content

    def test_extract_error_no_false_positives_from_code(self):
        """Error patterns in code comments/docstrings should NOT be extracted."""
        from scripts.agentica_patterns.memory_backfill import (
            extract_facts_from_spans,
            FactType,
        )

        # Read tool output containing "Error:" in code - should NOT match
        spans = [
            {
                "span_attributes": {"type": "tool", "name": "Read"},
                "metadata": {"tool_name": "Read"},
                "output": {
                    "file": {
                        "content": "# Handle Error: ModuleNotFoundError\ndef handle_error(e):\n    pass"
                    }
                },
            },
        ]

        facts = extract_facts_from_spans(spans, "session-123")
        errors = [f for f in facts if f.fact_type == FactType.ERROR]

        # No errors should be extracted from code comments
        assert len(errors) == 0

    def test_no_duplicate_facts_within_session(self):
        """Same content twice in session produces only one fact."""
        from scripts.agentica_patterns.memory_backfill import (
            extract_facts_from_spans,
            FactType,
        )

        # Real Braintrust structure: tool_name in metadata
        spans = [
            {
                "span_attributes": {"type": "tool", "name": "Write"},
                "metadata": {"tool_name": "Write"},
                "input": {"file_path": "/path/to/file.py"},
            },
            {
                "span_attributes": {"type": "tool", "name": "Write"},
                "metadata": {"tool_name": "Write"},
                "input": {"file_path": "/path/to/file.py"},  # duplicate
            },
        ]

        facts = extract_facts_from_spans(spans, "session-123")
        files = [f for f in facts if f.fact_type == FactType.FILE_CHANGE]

        # Should only have 1 unique hash (deduped by content_hash)
        unique_hashes = {f.content_hash for f in files}
        assert len(unique_hashes) == 1


# =============================================================================
# Phase 4: Storage (store_if_novel)
# =============================================================================


class TestStoreIfNovel:
    """Test novel fact detection and storage."""

    @pytest.fixture
    async def memory_service(self, tmp_path):
        """Create a test memory service."""
        from scripts.agentica_patterns.memory_factory import create_memory_service

        return await create_memory_service(
            backend="sqlite",
            session_id="test",
            db_path=tmp_path / "test.db",
        )

    @pytest.mark.asyncio
    async def test_store_if_novel_new_fact(self, memory_service):
        """New hash stores successfully."""
        from scripts.agentica_patterns.memory_backfill import (
            ExtractedFact,
            FactType,
            store_if_novel,
        )

        fact = ExtractedFact(
            content="Decision: Use PostgreSQL",
            fact_type=FactType.DECISION,
            source_session="sess-1",
        )
        # Add mock embedding
        fact.embedding = [0.1] * 1536

        stored_id, was_novel = await store_if_novel(memory_service, fact)

        assert was_novel is True
        assert stored_id is not None

    @pytest.mark.asyncio
    async def test_store_if_novel_duplicate(self, memory_service):
        """Existing hash skips storage."""
        from scripts.agentica_patterns.memory_backfill import (
            ExtractedFact,
            FactType,
            store_if_novel,
        )

        fact = ExtractedFact(
            content="Decision: Use PostgreSQL",
            fact_type=FactType.DECISION,
            source_session="sess-1",
        )
        fact.embedding = [0.1] * 1536

        # Store first time
        _, was_novel_1 = await store_if_novel(memory_service, fact)
        assert was_novel_1 is True

        # Try to store again with same content
        fact2 = ExtractedFact(
            content="Decision: Use PostgreSQL",
            fact_type=FactType.DECISION,
            source_session="sess-1",
        )
        fact2.embedding = [0.1] * 1536

        stored_id, was_novel_2 = await store_if_novel(memory_service, fact2)

        assert was_novel_2 is False
        assert stored_id is None


class TestEmbeddingIntegration:
    """Test embedding generation for facts."""

    @pytest.mark.asyncio
    async def test_embed_facts_batch(self):
        """Should batch-embed multiple facts."""
        from scripts.agentica_patterns.memory_backfill import (
            ExtractedFact,
            FactType,
            embed_facts,
        )
        from scripts.agentica_patterns.embedding_service import EmbeddingService

        service = EmbeddingService(provider="mock")
        facts = [
            ExtractedFact("Fact 1", FactType.LEARNING, "s1"),
            ExtractedFact("Fact 2", FactType.LEARNING, "s1"),
        ]

        embedded = await embed_facts(facts, service)

        assert len(embedded) == 2
        assert all(f.embedding is not None for f in embedded)


# =============================================================================
# Phase 5: CLI Argument Parsing
# =============================================================================


class TestCLI:
    """CLI argument parsing."""

    def test_cli_single_session_mode(self):
        """Should parse single session mode."""
        from scripts.agentica_patterns.memory_backfill import parse_args

        args = parse_args(["--session-id", "abc123"])

        assert args.session_id == "abc123"
        assert args.start_date is None
        assert args.end_date is None

    def test_cli_range_mode(self):
        """Should parse date range mode."""
        from scripts.agentica_patterns.memory_backfill import parse_args

        args = parse_args([
            "--start-date", "2025-12-20",
            "--end-date", "2025-12-27",
            "--batch-size", "20",
        ])

        assert args.start_date == "2025-12-20"
        assert args.end_date == "2025-12-27"
        assert args.batch_size == 20

    def test_cli_resume_mode(self):
        """Should parse resume mode."""
        from scripts.agentica_patterns.memory_backfill import parse_args

        args = parse_args(["--resume"])

        assert args.resume is True

    def test_cli_dry_run_flag(self):
        """Should parse dry-run flag."""
        from scripts.agentica_patterns.memory_backfill import parse_args

        args = parse_args(["--session-id", "abc", "--dry-run"])

        assert args.dry_run is True


# =============================================================================
# Phase 5: Batch Processing
# =============================================================================


class TestBatchProcessing:
    """Batch processing with checkpointing."""

    @pytest.mark.asyncio
    async def test_checkpoint_saves_progress(self, tmp_path):
        """Should save checkpoint after each batch."""
        from scripts.agentica_patterns.memory_backfill import save_checkpoint, load_checkpoint

        checkpoint_path = tmp_path / "checkpoint.json"

        await save_checkpoint(
            checkpoint_path,
            last_session="s1",
            last_timestamp="2025-12-26T10:00:00Z",
            processed_count=5,
        )

        checkpoint = await load_checkpoint(checkpoint_path)

        assert checkpoint["last_session"] == "s1"
        assert checkpoint["processed_count"] == 5

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint(self, tmp_path):
        """Should resume from saved checkpoint."""
        from scripts.agentica_patterns.memory_backfill import (
            save_checkpoint,
            get_resume_point,
        )

        checkpoint_path = tmp_path / "checkpoint.json"

        await save_checkpoint(
            checkpoint_path,
            last_session="s2",
            last_timestamp="2025-12-26T11:00:00Z",
            processed_count=2,
        )

        start_after = await get_resume_point(checkpoint_path)

        assert start_after == "2025-12-26T11:00:00Z"


# =============================================================================
# Full Pipeline Tests (Mocked)
# =============================================================================


class TestFullPipeline:
    """End-to-end pipeline tests with mocks."""

    @pytest.mark.asyncio
    async def test_backfill_single_session_mock(self, tmp_path):
        """Full pipeline for a mocked session."""
        from scripts.agentica_patterns.memory_backfill import backfill_session

        with patch("scripts.agentica_patterns.memory_backfill.fetch_session_spans") as mock_spans, \
             patch("scripts.agentica_patterns.memory_backfill.get_hierarchical_context") as mock_context:

            mock_spans.return_value = [
                {
                    "span_attributes": {"type": "tool", "tool_name": "Write"},
                    "input": {"file_path": "/path/test.py"},
                }
            ]
            mock_context.return_value = {
                "ledger": {"goal": "Build feature X"},
                "handoff": {"key_decisions": ["- Use Python"]},
            }

            result = await backfill_session(
                session_id="test-123",
                project_id="proj-1",
                api_key="key",
                memory_backend="sqlite",
                db_path=tmp_path / "test.db",
                embedding_provider="mock",
            )

            assert result.session_id == "test-123"
            assert result.facts_extracted >= 2  # goal + decision at minimum
            assert len(result.errors) == 0

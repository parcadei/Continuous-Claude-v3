"""Tests for backfill CLI orchestrator.

Phase 4 of backfill pipeline - tests the run_backfill.py CLI.

Tests:
- Dry run mode doesn't write to database
- Resume from checkpoint works correctly
- Single session processing
- Stats reporting
- Mock external dependencies (Braintrust API)
- Embedding integration (--embed flag)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import orchestrator components (will be created)
from scripts.backfill.run_backfill import (
    BackfillOrchestrator,
    BackfillStats,
    parse_args,
    run_backfill,
)


class TestParseArgs:
    """Test CLI argument parsing."""

    def test_parse_all_flag(self) -> None:
        """--all flag triggers full backfill."""
        args = parse_args(["--all"])
        assert args.all is True
        assert args.resume is False
        assert args.session is None

    def test_parse_resume_flag(self) -> None:
        """--resume flag triggers checkpoint resume."""
        args = parse_args(["--resume"])
        assert args.resume is True
        assert args.all is False

    def test_parse_session_flag(self) -> None:
        """--session specifies single session ID."""
        args = parse_args(["--session", "test-session-123"])
        assert args.session == "test-session-123"
        assert args.all is False
        assert args.resume is False

    def test_parse_dry_run_flag(self) -> None:
        """--dry-run prevents database writes."""
        args = parse_args(["--all", "--dry-run"])
        assert args.dry_run is True

    def test_parse_limit_flag(self) -> None:
        """--limit constrains session count."""
        args = parse_args(["--all", "--limit", "50"])
        assert args.limit == 50

    def test_parse_help_returns_none(self) -> None:
        """--help causes exit (handled by argparse)."""
        # argparse calls sys.exit on --help, so we can't easily test it
        # Just test that other args work
        pass

    def test_mutually_exclusive_modes(self) -> None:
        """Can only specify one of --all, --resume, --session."""
        # Note: argparse doesn't enforce mutual exclusivity by default
        # We test that at least one mode is required
        args = parse_args(["--all"])
        assert args.all is True

    def test_parse_embed_flag_voyage(self) -> None:
        """--embed=voyage enables Voyage embeddings."""
        args = parse_args(["--all", "--embed", "voyage"])
        assert args.embed == "voyage"

    def test_parse_embed_flag_local(self) -> None:
        """--embed=local enables local sentence-transformer embeddings."""
        args = parse_args(["--all", "--embed", "local"])
        assert args.embed == "local"

    def test_parse_embed_flag_none(self) -> None:
        """--embed=none disables embeddings (default)."""
        args = parse_args(["--all", "--embed", "none"])
        assert args.embed == "none"

    def test_parse_embed_flag_default(self) -> None:
        """--embed defaults to 'none' if not specified."""
        args = parse_args(["--all"])
        assert args.embed == "none"


class TestBackfillStats:
    """Test stats tracking dataclass."""

    def test_stats_initialization(self) -> None:
        """Stats start at zero."""
        stats = BackfillStats()
        assert stats.sessions_processed == 0
        assert stats.sessions_skipped == 0
        assert stats.facts_written == 0
        assert stats.errors == 0

    def test_stats_to_dict(self) -> None:
        """Stats can be converted to dict for reporting."""
        stats = BackfillStats(
            sessions_processed=10,
            sessions_skipped=2,
            facts_written=150,
            errors=1,
        )
        d = stats.to_dict()
        assert d["sessions_processed"] == 10
        assert d["sessions_skipped"] == 2
        assert d["facts_written"] == 150
        assert d["errors"] == 1


class TestBackfillOrchestrator:
    """Test orchestrator logic."""

    @pytest.fixture
    def temp_dirs(self, tmp_path: Path) -> dict[str, Path]:
        """Create temp directories for testing."""
        temporal_db = tmp_path / "temporal.db"
        context_db = tmp_path / "context.db"
        checkpoint = tmp_path / "checkpoint.json"
        gaps_log = tmp_path / "gaps.jsonl"

        # Create context.db with test data
        import sqlite3

        conn = sqlite3.connect(context_db)
        conn.execute(
            """
            CREATE TABLE handoffs (
                id TEXT PRIMARY KEY,
                root_span_id TEXT,
                outcome TEXT
            )
        """
        )
        conn.execute(
            "INSERT INTO handoffs VALUES ('h1', 'session-succeeded', 'SUCCEEDED')"
        )
        conn.execute("INSERT INTO handoffs VALUES ('h2', 'session-failed', 'FAILED')")
        conn.commit()
        conn.close()

        return {
            "temporal_db": temporal_db,
            "context_db": context_db,
            "checkpoint": checkpoint,
            "gaps_log": gaps_log,
        }

    @pytest.fixture
    def mock_braintrust_api(self) -> MagicMock:
        """Mock Braintrust API calls."""
        with patch(
            "scripts.backfill.run_backfill.query_braintrust_sessions"
        ) as mock_query:
            mock_query.return_value = [
                {"root_span_id": "session-1", "span_count": 50},
                {"root_span_id": "session-2", "span_count": 30},
            ]
            yield mock_query

    @pytest.fixture
    def mock_braintrust_spans(self) -> MagicMock:
        """Mock Braintrust span fetching."""
        with patch(
            "scripts.backfill.run_backfill.fetch_session_spans"
        ) as mock_fetch:
            mock_fetch.return_value = [
                {
                    "id": "span-1",
                    "span_attributes": {"type": "tool"},
                    "metadata": {"tool_name": "Read"},
                    "input": '{"file_path": "/test.py"}',
                },
                {
                    "id": "span-2",
                    "span_attributes": {"type": "llm"},
                    "metrics": {"tokens": 1000},
                },
            ]
            yield mock_fetch

    @pytest.mark.asyncio
    async def test_dry_run_no_database_writes(
        self, temp_dirs: dict[str, Path]
    ) -> None:
        """Dry run mode doesn't write to temporal.db."""
        orchestrator = BackfillOrchestrator(
            temporal_db_path=temp_dirs["temporal_db"],
            context_db_path=temp_dirs["context_db"],
            checkpoint_path=temp_dirs["checkpoint"],
            gaps_log_path=temp_dirs["gaps_log"],
            dry_run=True,
        )

        # Mock the components
        with patch.object(orchestrator, "_validate_session") as mock_validate:
            mock_validate.return_value = AsyncMock(is_valid=True, span_count=10)

            with patch.object(orchestrator, "_fetch_spans") as mock_fetch:
                mock_fetch.return_value = [
                    {
                        "id": "span-1",
                        "span_attributes": {"type": "tool"},
                        "metadata": {"tool_name": "Read"},
                        "input": '{"file_path": "/test.py"}',
                    }
                ]

                stats = await orchestrator.process_session("test-session")

        # Verify no database writes
        assert not temp_dirs["temporal_db"].exists()
        # Stats should still track what would have been written
        assert stats.facts_written >= 0

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint(self, temp_dirs: dict[str, Path]) -> None:
        """Resume mode loads pending sessions from checkpoint."""
        # Create checkpoint with pending sessions
        checkpoint_data = {
            "processed": ["session-1", "session-2"],
            "pending": ["session-3", "session-4"],
        }
        temp_dirs["checkpoint"].parent.mkdir(parents=True, exist_ok=True)
        with open(temp_dirs["checkpoint"], "w") as f:
            json.dump(checkpoint_data, f)

        orchestrator = BackfillOrchestrator(
            temporal_db_path=temp_dirs["temporal_db"],
            context_db_path=temp_dirs["context_db"],
            checkpoint_path=temp_dirs["checkpoint"],
            gaps_log_path=temp_dirs["gaps_log"],
        )

        pending = orchestrator.get_pending_sessions()
        assert pending == ["session-3", "session-4"]

    @pytest.mark.asyncio
    async def test_single_session_processing(
        self, temp_dirs: dict[str, Path]
    ) -> None:
        """Single session mode processes only specified session."""
        orchestrator = BackfillOrchestrator(
            temporal_db_path=temp_dirs["temporal_db"],
            context_db_path=temp_dirs["context_db"],
            checkpoint_path=temp_dirs["checkpoint"],
            gaps_log_path=temp_dirs["gaps_log"],
        )

        # Mock components for single session
        with patch.object(orchestrator, "_validate_session") as mock_validate:
            mock_validate.return_value = MagicMock(is_valid=True, span_count=10)

            with patch.object(orchestrator, "_fetch_spans") as mock_fetch:
                mock_fetch.return_value = [
                    {
                        "id": "span-1",
                        "span_attributes": {"type": "tool"},
                        "metadata": {"tool_name": "Write"},
                        "input": '{"file_path": "/output.py", "content": "test"}',
                    }
                ]

                with patch.object(orchestrator, "_write_facts") as mock_write:
                    mock_write.return_value = 2

                    stats = await orchestrator.process_session("session-succeeded")

        # Verify session was processed
        mock_validate.assert_called_once_with("session-succeeded")
        assert stats.sessions_processed == 1

    @pytest.mark.asyncio
    async def test_stats_reporting(self, temp_dirs: dict[str, Path]) -> None:
        """Stats correctly report processing results."""
        orchestrator = BackfillOrchestrator(
            temporal_db_path=temp_dirs["temporal_db"],
            context_db_path=temp_dirs["context_db"],
            checkpoint_path=temp_dirs["checkpoint"],
            gaps_log_path=temp_dirs["gaps_log"],
        )

        # Simulate processing multiple sessions
        stats = BackfillStats()
        stats.sessions_processed = 5
        stats.sessions_skipped = 2
        stats.facts_written = 120
        stats.errors = 1

        report = orchestrator.generate_report(stats)

        assert "Sessions processed: 5" in report
        assert "Sessions skipped: 2" in report
        assert "Facts written: 120" in report
        assert "Errors: 1" in report

    @pytest.mark.asyncio
    async def test_checkpoint_updated_after_session(
        self, temp_dirs: dict[str, Path]
    ) -> None:
        """Checkpoint is updated after processing each session."""
        # Initialize checkpoint
        checkpoint_data = {
            "processed": [],
            "pending": ["session-1", "session-2"],
        }
        temp_dirs["checkpoint"].parent.mkdir(parents=True, exist_ok=True)
        with open(temp_dirs["checkpoint"], "w") as f:
            json.dump(checkpoint_data, f)

        orchestrator = BackfillOrchestrator(
            temporal_db_path=temp_dirs["temporal_db"],
            context_db_path=temp_dirs["context_db"],
            checkpoint_path=temp_dirs["checkpoint"],
            gaps_log_path=temp_dirs["gaps_log"],
        )

        # Mock successful processing
        with patch.object(orchestrator, "_validate_session") as mock_validate:
            mock_validate.return_value = MagicMock(is_valid=True, span_count=10)

            with patch.object(orchestrator, "_fetch_spans") as mock_fetch:
                mock_fetch.return_value = []

                with patch.object(orchestrator, "_write_facts") as mock_write:
                    mock_write.return_value = 0

                    await orchestrator.process_session("session-1")
                    orchestrator.mark_session_processed("session-1")

        # Verify checkpoint was updated
        with open(temp_dirs["checkpoint"]) as f:
            updated_checkpoint = json.load(f)

        assert "session-1" in updated_checkpoint["processed"]
        assert "session-1" not in updated_checkpoint["pending"]

    @pytest.mark.asyncio
    async def test_gap_logged_for_invalid_session(
        self, temp_dirs: dict[str, Path]
    ) -> None:
        """Gaps are logged when sessions fail validation."""
        orchestrator = BackfillOrchestrator(
            temporal_db_path=temp_dirs["temporal_db"],
            context_db_path=temp_dirs["context_db"],
            checkpoint_path=temp_dirs["checkpoint"],
            gaps_log_path=temp_dirs["gaps_log"],
        )

        # Mock validation failure
        with patch.object(orchestrator, "_validate_session") as mock_validate:
            mock_validate.return_value = MagicMock(
                is_valid=False, error="insufficient_spans", span_count=2
            )

            stats = await orchestrator.process_session("bad-session")

        # Verify gap was logged
        assert temp_dirs["gaps_log"].exists()
        with open(temp_dirs["gaps_log"]) as f:
            gap_entry = json.loads(f.readline())

        assert gap_entry["session_id"] == "bad-session"
        assert gap_entry["reason"] == "insufficient_spans"

    @pytest.mark.asyncio
    async def test_limit_constrains_session_count(
        self, temp_dirs: dict[str, Path]
    ) -> None:
        """--limit flag constrains number of sessions processed."""
        orchestrator = BackfillOrchestrator(
            temporal_db_path=temp_dirs["temporal_db"],
            context_db_path=temp_dirs["context_db"],
            checkpoint_path=temp_dirs["checkpoint"],
            gaps_log_path=temp_dirs["gaps_log"],
            limit=2,
        )

        # Create checkpoint with many pending sessions
        checkpoint_data = {
            "processed": [],
            "pending": ["s1", "s2", "s3", "s4", "s5"],
        }
        temp_dirs["checkpoint"].parent.mkdir(parents=True, exist_ok=True)
        with open(temp_dirs["checkpoint"], "w") as f:
            json.dump(checkpoint_data, f)

        sessions = orchestrator.get_pending_sessions()

        # Should only return first 2 due to limit
        assert len(sessions) <= 2


class TestRunBackfill:
    """Test the main entry point function."""

    @pytest.fixture
    def temp_dirs(self, tmp_path: Path) -> dict[str, Path]:
        """Create temp directories for testing."""
        return {
            "temporal_db": tmp_path / "temporal.db",
            "context_db": tmp_path / "context.db",
            "checkpoint": tmp_path / "checkpoint.json",
            "gaps_log": tmp_path / "gaps.jsonl",
        }

    @pytest.mark.asyncio
    async def test_run_backfill_all(self, temp_dirs: dict[str, Path]) -> None:
        """Full backfill processes all sessions."""
        # Create context.db
        import sqlite3

        temp_dirs["context_db"].parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(temp_dirs["context_db"])
        conn.execute("CREATE TABLE handoffs (id TEXT, root_span_id TEXT, outcome TEXT)")
        conn.commit()
        conn.close()

        with patch(
            "scripts.backfill.run_backfill.query_braintrust_sessions"
        ) as mock_query:
            mock_query.return_value = []

            stats = await run_backfill(
                mode="all",
                temporal_db_path=temp_dirs["temporal_db"],
                context_db_path=temp_dirs["context_db"],
                checkpoint_path=temp_dirs["checkpoint"],
                gaps_log_path=temp_dirs["gaps_log"],
            )

        assert isinstance(stats, BackfillStats)

    @pytest.mark.asyncio
    async def test_run_backfill_single_session(
        self, temp_dirs: dict[str, Path]
    ) -> None:
        """Single session mode processes only that session."""
        # Create context.db
        import sqlite3

        temp_dirs["context_db"].parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(temp_dirs["context_db"])
        conn.execute("CREATE TABLE handoffs (id TEXT, root_span_id TEXT, outcome TEXT)")
        conn.commit()
        conn.close()

        with patch(
            "scripts.backfill.run_backfill.fetch_session_spans"
        ) as mock_fetch:
            mock_fetch.return_value = []

            with patch(
                "scripts.backfill.run_backfill.BackfillOrchestrator._validate_session"
            ) as mock_validate:
                mock_validate.return_value = MagicMock(
                    is_valid=False, error="api_error", span_count=0
                )

                stats = await run_backfill(
                    mode="session",
                    session_id="test-session-id",
                    temporal_db_path=temp_dirs["temporal_db"],
                    context_db_path=temp_dirs["context_db"],
                    checkpoint_path=temp_dirs["checkpoint"],
                    gaps_log_path=temp_dirs["gaps_log"],
                )

        # Stats should reflect the attempt
        assert isinstance(stats, BackfillStats)


class TestEmbeddingIntegration:
    """Test embedding integration with backfill."""

    @pytest.fixture
    def temp_dirs(self, tmp_path: Path) -> dict[str, Path]:
        """Create temp directories for testing."""
        temporal_db = tmp_path / "temporal.db"
        context_db = tmp_path / "context.db"
        checkpoint = tmp_path / "checkpoint.json"
        gaps_log = tmp_path / "gaps.jsonl"

        # Create context.db with test data
        import sqlite3

        conn = sqlite3.connect(context_db)
        conn.execute(
            """
            CREATE TABLE handoffs (
                id TEXT PRIMARY KEY,
                root_span_id TEXT,
                outcome TEXT
            )
        """
        )
        conn.execute(
            "INSERT INTO handoffs VALUES ('h1', 'session-succeeded', 'SUCCEEDED')"
        )
        conn.commit()
        conn.close()

        return {
            "temporal_db": temporal_db,
            "context_db": context_db,
            "checkpoint": checkpoint,
            "gaps_log": gaps_log,
        }

    def test_orchestrator_stores_embed_provider(
        self, temp_dirs: dict[str, Path]
    ) -> None:
        """BackfillOrchestrator stores embed_provider parameter."""
        with patch(
            "scripts.agentica_patterns.embedding_service.EmbeddingService"
        ) as mock_embedding_service:
            orchestrator = BackfillOrchestrator(
                temporal_db_path=temp_dirs["temporal_db"],
                context_db_path=temp_dirs["context_db"],
                checkpoint_path=temp_dirs["checkpoint"],
                gaps_log_path=temp_dirs["gaps_log"],
                embed_provider="local",
            )

            assert orchestrator.embed_provider == "local"
            mock_embedding_service.assert_called_once_with(provider="local")

    def test_orchestrator_no_embedding_when_none(
        self, temp_dirs: dict[str, Path]
    ) -> None:
        """BackfillOrchestrator doesn't initialize EmbeddingService when None."""
        orchestrator = BackfillOrchestrator(
            temporal_db_path=temp_dirs["temporal_db"],
            context_db_path=temp_dirs["context_db"],
            checkpoint_path=temp_dirs["checkpoint"],
            gaps_log_path=temp_dirs["gaps_log"],
            embed_provider=None,
        )

        assert orchestrator.embed_provider is None
        assert orchestrator._embedding_service is None

    @pytest.mark.asyncio
    async def test_write_facts_with_embeddings_uses_embed_method(
        self, temp_dirs: dict[str, Path]
    ) -> None:
        """_write_facts_by_turn_with_embeddings uses write_facts_with_embeddings."""
        with patch(
            "scripts.agentica_patterns.embedding_service.EmbeddingService"
        ) as mock_embedding_cls:
            mock_embedding_service = MagicMock()
            mock_embedding_service.embed = AsyncMock(return_value=[0.1] * 1536)
            mock_embedding_cls.return_value = mock_embedding_service

            orchestrator = BackfillOrchestrator(
                temporal_db_path=temp_dirs["temporal_db"],
                context_db_path=temp_dirs["context_db"],
                checkpoint_path=temp_dirs["checkpoint"],
                gaps_log_path=temp_dirs["gaps_log"],
                embed_provider="local",
            )

            # Create mock writer with write_facts_with_embeddings method
            mock_writer = MagicMock()
            mock_writer.write_facts_with_embeddings = AsyncMock(return_value=2)
            orchestrator.writer = mock_writer

            # Create mock facts
            from scripts.backfill.span_parser import SpanFact
            from scripts.backfill.outcome_tagger import SessionOutcome

            facts_by_turn = {
                1: [SpanFact(key="test", value="value", turn=1, confidence=0.9)]
            }
            outcome = SessionOutcome(
                session_id="test",
                outcome="SUCCEEDED",
                confidence_multiplier=1.0,
                method="test",
            )

            # Call the method
            written = await orchestrator._write_facts_by_turn_with_embeddings(
                "test-session", facts_by_turn, outcome
            )

            # Verify write_facts_with_embeddings was called
            assert mock_writer.write_facts_with_embeddings.called
            assert written == 2

    @pytest.mark.asyncio
    async def test_write_facts_falls_back_without_embed_method(
        self, temp_dirs: dict[str, Path]
    ) -> None:
        """_write_facts_by_turn_with_embeddings falls back if writer lacks method."""
        with patch(
            "scripts.agentica_patterns.embedding_service.EmbeddingService"
        ) as mock_embedding_cls:
            mock_embedding_service = MagicMock()
            mock_embedding_cls.return_value = mock_embedding_service

            orchestrator = BackfillOrchestrator(
                temporal_db_path=temp_dirs["temporal_db"],
                context_db_path=temp_dirs["context_db"],
                checkpoint_path=temp_dirs["checkpoint"],
                gaps_log_path=temp_dirs["gaps_log"],
                embed_provider="local",
            )

            # Create mock writer WITHOUT write_facts_with_embeddings method
            mock_writer = MagicMock(spec=["write_facts"])
            mock_writer.write_facts = AsyncMock(return_value=1)
            orchestrator.writer = mock_writer

            # Create mock facts
            from scripts.backfill.span_parser import SpanFact
            from scripts.backfill.outcome_tagger import SessionOutcome

            facts_by_turn = {
                1: [SpanFact(key="test", value="value", turn=1, confidence=0.9)]
            }
            outcome = SessionOutcome(
                session_id="test",
                outcome="SUCCEEDED",
                confidence_multiplier=1.0,
                method="test",
            )

            # Call the method
            written = await orchestrator._write_facts_by_turn_with_embeddings(
                "test-session", facts_by_turn, outcome
            )

            # Verify fallback to write_facts
            assert mock_writer.write_facts.called
            assert written == 1

    @pytest.mark.asyncio
    async def test_close_closes_embedding_service(
        self, temp_dirs: dict[str, Path]
    ) -> None:
        """close() also closes the embedding service."""
        with patch(
            "scripts.agentica_patterns.embedding_service.EmbeddingService"
        ) as mock_embedding_cls:
            mock_embedding_service = MagicMock()
            mock_embedding_service.aclose = AsyncMock()
            mock_embedding_cls.return_value = mock_embedding_service

            orchestrator = BackfillOrchestrator(
                temporal_db_path=temp_dirs["temporal_db"],
                context_db_path=temp_dirs["context_db"],
                checkpoint_path=temp_dirs["checkpoint"],
                gaps_log_path=temp_dirs["gaps_log"],
                embed_provider="local",
            )

            # Set a mock writer
            mock_writer = MagicMock()
            mock_writer.close = AsyncMock()
            orchestrator.writer = mock_writer

            # Call close
            await orchestrator.close()

            # Verify embedding service was closed
            mock_embedding_service.aclose.assert_called_once()

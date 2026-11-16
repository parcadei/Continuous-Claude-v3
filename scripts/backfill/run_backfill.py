#!/usr/bin/env python3
"""Run the backfill pipeline.

Phase 4 of backfill implementation - CLI orchestrator that ties together
all Phase 3 components.

Usage:
    # Full backfill (all unprocessed sessions)
    uv run python scripts/backfill/run_backfill.py --all

    # Resume interrupted backfill
    uv run python scripts/backfill/run_backfill.py --resume

    # Single session (for testing)
    uv run python scripts/backfill/run_backfill.py --session <session-id>

    # Dry run (validate only, no database writes)
    uv run python scripts/backfill/run_backfill.py --all --dry-run

    # With limits
    uv run python scripts/backfill/run_backfill.py --all --limit 50

Components orchestrated:
- SessionValidator: Validate session has sufficient data
- SpanParser: Extract facts from spans
- TurnInference: Determine turn boundaries
- OutcomeTagger: Link to context.db outcomes
- TemporalWriter: Write to temporal.db
- GapLogger: Track skipped sessions
- CheckpointManager: Resume interrupted backfills
- CalibrationAnalyzer: Analyze fact-outcome correlations
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Add the project root to PYTHONPATH to allow importing from 'scripts'
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from typing import Any, Sequence

import requests

# Import all Phase 3 components
from scripts.backfill.calibration import CalibrationAnalyzer
from scripts.backfill.checkpoint import CheckpointManager
from scripts.backfill.gap_logger import GapLogger, GapReason
from scripts.backfill.outcome_tagger import OutcomeTagger, SessionOutcome
from scripts.backfill.session_validator import SessionValidator, ValidationResult
from scripts.backfill.span_parser import SpanFact, SpanParser
from scripts.backfill.turn_inference import TurnInference, TurnResult

# Phase 3.4: Import factory for backend-agnostic writer creation
from scripts.temporal_memory.factory import (
    create_temporal_writer,
    get_temporal_backend,
)
from scripts.temporal_memory.protocol import TemporalWriterProtocol


@dataclass
class BackfillStats:
    """Statistics from backfill run."""

    sessions_processed: int = 0
    sessions_skipped: int = 0
    facts_written: int = 0
    traces_written: int = 0
    errors: int = 0
    calibration_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "sessions_processed": self.sessions_processed,
            "sessions_skipped": self.sessions_skipped,
            "facts_written": self.facts_written,
            "traces_written": self.traces_written,
            "errors": self.errors,
            "calibration_run": self.calibration_run,
        }


def query_braintrust_sessions(limit: int | None = None) -> list[dict[str, Any]]:
    """Query Braintrust for all sessions with their root_span_ids.

    Args:
        limit: Maximum number of sessions to return

    Returns:
        List of session dicts with root_span_id and metadata
    """
    api_key = _load_api_key()
    project_name = os.environ.get("BRAINTRUST_PROJECT", "agentica")
    project_id = _get_project_id(project_name, api_key)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # Query for unique sessions with span counts using BTQL native syntax
    # Note: BTQL doesn't support HAVING - we filter in Python instead
    # Fetch extra to account for filtering (3x or at least 500)
    fetch_limit = max(500, (limit or 100) * 3)
    query = f"""
        dimensions: root_span_id
        measures:
            count(1) as span_count,
            min(created) as first_span,
            max(created) as last_span
        from: project_logs('{project_id}')
        filter: root_span_id IS NOT NULL
        sort: first_span desc
        limit: {fetch_limit}
    """

    resp = requests.post(
        "https://api.braintrust.dev/btql",
        headers=headers,
        json={"query": query, "fmt": "json"},
        timeout=60,
    )

    if resp.status_code != 200:
        raise Exception(f"Braintrust API error: {resp.status_code} - {resp.text[:200]}")

    data = resp.json().get("data", [])

    # Filter for sessions with at least 5 spans (replaces HAVING clause)
    # and apply the user's requested limit
    results = [
        {
            "root_span_id": row["root_span_id"],
            "span_count": int(row["span_count"]),
            "first_span": row.get("first_span"),
            "last_span": row.get("last_span"),
        }
        for row in data
        if int(row["span_count"]) >= 5
    ]

    # Apply user limit after filtering
    if limit:
        results = results[:limit]

    return results


def fetch_session_spans(session_id: str) -> list[dict[str, Any]]:
    """Fetch all spans for a session from Braintrust.

    Args:
        session_id: The root_span_id of the session

    Returns:
        List of span dictionaries
    """
    api_key = _load_api_key()
    project_name = os.environ.get("BRAINTRUST_PROJECT", "agentica")
    project_id = _get_project_id(project_name, api_key)

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    query = f"""
        SELECT
            span_id as id,
            span_attributes,
            metadata,
            input,
            output,
            metrics,
            created
        FROM project_logs('{project_id}')
        WHERE root_span_id = '{session_id}'
        ORDER BY created ASC
    """

    resp = requests.post(
        "https://api.braintrust.dev/btql",
        headers=headers,
        json={"query": query, "fmt": "json"},
        timeout=120,
    )

    if resp.status_code != 200:
        raise Exception(f"Braintrust API error: {resp.status_code} - {resp.text[:200]}")

    data: list[dict[str, Any]] = resp.json().get("data", [])
    return data


def _load_api_key() -> str:
    """Load Braintrust API key from environment or .env file."""
    api_key = os.environ.get("BRAINTRUST_API_KEY")
    if api_key:
        return api_key

    # Try loading from .env files
    for path in [Path.home() / ".claude", Path.cwd(), *Path.cwd().parents]:
        env_file = path / ".env"
        if env_file.exists():
            with open(env_file) as f:
                for line in f:
                    if line.startswith("BRAINTRUST_API_KEY="):
                        key = line.strip().split("=", 1)[1].strip("\"'")
                        os.environ["BRAINTRUST_API_KEY"] = key
                        return key

    raise Exception("BRAINTRUST_API_KEY not found in environment or .env files")


def _get_project_id(project_name: str, api_key: str) -> str:
    """Get Braintrust project ID from name."""
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(
        "https://api.braintrust.dev/v1/project",
        headers=headers,
        params={"project_name": project_name},
        timeout=10,
    )

    if resp.status_code == 200:
        projects: list[dict[str, Any]] = resp.json().get("objects", [])
        if projects:
            project_id: str = projects[0]["id"]
            return project_id

    # Try listing all projects and matching by name
    resp = requests.get(
        "https://api.braintrust.dev/v1/project", headers=headers, timeout=10
    )
    if resp.status_code == 200:
        all_projects: list[dict[str, Any]] = resp.json().get("objects", [])
        for p in all_projects:
            if p.get("name", "").lower() == project_name.lower():
                matched_id: str = p["id"]
                return matched_id

    raise Exception(f"Project '{project_name}' not found")


class BackfillOrchestrator:
    """Orchestrates the backfill pipeline.

    Coordinates all Phase 3 components to:
    1. Validate sessions
    2. Fetch and parse spans
    3. Infer turns
    4. Tag outcomes
    5. Write to temporal.db
    6. Log gaps
    7. Update checkpoint
    """

    def __init__(
        self,
        temporal_db_path: Path | None = None,
        context_db_path: Path | None = None,
        checkpoint_path: Path | None = None,
        gaps_log_path: Path | None = None,
        dry_run: bool = False,
        limit: int | None = None,
        embed_provider: str | None = None,
        embed_model: str | None = None,
    ):
        """Initialize orchestrator.

        Args:
            temporal_db_path: Path to temporal.db
            context_db_path: Path to context.db
            checkpoint_path: Path to checkpoint.json
            gaps_log_path: Path to gaps.jsonl
            dry_run: If True, don't write to database
            limit: Maximum number of sessions to process
            embed_provider: Embedding provider ("voyage", "local", or None)
            embed_model: Embedding model name (e.g., "voyage-code-3")
        """
        self.temporal_db_path = temporal_db_path or Path(
            ".claude/cache/temporal-memory/temporal.db"
        )
        self.context_db_path = context_db_path or Path(
            ".claude/cache/artifact-index/context.db"
        )
        self.checkpoint_path = checkpoint_path or Path(
            ".claude/cache/backfill-checkpoint.json"
        )
        self.gaps_log_path = gaps_log_path or Path(".claude/cache/backfill-gaps.jsonl")

        self.dry_run = dry_run
        self.limit = limit
        self.embed_provider = embed_provider
        self.embed_model = embed_model

        # Initialize embedding service if enabled
        self._embedding_service = None
        if self.embed_provider:
            from scripts.agentica_patterns.embedding_service import EmbeddingService

            self._embedding_service = EmbeddingService(
                provider=self.embed_provider,
                model=self.embed_model,
            )

        # Initialize components
        self.validator = SessionValidator(temporal_db_path=str(self.temporal_db_path))
        self.parser = SpanParser()
        self.turn_inference = TurnInference()
        self.outcome_tagger = OutcomeTagger(context_db_path=self.context_db_path)
        # Phase 3.4: Writer is created via factory in initialize()
        self.writer: TemporalWriterProtocol | None = None
        self.gap_logger = GapLogger(log_path=self.gaps_log_path)
        self.checkpoint_manager = CheckpointManager(checkpoint_path=self.checkpoint_path)
        self.calibration_analyzer = CalibrationAnalyzer(
            temporal_db=self.temporal_db_path,
            context_db=self.context_db_path,
        )

    async def initialize(self) -> None:
        """Initialize database connections.

        Phase 3.4: Uses factory to create backend based on TEMPORAL_BACKEND env var.
        Defaults to SQLite for backwards compatibility.
        """
        if not self.dry_run:
            # Phase 3.4: Use factory for backend-agnostic writer creation
            backend = get_temporal_backend()
            self.writer = await create_temporal_writer(
                backend=backend,
                db_path=self.temporal_db_path if backend == "sqlite" else None,
            )

    async def close(self) -> None:
        """Close database connections and embedding service."""
        if self.writer is not None:
            await self.writer.close()
        if self._embedding_service is not None:
            await self._embedding_service.aclose()

    def get_pending_sessions(self) -> list[str]:
        """Get list of pending sessions from checkpoint.

        Returns:
            List of session IDs to process
        """
        state = self.checkpoint_manager.load()
        pending: list[str] = state.get("pending", [])

        if self.limit is not None:
            return pending[: self.limit]
        return pending

    def mark_session_processed(self, session_id: str) -> None:
        """Mark a session as processed in checkpoint."""
        self.checkpoint_manager.mark_processed(session_id)

    async def _validate_session(self, session_id: str) -> ValidationResult:
        """Validate session for processing."""
        return await self.validator.validate(session_id, min_spans=5)

    async def _fetch_spans(self, session_id: str) -> list[dict[str, Any]]:
        """Fetch spans from Braintrust."""
        return fetch_session_spans(session_id)

    async def _write_facts(
        self,
        session_id: str,
        facts: list[SpanFact],
        outcome: SessionOutcome,
    ) -> int:
        """Write facts to temporal.db."""
        if self.writer is None:
            return 0
        return await self.writer.write_facts(session_id, facts, outcome)

    async def _write_facts_by_turn_with_embeddings(
        self,
        session_id: str,
        facts_by_turn: dict[int, list[SpanFact]],
        outcome: SessionOutcome,
    ) -> int:
        """Write facts with embeddings, grouped by turn.

        Uses write_facts_with_embeddings when embedding is enabled and
        the writer supports it (PostgreSQL). Falls back to regular
        write_facts otherwise.

        Args:
            session_id: Root span ID of the session
            facts_by_turn: Dictionary mapping turn number to list of facts
            outcome: SessionOutcome with confidence multiplier

        Returns:
            Number of facts written (excluding duplicates)
        """
        if self.writer is None:
            return 0

        # Check if writer supports embeddings and we have an embedding service
        has_embed_method = hasattr(self.writer, "write_facts_with_embeddings")

        if self._embedding_service is not None and has_embed_method:
            # Create sync wrapper for embedding function
            # write_facts_with_embeddings expects (text: str) -> list[float]
            async def embed_fn(text: str) -> list[float]:
                return await self._embedding_service.embed(text)

            total_written = 0
            for turn, turn_facts in facts_by_turn.items():
                written = await self.writer.write_facts_with_embeddings(
                    session_id=session_id,
                    turn=turn,
                    facts=turn_facts,
                    outcome=outcome,
                    embedding_fn=embed_fn,
                )
                total_written += written
            return total_written
        else:
            # Fall back to regular write_facts (flatten all facts)
            all_facts = []
            for turn_facts in facts_by_turn.values():
                all_facts.extend(turn_facts)
            return await self.writer.write_facts(session_id, all_facts, outcome)

    async def _write_traces(
        self,
        session_id: str,
        facts_by_turn: dict[int, list[SpanFact]],
        outcome: SessionOutcome,
    ) -> int:
        """Write traces to temporal.db."""
        if self.writer is None:
            return 0
        return await self.writer.write_traces(session_id, facts_by_turn, outcome)

    async def process_session(self, session_id: str) -> BackfillStats:
        """Process a single session through the pipeline.

        Args:
            session_id: Root span ID of the session

        Returns:
            BackfillStats for this session
        """
        stats = BackfillStats()

        # Step 1: Validate session
        validation = await self._validate_session(session_id)
        if not validation.is_valid:
            # Log gap and skip
            reason = self._error_to_gap_reason(validation.error)
            self.gap_logger.log_gap(
                session_id,
                reason,
                error=validation.error,
                span_count=validation.span_count,
            )
            stats.sessions_skipped += 1
            return stats

        # Step 2: Fetch spans from Braintrust
        try:
            spans = await self._fetch_spans(session_id)
        except Exception as e:
            self.gap_logger.log_gap(
                session_id, GapReason.API_ERROR, error_message=str(e)[:200]
            )
            stats.errors += 1
            return stats

        # Step 3: Parse spans into facts
        all_facts: list[SpanFact] = []
        has_handoff_skill = False
        has_commit_skill = False

        for span in spans:
            facts = self.parser.parse_span(span, turn=1)  # Turn will be inferred
            all_facts.extend(facts)

            # Check for skill activations
            for fact in facts:
                if fact.key == "skill_activated":
                    if fact.value == "create_handoff":
                        has_handoff_skill = True
                    elif fact.value == "commit":
                        has_commit_skill = True

        # Step 4: Infer turns
        turn_result = self.turn_inference.infer_turns(spans)

        # Assign turn numbers to facts based on turn_result
        facts_by_turn = self._assign_turns_to_facts(all_facts, spans, turn_result)

        # Flatten for writing
        all_facts_with_turns: list[SpanFact] = []
        for turn_num, turn_facts in facts_by_turn.items():
            for fact in turn_facts:
                fact.turn = turn_num
                all_facts_with_turns.append(fact)

        # Step 5: Tag outcome
        outcome = self.outcome_tagger.tag(
            session_id,
            has_handoff_skill=has_handoff_skill,
            has_commit_skill=has_commit_skill,
        )

        # Step 6: Write to temporal.db (unless dry_run)
        if not self.dry_run:
            # Use embedding-aware write if embedding is enabled
            if self.embed_provider:
                facts_written = await self._write_facts_by_turn_with_embeddings(
                    session_id, facts_by_turn, outcome
                )
            else:
                facts_written = await self._write_facts(
                    session_id, all_facts_with_turns, outcome
                )
            traces_written = await self._write_traces(session_id, facts_by_turn, outcome)
            stats.facts_written += facts_written
            stats.traces_written += traces_written
        else:
            # In dry run, still track what would be written
            stats.facts_written += len(all_facts_with_turns)
            stats.traces_written += len(facts_by_turn)

        stats.sessions_processed += 1
        return stats

    def _assign_turns_to_facts(
        self,
        facts: list[SpanFact],
        spans: list[dict[str, Any]],
        turn_result: TurnResult,
    ) -> dict[int, list[SpanFact]]:
        """Assign turn numbers to facts based on turn inference.

        Args:
            facts: List of all extracted facts
            spans: Original spans from Braintrust
            turn_result: Result from TurnInference

        Returns:
            Dict mapping turn number to list of facts
        """
        # Build span_id to turn mapping
        span_to_turn: dict[str, int] = {}
        for turn_num, span_ids in turn_result.turns.items():
            for span_id in span_ids:
                span_to_turn[span_id] = turn_num

        # Assign facts to turns
        facts_by_turn: dict[int, list[SpanFact]] = {}
        for fact in facts:
            turn_num = span_to_turn.get(fact.span_id or "", 1)
            if turn_num not in facts_by_turn:
                facts_by_turn[turn_num] = []
            facts_by_turn[turn_num].append(fact)

        # Handle facts without span_id (fallback to turn 1)
        if 1 not in facts_by_turn:
            facts_by_turn[1] = []

        return facts_by_turn

    def _error_to_gap_reason(self, error: str | None) -> GapReason:
        """Convert validation error string to GapReason enum."""
        if error is None:
            return GapReason.PARSE_ERROR
        if "insufficient_spans" in error:
            return GapReason.INSUFFICIENT_SPANS
        if "already_processed" in error:
            return GapReason.ALREADY_PROCESSED
        if "api_error" in error:
            return GapReason.API_ERROR
        if "timeout" in error.lower():
            return GapReason.TIMEOUT
        return GapReason.PARSE_ERROR

    def generate_report(self, stats: BackfillStats) -> str:
        """Generate human-readable report.

        Args:
            stats: BackfillStats from processing

        Returns:
            Formatted report string
        """
        lines = [
            "=" * 50,
            "Backfill Pipeline Report",
            "=" * 50,
            "",
            f"Sessions processed: {stats.sessions_processed}",
            f"Sessions skipped: {stats.sessions_skipped}",
            f"Facts written: {stats.facts_written}",
            f"Traces written: {stats.traces_written}",
            f"Errors: {stats.errors}",
            "",
        ]

        if stats.calibration_run:
            lines.append("Calibration analysis completed.")
            lines.append("")

        # Add gap summary
        gap_summary = self.gap_logger.get_summary()
        if gap_summary["total"] > 0:
            lines.append("Gap Summary:")
            for reason, count in gap_summary["by_reason"].items():
                lines.append(f"  {reason}: {count}")
            lines.append("")

        lines.append("=" * 50)
        return "\n".join(lines)


async def run_backfill(
    mode: str,
    session_id: str | None = None,
    temporal_db_path: Path | None = None,
    context_db_path: Path | None = None,
    checkpoint_path: Path | None = None,
    gaps_log_path: Path | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    run_calibration: bool = True,
    embed_provider: str | None = None,
    embed_model: str | None = None,
) -> BackfillStats:
    """Run the backfill pipeline.

    Args:
        mode: One of "all", "resume", or "session"
        session_id: Required if mode is "session"
        temporal_db_path: Path to temporal.db
        context_db_path: Path to context.db
        checkpoint_path: Path to checkpoint.json
        gaps_log_path: Path to gaps.jsonl
        dry_run: If True, don't write to database
        limit: Maximum number of sessions to process
        run_calibration: If True, run calibration analysis after backfill
        embed_provider: Embedding provider ("voyage", "local", or None)
        embed_model: Embedding model name (e.g., "voyage-code-3")

    Returns:
        BackfillStats with processing results
    """
    orchestrator = BackfillOrchestrator(
        temporal_db_path=temporal_db_path,
        context_db_path=context_db_path,
        checkpoint_path=checkpoint_path,
        gaps_log_path=gaps_log_path,
        dry_run=dry_run,
        limit=limit,
        embed_provider=embed_provider,
        embed_model=embed_model,
    )

    await orchestrator.initialize()

    try:
        total_stats = BackfillStats()

        if mode == "session" and session_id:
            # Process single session
            stats = await orchestrator.process_session(session_id)
            total_stats.sessions_processed += stats.sessions_processed
            total_stats.sessions_skipped += stats.sessions_skipped
            total_stats.facts_written += stats.facts_written
            total_stats.traces_written += stats.traces_written
            total_stats.errors += stats.errors

        elif mode == "resume":
            # Resume from checkpoint
            pending = orchestrator.get_pending_sessions()
            print(f"Resuming backfill with {len(pending)} pending sessions")

            for i, sess_id in enumerate(pending):
                print(f"  [{i + 1}/{len(pending)}] Processing {sess_id[:12]}...")
                stats = await orchestrator.process_session(sess_id)
                total_stats.sessions_processed += stats.sessions_processed
                total_stats.sessions_skipped += stats.sessions_skipped
                total_stats.facts_written += stats.facts_written
                total_stats.traces_written += stats.traces_written
                total_stats.errors += stats.errors

                if stats.sessions_processed > 0 and not dry_run:
                    orchestrator.mark_session_processed(sess_id)

        elif mode == "all":
            # Full backfill
            print("Querying Braintrust for sessions...")
            sessions = query_braintrust_sessions(limit=limit)
            print(f"Found {len(sessions)} sessions to process")

            # Initialize checkpoint with all sessions
            already_processed = set(
                orchestrator.checkpoint_manager.load().get("processed", [])
            )
            pending = [
                s["root_span_id"]
                for s in sessions
                if s["root_span_id"] not in already_processed
            ]

            if pending and not dry_run:
                orchestrator.checkpoint_manager.save(
                    processed=list(already_processed),
                    pending=pending,
                )

            print(f"Processing {len(pending)} new sessions...")

            for i, sess_id in enumerate(pending):
                print(f"  [{i + 1}/{len(pending)}] Processing {sess_id[:12]}...")
                stats = await orchestrator.process_session(sess_id)
                total_stats.sessions_processed += stats.sessions_processed
                total_stats.sessions_skipped += stats.sessions_skipped
                total_stats.facts_written += stats.facts_written
                total_stats.traces_written += stats.traces_written
                total_stats.errors += stats.errors

                if stats.sessions_processed > 0 and not dry_run:
                    orchestrator.mark_session_processed(sess_id)

        # Run calibration analysis if requested
        if run_calibration and not dry_run:
            print("\nRunning calibration analysis...")
            calibration_report = orchestrator.calibration_analyzer.analyze()
            total_stats.calibration_run = True

            if calibration_report["sessions_analyzed"] > 0:
                print(
                    f"  Analyzed {calibration_report['sessions_analyzed']} sessions"
                )
                print(
                    f"  Found {len(calibration_report['success_patterns'])} success patterns"
                )
                print(
                    f"  Found {len(calibration_report['failure_patterns'])} failure patterns"
                )

        # Generate and print report
        report = orchestrator.generate_report(total_stats)
        print("\n" + report)

        return total_stats

    finally:
        await orchestrator.close()


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.

    Args:
        args: Command line arguments (defaults to sys.argv)

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Run the backfill pipeline for temporal memory.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Full backfill (all unprocessed sessions)
    uv run python scripts/backfill/run_backfill.py --all

    # Resume interrupted backfill
    uv run python scripts/backfill/run_backfill.py --resume

    # Single session (for testing)
    uv run python scripts/backfill/run_backfill.py --session abc123

    # Dry run (validate only)
    uv run python scripts/backfill/run_backfill.py --all --dry-run

    # With limits
    uv run python scripts/backfill/run_backfill.py --all --limit 50

    # With embeddings (PostgreSQL backend)
    TEMPORAL_BACKEND=postgres uv run python scripts/backfill/run_backfill.py --all --embed=local
    TEMPORAL_BACKEND=postgres uv run python scripts/backfill/run_backfill.py --all --embed=voyage

    # With specific embedding model
    TEMPORAL_BACKEND=postgres uv run python scripts/backfill/run_backfill.py --all --embed=voyage --embed-model=voyage-code-3
        """,
    )

    # Mode selection (mutually exclusive in practice)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--all",
        action="store_true",
        help="Process all unprocessed sessions",
    )
    mode_group.add_argument(
        "--resume",
        action="store_true",
        help="Resume from checkpoint (process pending sessions)",
    )
    mode_group.add_argument(
        "--session",
        type=str,
        help="Process a single session by root_span_id",
    )

    # Options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only, don't write to database",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of sessions to process",
    )
    parser.add_argument(
        "--no-calibration",
        action="store_true",
        help="Skip calibration analysis after backfill",
    )
    parser.add_argument(
        "--temporal-db",
        type=Path,
        help="Path to temporal.db (default: .claude/cache/temporal-memory/temporal.db)",
    )
    parser.add_argument(
        "--context-db",
        type=Path,
        help="Path to context.db (default: .claude/cache/artifact-index/context.db)",
    )
    parser.add_argument(
        "--embed",
        choices=["voyage", "local", "none"],
        default="none",
        help="Embedding provider for fact embeddings (default: none). "
        "Use 'voyage' for Voyage AI (requires VOYAGE_API_KEY), "
        "'local' for sentence-transformers (requires torch), "
        "or 'none' to skip embedding generation.",
    )
    parser.add_argument(
        "--embed-model",
        type=str,
        default=None,
        help="Embedding model name. Voyage: voyage-3, voyage-code-3, voyage-3-large. "
        "Local: all-MiniLM-L6-v2, all-mpnet-base-v2. If not set, uses provider default.",
    )

    return parser.parse_args(args)


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    args = parse_args()

    # Determine mode
    if args.all:
        mode = "all"
        session_id = None
    elif args.resume:
        mode = "resume"
        session_id = None
    else:
        mode = "session"
        session_id = args.session

    # Convert embed choice to provider (None if "none")
    embed_provider = None if args.embed == "none" else args.embed
    embed_model = getattr(args, "embed_model", None)

    try:
        stats = asyncio.run(
            run_backfill(
                mode=mode,
                session_id=session_id,
                temporal_db_path=args.temporal_db,
                context_db_path=args.context_db,
                dry_run=args.dry_run,
                limit=args.limit,
                run_calibration=not args.no_calibration,
                embed_provider=embed_provider,
                embed_model=embed_model,
            )
        )

        # Return error code if there were errors
        return 1 if stats.errors > 0 else 0

    except KeyboardInterrupt:
        print("\nInterrupted by user. Progress saved to checkpoint.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

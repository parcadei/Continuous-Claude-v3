"""Temporal memory Protocol definitions.

Phase 3.4 of PostgreSQL migration - Protocol definitions for temporal memory.

Defines the contracts that all temporal memory backends must implement.
Uses Protocol for structural typing (duck typing with type checking).

Both SQLite and PostgreSQL implementations satisfy these protocols.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from scripts.backfill.outcome_tagger import SessionOutcome
    from scripts.backfill.span_parser import SpanFact
    from scripts.temporal_memory.inertia import RevisionEvent, RevisionPriority


class TemporalWriterProtocol(Protocol):
    """Protocol for temporal writer backends.

    Defines the async interface for writing facts extracted from Braintrust spans.
    Used by the backfill pipeline.

    Backends implementing this protocol:
    - SQLite (scripts.backfill.temporal_writer.TemporalWriter)
    - PostgreSQL (scripts.backfill.temporal_writer_pg.TemporalWriterPG)
    """

    async def connect(self) -> None:
        """Initialize connection and schema.

        Should be idempotent - safe to call multiple times.
        For pool-based backends, this may be a no-op.

        Raises:
            ConnectionError: If connection fails
        """
        ...

    async def close(self) -> None:
        """Close connection and cleanup resources.

        Should be idempotent - safe to call multiple times.
        For pool-based backends, this may be a no-op.
        """
        ...

    async def write_facts(
        self,
        session_id: str,
        facts: list[SpanFact],
        outcome: SessionOutcome,
    ) -> int:
        """Write facts with calibrated confidence.

        Args:
            session_id: Root span ID of the session
            facts: List of SpanFact objects to write
            outcome: SessionOutcome with confidence multiplier

        Returns:
            Number of facts written (excluding duplicates)

        Raises:
            RuntimeError: If not connected
            ConnectionError: If database unavailable
        """
        ...

    async def write_traces(
        self,
        session_id: str,
        facts_by_turn: dict[int, list[SpanFact]],
        outcome: SessionOutcome,
    ) -> int:
        """Write turn-level trace snapshots.

        Args:
            session_id: Root span ID of the session
            facts_by_turn: Dictionary mapping turn number to list of facts
            outcome: SessionOutcome with confidence multiplier

        Returns:
            Number of trace entries written

        Raises:
            RuntimeError: If not connected
            ConnectionError: If database unavailable
        """
        ...

    async def get_facts(self, session_id: str) -> list[dict[str, Any]]:
        """Get all facts for a session.

        Args:
            session_id: Root span ID of the session

        Returns:
            List of fact dictionaries

        Raises:
            RuntimeError: If not connected
            ConnectionError: If database unavailable
        """
        ...

    async def get_traces(self, session_id: str) -> list[dict[str, Any]]:
        """Get all traces for a session.

        Args:
            session_id: Root span ID of the session

        Returns:
            List of trace dictionaries

        Raises:
            RuntimeError: If not connected
            ConnectionError: If database unavailable
        """
        ...


class TemporalStoreProtocol(Protocol):
    """Protocol for temporal memory store backends.

    Defines the async interface for session-scoped temporal fact storage.
    Used for interactive fact tracking during sessions.

    Backends implementing this protocol:
    - SQLite (scripts.temporal_memory.store.TemporalMemoryStore)
    - PostgreSQL (scripts.temporal_memory.store_pg.TemporalMemoryStorePG)
    """

    session_id: str
    """Unique identifier for this session."""

    async def connect(self) -> None:
        """Initialize connection and restore state.

        Should be idempotent - safe to call multiple times.
        Restores current turn from database to maintain continuity.

        Raises:
            ConnectionError: If connection fails
        """
        ...

    async def record(self, turn: int, facts: dict[str, Any]) -> None:
        """Record facts at a turn.

        Stores facts in both trace table (for historical playback)
        and facts table (for current state tracking).
        Automatically tracks when facts change.

        Args:
            turn: Turn number for this recording
            facts: Dictionary of key-value facts to record

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    async def get_trace(self) -> list[dict[str, Any]]:
        """Get full temporal trace ordered by turn.

        Returns:
            List of trace entries, each containing:
            - turn: Turn number
            - facts: Facts recorded at that turn
            - erotetic: E(X,Q) data if available

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    async def get_current_state(self) -> dict[str, Any]:
        """Get current values of all facts.

        Returns:
            Dictionary mapping fact keys to their current values

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    async def get_invariants(self) -> dict[str, Any]:
        """Get facts that never changed (change_count == 0).

        Returns:
            Dictionary mapping invariant fact keys to their values

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    async def record_with_erotetic(
        self, turn: int, facts: dict[str, Any]
    ) -> dict[str, Any]:
        """Record facts and compute E(X,Q) evocation.

        Args:
            turn: Turn number
            facts: Dictionary of key-value facts

        Returns:
            Evocation result: {"isEmpty": bool, "unknowns": list, "count": int}

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    async def get_open_questions(self, turn: int | None = None) -> list[str]:
        """Get E(X,Q) unknowns at a turn.

        Args:
            turn: Specific turn number, or None for latest

        Returns:
            List of unknown proposition names

        Raises:
            ConnectionError: If database unavailable
        """
        ...

    async def advance_turn(
        self,
        updates: dict[str, Any],
        priority: RevisionPriority = ...,
    ) -> list[RevisionEvent]:
        """Advance to next turn with updates.

        Applies inertia rule: persisted facts + updates.
        Returns any revision events (conflicts resolved).

        Args:
            updates: Dictionary of key-value pairs to update
            priority: Priority level for the updates

        Returns:
            List of RevisionEvent objects for conflicts resolved

        Raises:
            ConnectionError: If database unavailable
        """
        ...

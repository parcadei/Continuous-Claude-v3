"""
ScopeManager - Scope isolation enforcement for the Orchestration Layer.

Provides managed scopes with access control based on ScopeType:
- ISOLATED: No shared state access
- SHARED: Full shared context access
- FEDERATED: Read-only access to parent scope
- HANDOFF: Sequential state transfer

Access Rules:
| Scope Type | read | write | read_shared | write_shared |
|------------|------|-------|-------------|--------------|
| ISOLATED   | Yes  | Yes   | No          | No           |
| SHARED     | Yes  | Yes   | Yes         | Yes          |
| FEDERATED  | Yes  | Yes   | Yes (parent)| No           |
| HANDOFF    | Yes  | Yes   | No          | No           |

Usage:
    manager = ScopeManager(session_id="abc123", db_path=Path("/tmp/test.db"))
    scope = manager.create_scope(mode=ScopeType.SHARED)
    manager.validate_access(scope, "read_shared", "key")  # OK

    isolated = manager.create_scope(mode=ScopeType.ISOLATED)
    manager.validate_access(isolated, "read_shared", "key")  # Raises ScopeViolationError
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.agentica_patterns.primitives import HandoffState
from scripts.agentica_patterns.unified_scope import (
    SharedContext,
    LocalCacheManager,
    create_unified_scope,
)
from scripts.validate_composition import ScopeType


# ============================================================================
# Exceptions
# ============================================================================


class ScopeViolationError(Exception):
    """Raised when an operation violates scope access rules.

    Attributes:
        scope_type: The ScopeType that was violated
        operation: The operation that was attempted (read, write, read_shared, write_shared)
        key: The key that was accessed
    """

    def __init__(
        self,
        scope_type: ScopeType,
        operation: str,
        key: str,
        message: str | None = None,
    ):
        self.scope_type = scope_type
        self.operation = operation
        self.key = key

        if message is None:
            message = f"{operation} on '{key}' not allowed for {scope_type.value} scope"

        super().__init__(message)


# ============================================================================
# ManagedScope
# ============================================================================


@dataclass
class ManagedScope:
    """Managed scope with access control based on ScopeType.

    Wraps a scope dict and enforces access rules via properties.
    Uses the proxy pattern - intercepts access attempts at the boundary.

    Attributes:
        scope: The underlying scope dictionary
        scope_type: The type of isolation (ISOLATED, SHARED, FEDERATED, HANDOFF)
        parent: Optional parent scope for FEDERATED mode
        task_id: Optional task identifier
        _handoff_state: Internal HandoffState for HANDOFF scopes
    """

    scope: dict[str, Any]
    scope_type: ScopeType
    parent: "ManagedScope | None" = None
    task_id: str | None = None
    _handoff_state: HandoffState | None = field(default=None, repr=False)

    @property
    def allows_shared_access(self) -> bool:
        """Whether this scope can access shared context."""
        return self.scope_type in (ScopeType.SHARED, ScopeType.FEDERATED)

    @property
    def allows_write(self) -> bool:
        """Whether this scope can write to shared context."""
        return self.scope_type == ScopeType.SHARED

    @property
    def allows_parent_read(self) -> bool:
        """Whether this scope can read from parent's shared context."""
        return self.scope_type == ScopeType.FEDERATED and self.parent is not None


# ============================================================================
# ScopeManager
# ============================================================================


class ScopeManager:
    """Manager for creating and enforcing scope isolation.

    Creates scopes with different isolation modes and validates
    access attempts based on the access rules table.

    Thread-safe for concurrent scope creation and validation.
    """

    # Access rules table: scope_type -> (allowed_operations)
    # True = allowed, False = raises ScopeViolationError
    _ACCESS_RULES: dict[ScopeType, dict[str, bool]] = {
        ScopeType.ISOLATED: {
            "read": True,
            "write": True,
            "read_shared": False,
            "write_shared": False,
        },
        ScopeType.SHARED: {
            "read": True,
            "write": True,
            "read_shared": True,
            "write_shared": True,
        },
        ScopeType.FEDERATED: {
            "read": True,
            "write": True,
            "read_shared": True,  # From parent only
            "write_shared": False,
        },
        ScopeType.HANDOFF: {
            "read": True,
            "write": True,
            "read_shared": False,
            "write_shared": False,
        },
    }

    def __init__(
        self,
        session_id: str,
        db_path: Path | None = None,
        project_dir: str | None = None,
        enable_memory: bool = True,
        enable_tasks: bool = True,
    ):
        """Initialize ScopeManager with session config.

        Args:
            session_id: Session identifier for isolation
            db_path: Optional database path for memory/tasks
            project_dir: Optional project directory for path validation
            enable_memory: Whether to enable memory operations
            enable_tasks: Whether to enable task operations
        """
        self.session_id = session_id
        self.db_path = db_path
        self.project_dir = project_dir
        self.enable_memory = enable_memory
        self.enable_tasks = enable_tasks

        # Shared context for SHARED/FEDERATED scopes (lazy initialized)
        self._shared_context: SharedContext | None = None
        self._shared_context_lock = threading.Lock()

        # Track created scopes for debugging
        self._created_scopes: list[ManagedScope] = []
        self._scopes_lock = threading.Lock()

    def _get_or_create_shared_context(self) -> SharedContext:
        """Get or lazily create the shared context (thread-safe)."""
        if self._shared_context is None:
            with self._shared_context_lock:
                # Double-check after acquiring lock
                if self._shared_context is None:
                    self._shared_context = SharedContext()
        return self._shared_context

    def create_scope(
        self,
        mode: ScopeType,
        task_id: str | None = None,
        parent: ManagedScope | None = None,
    ) -> ManagedScope:
        """Create managed scope with specified isolation mode.

        Args:
            mode: Isolation mode (ISOLATED, SHARED, FEDERATED, HANDOFF)
            task_id: Optional task identifier
            parent: Required parent scope for FEDERATED mode

        Returns:
            ManagedScope with appropriate access control

        Raises:
            ValueError: If FEDERATED mode without parent
        """
        # Validation
        if mode == ScopeType.FEDERATED and parent is None:
            raise ValueError("FEDERATED scope requires parent scope")

        # Create scope dict based on mode
        if mode == ScopeType.SHARED:
            # SHARED scopes share the same SharedContext
            shared = self._get_or_create_shared_context()
            # Create a scope dict that IS the shared context's internal dict
            # This allows multiple SHARED scopes to see each other's writes
            scope_dict = shared.file_cache  # Direct reference for sharing
        elif mode == ScopeType.FEDERATED:
            # FEDERATED gets its own local scope dict
            # Parent reference allows read access to parent's shared context
            scope_dict = {}
        else:
            # ISOLATED and HANDOFF get their own local scope dict
            scope_dict = {}

        # Create HandoffState for HANDOFF scopes
        handoff_state: HandoffState | None = None
        if mode == ScopeType.HANDOFF:
            handoff_state = HandoffState(
                context="",
                next_instruction="",
                artifacts={},
                metadata={},
            )

        managed = ManagedScope(
            scope=scope_dict,
            scope_type=mode,
            parent=parent,
            task_id=task_id,
            _handoff_state=handoff_state,
        )

        # Track created scope
        with self._scopes_lock:
            self._created_scopes.append(managed)

        return managed

    def validate_access(
        self,
        scope: ManagedScope,
        operation: str,
        key: str,
    ) -> bool:
        """Validate if operation is allowed for scope.

        Args:
            scope: The ManagedScope to validate against
            operation: Operation type (read, write, read_shared, write_shared)
            key: The key being accessed

        Returns:
            True if operation is allowed

        Raises:
            ScopeViolationError: If operation is not allowed
        """
        rules = self._ACCESS_RULES.get(scope.scope_type)
        if rules is None:
            raise ScopeViolationError(
                scope_type=scope.scope_type,
                operation=operation,
                key=key,
                message=f"Unknown scope type: {scope.scope_type}",
            )

        allowed = rules.get(operation, False)

        if not allowed:
            raise ScopeViolationError(
                scope_type=scope.scope_type,
                operation=operation,
                key=key,
            )

        return True

    def transfer_handoff(
        self,
        from_scope: ManagedScope,
        to_scope: ManagedScope,
    ) -> None:
        """Transfer state between HANDOFF scopes.

        Transfers artifacts, metadata, context, and next_instruction
        from source to destination. Records the handoff in the chain.

        Args:
            from_scope: Source HANDOFF scope
            to_scope: Destination HANDOFF scope

        Raises:
            ScopeViolationError: If either scope is not HANDOFF type
        """
        # Validate both scopes are HANDOFF
        if from_scope.scope_type != ScopeType.HANDOFF:
            raise ScopeViolationError(
                scope_type=from_scope.scope_type,
                operation="transfer_handoff",
                key="from_scope",
                message=f"Source scope must be HANDOFF, got {from_scope.scope_type.value}",
            )

        if to_scope.scope_type != ScopeType.HANDOFF:
            raise ScopeViolationError(
                scope_type=to_scope.scope_type,
                operation="transfer_handoff",
                key="to_scope",
                message=f"Destination scope must be HANDOFF, got {to_scope.scope_type.value}",
            )

        # Get handoff states
        source_state = from_scope._handoff_state
        dest_state = to_scope._handoff_state

        if source_state is None:
            raise ScopeViolationError(
                scope_type=from_scope.scope_type,
                operation="transfer_handoff",
                key="from_scope",
                message="Source scope has no HandoffState",
            )

        if dest_state is None:
            raise ScopeViolationError(
                scope_type=to_scope.scope_type,
                operation="transfer_handoff",
                key="to_scope",
                message="Destination scope has no HandoffState",
            )

        # Record handoff in chain before merging
        from_id = from_scope.task_id or "unknown"
        to_id = to_scope.task_id or "unknown"
        source_state.record_handoff(from_id, to_id)

        # Merge source into destination using HandoffState.merge()
        merged = dest_state.merge(source_state)

        # Update destination with merged state
        to_scope._handoff_state = merged

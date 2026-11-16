"""
Unit tests for ScopeManager.

Tests scope isolation enforcement for the Orchestration Layer.
TDD: These tests are written BEFORE implementation and should FAIL initially.

Test coverage:
- ScopeViolationError exception attributes
- ManagedScope dataclass properties per ScopeType
- ScopeManager.create_scope() for all scope types
- ScopeManager.validate_access() enforcement rules
- ScopeManager.transfer_handoff() state transfer
- Thread safety for concurrent SharedContext access
"""

import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from uuid import uuid4

# Import will fail until implementation exists - this is expected for TDD
from scripts.agentica_patterns.scope_manager import (
    ScopeManager,
    ManagedScope,
    ScopeViolationError,
)
from scripts.validate_composition import ScopeType


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def session_id() -> str:
    """Generate unique session ID for each test."""
    return f"test-session-{uuid4().hex[:8]}"


@pytest.fixture
def scope_manager(session_id: str, tmp_path) -> ScopeManager:
    """Create ScopeManager with in-memory/temp DB for testing."""
    return ScopeManager(
        session_id=session_id,
        db_path=tmp_path / "test.db",
        project_dir=str(tmp_path),
        enable_memory=False,  # Disable for unit tests
        enable_tasks=False,
    )


# ============================================================================
# TestScopeViolationError
# ============================================================================


class TestScopeViolationError:
    """Tests for ScopeViolationError exception."""

    def test_attributes_accessible(self):
        """Error has correct scope_type, operation, key attributes."""
        error = ScopeViolationError(
            scope_type=ScopeType.ISOLATED,
            operation="read_shared",
            key="shared_data",
        )

        assert error.scope_type == ScopeType.ISOLATED
        assert error.operation == "read_shared"
        assert error.key == "shared_data"

    def test_string_representation(self):
        """Error message includes scope type, operation, and key."""
        error = ScopeViolationError(
            scope_type=ScopeType.ISOLATED,
            operation="read_shared",
            key="my_key",
        )

        msg = str(error)
        assert "read_shared" in msg
        assert "my_key" in msg
        assert "iso" in msg.lower() or "isolated" in msg.lower()

    def test_custom_message_override(self):
        """Custom message is used if provided."""
        custom_msg = "Custom violation message for testing"
        error = ScopeViolationError(
            scope_type=ScopeType.SHARED,
            operation="forbidden_op",
            key="test_key",
            message=custom_msg,
        )

        assert str(error) == custom_msg
        # Attributes still accessible
        assert error.scope_type == ScopeType.SHARED
        assert error.operation == "forbidden_op"
        assert error.key == "test_key"

    def test_is_exception_subclass(self):
        """ScopeViolationError is a proper Exception."""
        error = ScopeViolationError(
            scope_type=ScopeType.ISOLATED,
            operation="test",
            key="test",
        )
        assert isinstance(error, Exception)

        # Can be raised and caught
        with pytest.raises(ScopeViolationError) as exc_info:
            raise error
        assert exc_info.value.scope_type == ScopeType.ISOLATED


# ============================================================================
# TestManagedScope
# ============================================================================


class TestManagedScope:
    """Tests for ManagedScope dataclass."""

    def test_allows_shared_access_isolated(self):
        """ISOLATED scope does not allow shared access."""
        scope = ManagedScope(
            scope={},
            scope_type=ScopeType.ISOLATED,
        )
        assert scope.allows_shared_access is False

    def test_allows_shared_access_shared(self):
        """SHARED scope allows shared access."""
        scope = ManagedScope(
            scope={},
            scope_type=ScopeType.SHARED,
        )
        assert scope.allows_shared_access is True

    def test_allows_shared_access_federated(self):
        """FEDERATED scope allows shared access (read-only)."""
        parent = ManagedScope(scope={}, scope_type=ScopeType.SHARED)
        scope = ManagedScope(
            scope={},
            scope_type=ScopeType.FEDERATED,
            parent=parent,
        )
        assert scope.allows_shared_access is True

    def test_allows_shared_access_handoff(self):
        """HANDOFF scope does not allow shared access."""
        scope = ManagedScope(
            scope={},
            scope_type=ScopeType.HANDOFF,
        )
        assert scope.allows_shared_access is False

    def test_allows_write_shared(self):
        """Only SHARED scope allows write to shared context."""
        for scope_type in ScopeType:
            scope = ManagedScope(scope={}, scope_type=scope_type)
            if scope_type == ScopeType.SHARED:
                assert scope.allows_write is True, f"{scope_type} should allow write"
            else:
                assert scope.allows_write is False, f"{scope_type} should not allow write"

    def test_allows_parent_read_federated_with_parent(self):
        """FEDERATED scope with parent allows parent read."""
        parent = ManagedScope(scope={}, scope_type=ScopeType.SHARED)
        scope = ManagedScope(
            scope={},
            scope_type=ScopeType.FEDERATED,
            parent=parent,
        )
        assert scope.allows_parent_read is True

    def test_allows_parent_read_federated_without_parent(self):
        """FEDERATED scope without parent does not allow parent read."""
        scope = ManagedScope(
            scope={},
            scope_type=ScopeType.FEDERATED,
            parent=None,
        )
        assert scope.allows_parent_read is False

    def test_allows_parent_read_non_federated(self):
        """Non-FEDERATED scopes do not allow parent read."""
        for scope_type in [ScopeType.ISOLATED, ScopeType.SHARED, ScopeType.HANDOFF]:
            scope = ManagedScope(scope={}, scope_type=scope_type)
            assert scope.allows_parent_read is False

    def test_task_id_stored(self):
        """task_id is properly stored and accessible."""
        scope = ManagedScope(
            scope={},
            scope_type=ScopeType.ISOLATED,
            task_id="task-123",
        )
        assert scope.task_id == "task-123"

    def test_task_id_default_none(self):
        """task_id defaults to None."""
        scope = ManagedScope(scope={}, scope_type=ScopeType.ISOLATED)
        assert scope.task_id is None


# ============================================================================
# TestScopeManagerCreateScope
# ============================================================================


class TestScopeManagerCreateScope:
    """Tests for ScopeManager.create_scope()."""

    def test_isolated_no_shared_context(self, scope_manager: ScopeManager):
        """ISOLATED scope has no SharedContext access."""
        scope = scope_manager.create_scope(mode=ScopeType.ISOLATED)

        assert scope.scope_type == ScopeType.ISOLATED
        assert scope.allows_shared_access is False
        # Scope dict exists but is isolated
        assert isinstance(scope.scope, dict)

    def test_shared_scopes_share_context(self, scope_manager: ScopeManager):
        """Multiple SHARED scopes share the same SharedContext."""
        scope1 = scope_manager.create_scope(mode=ScopeType.SHARED)
        scope2 = scope_manager.create_scope(mode=ScopeType.SHARED)

        # Write to scope1's shared context
        scope1.scope["shared_key"] = "shared_value"

        # scope2 should see the same data (shared context)
        assert scope2.scope.get("shared_key") == "shared_value"

    def test_isolated_scopes_not_shared(self, scope_manager: ScopeManager):
        """ISOLATED scopes do not share context."""
        scope1 = scope_manager.create_scope(mode=ScopeType.ISOLATED)
        scope2 = scope_manager.create_scope(mode=ScopeType.ISOLATED)

        scope1.scope["local_key"] = "local_value"

        # scope2 should NOT see scope1's data
        assert scope2.scope.get("local_key") is None

    def test_federated_requires_parent(self, scope_manager: ScopeManager):
        """FEDERATED scope without parent raises ValueError."""
        with pytest.raises(ValueError, match="parent"):
            scope_manager.create_scope(mode=ScopeType.FEDERATED, parent=None)

    def test_federated_reads_parent(self, scope_manager: ScopeManager):
        """FEDERATED scope can read parent's shared context."""
        parent = scope_manager.create_scope(mode=ScopeType.SHARED)
        parent.scope["parent_data"] = "important_info"

        child = scope_manager.create_scope(
            mode=ScopeType.FEDERATED,
            parent=parent,
        )

        # Child can read parent data
        assert child.parent is not None
        assert child.parent.scope.get("parent_data") == "important_info"

    def test_federated_write_isolated(self, scope_manager: ScopeManager):
        """FEDERATED scope writes are isolated from parent."""
        parent = scope_manager.create_scope(mode=ScopeType.SHARED)

        child = scope_manager.create_scope(
            mode=ScopeType.FEDERATED,
            parent=parent,
        )

        # Child writes should NOT affect parent
        child.scope["child_only"] = "my_data"

        assert parent.scope.get("child_only") is None

    def test_handoff_state_initialized(self, scope_manager: ScopeManager):
        """HANDOFF scope has HandoffState initialized."""
        scope = scope_manager.create_scope(mode=ScopeType.HANDOFF)

        assert scope.scope_type == ScopeType.HANDOFF
        # HandoffState should be accessible (internal attribute)
        assert hasattr(scope, "_handoff_state")
        assert scope._handoff_state is not None

    def test_handoff_artifacts_empty_initially(self, scope_manager: ScopeManager):
        """HANDOFF scope starts with empty artifacts."""
        scope = scope_manager.create_scope(mode=ScopeType.HANDOFF)

        assert scope._handoff_state.artifacts == {}

    def test_task_id_propagated(self, scope_manager: ScopeManager):
        """task_id is propagated to created scope."""
        scope = scope_manager.create_scope(
            mode=ScopeType.ISOLATED,
            task_id="my-task-123",
        )

        assert scope.task_id == "my-task-123"


# ============================================================================
# TestScopeManagerValidateAccess
# ============================================================================


class TestScopeManagerValidateAccess:
    """Tests for ScopeManager.validate_access()."""

    # ISOLATED scope tests

    def test_isolated_read_allowed(self, scope_manager: ScopeManager):
        """ISOLATED scope allows read operation."""
        scope = scope_manager.create_scope(mode=ScopeType.ISOLATED)
        # Should not raise
        result = scope_manager.validate_access(scope, "read", "any_key")
        assert result is True

    def test_isolated_write_allowed(self, scope_manager: ScopeManager):
        """ISOLATED scope allows write operation."""
        scope = scope_manager.create_scope(mode=ScopeType.ISOLATED)
        result = scope_manager.validate_access(scope, "write", "any_key")
        assert result is True

    def test_isolated_read_shared_raises(self, scope_manager: ScopeManager):
        """ISOLATED scope raises on read_shared operation."""
        scope = scope_manager.create_scope(mode=ScopeType.ISOLATED)

        with pytest.raises(ScopeViolationError) as exc_info:
            scope_manager.validate_access(scope, "read_shared", "shared_key")

        assert exc_info.value.scope_type == ScopeType.ISOLATED
        assert exc_info.value.operation == "read_shared"

    def test_isolated_write_shared_raises(self, scope_manager: ScopeManager):
        """ISOLATED scope raises on write_shared operation."""
        scope = scope_manager.create_scope(mode=ScopeType.ISOLATED)

        with pytest.raises(ScopeViolationError) as exc_info:
            scope_manager.validate_access(scope, "write_shared", "shared_key")

        assert exc_info.value.scope_type == ScopeType.ISOLATED

    # SHARED scope tests

    def test_shared_read_allowed(self, scope_manager: ScopeManager):
        """SHARED scope allows read operation."""
        scope = scope_manager.create_scope(mode=ScopeType.SHARED)
        result = scope_manager.validate_access(scope, "read", "key")
        assert result is True

    def test_shared_write_allowed(self, scope_manager: ScopeManager):
        """SHARED scope allows write operation."""
        scope = scope_manager.create_scope(mode=ScopeType.SHARED)
        result = scope_manager.validate_access(scope, "write", "key")
        assert result is True

    def test_shared_read_shared_allowed(self, scope_manager: ScopeManager):
        """SHARED scope allows read_shared operation."""
        scope = scope_manager.create_scope(mode=ScopeType.SHARED)
        result = scope_manager.validate_access(scope, "read_shared", "key")
        assert result is True

    def test_shared_write_shared_allowed(self, scope_manager: ScopeManager):
        """SHARED scope allows write_shared operation."""
        scope = scope_manager.create_scope(mode=ScopeType.SHARED)
        result = scope_manager.validate_access(scope, "write_shared", "key")
        assert result is True

    # FEDERATED scope tests

    def test_federated_read_allowed(self, scope_manager: ScopeManager):
        """FEDERATED scope allows read operation."""
        parent = scope_manager.create_scope(mode=ScopeType.SHARED)
        scope = scope_manager.create_scope(mode=ScopeType.FEDERATED, parent=parent)
        result = scope_manager.validate_access(scope, "read", "key")
        assert result is True

    def test_federated_write_allowed(self, scope_manager: ScopeManager):
        """FEDERATED scope allows write operation (to local scope)."""
        parent = scope_manager.create_scope(mode=ScopeType.SHARED)
        scope = scope_manager.create_scope(mode=ScopeType.FEDERATED, parent=parent)
        result = scope_manager.validate_access(scope, "write", "key")
        assert result is True

    def test_federated_read_shared_allowed(self, scope_manager: ScopeManager):
        """FEDERATED scope allows read_shared (from parent)."""
        parent = scope_manager.create_scope(mode=ScopeType.SHARED)
        scope = scope_manager.create_scope(mode=ScopeType.FEDERATED, parent=parent)
        result = scope_manager.validate_access(scope, "read_shared", "key")
        assert result is True

    def test_federated_write_shared_raises(self, scope_manager: ScopeManager):
        """FEDERATED scope raises on write_shared operation."""
        parent = scope_manager.create_scope(mode=ScopeType.SHARED)
        scope = scope_manager.create_scope(mode=ScopeType.FEDERATED, parent=parent)

        with pytest.raises(ScopeViolationError) as exc_info:
            scope_manager.validate_access(scope, "write_shared", "key")

        assert exc_info.value.scope_type == ScopeType.FEDERATED
        assert exc_info.value.operation == "write_shared"

    # HANDOFF scope tests

    def test_handoff_read_allowed(self, scope_manager: ScopeManager):
        """HANDOFF scope allows read operation."""
        scope = scope_manager.create_scope(mode=ScopeType.HANDOFF)
        result = scope_manager.validate_access(scope, "read", "key")
        assert result is True

    def test_handoff_write_allowed(self, scope_manager: ScopeManager):
        """HANDOFF scope allows write operation."""
        scope = scope_manager.create_scope(mode=ScopeType.HANDOFF)
        result = scope_manager.validate_access(scope, "write", "key")
        assert result is True

    def test_handoff_read_shared_raises(self, scope_manager: ScopeManager):
        """HANDOFF scope raises on read_shared operation."""
        scope = scope_manager.create_scope(mode=ScopeType.HANDOFF)

        with pytest.raises(ScopeViolationError) as exc_info:
            scope_manager.validate_access(scope, "read_shared", "key")

        assert exc_info.value.scope_type == ScopeType.HANDOFF

    def test_handoff_write_shared_raises(self, scope_manager: ScopeManager):
        """HANDOFF scope raises on write_shared operation."""
        scope = scope_manager.create_scope(mode=ScopeType.HANDOFF)

        with pytest.raises(ScopeViolationError) as exc_info:
            scope_manager.validate_access(scope, "write_shared", "key")

        assert exc_info.value.scope_type == ScopeType.HANDOFF


# ============================================================================
# TestScopeManagerTransferHandoff
# ============================================================================


class TestScopeManagerTransferHandoff:
    """Tests for ScopeManager.transfer_handoff()."""

    def test_success_transfers_artifacts(self, scope_manager: ScopeManager):
        """Artifacts transfer from source to destination HANDOFF scope."""
        source = scope_manager.create_scope(mode=ScopeType.HANDOFF)
        dest = scope_manager.create_scope(mode=ScopeType.HANDOFF)

        # Add artifacts to source
        source._handoff_state.add_artifact("result", {"data": [1, 2, 3]})
        source._handoff_state.add_artifact("report", "Final report text")

        # Transfer
        scope_manager.transfer_handoff(source, dest)

        # Destination should have the artifacts
        assert dest._handoff_state.artifacts.get("result") == {"data": [1, 2, 3]}
        assert dest._handoff_state.artifacts.get("report") == "Final report text"

    def test_success_records_chain(self, scope_manager: ScopeManager):
        """Handoff chain is recorded during transfer."""
        source = scope_manager.create_scope(
            mode=ScopeType.HANDOFF,
            task_id="task-source",
        )
        dest = scope_manager.create_scope(
            mode=ScopeType.HANDOFF,
            task_id="task-dest",
        )

        scope_manager.transfer_handoff(source, dest)

        chain = dest._handoff_state.get_handoff_chain()
        assert len(chain) >= 1
        # Latest handoff should be from source to dest
        last_handoff = chain[-1]
        assert "task-source" in str(last_handoff) or last_handoff.get("from") == "task-source"

    def test_non_handoff_source_raises(self, scope_manager: ScopeManager):
        """Transferring from non-HANDOFF scope raises ScopeViolationError."""
        source = scope_manager.create_scope(mode=ScopeType.ISOLATED)
        dest = scope_manager.create_scope(mode=ScopeType.HANDOFF)

        with pytest.raises(ScopeViolationError):
            scope_manager.transfer_handoff(source, dest)

    def test_non_handoff_dest_raises(self, scope_manager: ScopeManager):
        """Transferring to non-HANDOFF scope raises ScopeViolationError."""
        source = scope_manager.create_scope(mode=ScopeType.HANDOFF)
        dest = scope_manager.create_scope(mode=ScopeType.SHARED)

        with pytest.raises(ScopeViolationError):
            scope_manager.transfer_handoff(source, dest)

    def test_metadata_transferred(self, scope_manager: ScopeManager):
        """Metadata is transferred along with artifacts."""
        source = scope_manager.create_scope(mode=ScopeType.HANDOFF)
        dest = scope_manager.create_scope(mode=ScopeType.HANDOFF)

        source._handoff_state.metadata["priority"] = "high"
        source._handoff_state.metadata["tags"] = ["urgent", "review"]

        scope_manager.transfer_handoff(source, dest)

        assert dest._handoff_state.metadata.get("priority") == "high"
        assert dest._handoff_state.metadata.get("tags") == ["urgent", "review"]

    def test_context_transferred(self, scope_manager: ScopeManager):
        """Context and next_instruction are transferred."""
        source = scope_manager.create_scope(mode=ScopeType.HANDOFF)
        dest = scope_manager.create_scope(mode=ScopeType.HANDOFF)

        source._handoff_state.context = "Processing phase 2"
        source._handoff_state.next_instruction = "Validate results and report"

        scope_manager.transfer_handoff(source, dest)

        assert dest._handoff_state.context == "Processing phase 2"
        assert dest._handoff_state.next_instruction == "Validate results and report"

    def test_multiple_transfers_chain(self, scope_manager: ScopeManager):
        """Multiple transfers maintain complete handoff chain."""
        scope1 = scope_manager.create_scope(mode=ScopeType.HANDOFF, task_id="phase-1")
        scope2 = scope_manager.create_scope(mode=ScopeType.HANDOFF, task_id="phase-2")
        scope3 = scope_manager.create_scope(mode=ScopeType.HANDOFF, task_id="phase-3")

        scope1._handoff_state.add_artifact("initial", "data")

        scope_manager.transfer_handoff(scope1, scope2)
        scope_manager.transfer_handoff(scope2, scope3)

        # scope3 should have original artifact
        assert scope3._handoff_state.artifacts.get("initial") == "data"

        # Chain should record both transfers
        chain = scope3._handoff_state.get_handoff_chain()
        assert len(chain) >= 2


# ============================================================================
# TestConcurrency
# ============================================================================


class TestConcurrency:
    """Thread safety tests for SharedContext access."""

    def test_concurrent_shared_scope_access(self, scope_manager: ScopeManager):
        """
        Multiple threads accessing SHARED scopes don't corrupt state.

        This is a critical thread safety test (Condition 1 from requirements).
        """
        # Create shared scope that all threads will access
        shared_scope = scope_manager.create_scope(mode=ScopeType.SHARED)

        num_threads = 10
        writes_per_thread = 100
        errors: list[Exception] = []
        results: dict[str, Any] = {}

        def worker(thread_id: int) -> None:
            """Each worker writes to shared scope multiple times."""
            try:
                for i in range(writes_per_thread):
                    key = f"thread_{thread_id}_item_{i}"
                    value = f"value_{thread_id}_{i}"
                    shared_scope.scope[key] = value

                    # Small delay to increase chance of race conditions
                    if i % 10 == 0:
                        time.sleep(0.001)

                    # Verify our own write succeeded
                    if shared_scope.scope.get(key) != value:
                        errors.append(
                            ValueError(f"Thread {thread_id}: Lost write at {key}")
                        )
            except Exception as e:
                errors.append(e)

        # Run workers concurrently
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()  # Raise any exceptions

        # Verify no errors occurred
        assert len(errors) == 0, f"Concurrency errors: {errors}"

        # Verify all expected keys are present
        expected_key_count = num_threads * writes_per_thread
        actual_key_count = sum(
            1 for k in shared_scope.scope.keys()
            if k.startswith("thread_")
        )
        assert actual_key_count == expected_key_count, (
            f"Expected {expected_key_count} keys, got {actual_key_count}"
        )

    def test_concurrent_scope_creation(self, scope_manager: ScopeManager):
        """Multiple threads can safely create scopes concurrently."""
        num_threads = 20
        scopes: list[ManagedScope] = []
        lock = threading.Lock()
        errors: list[Exception] = []

        def create_scope(thread_id: int) -> None:
            try:
                scope = scope_manager.create_scope(
                    mode=ScopeType.SHARED,
                    task_id=f"task-{thread_id}",
                )
                with lock:
                    scopes.append(scope)
            except Exception as e:
                with lock:
                    errors.append(e)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_scope, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Scope creation errors: {errors}"
        assert len(scopes) == num_threads

    def test_concurrent_validate_access(self, scope_manager: ScopeManager):
        """validate_access is thread-safe."""
        scope = scope_manager.create_scope(mode=ScopeType.SHARED)
        num_threads = 50
        validations_per_thread = 100
        errors: list[Exception] = []

        def validate_worker(thread_id: int) -> None:
            try:
                for i in range(validations_per_thread):
                    result = scope_manager.validate_access(
                        scope, "read", f"key_{thread_id}_{i}"
                    )
                    assert result is True
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(validate_worker, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Validation errors: {errors}"

    def test_concurrent_handoff_isolation(self, scope_manager: ScopeManager):
        """HANDOFF transfers in parallel don't interfere with each other."""
        num_pairs = 10
        errors: list[Exception] = []

        def transfer_pair(pair_id: int) -> None:
            try:
                source = scope_manager.create_scope(
                    mode=ScopeType.HANDOFF,
                    task_id=f"source-{pair_id}",
                )
                dest = scope_manager.create_scope(
                    mode=ScopeType.HANDOFF,
                    task_id=f"dest-{pair_id}",
                )

                # Add unique artifact
                unique_value = f"artifact-{pair_id}"
                source._handoff_state.add_artifact("data", unique_value)

                scope_manager.transfer_handoff(source, dest)

                # Verify our transfer worked
                if dest._handoff_state.artifacts.get("data") != unique_value:
                    errors.append(
                        ValueError(f"Pair {pair_id}: Transfer corrupted")
                    )
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=num_pairs) as executor:
            futures = [executor.submit(transfer_pair, i) for i in range(num_pairs)]
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Handoff errors: {errors}"


# ============================================================================
# TestAccessRulesTable
# ============================================================================


class TestAccessRulesTable:
    """
    Verify access rules match the specification table:

    | Scope Type | read | write | read_shared | write_shared |
    |------------|------|-------|-------------|--------------|
    | ISOLATED   | Yes  | Yes   | No          | No           |
    | SHARED     | Yes  | Yes   | Yes         | Yes          |
    | FEDERATED  | Yes  | Yes   | Yes (parent)| No           |
    | HANDOFF    | Yes  | Yes   | No          | No           |
    """

    @pytest.mark.parametrize("scope_type,operation,expected", [
        # ISOLATED
        (ScopeType.ISOLATED, "read", True),
        (ScopeType.ISOLATED, "write", True),
        (ScopeType.ISOLATED, "read_shared", False),
        (ScopeType.ISOLATED, "write_shared", False),
        # SHARED
        (ScopeType.SHARED, "read", True),
        (ScopeType.SHARED, "write", True),
        (ScopeType.SHARED, "read_shared", True),
        (ScopeType.SHARED, "write_shared", True),
        # HANDOFF
        (ScopeType.HANDOFF, "read", True),
        (ScopeType.HANDOFF, "write", True),
        (ScopeType.HANDOFF, "read_shared", False),
        (ScopeType.HANDOFF, "write_shared", False),
    ])
    def test_access_rule(
        self,
        scope_manager: ScopeManager,
        scope_type: ScopeType,
        operation: str,
        expected: bool,
    ):
        """Test access rule from specification table."""
        scope = scope_manager.create_scope(mode=scope_type)

        if expected:
            result = scope_manager.validate_access(scope, operation, "test_key")
            assert result is True
        else:
            with pytest.raises(ScopeViolationError):
                scope_manager.validate_access(scope, operation, "test_key")

    @pytest.mark.parametrize("operation,expected", [
        ("read", True),
        ("write", True),
        ("read_shared", True),
        ("write_shared", False),
    ])
    def test_federated_access_rule(
        self,
        scope_manager: ScopeManager,
        operation: str,
        expected: bool,
    ):
        """Test FEDERATED access rules (requires parent)."""
        parent = scope_manager.create_scope(mode=ScopeType.SHARED)
        scope = scope_manager.create_scope(mode=ScopeType.FEDERATED, parent=parent)

        if expected:
            result = scope_manager.validate_access(scope, operation, "test_key")
            assert result is True
        else:
            with pytest.raises(ScopeViolationError):
                scope_manager.validate_access(scope, operation, "test_key")

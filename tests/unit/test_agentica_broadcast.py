"""Tests for Agentica Broadcast functionality (Phase 6).

These tests are written FIRST before implementation (TDD).
They will FAIL initially because BroadcastType, BroadcastRecord,
create_broadcast(), and get_broadcasts() don't exist yet.

See plan: thoughts/shared/plans/2025-12-28-user-triggered-agentica.md
"""

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest


class TestBroadcastTypeEnum:
    """Tests for BroadcastType enum values (Phase 2)."""

    def test_broadcast_type_finding_value(self):
        """BroadcastType.FINDING should have value 'finding'."""
        from scripts.agentica_patterns.coordination import BroadcastType

        assert BroadcastType.FINDING.value == "finding"

    def test_broadcast_type_question_value(self):
        """BroadcastType.QUESTION should have value 'question'."""
        from scripts.agentica_patterns.coordination import BroadcastType

        assert BroadcastType.QUESTION.value == "question"

    def test_broadcast_type_blocker_value(self):
        """BroadcastType.BLOCKER should have value 'blocker'."""
        from scripts.agentica_patterns.coordination import BroadcastType

        assert BroadcastType.BLOCKER.value == "blocker"

    def test_broadcast_type_done_value(self):
        """BroadcastType.DONE should have value 'done'."""
        from scripts.agentica_patterns.coordination import BroadcastType

        assert BroadcastType.DONE.value == "done"

    def test_broadcast_type_abort_value(self):
        """BroadcastType.ABORT should have value 'abort'."""
        from scripts.agentica_patterns.coordination import BroadcastType

        assert BroadcastType.ABORT.value == "abort"

    def test_broadcast_type_is_string_enum(self):
        """BroadcastType should be a string enum (inherits from str, Enum)."""
        from scripts.agentica_patterns.coordination import BroadcastType

        # String enums can be used directly as strings
        assert f"Type: {BroadcastType.FINDING}" == "Type: finding"

    def test_broadcast_type_all_values(self):
        """BroadcastType should have exactly 5 values."""
        from scripts.agentica_patterns.coordination import BroadcastType

        all_types = list(BroadcastType)
        assert len(all_types) == 5
        assert set(bt.value for bt in all_types) == {
            "finding", "question", "blocker", "done", "abort"
        }


class TestBroadcastRecordDataclass:
    """Tests for BroadcastRecord dataclass (Phase 2)."""

    def test_broadcast_record_creation(self):
        """BroadcastRecord should be created with all required fields."""
        from scripts.agentica_patterns.coordination import BroadcastRecord, BroadcastType

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        record = BroadcastRecord(
            id="bc123456",
            swarm_id="swarm-abc123",
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Found important pattern"},
            created_at=now,
        )

        assert record.id == "bc123456"
        assert record.swarm_id == "swarm-abc123"
        assert record.sender_agent == "agent-1"
        assert record.broadcast_type == BroadcastType.FINDING
        assert record.payload == {"finding": "Found important pattern"}
        assert record.created_at == now

    def test_broadcast_record_with_complex_payload(self):
        """BroadcastRecord should handle complex nested payloads."""
        from scripts.agentica_patterns.coordination import BroadcastRecord, BroadcastType

        complex_payload = {
            "finding": "Security vulnerability",
            "metadata": {
                "file": "auth.py",
                "line": 42,
                "severity": "high",
                "tags": ["security", "auth", "critical"],
            },
            "code_snippet": "def authenticate(user): pass",
        }

        record = BroadcastRecord(
            id="bc789",
            swarm_id="swarm-xyz",
            sender_agent="security-agent",
            broadcast_type=BroadcastType.FINDING,
            payload=complex_payload,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        assert record.payload["metadata"]["severity"] == "high"
        assert "security" in record.payload["metadata"]["tags"]

    def test_broadcast_record_with_empty_payload(self):
        """BroadcastRecord should handle empty payload dict."""
        from scripts.agentica_patterns.coordination import BroadcastRecord, BroadcastType

        record = BroadcastRecord(
            id="bc000",
            swarm_id="swarm-test",
            sender_agent="agent-x",
            broadcast_type=BroadcastType.DONE,
            payload={},
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )

        assert record.payload == {}


class TestCreateBroadcast:
    """Tests for create_broadcast() method (Phase 3)."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary database."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    def test_create_broadcast_finding(self, db):
        """Test creating a finding broadcast."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]
        record = db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="researcher-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Found API rate limiting issue"},
        )

        assert record.id is not None
        assert len(record.id) == 12  # 12-char hex ID
        assert record.swarm_id == swarm_id
        assert record.sender_agent == "researcher-1"
        assert record.broadcast_type == BroadcastType.FINDING
        assert record.payload["finding"] == "Found API rate limiting issue"
        assert record.created_at is not None

    def test_create_broadcast_blocker(self, db):
        """Test creating a blocker broadcast."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]
        record = db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="implementer-2",
            broadcast_type=BroadcastType.BLOCKER,
            payload={
                "blocker": "Cannot access database",
                "severity": "high",
            },
        )

        assert record.broadcast_type == BroadcastType.BLOCKER
        assert record.payload["severity"] == "high"

    def test_create_broadcast_done(self, db):
        """Test creating a done broadcast."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]
        record = db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-complete",
            broadcast_type=BroadcastType.DONE,
            payload={
                "summary": "Completed security analysis",
                "artifacts": {"report": "findings.md"},
            },
        )

        assert record.broadcast_type == BroadcastType.DONE
        assert record.payload["summary"] == "Completed security analysis"

    def test_create_broadcast_abort(self, db):
        """Test creating an abort broadcast."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]
        record = db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="coordinator",
            broadcast_type=BroadcastType.ABORT,
            payload={
                "reason": "Critical error detected",
                "error_code": "E500",
            },
        )

        assert record.broadcast_type == BroadcastType.ABORT
        assert record.payload["reason"] == "Critical error detected"

    def test_create_broadcast_question(self, db):
        """Test creating a question broadcast."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]
        record = db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="researcher",
            broadcast_type=BroadcastType.QUESTION,
            payload={
                "question": "Has anyone found the auth config?",
                "context": "Looking for OAuth settings",
            },
        )

        assert record.broadcast_type == BroadcastType.QUESTION
        assert "auth config" in record.payload["question"]

    def test_create_broadcast_persists_to_db(self, db):
        """Broadcast should be persisted and queryable."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]
        record = db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Test persistence"},
        )

        # Query back the broadcast
        broadcasts = db.get_broadcasts(swarm_id=swarm_id)
        assert len(broadcasts) == 1
        assert broadcasts[0].id == record.id
        assert broadcasts[0].payload["finding"] == "Test persistence"

    def test_create_multiple_broadcasts_same_swarm(self, db):
        """Multiple broadcasts in same swarm should all be stored."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]

        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "First"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Second"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-3",
            broadcast_type=BroadcastType.BLOCKER,
            payload={"blocker": "Stuck"},
        )

        broadcasts = db.get_broadcasts(swarm_id=swarm_id)
        assert len(broadcasts) == 3


class TestGetBroadcasts:
    """Tests for get_broadcasts() method (Phase 4)."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary database."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    @pytest.fixture
    def populated_db(self, db):
        """Database with some broadcasts pre-populated."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = "swarm-test-123"

        # Create broadcasts from different agents
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Pattern A found"},
        )
        time.sleep(0.01)  # Small delay for distinct timestamps

        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Pattern B found"},
        )
        time.sleep(0.01)

        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.BLOCKER,
            payload={"blocker": "Need help"},
        )

        db._test_swarm_id = swarm_id  # Store for test access
        return db

    def test_get_broadcasts_by_swarm(self, populated_db):
        """Test querying broadcasts for specific swarm."""
        swarm_id = populated_db._test_swarm_id
        broadcasts = populated_db.get_broadcasts(swarm_id=swarm_id)

        assert len(broadcasts) == 3
        # Should be ordered by created_at ASC
        assert broadcasts[0].payload["finding"] == "Pattern A found"
        assert broadcasts[1].payload["finding"] == "Pattern B found"

    def test_get_broadcasts_empty_swarm(self, db):
        """Query for non-existent swarm returns empty list."""
        broadcasts = db.get_broadcasts(swarm_id="nonexistent-swarm")
        assert broadcasts == []

    def test_get_broadcasts_since(self, db):
        """Test since filter excludes old broadcasts."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]

        # Create first broadcast
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Old finding"},
        )

        # Record time between broadcasts
        time.sleep(0.02)
        cutoff_time = datetime.now(timezone.utc).replace(tzinfo=None)
        time.sleep(0.02)

        # Create second broadcast after cutoff
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "New finding"},
        )

        # Query with since filter
        broadcasts = db.get_broadcasts(swarm_id=swarm_id, since=cutoff_time)
        assert len(broadcasts) == 1
        assert broadcasts[0].payload["finding"] == "New finding"

    def test_get_broadcasts_exclude_sender(self, populated_db):
        """Test exclude_sender filter works."""
        swarm_id = populated_db._test_swarm_id

        # Exclude agent-1 (who sent 2 broadcasts)
        broadcasts = populated_db.get_broadcasts(
            swarm_id=swarm_id,
            exclude_sender="agent-1"
        )

        assert len(broadcasts) == 1
        assert broadcasts[0].sender_agent == "agent-2"

    def test_get_broadcasts_exclude_sender_not_found(self, populated_db):
        """Excluding non-existent sender returns all broadcasts."""
        swarm_id = populated_db._test_swarm_id

        broadcasts = populated_db.get_broadcasts(
            swarm_id=swarm_id,
            exclude_sender="agent-nonexistent"
        )

        assert len(broadcasts) == 3

    def test_get_broadcasts_by_type_single(self, populated_db):
        """Test filtering by single broadcast type."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = populated_db._test_swarm_id

        # Get only BLOCKER broadcasts
        broadcasts = populated_db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.BLOCKER]
        )

        assert len(broadcasts) == 1
        assert broadcasts[0].broadcast_type == BroadcastType.BLOCKER
        assert "Need help" in broadcasts[0].payload["blocker"]

    def test_get_broadcasts_by_type_multiple(self, db):
        """Test filtering by multiple broadcast types."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]

        # Create various types
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="a1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Found it"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="a2",
            broadcast_type=BroadcastType.BLOCKER,
            payload={"blocker": "Stuck"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="a3",
            broadcast_type=BroadcastType.DONE,
            payload={"summary": "Complete"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="a4",
            broadcast_type=BroadcastType.QUESTION,
            payload={"question": "What now?"},
        )

        # Filter for FINDING and DONE only
        broadcasts = db.get_broadcasts(
            swarm_id=swarm_id,
            broadcast_types=[BroadcastType.FINDING, BroadcastType.DONE]
        )

        assert len(broadcasts) == 2
        types = {b.broadcast_type for b in broadcasts}
        assert types == {BroadcastType.FINDING, BroadcastType.DONE}

    def test_get_broadcasts_combined_filters(self, db):
        """Test combining since, exclude_sender, and broadcast_types filters."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]

        # Create initial broadcasts
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Old from agent-1"},
        )

        time.sleep(0.02)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None)
        time.sleep(0.02)

        # Create broadcasts after cutoff
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "New from agent-1"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "New from agent-2"},
        )
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.BLOCKER,
            payload={"blocker": "Blocker from agent-2"},
        )

        # Combined filter: since cutoff, exclude agent-1, only FINDING type
        broadcasts = db.get_broadcasts(
            swarm_id=swarm_id,
            since=cutoff,
            exclude_sender="agent-1",
            broadcast_types=[BroadcastType.FINDING]
        )

        assert len(broadcasts) == 1
        assert broadcasts[0].sender_agent == "agent-2"
        assert broadcasts[0].broadcast_type == BroadcastType.FINDING


class TestBroadcastSwarmIsolation:
    """Tests for broadcast isolation between swarms."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary database."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    def test_broadcasts_isolated_by_swarm(self, db):
        """Test broadcasts from different swarms don't mix."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_1 = "swarm-alpha"
        swarm_2 = "swarm-beta"

        # Create broadcasts in swarm 1
        db.create_broadcast(
            swarm_id=swarm_1,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Alpha finding 1"},
        )
        db.create_broadcast(
            swarm_id=swarm_1,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Alpha finding 2"},
        )

        # Create broadcasts in swarm 2
        db.create_broadcast(
            swarm_id=swarm_2,
            sender_agent="agent-3",
            broadcast_type=BroadcastType.BLOCKER,
            payload={"blocker": "Beta blocker"},
        )

        # Query swarm 1 - should only see swarm 1 broadcasts
        swarm_1_broadcasts = db.get_broadcasts(swarm_id=swarm_1)
        assert len(swarm_1_broadcasts) == 2
        assert all(b.swarm_id == swarm_1 for b in swarm_1_broadcasts)

        # Query swarm 2 - should only see swarm 2 broadcasts
        swarm_2_broadcasts = db.get_broadcasts(swarm_id=swarm_2)
        assert len(swarm_2_broadcasts) == 1
        assert swarm_2_broadcasts[0].swarm_id == swarm_2
        assert swarm_2_broadcasts[0].payload["blocker"] == "Beta blocker"

    def test_same_agent_different_swarms(self, db):
        """Same agent can broadcast to different swarms independently."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_1 = "swarm-x"
        swarm_2 = "swarm-y"

        # Same agent broadcasts to both swarms
        db.create_broadcast(
            swarm_id=swarm_1,
            sender_agent="shared-agent",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "X finding"},
        )
        db.create_broadcast(
            swarm_id=swarm_2,
            sender_agent="shared-agent",
            broadcast_type=BroadcastType.FINDING,
            payload={"finding": "Y finding"},
        )

        # Each swarm should only see its own broadcast
        x_broadcasts = db.get_broadcasts(swarm_id=swarm_1)
        y_broadcasts = db.get_broadcasts(swarm_id=swarm_2)

        assert len(x_broadcasts) == 1
        assert x_broadcasts[0].payload["finding"] == "X finding"

        assert len(y_broadcasts) == 1
        assert y_broadcasts[0].payload["finding"] == "Y finding"


class TestBroadcastRowConversion:
    """Tests for _row_to_broadcast() helper method (Phase 5)."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary database."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    def test_row_to_broadcast_preserves_all_fields(self, db):
        """Round-trip test: create broadcast, query, verify all fields."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]
        original_payload = {
            "finding": "Important discovery",
            "nested": {"key": "value"},
            "list": [1, 2, 3],
        }

        created = db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="test-agent",
            broadcast_type=BroadcastType.FINDING,
            payload=original_payload,
        )

        # Query back
        queried = db.get_broadcasts(swarm_id=swarm_id)[0]

        assert queried.id == created.id
        assert queried.swarm_id == swarm_id
        assert queried.sender_agent == "test-agent"
        assert queried.broadcast_type == BroadcastType.FINDING
        assert queried.payload == original_payload
        # Timestamps should be close (within 1 second)
        time_diff = abs((queried.created_at - created.created_at).total_seconds())
        assert time_diff < 1

    def test_row_to_broadcast_handles_enum_conversion(self, db):
        """BroadcastType enum should be properly reconstructed from DB."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]

        # Create all broadcast types
        for bt in BroadcastType:
            db.create_broadcast(
                swarm_id=swarm_id,
                sender_agent=f"agent-{bt.value}",
                broadcast_type=bt,
                payload={"type": bt.value},
            )

        # Query and verify enum types
        broadcasts = db.get_broadcasts(swarm_id=swarm_id)
        assert len(broadcasts) == 5

        reconstructed_types = {b.broadcast_type for b in broadcasts}
        assert reconstructed_types == set(BroadcastType)

        # Verify they're actual enum instances, not strings
        for b in broadcasts:
            assert isinstance(b.broadcast_type, BroadcastType)

    def test_row_to_broadcast_handles_empty_payload(self, db):
        """Empty payload should deserialize correctly."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]

        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="minimal-agent",
            broadcast_type=BroadcastType.DONE,
            payload={},
        )

        queried = db.get_broadcasts(swarm_id=swarm_id)[0]
        assert queried.payload == {}

    def test_row_to_broadcast_datetime_parsing(self, db):
        """created_at should be properly parsed as datetime."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]

        before = datetime.now(timezone.utc).replace(tzinfo=None)
        db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="time-agent",
            broadcast_type=BroadcastType.FINDING,
            payload={"test": True},
        )
        after = datetime.now(timezone.utc).replace(tzinfo=None)

        queried = db.get_broadcasts(swarm_id=swarm_id)[0]

        # Should be a datetime instance
        assert isinstance(queried.created_at, datetime)
        # Should be between before and after
        assert before <= queried.created_at <= after


class TestBroadcastTableSchema:
    """Tests for broadcasts table schema (Phase 1)."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary database."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    def test_broadcasts_table_exists(self, db, tmp_path):
        """The broadcasts table should be created with schema init."""
        import sqlite3

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='broadcasts'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "broadcasts"

    def test_broadcasts_table_columns(self, db, tmp_path):
        """The broadcasts table should have all required columns."""
        import sqlite3

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        cursor = conn.execute("PRAGMA table_info(broadcasts)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            "id": "TEXT",
            "swarm_id": "TEXT",
            "sender_agent": "TEXT",
            "broadcast_type": "TEXT",
            "payload": "TEXT",
            "created_at": "TEXT",
        }

        for col_name, col_type in expected_columns.items():
            assert col_name in columns, f"Missing column: {col_name}"
            assert columns[col_name] == col_type, f"Wrong type for {col_name}"

    def test_broadcasts_index_exists(self, db, tmp_path):
        """Index on swarm_id, created_at should exist."""
        import sqlite3

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_broadcasts_swarm'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "idx_broadcasts_swarm"


class TestBroadcastEdgeCases:
    """Edge case tests for broadcast functionality."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create temporary database."""
        from scripts.agentica_patterns.coordination import CoordinationDB

        return CoordinationDB(
            db_path=tmp_path / "test.db",
            session_id="test-session"
        )

    def test_large_payload(self, db):
        """Should handle reasonably large payloads."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]
        large_payload = {
            "finding": "x" * 10000,  # 10KB of text
            "data": list(range(1000)),  # 1000 numbers
        }

        created = db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="large-agent",
            broadcast_type=BroadcastType.FINDING,
            payload=large_payload,
        )

        queried = db.get_broadcasts(swarm_id=swarm_id)[0]
        assert queried.payload == large_payload

    def test_special_characters_in_payload(self, db):
        """Should handle special characters in payload."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]
        special_payload = {
            "finding": "Special chars: \"quotes\" 'apostrophe' \\ backslash",
            "unicode": "Unicode: \u00e9 \u4e2d\u6587 \U0001F600",
            "newlines": "Line1\nLine2\rLine3\r\n",
            "json_like": '{"nested": "json as string"}',
        }

        created = db.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="special-agent",
            broadcast_type=BroadcastType.FINDING,
            payload=special_payload,
        )

        queried = db.get_broadcasts(swarm_id=swarm_id)[0]
        assert queried.payload == special_payload

    def test_concurrent_broadcasts_same_swarm(self, tmp_path):
        """Multiple DB connections can write broadcasts concurrently."""
        from scripts.agentica_patterns.coordination import CoordinationDB, BroadcastType

        swarm_id = uuid4().hex[:12]
        db_path = tmp_path / "concurrent.db"

        # Create multiple DB connections (simulating concurrent agents)
        db1 = CoordinationDB(db_path=db_path, session_id="s1")
        db2 = CoordinationDB(db_path=db_path, session_id="s2")
        db3 = CoordinationDB(db_path=db_path, session_id="s3")

        # Each connection creates a broadcast
        db1.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-1",
            broadcast_type=BroadcastType.FINDING,
            payload={"from": "db1"},
        )
        db2.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-2",
            broadcast_type=BroadcastType.FINDING,
            payload={"from": "db2"},
        )
        db3.create_broadcast(
            swarm_id=swarm_id,
            sender_agent="agent-3",
            broadcast_type=BroadcastType.FINDING,
            payload={"from": "db3"},
        )

        # Any connection should see all broadcasts
        all_broadcasts = db1.get_broadcasts(swarm_id=swarm_id)
        assert len(all_broadcasts) == 3
        sources = {b.payload["from"] for b in all_broadcasts}
        assert sources == {"db1", "db2", "db3"}

    def test_many_broadcasts_performance(self, db):
        """Should handle many broadcasts efficiently."""
        from scripts.agentica_patterns.coordination import BroadcastType

        swarm_id = uuid4().hex[:12]

        # Create 100 broadcasts
        for i in range(100):
            db.create_broadcast(
                swarm_id=swarm_id,
                sender_agent=f"agent-{i % 10}",
                broadcast_type=BroadcastType.FINDING,
                payload={"index": i, "data": "x" * 100},
            )

        # Query should return all
        broadcasts = db.get_broadcasts(swarm_id=swarm_id)
        assert len(broadcasts) == 100

        # Filtered query
        agent_0_broadcasts = db.get_broadcasts(
            swarm_id=swarm_id,
            exclude_sender="agent-0"
        )
        assert len(agent_0_broadcasts) == 90  # 100 - 10 from agent-0

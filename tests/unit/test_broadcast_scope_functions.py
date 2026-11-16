"""Tests for broadcast scope functions - TDD Implementation.

Tests for Phases 13-16 of the user-triggered Agentica implementation plan.

Functions to test:
- broadcast_finding(finding: str, metadata: dict | None = None)
- broadcast_blocker(blocker: str, severity: str = "medium")
- broadcast_done(summary: str, artifacts: dict | None = None)

These functions allow agents to share discoveries, report blockers,
and signal completion within a swarm.

Test implementation follows strict TDD:
1. Write failing tests (this file)
2. Implement minimal code to pass
3. Verify tests pass
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


# ============================================================================
# Phase 13: broadcast_finding Tests
# ============================================================================


class TestBroadcastFinding:
    """Test broadcast_finding scope function."""

    def test_broadcast_finding_success(self, tmp_path):
        """broadcast_finding returns success with broadcast_id when in swarm."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB

        # Setup: Create coordination DB and set environment
        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-123",
            "AGENT_ID": "agent-1"
        }):
            # Patch CoordinationDB to use our temp DB
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                result = scope["broadcast_finding"]("Found important pattern")

                assert result["success"] is True
                assert "broadcast_id" in result
                assert result["message"] == "Broadcast sent to swarm swarm-123"

    def test_broadcast_finding_not_in_swarm(self):
        """broadcast_finding returns error when SWARM_ID not set."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope

        # Ensure SWARM_ID is not set
        env = os.environ.copy()
        env.pop("SWARM_ID", None)

        with patch.dict(os.environ, env, clear=True):
            scope = create_claude_scope()

            result = scope["broadcast_finding"]("Some finding")

            assert result["success"] is False
            assert "error" in result
            assert "SWARM_ID not set" in result["error"]

    def test_broadcast_finding_with_metadata(self, tmp_path):
        """broadcast_finding includes metadata in payload."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB, BroadcastType

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-456",
            "AGENT_ID": "agent-2"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                metadata = {"file": "main.py", "line": 42, "severity": "high"}
                result = scope["broadcast_finding"](
                    "Found bug in authentication",
                    metadata=metadata
                )

                assert result["success"] is True

                # Verify metadata was persisted
                broadcasts = db.get_broadcasts("swarm-456")
                assert len(broadcasts) == 1
                assert broadcasts[0].payload["metadata"] == metadata

    def test_broadcast_finding_persists_to_db(self, tmp_path):
        """broadcast_finding creates record in broadcasts table."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB, BroadcastType

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-789",
            "AGENT_ID": "agent-3"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                scope["broadcast_finding"]("Discovered optimization opportunity")

                # Query database directly
                broadcasts = db.get_broadcasts("swarm-789")
                assert len(broadcasts) == 1
                assert broadcasts[0].broadcast_type == BroadcastType.FINDING
                assert broadcasts[0].sender_agent == "agent-3"
                assert "Discovered optimization opportunity" in broadcasts[0].payload["finding"]


# ============================================================================
# Phase 14: broadcast_blocker Tests
# ============================================================================


class TestBroadcastBlocker:
    """Test broadcast_blocker scope function."""

    def test_broadcast_blocker_success(self, tmp_path):
        """broadcast_blocker returns success with broadcast_id."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-block-1",
            "AGENT_ID": "agent-stuck"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                result = scope["broadcast_blocker"](
                    "Cannot find authentication module"
                )

                assert result["success"] is True
                assert "broadcast_id" in result

    def test_broadcast_blocker_not_in_swarm(self):
        """broadcast_blocker returns error when SWARM_ID not set."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope

        env = os.environ.copy()
        env.pop("SWARM_ID", None)

        with patch.dict(os.environ, env, clear=True):
            scope = create_claude_scope()

            result = scope["broadcast_blocker"]("I'm stuck")

            assert result["success"] is False
            assert "error" in result
            assert "SWARM_ID not set" in result["error"]

    def test_broadcast_blocker_severity_levels(self, tmp_path):
        """broadcast_blocker accepts low/medium/high severity."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB, BroadcastType

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-severity",
            "AGENT_ID": "agent-sev"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                # Test all severity levels
                for severity in ["low", "medium", "high"]:
                    result = scope["broadcast_blocker"](
                        f"Blocker with {severity} severity",
                        severity=severity
                    )
                    assert result["success"] is True

                # Verify severity was persisted
                broadcasts = db.get_broadcasts("swarm-severity")
                assert len(broadcasts) == 3

                severities = [b.payload["severity"] for b in broadcasts]
                assert "low" in severities
                assert "medium" in severities
                assert "high" in severities

    def test_broadcast_blocker_default_severity(self, tmp_path):
        """broadcast_blocker defaults to medium severity."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-default",
            "AGENT_ID": "agent-def"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                scope["broadcast_blocker"]("Blocked without severity")

                broadcasts = db.get_broadcasts("swarm-default")
                assert len(broadcasts) == 1
                assert broadcasts[0].payload["severity"] == "medium"

    def test_broadcast_blocker_persists_to_db(self, tmp_path):
        """broadcast_blocker creates record in broadcasts table."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB, BroadcastType

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-persist",
            "AGENT_ID": "agent-p"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                scope["broadcast_blocker"](
                    "Database connection failed",
                    severity="high"
                )

                broadcasts = db.get_broadcasts("swarm-persist")
                assert len(broadcasts) == 1
                assert broadcasts[0].broadcast_type == BroadcastType.BLOCKER
                assert broadcasts[0].sender_agent == "agent-p"
                assert "Database connection failed" in broadcasts[0].payload["blocker"]


# ============================================================================
# Phase 15: broadcast_done Tests
# ============================================================================


class TestBroadcastDone:
    """Test broadcast_done scope function."""

    def test_broadcast_done_success(self, tmp_path):
        """broadcast_done returns success with broadcast_id."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-done-1",
            "AGENT_ID": "agent-complete"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                result = scope["broadcast_done"]("Completed security analysis")

                assert result["success"] is True
                assert "broadcast_id" in result

    def test_broadcast_done_not_in_swarm(self):
        """broadcast_done returns error when SWARM_ID not set."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope

        env = os.environ.copy()
        env.pop("SWARM_ID", None)

        with patch.dict(os.environ, env, clear=True):
            scope = create_claude_scope()

            result = scope["broadcast_done"]("I'm done")

            assert result["success"] is False
            assert "error" in result
            assert "Not in a swarm" in result["error"]

    def test_broadcast_done_with_artifacts(self, tmp_path):
        """broadcast_done includes artifacts in payload."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB, BroadcastType

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-artifacts",
            "AGENT_ID": "agent-art"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                artifacts = {
                    "report_path": "/tmp/security-report.md",
                    "vulnerabilities_found": 3,
                    "recommendations": ["Fix XSS", "Update deps", "Add CSP"]
                }
                result = scope["broadcast_done"](
                    "Security analysis complete",
                    artifacts=artifacts
                )

                assert result["success"] is True

                # Verify artifacts were persisted
                broadcasts = db.get_broadcasts("swarm-artifacts")
                assert len(broadcasts) == 1
                assert broadcasts[0].payload["artifacts"] == artifacts

    def test_broadcast_done_empty_artifacts(self, tmp_path):
        """broadcast_done handles None artifacts."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-no-art",
            "AGENT_ID": "agent-simple"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                result = scope["broadcast_done"]("Just finished, no artifacts")

                assert result["success"] is True

                broadcasts = db.get_broadcasts("swarm-no-art")
                assert len(broadcasts) == 1
                assert broadcasts[0].payload["artifacts"] == {}

    def test_broadcast_done_persists_to_db(self, tmp_path):
        """broadcast_done creates record in broadcasts table."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB, BroadcastType

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-done-db",
            "AGENT_ID": "agent-db"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                scope["broadcast_done"](
                    "All tasks completed successfully",
                    artifacts={"files_created": ["a.py", "b.py"]}
                )

                broadcasts = db.get_broadcasts("swarm-done-db")
                assert len(broadcasts) == 1
                assert broadcasts[0].broadcast_type == BroadcastType.DONE
                assert broadcasts[0].sender_agent == "agent-db"
                assert "All tasks completed" in broadcasts[0].payload["summary"]


# ============================================================================
# Phase 16: create_claude_scope Integration Tests
# ============================================================================


class TestScopeIncludesBroadcastFunctions:
    """Test that create_claude_scope includes all broadcast functions."""

    def test_scope_includes_broadcast_finding(self):
        """create_claude_scope includes broadcast_finding function."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope

        scope = create_claude_scope()

        assert "broadcast_finding" in scope
        assert callable(scope["broadcast_finding"])

    def test_scope_includes_broadcast_blocker(self):
        """create_claude_scope includes broadcast_blocker function."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope

        scope = create_claude_scope()

        assert "broadcast_blocker" in scope
        assert callable(scope["broadcast_blocker"])

    def test_scope_includes_broadcast_done(self):
        """create_claude_scope includes broadcast_done function."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope

        scope = create_claude_scope()

        assert "broadcast_done" in scope
        assert callable(scope["broadcast_done"])

    def test_all_broadcast_functions_present(self):
        """All three broadcast functions should be in scope."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope

        scope = create_claude_scope()

        broadcast_functions = [
            "broadcast_finding",
            "broadcast_blocker",
            "broadcast_done"
        ]

        for func_name in broadcast_functions:
            assert func_name in scope, f"{func_name} missing from scope"
            assert callable(scope[func_name]), f"{func_name} is not callable"


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestBroadcastEdgeCases:
    """Test edge cases for broadcast functions."""

    def test_broadcast_with_empty_finding(self, tmp_path):
        """broadcast_finding handles empty string."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-empty",
            "AGENT_ID": "agent-e"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                result = scope["broadcast_finding"]("")

                # Should still succeed even with empty finding
                assert result["success"] is True

    def test_broadcast_with_unicode_content(self, tmp_path):
        """broadcast_finding handles unicode content."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-unicode",
            "AGENT_ID": "agent-u"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                result = scope["broadcast_finding"](
                    "Found issue with encoding: \u00e9\u00e0\u00f1\u4e2d\u6587"
                )

                assert result["success"] is True

                broadcasts = db.get_broadcasts("swarm-unicode")
                assert "\u4e2d\u6587" in broadcasts[0].payload["finding"]

    def test_broadcast_with_large_metadata(self, tmp_path):
        """broadcast_finding handles large metadata dict."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {
            "SWARM_ID": "swarm-large",
            "AGENT_ID": "agent-l"
        }):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                large_metadata = {f"key_{i}": f"value_{i}" * 100 for i in range(50)}
                result = scope["broadcast_finding"](
                    "Finding with large metadata",
                    metadata=large_metadata
                )

                assert result["success"] is True

    def test_default_agent_id_when_not_set(self, tmp_path):
        """broadcast functions use 'unknown' when AGENT_ID not set."""
        from scripts.agentica_patterns.claude_scope import create_claude_scope
        from scripts.agentica_patterns.coordination import CoordinationDB

        db = CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

        with patch.dict(os.environ, {"SWARM_ID": "swarm-no-agent"}, clear=True):
            with patch(
                'scripts.agentica_patterns.claude_scope.CoordinationDB',
                return_value=db
            ):
                scope = create_claude_scope()

                scope["broadcast_finding"]("Finding from unknown agent")

                broadcasts = db.get_broadcasts("swarm-no-agent")
                assert len(broadcasts) == 1
                assert broadcasts[0].sender_agent == "unknown"

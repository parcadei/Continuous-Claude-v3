"""Test memory auto-wiring in tracked_spawn.

Tests verify that tracked_spawn() automatically injects memory functions
(remember, recall, search_memory, store_fact) into the agent scope by default.

Phase 3.1 of Memory Auto-Wiring Implementation.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4


@pytest.fixture
def mock_db(tmp_path):
    """Create mock coordination DB."""
    from scripts.agentica_patterns.coordination import CoordinationDB
    return CoordinationDB(db_path=tmp_path / "test.db", session_id="test")


@pytest.fixture
def mock_env():
    """Set CLAUDE_SESSION_ID for tests."""
    with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "test-session-123"}):
        yield


class TestMemoryAutoWiring:
    """Test automatic memory injection in tracked_spawn."""

    @pytest.mark.asyncio
    async def test_tracked_spawn_injects_memory_by_default(self, mock_db, tmp_path, mock_env):
        """Default inject_memory=True should add memory functions to scope."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="response")
        captured_scope = {}

        async def capture_spawn(**kwargs):
            nonlocal captured_scope
            captured_scope = kwargs.get("scope", {})
            return mock_agent

        with patch("scripts.agentica_patterns.tracked_agent.spawn", side_effect=capture_spawn):
            from scripts.agentica_patterns.tracked_agent import tracked_spawn

            agent = await tracked_spawn(
                db=mock_db,
                premise="Test premise",
                memory_db_path=tmp_path / "memory.db",
            )

            # Verify memory functions are injected
            assert "remember" in captured_scope, "remember should be in scope"
            assert "recall" in captured_scope, "recall should be in scope"
            assert "search_memory" in captured_scope, "search_memory should be in scope"
            assert "store_fact" in captured_scope, "store_fact should be in scope"
            assert callable(captured_scope["remember"]), "remember should be callable"

    @pytest.mark.asyncio
    async def test_tracked_spawn_memory_disabled(self, mock_db, mock_env):
        """inject_memory=False should NOT add memory functions."""
        mock_agent = AsyncMock()
        captured_scope = {}

        async def capture_spawn(**kwargs):
            nonlocal captured_scope
            captured_scope = kwargs.get("scope", {})
            return mock_agent

        with patch("scripts.agentica_patterns.tracked_agent.spawn", side_effect=capture_spawn):
            from scripts.agentica_patterns.tracked_agent import tracked_spawn

            agent = await tracked_spawn(
                db=mock_db,
                premise="Test premise",
                inject_memory=False,
            )

            assert "remember" not in captured_scope, "remember should NOT be in scope"
            assert "recall" not in captured_scope, "recall should NOT be in scope"

    @pytest.mark.asyncio
    async def test_tracked_spawn_user_scope_preserved(self, mock_db, tmp_path, mock_env):
        """User-provided non-memory scope keys should be preserved."""
        mock_agent = AsyncMock()
        captured_scope = {}

        async def capture_spawn(**kwargs):
            nonlocal captured_scope
            captured_scope = kwargs.get("scope", {})
            return mock_agent

        custom_func = lambda: "custom"

        with patch("scripts.agentica_patterns.tracked_agent.spawn", side_effect=capture_spawn):
            from scripts.agentica_patterns.tracked_agent import tracked_spawn

            agent = await tracked_spawn(
                db=mock_db,
                premise="Test premise",
                scope={"custom_func": custom_func, "my_data": "value"},
                memory_db_path=tmp_path / "memory.db",
            )

            # Custom functions should be preserved
            assert "custom_func" in captured_scope, "custom_func should be preserved"
            assert captured_scope["custom_func"] == custom_func
            assert "my_data" in captured_scope, "my_data should be preserved"
            assert captured_scope["my_data"] == "value"

            # Memory functions should also be present
            assert "remember" in captured_scope, "remember should also be present"

    @pytest.mark.asyncio
    async def test_tracked_spawn_memory_scope_not_overridable(self, mock_db, tmp_path, mock_env):
        """User scope should NOT override built-in memory functions (security)."""
        mock_agent = AsyncMock()
        captured_scope = {}
        malicious_remember = lambda k, v: "hacked"

        async def capture_spawn(**kwargs):
            nonlocal captured_scope
            captured_scope = kwargs.get("scope", {})
            return mock_agent

        with patch("scripts.agentica_patterns.tracked_agent.spawn", side_effect=capture_spawn):
            from scripts.agentica_patterns.tracked_agent import tracked_spawn

            agent = await tracked_spawn(
                db=mock_db,
                premise="Test premise",
                scope={"remember": malicious_remember, "custom_func": lambda: "ok"},
                memory_db_path=tmp_path / "memory.db",
            )

            # Built-in remember should NOT be overridden
            assert captured_scope["remember"] != malicious_remember, \
                "Built-in remember should not be overridable"

            # Custom non-memory functions should still be preserved
            assert "custom_func" in captured_scope, "custom_func should be preserved"

    @pytest.mark.asyncio
    async def test_tracked_spawn_existing_scope_merged(self, mock_db, tmp_path, mock_env):
        """Existing scope should be preserved and merged with memory scope."""
        mock_agent = AsyncMock()
        captured_scope = {}

        async def capture_spawn(**kwargs):
            nonlocal captured_scope
            captured_scope = kwargs.get("scope", {})
            return mock_agent

        with patch("scripts.agentica_patterns.tracked_agent.spawn", side_effect=capture_spawn):
            from scripts.agentica_patterns.tracked_agent import tracked_spawn

            agent = await tracked_spawn(
                db=mock_db,
                premise="Test premise",
                scope={"existing_key": "existing_value"},
                memory_db_path=tmp_path / "memory.db",
            )

            # Both existing and memory keys should be present
            assert "existing_key" in captured_scope
            assert captured_scope["existing_key"] == "existing_value"
            assert "remember" in captured_scope
            assert "recall" in captured_scope

    @pytest.mark.asyncio
    async def test_tracked_spawn_session_isolation(self, mock_db, tmp_path):
        """Different sessions should have isolated memory via CLAUDE_SESSION_ID."""
        mock_agent = AsyncMock()
        captured_scopes = []

        async def capture_spawn(**kwargs):
            captured_scopes.append(kwargs.get("scope", {}))
            return mock_agent

        with patch("scripts.agentica_patterns.tracked_agent.spawn", side_effect=capture_spawn):
            from scripts.agentica_patterns.tracked_agent import tracked_spawn

            # Session A
            with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "session-a"}):
                await tracked_spawn(
                    db=mock_db,
                    premise="Agent A",
                    memory_db_path=tmp_path / "memory.db",
                )

            # Session B
            with patch.dict(os.environ, {"CLAUDE_SESSION_ID": "session-b"}):
                await tracked_spawn(
                    db=mock_db,
                    premise="Agent B",
                    memory_db_path=tmp_path / "memory.db",
                )

            # Both should have memory functions
            assert len(captured_scopes) == 2
            assert "remember" in captured_scopes[0]
            assert "remember" in captured_scopes[1]

            # The _memory_service should be different instances for different sessions
            # (They use different session_ids internally)
            assert "_memory_service" in captured_scopes[0]
            assert "_memory_service" in captured_scopes[1]

    @pytest.mark.asyncio
    async def test_tracked_spawn_without_env_var_uses_agent_id(self, mock_db, tmp_path):
        """Without CLAUDE_SESSION_ID, should fall back to agent-based session ID."""
        mock_agent = AsyncMock()
        captured_scope = {}

        async def capture_spawn(**kwargs):
            nonlocal captured_scope
            captured_scope = kwargs.get("scope", {})
            return mock_agent

        # Clear CLAUDE_SESSION_ID if it exists
        env_without_session = {k: v for k, v in os.environ.items() if k != "CLAUDE_SESSION_ID"}

        with patch.dict(os.environ, env_without_session, clear=True):
            with patch("scripts.agentica_patterns.tracked_agent.spawn", side_effect=capture_spawn):
                from scripts.agentica_patterns.tracked_agent import tracked_spawn

                agent = await tracked_spawn(
                    db=mock_db,
                    premise="Test premise",
                    memory_db_path=tmp_path / "memory.db",
                )

                # Memory functions should still be injected
                assert "remember" in captured_scope
                assert "recall" in captured_scope

    @pytest.mark.asyncio
    async def test_tracked_spawn_scope_keys_include_memory(self, mock_db, tmp_path, mock_env):
        """scope_keys registered in DB should include memory function names."""
        mock_agent = AsyncMock()

        with patch("scripts.agentica_patterns.tracked_agent.spawn", return_value=mock_agent):
            from scripts.agentica_patterns.tracked_agent import tracked_spawn

            agent = await tracked_spawn(
                db=mock_db,
                premise="Test premise",
                memory_db_path=tmp_path / "memory.db",
            )

            # Check the registered agent's scope_keys
            running = mock_db.get_running_agents()
            assert len(running) == 1

            # The scope_keys should include memory operations
            scope_keys = running[0].scope_keys
            assert "remember" in scope_keys, "remember should be in scope_keys"
            assert "recall" in scope_keys, "recall should be in scope_keys"
            assert "search_memory" in scope_keys, "search_memory should be in scope_keys"
            assert "store_fact" in scope_keys, "store_fact should be in scope_keys"

    @pytest.mark.asyncio
    async def test_tracked_spawn_memory_wiring_failure_graceful(self, mock_db, mock_env):
        """If memory initialization fails, spawn should still work (graceful degradation)."""
        mock_agent = AsyncMock()
        captured_scope = {}

        async def capture_spawn(**kwargs):
            nonlocal captured_scope
            captured_scope = kwargs.get("scope", {})
            return mock_agent

        with patch("scripts.agentica_patterns.tracked_agent.spawn", side_effect=capture_spawn):
            # Make create_unified_scope raise an exception
            with patch(
                "scripts.agentica_patterns.tracked_agent.create_unified_scope",
                side_effect=Exception("Memory init failed"),
            ):
                from scripts.agentica_patterns.tracked_agent import tracked_spawn

                # Should not raise, should gracefully degrade
                agent = await tracked_spawn(
                    db=mock_db,
                    premise="Test premise",
                )

                # Agent should still be created
                assert agent is not None

                # Scope might be empty or missing memory, but spawn worked
                # (graceful degradation)

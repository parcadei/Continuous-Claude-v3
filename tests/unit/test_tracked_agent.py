"""Tests for TrackedAgent and tracked_spawn."""

import pytest
from unittest.mock import AsyncMock, patch


class TestTrackedSpawn:
    """Test tracked_spawn factory function."""

    @pytest.fixture
    def mock_db(self, tmp_path):
        from scripts.agentica_patterns.coordination import CoordinationDB
        return CoordinationDB(db_path=tmp_path / "test.db", session_id="test")

    @pytest.mark.asyncio
    async def test_tracked_spawn_registers_agent(self, mock_db):
        """tracked_spawn should register agent in DB."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="response")

        with patch("scripts.agentica_patterns.tracked_agent.spawn", return_value=mock_agent):
            from scripts.agentica_patterns.tracked_agent import tracked_spawn

            agent = await tracked_spawn(
                db=mock_db,
                premise="Test premise",
                model="claude-sonnet",
                pattern="swarm",
            )

            running = mock_db.get_running_agents()
            assert len(running) == 1
            assert running[0].premise == "Test premise"

    @pytest.mark.asyncio
    async def test_tracked_spawn_without_db(self):
        """tracked_spawn should work without DB (db=None)."""
        mock_agent = AsyncMock()
        mock_agent.call = AsyncMock(return_value="response")

        with patch("scripts.agentica_patterns.tracked_agent.spawn", return_value=mock_agent):
            from scripts.agentica_patterns.tracked_agent import tracked_spawn

            agent = await tracked_spawn(db=None, premise="Test premise")
            result = await agent.call(str, "test")
            assert result == "response"

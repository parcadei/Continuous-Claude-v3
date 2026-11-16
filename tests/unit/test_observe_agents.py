"""Tests for agent observation script.

Tests cover:
- PostgreSQL memory table queries
- Blackboard HOT tier JSON reading
- Task graph SQLite queries
- Agent output file listing
- Combined observation across all sources

Prerequisites:
- PostgreSQL + pgvector for memory tests (docker/start-postgres.sh)
- Blackboard directory for blackboard tests

Run with:
    uv run pytest tests/unit/test_observe_agents.py -v
"""

import asyncio
import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def unique_session_id() -> str:
    """Generate a unique session ID for test isolation."""
    return f"test-observe-{uuid4().hex[:8]}"


class TestQueryMemory:
    """Test querying PostgreSQL memory tables."""

    @pytest.mark.asyncio
    async def test_query_memory_returns_list(self):
        """Should return a list of memory records."""
        # Mock asyncpg module before importing
        import sys
        mock_asyncpg = MagicMock()
        mock_rows = [
            {
                "id": "mem-1",
                "session_id": "sess-1",
                "agent_id": "agent-1",
                "content": "Test memory content",
                "created_at": datetime.now(),
            }
        ]

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=mock_rows)
        mock_conn.close = AsyncMock()
        mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

        with patch.dict(sys.modules, {"asyncpg": mock_asyncpg}):
            # Re-import to pick up the mock
            if "scripts.observe_agents" in sys.modules:
                del sys.modules["scripts.observe_agents"]
            from scripts.observe_agents import query_memory

            result = await query_memory(query="Test")

            assert isinstance(result, list)
            mock_conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_memory_with_session_filter(self):
        """Should filter by session ID when provided."""
        import sys
        mock_asyncpg = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.close = AsyncMock()
        mock_asyncpg.connect = AsyncMock(return_value=mock_conn)

        with patch.dict(sys.modules, {"asyncpg": mock_asyncpg}):
            if "scripts.observe_agents" in sys.modules:
                del sys.modules["scripts.observe_agents"]
            from scripts.observe_agents import query_memory

            await query_memory(session_id="specific-session")

            # Verify session_id was passed to the query
            call_args = mock_conn.fetch.call_args
            assert call_args[0][2] == "specific-session"

    @pytest.mark.asyncio
    async def test_query_memory_handles_connection_error(self):
        """Should handle connection errors gracefully."""
        import sys
        mock_asyncpg = MagicMock()
        mock_asyncpg.connect = AsyncMock(side_effect=Exception("Connection failed"))

        with patch.dict(sys.modules, {"asyncpg": mock_asyncpg}):
            if "scripts.observe_agents" in sys.modules:
                del sys.modules["scripts.observe_agents"]
            from scripts.observe_agents import query_memory

            result = await query_memory()

            # Should return empty list on error
            assert result == []


class TestReadBlackboard:
    """Test reading blackboard JSON files."""

    def test_read_blackboard_returns_dict(self):
        """Should return a dictionary of blackboard contents."""
        from scripts.observe_agents import read_blackboard

        with tempfile.TemporaryDirectory() as tmpdir:
            bb_dir = Path(tmpdir)

            # Create test blackboard file
            test_data = {"key": "value", "items": [1, 2, 3]}
            (bb_dir / "test-board.json").write_text(json.dumps(test_data))

            with patch("scripts.observe_agents.BLACKBOARD_DIR", bb_dir):
                result = read_blackboard()

            assert isinstance(result, dict)
            assert "test-board" in result
            assert result["test-board"]["key"] == "value"

    def test_read_blackboard_handles_invalid_json(self):
        """Should handle invalid JSON files gracefully."""
        from scripts.observe_agents import read_blackboard

        with tempfile.TemporaryDirectory() as tmpdir:
            bb_dir = Path(tmpdir)

            # Create invalid JSON file
            (bb_dir / "invalid.json").write_text("not valid json {{{")

            with patch("scripts.observe_agents.BLACKBOARD_DIR", bb_dir):
                result = read_blackboard()

            assert "invalid" in result
            assert "error" in result["invalid"]

    def test_read_blackboard_handles_missing_dir(self):
        """Should return empty dict if blackboard dir doesn't exist."""
        from scripts.observe_agents import read_blackboard

        with patch("scripts.observe_agents.BLACKBOARD_DIR", Path("/nonexistent/path")):
            result = read_blackboard()

        assert result == {}

    def test_read_blackboard_multiple_files(self):
        """Should read all JSON files in directory."""
        from scripts.observe_agents import read_blackboard

        with tempfile.TemporaryDirectory() as tmpdir:
            bb_dir = Path(tmpdir)

            # Create multiple blackboard files
            (bb_dir / "board1.json").write_text('{"data": "one"}')
            (bb_dir / "board2.json").write_text('{"data": "two"}')
            (bb_dir / "board3.json").write_text('{"data": "three"}')

            with patch("scripts.observe_agents.BLACKBOARD_DIR", bb_dir):
                result = read_blackboard()

            assert len(result) == 3
            assert result["board1"]["data"] == "one"
            assert result["board2"]["data"] == "two"
            assert result["board3"]["data"] == "three"


class TestQueryTaskGraph:
    """Test querying task SQLite database."""

    def test_query_task_graph_returns_list(self):
        """Should return a list of task records."""
        from scripts.observe_agents import query_task_graph

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "tasks.db"

            # Create test database
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    agent_id TEXT,
                    status TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("""
                INSERT INTO tasks VALUES (?, ?, ?, ?, ?)
            """, ("task-1", "sess-1", "agent-1", "completed", datetime.now().isoformat()))
            conn.commit()
            conn.close()

            with patch("scripts.observe_agents.TASKS_DB", db_path):
                result = query_task_graph()

            assert isinstance(result, list)
            assert len(result) == 1
            assert result[0]["id"] == "task-1"

    def test_query_task_graph_filters_by_session(self):
        """Should filter by session ID when provided."""
        from scripts.observe_agents import query_task_graph

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "tasks.db"

            # Create test database with multiple sessions
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    status TEXT,
                    created_at TEXT
                )
            """)
            conn.execute("INSERT INTO tasks VALUES (?, ?, ?, ?)",
                        ("task-1", "sess-1", "completed", datetime.now().isoformat()))
            conn.execute("INSERT INTO tasks VALUES (?, ?, ?, ?)",
                        ("task-2", "sess-2", "pending", datetime.now().isoformat()))
            conn.commit()
            conn.close()

            with patch("scripts.observe_agents.TASKS_DB", db_path):
                result = query_task_graph(session_id="sess-1")

            assert len(result) == 1
            assert result[0]["session_id"] == "sess-1"

    def test_query_task_graph_handles_missing_db(self):
        """Should return empty list if database doesn't exist."""
        from scripts.observe_agents import query_task_graph

        with patch("scripts.observe_agents.TASKS_DB", Path("/nonexistent/tasks.db")):
            result = query_task_graph()

        assert result == []

    def test_query_task_graph_handles_missing_table(self):
        """Should handle missing tasks table gracefully."""
        from scripts.observe_agents import query_task_graph

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "tasks.db"

            # Create empty database (no tasks table)
            conn = sqlite3.connect(db_path)
            conn.close()

            with patch("scripts.observe_agents.TASKS_DB", db_path):
                result = query_task_graph()

            assert result == []


class TestListAgentOutputs:
    """Test listing agent output files."""

    def test_list_agent_outputs_returns_list(self):
        """Should return a list of output file metadata."""
        from scripts.observe_agents import list_agent_outputs

        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)

            # Create agent output files
            agent1_dir = agents_dir / "agent-1"
            agent1_dir.mkdir()
            (agent1_dir / "output.md").write_text("# Agent 1 Output")
            (agent1_dir / "summary.md").write_text("# Summary")

            with patch("scripts.observe_agents.AGENTS_DIR", agents_dir):
                result = list_agent_outputs()

            assert isinstance(result, list)
            assert len(result) == 2
            assert all("agent" in r for r in result)
            assert all("file" in r for r in result)
            assert all("path" in r for r in result)
            assert all("modified" in r for r in result)
            assert all("size" in r for r in result)

    def test_list_agent_outputs_sorted_by_modified(self):
        """Should return outputs sorted by modification time (newest first)."""
        from scripts.observe_agents import list_agent_outputs
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)
            agent_dir = agents_dir / "agent-1"
            agent_dir.mkdir()

            # Create files with different timestamps
            old_file = agent_dir / "old.md"
            old_file.write_text("old")
            time.sleep(0.1)
            new_file = agent_dir / "new.md"
            new_file.write_text("new")

            with patch("scripts.observe_agents.AGENTS_DIR", agents_dir):
                result = list_agent_outputs()

            assert result[0]["file"] == "new.md"
            assert result[1]["file"] == "old.md"

    def test_list_agent_outputs_handles_missing_dir(self):
        """Should return empty list if agents dir doesn't exist."""
        from scripts.observe_agents import list_agent_outputs

        with patch("scripts.observe_agents.AGENTS_DIR", Path("/nonexistent/agents")):
            result = list_agent_outputs()

        assert result == []

    def test_list_agent_outputs_multiple_agents(self):
        """Should list outputs from multiple agent directories."""
        from scripts.observe_agents import list_agent_outputs

        with tempfile.TemporaryDirectory() as tmpdir:
            agents_dir = Path(tmpdir)

            # Create multiple agent directories
            for agent_name in ["agent-1", "agent-2", "agent-3"]:
                agent_dir = agents_dir / agent_name
                agent_dir.mkdir()
                (agent_dir / "output.md").write_text(f"# {agent_name} output")

            with patch("scripts.observe_agents.AGENTS_DIR", agents_dir):
                result = list_agent_outputs()

            assert len(result) == 3
            agents = {r["agent"] for r in result}
            assert agents == {"agent-1", "agent-2", "agent-3"}


class TestObserveAll:
    """Test combined observation of all sources."""

    @pytest.mark.asyncio
    async def test_observe_all_returns_combined_dict(self):
        """Should return a dictionary with all observation sources."""
        from scripts.observe_agents import observe_all

        with patch("scripts.observe_agents.query_memory", AsyncMock(return_value=[])), \
             patch("scripts.observe_agents.read_blackboard", return_value={}), \
             patch("scripts.observe_agents.query_task_graph", return_value=[]), \
             patch("scripts.observe_agents.list_agent_outputs", return_value=[]):

            result = await observe_all()

            assert isinstance(result, dict)
            assert "timestamp" in result
            assert "memory" in result
            assert "blackboard" in result
            assert "tasks" in result
            assert "outputs" in result

    @pytest.mark.asyncio
    async def test_observe_all_includes_counts(self):
        """Should include counts for each source."""
        from scripts.observe_agents import observe_all

        mock_memory = [{"id": "1"}, {"id": "2"}]
        mock_blackboard = {"board1": {}, "board2": {}}
        mock_tasks = [{"id": "t1"}]
        mock_outputs = [{"file": "f1"}, {"file": "f2"}, {"file": "f3"}]

        with patch("scripts.observe_agents.query_memory", AsyncMock(return_value=mock_memory)), \
             patch("scripts.observe_agents.read_blackboard", return_value=mock_blackboard), \
             patch("scripts.observe_agents.query_task_graph", return_value=mock_tasks), \
             patch("scripts.observe_agents.list_agent_outputs", return_value=mock_outputs):

            result = await observe_all()

            assert result["memory"]["count"] == 2
            assert result["blackboard"]["count"] == 2
            assert result["tasks"]["count"] == 1
            assert result["outputs"]["count"] == 3

    @pytest.mark.asyncio
    async def test_observe_all_passes_filters(self):
        """Should pass query and session_id filters to relevant sources."""
        from scripts.observe_agents import observe_all

        mock_query_memory = AsyncMock(return_value=[])
        mock_query_tasks = MagicMock(return_value=[])

        with patch("scripts.observe_agents.query_memory", mock_query_memory), \
             patch("scripts.observe_agents.read_blackboard", return_value={}), \
             patch("scripts.observe_agents.query_task_graph", mock_query_tasks), \
             patch("scripts.observe_agents.list_agent_outputs", return_value=[]):

            await observe_all(query="test query", session_id="test-session")

            mock_query_memory.assert_called_once_with("test query", "test-session")
            mock_query_tasks.assert_called_once_with("test-session")


class TestIntegrationWithRealData:
    """Integration tests with real data sources (skipped if not available)."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not Path("/tmp/claude-blackboard").exists(),
        reason="Blackboard directory not available"
    )
    async def test_real_blackboard_reading(self):
        """Test reading actual blackboard files."""
        from scripts.observe_agents import read_blackboard

        result = read_blackboard()

        # Should return dict even if empty
        assert isinstance(result, dict)

    @pytest.mark.skipif(
        not Path("/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/.claude/cache/agents").exists(),
        reason="Agents cache not available"
    )
    def test_real_agent_outputs(self):
        """Test listing actual agent output files."""
        from scripts.observe_agents import list_agent_outputs

        result = list_agent_outputs()

        # Should return list even if empty
        assert isinstance(result, list)


class TestCLIInterface:
    """Test command-line interface."""

    def test_main_requires_what_argument(self):
        """Should require --what argument."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "scripts.observe_agents"],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
        )

        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_help_output(self):
        """Should provide helpful usage information."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "scripts.observe_agents", "--help"],
            capture_output=True,
            text=True,
            cwd="/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit"
        )

        assert result.returncode == 0
        assert "memory" in result.stdout
        assert "blackboard" in result.stdout
        assert "tasks" in result.stdout
        assert "outputs" in result.stdout

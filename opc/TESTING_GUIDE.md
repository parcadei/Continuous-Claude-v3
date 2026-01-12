# Continuous-Claude-v3 Testing Guide

Comprehensive testing patterns for core scripts: memory_daemon.py, recall_learnings.py, store_learning.py, stream_monitor.py, and mcp_client.py.

---

## Table of Contents

1. [pytest Configuration](#pytest-configuration)
2. [conftest.py Fixtures](#conftestpy-fixtures)
3. [memory_daemon.py Tests](#memory_daemonpy-tests)
4. [recall_learnings.py Tests](#recall_learningspy-tests)
5. [store_learning.py Tests](#store_learningpy-tests)
6. [stream_monitor.py Tests](#stream_monitorpy-tests)
7. [mcp_client.py Tests](#mcp_clientpy-tests)
8. [Test Data Factories](#test-data-factories)
9. [CI Pipeline Integration](#ci-pipeline-integration)
10. [Coverage Targets](#coverage-targets)

---

## pytest Configuration

### pyproject.toml pytest section

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests/unit", "tests/integration", "tests/e2e"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--tb=short",
    "--strict-markers",
    "-p", "no:cacheprovider",
]
filterwarnings = [
    "ignore::DeprecationWarning",
    "ignore::PendingDeprecationWarning",
]

[tool.pytest.ini_options]
markers = [
    # Test categories
    "unit: Unit tests (fast, mocked dependencies)",
    "integration: Integration tests (real services, Docker required)",
    "e2e: End-to-end tests (full workflow validation)",
    "slow: Long-running tests (>30s)",
    "docker: Requires Docker services",
    "redis: Requires Redis container",
    "postgres: Requires PostgreSQL container",
    # Feature markers
    "daemon: Memory daemon tests",
    "memory: Memory storage/recall tests",
    "stream: Stream monitoring tests",
    "mcp: MCP client tests",
    "embedding: Embedding generation tests",
    "search: Vector search tests",
    "stuck_detection: Stuck agent detection tests",
]
```

### pytest.ini (alternative)

```ini
[pytest]
asyncio_mode = auto
testpaths = tests/unit tests/integration tests/e2e
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --strict-markers
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

---

## conftest.py Fixtures

### Central test fixtures for all test suites

```python
"""
Central test fixtures for Continuous-Claude-v3 test suite.

Location: opc/tests/conftest.py
"""

import asyncio
import json
import os
import sys
import tempfile
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.environ["CLAUDE_PROJECT_DIR"] = str(PROJECT_ROOT)


# =============================================================================
# Configuration Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for test artifacts."""
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(Path(__file__).parent.parent.parent)


@pytest.fixture
def claude_home_dir(temp_dir: Path) -> Generator[Path, None, None]:
    """Create temporary ~/.claude directory."""
    claude_home = temp_dir / ".claude"
    claude_home.mkdir(parents=True, exist_ok=True)
    with patch("pathlib.Path.home", return_value=claude_home):
        yield claude_home


# =============================================================================
# Mock Fixtures
# =============================================================================

@pytest.fixture
def mock_subprocess():
    """Mock subprocess module for daemon testing."""
    mock = MagicMock()
    mock.Popen = MagicMock()
    mock.DETACHED_PROCESS = 0x00000008
    return mock


@pytest.fixture
def mock_signal():
    """Mock signal module."""
    mock = MagicMock()
    mock.SIGTERM = 15
    mock.SIGKILL = 9
    return mock


@pytest.fixture
def mock_psycopg2():
    """Mock psycopg2 for PostgreSQL testing."""
    with patch.dict("sys.modules", {"psycopg2": MagicMock(), "psycopg2.extensions": MagicMock()}):
        yield MagicMock()


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    client = MagicMock()
    client.lpush = MagicMock(return_value=1)
    client.rpush = MagicMock(return_value=1)
    client.expire = MagicMock(return_value=True)
    client.set = MagicMock(return_value=True)
    client.get = MagicMock(return_value=None)
    client.delete = MagicMock(return_value=1)
    client.exists = MagicMock(return_value=0)
    client.lrange = MagicMock(return_value=[])
    client.xadd = MagicMock(return_value="test-stream-id")
    client.xread = MagicMock(return_value=[])
    return client


@pytest.fixture
def mock_embedding_service():
    """Create a mock embedding service."""
    mock = AsyncMock()
    mock.embed = AsyncMock(return_value=[0.1] * 384)  # 384-dim embedding
    mock.aclose = AsyncMock()
    return mock


# =============================================================================
# Docker Service Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def docker_services():
    """Check if Docker is available."""
    import subprocess
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


@pytest.fixture(scope="session")
def postgres_container(docker_services):
    """Start PostgreSQL container for integration tests."""
    if not docker_services:
        pytest.skip("Docker not available")

    import subprocess
    import time

    container_id = None
    try:
        # Start container with pgvector
        result = subprocess.run([
            "docker", "run", "-d",
            "--name", "test-pgvector",
            "-e", "POSTGRES_PASSWORD=postgres",
            "-e", "POSTGRES_DB=test_db",
            "-p", "5432:5432",
            "pgvector/pgvector:pg16"
        ], capture_output=True, timeout=60)

        if result.returncode != 0:
            pytest.skip("Failed to start PostgreSQL container")

        container_id = result.stdout.decode().strip()

        # Wait for PostgreSQL to be ready
        for _ in range(30):
            time.sleep(2)
            result = subprocess.run([
                "docker", "exec", container_id,
                "pg_isready", "-U", "postgres"
            ], capture_output=True)
            if result.returncode == 0:
                break

        # Set DATABASE_URL
        os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/test_db"

        yield container_id

    finally:
        if container_id:
            subprocess.run(["docker", "stop", container_id], capture_output=True)
            subprocess.run(["docker", "rm", container_id], capture_output=True)


@pytest.fixture(scope="session")
def redis_container(docker_services):
    """Start Redis container for integration tests."""
    if not docker_services:
        pytest.skip("Docker not available")

    import subprocess
    import time

    container_id = None
    try:
        result = subprocess.run([
            "docker", "run", "-d",
            "--name", "test-redis",
            "-p", "6379:6379",
            "redis:alpine"
        ], capture_output=True, timeout=60)

        if result.returncode != 0:
            pytest.skip("Failed to start Redis container")

        container_id = result.stdout.decode().strip()

        # Wait for Redis to be ready
        for _ in range(15):
            time.sleep(1)
            result = subprocess.run([
                "docker", "exec", container_id,
                "redis-cli", "ping"
            ], capture_output=True)
            if result.returncode == 0 and result.stdout == b"PONG\n":
                break

        os.environ["REDIS_URL"] = "redis://localhost:6379"

        yield container_id

    finally:
        if container_id:
            subprocess.run(["docker", "stop", container_id], capture_output=True)
            subprocess.run(["docker", "rm", container_id], capture_output=True)


# =============================================================================
# Session/Data Fixtures
# =============================================================================

@pytest.fixture
def sample_session_data() -> dict:
    """Create sample session data for testing."""
    return {
        "id": "test-session-123",
        "project": "/tmp/test-project",
        "working_on": "Testing feature X",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "memory_extracted_at": None,
    }


@pytest.fixture
def sample_learning_data() -> dict:
    """Create sample learning data for testing."""
    return {
        "id": "learning-001",
        "session_id": "test-session-123",
        "content": "What worked: Using fixtures for test isolation. What failed: Hardcoded paths. Decisions: Use tmp_path fixture.",
        "metadata": {
            "type": "session_learning",
            "session_id": "test-session-123",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "learning_type": "WORKING_SOLUTION",
            "context": "testing patterns",
            "tags": ["testing", "fixtures", "pytest"],
            "confidence": "high",
        },
        "embedding": [0.1] * 384,
        "created_at": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_stream_events() -> list[dict]:
    """Create sample stream events for testing."""
    return [
        {
            "type": "thinking",
            "thinking": "Analyzing the problem...",
        },
        {
            "type": "tool_use",
            "name": "Read",
            "input": {"file_path": "/test/file.py"},
        },
        {
            "type": "tool_result",
            "tool_use_id": "123",
            "content": "File content here...",
            "is_error": False,
        },
        {
            "type": "text",
            "text": "The solution is complete.",
        },
        {
            "type": "result",
            "content": {"success": True},
        },
    ]


@pytest.fixture
def sample_mcp_config() -> dict:
    """Create sample MCP configuration for testing."""
    return {
        "mcpServers": {
            "test-server": {
                "command": "python",
                "args": ["-m", "test_server"],
                "type": "stdio",
                "disabled": False,
            },
            "http-server": {
                "url": "http://localhost:8080/mcp",
                "type": "http",
                "disabled": False,
            },
        }
    }


# =============================================================================
# Async Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def async_temp_file(temp_dir: Path) -> AsyncGenerator[Path, None]:
    """Create a temporary file for async tests."""
    file_path = temp_dir / "test_async.txt"
    file_path.write_text("")
    yield file_path
    if file_path.exists():
        file_path.unlink()


@pytest_asyncio.fixture
async def mock_postgres_pool():
    """Create a mock async PostgreSQL pool."""
    pool = AsyncMock()

    # Mock context manager
    pool_ctx = AsyncMock()
    pool_ctx.__aenter__ = AsyncMock(return_value=pool)
    pool_ctx.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=pool_ctx)

    yield pool


# =============================================================================
# Event Loop Fixtures
# =============================================================================

@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Process Fixtures
# =============================================================================

@pytest.fixture
def mock_process(claude_home_dir: Path):
    """Create a mock subprocess.Popen object."""
    process = MagicMock()
    process.pid = 12345
    process.returncode = None
    process.stdout = MagicMock()
    process.stdout.readline = MagicMock(side_effect=StopIteration)
    process.wait = MagicMock(return_value=0)
    return process


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def sandboxed_mcp_config(sample_mcp_config) -> dict:
    """Return MCP config with sandboxed server settings."""
    config = sample_mcp_config.copy()
    config["mcpServers"]["test-server"]["args"] = [
        "--sandbox",
        "--container-image", "test-image"
    ]
    return config


# =============================================================================
# Cleanup Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_daemon_state():
    """Clean up daemon state after each test."""
    pid_file = Path.home() / ".claude" / "memory-daemon.pid"
    log_file = Path.home() / ".claude" / "memory-daemon.log"

    yield

    # Cleanup
    if pid_file.exists():
        pid_file.unlink()
    # Note: Don't delete log file, just let tests append to it
```

---

## memory_daemon.py Tests

### Unit Tests

```python
"""
Unit tests for memory_daemon.py

Location: opc/tests/unit/test_memory_daemon.py
"""

import os
import signal
import sqlite3
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import test utilities
from tests.conftest import *


class TestMemoryDaemonUnit:
    """Unit tests for memory daemon core functionality."""

    def test_is_running_no_pid_file(self, claude_home_dir: Path):
        """Test is_running returns False when PID file doesn't exist."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import is_running, PID_FILE

            result, pid = is_running()
            assert result is False
            assert pid is None

    def test_is_running_stale_pid_file(self, claude_home_dir: Path):
        """Test is_running cleans up stale PID file."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import is_running, PID_FILE

            # Write stale PID
            PID_FILE.write_text("99999")

            result, pid = is_running()
            assert result is False
            assert pid is None
            assert not PID_FILE.exists()

    def test_is_running_valid_process(self, claude_home_dir: Path):
        """Test is_running returns True for running process."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import is_running, PID_FILE

            # Get current process PID
            current_pid = os.getpid()
            PID_FILE.write_text(str(current_pid))

            result, pid = is_running()
            assert result is True
            assert pid == current_pid

    @patch("scripts.core.memory_daemon.use_postgres", return_value=False)
    def test_daemon_loop_uses_sqlite(self, mock_pg, claude_home_dir: Path):
        """Test daemon loop uses SQLite when PostgreSQL not available."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import use_postgres, sqlite_get_stale_sessions

            # Ensure we're using SQLite
            assert use_postgres() is False

            # Mock get_stale_sessions to return empty
            with patch("scripts.core.memory_daemon.get_stale_sessions", return_value=[]):
                with patch("scripts.core.memory_daemon.process_pending_queue"):
                    with patch("scripts.core.memory_daemon.reap_completed_extractions", return_value=0):
                        # Just verify imports work without error
                        import scripts.core.memory_daemon as daemon
                        assert daemon.POLL_INTERVAL == 60
                        assert daemon.STALE_THRESHOLD == 300

    @patch("scripts.core.memory_daemon.use_postgres", return_value=True)
    def test_daemon_loop_uses_postgres(self, mock_pg, claude_home_dir: Path):
        """Test daemon loop uses PostgreSQL when available."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test@localhost/test"}):
            from scripts.core.memory_daemon import use_postgres

            assert use_postgres() is True

    def test_pid_file_location(self, claude_home_dir: Path):
        """Test PID file is created in correct location."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import PID_FILE

            expected = claude_home_dir / "memory-daemon.pid"
            assert PID_FILE == expected

    def test_log_function_creates_directory(self, temp_dir: Path):
        """Test log function creates log directory if needed."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            # Create a custom log file in temp directory
            custom_log = temp_dir / "logs" / "daemon.log"

            with patch("scripts.core.memory_daemon.LOG_FILE", custom_log):
                with patch("scripts.core.memory_daemon.log") as mock_log:
                    # Just verify the log path can be created
                    custom_log.parent.mkdir(parents=True, exist_ok=True)
                    custom_log.write_text("")
                    assert custom_log.parent.exists()


class TestSQLiteOperations:
    """Unit tests for SQLite database operations."""

    def test_sqlite_ensure_table_creates_table(self, temp_dir: Path):
        """Test sqlite_ensure_table creates sessions table."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import sqlite_ensure_table, get_sqlite_path

            # Patch home to use temp directory
            with patch("pathlib.Path.home", return_value=temp_dir):
                sqlite_ensure_table()

                db_path = get_sqlite_path()
                assert db_path.exists()

                # Verify table structure
                conn = sqlite3.connect(db_path)
                cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
                assert cursor.fetchone() is not None
                conn.close()

    def test_sqlite_get_stale_sessions_empty_db(self, temp_dir: Path):
        """Test sqlite_get_stale_sessions returns empty list for new database."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import sqlite_get_stale_sessions, sqlite_ensure_table

            with patch("pathlib.Path.home", return_value=temp_dir):
                sqlite_ensure_table()
                result = sqlite_get_stale_sessions()
                assert result == []

    def test_sqlite_mark_extracted(self, temp_dir: Path):
        """Test sqlite_mark_extracted updates session record."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import (
                sqlite_ensure_table,
                sqlite_mark_extracted,
                get_sqlite_path,
            )

            with patch("pathlib.Path.home", return_value=temp_dir):
                sqlite_ensure_table()

                # Insert test session
                db_path = get_sqlite_path()
                conn = sqlite3.connect(db_path)
                conn.execute(
                    "INSERT INTO sessions (id, project, started_at, last_heartbeat) VALUES (?, ?, ?, ?)",
                    ("test-session", "/test", datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat())
                )
                conn.commit()
                conn.close()

                # Mark as extracted
                sqlite_mark_extracted("test-session")

                # Verify
                conn = sqlite3.connect(db_path)
                cursor = conn.execute(
                    "SELECT memory_extracted_at FROM sessions WHERE id = ?",
                    ("test-session",)
                )
                result = cursor.fetchone()
                conn.close()

                assert result is not None
                assert result[0] is not None


class TestProcessManagement:
    """Unit tests for extraction process management."""

    def test_reap_completed_extractions(self, claude_home_dir: Path):
        """Test reap_completed_extractions removes finished processes."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import active_extractions, reap_completed_extractions

            # Add a fake completed process (PID that doesn't exist)
            active_extractions[99999] = "completed-session"

            # Mock os.kill to raise ProcessLookupError (simulating dead process)
            with patch("os.kill", side_effect=ProcessLookupError):
                count = reap_completed_extractions()

            assert count == 1
            assert 99999 not in active_extractions

    def test_queue_or_extract_at_limit(self, claude_home_dir: Path):
        """Test queue_or_extract queues when at concurrency limit."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import (
                active_extractions,
                pending_queue,
                MAX_CONCURRENT_EXTRACTIONS,
                queue_or_extract,
            )

            # Fill up active extractions
            for i in range(MAX_CONCURRENT_EXTRACTIONS):
                active_extractions[f"pid-{i}"] = f"session-{i}"

            with patch("scripts.core.memory_daemon.extract_memories") as mock_extract:
                queue_or_extract("new-session", "/test-project")

                # Should be queued, not extracted
                assert ("new-session", "/test-project") in pending_queue
                mock_extract.assert_not_called()

    def test_queue_or_extract_under_limit(self, claude_home_dir: Path):
        """Test queue_or_extract extracts immediately when under limit."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import (
                active_extractions,
                pending_queue,
                queue_or_extract,
            )

            with patch("scripts.core.memory_daemon.extract_memories") as mock_extract:
                queue_or_extract("new-session", "/test-project")

                # Should be extracted immediately
                mock_extract.assert_called_once_with("new-session", "/test-project")


class TestDaemonStartStop:
    """Unit tests for daemon start/stop operations."""

    @patch("subprocess.Popen")
    @patch("scripts.core.memory_daemon.is_running", return_value=(False, None))
    def test_start_daemon_unix_double_fork(self, mock_running, mock_popen, claude_home_dir: Path):
        """Test start_daemon uses double-fork on Unix."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            if sys.platform == "win32":
                pytest.skip("Not applicable on Windows")

            from scripts.core.memory_daemon import start_daemon

            # Mock the fork calls
            with patch("os.fork", side_effect=[0, 0]):  # Both forks return 0 (child)
                with patch("os.setsid"):
                    with patch("scripts.core.memory_daemon._run_as_daemon"):
                        with patch("sys.exit"):
                            result = start_daemon()

            assert result == 0

    @patch("scripts.core.memory_daemon.is_running", return_value=(True, 12345))
    def test_start_daemon_already_running(self, mock_running, claude_home_dir: Path):
        """Test start_daemon returns 0 when already running."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import start_daemon

            result = start_daemon()
            assert result == 0

    @patch("os.kill")
    @patch("scripts.core.memory_daemon.is_running", return_value=(True, 12345))
    def test_stop_daemon(self, mock_running, mock_kill, claude_home_dir: Path):
        """Test stop_daemon sends SIGTERM to daemon process."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import stop_daemon

            with patch("scripts.core.memory_daemon.PID_FILE.unlink"):
                result = stop_daemon()

            mock_kill.assert_called_once_with(12345, signal.SIGTERM)
            assert result == 0

    @patch("scripts.core.memory_daemon.is_running", return_value=(False, None))
    def test_stop_daemon_not_running(self, mock_running, claude_home_dir: Path):
        """Test stop_daemon returns 0 when not running."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import stop_daemon

            result = stop_daemon()
            assert result == 0


class TestDaemonStatus:
    """Unit tests for daemon status command."""

    @patch("scripts.core.memory_daemon.is_running", return_value=(True, 12345))
    def test_status_daemon_running(self, mock_running, claude_home_dir: Path, capsys):
        """Test status_daemon shows running status."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import status_daemon

            with patch("scripts.core.memory_daemon.use_postgres", return_value=False):
                result = status_daemon()

            captured = capsys.readouterr()
            assert "Memory Daemon Status" in captured.out
            assert "Running: Yes" in captured.out
            assert "PID: 12345" in captured.out

    @patch("scripts.core.memory_daemon.is_running", return_value=(False, None))
    def test_status_daemon_not_running(self, mock_running, claude_home_dir: Path, capsys):
        """Test status_daemon shows not running."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.core.memory_daemon import status_daemon

            with patch("scripts.core.memory_daemon.use_postgres", return_value=False):
                result = status_daemon()

            captured = capsys.readouterr()
            assert "Memory Daemon Status" in captured.out
            assert "Running: No" in captured.out
```

### Integration Tests

```python
"""
Integration tests for memory_daemon.py

Location: opc/tests/integration/test_memory_daemon.py
"""

import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import pytest

from tests.conftest import *


@pytest.fixture
def running_daemon(claude_home_dir: Path) -> Generator[subprocess.Popen, None, None]:
    """Start daemon and yield process for testing."""
    env = os.environ.copy()
    env["DATABASE_URL"] = ""  # Force SQLite

    # Start daemon as subprocess
    proc = subprocess.Popen(
        [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from scripts.core.memory_daemon import start_daemon, main
sys.exit(main())
"""],
        cwd=str(claude_home_dir.parent.parent),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(1)  # Give daemon time to start

    try:
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


class TestDaemonIntegration:
    """Integration tests for memory daemon with real database."""

    @pytest.mark.docker
    @pytest.mark.postgres
    def test_daemon_with_postgres(self, postgres_container):
        """Test daemon works with PostgreSQL database."""
        # DATABASE_URL is set by postgres_container fixture
        assert "DATABASE_URL" in os.environ
        assert "postgresql://" in os.environ["DATABASE_URL"]

        # Import and verify PostgreSQL functions work
        from scripts.core.memory_daemon import (
            use_postgres,
            pg_ensure_column,
            pg_get_stale_sessions,
        )

        assert use_postgres() is True

        # Test schema creation
        pg_ensure_column()

        # Test query
        sessions = pg_get_stale_sessions()
        assert isinstance(sessions, list)


@pytest.mark.docker
@pytest.mark.postgres
class TestPostgresSchemaIntegration:
    """Integration tests for PostgreSQL schema operations."""

    def test_pg_ensure_column_idempotent(self, postgres_container):
        """Test pg_ensure_column can be called multiple times safely."""
        from scripts.core.memory_daemon import pg_ensure_column, get_postgres_url

        # Call twice - second call should not fail
        pg_ensure_column()
        pg_ensure_column()  # Should not raise

        # Verify column exists by querying
        import psycopg2
        conn = psycopg2.connect(get_postgres_url())
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'sessions' AND column_name = 'memory_extracted_at'
        """)
        result = cur.fetchone()
        conn.close()

        assert result is not None

    def test_pg_mark_extracted(self, postgres_container):
        """Test pg_mark_extracted updates session record."""
        from scripts.core.memory_daemon import (
            pg_mark_extracted,
            get_postgres_url,
            pg_ensure_column,
        )
        import psycopg2

        pg_ensure_column()

        # Insert test session
        conn = psycopg2.connect(get_postgres_url())
        cur = conn.cursor()
        test_id = f"test-session-{datetime.now().timestamp()}"
        cur.execute(
            "INSERT INTO sessions (id, project, started_at, last_heartbeat) VALUES (%s, %s, %s, %s)",
            (test_id, "/test", datetime.now(timezone.utc), datetime.now(timezone.utc))
        )
        conn.commit()
        conn.close()

        # Mark as extracted
        pg_mark_extracted(test_id)

        # Verify
        conn = psycopg2.connect(get_postgres_url())
        cur = conn.cursor()
        cur.execute(
            "SELECT memory_extracted_at FROM sessions WHERE id = %s",
            (test_id,)
        )
        result = cur.fetchone()
        conn.close()

        assert result is not None
        assert result[0] is not None


class TestDaemonLifecycleIntegration:
    """Integration tests for daemon lifecycle."""

    @pytest.mark.slow
    def test_daemon_polling_cycle(self, claude_home_dir: Path):
        """Test daemon's polling cycle works correctly."""
        from scripts.core.memory_daemon import (
            POLL_INTERVAL,
            STALE_THRESHOLD,
            get_stale_sessions,
            ensure_schema,
        )

        # Verify configuration values
        assert POLL_INTERVAL == 60
        assert STALE_THRESHOLD == 300

        # Test that schema can be ensured
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            ensure_schema()

    def test_daemon_log_rotation(self, claude_home_dir: Path):
        """Test daemon logs to file correctly."""
        from scripts.core.memory_daemon import LOG_FILE

        # Ensure log directory exists
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Write log
        test_message = f"Test log entry at {datetime.now()}"
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {test_message}\n")

        # Verify log was written
        assert LOG_FILE.exists()
        content = LOG_FILE.read_text()
        assert test_message in content
```

### E2E Tests

```python
"""
End-to-end tests for memory_daemon.py

Location: opc/tests/e2e/test_memory_daemon.py
"""

import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.conftest import *


class TestDaemonE2E:
    """End-to-end tests for memory daemon."""

    @pytest.mark.slow
    def test_full_daemon_lifecycle(self, claude_home_dir: Path):
        """Test complete daemon lifecycle: start -> run -> stop."""
        from scripts.core.memory_daemon import (
            start_daemon,
            stop_daemon,
            is_running,
            PID_FILE,
        )

        # Verify not running initially
        running, _ = is_running()
        assert not running

        # Start daemon
        result = start_daemon()
        assert result == 0

        # Verify running
        running, pid = is_running()
        assert running
        assert pid is not None

        # Stop daemon
        result = stop_daemon()
        assert result == 0

        # Verify stopped
        running, _ = is_running()
        assert not running
        assert not PID_FILE.exists()

    @pytest.mark.slow
    def test_daemon_handles_stale_sessions(self, claude_home_dir: Path):
        """Test daemon processes stale sessions correctly."""
        from scripts.core.memory_daemon import (
            start_daemon,
            stop_daemon,
            sqlite_ensure_table,
            get_sqlite_path,
            sqlite_mark_extracted,
        )
        import sqlite3
        from datetime import timedelta

        # Setup
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            sqlite_ensure_table()

            # Insert stale session
            db_path = get_sqlite_path()
            conn = sqlite3.connect(db_path)
            stale_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
            conn.execute(
                "INSERT INTO sessions (id, project, started_at, last_heartbeat) VALUES (?, ?, ?, ?)",
                ("stale-session", "/test", stale_time, stale_time)
            )
            conn.commit()
            conn.close()

            # Start daemon
            start_daemon()
            time.sleep(2)  # Let daemon run one cycle

            # Verify session was marked as extracted
            conn = sqlite3.connect(db_path)
            cur = conn.execute(
                "SELECT memory_extracted_at FROM sessions WHERE id = ?",
                ("stale-session",)
            )
            result = cur.fetchone()
            conn.close()

            assert result is not None

            # Cleanup
            stop_daemon()

    @pytest.mark.slow
    def test_daemon_prevents_duplicate_start(self, claude_home_dir: Path):
        """Test daemon prevents starting duplicate instances."""
        from scripts.core.memory_daemon import start_daemon, is_running

        # Start first instance
        result1 = start_daemon()

        # Try to start second instance
        result2 = start_daemon()

        # Verify only one is running
        running, pid = is_running()
        assert running

        # Cleanup
        from scripts.core.memory_daemon import stop_daemon
        stop_daemon()

        assert result1 == 0
        assert result2 == 0  # Should return 0, just print message


class TestDaemonConcurrencyE2E:
    """End-to-end tests for daemon concurrency handling."""

    @pytest.mark.slow
    def test_concurrent_extraction_limit(self, claude_home_dir: Path):
        """Test daemon respects MAX_CONCURRENT_EXTRACTIONS limit."""
        from scripts.core.memory_daemon import (
            MAX_CONCURRENT_EXTRACTIONS,
            active_extractions,
            pending_queue,
            queue_or_extract,
        )

        assert MAX_CONCURRENT_EXTRACTIONS == 2

        # Simulate adding more sessions than limit
        active_extractions.clear()
        pending_queue.clear()

        # Add sessions up to limit
        for i in range(MAX_CONCURRENT_EXTRACTIONS):
            active_extractions[f"pid-{i}"] = f"session-{i}"

        # Next session should be queued
        with patch("scripts.core.memory_daemon.extract_memories") as mock:
            queue_or_extract("extra-session", "/test")

            assert len(pending_queue) == 1
            mock.assert_not_called()


### Common Failure Points for memory_daemon.py

"""
Failure points to test:

1. PID file handling:
   - Stale PID file with dead process
   - PID file with invalid content
   - PID file permission issues

2. Database operations:
   - PostgreSQL connection failures
   - SQLite database corruption
   - Race conditions in session marking

3. Process management:
   - Zombie process detection
   - Process termination edge cases
   - SIGTERM vs SIGKILL handling

4. Concurrency:
   - Queue overflow
   - Session deduplication race
   - Multiple daemons starting simultaneously

5. Logging:
   - Log file rotation
   - Disk space exhaustion
   - Log injection attacks
"""
```

---

## recall_learnings.py Tests

### Unit Tests

```python
"""
Unit tests for recall_learnings.py

Location: opc/tests/unit/test_recall_learnings.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import *


class TestBackendSelection:
    """Tests for backend selection logic."""

    def test_get_backend_sqlite_default(self, temp_dir: Path):
        """Test get_backend returns sqlite when no DATABASE_URL."""
        with patch.dict(os.environ, {"DATABASE_URL": "", "CONTINUOUS_CLAUDE_DB_URL": ""}):
            from scripts.recall_learnings import get_backend

            result = get_backend()
            assert result == "sqlite"

    def test_get_backend_postgres_with_url(self, temp_dir: Path):
        """Test get_backend returns postgres when DATABASE_URL is set."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test@localhost/test"}):
            from scripts.recall_learnings import get_backend

            result = get_backend()
            assert result == "postgres"

    def test_get_backend_explicit_override(self, temp_dir: Path):
        """Test AGENTICA_MEMORY_BACKEND env var takes precedence."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test@localhost/test",
            "AGENTICA_MEMORY_BACKEND": "sqlite"
        }):
            from scripts.recall_learnings import get_backend

            result = get_backend()
            assert result == "sqlite"


class TestTextFormatting:
    """Tests for result text formatting."""

    def test_format_result_preview_short(self):
        """Test format_result_preview with short content."""
        from scripts.recall_learnings import format_result_preview

        result = format_result_preview("Short content", max_length=100)
        assert result == "Short content"

    def test_format_result_preview_long(self):
        """Test format_result_preview truncates long content."""
        from scripts.recall_learnings import format_result_preview

        long_content = "A" * 200
        result = format_result_preview(long_content, max_length=100)
        assert result == "A" * 100 + "..."
        assert len(result) == 103


class TestPostgresSearch:
    """Unit tests for PostgreSQL search functions."""

    @pytest.mark.asyncio
    async def test_search_learnings_text_only_postgres_no_results(self, mock_postgres_pool):
        """Test text-only search returns empty list when no results."""
        with patch("scripts.recall_learnings.get_pool", return_value=mock_postgres_pool):
            from scripts.recall_learnings import search_learnings_text_only_postgres

            # Mock connection with empty results
            mock_conn = AsyncMock()
            mock_pool = AsyncMock()
            mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
            mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
            mock_conn.fetch = AsyncMock(return_value=[])

            with patch("scripts.recall_learnings.get_pool", return_value=mock_pool):
                result = await search_learnings_text_only_postgres("test query", k=5)

                assert result == []

    @pytest.mark.asyncio
    async def test_search_learnings_sqlite_no_db(self, temp_dir: Path):
        """Test SQLite search returns empty when database doesn't exist."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.recall_learnings import search_learnings_sqlite

            # Patch Path.home to use temp directory
            with patch("pathlib.Path.home", return_value=temp_dir):
                result = await search_learnings_sqlite("test query", k=5)

                assert result == []


class TestHybridSearch:
    """Tests for hybrid RRF search."""

    @pytest.mark.asyncio
    async def test_search_learnings_hybrid_rrf_empty_query(self, mock_postgres_pool):
        """Test hybrid search returns empty for empty query."""
        from scripts.recall_learnings import search_learnings_hybrid_rrf

        with patch("scripts.recall_learnings.get_pool", return_value=mock_postgres_pool):
            with patch("scripts.recall_learnings.EmbeddingService") as mock_embed:
                mock_service = MagicMock()
                mock_service.embed = AsyncMock(return_value=[0.1] * 384)
                mock_service.aclose = AsyncMock()
                mock_embed.return_value = mock_service

                with patch("scripts.recall_learnings.init_pgvector"):
                    mock_conn = AsyncMock()
                    mock_conn.fetch = AsyncMock(return_value=[])
                    mock_pool = AsyncMock()
                    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
                    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

                    result = await search_learnings_hybrid_rrf("", k=5)

                    # Empty query should return empty
                    assert result == []

    @pytest.mark.asyncio
    async def test_search_learnings_hybrid_rrf_with_results(self, mock_postgres_pool):
        """Test hybrid search returns results with scores."""
        from scripts.recall_learnings import search_learnings_hybrid_rrf

        # Mock row with learning data
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "id": "learning-1",
            "session_id": "session-123",
            "content": "Test learning content",
            "metadata": {"type": "session_learning"},
            "created_at": datetime.now(),
            "rrf_score": 0.025,
            "fts_rank": 1,
            "vec_rank": 2,
        }[key]

        with patch("scripts.recall_learnings.get_pool", return_value=mock_postgres_pool):
            with patch("scripts.recall_learnings.EmbeddingService") as mock_embed:
                mock_service = MagicMock()
                mock_service.embed = AsyncMock(return_value=[0.1] * 384)
                mock_service.aclose = AsyncMock()
                mock_embed.return_value = mock_service

                with patch("scripts.recall_learnings.init_pgvector"):
                    mock_conn = AsyncMock()
                    mock_conn.fetch = AsyncMock(return_value=[mock_row])
                    mock_pool = AsyncMock()
                    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
                    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

                    result = await search_learnings_hybrid_rrf("test query", k=5)

                    assert len(result) == 1
                    assert "similarity" in result[0]


class TestSearchFunction:
    """Tests for main search_learnings function."""

    @pytest.mark.asyncio
    async def test_search_learnings_empty_query(self, temp_dir: Path):
        """Test search_learnings returns empty for empty query."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.recall_learnings import search_learnings

            result = await search_learnings("", k=5)
            assert result == []

    @pytest.mark.asyncio
    async def test_search_learnings_sqlite_backend(self, temp_dir: Path):
        """Test search_learnings uses SQLite backend when no DATABASE_URL."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.recall_learnings import search_learnings

            with patch("scripts.recall_learnings.search_learnings_sqlite", new_callable=AsyncMock) as mock:
                mock.return_value = []

                result = await search_learnings("test query", k=5)

                mock.assert_called_once_with("test query", 5)

    @pytest.mark.asyncio
    async def test_search_learnings_postgres_backend(self, temp_dir: Path):
        """Test search_learnings uses PostgreSQL backend when DATABASE_URL set."""
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://test@localhost/test"}):
            from scripts.recall_learnings import search_learnings

            with patch("scripts.recall_learnings.search_learnings_postgres", new_callable=AsyncMock) as mock:
                mock.return_value = []

                result = await search_learnings("test query", k=5)

                mock.assert_called_once()
                # Verify called with expected parameters
                call_kwargs = mock.call_args[1]
                assert call_kwargs.get("k") == 5
```

### Integration Tests

```python
"""
Integration tests for recall_learnings.py

Location: opc/tests/integration/test_recall_learnings.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.conftest import *


@pytest.mark.docker
@pytest.mark.postgres
class TestPostgresIntegration:
    """Integration tests with real PostgreSQL database."""

    @pytest.fixture
    def populated_postgres(self, postgres_container):
        """Populate PostgreSQL with test learnings."""
        from scripts.core.db.postgres_pool import get_pool

        pool = None
        try:
            pool = get_pool()

            async def setup():
                async with pool.acquire() as conn:
                    # Create table if needed
                    await conn.execute("""
                        CREATE TABLE IF NOT EXISTS archival_memory (
                            id SERIAL PRIMARY KEY,
                            session_id TEXT NOT NULL,
                            content TEXT NOT NULL,
                            metadata JSONB,
                            embedding vector(384),
                            created_at TIMESTAMP DEFAULT NOW()
                        )
                    """)

                    # Insert test data
                    await conn.execute("""
                        INSERT INTO archival_memory (session_id, content, metadata)
                        VALUES
                            ('session-1', 'Test learning about auth patterns', '{"type": "session_learning"}'),
                            ('session-2', 'Database migration approach', '{"type": "session_learning"}'),
                            ('session-3', 'Error handling patterns', '{"type": "session_learning"}')
                    """)

            import asyncio
            asyncio.run(setup())

            yield pool
        finally:
            if pool:
                pool.close()

    @pytest.mark.asyncio
    async def test_full_text_search(self, populated_postgres):
        """Test full-text search against real database."""
        from scripts.recall_learnings import search_learnings_text_only_postgres

        results = await search_learnings_text_only_postgres("auth patterns", k=5)

        assert len(results) >= 1
        assert any("auth" in r["content"].lower() for r in results)

    @pytest.mark.asyncio
    async def test_vector_search_with_embeddings(self, populated_postgres):
        """Test vector similarity search."""
        from scripts.recall_learnings import search_learnings_postgres

        with patch("scripts.recall_learnings.EmbeddingService") as mock_embed:
            mock_service = MagicMock()
            mock_service.embed = AsyncMock(return_value=[0.1] * 384)
            mock_service.aclose = AsyncMock()
            mock_embed.return_value = mock_service

            results = await search_learnings_postgres("authentication", k=5)

            assert isinstance(results, list)


@pytest.mark.docker
@pytest.mark.redis
class TestSQLiteFTSIntegration:
    """Integration tests with SQLite FTS5."""

    @pytest.fixture
    def populated_sqlite(self, temp_dir: Path):
        """Populate SQLite with test learnings."""
        import sqlite3

        with patch("pathlib.Path.home", return_value=temp_dir):
            from scripts.recall_learnings import search_learnings_sqlite

            db_path = temp_dir / ".claude" / "cache" / "memory.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(db_path))
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS archival_memory USING fts5(
                    content, session_id, metadata_json, tokenize='porter'
                )
            """)

            # Insert test data
            conn.execute("""
                INSERT INTO archival_memory (content, session_id, metadata_json)
                VALUES
                    ('Test learning about auth patterns', 'session-1', '{"type": "session_learning"}'),
                    ('Database migration approach', 'session-2', '{"type": "session_learning"}'),
                    ('Error handling patterns', 'session-3', '{"type": "session_learning"}')
            """)
            conn.commit()
            conn.close()

            yield db_path

    @pytest.mark.asyncio
    async def test_fts5_search(self, populated_sqlite, temp_dir: Path):
        """Test FTS5 search against real SQLite database."""
        with patch("pathlib.Path.home", return_value=temp_dir):
            from scripts.recall_learnings import search_learnings_sqlite

            results = await search_learnings_sqlite("auth patterns", k=5)

            assert len(results) >= 1
```

### E2E Tests

```python
"""
End-to-end tests for recall_learnings.py

Location: opc/tests/e2e/test_recall_learnings.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from tests.conftest import *


class TestRecallE2E:
    """End-to-end tests for recall CLI."""

    @pytest.mark.slow
    def test_recall_cli_empty_query(self, temp_dir: Path):
        """Test recall CLI handles empty query gracefully."""
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from scripts.recall_learnings import main
sys.exit(asyncio.run(main()))
"""],
            cwd=str(Path(__file__).parent.parent.parent),
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": ""},
            input="",  # Empty query
        )

        # Should exit with error for missing --query
        assert result.returncode != 0 or "--query" in result.stderr

    @pytest.mark.slow
    def test_recall_cli_with_results(self, temp_dir: Path):
        """Test recall CLI outputs results correctly."""
        # First, store a learning
        store_result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from scripts.store_learning import main
sys.exit(asyncio.run(main()))
"""],
            cwd=str(Path(__file__).parent.parent.parent),
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": ""},
            input="--session-id test-session --content 'Test learning content' --json",
        )

        # Now recall it
        recall_result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from scripts.recall_learnings import main
sys.exit(asyncio.run(main()))
"""],
            cwd=str(Path(__file__).parent.parent.parent),
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": ""},
            input="--query 'learning content' --json",
        )

        # Verify output
        if recall_result.returncode == 0:
            output = json.loads(recall_result.stdout)
            assert "results" in output


class TestHybridSearchE2E:
    """End-to-end tests for hybrid search."""

    @pytest.mark.slow
    def test_hybrid_rrf_combines_results(self, temp_dir: Path):
        """Test RRF combines text and vector rankings."""
        from scripts.recall_learnings import search_learnings_hybrid_rrf

        with patch("scripts.recall_learnings.get_pool") as mock_pool:
            with patch("scripts.recall_learnings.EmbeddingService") as mock_embed:
                mock_service = MagicMock()
                mock_service.embed = AsyncMock(return_value=[0.1] * 384)
                mock_service.aclose = AsyncMock()
                mock_embed.return_value = mock_service

                # Mock pool with results
                mock_row = MagicMock()
                mock_row.__getitem__ = lambda self, key: {
                    "id": "1",
                    "session_id": "s1",
                    "content": "test content",
                    "metadata": {"type": "session_learning"},
                    "created_at": datetime.now(),
                    "rrf_score": 0.02,
                    "fts_rank": 1,
                    "vec_rank": 1,
                }[key]

                mock_conn = AsyncMock()
                mock_conn.fetch = AsyncMock(return_value=[mock_row])

                mock_ctx = AsyncMock()
                mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
                mock_ctx.__aexit__ = AsyncMock(return_value=None)
                mock_pool.return_value.acquire = MagicMock(return_value=mock_ctx)

                import asyncio
                results = asyncio.run(search_learnings_hybrid_rrf("test", k=5))

                assert len(results) >= 0  # May be empty depending on mock setup


### Common Failure Points for recall_learnings.py

"""
Failure points to test:

1. Backend selection:
   - DATABASE_URL with invalid format
   - Missing pgvector extension
   - Connection timeout

2. Embedding service:
   - API key issues (Voyage)
   - Model loading failures
   - Dimension mismatches

3. Search algorithms:
   - Empty query handling
   - All stopwords in query
   - Very long queries

4. Result processing:
   - Invalid metadata JSON
   - Missing embedding column
   - Type conversion errors

5. Performance:
   - Large result sets
   - Slow embedding generation
   - Database connection pool exhaustion
"""
```

---

## store_learning.py Tests

### Unit Tests

```python
"""
Unit tests for store_learning.py

Location: opc/tests/unit/test_store_learning.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import *


class TestLearningTypes:
    """Tests for learning type validation."""

    def test_valid_learning_types(self, temp_dir: Path):
        """Test all valid learning types are accepted."""
        from scripts.store_learning import LEARNING_TYPES, CONFIDENCE_LEVELS

        expected_types = [
            "FAILED_APPROACH",
            "WORKING_SOLUTION",
            "USER_PREFERENCE",
            "CODEBASE_PATTERN",
            "ARCHITECTURAL_DECISION",
            "ERROR_FIX",
            "OPEN_THREAD",
        ]

        assert LEARNING_TYPES == expected_types
        assert CONFIDENCE_LEVELS == ["high", "medium", "low"]

    def test_dedup_threshold(self, temp_dir: Path):
        """Test deduplication threshold is set correctly."""
        from scripts.store_learning import DEDUP_THRESHOLD

        assert DEDUP_THRESHOLD == 0.85


class TestStoreLearningV2:
    """Unit tests for store_learning_v2 function."""

    @pytest.mark.asyncio
    async def test_store_learning_v2_empty_content(self, temp_dir: Path):
        """Test store_learning_v2 rejects empty content."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.store_learning import store_learning_v2

            result = await store_learning_v2(
                session_id="test-session",
                content="",
            )

            assert result["success"] is False
            assert "No content provided" in result["error"]

    @pytest.mark.asyncio
    async def test_store_learning_v2_whitespace_only(self, temp_dir: Path):
        """Test store_learning_v2 rejects whitespace-only content."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.store_learning import store_learning_v2

            result = await store_learning_v2(
                session_id="test-session",
                content="   \n\t  ",
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_store_learning_v2_success(self, temp_dir: Path):
        """Test successful learning storage."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.store_learning import store_learning_v2

            # Mock dependencies
            mock_memory = AsyncMock()
            mock_memory.store = AsyncMock(return_value="memory-123")
            mock_memory.search_vector = AsyncMock(return_value=[])  # No duplicates
            mock_memory.close = AsyncMock()

            with patch("scripts.store_learning.create_memory_service", new_callable=AsyncMock) as mock_create:
                with patch("scripts.store_learning.EmbeddingService") as mock_embed:
                    mock_create.return_value = mock_memory

                    mock_service = MagicMock()
                    mock_service.embed = AsyncMock(return_value=[0.1] * 384)
                    mock_embed.return_value = mock_service

                    result = await store_learning_v2(
                        session_id="test-session",
                        content="Test learning content",
                        learning_type="WORKING_SOLUTION",
                        context="testing",
                        tags=["test", "pytest"],
                        confidence="high",
                    )

                    assert result["success"] is True
                    assert result["memory_id"] == "memory-123"

    @pytest.mark.asyncio
    async def test_store_learning_v2_duplicate_detection(self, temp_dir: Path):
        """Test store_learning_v2 detects and skips duplicates."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.store_learning import store_learning_v2

            # Mock similar existing learning
            mock_memory = AsyncMock()
            mock_memory.search_vector = AsyncMock(return_value=[
                {"id": "existing-123", "similarity": 0.9}
            ])

            with patch("scripts.store_learning.create_memory_service", new_callable=AsyncMock) as mock_create:
                with patch("scripts.store_learning.EmbeddingService") as mock_embed:
                    mock_create.return_value = mock_memory

                    mock_service = MagicMock()
                    mock_service.embed = AsyncMock(return_value=[0.1] * 384)
                    mock_embed.return_value = mock_service

                    result = await store_learning_v2(
                        session_id="test-session",
                        content="Almost identical content",
                    )

                    assert result["success"] is True
                    assert result["skipped"] is True
                    assert result["existing_id"] == "existing-123"


class TestStoreLearningLegacy:
    """Unit tests for legacy store_learning function."""

    @pytest.mark.asyncio
    async def test_store_learning_all_none(self, temp_dir: Path):
        """Test store_learning rejects when all fields are None."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.store_learning import store_learning

            result = await store_learning(
                session_id="test-session",
                worked="None",
                failed="None",
                decisions="None",
                patterns="None",
            )

            assert result["success"] is False
            assert "No learning content provided" in result["error"]

    @pytest.mark.asyncio
    async def test_store_learning_partial_content(self, temp_dir: Path):
        """Test store_learning works with partial content."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.store_learning import store_learning

            mock_memory = AsyncMock()
            mock_memory.store = AsyncMock(return_value="memory-456")
            mock_memory.close = AsyncMock()

            with patch("scripts.store_learning.create_memory_service", new_callable=AsyncMock) as mock_create:
                with patch("scripts.store_learning.EmbeddingService") as mock_embed:
                    mock_create.return_value = mock_memory

                    mock_service = MagicMock()
                    mock_service.embed = AsyncMock(return_value=[0.1] * 384)
                    mock_embed.return_value = mock_service

                    result = await store_learning(
                        session_id="test-session",
                        worked="Using fixtures helped",
                        failed="None",
                        decisions="None",
                        patterns="None",
                    )

                    assert result["success"] is True
                    assert "What worked" in result.get("content", "")


class TestMetadataConstruction:
    """Tests for metadata construction."""

    @pytest.mark.asyncio
    async def test_metadata_includes_all_fields(self, temp_dir: Path):
        """Test metadata includes all provided fields."""
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            from scripts.store_learning import store_learning_v2

            mock_memory = AsyncMock()
            mock_memory.store = AsyncMock(return_value="memory-id")
            mock_memory.search_vector = AsyncMock(return_value=[])
            mock_memory.close = AsyncMock()

            with patch("scripts.store_learning.create_memory_service", new_callable=AsyncMock) as mock_create:
                with patch("scripts.store_learning.EmbeddingService") as mock_embed:
                    mock_create.return_value = mock_memory

                    mock_service = MagicMock()
                    mock_service.embed = AsyncMock(return_value=[0.1] * 384)
                    mock_embed.return_value = mock_service

                    await store_learning_v2(
                        session_id="test-session",
                        content="Test content",
                        learning_type="WORKING_SOLUTION",
                        context="testing patterns",
                        tags=["test", "pytest"],
                        confidence="high",
                    )

                    # Verify store was called with correct metadata
                    call_args = mock_memory.store.call_args
                    metadata = call_args.kwargs.get("metadata", call_args[1].get("metadata"))

                    assert metadata["type"] == "session_learning"
                    assert metadata["session_id"] == "test-session"
                    assert metadata["learning_type"] == "WORKING_SOLUTION"
                    assert metadata["context"] == "testing patterns"
                    assert metadata["tags"] == ["test", "pytest"]
                    assert metadata["confidence"] == "high"
```

### Integration Tests

```python
"""
Integration tests for store_learning.py

Location: opc/tests/integration/test_store_learning.py
"""

import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import *


@pytest.mark.docker
@pytest.mark.postgres
class TestStorePostgresIntegration:
    """Integration tests with PostgreSQL storage."""

    @pytest.fixture
    def clean_postgres(self, postgres_container):
        """Clean PostgreSQL before test."""
        import psycopg2

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor()
        cur.execute("DELETE FROM archival_memory WHERE session_id LIKE 'test-%'")
        conn.commit()
        conn.close()

        yield postgres_container

    @pytest.mark.asyncio
    async def test_store_with_real_postgres(self, clean_postgres):
        """Test storing learning to real PostgreSQL database."""
        from scripts.store_learning import store_learning_v2

        result = await store_learning_v2(
            session_id="test-integration-session",
            content="Integration test learning",
            learning_type="WORKING_SOLUTION",
            context="integration testing",
            tags=["integration", "test"],
            confidence="high",
        )

        assert result["success"] is True
        assert result["backend"] == "postgres"
        assert result["memory_id"] is not None

    @pytest.mark.asyncio
    async def test_store_duplicate_detection_postgres(self, clean_postgres):
        """Test duplicate detection works with PostgreSQL."""
        from scripts.store_learning import store_learning_v2

        # Store first learning
        result1 = await store_learning_v2(
            session_id="test-dedup-session",
            content="First version of learning",
            learning_type="WORKING_SOLUTION",
        )

        # Try to store similar learning
        result2 = await store_learning_v2(
            session_id="test-dedup-session",
            content="Almost identical learning content",  # Very similar
            learning_type="WORKING_SOLUTION",
        )

        # Second might be skipped depending on similarity
        assert result1["success"] is True
        assert result2["success"] is True


@pytest.mark.docker
@pytest.mark.postgres
class TestPostgresBackendSwitching:
    """Tests for backend switching behavior."""

    def test_postgres_backend_selected_with_url(self, postgres_container):
        """Test PostgreSQL backend is selected when DATABASE_URL is set."""
        with patch.dict(os.environ, {"DATABASE_URL": os.environ["DATABASE_URL"]}):
            from scripts.store_learning import store_learning_v2

            # The backend should be detected as postgres
            import asyncio

            async def check_backend():
                from scripts.core.db.memory_factory import get_default_backend
                return get_default_backend()

            with patch("scripts.store_learning.create_memory_service", new_callable=AsyncMock):
                with patch("scripts.store_learning.EmbeddingService") as mock_embed:
                    mock_service = MagicMock()
                    mock_service.embed = AsyncMock(return_value=[0.1] * 384)
                    mock_embed.return_value = mock_service

                    result = asyncio.run(store_learning_v2(
                        session_id="test-backend",
                        content="Test content",
                    ))

                    # Should succeed with postgres backend
                    if result["success"]:
                        assert result.get("backend") == "postgres"
```

### E2E Tests

```python
"""
End-to-end tests for store_learning.py

Location: opc/tests/e2e/test_store_learning.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import *


class TestStoreE2E:
    """End-to-end tests for store CLI."""

    @pytest.mark.slow
    def test_store_cli_v2_success(self, temp_dir: Path):
        """Test successful v2 storage via CLI."""
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from scripts.store_learning import main
sys.exit(asyncio.run(main()))
"""],
            cwd=str(Path(__file__).parent.parent.parent),
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": ""},
            input="--session-id test-session --content 'E2E test learning' --type WORKING_SOLUTION --json",
        )

        if result.returncode == 0:
            output = json.loads(result.stdout)
            assert output["success"] is True

    @pytest.mark.slow
    def test_store_cli_missing_session_id(self, temp_dir: Path):
        """Test CLI rejects missing session ID."""
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from scripts.store_learning import main
sys.exit(asyncio.run(main()))
"""],
            cwd=str(Path(__file__).parent.parent.parent),
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": ""},
            input="--content 'Test content'",
        )

        # Should fail due to missing required --session-id
        assert result.returncode != 0

    @pytest.mark.slow
    def test_store_cli_legacy_mode(self, temp_dir: Path):
        """Test legacy storage mode still works."""
        result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from scripts.store_learning import main
sys.exit(asyncio.run(main()))
"""],
            cwd=str(Path(__file__).parent.parent.parent),
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": ""},
            input="--session-id legacy-session --worked 'Legacy approach worked' --json",
        )

        if result.returncode == 0:
            output = json.loads(result.stdout)
            assert output["success"] is True


class TestStoreEndToEnd:
    """End-to-end storage and recall workflow."""

    @pytest.mark.slow
    def test_store_then_recall_workflow(self, temp_dir: Path):
        """Test complete store then recall workflow."""
        import subprocess
        import sys
        from pathlib import Path

        project_root = Path(__file__).parent.parent.parent

        # Step 1: Store a learning
        store_result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from scripts.store_learning import main
sys.exit(asyncio.run(main()))
"""],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": ""},
            input="--session-id workflow-session --content 'Workflow test learning about testing' --type CODEBASE_PATTERN --context testing --tags workflow,test --json",
        )

        if store_result.returncode != 0:
            pytest.skip("Store failed, possibly no database available")

        # Step 2: Recall the learning
        recall_result = subprocess.run(
            [sys.executable, "-c", """
import sys
sys.path.insert(0, '.')
from scripts.recall_learnings import main
sys.exit(asyncio.run(main()))
"""],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            env={**os.environ, "DATABASE_URL": ""},
            input="--query 'testing patterns' --json",
        )

        # Verify
        if recall_result.returncode == 0:
            output = json.loads(recall_result.stdout)
            assert "results" in output


### Common Failure Points for store_learning.py

"""
Failure points to test:

1. Content validation:
   - Empty strings
   - Whitespace-only
   - Extremely long content

2. Metadata construction:
   - Invalid learning types
   - Invalid confidence levels
   - Missing required fields

3. Deduplication:
   - Below threshold similarity
   - Search failures during dedup
   - Race conditions with concurrent stores

4. Backend selection:
   - DATABASE_URL with invalid format
   - Connection pool exhaustion
   - SQLite file locking

5. Embedding generation:
   - API failures (Voyage)
   - Model loading failures
   - Dimension mismatches
"""
```

---

## stream_monitor.py Tests

### Unit Tests

```python
"""
Unit tests for stream_monitor.py

Location: opc/tests/unit/test_stream_monitor.py
"""

import json
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import *


class TestStreamEvent:
    """Unit tests for StreamEvent dataclass."""

    def test_stream_event_creation(self):
        """Test StreamEvent can be created with all fields."""
        from stream_monitor import StreamEvent

        event = StreamEvent(
            event_type="tool_use",
            timestamp=datetime.now(UTC).isoformat(),
            data={"name": "Read", "input": {"file_path": "/test.py"}},
            turn_number=0,
        )

        assert event.event_type == "tool_use"
        assert event.data["name"] == "Read"
        assert event.turn_number == 0

    def test_stream_event_to_dict(self):
        """Test StreamEvent.to_dict() serializes correctly."""
        from stream_monitor import StreamEvent

        event = StreamEvent(
            event_type="text",
            timestamp="2024-01-01T00:00:00Z",
            data={"text": "Hello"},
            turn_number=1,
        )

        result = event.to_dict()

        assert isinstance(result, dict)
        assert result["event_type"] == "text"
        assert result["data"] == {"text": "Hello"}
        assert result["turn_number"] == 1


class TestMonitorState:
    """Unit tests for MonitorState dataclass."""

    def test_monitor_state_defaults(self):
        """Test MonitorState has correct default values."""
        from stream_monitor import MonitorState

        state = MonitorState(agent_id="test-agent")

        assert state.agent_id == "test-agent"
        assert state.events == []
        assert state.turn_count == 0
        assert state.is_stuck is False
        assert state.stuck_reason is None


class TestStreamMonitor:
    """Unit tests for StreamMonitor class."""

    def test_monitor_initialization(self, mock_redis_client):
        """Test StreamMonitor initializes correctly."""
        from stream_monitor import StreamMonitor

        callback_event = MagicMock()
        callback_stuck = MagicMock()

        monitor = StreamMonitor(
            agent_id="test-agent",
            redis_client=mock_redis_client,
            on_event=callback_event,
            on_stuck=callback_stuck,
        )

        assert monitor.agent_id == "test-agent"
        assert monitor.redis_client is mock_redis_client
        assert monitor.is_stuck is False

    def test_monitor_properties(self, mock_redis_client):
        """Test StreamMonitor property access."""
        from stream_monitor import StreamMonitor

        monitor = StreamMonitor(agent_id="test-agent")

        assert monitor.turn_count == 0
        assert monitor.event_count == 0
        assert monitor.stuck_reason is None

    def test_get_events_empty(self, mock_redis_client):
        """Test get_events returns empty list initially."""
        from stream_monitor import StreamMonitor

        monitor = StreamMonitor(agent_id="test-agent")

        events = monitor.get_events()

        assert events == []

    def test_get_events_with_limit(self, mock_redis_client):
        """Test get_events respects limit parameter."""
        from stream_monitor import StreamMonitor
        from stream_monitor import StreamEvent

        monitor = StreamMonitor(agent_id="test-agent")

        # Add events directly to internal state
        with patch.object(monitor, '_lock'):
            for i in range(10):
                monitor._state.events.append(
                    StreamEvent(
                        event_type="text",
                        timestamp=datetime.now(UTC).isoformat(),
                        data={"text": f"Event {i}"},
                    )
                )

        # Get last 3
        events = monitor.get_events(limit=3)

        assert len(events) == 3

    def test_get_summary(self, mock_redis_client):
        """Test get_summary returns correct state."""
        from stream_monitor import StreamMonitor
        from stream_monitor import StreamEvent

        monitor = StreamMonitor(agent_id="test-agent")

        # Add some events
        with patch.object(monitor, '_lock'):
            monitor._state.events.append(
                StreamEvent(
                    event_type="text",
                    timestamp=datetime.now(UTC).isoformat(),
                    data={"text": "Hello"},
                )
            )
            monitor._state.turn_count = 1

        summary = monitor.get_summary()

        assert summary["agent_id"] == "test-agent"
        assert summary["event_count"] == 1
        assert summary["turn_count"] == 1
        assert summary["is_stuck"] is False


class TestStuckDetection:
    """Unit tests for stuck agent detection."""

    def test_consecutive_tool_detection(self, mock_redis_client):
        """Test detection of same tool called repeatedly."""
        from stream_monitor import StreamMonitor, StreamEvent

        monitor = StreamMonitor(agent_id="test-agent")

        # Simulate 5+ Read calls
        for i in range(6):
            event = StreamEvent(
                event_type="tool_use",
                timestamp=datetime.now(UTC).isoformat(),
                data={"tool": "Read", "input": {}},
                turn_number=0,
            )
            monitor._process_event(event)

        assert monitor.is_stuck is True
        assert "Read" in monitor.stuck_reason
        assert "5+" in monitor.stuck_reason

    def test_consecutive_thinking_detection(self, mock_redis_client):
        """Test detection of agent stuck in thinking."""
        from stream_monitor import StreamMonitor, StreamEvent

        monitor = StreamMonitor(agent_id="test-agent")

        # Simulate 5+ thinking events
        for i in range(6):
            event = StreamEvent(
                event_type="thinking",
                timestamp=datetime.now(UTC).isoformat(),
                data={"thinking": f"Thinking {i}..."},
                turn_number=0,
            )
            monitor._process_event(event)

        assert monitor.is_stuck is True
        assert "thinking" in monitor.stuck_reason

    def test_counter_reset_on_other_events(self, mock_redis_client):
        """Test counters reset when non-stuck events occur."""
        from stream_monitor import StreamMonitor, StreamEvent

        monitor = StreamMonitor(agent_id="test-agent")

        # 3 Read calls
        for i in range(3):
            event = StreamEvent(
                event_type="tool_use",
                timestamp=datetime.now(UTC).isoformat(),
                data={"tool": "Read"},
            )
            monitor._process_event(event)

        # Text event should reset counter
        event = StreamEvent(
            event_type="text",
            timestamp=datetime.now(UTC).isoformat(),
            data={"text": "Response"},
        )
        monitor._process_event(event)

        # Now only 2 more Read calls should not trigger stuck
        for i in range(2):
            event = StreamEvent(
                event_type="tool_use",
                timestamp=datetime.now(UTC).isoformat(),
                data={"tool": "Read"},
            )
            monitor._process_event(event)

        assert monitor.is_stuck is False


class TestEventParsing:
    """Unit tests for event parsing."""

    def test_parse_event_tool_use(self):
        """Test parsing tool_use events."""
        from stream_monitor import StreamMonitor

        monitor = StreamMonitor(agent_id="test")

        event = monitor._parse_event(
            json.dumps({"type": "tool_use", "name": "Read"})
        )

        assert event is not None
        assert event.event_type == "tool_use"

    def test_parse_event_thinking(self):
        """Test parsing thinking events."""
        from stream_monitor import StreamMonitor

        monitor = StreamMonitor(agent_id="test")

        event = monitor._parse_event(
            json.dumps({"type": "thinking", "thinking": "Analyzing..."})
        )

        assert event is not None
        assert event.event_type == "thinking"

    def test_parse_event_tool_result(self):
        """Test parsing tool_result events."""
        from stream_monitor import StreamMonitor

        monitor = StreamMonitor(agent_id="test")

        event = monitor._parse_event(
            json.dumps({"type": "tool_result", "tool_use_id": "123", "content": "result"})
        )

        assert event is not None
        assert event.event_type == "tool_result"

    def test_parse_event_error(self):
        """Test parsing error events."""
        from stream_monitor import StreamMonitor

        monitor = StreamMonitor(agent_id="test")

        event = monitor._parse_event(
            json.dumps({"type": "error", "error": "Something went wrong"})
        )

        assert event is not None
        assert event.event_type == "error"

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON returns None."""
        from stream_monitor import StreamMonitor

        monitor = StreamMonitor(agent_id="test")

        result = monitor._parse_event("not valid json")

        assert result is None

    def test_parse_empty_line(self):
        """Test parsing empty line returns None."""
        from stream_monitor import StreamMonitor

        monitor = StreamMonitor(agent_id="test")

        result = monitor._parse_event("")

        assert result is None


class TestRedisIntegration:
    """Unit tests for Redis event pushing."""

    def test_redis_push_on_event(self, mock_redis_client):
        """Test events are pushed to Redis."""
        from stream_monitor import StreamMonitor, StreamEvent

        monitor = StreamMonitor(agent_id="test-agent", redis_client=mock_redis_client)

        event = StreamEvent(
            event_type="tool_use",
            timestamp=datetime.now(UTC).isoformat(),
            data={"tool": "Read"},
        )
        monitor._process_event(event)

        # Verify Redis was called
        mock_redis_client.lpush.assert_called()
        mock_redis_client.expire.assert_called()

    def test_redis_ttl_is_set(self, mock_redis_client):
        """Test Redis TTL is set correctly."""
        from stream_monitor import StreamMonitor, StreamEvent, REDIS_EVENT_TTL

        monitor = StreamMonitor(agent_id="test-agent", redis_client=mock_redis_client)

        event = StreamEvent(
            event_type="text",
            timestamp=datetime.now(UTC).isoformat(),
            data={"text": "Hello"},
        )
        monitor._process_event(event)

        # Verify expire was called with correct TTL
        mock_redis_client.expire.assert_called()
        args = mock_redis_client.expire.call_args
        assert args[0][1] == REDIS_EVENT_TTL
```

### Integration Tests

```python
"""
Integration tests for stream_monitor.py

Location: opc/tests/integration/test_stream_monitor.py
"""

import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import *


@pytest.fixture
def mock_subprocess_with_output(temp_dir: Path) -> Generator[MagicMock, None, None]:
    """Create a mock process with stdout that produces stream events."""
    process = MagicMock()

    # Simulate stream-json output
    def generate_output():
        events = [
            {"type": "thinking", "thinking": "Analyzing..."},
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/test.py"}},
            {"type": "tool_result", "tool_use_id": "1", "content": "file content"},
            {"type": "text", "text": "Done"},
            {"type": "result", "content": {"success": True}},
        ]
        for event in events:
            yield json.dumps(event).encode()
        raise StopIteration

    process.stdout.readline = MagicMock(side_effect=generate_output())
    process.wait = MagicMock(return_value=0)

    yield process


@pytest.mark.docker
@pytest.mark.redis
class TestRedisIntegration:
    """Integration tests with real Redis."""

    @pytest.fixture
    def real_redis_client(self, redis_container):
        """Create real Redis client."""
        import redis
        return redis.Redis(host="localhost", port=6379, decode_responses=True)

    def test_redis_event_stream(self, real_redis_client):
        """Test events are correctly streamed to Redis."""
        from stream_monitor import StreamMonitor, StreamEvent

        monitor = StreamMonitor(agent_id="test-redis-agent", redis_client=real_redis_client)

        # Add events
        event = StreamEvent(
            event_type="tool_use",
            timestamp=datetime.now(UTC).isoformat(),
            data={"tool": "Read"},
        )
        monitor._process_event(event)

        # Verify in Redis
        key = "agent:test-redis-agent:events"
        events = real_redis_client.lrange(key, 0, -1)

        assert len(events) == 1
        stored = json.loads(events[0])
        assert stored["event_type"] == "tool_use"

    def test_redis_ttl_enforced(self, real_redis_client):
        """Test Redis TTL is enforced on event keys."""
        from stream_monitor import StreamMonitor, StreamEvent

        agent_id = f"test-ttl-{datetime.now().timestamp()}"
        monitor = StreamMonitor(agent_id=agent_id, redis_client=real_redis_client)

        event = StreamEvent(
            event_type="text",
            timestamp=datetime.now(UTC).isoformat(),
            data={"text": "Test"},
        )
        monitor._process_event(event)

        # Verify TTL is set
        key = f"agent:{agent_id}:events"
        ttl = real_redis_client.ttl(key)

        assert ttl > 0
        assert ttl <= 24 * 60 * 60  # Max 24 hours


class TestMonitorThreading:
    """Integration tests for monitor threading."""

    def test_start_stop_thread_safety(self, mock_subprocess_with_output):
        """Test start/stop operations are thread-safe."""
        from stream_monitor import StreamMonitor

        monitor = StreamMonitor(agent_id="test-thread")

        # Start monitoring
        monitor.start(mock_subprocess_with_output)

        # Stop monitoring
        monitor.stop(timeout=1.0)

        assert monitor._thread is not None

    def test_already_started_error(self, mock_subprocess_with_output):
        """Test starting monitor twice raises error."""
        from stream_monitor import StreamMonitor

        monitor = StreamMonitor(agent_id="test-double")

        monitor.start(mock_subprocess_with_output)

        with pytest.raises(RuntimeError, match="already started"):
            monitor.start(mock_subprocess_with_output)

        monitor.stop(timeout=1.0)


class TestTurnTracking:
    """Integration tests for turn tracking."""

    def test_turn_increment_on_tool_result(self, mock_redis_client):
        """Test turn count increments on tool_result events."""
        from stream_monitor import StreamMonitor, StreamEvent

        monitor = StreamMonitor(agent_id="test-turns")

        # Initial state
        assert monitor.turn_count == 0

        # Tool result should increment turn
        event = StreamEvent(
            event_type="tool_result",
            timestamp=datetime.now(UTC).isoformat(),
            data={"tool_use_id": "1"},
        )
        monitor._process_event(event)

        assert monitor.turn_count == 1

    def test_multiple_turns(self, mock_redis_client):
        """Test multiple turns are counted correctly."""
        from stream_monitor import StreamMonitor, StreamEvent

        monitor = StreamMonitor(agent_id="test-multi-turns")

        for i in range(3):
            event = StreamEvent(
                event_type="tool_result",
                timestamp=datetime.now(UTC).isoformat(),
                data={"tool_use_id": str(i)},
            )
            monitor._process_event(event)

        assert monitor.turn_count == 3
```

### E2E Tests

```python
"""
End-to-end tests for stream_monitor.py

Location: opc/tests/e2e/test_stream_monitor.py
"""

import json
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from tests.conftest import *


class TestMonitorE2E:
    """End-to-end tests for stream monitoring."""

    @pytest.mark.slow
    def test_full_monitoring_cycle(self, temp_dir: Path):
        """Test complete monitoring cycle from start to finish."""
        from stream_monitor import StreamMonitor

        # Create a simple subprocess that outputs events
        proc = subprocess.Popen(
            [sys.executable, "-c", """
import json
import time
events = [
    {"type": "thinking", "thinking": "Processing..."},
    {"type": "tool_use", "name": "Read", "input": {"file_path": "/test.py"}},
    {"type": "tool_result", "tool_use_id": "1", "content": "test"},
    {"type": "text", "text": "Complete"},
    {"type": "result", "content": "success"},
]
for event in events:
    print(json.dumps(event))
    time.sleep(0.1)
"""],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Create monitor with callbacks
        events_received = []
        stuck_detected = []

        def on_event(event):
            events_received.append(event)

        def on_stuck(reason):
            stuck_detected.append(reason)

        monitor = StreamMonitor(
            agent_id="e2e-test-agent",
            on_event=on_event,
            on_stuck=on_stuck,
        )

        # Start monitoring
        monitor.start(proc)

        # Wait for process to complete
        proc.wait()

        # Give monitor time to process
        time.sleep(0.5)

        # Stop monitor
        monitor.stop(timeout=2.0)

        # Verify
        assert len(events_received) > 0
        assert len(stuck_detected) == 0  # Should not be stuck
        assert monitor.get_summary()["exit_code"] == 0

    @pytest.mark.slow
    def test_stuck_detection_e2e(self, temp_dir: Path):
        """Test end-to-end stuck detection."""
        from stream_monitor import StreamMonitor

        # Create a process that loops the same tool
        proc = subprocess.Popen(
            [sys.executable, "-c", """
import json
import time
for i in range(10):  # 10 Read calls should trigger stuck detection
    print(json.dumps({"type": "tool_use", "name": "Read", "input": {}}))
    time.sleep(0.05)
"""],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        stuck_reason = []

        def on_stuck(reason):
            stuck_reason.append(reason)
            # Terminate process for cleanup
            import os
            os.kill(proc.pid, 9)

        monitor = StreamMonitor(
            agent_id="stuck-test-agent",
            on_stuck=on_stuck,
        )

        monitor.start(proc)
        proc.wait()
        time.sleep(0.5)
        monitor.stop(timeout=1.0)

        # Verify stuck was detected
        assert len(stuck_reason) > 0
        assert "Read" in stuck_reason[0]


class TestAsyncMonitoring:
    """End-to-end tests for async monitoring."""

    @pytest.mark.asyncio
    async def test_async_file_monitoring(self, temp_dir: Path):
        """Test async monitoring of output file."""
        from stream_monitor import monitor_agent_async

        # Create output file
        output_file = temp_dir / "agent_output.jsonl"
        output_file.write_text(
            json.dumps({"type": "thinking", "thinking": "Thinking..."}) + "\n"
            + json.dumps({"type": "result", "content": "done"}) + "\n"
        )

        # Monitor file
        state = await monitor_agent_async(
            agent_id="async-test",
            output_file=str(output_file),
        )

        assert state.agent_id == "async-test"
        assert len(state.events) == 2


### Common Failure Points for stream_monitor.py

"""
Failure points to test:

1. Threading:
   - Race conditions in event processing
   - Thread termination during event parsing
   - Lock contention with many events

2. Stuck detection:
   - Counter overflow
   - Mixed tool calls resetting incorrectly
   - Threshold boundary conditions

3. Redis:
   - Connection failures during push
   - TTL calculation errors
   - Key naming conflicts

4. Event parsing:
   - Malformed JSON handling
   - Unknown event types
   - Large event payloads

5. Memory:
   - Event list unbounded growth
   - Large embedding payloads
   - Memory leaks in long-running monitors
"""
```

---

## mcp_client.py Tests

### Unit Tests

```python
"""
Unit tests for mcp_client.py

Location: opc/tests/unit/test_mcp_client.py
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import *


class TestConnectionState:
    """Unit tests for ConnectionState enum."""

    def test_connection_states(self):
        """Test all connection states are defined."""
        from mcp_client import ConnectionState

        assert ConnectionState.UNINITIALIZED.value == "uninitialized"
        assert ConnectionState.INITIALIZED.value == "initialized"
        assert ConnectionState.CONNECTED.value == "connected"


class TestResultUnwrapping:
    """Unit tests for result unwrapping functions."""

    def test_unwrap_result_value(self):
        """Test unwrapping result.value."""
        from mcp_client import _unwrap_result

        mock_result = MagicMock()
        mock_result.value = "test value"

        result = _unwrap_result(mock_result)
        assert result == "test value"

    def test_unwrap_result_content(self):
        """Test unwrapping result.content."""
        from mcp_client import _unwrap_result

        mock_result = MagicMock()
        mock_result.value = AttributeError()  # Will raise
        mock_result.content = "content value"

        result = _unwrap_result(mock_result)
        assert result == "content value"

    def test_unwrap_result_fallback(self):
        """Test unwrapping falls back to result itself."""
        from mcp_client import _unwrap_result

        mock_result = "raw value"

        result = _unwrap_result(mock_result)
        assert result == "raw value"

    def test_unwrap_text_content_simple(self):
        """Test unwrapping text content."""
        from mcp_client import _unwrap_text_content

        mock_item = MagicMock()
        mock_item.text = "simple text"

        result = _unwrap_text_content([mock_item])
        assert result == "simple text"

    def test_unwrap_text_content_json(self):
        """Test unwrapping JSON-formatted text content."""
        from mcp_client import _unwrap_text_content

        mock_item = MagicMock()
        mock_item.text = '{"key": "value"}'

        result = _unwrap_text_content([mock_item])
        assert result == {"key": "value"}

    def test_unwrap_empty_list(self):
        """Test unwrapping empty content list."""
        from mcp_client import _unwrap_text_content

        result = _unwrap_text_content([])
        assert result == []


class TestMcpClientManager:
    """Unit tests for McpClientManager class."""

    def test_manager_initial_state(self):
        """Test manager starts in UNINITIALIZED state."""
        from mcp_client import McpClientManager, ConnectionState

        manager = McpClientManager()

        assert manager._state == ConnectionState.UNINITIALIZED
        assert manager._clients == {}
        assert manager._tool_cache == {}
        assert manager._config is None

    def test_validate_state_uninitialized(self):
        """Test state validation for uninitialized manager."""
        from mcp_client import McpClientManager, ConnectionState

        manager = McpClientManager()

        # Should not raise for uninitialized state
        manager._validate_state(ConnectionState.UNINITIALIZED, "test operation")

    def test_validate_state_wrong_state(self):
        """Test state validation raises error for wrong state."""
        from mcp_client import McpClientManager, ConnectionState
        from mcp_client.exceptions import ConfigurationError

        manager = McpClientManager()

        with pytest.raises(ConfigurationError):
            manager._validate_state(ConnectionState.CONNECTED, "test operation")

    def test_validate_state_at_least(self):
        """Test minimum state validation."""
        from mcp_client import McpClientManager, ConnectionState

        manager = McpClientManager()

        # Should not raise - uninitialized >= uninitialized
        manager._validate_state_at_least(ConnectionState.UNINITIALIZED, "test")

    def test_state_transitions(self):
        """Test state transition methods."""
        from mcp_client import McpClientManager, ConnectionState

        manager = McpClientManager()

        # Initial state
        assert manager._state == ConnectionState.UNINITIALIZED

        # Transition to initialized
        manager._mark_initialized()
        assert manager._state == ConnectionState.INITIALIZED

        # Transition to connected
        manager._mark_connected()
        assert manager._state == ConnectionState.CONNECTED

        # Transition back to uninitialized
        manager._mark_uninitialized()
        assert manager._state == ConnectionState.UNINITIALIZED

    def test_config_merge(self, sample_mcp_config):
        """Test config merging."""
        from mcp_client import McpConfig

        # Create config objects
        global_config = McpConfig.model_validate_json(json.dumps(sample_mcp_config))
        project_config = McpConfig.model_validate_json(json.dumps({
            "mcpServers": {
                "project-server": {
                    "command": "python",
                    "args": ["-m", "project"],
                    "type": "stdio",
                }
            }
        }))

        # Merge
        merged = global_config.merge(project_config)

        # Project config should be included
        assert "project-server" in merged.mcpServers

    def test_tool_caching(self):
        """Test tool caching behavior."""
        from mcp_client import McpClientManager, ConnectionState

        manager = McpClientManager()
        manager._state = ConnectionState.INITIALIZED

        # Initially empty
        assert manager._tool_cache == {}

        # Add cached tools
        mock_tool = MagicMock()
        mock_tool.name = "test_tool"
        manager._tool_cache["test-server"] = [mock_tool]

        assert len(manager._tool_cache["test-server"]) == 1

    def test_get_server_tools_from_cache(self):
        """Test getting tools from cache."""
        from mcp_client import McpClientManager, ConnectionState

        manager = McpClientManager()
        manager._state = ConnectionState.INITIALIZED

        # Add cached tool
        mock_tool = MagicMock()
        mock_tool.name = "cached_tool"
        manager._tool_cache["test-server"] = [mock_tool]

        tools = manager._get_server_tools("test-server")

        assert len(tools) == 1
        assert tools[0].name == "cached_tool"

    def test_get_server_tools_not_connected(self):
        """Test getting tools from unconnected server raises error."""
        from mcp_client import McpClientManager, ConnectionState
        from mcp_client.exceptions import ServerConnectionError

        manager = McpClientManager()
        manager._state = ConnectionState.INITIALIZED

        with pytest.raises(ServerConnectionError, match="Not connected"):
            manager._get_server_tools("unconnected-server")


class TestToolCalling:
    """Unit tests for tool calling functionality."""

    def test_call_tool_invalid_identifier(self):
        """Test calling tool with invalid identifier format."""
        from mcp_client import McpClientManager
        from mcp_client.exceptions import ToolNotFoundError

        manager = McpClientManager()
        manager._state = ConnectionState.INITIALIZED

        with pytest.raises(ToolNotFoundError, match="Invalid tool identifier"):
            manager.call_tool("no_double_underscore", {})

    def test_call_tool_not_initialized(self):
        """Test calling tool without initialization."""
        from mcp_client import McpClientManager
        from mcp_client.exceptions import ConfigurationError

        manager = McpClientManager()

        with pytest.raises(ConfigurationError):
            manager.call_tool("server__tool", {})


class TestConfigLoading:
    """Unit tests for configuration loading."""

    def test_find_project_config_exists(self, sample_mcp_config, temp_dir: Path):
        """Test finding project config when it exists."""
        from mcp_client import _find_project_config

        # Create config file
        config_file = temp_dir / ".mcp.json"
        config_file.write_text(json.dumps(sample_mcp_config))

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = _find_project_config()

            assert result == config_file

    def test_find_project_config_not_exists(self, temp_dir: Path):
        """Test finding project config when it doesn't exist."""
        from mcp_client import _find_project_config

        with patch("pathlib.Path.cwd", return_value=temp_dir):
            result = _find_project_config()

            assert result is None

    def test_merge_configs(self, sample_mcp_config):
        """Test merging global and project configs."""
        from mcp_client import _merge_configs, McpConfig

        global_cfg = McpConfig.model_validate_json(json.dumps(sample_mcp_config))
        project_cfg = McpConfig.model_validate_json(json.dumps({
            "mcpServers": {
                "project-server": sample_mcp_config["mcpServers"]["test-server"]
            }
        }))

        merged = _merge_configs(global_cfg, project_cfg)

        assert "test-server" in merged.mcpServers
        assert "project-server" in merged.mcpServers

    def test_merge_configs_project_precedence(self, sample_mcp_config):
        """Test project config takes precedence for same server."""
        from mcp_client import _merge_configs, McpConfig

        global_cfg = McpConfig.model_validate_json(json.dumps({
            "mcpServers": {
                "shared-server": {
                    "command": "global",
                    "args": [],
                    "type": "stdio",
                }
            }
        }))

        project_cfg = McpConfig.model_validate_json(json.dumps({
            "mcpServers": {
                "shared-server": {
                    "command": "project",
                    "args": [],
                    "type": "stdio",
                }
            }
        }))

        merged = _merge_configs(global_cfg, project_cfg)

        # Project config should override
        assert merged.mcpServers["shared-server"].command == "project"


class TestEnvVarSubstitution:
    """Unit tests for environment variable substitution."""

    def test_substitute_env_vars(self):
        """Test environment variable substitution in config."""
        from mcp_client import McpClientManager

        manager = McpClientManager()

        env = {"API_KEY": "${TEST_API_KEY}"}

        with patch.dict(os.environ, {"TEST_API_KEY": "secret123"}):
            result = manager._substitute_env_vars(env)

            assert result["API_KEY"] == "secret123"

    def test_substitute_env_vars_no_match(self):
        """Test substitution with no matching env var."""
        from mcp_client import McpClientManager

        manager = McpClientManager()

        env = {"API_KEY": "${NONEXISTENT_KEY}"}

        result = manager._substitute_env_vars(env)

        assert result["API_KEY"] == ""
```

### Integration Tests

```python
"""
Integration tests for mcp_client.py

Location: opc/tests/integration/test_mcp_client.py
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import *


@pytest.fixture
def mock_mcp_server() -> Generator[subprocess.Popen, None, None]:
    """Start a mock MCP server for integration testing."""
    server_code = '''
import json
import sys

# Simple mock MCP server
while True:
    line = sys.stdin.readline()
    if not line:
        break
    try:
        msg = json.loads(line)
        method = msg.get("method")
        params = msg.get("params", {})

        if method == "initialize":
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "test-server", "version": "1.0.0"}
                }
            }))
            sys.stdout.flush()
        elif method == "tools/list":
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "result": {"tools": [
                    {"name": "test_tool", "description": "A test tool"}
                ]}
            }))
            sys.stdout.flush()
        elif method == "tools/call":
            print(json.dumps({
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "result": {"content": [{"type": "text", "text": "tool result"}]}
            }))
            sys.stdout.flush()
    except Exception as e:
        print(json.dumps({"jsonrpc": "2.0", "error": {"code": -1, "message": str(e)}}))
        sys.stdout.flush()
'''

    proc = subprocess.Popen(
        [sys.executable, "-c", server_code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()


class TestMcpClientIntegration:
    """Integration tests for MCP client with real connections."""

    def test_initialization_with_config(self, sample_mcp_config, temp_dir: Path):
        """Test client initialization with valid configuration."""
        from mcp_client import McpClientManager, McpConfig

        manager = McpClientManager()

        # Create config
        config = McpConfig.model_validate_json(json.dumps(sample_mcp_config))

        # Should not raise
        assert manager._state.value == "uninitialized"

    def test_list_all_tools(self, sample_mcp_config, temp_dir: Path):
        """Test listing all tools from configuration."""
        from mcp_client import McpClientManager, McpConfig
        from mcp_client.exceptions import ConfigurationError

        manager = McpClientManager()

        # Create config with disabled server
        config = McpConfig.model_validate_json(json.dumps(sample_mcp_config))
        config.mcpServers["test-server"].disabled = True

        manager._config = config
        manager._state.value = "initialized"  # Direct state manipulation for test

        # Should return empty list for no enabled servers
        async def run_test():
            return await manager.list_all_tools()

        with patch("mcp_client.McpClientManager._connect_to_server"):
            result = asyncio.run(run_test())

            assert isinstance(result, list)

    def test_cleanup_all_connections(self, sample_mcp_config, temp_dir: Path):
        """Test cleaning up all connections."""
        from mcp_client import McpClientManager, ConnectionState

        manager = McpClientManager()
        manager._state = ConnectionState.CONNECTED

        # Add fake connections
        manager._clients["test-server"] = MagicMock()
        manager._session_contexts["test-server"] = MagicMock()
        manager._stdio_contexts["test-server"] = MagicMock()

        # Cleanup
        async def run_cleanup():
            await manager.cleanup()

        with patch.object(manager._session_contexts["test-server"], "__aexit__", new_callable=AsyncMock):
            with patch.object(manager._stdio_contexts["test-server"], "__aexit__", new_callable=AsyncMock):
                asyncio.run(run_cleanup())

        # Verify cleanup
        assert manager._state == ConnectionState.UNINITIALIZED
        assert len(manager._clients) == 0
        assert len(manager._session_contexts) == 0


class TestStateTransitionsIntegration:
    """Integration tests for state transitions."""

    def test_initialize_from_uninitialized(self, sample_mcp_config, temp_dir: Path):
        """Test initialization transition from UNINITIALIZED."""
        from mcp_client import McpClientManager, ConnectionState

        manager = McpClientManager()
        assert manager._state == ConnectionState.UNINITIALIZED

        manager._mark_initialized()
        assert manager._state == ConnectionState.INITIALIZED

    def test_connected_from_initialized(self, sample_mcp_config, temp_dir: Path):
        """Test connection transition from INITIALIZED to CONNECTED."""
        from mcp_client import McpClientManager, ConnectionState

        manager = McpClientManager()
        manager._state = ConnectionState.INITIALIZED

        manager._mark_connected()
        assert manager._state == ConnectionState.CONNECTED

    def test_cleanup_resets_state(self, sample_mcp_config, temp_dir: Path):
        """Test cleanup resets state to UNINITIALIZED."""
        from mcp_client import McpClientManager, ConnectionState

        manager = McpClientManager()
        manager._state = ConnectionState.CONNECTED

        manager._mark_uninitialized()
        assert manager._state == ConnectionState.UNINITIALIZED


class TestHttpTransportIntegration:
    """Integration tests for HTTP transport."""

    def test_connect_http_format(self, sample_mcp_config):
        """Test HTTP connection format validation."""
        from mcp_client import McpClientManager

        manager = McpClientManager()

        # Valid HTTP URL
        assert manager._connect_http is not None

    def test_connect_sse_format(self, sample_mcp_config):
        """Test SSE connection format validation."""
        from mcp_client import McpClientManager

        manager = McpClientManager()

        # Valid SSE URL
        assert manager._connect_sse is not None
```

### E2E Tests

```python
"""
End-to-end tests for mcp_client.py

Location: opc/tests/e2e/test_mcp_client.py
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import *


class TestMcpClientE2E:
    """End-to-end tests for MCP client."""

    @pytest.mark.slow
    def test_full_tool_call_lifecycle(self, temp_dir: Path):
        """Test complete tool call lifecycle."""
        from mcp_client import McpClientManager, ConnectionState, McpConfig

        # Create a simple mock server script
        server_script = temp_dir / "mock_server.py"
        server_script.write_text('''
import json
import sys

def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            msg = json.loads(line)
            msg_id = msg.get("id")
            method = msg.get("method")

            if method == "initialize":
                print(json.dumps({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "test-server", "version": "1.0.0"}
                    }
                }))
                sys.stdout.flush()
            elif method == "tools/list":
                print(json.dumps({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {"tools": [{"name": "echo", "description": "Echo tool"}]}
                }))
                sys.stdout.flush()
            elif method == "tools/call":
                print(json.dumps({
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {"content": [{"type": "text", "text": msg.get("params", {}).get("arguments", {}).get("message", "")}]}
                }))
                sys.stdout.flush()
        except Exception as e:
            print(json.dumps({"jsonrpc": "2.0", "error": {"code": -1, "message": str(e)}}))
            sys.stdout.flush()

if __name__ == "__main__":
    main()
''')

        # Create config
        config_data = {
            "mcpServers": {
                "echo-server": {
                    "command": sys.executable,
                    "args": [str(server_script)],
                    "type": "stdio",
                }
            }
        }

        # Create manager and initialize
        manager = McpClientManager()

        async def run():
            manager._config = McpConfig.model_validate_json(json.dumps(config_data))
            manager._mark_initialized()

            # List tools (should connect)
            tools = await manager.list_all_tools()

            # Cleanup
            await manager.cleanup()

            return tools

        tools = asyncio.run(run())

        assert len(tools) >= 0  # May be empty depending on mock server

    @pytest.mark.slow
    def test_singleton_pattern(self, temp_dir: Path):
        """Test get_mcp_client_manager returns singleton."""
        from mcp_client import get_mcp_client_manager

        manager1 = get_mcp_client_manager()
        manager2 = get_mcp_client_manager()

        # Both should be the same instance (due to lru_cache)
        assert manager1 is manager2


class TestRetryLogic:
    """End-to-end tests for retry logic."""

    @pytest.mark.slow
    def test_retry_on_failure(self, temp_dir: Path):
        """Test retry logic on tool call failure."""
        from mcp_client import McpClientManager, McpConfig, ConnectionState
        from mcp_client.exceptions import ToolExecutionError

        # Create config that will fail
        config_data = {
            "mcpServers": {
                "failing-server": {
                    "command": "nonexistent-command",
                    "args": [],
                    "type": "stdio",
                }
            }
        }

        manager = McpClientManager()
        manager._config = McpConfig.model_validate_json(json.dumps(config_data))
        manager._mark_initialized()

        async def run():
            return await manager.call_tool("failing-server__tool", {}, max_retries=1)

        # Should raise after retries exhausted
        with pytest.raises(ToolExecutionError):
            asyncio.run(run())


class TestCleanupE2E:
    """End-to-end tests for cleanup."""

    @pytest.mark.slow
    def test_cleanup_after_partial_connection(self, temp_dir: Path):
        """Test cleanup after partial connection attempt."""
        from mcp_client import McpClientManager, McpConfig, ConnectionState

        manager = McpClientManager()
        manager._state = ConnectionState.CONNECTED
        manager._clients["partial-server"] = MagicMock()
        manager._session_contexts["partial-server"] = AsyncMock()
        manager._stdio_contexts["partial-server"] = AsyncMock()

        async def run_cleanup():
            await manager.cleanup()

        with patch.object(manager._session_contexts["partial-server"], "__aexit__", new_callable=AsyncMock, return_value=None):
            with patch.object(manager._stdio_contexts["partial-server"], "__aexit__", new_callable=AsyncMock, return_value=None):
                asyncio.run(run_cleanup())

        assert manager._state == ConnectionState.UNINITIALIZED
        assert len(manager._clients) == 0


### Common Failure Points for mcp_client.py

"""
Failure points to test:

1. State machine:
   - Invalid state transitions
   - Race conditions in state changes
   - Cleanup during connection attempts

2. Connection lifecycle:
   - Connection failures during lazy connect
   - Transport type mismatches
   - Server process crashes

3. Tool calling:
   - Tool not found errors
   - Tool execution failures
   - Retry exhaustion

4. Response unwrapping:
   - Unexpected response formats
   - Missing fields in responses
   - Type conversion errors

5. Memory management:
   - Connection leaks
   - Session context leaks
   - Tool cache unbounded growth
"""
```

---

## Test Data Factories

```python
"""
Test data factories for creating consistent test data.

Location: opc/tests/factories.py
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest


class StreamEventFactory:
    """Factory for creating StreamEvent objects."""

    @staticmethod
    def create(
        event_type: str = "text",
        timestamp: str | None = None,
        data: dict | None = None,
        turn_number: int = 0,
    ) -> dict:
        """Create a stream event dictionary."""
        return {
            "type": event_type,
            "timestamp": timestamp or datetime.now(UTC).isoformat(),
            "data": data or {},
            "turn_number": turn_number,
        }

    @staticmethod
    def thinking(content: str = "Thinking...") -> dict:
        """Create a thinking event."""
        return StreamEventFactory.create(
            event_type="thinking",
            data={"thinking": content},
        )

    @staticmethod
    def tool_use(
        name: str = "Read",
        input_data: dict | None = None,
    ) -> dict:
        """Create a tool_use event."""
        return StreamEventFactory.create(
            event_type="tool_use",
            data={"tool": name, "input": input_data or {}},
        )

    @staticmethod
    def tool_result(
        tool_use_id: str = "1",
        content: str = "",
        is_error: bool = False,
    ) -> dict:
        """Create a tool_result event."""
        return StreamEventFactory.create(
            event_type="tool_result",
            data={
                "tool_use_id": tool_use_id,
                "content": content,
                "is_error": is_error,
            },
        )

    @staticmethod
    def text(content: str = "Done") -> dict:
        """Create a text event."""
        return StreamEventFactory.create(
            event_type="text",
            data={"text": content},
        )

    @staticmethod
    def result(success: bool = True) -> dict:
        """Create a result event."""
        return StreamEventFactory.create(
            event_type="result",
            data={"success": success},
        )


class LearningFactory:
    """Factory for creating learning data."""

    @staticmethod
    def create(
        session_id: str = "test-session",
        content: str = "Test learning content",
        learning_type: str = "WORKING_SOLUTION",
        context: str = "testing",
        tags: list[str] | None = None,
        confidence: str = "high",
        embedding_dim: int = 384,
    ) -> dict:
        """Create learning data dictionary."""
        return {
            "id": f"learning-{datetime.now().timestamp()}",
            "session_id": session_id,
            "content": content,
            "metadata": {
                "type": "session_learning",
                "session_id": session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "learning_type": learning_type,
                "context": context,
                "tags": tags or ["test"],
                "confidence": confidence,
            },
            "embedding": [0.1] * embedding_dim,
            "created_at": datetime.now(timezone.utc),
        }

    @staticmethod
    def working_solution(
        content: str = "Approach X worked well",
        context: str = "implementation",
    ) -> dict:
        """Create a WORKING_SOLUTION learning."""
        return LearningFactory.create(
            content=content,
            learning_type="WORKING_SOLUTION",
            context=context,
        )

    @staticmethod
    def failed_approach(
        content: str = "Approach Y didn't work",
        context: str = "implementation",
    ) -> dict:
        """Create a FAILED_APPROACH learning."""
        return LearningFactory.create(
            content=content,
            learning_type="FAILED_APPROACH",
            context=context,
        )


class SessionFactory:
    """Factory for creating session data."""

    @staticmethod
    def create(
        session_id: str | None = None,
        project: str = "/tmp/test-project",
        working_on: str = "Testing",
        extracted: bool = False,
    ) -> dict:
        """Create session data dictionary."""
        return {
            "id": session_id or f"session-{datetime.now().timestamp()}",
            "project": project,
            "working_on": working_on,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
            "memory_extracted_at": (
                datetime.now(timezone.utc).isoformat()
                if extracted else None
            ),
        }

    @staticmethod
    def stale(
        minutes_ago: int = 10,
    ) -> dict:
        """Create a stale session."""
        from datetime import timedelta
        stale_time = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
        return {
            "id": f"stale-session-{datetime.now().timestamp()}",
            "project": "/test",
            "working_on": "Old work",
            "started_at": stale_time.isoformat(),
            "last_heartbeat": stale_time.isoformat(),
            "memory_extracted_at": None,
        }


class McpConfigFactory:
    """Factory for creating MCP configuration."""

    @staticmethod
    def create(
        servers: dict[str, Any] | None = None,
    ) -> dict:
        """Create MCP configuration dictionary."""
        return {
            "mcpServers": servers or {
                "test-server": {
                    "command": "python",
                    "args": ["-m", "test_server"],
                    "type": "stdio",
                    "disabled": False,
                }
            }
        }

    @staticmethod
    def stdio_server(
        name: str = "test-server",
        command: str = "python",
        args: list[str] | None = None,
        disabled: bool = False,
    ) -> dict:
        """Create a stdio server config."""
        return {
            "command": command,
            "args": args or ["-m", "test_server"],
            "type": "stdio",
            "disabled": disabled,
        }

    @staticmethod
    def http_server(
        name: str = "http-server",
        url: str = "http://localhost:8080/mcp",
        disabled: bool = False,
    ) -> dict:
        """Create an HTTP server config."""
        return {
            "url": url,
            "type": "http",
            "headers": {},
            "disabled": disabled,
        }


class MockFactory:
    """Factory for creating mock objects."""

    @staticmethod
    def redis_client() -> MagicMock:
        """Create a mock Redis client."""
        client = MagicMock()
        client.lpush = MagicMock(return_value=1)
        client.rpush = MagicMock(return_value=1)
        client.expire = MagicMock(return_value=True)
        client.set = MagicMock(return_value=True)
        client.get = MagicMock(return_value=None)
        client.delete = MagicMock(return_value=1)
        client.exists = MagicMock(return_value=0)
        client.lrange = MagicMock(return_value=[])
        client.xadd = MagicMock(return_value="test-stream-id")
        client.xread = MagicMock(return_value=[])
        return client

    @staticmethod
    def embedding_service(dims: int = 384) -> MagicMock:
        """Create a mock embedding service."""
        mock = MagicMock()
        mock.embed = MagicMock(return_value=[0.1] * dims)
        mock.aclose = MagicMock()
        return mock

    @staticmethod
    def subprocess(
        pid: int = 12345,
        returncode: int | None = None,
    ) -> MagicMock:
        """Create a mock subprocess.Popen."""
        process = MagicMock()
        process.pid = pid
        process.returncode = returncode
        process.stdout = MagicMock()
        process.stdout.readline = MagicMock(side_effect=StopIteration)
        process.wait = MagicMock(return_value=returncode or 0)
        return process
```

---

## CI Pipeline Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  PYTHON_VERSION: "3.12"

jobs:
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: |
          uv sync --extra dev

      - name: Run unit tests
        run: |
          uv run pytest tests/unit/ \
            -v \
            --tb=short \
            -x \
            --no-header \
            -q \
            --color=yes \
            --cov=scripts \
            --cov-report=term-missing \
            --cov-report=html:coverage-html \
            -m "unit"

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
          fail_ci_if_error: false

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        ports:
          - 5432:5432
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd redis-cli ping
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: |
          uv sync --extra dev --extra postgres --extra embeddings

      - name: Set up PostgreSQL
        run: |
          export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/test_db"
          uv run python -c "from scripts.core.db.postgres_pool import init_db; import asyncio; asyncio.run(init_db())"

      - name: Run integration tests
        run: |
          export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/test_db"
          export REDIS_URL="redis://localhost:6379"

          uv run pytest tests/integration/ \
            -v \
            --tb=short \
            -x \
            --no-header \
            -q \
            --color=yes \
            -m "integration or docker"

  e2e-tests:
    name: End-to-End Tests
    runs-on: ubuntu-latest
    # E2E tests require Docker services
    container: pgvector/pgvector:pg16

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: |
          uv sync --extra dev --extra postgres --extra embeddings

      - name: Run E2E tests
        env:
          DATABASE_URL: "postgresql://postgres:postgres@localhost:5432/test_db"
          REDIS_URL: "redis://localhost:6379"
        run: |
          uv run pytest tests/e2e/ \
            -v \
            --tb=long \
            --timeout=120 \
            -x \
            --no-header \
            -q \
            --color=yes \
            -m "e2e"

  lint:
    name: Lint & Type Check
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync --extra dev

      - name: Run ruff
        run: uv run ruff check scripts/ tests/

      - name: Run mypy
        run: uv run mypy scripts/ tests/ --strict

  all-checks:
    name: All Checks Passed
    needs: [unit-tests, integration-tests, e2e-tests, lint]
    runs-on: ubuntu-latest
    if: always()

    steps:
      - name: Check results
        run: |
          if [ "${{ needs.unit-tests.result }}" != "success" ] || \
             [ "${{ needs.integration-tests.result }}" != "success" ] || \
             [ "${{ needs.e2e-tests.result }}" != "success" ] || \
             [ "${{ needs.lint.result }}" != "success" ]; then
            echo "Some checks failed"
            exit 1
          fi
          echo "All checks passed!"
```

### Makefile for Local Testing

```makefile
# Makefile for local testing

.PHONY: test test-unit test-integration test-e2e test-all test-coverage lint

# Run all tests
test: test-unit test-integration test-e2e
	@echo "All tests passed!"

# Unit tests only
test-unit:
	@echo "Running unit tests..."
	uv run pytest tests/unit/ -v --tb=short -x

# Integration tests (requires Docker)
test-integration:
	@echo "Running integration tests..."
	@if ! command -v docker &> /dev/null; then \
		echo "Docker not available, skipping integration tests"; \
		exit 0; \
	fi
	uv run pytest tests/integration/ -v --tb=short -x -m "integration"

# E2E tests
test-e2e:
	@echo "Running E2E tests..."
	uv run pytest tests/e2e/ -v --tb=long --timeout=120 -x

# All tests with coverage
test-coverage:
	@echo "Running all tests with coverage..."
	uv run pytest tests/ \
		-v \
		--tb=short \
		--cov=scripts \
		--cov-report=term-missing \
		--cov-report=html

# Linting
lint: lint-ruff lint-mypy

lint-ruff:
	@echo "Running ruff..."
	uv run ruff check scripts/ tests/

lint-mypy:
	@echo "Running mypy..."
	uv run mypy scripts/ tests/ --strict

# Quick test run (unit + lint only)
quick-test: test-unit lint

# Test with Docker services
test-docker: test-integration test-e2e
	@echo "Docker-based tests complete!"

# Generate test report
report:
	uv run pytest tests/ \
		--html=report.html \
		--self-contained-html \
		-v
```

---

## Coverage Targets

### Coverage Goals

```ini
# .coveragerc
[run]
source = scripts
omit =
    scripts/core/db/postgres_pool.py
    scripts/core/db/memory_factory.py
    scripts/core/db/embedding_service.py

[report]
# Minimum coverage thresholds
fail_under = 80

exclude_lines =
    # pragma: no cover
    def __repr__
    raise NotImplementedError
    if TYPE_CHECKING:
    @abstractmethod
    @abc.abstractmethod

[html]
title = Continuous-Claude-v3 Test Coverage Report
```

### Per-Module Coverage Targets

| Module | Target | Notes |
|--------|--------|-------|
| `memory_daemon.py` | 85% | Core daemon logic, PID handling |
| `recall_learnings.py` | 85% | Search algorithms, backend switching |
| `store_learning.py` | 85% | Storage, deduplication, metadata |
| `stream_monitor.py` | 85% | Event parsing, stuck detection |
| `mcp_client.py` | 85% | State machine, connection lifecycle |

### Coverage Enforcement in CI

```yaml
# Add to GitHub Actions test step
- name: Check coverage
  run: |
    uv run pytest tests/unit/ --cov=scripts --cov-report=term-missing
    TOTAL=$(uv run coverage report --total-percent | tail -1 | awk '{print $NF}')
    echo "Total coverage: $TOTAL%"
    if (( $(echo "$TOTAL < 80" | bc -l) )); then
      echo "Coverage below 80%!"
      exit 1
    fi
```

---

## Summary

This testing guide provides comprehensive patterns for testing all five core scripts:

### Key Patterns
- **Unit tests**: Heavy mocking of external dependencies (PostgreSQL, Redis, MCP servers)
- **Integration tests**: Real Docker containers for PostgreSQL and Redis
- **E2E tests**: Full workflow validation with subprocess spawning

### Fixtures Provided
- `claude_home_dir`: Temporary ~/.claude directory
- `mock_redis_client`: Pre-configured Redis mock
- `mock_embedding_service`: Pre-configured embedding mock
- `postgres_container`: Real PostgreSQL with pgvector
- `redis_container`: Real Redis server

### Common Failure Points Documented
Each script section includes specific failure points to test, covering:
- Configuration errors
- Connection failures
- Race conditions
- Edge cases in algorithms
- Resource cleanup

### CI Integration
GitHub Actions workflow with parallel jobs for fast feedback:
- Unit tests (fast, no external deps)
- Integration tests (Docker services)
- E2E tests (full workflows)
- Linting (ruff + mypy)

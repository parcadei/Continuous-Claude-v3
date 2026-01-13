"""
Pytest fixtures for Continuous-Claude-v3 integration tests.

Provides fixtures for:
- Database connection (PostgreSQL with asyncpg or SQLite fallback)
- Mock git repository for wizard testing
- Temporary directories for file operations
- Environment variable isolation
"""

import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# =============================================================================
# Environment Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Isolate environment variables for each test."""
    # Save original env
    original_env = os.environ.copy()

    # Clear potentially problematic env vars
    for key in ["DATABASE_URL", "OPC_POSTGRES_URL", "AGENTICA_POSTGRES_URL", "REDIS_URL"]:
        monkeypatch.delenv(key, raising=False)

    # Set test database URL
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost:5432/test_db")
    monkeypatch.setenv("AGENTICA_ENV", "development")

    yield

    # Restore original env
    os.environ.clear()
    os.environ.update(original_env)


# =============================================================================
# Temporary Directory Fixtures
# =============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory that is cleaned up after the test."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def temp_project_dir(temp_dir: Path) -> Path:
    """Create a temporary project directory structure."""
    project_dir = temp_dir / "project"
    project_dir.mkdir()

    # Create .claude structure
    claude_dir = project_dir / ".claude"
    (claude_dir / "hooks").mkdir()
    (claude_dir / "skills").mkdir()
    (claude_dir / "rules").mkdir()
    (claude_dir / "agents").mkdir()
    (claude_dir / "servers").mkdir()

    # Create opc structure
    opc_dir = project_dir / "opc"
    (opc_dir / "scripts" / "core").mkdir(parents=True)
    (opc_dir / "scripts" / "setup").mkdir(parents=True)
    (opc_dir / "scripts" / "tldr").mkdir(parents=True)

    # Create some sample files
    (claude_dir / "hooks" / "test_hook.py").write_text("# Test hook")
    (claude_dir / "skills" / "test_skill.py").write_text("# Test skill")
    (claude_dir / "rules" / "test_rule.md").write_text("# Test rule")

    return project_dir


@pytest.fixture
def temp_claude_home(temp_dir: Path) -> Path:
    """Create a temporary ~/.claude directory."""
    claude_home = temp_dir / ".claude"
    claude_home.mkdir()

    # Create subdirectories
    (claude_home / "hooks").mkdir()
    (claude_home / "hooks" / "dist").mkdir()
    (claude_home / "skills").mkdir()
    (claude_home / "rules").mkdir()
    (claude_home / "agents").mkdir()
    (claude_home / "servers").mkdir()
    (claude_home / "scripts" / "core").mkdir(parents=True)
    (claude_home / "cache" / "symbol-index").mkdir(parents=True)

    # Create settings.json
    (claude_home / "settings.json").write_text('{"version": "3.0.0"}')

    return claude_home


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_subprocess() -> Generator[MagicMock, None, None]:
    """Mock subprocess module for testing git/docker operations."""
    mock = MagicMock()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_result.stderr = ""
    mock.run.return_value = mock_result
    mock.Popen.return_value = MagicMock(
        communicate=AsyncMock(return_value=(b"", b"")),
        returncode=0,
    )
    yield mock


@pytest.fixture
def mock_async_subprocess() -> Generator[MagicMock, None, None]:
    """Mock asyncio subprocess for async operations."""
    mock = MagicMock()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = b""
    mock_result.stderr = b""
    mock.create_subprocess_exec = AsyncMock(return_value=mock_result)
    yield mock


@pytest.fixture
def mock_git_repo(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a mock git repository."""
    repo_dir = temp_dir / "mock_repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, capture_output=True, check=True)

    # Create initial commit
    (repo_dir / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "."], cwd=repo_dir, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        capture_output=True,
        check=True,
    )
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, capture_output=True, check=True)

    return repo_dir


@pytest.fixture
def mock_typescript_hooks(temp_dir: Path) -> Path:
    """Create mock TypeScript hooks directory."""
    hooks_dir = temp_dir / "hooks"
    hooks_dir.mkdir()

    # Create package.json
    (hooks_dir / "package.json").write_text(
        '{"name": "test-hooks", "scripts": {"build": "tsc"}}'
    )

    # Create TypeScript source
    (hooks_dir / "src").mkdir()
    (hooks_dir / "src" / "test-hook.ts").write_text("export const test = () => {};")

    # Create tsconfig
    (hooks_dir / "tsconfig.json").write_text('{"compilerOptions": {"outDir": "dist"}}')

    return hooks_dir


# =============================================================================
# Sample Code Fixtures
# =============================================================================


@pytest.fixture
def sample_python_code() -> str:
    """Sample Python code for testing symbol extraction."""
    return '''
"""Sample module for testing."""

import os
from pathlib import Path


class SampleClass:
    """A sample class for testing."""

    def __init__(self, name: str):
        self.name = name

    def greet(self) -> str:
        """Return a greeting."""
        return f"Hello, {self.name}!"


def sample_function(x: int, y: int) -> int:
    """A simple function for testing."""
    return x + y


async def async_sample(value: str) -> str:
    """An async function for testing."""
    return value.upper()


CONSTANT_VALUE = 42


if __name__ == "__main__":
    obj = SampleClass("Test")
    print(obj.greet())
'''


@pytest.fixture
def sample_wizard_files(temp_dir: Path) -> Path:
    """Create sample files for wizard sync testing."""
    source_dir = temp_dir / "source"
    source_dir.mkdir()

    # Create various file types
    (source_dir / "hooks").mkdir()
    (source_dir / "hooks" / "hook1.py").write_text("# Hook 1")
    (source_dir / "hooks" / "hook2.py").write_text("# Hook 2 v2")

    (source_dir / "skills").mkdir()
    (source_dir / "skills" / "skill1.py").write_text("# Skill 1")

    (source_dir / "rules").mkdir()
    (source_dir / "rules" / "rule1.md").write_text("# Rule 1")

    return source_dir


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def postgres_pool() -> AsyncGenerator[Any, None]:
    """Create a PostgreSQL connection pool for testing.

    Skips if PostgreSQL is not available.
    """
    # Try to import asyncpg
    try:
        import asyncpg
    except ImportError:
        pytest.skip("asyncpg not installed")

    # Try to connect to test database
    connection_string = os.environ.get("DATABASE_URL", "postgresql://test:test@localhost:5432/test_db")

    try:
        pool = await asyncpg.create_pool(
            connection_string,
            min_size=1,
            max_size=2,
            command_timeout=30,
        )

        # Test connection
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")

        yield pool

        await pool.close()
    except (ConnectionRefusedError, asyncpg.PostgresConnectionError):
        pytest.skip("PostgreSQL not available")


@pytest_asyncio.fixture
async def test_schema(postgres_pool: Any) -> AsyncGenerator[None, None]:
    """Create test tables in the database."""
    async with postgres_pool.acquire() as conn:
        # Create test table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_sessions (
                id TEXT PRIMARY KEY,
                project TEXT NOT NULL,
                working_on TEXT,
                started_at TIMESTAMP DEFAULT NOW(),
                last_heartbeat TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create test archival_memory table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_archival_memory (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id TEXT NOT NULL,
                agent_id TEXT,
                content TEXT NOT NULL,
                metadata JSONB DEFAULT '{}',
                embedding vector(1024),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # Create test handoffs table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_handoffs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_name TEXT NOT NULL,
                file_path TEXT UNIQUE NOT NULL,
                format TEXT DEFAULT 'yaml',
                session_id TEXT,
                agent_id TEXT,
                goal TEXT,
                outcome TEXT CHECK(outcome IN ('SUCCEEDED','PARTIAL_PLUS','PARTIAL_MINUS','FAILED','UNKNOWN')),
                content TEXT,
                embedding VECTOR(1024),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

    yield

    # Cleanup
    async with postgres_pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS test_handoffs CASCADE")
        await conn.execute("DROP TABLE IF EXISTS test_archival_memory CASCADE")
        await conn.execute("DROP TABLE IF EXISTS test_sessions CASCADE")


@pytest.fixture
def sqlite_db_path(temp_dir: Path) -> Path:
    """Create a SQLite database for testing (fallback when PostgreSQL unavailable)."""
    db_path = temp_dir / "test.db"
    return db_path


@pytest.fixture
def sqlite_connection(sqlite_db_path: Path) -> Generator[Any, None, None]:
    """Create a SQLite connection for testing."""
    import sqlite3

    conn = sqlite3.connect(str(sqlite_db_path))
    conn.row_factory = sqlite3.Row

    yield conn

    conn.close()


@pytest.fixture
def initialized_sqlite_db(sqlite_connection: Any) -> Any:
    """Create and initialize SQLite database with schema."""
    cursor = sqlite_connection.cursor()

    # Create sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            project TEXT NOT NULL,
            working_on TEXT,
            started_at TIMESTAMP DEFAULT NOW(),
            last_heartbeat TIMESTAMP DEFAULT NOW()
        )
    """)

    # Create file_claims table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_claims (
            file_path TEXT NOT NULL,
            project TEXT NOT NULL,
            session_id TEXT,
            claimed_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (file_path, project)
        )
    """)

    sqlite_connection.commit()
    return sqlite_connection


# =============================================================================
# Health Check Fixtures
# =============================================================================


@pytest.fixture
def mock_health_check_result() -> dict:
    """Mock health check result for testing."""
    return {
        "name": "test_check",
        "status": "healthy",
        "level": "readiness",
        "message": "Test check passed",
        "details": {"key": "value"},
        "timestamp": "2024-01-01T00:00:00Z",
        "recovery_action": None,
    }


# =============================================================================
# Assertion Helpers
# =============================================================================


class Assertions:
    """Helper assertion methods for common test patterns."""

    @staticmethod
    def assert_path_exists(path: Path, message: str = "") -> None:
        """Assert that a path exists."""
        assert path.exists(), f"{message}: Path does not exist: {path}"

    @staticmethod
    def assert_path_missing(path: Path, message: str = "") -> None:
        """Assert that a path does not exist."""
        assert not path.exists(), f"{message}: Path exists when it should not: {path}"

    @staticmethod
    def assert_file_contains(file_path: Path, expected_content: str) -> None:
        """Assert that a file contains expected content."""
        assert file_path.exists(), f"File does not exist: {file_path}"
        content = file_path.read_text()
        assert expected_content in content, f"File does not contain expected content"

    @staticmethod
    def assert_json_file_equals(file_path: Path, expected: dict) -> None:
        """Assert that a JSON file equals expected content."""
        import json

        assert file_path.exists(), f"File does not exist: {file_path}"
        content = json.loads(file_path.read_text())
        assert content == expected, f"JSON content does not match expected"


@pytest.fixture
def asserts() -> type[Assertions]:
    """Provide assertion helpers."""
    return Assertions


# =============================================================================
# TLDR Installation Fixtures
# =============================================================================


@pytest.fixture
def mock_venv_bin(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a mock venv bin directory with tldr script."""
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)

    # Create a mock tldr script that outputs expected help text
    tldr_script = venv_bin / "tldr"
    tldr_script.write_text("#!/bin/bash\necho 'Token-efficient code analysis'\n")
    tldr_script.chmod(tldr_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    # Create llm-tldr as well
    llm_tldr = venv_bin / "llm-tldr"
    llm_tldr.write_text("#!/bin/bash\necho 'Token-efficient code analysis'\n")
    llm_tldr.chmod(llm_tldr.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    yield venv_bin


@pytest.fixture
def mock_tldr_executable(mock_venv_bin: Path) -> Generator[Path, None, None]:
    """Create a mock llm-tldr executable that outputs expected help text."""
    tldr_path = mock_venv_bin / "llm-tldr"
    tldr_path.write_text(
        """#!/bin/bash
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    echo "Token-efficient code analysis"
    exit 0
fi
echo "Token-efficient code analysis"
exit 0
"""
    )
    tldr_path.chmod(tldr_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return tldr_path


@pytest.fixture
def mock_usr_local_bin(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a mock /usr/local/bin directory."""
    usr_local_bin = tmp_path / "usr" / "local" / "bin"
    usr_local_bin.mkdir(parents=True)
    return usr_local_bin


@pytest.fixture
def sudo_mock() -> Generator[MagicMock, None, None]:
    """Mock sudo command."""
    mock = MagicMock()
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = b""
    mock_result.stderr = b""
    mock.run.return_value = mock_result
    yield mock

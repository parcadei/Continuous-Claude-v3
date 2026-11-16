"""Tests for SQLite busy_timeout and WAL mode configuration.

These tests verify that SQLite connections are properly configured to:
1. Set PRAGMA busy_timeout to prevent indefinite blocking
2. Enable WAL mode for better concurrent access
3. Handle concurrent writes without blocking indefinitely

Issue: STARVATION_FINDINGS.md Finding 3 - SQLite Database Lock Without Busy Timeout

The current implementation in db-utils.ts and Python scripts uses sqlite3.connect()
without configuring busy_timeout or WAL mode, causing indefinite blocks when multiple
writers contend for the database.

Expected fix:
- Add conn.execute("PRAGMA busy_timeout = 5000") after every sqlite3.connect()
- Add conn.execute("PRAGMA journal_mode = WAL") for concurrent access
- Implement retry logic for transient lock timeouts
"""

import re
import sqlite3
import tempfile
import threading
import time
from collections.abc import Generator
from pathlib import Path

import pytest


class TestBusyTimeoutConfiguration:
    """Tests for busy_timeout PRAGMA configuration."""

    @pytest.fixture
    def temp_db(self) -> Generator[Path, None, None]:
        """Create a temporary SQLite database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute(
                """
                CREATE TABLE test_data (
                    id INTEGER PRIMARY KEY,
                    value TEXT
                )
            """
            )
            conn.execute("INSERT INTO test_data (value) VALUES ('initial')")
            conn.commit()
            conn.close()
            yield db_path

    @pytest.fixture
    def hooks_src_dir(self) -> Path:
        """Path to hooks/src directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "src"

    @pytest.fixture
    def db_utils_path(self, hooks_src_dir: Path) -> Path:
        """Path to db-utils.ts."""
        return hooks_src_dir / "shared" / "db-utils.ts"

    def test_db_utils_sets_busy_timeout(self, db_utils_path: Path) -> None:
        """db-utils.ts Python scripts must set PRAGMA busy_timeout.

        The getActiveAgentCount() function contains embedded Python that
        calls sqlite3.connect(). This test verifies that busy_timeout
        is set to prevent indefinite blocking.
        """
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet")

        content = db_utils_path.read_text()

        # Check that busy_timeout PRAGMA is set in Python code
        assert "busy_timeout" in content, (
            "db-utils.ts must set PRAGMA busy_timeout in Python scripts.\n"
            "Expected: conn.execute('PRAGMA busy_timeout = 5000')\n"
            "This prevents indefinite blocking when multiple writers contend."
        )

    def test_db_utils_enables_wal_mode(self, db_utils_path: Path) -> None:
        """db-utils.ts Python scripts must enable WAL mode.

        WAL (Write-Ahead Logging) mode allows concurrent readers and
        writers, improving performance and reducing lock contention.
        """
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet")

        content = db_utils_path.read_text()

        # Check that WAL mode is enabled
        assert "journal_mode" in content and "WAL" in content, (
            "db-utils.ts must enable WAL mode in Python scripts.\n"
            "Expected: conn.execute('PRAGMA journal_mode = WAL')\n"
            "WAL mode allows concurrent readers and writers."
        )

    def test_busy_timeout_value_is_reasonable(self, db_utils_path: Path) -> None:
        """busy_timeout should be set to a reasonable value (1-10 seconds).

        Too short: causes spurious failures
        Too long: defeats the purpose of timeout
        Recommended: 5000ms (5 seconds)
        """
        if not db_utils_path.exists():
            pytest.skip("db-utils.ts doesn't exist yet")

        content = db_utils_path.read_text()

        # Look for busy_timeout setting and extract value
        match = re.search(r"busy_timeout\s*[=,]\s*(\d+)", content)
        assert match is not None, (
            "Could not find busy_timeout value in db-utils.ts.\n"
            "Expected: PRAGMA busy_timeout = 5000"
        )

        timeout_ms = int(match.group(1))
        assert 1000 <= timeout_ms <= 10000, (
            f"busy_timeout should be between 1000ms and 10000ms.\n"
            f"Got: {timeout_ms}ms\n"
            f"Recommended: 5000ms"
        )


class TestWALModeConfiguration:
    """Tests for WAL mode configuration in SQLite connections."""

    @pytest.fixture
    def scripts_dir(self) -> Path:
        """Path to scripts directory."""
        return Path(__file__).parents[2] / "scripts"

    def test_artifact_index_enables_wal_mode(self, scripts_dir: Path) -> None:
        """artifact_index.py must enable WAL mode on database connection."""
        artifact_index = scripts_dir / "artifact_index.py"
        if not artifact_index.exists():
            pytest.skip("artifact_index.py doesn't exist")

        content = artifact_index.read_text()

        assert "journal_mode" in content and "WAL" in content, (
            "artifact_index.py must enable WAL mode.\n"
            "Expected: conn.execute('PRAGMA journal_mode = WAL')\n"
            "Location: init_db() function after sqlite3.connect()"
        )

    def test_artifact_index_sets_busy_timeout(self, scripts_dir: Path) -> None:
        """artifact_index.py must set busy_timeout on database connection."""
        artifact_index = scripts_dir / "artifact_index.py"
        if not artifact_index.exists():
            pytest.skip("artifact_index.py doesn't exist")

        content = artifact_index.read_text()

        assert "busy_timeout" in content, (
            "artifact_index.py must set PRAGMA busy_timeout.\n"
            "Expected: conn.execute('PRAGMA busy_timeout = 5000')\n"
            "Location: init_db() function after sqlite3.connect()"
        )

    def test_artifact_query_sets_busy_timeout(self, scripts_dir: Path) -> None:
        """artifact_query.py must set busy_timeout on database connections."""
        artifact_query = scripts_dir / "artifact_query.py"
        if not artifact_query.exists():
            pytest.skip("artifact_query.py doesn't exist")

        content = artifact_query.read_text()

        assert "busy_timeout" in content, (
            "artifact_query.py must set PRAGMA busy_timeout.\n"
            "Expected: conn.execute('PRAGMA busy_timeout = 5000')\n"
            "Location: after each sqlite3.connect() call"
        )

    def test_artifact_mark_sets_busy_timeout(self, scripts_dir: Path) -> None:
        """artifact_mark.py must set busy_timeout on database connection."""
        artifact_mark = scripts_dir / "artifact_mark.py"
        if not artifact_mark.exists():
            pytest.skip("artifact_mark.py doesn't exist")

        content = artifact_mark.read_text()

        assert "busy_timeout" in content, (
            "artifact_mark.py must set PRAGMA busy_timeout.\n"
            "Expected: conn.execute('PRAGMA busy_timeout = 5000')\n"
            "Location: after sqlite3.connect() call"
        )

    def test_braintrust_analyze_sets_busy_timeout(self, scripts_dir: Path) -> None:
        """braintrust_analyze.py must set busy_timeout on database connection."""
        braintrust_analyze = scripts_dir / "braintrust_analyze.py"
        if not braintrust_analyze.exists():
            pytest.skip("braintrust_analyze.py doesn't exist")

        content = braintrust_analyze.read_text()

        assert "busy_timeout" in content, (
            "braintrust_analyze.py must set PRAGMA busy_timeout.\n"
            "Expected: conn.execute('PRAGMA busy_timeout = 5000')\n"
            "Location: after sqlite3.connect() call (around line 904)"
        )


class TestConcurrentWriteTimeout:
    """Tests for concurrent write behavior with busy_timeout."""

    @pytest.fixture
    def temp_db(self) -> Generator[Path, None, None]:
        """Create a temporary SQLite database with WAL mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "concurrent_test.db"
            conn = sqlite3.connect(str(db_path))
            # Enable WAL mode for better concurrency
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute(
                """
                CREATE TABLE test_data (
                    id INTEGER PRIMARY KEY,
                    value TEXT,
                    updated_at REAL
                )
            """
            )
            conn.execute(
                "INSERT INTO test_data (value, updated_at) VALUES ('initial', 0)"
            )
            conn.commit()
            conn.close()
            yield db_path

    def test_concurrent_writes_timeout_without_busy_timeout(
        self, temp_db: Path
    ) -> None:
        """Without busy_timeout, concurrent writes can block indefinitely.

        This test demonstrates the problem: when one connection holds
        a write lock, another connection blocks forever waiting.
        """
        # Connection 1: Hold a write lock
        conn1 = sqlite3.connect(str(temp_db))
        conn1.execute("BEGIN IMMEDIATE")  # Acquire write lock
        conn1.execute("UPDATE test_data SET value = 'conn1' WHERE id = 1")

        # Connection 2: Try to write (should block)
        conn2 = sqlite3.connect(str(temp_db))
        # Note: Without busy_timeout, this would block indefinitely
        # We set a short timeout to make the test pass quickly
        conn2.execute("PRAGMA busy_timeout = 100")  # 100ms timeout

        start_time = time.time()
        blocked = False
        try:
            conn2.execute("BEGIN IMMEDIATE")
            conn2.execute("UPDATE test_data SET value = 'conn2' WHERE id = 1")
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                blocked = True
        elapsed = time.time() - start_time

        # Cleanup
        conn1.rollback()
        conn1.close()
        conn2.close()

        # The write should have been blocked (and timed out)
        assert blocked, (
            "Connection 2 should have been blocked by Connection 1's write lock.\n"
            "This demonstrates why busy_timeout is needed."
        )

        # The timeout should have occurred quickly (not indefinitely)
        assert elapsed < 1.0, (
            f"Timeout occurred in {elapsed:.2f}s, expected < 1s.\n"
            "Without busy_timeout, this would block indefinitely."
        )

    def test_concurrent_writes_succeed_with_proper_timeout(
        self, temp_db: Path
    ) -> None:
        """With proper busy_timeout, concurrent writes eventually succeed.

        When one connection releases its lock within the timeout period,
        the waiting connection should acquire the lock and complete.
        """
        results: dict[str, object] = {"conn2_success": False, "error": None}

        def writer1() -> None:
            """Hold lock briefly, then commit."""
            conn = sqlite3.connect(str(temp_db))
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE test_data SET value = 'writer1' WHERE id = 1")
            time.sleep(0.5)  # Hold lock for 500ms
            conn.commit()
            conn.close()

        def writer2() -> None:
            """Wait for lock with busy_timeout."""
            time.sleep(0.1)  # Start slightly after writer1
            conn = sqlite3.connect(str(temp_db))
            conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("UPDATE test_data SET value = 'writer2' WHERE id = 1")
                conn.commit()
                results["conn2_success"] = True
            except sqlite3.OperationalError as e:
                results["error"] = str(e)
            finally:
                conn.close()

        t1 = threading.Thread(target=writer1)
        t2 = threading.Thread(target=writer2)

        start_time = time.time()
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)
        elapsed = time.time() - start_time

        assert results["conn2_success"], (
            f"Writer 2 should have succeeded after Writer 1 released lock.\n"
            f"Error: {results['error']}\n"
            f"This requires busy_timeout to be set on all connections."
        )

        # Both writers should complete within a reasonable time
        assert elapsed < 3.0, (
            f"Both writers should complete within 3s.\n"
            f"Elapsed: {elapsed:.2f}s\n"
            f"If this takes too long, busy_timeout may not be configured."
        )


class TestHookPythonScriptsTimeout:
    """Tests for busy_timeout in Python scripts embedded in TypeScript hooks."""

    @pytest.fixture
    def hooks_dist_dir(self) -> Path:
        """Path to hooks/dist directory (compiled JS)."""
        return Path(__file__).parents[2] / ".claude" / "hooks" / "dist"

    def test_all_python_scripts_have_busy_timeout(
        self, hooks_dist_dir: Path
    ) -> None:
        """All Python scripts in hooks must set busy_timeout.

        This scans all JS files in hooks/dist for embedded Python
        scripts that use sqlite3.connect() and verifies they set
        busy_timeout.
        """
        if not hooks_dist_dir.exists():
            pytest.skip("hooks/dist directory doesn't exist")

        js_files = list(hooks_dist_dir.rglob("*.js"))
        violations: list[str] = []

        for js_file in js_files:
            content = js_file.read_text()

            # Check if file contains embedded Python with sqlite3
            if "sqlite3.connect" in content:
                if "busy_timeout" not in content:
                    violations.append(str(js_file.relative_to(hooks_dist_dir)))

        assert not violations, (
            f"The following hook files contain sqlite3.connect() without busy_timeout:\n"
            f"{chr(10).join('  - ' + v for v in violations)}\n\n"
            f"Fix: Add conn.execute('PRAGMA busy_timeout = 5000') after each connect()"
        )

    def test_db_utils_js_sets_busy_timeout(self, hooks_dist_dir: Path) -> None:
        """shared/db-utils.js must set busy_timeout in embedded Python."""
        db_utils_js = hooks_dist_dir / "shared" / "db-utils.js"
        if not db_utils_js.exists():
            pytest.skip("shared/db-utils.js doesn't exist")

        content = db_utils_js.read_text()

        # The Python script in getActiveAgentCount must set busy_timeout
        assert "busy_timeout" in content, (
            "shared/db-utils.js must set PRAGMA busy_timeout in Python code.\n"
            "Location: getActiveAgentCount() function's embedded Python script.\n"
            "Expected: conn.execute('PRAGMA busy_timeout = 5000')"
        )


class TestConnectionFactoryPattern:
    """Tests for a connection factory pattern that enforces busy_timeout."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Path to project root."""
        return Path(__file__).parents[2]

    def test_connection_factory_exists(self, project_root: Path) -> None:
        """A shared connection factory should exist for consistent configuration.

        Instead of calling sqlite3.connect() directly everywhere, code
        should use a shared factory that sets busy_timeout and WAL mode.
        """
        # Look for a centralized connection function
        possible_locations = [
            project_root / "src" / "db" / "connection.py",
            project_root / "src" / "runtime" / "db.py",
            project_root / "scripts" / "agentica" / "db_utils.py",
        ]

        factory_exists = any(p.exists() for p in possible_locations)

        # This test is informational - it suggests a pattern improvement
        # but doesn't fail if the factory doesn't exist yet
        if not factory_exists:
            pytest.skip(
                "No centralized connection factory found. "
                "Consider creating one to enforce consistent configuration."
            )


class TestTimeoutErrorHandling:
    """Tests for proper error handling when busy_timeout expires."""

    @pytest.fixture
    def temp_db(self) -> Generator[Path, None, None]:
        """Create a temporary SQLite database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "timeout_test.db"
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute(
                """
                CREATE TABLE test_data (
                    id INTEGER PRIMARY KEY,
                    value TEXT
                )
            """
            )
            conn.commit()
            conn.close()
            yield db_path

    def test_timeout_raises_operational_error(self, temp_db: Path) -> None:
        """When busy_timeout expires, sqlite3.OperationalError should be raised.

        The error message should contain 'database is locked' to allow
        proper error handling and retry logic.
        """
        # Connection 1: Hold exclusive lock
        conn1 = sqlite3.connect(str(temp_db))
        conn1.execute("BEGIN EXCLUSIVE")

        # Connection 2: Try to access with short timeout
        conn2 = sqlite3.connect(str(temp_db))
        conn2.execute("PRAGMA busy_timeout = 50")  # 50ms

        error_raised = False
        error_message = ""
        try:
            conn2.execute("INSERT INTO test_data (value) VALUES ('test')")
        except sqlite3.OperationalError as e:
            error_raised = True
            error_message = str(e)
        finally:
            conn1.rollback()
            conn1.close()
            conn2.close()

        assert error_raised, (
            "sqlite3.OperationalError should be raised when busy_timeout expires."
        )
        assert "locked" in error_message.lower(), (
            f"Error message should indicate database is locked.\n"
            f"Got: {error_message}"
        )

    def test_retry_logic_after_timeout(self, temp_db: Path) -> None:
        """Code should implement retry logic when busy_timeout expires.

        This test verifies that a retry mechanism works correctly:
        1. First attempt fails due to lock
        2. Lock is released
        3. Retry succeeds
        """
        lock_holder_done = threading.Event()

        def hold_lock_briefly() -> None:
            """Hold lock for 200ms then release."""
            conn = sqlite3.connect(str(temp_db))
            conn.execute("BEGIN EXCLUSIVE")
            time.sleep(0.2)
            conn.commit()
            conn.close()
            lock_holder_done.set()

        # Start lock holder
        t = threading.Thread(target=hold_lock_briefly)
        t.start()

        # Give lock holder time to acquire lock
        time.sleep(0.05)

        # Try to write with retry logic
        conn = sqlite3.connect(str(temp_db))
        conn.execute("PRAGMA busy_timeout = 100")  # 100ms timeout per attempt

        max_retries = 5
        success = False
        attempts = 0

        for _ in range(max_retries):
            attempts += 1
            try:
                conn.execute("INSERT INTO test_data (value) VALUES ('retry_test')")
                conn.commit()
                success = True
                break
            except sqlite3.OperationalError:
                time.sleep(0.1)  # Wait before retry
                continue

        conn.close()
        t.join(timeout=5)

        assert success, (
            f"Retry logic should eventually succeed after lock is released.\n"
            f"Attempts made: {attempts}"
        )
        assert attempts > 1, (
            f"Should have required multiple attempts due to initial lock.\n"
            f"Attempts: {attempts}"
        )

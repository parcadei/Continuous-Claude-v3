"""Integration tests for PostgreSQL + pgvector Docker setup.

These tests verify Phase 1 of the Memory PostgreSQL Migration:
1. Container starts and is healthy
2. pgvector extension is installed
3. Can connect with asyncpg
4. Can create vector column

Prerequisites:
- Docker must be running
- Run: ./docker/start-postgres.sh before tests
- Or: docker compose -f docker/docker-compose.yml up -d

Usage:
    uv run pytest tests/integration/test_postgres_setup.py -v
"""

import asyncio
import subprocess

import pytest

# Will be imported after dependencies are added
# import asyncpg


@pytest.fixture(scope="module")
def docker_compose_path() -> str:
    """Path to docker-compose.yml."""
    from pathlib import Path

    return str(Path(__file__).parent.parent.parent / "docker" / "docker-compose.yml")


@pytest.fixture(scope="module")
def connection_string() -> str:
    """PostgreSQL connection string for tests."""
    return "postgresql://agentica:agentica_dev@localhost:5433/agentica_memory"


def is_container_running(container_name: str = "agentica-postgres") -> bool:
    """Check if the PostgreSQL container is running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == "true"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def is_container_healthy(container_name: str = "agentica-postgres") -> bool:
    """Check if the PostgreSQL container is healthy."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Health.Status}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == "healthy"
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.fixture(scope="module")
def ensure_postgres_running():
    """Ensure PostgreSQL container is running before tests.

    This fixture checks if the container is running and healthy.
    If not, it skips the test suite with a helpful message.
    """
    if not is_container_running():
        pytest.skip(
            "PostgreSQL container not running. "
            "Start with: ./docker/start-postgres.sh or "
            "docker compose -f docker/docker-compose.yml up -d"
        )

    # Wait for container to become healthy (max 30 seconds)
    for _ in range(30):
        if is_container_healthy():
            break
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(1))
    else:
        pytest.skip("PostgreSQL container not healthy after 30 seconds")

    yield


class TestDockerSetup:
    """Test Docker container setup for PostgreSQL + pgvector."""

    def test_container_is_running(self, ensure_postgres_running):
        """Container should be running."""
        assert is_container_running("agentica-postgres")

    def test_container_is_healthy(self, ensure_postgres_running):
        """Container should pass health check."""
        assert is_container_healthy("agentica-postgres")

    def test_postgres_port_accessible(self, ensure_postgres_running):
        """PostgreSQL port 5433 should be accessible."""
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            result = sock.connect_ex(("localhost", 5433))
            assert result == 0, "Port 5433 is not accessible"
        finally:
            sock.close()


class TestPgvectorExtension:
    """Test pgvector extension installation."""

    @pytest.mark.asyncio
    async def test_pgvector_extension_exists(
        self, ensure_postgres_running, connection_string
    ):
        """pgvector extension should be installed."""
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            row = await conn.fetchrow(
                "SELECT * FROM pg_extension WHERE extname = 'vector'"
            )
            assert row is not None, "pgvector extension not found"
            assert row["extname"] == "vector"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_can_create_vector_column(
        self, ensure_postgres_running, connection_string
    ):
        """Should be able to create a vector column."""
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            # Create a test table with vector column
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS test_vectors (
                    id SERIAL PRIMARY KEY,
                    embedding vector(4)
                )
            """)

            # Insert a test vector
            await conn.execute("""
                INSERT INTO test_vectors (embedding) VALUES ('[1,2,3,4]')
            """)

            # Query it back
            row = await conn.fetchrow(
                "SELECT embedding FROM test_vectors ORDER BY id DESC LIMIT 1"
            )
            assert row is not None
            # Vector should be returned as string in format '[1,2,3,4]'
            assert row["embedding"] is not None

            # Cleanup
            await conn.execute("DROP TABLE test_vectors")
        finally:
            await conn.close()


class TestAsyncpgConnection:
    """Test asyncpg connection and basic operations."""

    @pytest.mark.asyncio
    async def test_can_connect_with_asyncpg(
        self, ensure_postgres_running, connection_string
    ):
        """Should be able to connect with asyncpg."""
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            # Simple query to verify connection
            row = await conn.fetchrow("SELECT 1 as value")
            assert row is not None
            assert row["value"] == 1
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_can_query_pg_version(
        self, ensure_postgres_running, connection_string
    ):
        """Should be able to query PostgreSQL version."""
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            row = await conn.fetchrow("SELECT version()")
            assert row is not None
            version = row["version"]
            assert "PostgreSQL" in version
            # We expect PostgreSQL 16 from pgvector/pgvector:pg16
            assert "16" in version or "17" in version
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_database_exists(self, ensure_postgres_running, connection_string):
        """agentica_memory database should exist."""
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            row = await conn.fetchrow(
                "SELECT datname FROM pg_database WHERE datname = 'agentica_memory'"
            )
            assert row is not None
            assert row["datname"] == "agentica_memory"
        finally:
            await conn.close()


class TestSchemaCreation:
    """Test that init.sql creates expected tables."""

    @pytest.mark.asyncio
    async def test_core_memory_table_exists(
        self, ensure_postgres_running, connection_string
    ):
        """core_memory table should exist with correct schema."""
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            # Check table exists
            row = await conn.fetchrow("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'core_memory'
            """)
            assert row is not None, "core_memory table does not exist"

            # Check columns
            columns = await conn.fetch("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'core_memory'
                ORDER BY ordinal_position
            """)
            column_names = [col["column_name"] for col in columns]
            assert "id" in column_names
            assert "session_id" in column_names
            assert "key" in column_names
            assert "value" in column_names
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_archival_memory_table_exists(
        self, ensure_postgres_running, connection_string
    ):
        """archival_memory table should exist with vector column."""
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            # Check table exists
            row = await conn.fetchrow("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'archival_memory'
            """)
            assert row is not None, "archival_memory table does not exist"

            # Check embedding column exists (vector type)
            columns = await conn.fetch("""
                SELECT column_name, udt_name
                FROM information_schema.columns
                WHERE table_name = 'archival_memory'
            """)
            column_dict = {col["column_name"]: col["udt_name"] for col in columns}
            assert "embedding" in column_dict, "embedding column missing"
            assert column_dict["embedding"] == "vector", "embedding should be vector type"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_indexes_exist(self, ensure_postgres_running, connection_string):
        """Expected indexes should be created."""
        import asyncpg

        conn = await asyncpg.connect(connection_string)
        try:
            indexes = await conn.fetch("""
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public'
            """)
            index_names = [idx["indexname"] for idx in indexes]

            # Check for key indexes from init.sql
            assert "idx_core_memory_session" in index_names
            assert "idx_archival_session" in index_names
        finally:
            await conn.close()


class TestConnectionPool:
    """Test connection pool functionality (after postgres_pool.py is created)."""

    @pytest.mark.asyncio
    async def test_pool_module_importable(self, ensure_postgres_running):
        """postgres_pool module should be importable."""
        try:
            from scripts.agentica.postgres_pool import close_pool, get_pool

            assert get_pool is not None
            assert close_pool is not None
        except ImportError as e:
            pytest.fail(f"Could not import postgres_pool: {e}")

    @pytest.mark.asyncio
    async def test_pool_connection_works(self, ensure_postgres_running):
        """Pool should acquire and release connections."""
        try:
            from scripts.agentica.postgres_pool import close_pool, get_pool

            pool = await get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT 1 as value")
                assert row["value"] == 1

            await close_pool()
        except ImportError:
            pytest.skip("postgres_pool not yet implemented")

    @pytest.mark.asyncio
    async def test_pool_concurrent_connections(self, ensure_postgres_running):
        """Pool should handle multiple concurrent connections."""
        try:
            from scripts.agentica.postgres_pool import close_pool, get_pool

            pool = await get_pool()

            async def make_query(n: int) -> int:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow("SELECT $1::int as value", n)
                    return row["value"]

            # Run 5 concurrent queries
            results = await asyncio.gather(*[make_query(i) for i in range(5)])
            assert results == [0, 1, 2, 3, 4]

            await close_pool()
        except ImportError:
            pytest.skip("postgres_pool not yet implemented")

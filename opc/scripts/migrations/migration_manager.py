"""Database Migration Manager for OPC.

Manages incremental database migrations for the coordination layer.
Migrations are numbered (001, 002, etc.) and tracked in a migrations table.

USAGE:
    uv run python -m scripts.migrations.migration_manager

    # Or via updater:
    uv run python -m scripts.setup.update --migrate
"""

import asyncio
import hashlib
import re
from dataclasses import dataclass
from functools import total_ordering
from pathlib import Path
from typing import Any

# Ensure project root is in sys.path for imports
_migrations_dir = Path(__file__).resolve().parent
_project_root = _migrations_dir.parent.parent.parent
if str(_project_root) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_project_root))


@dataclass
class MigrationResult:
    """Result of applying migrations."""
    applied: list[str]
    skipped: list[str]
    failed: list[str]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "applied": self.applied,
            "skipped": self.skipped,
            "failed": self.failed,
            "error": self.error,
        }


@total_ordering
class Migration:
    """Represents a database migration file.

    Attributes:
        id: The migration number (extracted from filename prefix)
        filename: The full filename (e.g., "001_add_findings_table.sql")
        description: Human-readable description (extracted from filename)
        checksum: SHA256 checksum of the file contents for validation
    """

    # Pattern to match migration filenames like "001_add_findings_table.sql"
    FILENAME_PATTERN = re.compile(r"^(\d+)_(.+)\.sql$")

    def __init__(self, id: int, filename: str, description: str, checksum: str | None = None):
        """Initialize a Migration instance.

        Args:
            id: The migration number
            filename: The full filename
            description: Human-readable description
            checksum: Optional SHA256 checksum for validation
        """
        self.id = id
        self.filename = filename
        self.description = description
        self._checksum = checksum

    @classmethod
    def from_filename(cls, filename: str) -> "Migration":
        """Create a Migration from a filename.

        Args:
            filename: The migration filename (e.g., "001_add_findings_table.sql")

        Returns:
            A new Migration instance

        Raises:
            ValueError: If the filename doesn't match the expected pattern
        """
        match = cls.FILENAME_PATTERN.match(filename)
        if not match:
            raise ValueError(f"Invalid migration filename: {filename}")

        migration_id = int(match.group(1))
        description = match.group(2).replace("_", " ").strip()

        return cls(id=migration_id, filename=filename, description=description)

    @classmethod
    def from_path(cls, path: Path) -> "Migration":
        """Create a Migration from a file path.

        Args:
            path: Path to the migration file

        Returns:
            A new Migration instance with checksum computed from file contents
        """
        migration = cls.from_filename(path.name)
        migration._checksum = migration._compute_checksum(path)
        return migration

    def _compute_checksum(self, path: Path) -> str:
        """Compute SHA256 checksum of the migration file.

        Args:
            path: Path to the migration file

        Returns:
            Hex-encoded SHA256 checksum
        """
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()

    @property
    def checksum(self) -> str | None:
        """Get the checksum if available."""
        return self._checksum

    def validate_checksum(self, expected_checksum: str) -> bool:
        """Validate the migration against an expected checksum.

        Args:
            expected_checksum: The expected SHA256 checksum

        Returns:
            True if the checksum matches
        """
        return self._checksum == expected_checksum if self._checksum else False

    def __lt__(self, other: "Migration") -> bool:
        """Compare migrations by their ID for ordering."""
        if not isinstance(other, Migration):
            return NotImplemented
        return self.id < other.id

    def __eq__(self, other: object) -> bool:
        """Check equality based on migration ID."""
        if not isinstance(other, Migration):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        """Hash based on migration ID for use in sets/dicts."""
        return hash(self.id)

    def __repr__(self) -> str:
        """String representation of the migration."""
        return f"Migration(id={self.id}, filename={self.filename!r}, description={self.description!r})"


class MigrationManager:
    """Manages database migrations for OPC coordination layer."""

    MIGRATIONS_DIR = _migrations_dir
    MIGRATION_PATTERN = re.compile(r"^(\d+)_.*\.sql$")

    def __init__(self):
        """Initialize migration manager."""
        self.migrations_dir = Path(__file__).resolve().parent
        self._db_url: str | None = None

    @property
    def db_url(self) -> str:
        """Get database URL from environment."""
        if self._db_url is None:
            # Try multiple environment variables
            self._db_url = (
                __import__("os").environ.get("OPC_POSTGRES_URL") or
                __import__("os").environ.get("DATABASE_URL") or
                "postgresql://claude:claude_dev@localhost:5432/continuous_claude"
            )
        return self._db_url

    def get_migration_files(self) -> list[tuple[int, Path]]:
        """Get all migration files sorted by number.

        Returns:
            List of (migration_number, Path) tuples
        """
        migrations = []
        for f in self.migrations_dir.glob("*.sql"):
            match = self.MIGRATION_PATTERN.match(f.name)
            if match:
                num = int(match.group(1))
                migrations.append((num, f))

        return sorted(migrations, key=lambda x: x[0])

    async def _get_applied_migrations(self) -> set[str]:
        """Get set of already applied migration names."""
        import asyncpg

        applied = set()
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Check if migrations table exists
                result = await conn.fetch(
                    "SELECT tablename FROM pg_tables WHERE tablename = 'schema_migrations'"
                )
                if result:
                    # Check column names - adapt to existing schema
                    cols = await conn.fetch("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = 'schema_migrations'
                    """)
                    col_names = {r["column_name"] for r in cols}

                    if "script_name" in col_names:
                        # Legacy schema
                        rows = await conn.fetch("SELECT script_name FROM schema_migrations")
                        applied = {r["script_name"] for r in rows}
                    elif "migration_name" in col_names:
                        # New schema
                        rows = await conn.fetch("SELECT migration_name FROM schema_migrations")
                        applied = {r["migration_name"] for r in rows}
            finally:
                await conn.close()
        except Exception:
            # Table doesn't exist or DB not available - all migrations are pending
            pass

        return applied

    async def get_pending_migrations(self) -> list[tuple[int, Path]]:
        """Get migrations that haven't been applied yet.

        Returns:
            List of pending (migration_number, Path) tuples
        """
        applied = await self._get_applied_migrations()

        pending = []
        for num, path in self.get_migration_files():
            if path.name not in applied:
                pending.append((num, path))

        return pending

    async def _apply_migration(self, conn: Any, migration_name: str, sql: str) -> bool:
        """Apply a single migration.

        Args:
            conn: AsyncPG connection
            migration_name: Name of the migration
            sql: SQL statements to execute

        Returns:
            True if successful
        """
        try:
            # Execute the migration SQL
            await conn.execute(sql)

            # Record the migration - try new schema first, fall back to legacy
            try:
                await conn.execute(
                    "INSERT INTO schema_migrations (migration_name) VALUES ($1)",
                    migration_name
                )
            except asyncpg.UndefinedColumnError:
                # Legacy schema uses different column name
                await conn.execute(
                    "INSERT INTO schema_migrations (script_name) VALUES ($1)",
                    migration_name
                )

            return True
        except Exception as e:
            print(f"  [red]Error applying {migration_name}: {e}[/red]")
            return False

    async def apply_all(self) -> MigrationResult:
        """Apply all pending migrations.

        Returns:
            MigrationResult with applied, skipped, and failed lists
        """
        import asyncpg

        result = MigrationResult(applied=[], skipped=[], failed=[])

        pending = await self.get_pending_migrations()

        if not pending:
            return result

        print(f"  [bold]{len(pending)}[/bold] pending migration(s)")

        # Read and parse each migration file
        for num, path in pending:
            migration_name = path.name
            print(f"\n  [dim]Applying {migration_name}...[/dim]")

            try:
                sql = path.read_text()

                conn = await asyncpg.connect(self.db_url)
                try:
                    # Use READ COMMITTED isolation level to avoid transaction issues
                    # Each statement is its own transaction
                    # Execute the migration SQL
                    await conn.execute(sql)

                    # Record the migration (will fail if already recorded)
                    try:
                        await conn.execute(
                            "INSERT INTO schema_migrations (migration_name) VALUES ($1)",
                            migration_name
                        )
                    except asyncpg.UndefinedColumnError:
                        # Legacy schema
                        await conn.execute(
                            "INSERT INTO schema_migrations (script_name) VALUES ($1)",
                            migration_name
                        )
                    except asyncpg.UniqueViolationError:
                        # Already applied, skip
                        result.skipped.append(migration_name)
                        print(f"  [yellow]SKIPPED[/yellow] {migration_name} (already applied)")
                        continue

                    result.applied.append(migration_name)
                    print(f"  [green]OK[/green] {migration_name}")

                except asyncpg.SerializationError as e:
                    # Retry on serialization errors
                    result.failed.append(migration_name)
                    result.error = f"Serialization error (retry needed): {str(e)}"
                    print(f"  [red]RETRY[/red] {migration_name}: {e}")
                except Exception as e:
                    result.failed.append(migration_name)
                    result.error = str(e)
                    print(f"  [red]ERROR[/red] {migration_name}: {e}")
                finally:
                    await conn.close()

            except Exception as e:
                result.failed.append(migration_name)
                result.error = str(e)
                print(f"  [red]ERROR[/red] {migration_name}: {e}")

        return result

    def apply_all_sync(self) -> MigrationResult:
        """Synchronous wrapper for apply_all."""
        return asyncio.run(self.apply_all())


async def _async_get_pending() -> list[tuple[int, Path]]:
    """Async helper to get pending migrations."""
    manager = MigrationManager()
    return await manager.get_pending_migrations()


def get_pending_migrations() -> list[tuple[int, Path]]:
    """Get list of pending migrations."""
    return asyncio.run(_async_get_pending())


def run_migrations() -> MigrationResult:
    """Run all pending migrations."""
    manager = MigrationManager()
    return manager.apply_all_sync()


def main() -> int:
    """Main entry point."""
    from rich.console import Console

    console = Console()
    console.print("\n[bold]OPC Database Migration Manager[/bold]\n")

    manager = MigrationManager()

    # Show pending migrations
    pending = asyncio.run(manager.get_pending_migrations())

    if not pending:
        console.print("  [green]All migrations up to date[/green]")
        return 0

    console.print(f"  [bold]{len(pending)}[/bold] pending migration(s):")
    for num, path in pending:
        console.print(f"    {num:03d}. {path.name}")

    console.print("\n[dim]Applying migrations...[/dim]")

    result = manager.apply_all_sync()

    console.print("\n[bold]Results:[/bold]")
    if result.applied:
        console.print(f"  [green]Applied:[/green] {', '.join(result.applied)}")
    if result.skipped:
        console.print(f"  [yellow]Skipped:[/yellow] {', '.join(result.skipped)}")
    if result.failed:
        console.print(f"  [red]Failed:[/red] {', '.join(result.failed)}")
        if result.error:
            console.print(f"  [red]Error: {result.error}[/red]")
        return 1

    console.print("\n[green]All migrations applied successfully[/green]")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

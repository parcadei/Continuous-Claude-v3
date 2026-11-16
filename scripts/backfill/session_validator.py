"""Session validation for backfill pipeline.

Validates that a Braintrust session has sufficient data for processing.

Usage:
    from scripts.backfill.session_validator import SessionValidator, ValidationResult

    validator = SessionValidator()
    result = await validator.validate("root-span-id", min_spans=5)

    if result.is_valid:
        # Process session
        pass
    else:
        print(f"Skipping: {result.error}")
"""
from dataclasses import dataclass, field
from typing import Optional, Any
from pathlib import Path
import os

import aiosqlite


@dataclass
class ValidationResult:
    """Result of session validation."""

    is_valid: bool
    session_id: str
    span_count: int = 0
    has_tool_spans: bool = False
    has_llm_spans: bool = False
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None


class SessionValidator:
    """Validate Braintrust sessions for backfill processing.

    Checks:
    1. Session not already processed (in temporal.db)
    2. Session has minimum span count
    3. Session has expected span types (tool, llm)
    """

    def __init__(self, temporal_db_path: Optional[str] = None):
        """Initialize validator.

        Args:
            temporal_db_path: Path to temporal.db. If None, uses default location.
        """
        if temporal_db_path:
            self.temporal_db_path = Path(temporal_db_path)
        else:
            project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            self.temporal_db_path = (
                Path(project_dir) / ".claude" / "cache" / "temporal-memory" / "temporal.db"
            )

    async def validate(
        self,
        root_span_id: str,
        min_spans: int = 5
    ) -> ValidationResult:
        """Validate session readiness for processing.

        Args:
            root_span_id: The Braintrust root_span_id for the session.
            min_spans: Minimum number of spans required (default 5).

        Returns:
            ValidationResult with validation status and details.
        """
        warnings: list[str] = []

        # Step 1: Check if already processed
        try:
            if await self._check_already_processed(root_span_id):
                return ValidationResult(
                    is_valid=False,
                    session_id=root_span_id,
                    error="already_processed"
                )
        except Exception:
            # Database might not exist yet, continue
            pass

        # Step 2: Query Braintrust for session stats
        try:
            stats = await self._query_braintrust_stats(root_span_id)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                session_id=root_span_id,
                error=f"api_error: {str(e)[:100]}"
            )

        span_count = stats.get("span_count", 0)
        tool_count = stats.get("tool_count", 0)
        llm_count = stats.get("llm_count", 0)

        # Step 3: Check minimum span count
        if span_count < min_spans:
            return ValidationResult(
                is_valid=False,
                session_id=root_span_id,
                span_count=span_count,
                error="insufficient_spans"
            )

        # Step 4: Check for expected span types (warnings only)
        has_tool_spans = tool_count > 0
        has_llm_spans = llm_count > 0

        if not has_tool_spans:
            warnings.append("no_tool_spans")
        if not has_llm_spans:
            warnings.append("no_llm_spans")

        return ValidationResult(
            is_valid=True,
            session_id=root_span_id,
            span_count=span_count,
            has_tool_spans=has_tool_spans,
            has_llm_spans=has_llm_spans,
            warnings=warnings,
            error=None
        )

    async def _check_already_processed(self, session_id: str) -> bool:
        """Check if session already exists in temporal.db.

        Args:
            session_id: The session ID (root_span_id) to check.

        Returns:
            True if already processed, False otherwise.
        """
        if not self.temporal_db_path.exists():
            return False

        async with aiosqlite.connect(self.temporal_db_path) as db:
            # Check if processed_sessions table exists
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_sessions'"
            )
            if not await cursor.fetchone():
                return False

            cursor = await db.execute(
                "SELECT 1 FROM processed_sessions WHERE session_id = ?",
                (session_id,)
            )
            row = await cursor.fetchone()
            return row is not None

    async def _mark_processed(self, session_id: str) -> None:
        """Mark a session as processed in temporal.db.

        Args:
            session_id: The session ID to mark as processed.
        """
        # Ensure parent directory exists
        self.temporal_db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.temporal_db_path) as db:
            # Create table if needed
            await db.execute("""
                CREATE TABLE IF NOT EXISTS processed_sessions (
                    session_id TEXT PRIMARY KEY,
                    processed_at TEXT NOT NULL
                )
            """)
            await db.execute(
                "INSERT OR REPLACE INTO processed_sessions (session_id, processed_at) VALUES (?, datetime('now'))",
                (session_id,)
            )
            await db.commit()

    async def _query_braintrust_stats(self, session_id: str) -> dict[str, int]:
        """Query Braintrust for session statistics.

        Uses the same pattern as scripts/braintrust_analyze.py.

        Args:
            session_id: The root_span_id to query.

        Returns:
            Dict with span_count, tool_count, llm_count.
        """
        import requests

        # Load API key
        api_key = self._load_api_key()
        project_name = os.environ.get("BRAINTRUST_PROJECT", "agentica")
        project_id = self._get_project_id(project_name, api_key)

        # Query for session stats
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        # Total span count
        query = f"""
            SELECT
                COUNT(*) as span_count,
                COUNT(*) FILTER (WHERE span_attributes['type'] = 'tool') as tool_count,
                COUNT(*) FILTER (WHERE span_attributes['type'] = 'llm') as llm_count
            FROM project_logs('{project_id}')
            WHERE root_span_id = '{session_id}'
        """

        resp = requests.post(
            "https://api.braintrust.dev/btql",
            headers=headers,
            json={"query": query, "fmt": "json"},
            timeout=30
        )

        if resp.status_code != 200:
            raise Exception(f"Braintrust API error: {resp.status_code} - {resp.text[:100]}")

        data = resp.json().get("data", [])
        if not data:
            return {"span_count": 0, "tool_count": 0, "llm_count": 0}

        row = data[0]
        return {
            "span_count": int(row.get("span_count", 0) or 0),
            "tool_count": int(row.get("tool_count", 0) or 0),
            "llm_count": int(row.get("llm_count", 0) or 0),
        }

    def _load_api_key(self) -> str:
        """Load Braintrust API key from environment or .env file."""
        # Check env first
        api_key = os.environ.get("BRAINTRUST_API_KEY")
        if api_key:
            return api_key

        # Try loading from .env files
        for path in [Path.home() / ".claude", Path.cwd(), *Path.cwd().parents]:
            env_file = path / ".env"
            if env_file.exists():
                with open(env_file) as f:
                    for line in f:
                        if line.startswith("BRAINTRUST_API_KEY="):
                            key = line.strip().split("=", 1)[1].strip("\"'")
                            os.environ["BRAINTRUST_API_KEY"] = key
                            return key

        raise Exception("BRAINTRUST_API_KEY not found in environment or .env files")

    def _get_project_id(self, project_name: str, api_key: str) -> str:
        """Get Braintrust project ID from name."""
        import requests

        headers = {"Authorization": f"Bearer {api_key}"}
        resp = requests.get(
            "https://api.braintrust.dev/v1/project",
            headers=headers,
            params={"project_name": project_name},
            timeout=10
        )

        if resp.status_code == 200:
            projects: list[dict[str, Any]] = resp.json().get("objects", [])
            if projects:
                project_id: str = projects[0]["id"]
                return project_id

        # Try listing all projects and matching by name
        resp = requests.get("https://api.braintrust.dev/v1/project", headers=headers, timeout=10)
        if resp.status_code == 200:
            projects = resp.json().get("objects", [])
            for p in projects:
                if p.get("name", "").lower() == project_name.lower():
                    project_id = p["id"]
                    return project_id

        raise Exception(f"Project '{project_name}' not found")

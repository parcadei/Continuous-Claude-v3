#!/usr/bin/env python3
"""
USAGE: artifact_index.py [--handoffs] [--plans] [--continuity] [--all] [--file PATH] [--db PATH]

Index handoffs, plans, and continuity ledgers into the Context Graph database.

Examples:
    # Index all handoffs
    uv run python scripts/artifact_index.py --handoffs

    # Index everything
    uv run python scripts/artifact_index.py --all

    # Index a single handoff file (fast, for hooks)
    uv run python scripts/artifact_index.py --file thoughts/shared/handoffs/session/task-01.md

    # Use custom database path
    uv run python scripts/artifact_index.py --all --db /path/to/context.db
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import yaml
from datetime import datetime
from pathlib import Path

# Load .env files for DATABASE_URL (cross-platform)
try:
    from dotenv import load_dotenv
    # Global ~/.claude/.env
    global_env = Path.home() / ".claude" / ".env"
    if global_env.exists():
        load_dotenv(global_env)
    # Local opc/.env
    opc_env = Path(__file__).parent.parent.parent / ".env"
    if opc_env.exists():
        load_dotenv(opc_env, override=True)
except ImportError:
    pass  # dotenv not required


# =============================================================================
# DATABASE BACKEND SELECTION
# =============================================================================

def get_postgres_url() -> str | None:
    """Get PostgreSQL URL from environment variables (canonical first)."""
    return os.environ.get("CONTINUOUS_CLAUDE_DB_URL") or os.environ.get("DATABASE_URL")


def use_postgres() -> bool:
    """Check if PostgreSQL should be used as backend."""
    url = get_postgres_url()
    if not url:
        return False
    try:
        import psycopg2  # noqa: F401
        return True
    except ImportError:
        return False


# =============================================================================
# SQLITE BACKEND
# =============================================================================

def get_db_path(custom_path: str | None = None) -> Path:
    """Get SQLite database path, creating directory if needed."""
    if custom_path:
        path = Path(custom_path)
    else:
        path = Path(".claude/cache/artifact-index/context.db")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_sqlite(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite database with schema."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode = WAL")
    schema_path = Path(__file__).parent / "artifact_schema.sql"
    if schema_path.exists():
        conn.executescript(schema_path.read_text())
    return conn


# =============================================================================
# POSTGRESQL BACKEND
# =============================================================================

def pg_connect():
    """Connect to PostgreSQL."""
    import psycopg2
    return psycopg2.connect(get_postgres_url())


def init_postgres():
    """Initialize PostgreSQL connection and ensure schema exists."""
    conn = pg_connect()
    cur = conn.cursor()

    # Create handoffs table if not exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS handoffs (
            id TEXT PRIMARY KEY,
            session_name TEXT,
            task_number INTEGER,
            file_path TEXT,
            task_summary TEXT,
            what_worked TEXT,
            what_failed TEXT,
            key_decisions TEXT,
            files_modified TEXT,
            outcome TEXT DEFAULT 'UNKNOWN',
            outcome_notes TEXT,
            root_span_id TEXT,
            turn_span_id TEXT,
            session_id TEXT,
            braintrust_session_id TEXT,
            created_at TIMESTAMP,
            indexed_at TIMESTAMP DEFAULT NOW(),
            goal TEXT
        )
    """)

    # Create plans table if not exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY,
            title TEXT,
            file_path TEXT,
            overview TEXT,
            approach TEXT,
            phases TEXT,
            constraints TEXT,
            indexed_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Create continuity table if not exists
    cur.execute("""
        CREATE TABLE IF NOT EXISTS continuity (
            id TEXT PRIMARY KEY,
            session_name TEXT,
            goal TEXT,
            state_done TEXT,
            state_now TEXT,
            state_next TEXT,
            key_learnings TEXT,
            key_decisions TEXT,
            snapshot_reason TEXT,
            indexed_at TIMESTAMP DEFAULT NOW()
        )
    """)

    conn.commit()
    return conn


# =============================================================================
# UNIFIED DATABASE INTERFACE
# =============================================================================

class DatabaseConnection:
    """Unified interface for SQLite and PostgreSQL."""

    def __init__(self, use_pg: bool = False, sqlite_path: Path | None = None):
        self.use_pg = use_pg
        self.sqlite_path = sqlite_path
        self.conn = None
        self.cur = None

    def __enter__(self):
        if self.use_pg:
            self.conn = init_postgres()
            self.cur = self.conn.cursor()
        else:
            self.conn = init_sqlite(self.sqlite_path or get_db_path())
            self.cur = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()

    def execute(self, sql: str, params: tuple = ()):
        """Execute SQL with backend-appropriate placeholder conversion."""
        if self.cur is None:
            raise RuntimeError("Database connection not initialized")
        if self.use_pg:
            # Convert ? to %s for PostgreSQL
            sql = sql.replace("?", "%s")
            # Convert INSERT OR REPLACE to ON CONFLICT DO UPDATE
            if "INSERT OR REPLACE INTO" in sql:
                sql = self._convert_upsert(sql)
        self.cur.execute(sql, params)

    def _convert_upsert(self, sql: str) -> str:
        """Convert SQLite INSERT OR REPLACE to PostgreSQL ON CONFLICT."""
        # Extract table name and columns
        import re
        match = re.match(r"INSERT OR REPLACE INTO (\w+)\s*\(([^)]+)\)", sql, re.IGNORECASE)
        if not match:
            return sql

        table = match.group(1)
        columns = [c.strip() for c in match.group(2).split(",")]

        # Build ON CONFLICT clause
        non_pk_cols = [c for c in columns if c != "id"]
        update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in non_pk_cols)

        # Replace INSERT OR REPLACE with INSERT ... ON CONFLICT
        sql = sql.replace("INSERT OR REPLACE INTO", "INSERT INTO")
        sql = sql.rstrip().rstrip(";")
        sql += f" ON CONFLICT (id) DO UPDATE SET {update_clause}"

        return sql

    def commit(self):
        if self.conn:
            self.conn.commit()


def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize database with schema (legacy compatibility)."""
    return init_sqlite(db_path)


def db_execute(conn, sql: str, params: tuple = (), table_hint: str = ""):
    """Execute SQL on either SQLite or PostgreSQL connection.

    Handles the difference between SQLite (conn.execute) and
    PostgreSQL (conn.cursor().execute) interfaces.
    """
    # Check if this is a PostgreSQL connection
    is_pg = hasattr(conn, 'cursor') and not isinstance(conn, sqlite3.Connection)

    if is_pg:
        # PostgreSQL: use adapted queries for existing schema
        sql, params = _adapt_for_postgres(sql, params, table_hint)
        cur = conn.cursor()
        cur.execute(sql, params)
        cur.close()
    else:
        # SQLite: use directly
        conn.execute(sql, params)


def _adapt_for_postgres(sql: str, params: tuple, table_hint: str) -> tuple:
    """Adapt SQL and params for PostgreSQL's existing schema."""
    # Convert ? to %s
    sql = sql.replace("?", "%s")

    # Handle handoffs table - different schema in PostgreSQL
    if "INTO handoffs" in sql or table_hint == "handoffs":
        # PostgreSQL schema uses UUID id and different columns
        # Map SQLite columns to PostgreSQL columns
        sql = """
            INSERT INTO handoffs
            (id, session_name, file_path, goal, what_worked, what_failed,
             key_decisions, outcome, root_span_id, session_id)
            VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (file_path) DO UPDATE SET
                goal = EXCLUDED.goal,
                what_worked = EXCLUDED.what_worked,
                what_failed = EXCLUDED.what_failed,
                key_decisions = EXCLUDED.key_decisions,
                outcome = EXCLUDED.outcome,
                root_span_id = EXCLUDED.root_span_id,
                session_id = EXCLUDED.session_id,
                indexed_at = NOW()
        """
        # Reorder params: session_name, file_path, task_summary->goal, what_worked,
        # what_failed, key_decisions, outcome, root_span_id, session_id
        # Original order: id, session_name, task_number, file_path, task_summary,
        #                 what_worked, what_failed, key_decisions, files_modified,
        #                 outcome, root_span_id, turn_span_id, session_id,
        #                 braintrust_session_id, created_at
        if len(params) == 15:  # handoffs insert
            params = (
                params[1],   # session_name
                params[3],   # file_path
                params[4],   # task_summary -> goal
                params[5],   # what_worked
                params[6],   # what_failed
                params[7],   # key_decisions
                params[9],   # outcome
                params[10],  # root_span_id
                params[12],  # session_id
            )
        return sql, params

    # Handle plans and continuity - just convert syntax
    if "INSERT OR REPLACE INTO" in sql:
        sql = _convert_pg_upsert(sql)

    return sql, params


def _convert_pg_upsert(sql: str) -> str:
    """Convert SQLite INSERT OR REPLACE to PostgreSQL ON CONFLICT."""
    # Use DOTALL to match across newlines
    match = re.search(r"INSERT\s+OR\s+REPLACE\s+INTO\s+(\w+)\s*\(([^)]+)\)", sql, re.IGNORECASE | re.DOTALL)
    if not match:
        return sql

    columns = [c.strip() for c in match.group(2).split(",")]
    non_pk_cols = [c for c in columns if c != "id"]
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in non_pk_cols)

    # Replace with whitespace-tolerant pattern
    sql = re.sub(r"INSERT\s+OR\s+REPLACE\s+INTO", "INSERT INTO", sql, flags=re.IGNORECASE)
    sql = sql.rstrip().rstrip(";")
    sql += f" ON CONFLICT (id) DO UPDATE SET {update_clause}"
    return sql


# --- Helper functions for reduced complexity ---

def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter from markdown content.

    Returns:
        Tuple of (frontmatter_dict, remaining_content)
    """
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    frontmatter = {}
    for line in parts[1].strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip()

    return frontmatter, parts[2]


def extract_sections(content: str, level: int = 2) -> dict:
    """Extract markdown sections at the specified heading level.

    Args:
        content: Markdown content to parse
        level: Heading level (2 for ##, 3 for ###)

    Returns:
        Dict mapping normalized section names to content
    """
    if not content:
        return {}

    prefix = "#" * level + " "
    next_level_prefix = "#" * (level - 1) + " " if level > 1 else None

    sections = {}
    current_section = None
    current_content = []

    for line in content.split("\n"):
        if line.startswith(prefix):
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = line[len(prefix):].strip().lower().replace(" ", "_")
            current_content = []
        elif next_level_prefix and line.startswith(next_level_prefix):
            # End section at higher-level heading
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = None
            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    return sections


def extract_session_info(file_path: Path) -> tuple[str, str | None]:
    """Extract session name and optional UUID from handoff file path.

    Supports paths like:
    - thoughts/shared/handoffs/my-session/task-01.md
    - thoughts/shared/handoffs/my-session-550e8400/task-01.md (with UUID suffix)

    Returns:
        Tuple of (session_name, session_uuid or None)
    """
    parts = file_path.parts

    if "handoffs" not in parts:
        return "", None

    idx = parts.index("handoffs")
    if idx + 1 >= len(parts):
        return "", None

    raw_name = parts[idx + 1]

    # Check for UUID suffix: "auth-refactor-550e8400" -> "auth-refactor", "550e8400"
    uuid_match = re.match(r"^(.+)-([0-9a-f]{8})$", raw_name, re.IGNORECASE)
    if uuid_match:
        return uuid_match.group(1), uuid_match.group(2).lower()

    return raw_name, None


# Dispatch table for outcome normalization
OUTCOME_MAP = {
    "SUCCESS": "SUCCEEDED",
    "SUCCEEDED": "SUCCEEDED",
    "PARTIAL": "PARTIAL_PLUS",
    "PARTIAL_PLUS": "PARTIAL_PLUS",
    "PARTIAL_MINUS": "PARTIAL_MINUS",
    "FAILED": "FAILED",
    "FAILURE": "FAILED",
    "UNKNOWN": "UNKNOWN",
}


def normalize_outcome(status: str) -> str:
    """Normalize status string to canonical outcome value.

    Uses dispatch table for O(1) lookup instead of if/elif chains.
    """
    return OUTCOME_MAP.get(status.upper(), "UNKNOWN")


# --- End helper functions ---


def parse_handoff(file_path: Path) -> dict:
    """Parse a handoff markdown file into structured data.

    Uses helper functions for reduced complexity:
    - parse_frontmatter(): Extract YAML frontmatter
    - extract_sections(): Extract markdown sections
    - extract_session_info(): Parse session from path
    - normalize_outcome(): Map status to canonical outcome
    """
    raw_content = file_path.read_text()

    # Use helper functions for parsing
    frontmatter, content = parse_frontmatter(raw_content)

    # Extract sections at both levels and merge (h3 overrides h2)
    sections = extract_sections(content, level=2)
    subsections = extract_sections(content, level=3)
    sections.update(subsections)

    # Generate ID from file path
    file_id = hashlib.md5(str(file_path).encode()).hexdigest()[:12]

    # Use helper for session info extraction
    session_name, session_uuid = extract_session_info(file_path)

    # Extract task number
    task_match = re.search(r"task-(\d+)", file_path.stem)
    task_number = int(task_match.group(1)) if task_match else None

    # Use dispatch table for outcome normalization
    status = frontmatter.get("status", "UNKNOWN")
    outcome = normalize_outcome(status)

    return {
        "id": file_id,
        "session_name": session_name,
        "session_uuid": session_uuid,  # UUID suffix from directory name (if present)
        "task_number": task_number,
        "file_path": str(file_path),
        "task_summary": sections.get("what_was_done", sections.get("summary", ""))[:500],
        "what_worked": sections.get("what_worked", ""),
        "what_failed": sections.get("what_failed", ""),
        "key_decisions": sections.get("key_decisions", sections.get("decisions", "")),
        "files_modified": json.dumps(extract_files(sections.get("files_modified", ""))),
        "outcome": outcome,
        # Braintrust trace links
        "root_span_id": frontmatter.get("root_span_id", ""),
        "turn_span_id": frontmatter.get("turn_span_id", ""),
        "session_id": frontmatter.get("session_id", ""),
        "braintrust_session_id": frontmatter.get("braintrust_session_id", ""),
        "created_at": frontmatter.get("date", datetime.now().isoformat()),
    }


def parse_handoff_yaml(file_path: Path) -> dict:
    """Parse a handoff YAML file into structured data.

    Handles the YAML format used by newer handoff files with:
    - YAML frontmatter (session, date, status, outcome)
    - YAML body sections (done_this_session, decisions, findings, etc.)
    """
    raw_content = file_path.read_text()

    # Parse YAML with frontmatter and body
    # Use line-anchored regex to avoid splitting on '---' inside YAML content
    parts = re.split(r'^\s*---\s*$', raw_content, maxsplit=2, flags=re.MULTILINE)
    if len(parts) < 3 or parts[0].strip():
        raise ValueError("Invalid YAML handoff format - missing frontmatter")

    # Parse frontmatter (first --- block)
    frontmatter = yaml.safe_load(parts[1]) or {}

    # Parse body (everything after second ---)
    body = yaml.safe_load(parts[2]) or {}

    # Generate ID from file path
    file_id = hashlib.md5(str(file_path).encode()).hexdigest()[:12]

    # Use helper for session info extraction
    session_name, session_uuid = extract_session_info(file_path)

    # Extract task number from filename (e.g., "2026-01-20_19-37_phase-1-7-complete.yaml")
    task_match = re.search(r"phase-(\d+)-(\d+)", file_path.stem)
    task_number = None
    if task_match:
        # Combine major.minor into single number (e.g., 1.11 -> 111, 2.1 -> 201)
        # Use base 100 to prevent collisions (phase-1-11 vs phase-2-1)
        task_number = int(task_match.group(1)) * 100 + int(task_match.group(2))

    # Get outcome and normalize to canonical format
    outcome = normalize_outcome(frontmatter.get("outcome", "UNKNOWN"))

    # Build task summary from goal or done_this_session
    task_summary = body.get("goal", "")
    if not task_summary and "done_this_session" in body:
        tasks = body["done_this_session"]
        if isinstance(tasks, list) and len(tasks) > 0:
            task_summary = tasks[0].get("task", "") if isinstance(tasks[0], dict) else ""
    task_summary = task_summary[:500]

    # Extract what worked/failed
    worked_items = body.get("worked", [])
    what_worked = "\n".join(f"- {item}" for item in worked_items) if isinstance(worked_items, list) else str(worked_items)

    failed_items = body.get("failed", [])
    what_failed = "\n".join(f"- {item}" for item in failed_items) if isinstance(failed_items, list) else str(failed_items)

    # Extract decisions
    decisions = body.get("decisions", {})
    if isinstance(decisions, dict):
        key_decisions = "\n".join(f"- {k}: {v}" for k, v in decisions.items())
    elif isinstance(decisions, list):
        key_decisions = "\n".join(f"- {item}" for item in decisions)
    else:
        key_decisions = str(decisions)

    # Extract files from done_this_session and files sections
    all_files = []
    if "done_this_session" in body:
        for task in body["done_this_session"]:
            if isinstance(task, dict) and "files" in task:
                files = task["files"]
                if isinstance(files, list):
                    all_files.extend(files)

    if "files" in body:
        files_section = body["files"]
        if isinstance(files_section, dict):
            for file_list in files_section.values():
                if isinstance(file_list, list):
                    all_files.extend(file_list)

    return {
        "id": file_id,
        "session_name": session_name,
        "session_uuid": session_uuid,
        "task_number": task_number,
        "file_path": str(file_path),
        "task_summary": task_summary,
        "what_worked": what_worked,
        "what_failed": what_failed,
        "key_decisions": key_decisions,
        "files_modified": json.dumps(all_files),
        "outcome": outcome,
        # Braintrust trace links (may not be present in YAML format)
        "root_span_id": frontmatter.get("root_span_id", ""),
        "turn_span_id": frontmatter.get("turn_span_id", ""),
        "session_id": frontmatter.get("session_id", ""),
        "braintrust_session_id": frontmatter.get("braintrust_session_id", ""),
        "created_at": frontmatter.get("date", datetime.now().isoformat()),
    }


def extract_files(content: str) -> list:
    """Extract file paths from markdown content."""
    files = []
    for line in content.split("\n"):
        # Match common patterns like "- `path/to/file.py`" or "- `path/to/file.py:123`"
        # Group 1 captures path up to extension, Group 2 captures optional :line-range
        matches = re.findall(r"`([^`]+\.[a-z]+)(:[^`]*)?`", line)
        files.extend([m[0] for m in matches])  # Only take the path, not line range
        # Match **File**: format
        matches = re.findall(r"\*\*File\*\*:\s*`?([^\s`]+)`?", line)
        files.extend(matches)
    return files


def index_handoffs(conn, base_path: Path = Path("thoughts/shared/handoffs")):
    """Index all handoffs into the database."""
    if not base_path.exists():
        print(f"Handoffs directory not found: {base_path}")
        return 0

    count = 0

    # Index markdown handoffs
    for handoff_file in base_path.rglob("*.md"):
        try:
            data = parse_handoff(handoff_file)
            db_execute(
                conn,
                """
                INSERT OR REPLACE INTO handoffs
                (id, session_name, task_number, file_path, task_summary, what_worked,
                 what_failed, key_decisions, files_modified, outcome,
                 root_span_id, turn_span_id, session_id, braintrust_session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["id"],
                    data["session_name"],
                    data["task_number"],
                    data["file_path"],
                    data["task_summary"],
                    data["what_worked"],
                    data["what_failed"],
                    data["key_decisions"],
                    data["files_modified"],
                    data["outcome"],
                    data["root_span_id"],
                    data["turn_span_id"],
                    data["session_id"],
                    data["braintrust_session_id"],
                    data["created_at"],
                ),
            )
            count += 1
        except Exception as e:
            print(f"Error indexing {handoff_file}: {e}")

    # Index YAML handoffs (both .yaml and .yml extensions)
    for extension in ["*.yaml", "*.yml"]:
        for handoff_file in base_path.rglob(extension):
            try:
                data = parse_handoff_yaml(handoff_file)
                db_execute(
                    conn,
                    """
                    INSERT OR REPLACE INTO handoffs
                    (id, session_name, task_number, file_path, task_summary, what_worked,
                     what_failed, key_decisions, files_modified, outcome,
                     root_span_id, turn_span_id, session_id, braintrust_session_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["id"],
                        data["session_name"],
                        data["task_number"],
                        data["file_path"],
                        data["task_summary"],
                        data["what_worked"],
                        data["what_failed"],
                        data["key_decisions"],
                        data["files_modified"],
                        data["outcome"],
                        data["root_span_id"],
                        data["turn_span_id"],
                        data["session_id"],
                        data["braintrust_session_id"],
                        data["created_at"],
                    ),
                )
                count += 1
            except Exception as e:
                print(f"Error indexing {handoff_file}: {e}")

    conn.commit()
    print(f"Indexed {count} handoffs")
    return count


def parse_plan(file_path: Path) -> dict:
    """Parse a plan markdown file into structured data."""
    content = file_path.read_text()

    # Generate ID
    file_id = hashlib.md5(str(file_path).encode()).hexdigest()[:12]

    # Extract title from first H1
    title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
    title = title_match.group(1) if title_match else file_path.stem

    # Extract sections
    sections = {}
    current_section = None
    current_content = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = line[3:].strip().lower().replace(" ", "_")
            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    # Extract phases
    phases = []
    for key in sections:
        if key.startswith("phase_"):
            phases.append({"name": key, "content": sections[key][:500]})

    return {
        "id": file_id,
        "title": title,
        "file_path": str(file_path),
        "overview": sections.get("overview", "")[:1000],
        "approach": sections.get("implementation_approach", sections.get("approach", ""))[:1000],
        "phases": json.dumps(phases),
        "constraints": sections.get("what_we're_not_doing", sections.get("constraints", "")),
    }


def index_plans(conn, base_path: Path = Path("thoughts/shared/plans")):
    """Index all plans into the database."""
    if not base_path.exists():
        print(f"Plans directory not found: {base_path}")
        return 0

    count = 0
    for plan_file in base_path.glob("*.md"):
        try:
            data = parse_plan(plan_file)
            db_execute(
                conn,
                """
                INSERT OR REPLACE INTO plans
                (id, title, file_path, overview, approach, phases, constraints)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["id"],
                    data["title"],
                    data["file_path"],
                    data["overview"],
                    data["approach"],
                    data["phases"],
                    data["constraints"],
                ),
            )
            count += 1
        except Exception as e:
            print(f"Error indexing {plan_file}: {e}")

    conn.commit()
    print(f"Indexed {count} plans")
    return count


def parse_continuity(file_path: Path) -> dict:
    """Parse a continuity ledger into structured data."""
    content = file_path.read_text()

    # Generate ID
    file_id = hashlib.md5(str(file_path).encode()).hexdigest()[:12]

    # Extract session name from filename (CONTINUITY_CLAUDE-<session>.md)
    session_match = re.search(r"CONTINUITY_CLAUDE-(.+)\.md", file_path.name)
    session_name = session_match.group(1) if session_match else file_path.stem

    # Extract sections
    sections = {}
    current_section = None
    current_content = []

    for line in content.split("\n"):
        if line.startswith("## "):
            if current_section:
                sections[current_section] = "\n".join(current_content).strip()
            current_section = line[3:].strip().lower().replace(" ", "_")
            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(current_content).strip()

    # Parse state section
    state = sections.get("state", "")
    state_done = []
    state_now = ""
    state_next = ""

    for line in state.split("\n"):
        if "[x]" in line.lower():
            state_done.append(line.strip())
        elif "[->]" in line or "now:" in line.lower():
            state_now = line.strip()
        elif "[ ]" in line or "next:" in line.lower():
            state_next = line.strip()

    return {
        "id": file_id,
        "session_name": session_name,
        "goal": sections.get("goal", "")[:500],
        "state_done": json.dumps(state_done),
        "state_now": state_now,
        "state_next": state_next,
        "key_learnings": sections.get(
            "key_learnings", sections.get("key_learnings_(this_session)", "")
        ),
        "key_decisions": sections.get("key_decisions", ""),
        "snapshot_reason": "manual",
    }


def index_continuity(conn, base_path: Path = Path(".")):
    """Index all continuity ledgers into the database."""
    count = 0
    for ledger_file in base_path.glob("CONTINUITY_CLAUDE-*.md"):
        try:
            data = parse_continuity(ledger_file)
            db_execute(
                conn,
                """
                INSERT OR REPLACE INTO continuity
                (id, session_name, goal, state_done, state_now, state_next,
                 key_learnings, key_decisions, snapshot_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["id"],
                    data["session_name"],
                    data["goal"],
                    data["state_done"],
                    data["state_now"],
                    data["state_next"],
                    data["key_learnings"],
                    data["key_decisions"],
                    data["snapshot_reason"],
                ),
            )
            count += 1
        except Exception as e:
            print(f"Error indexing {ledger_file}: {e}")

    conn.commit()
    print(f"Indexed {count} continuity ledgers")
    return count


def index_single_file(conn, file_path: Path) -> bool:
    """Index a single file based on its location/type.

    Returns True if indexed successfully, False otherwise.
    """
    file_path = Path(file_path).resolve()

    # Determine file type based on path
    path_str = str(file_path)

    if "handoffs" in path_str and file_path.suffix == ".md":
        try:
            data = parse_handoff(file_path)
            db_execute(
                conn,
                """
                INSERT OR REPLACE INTO handoffs
                (id, session_name, task_number, file_path, task_summary, what_worked,
                 what_failed, key_decisions, files_modified, outcome,
                 root_span_id, turn_span_id, session_id, braintrust_session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["id"],
                    data["session_name"],
                    data["task_number"],
                    data["file_path"],
                    data["task_summary"],
                    data["what_worked"],
                    data["what_failed"],
                    data["key_decisions"],
                    data["files_modified"],
                    data["outcome"],
                    data["root_span_id"],
                    data["turn_span_id"],
                    data["session_id"],
                    data["braintrust_session_id"],
                    data["created_at"],
                ),
            )
            conn.commit()
            print(f"Indexed handoff: {file_path.name}")
            return True
        except Exception as e:
            print(f"Error indexing handoff {file_path}: {e}")
            return False

    elif "handoffs" in path_str and file_path.suffix in [".yaml", ".yml"]:
        try:
            data = parse_handoff_yaml(file_path)
            db_execute(
                conn,
                """
                INSERT OR REPLACE INTO handoffs
                (id, session_name, task_number, file_path, task_summary, what_worked,
                 what_failed, key_decisions, files_modified, outcome,
                 root_span_id, turn_span_id, session_id, braintrust_session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["id"],
                    data["session_name"],
                    data["task_number"],
                    data["file_path"],
                    data["task_summary"],
                    data["what_worked"],
                    data["what_failed"],
                    data["key_decisions"],
                    data["files_modified"],
                    data["outcome"],
                    data["root_span_id"],
                    data["turn_span_id"],
                    data["session_id"],
                    data["braintrust_session_id"],
                    data["created_at"],
                ),
            )
            conn.commit()
            print(f"Indexed handoff: {file_path.name}")
            return True
        except Exception as e:
            print(f"Error indexing YAML handoff {file_path}: {e}")
            return False

    elif "plans" in path_str and file_path.suffix == ".md":
        try:
            data = parse_plan(file_path)
            db_execute(
                conn,
                """
                INSERT OR REPLACE INTO plans
                (id, title, file_path, overview, approach, phases, constraints)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["id"],
                    data["title"],
                    data["file_path"],
                    data["overview"],
                    data["approach"],
                    data["phases"],
                    data["constraints"],
                ),
            )
            conn.commit()
            print(f"Indexed plan: {file_path.name}")
            return True
        except Exception as e:
            print(f"Error indexing plan {file_path}: {e}")
            return False

    elif file_path.name.startswith("CONTINUITY_CLAUDE-"):
        try:
            data = parse_continuity(file_path)
            db_execute(
                conn,
                """
                INSERT OR REPLACE INTO continuity
                (id, session_name, goal, state_done, state_now, state_next,
                 key_learnings, key_decisions, snapshot_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    data["id"],
                    data["session_name"],
                    data["goal"],
                    data["state_done"],
                    data["state_now"],
                    data["state_next"],
                    data["key_learnings"],
                    data["key_decisions"],
                    data["snapshot_reason"],
                ),
            )
            conn.commit()
            print(f"Indexed continuity: {file_path.name}")
            return True
        except Exception as e:
            print(f"Error indexing continuity {file_path}: {e}")
            return False

    else:
        print(f"Unknown file type, skipping: {file_path}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Index context graph artifacts")
    parser.add_argument("--handoffs", action="store_true", help="Index handoffs")
    parser.add_argument("--plans", action="store_true", help="Index plans")
    parser.add_argument("--continuity", action="store_true", help="Index continuity ledgers")
    parser.add_argument("--all", action="store_true", help="Index everything")
    parser.add_argument("--file", type=str, help="Index a single file (fast, for hooks)")
    parser.add_argument("--db", type=str, help="Custom database path (SQLite only)")

    args = parser.parse_args()

    # Determine backend
    using_pg = use_postgres() and not args.db  # Custom db path forces SQLite
    db_type = "PostgreSQL" if using_pg else "SQLite"

    # Handle single file indexing (fast path for hooks)
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"File not found: {file_path}")
            return 1

        if using_pg:
            conn = init_postgres()
        else:
            conn = init_sqlite(get_db_path(args.db))

        success = index_single_file(conn, file_path)
        conn.close()
        return 0 if success else 1

    if not any([args.handoffs, args.plans, args.continuity, args.all]):
        parser.print_help()
        return 0

    # Initialize connection
    if using_pg:
        conn = init_postgres()
        print(f"Using database: {db_type} ({get_postgres_url()[:30]}...)")
    else:
        db_path = get_db_path(args.db)
        conn = init_sqlite(db_path)
        print(f"Using database: {db_type} ({db_path})")

    if args.all or args.handoffs:
        index_handoffs(conn)

    if args.all or args.plans:
        index_plans(conn)

    if args.all or args.continuity:
        index_continuity(conn)

    # FTS5 operations are SQLite-specific
    if not using_pg:
        print("Rebuilding FTS5 indexes...")
        conn.execute("INSERT INTO handoffs_fts(handoffs_fts) VALUES('rebuild')")
        conn.execute("INSERT INTO plans_fts(plans_fts) VALUES('rebuild')")
        conn.execute("INSERT INTO continuity_fts(continuity_fts) VALUES('rebuild')")
        conn.execute("INSERT INTO queries_fts(queries_fts) VALUES('rebuild')")

        # Configure BM25 column weights
        conn.execute(
            "INSERT OR REPLACE INTO handoffs_fts(handoffs_fts, rank) "
            "VALUES('rank', 'bm25(10.0, 5.0, 3.0, 3.0, 1.0)')"
        )
        conn.execute(
            "INSERT OR REPLACE INTO plans_fts(plans_fts, rank) "
            "VALUES('rank', 'bm25(10.0, 5.0, 3.0, 3.0, 1.0)')"
        )

        print("Optimizing indexes...")
        conn.execute("INSERT INTO handoffs_fts(handoffs_fts) VALUES('optimize')")
        conn.execute("INSERT INTO plans_fts(plans_fts) VALUES('optimize')")
        conn.execute("INSERT INTO continuity_fts(continuity_fts) VALUES('optimize')")
        conn.execute("INSERT INTO queries_fts(queries_fts) VALUES('optimize')")

    conn.commit()
    conn.close()
    print("Done!")


if __name__ == "__main__":
    main()

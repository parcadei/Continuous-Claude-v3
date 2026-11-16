# Module: Session & State Management

## Overview

Rigg provides git-style session branching, deep git integration, and robust state management. Sessions are stored in PostgreSQL (full features) with SQLite fallback (limited features). State snapshots enable undo/revert at message granularity.

---

## Session Branching

### Git-Style Model

Sessions use git-like branching semantics (not real-time collaboration):

```
main-session
    │
    ├── feature/auth-experiment (branched at message 15)
    │       │
    │       └── fix/token-refresh (branched at message 8)
    │
    └── refactor/cleanup (branched at message 22)
```

### PostgreSQL Schema

```sql
-- Session management
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_session_id UUID REFERENCES sessions(id),
    branch_name TEXT NOT NULL,  -- User-friendly name
    git_commit_hash TEXT,       -- Link to git state at branch point
    git_branch TEXT,            -- Current git branch
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'merged')),
    merged_into UUID REFERENCES sessions(id),

    -- Workspace context
    workspace_path TEXT NOT NULL,
    repos JSONB DEFAULT '[]'::jsonb,  -- Multi-repo support

    -- Metadata
    owner TEXT,
    description TEXT,
    tags JSONB DEFAULT '[]'::jsonb
);

CREATE INDEX idx_sessions_parent ON sessions(parent_session_id);
CREATE INDEX idx_sessions_branch ON sessions(branch_name);
CREATE INDEX idx_sessions_git ON sessions(git_commit_hash);
CREATE INDEX idx_sessions_status ON sessions(status);

-- Session ancestry for efficient tree traversal
CREATE TABLE session_ancestry (
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    ancestor_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    depth INTEGER NOT NULL,
    PRIMARY KEY (session_id, ancestor_id)
);

CREATE INDEX idx_ancestry_session ON session_ancestry(session_id);
CREATE INDEX idx_ancestry_depth ON session_ancestry(depth);
```

### Branching Operations

```python
# scripts/session_manager.py
from dataclasses import dataclass
from typing import Optional
import asyncpg

@dataclass
class Session:
    id: str
    parent_session_id: Optional[str]
    branch_name: str
    git_commit_hash: Optional[str]
    git_branch: Optional[str]
    workspace_path: str
    repos: list[str]

async def branch_session(
    pool: asyncpg.Pool,
    parent_id: str,
    branch_name: str,
    description: str = "",
) -> Session:
    """Create a new session branch from parent."""

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Get parent session
            parent = await conn.fetchrow(
                "SELECT * FROM sessions WHERE id = $1",
                parent_id
            )

            # Capture current git state
            git_hash = await capture_git_state(parent['workspace_path'])
            git_branch = await get_current_git_branch(parent['workspace_path'])

            # Create new session
            session = await conn.fetchrow("""
                INSERT INTO sessions (
                    parent_session_id, branch_name, git_commit_hash,
                    git_branch, workspace_path, repos, description
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING *
            """, parent_id, branch_name, git_hash, git_branch,
                parent['workspace_path'], parent['repos'], description)

            # Build ancestry chain
            await conn.execute("""
                INSERT INTO session_ancestry (session_id, ancestor_id, depth)
                SELECT $1, ancestor_id, depth + 1
                FROM session_ancestry
                WHERE session_id = $2
                UNION ALL
                SELECT $1, $2, 1
            """, session['id'], parent_id)

            return Session(**session)

async def list_branches(
    pool: asyncpg.Pool,
    session_id: str,
) -> list[Session]:
    """List all child branches of a session."""
    rows = await pool.fetch("""
        SELECT * FROM sessions
        WHERE parent_session_id = $1
        ORDER BY created_at DESC
    """, session_id)
    return [Session(**row) for row in rows]
```

---

## Git Integration

### Deep Integration Model

Every session maintains a tight link to git state:

| Event | Git Action | Rationale |
|-------|------------|-----------|
| Branch session | Record commit hash | Link session to code state |
| Message complete | Auto-commit (optional) | Undo via git revert |
| Agent edits file | Stage changes | Track WIP |
| Session merge | Git merge | Combine branches |

### Auto-Commit Configuration

```python
# scripts/git_integration.py
from enum import Enum
import subprocess

class GitCommitMode(Enum):
    DISABLED = "disabled"           # No auto-commits
    ON_MESSAGE = "on_message"       # Commit after each message
    ON_MILESTONE = "on_milestone"   # Commit at user-defined points
    ON_BRANCH = "on_branch"         # Commit when branching

GIT_CONFIG = {
    "commit_mode": GitCommitMode.ON_MESSAGE,
    "commit_message_template": "[rigg] {session_branch}: {summary}",
    "branch_prefix": "rigg/",
    "auto_push": False,  # Never auto-push without user consent
}

async def auto_commit_after_message(
    session: Session,
    message_summary: str,
) -> str | None:
    """Create auto-commit after message completion."""
    if GIT_CONFIG["commit_mode"] != GitCommitMode.ON_MESSAGE:
        return None

    # Check for staged changes
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=session.workspace_path,
        capture_output=True
    )

    if result.returncode == 0:
        return None  # No staged changes

    # Create commit
    commit_msg = GIT_CONFIG["commit_message_template"].format(
        session_branch=session.branch_name,
        summary=message_summary[:50]
    )

    result = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=session.workspace_path,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        # Get commit hash
        hash_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=session.workspace_path,
            capture_output=True,
            text=True
        )
        return hash_result.stdout.strip()

    return None
```

### Branch Per Session (Optional)

```python
async def create_git_branch_for_session(
    session: Session,
) -> str:
    """Create a dedicated git branch for this session."""
    branch_name = f"{GIT_CONFIG['branch_prefix']}{session.branch_name}"

    subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=session.workspace_path,
        check=True
    )

    # Update session record
    await update_session_git_branch(session.id, branch_name)

    return branch_name
```

---

## Team Mode

### Local-First, Git-Style Merge

Team mode follows git semantics (not real-time OT):

```
Alice (local)                Bob (local)
    │                            │
    ├── Makes edits              ├── Makes edits
    │                            │
    ├── Commits                  ├── Commits
    │                            │
    └── Pushes ──────────────────┼── Pull + Merge/Rebase
                                 │
                                 └── Pushes
```

### Merge Operations

```python
async def merge_sessions(
    pool: asyncpg.Pool,
    source_id: str,
    target_id: str,
    strategy: str = "three-way",
) -> dict:
    """Merge source session into target."""

    source = await get_session(pool, source_id)
    target = await get_session(pool, target_id)

    # Find common ancestor
    ancestor = await find_common_ancestor(pool, source_id, target_id)

    if strategy == "three-way":
        # Attempt git merge
        result = subprocess.run(
            ["git", "merge", source.git_branch, "--no-commit"],
            cwd=target.workspace_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            # Conflict detected
            conflicts = parse_merge_conflicts(result.stderr)
            return {
                "status": "conflict",
                "conflicts": conflicts,
                "instructions": "Resolve conflicts and run merge_complete()"
            }

    elif strategy == "accept-theirs":
        subprocess.run(
            ["git", "merge", "-X", "theirs", source.git_branch],
            cwd=target.workspace_path,
            check=True
        )

    elif strategy == "accept-ours":
        subprocess.run(
            ["git", "merge", "-X", "ours", source.git_branch],
            cwd=target.workspace_path,
            check=True
        )

    # Update session metadata
    await pool.execute("""
        UPDATE sessions
        SET status = 'merged', merged_into = $2, updated_at = NOW()
        WHERE id = $1
    """, source_id, target_id)

    return {"status": "merged", "commit": await get_current_commit(target.workspace_path)}
```

---

## State Storage

### PostgreSQL (Full Features)

Required for:
- Session branching
- Team collaboration
- Full state snapshots
- Cross-repo references
- Query capabilities

```sql
-- State snapshots for undo/revert
CREATE TABLE state_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_index INTEGER NOT NULL,
    git_commit_hash TEXT NOT NULL,

    -- Snapshot data
    ledger_content TEXT,           -- Continuity ledger at this point
    working_set JSONB,             -- Files being worked on
    todo_state JSONB,              -- TodoWrite state

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    snapshot_type TEXT DEFAULT 'message' CHECK (snapshot_type IN ('message', 'milestone', 'manual')),
    description TEXT,

    UNIQUE(session_id, message_index)
);

CREATE INDEX idx_snapshots_session ON state_snapshots(session_id, message_index DESC);
CREATE INDEX idx_snapshots_git ON state_snapshots(git_commit_hash);

-- Efficient snapshot lookup
CREATE TABLE snapshot_files (
    snapshot_id UUID REFERENCES state_snapshots(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,  -- SHA256 of file content
    PRIMARY KEY (snapshot_id, file_path)
);
```

### SQLite Lite Mode

Fallback for users without Docker:

| Feature | PostgreSQL | SQLite |
|---------|------------|--------|
| Session branching | Full tree | Linear only |
| Team mode | Yes | No |
| Snapshots per message | Yes | Every 10 messages |
| Multi-repo | Yes | Single repo |
| Query speed | Fast | Adequate |
| State persistence | Durable | File-based |

```python
# scripts/state_storage.py
import sqlite3
from pathlib import Path

class SQLiteLiteMode:
    """Limited feature set for SQLite fallback."""

    def __init__(self, db_path: Path):
        self.conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                branch_name TEXT NOT NULL,
                git_commit_hash TEXT,
                workspace_path TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS state_snapshots (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                message_index INTEGER NOT NULL,
                git_commit_hash TEXT NOT NULL,
                ledger_content TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, message_index)
            );
        """)

    def snapshot(self, session_id: str, message_index: int) -> str | None:
        """Create snapshot every 10 messages in lite mode."""
        if message_index % 10 != 0:
            return None

        # Create snapshot
        snapshot_id = generate_uuid()
        git_hash = capture_git_state_sync()
        ledger = read_ledger_sync()

        self.conn.execute("""
            INSERT INTO state_snapshots (id, session_id, message_index, git_commit_hash, ledger_content)
            VALUES (?, ?, ?, ?, ?)
        """, (snapshot_id, session_id, message_index, git_hash, ledger))
        self.conn.commit()

        return snapshot_id
```

---

## Disconnect Handling

### Auto-Save Strategy

State is saved immediately, not on interval:

```python
# scripts/disconnect_handler.py
import signal
import atexit

class DisconnectHandler:
    """Handle unexpected disconnects gracefully."""

    def __init__(self, session: Session, pool: asyncpg.Pool):
        self.session = session
        self.pool = pool
        self._register_handlers()

    def _register_handlers(self):
        # Register for multiple signals
        signal.signal(signal.SIGTERM, self._save_and_exit)
        signal.signal(signal.SIGINT, self._save_and_exit)
        signal.signal(signal.SIGHUP, self._save_and_exit)
        atexit.register(self._save_state_sync)

    async def _save_state(self):
        """Save current state immediately."""
        await self.pool.execute("""
            UPDATE sessions
            SET updated_at = NOW()
            WHERE id = $1
        """, self.session.id)

        # Capture git state
        git_hash = await capture_git_state(self.session.workspace_path)

        # Create emergency snapshot
        await self.pool.execute("""
            INSERT INTO state_snapshots (session_id, message_index, git_commit_hash, snapshot_type)
            VALUES ($1, -1, $2, 'disconnect')
            ON CONFLICT (session_id, message_index) DO UPDATE
            SET git_commit_hash = $2, created_at = NOW()
        """, self.session.id, git_hash)

    def _save_and_exit(self, signum, frame):
        """Signal handler - save and exit."""
        asyncio.run(self._save_state())
        sys.exit(0)

    def _save_state_sync(self):
        """Synchronous save for atexit."""
        asyncio.run(self._save_state())

async def resume_session(
    pool: asyncpg.Pool,
    session_id: str,
) -> dict:
    """Resume from last known state."""

    # Get latest snapshot
    snapshot = await pool.fetchrow("""
        SELECT * FROM state_snapshots
        WHERE session_id = $1
        ORDER BY created_at DESC
        LIMIT 1
    """, session_id)

    if snapshot:
        # Restore git state
        await restore_git_state(snapshot['git_commit_hash'])

        return {
            "resumed_at": snapshot['message_index'],
            "git_state": snapshot['git_commit_hash'],
            "snapshot_type": snapshot['snapshot_type'],
        }

    return {"resumed_at": 0, "git_state": None, "snapshot_type": None}
```

---

## Workspaces

### Multi-Repo Support

Sessions can span multiple repositories:

```sql
-- Repository tracking
CREATE TABLE session_repos (
    session_id UUID REFERENCES sessions(id) ON DELETE CASCADE,
    repo_path TEXT NOT NULL,
    repo_alias TEXT NOT NULL,  -- Short name for cross-references
    git_remote TEXT,
    default_branch TEXT DEFAULT 'main',
    PRIMARY KEY (session_id, repo_path)
);

CREATE INDEX idx_session_repos ON session_repos(session_id);

-- Cross-repo file references
CREATE TABLE cross_repo_refs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    source_repo TEXT NOT NULL,
    source_file TEXT NOT NULL,
    target_repo TEXT NOT NULL,
    target_file TEXT NOT NULL,
    ref_type TEXT NOT NULL CHECK (ref_type IN ('import', 'reference', 'copy')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Workspace Operations

```python
@dataclass
class Workspace:
    session_id: str
    repos: list[dict]  # [{path, alias, remote}]
    active_repo: str | None

async def add_repo_to_workspace(
    pool: asyncpg.Pool,
    session_id: str,
    repo_path: str,
    alias: str,
) -> None:
    """Add a repository to the session workspace."""

    # Detect git remote
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    remote = result.stdout.strip() if result.returncode == 0 else None

    await pool.execute("""
        INSERT INTO session_repos (session_id, repo_path, repo_alias, git_remote)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (session_id, repo_path) DO UPDATE
        SET repo_alias = $3, git_remote = $4
    """, session_id, repo_path, alias, remote)

    # Update session repos JSONB
    await pool.execute("""
        UPDATE sessions
        SET repos = repos || $2::jsonb
        WHERE id = $1
    """, session_id, json.dumps([{"path": repo_path, "alias": alias}]))

async def get_cross_repo_context(
    pool: asyncpg.Pool,
    session_id: str,
    file_path: str,
) -> list[dict]:
    """Get files in other repos that reference this file."""
    return await pool.fetch("""
        SELECT * FROM cross_repo_refs
        WHERE session_id = $1
        AND (source_file = $2 OR target_file = $2)
    """, session_id, file_path)
```

---

## Session Modes

### Auto-Detection via Tool Patterns

| Mode | Trigger Tools | Description |
|------|--------------|-------------|
| **Research** | WebSearch, Grep, Read (majority) | Exploration, learning |
| **Work/Build** | Write, Edit, Bash (high frequency) | Implementation |
| **Debug** | Read, Grep (error patterns), Bash (test runs) | Issue investigation |
| **Review** | Read (diff patterns), no Write | Code review |

### Detection Logic

```python
# scripts/mode_detector.py
from collections import Counter
from enum import Enum

class SessionMode(Enum):
    RESEARCH = "research"
    WORK = "work"
    DEBUG = "debug"
    REVIEW = "review"

TOOL_MODE_WEIGHTS = {
    "WebSearch": {"research": 3},
    "WebFetch": {"research": 2},
    "Grep": {"research": 1, "debug": 2},
    "Read": {"research": 1, "review": 2, "debug": 1},
    "Write": {"work": 3},
    "Edit": {"work": 3},
    "MultiEdit": {"work": 3},
    "Bash": {"work": 2, "debug": 2},
}

ERROR_PATTERNS = ["error", "fail", "bug", "issue", "fix", "debug", "trace"]

def detect_mode(tool_history: list[dict]) -> SessionMode:
    """Detect session mode from tool usage patterns."""

    if len(tool_history) < 5:
        return SessionMode.WORK  # Default

    # Count tool types
    mode_scores = Counter()

    for tool_call in tool_history[-20:]:  # Last 20 tools
        tool_name = tool_call.get("tool_name", "")
        weights = TOOL_MODE_WEIGHTS.get(tool_name, {})

        for mode, weight in weights.items():
            mode_scores[mode] += weight

        # Check for error patterns in tool inputs
        tool_input = str(tool_call.get("tool_input", "")).lower()
        if any(pattern in tool_input for pattern in ERROR_PATTERNS):
            mode_scores["debug"] += 2

    if not mode_scores:
        return SessionMode.WORK

    top_mode = mode_scores.most_common(1)[0][0]
    return SessionMode(top_mode)

class ModeOverride:
    """Allow manual mode override."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def set_mode(self, session_id: str, mode: SessionMode) -> None:
        """Manually set session mode."""
        await self.pool.execute("""
            INSERT INTO session_mode_overrides (session_id, mode, set_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (session_id) DO UPDATE
            SET mode = $2, set_at = NOW()
        """, session_id, mode.value)

    async def get_effective_mode(
        self,
        session_id: str,
        tool_history: list[dict],
    ) -> tuple[SessionMode, bool]:
        """Get mode with override check."""

        override = await self.pool.fetchrow("""
            SELECT mode, set_at FROM session_mode_overrides
            WHERE session_id = $1
            AND set_at > NOW() - INTERVAL '1 hour'  -- Expire after 1 hour
        """, session_id)

        if override:
            return SessionMode(override['mode']), True  # is_override=True

        return detect_mode(tool_history), False
```

### Debug Mode

Debug mode can be triggered manually and provides enhanced diagnostics:

```python
async def enter_debug_mode(
    pool: asyncpg.Pool,
    session_id: str,
    error_context: str,
) -> dict:
    """Enter debug mode with error analysis."""

    # Set mode override
    await ModeOverride(pool).set_mode(session_id, SessionMode.DEBUG)

    # Gather recent context
    recent_tools = await pool.fetch("""
        SELECT tool_name, tool_input, tool_output
        FROM tool_calls
        WHERE session_id = $1
        ORDER BY created_at DESC
        LIMIT 50
    """, session_id)

    # Spawn debug agent
    debug_prompt = f"""
    Debug Mode Activated.

    Error Context:
    {error_context}

    Recent Tool Calls:
    {format_tool_history(recent_tools)}

    Analyze the error and suggest fixes.
    """

    return {
        "mode": "debug",
        "context_gathered": len(recent_tools),
        "prompt": debug_prompt,
    }
```

---

## Snapshot & Undo

### Message-Level Undo

```python
async def undo_to_message(
    pool: asyncpg.Pool,
    session_id: str,
    target_message_index: int,
) -> dict:
    """Undo session state to a specific message."""

    # Get snapshot at or before target
    snapshot = await pool.fetchrow("""
        SELECT * FROM state_snapshots
        WHERE session_id = $1 AND message_index <= $2
        ORDER BY message_index DESC
        LIMIT 1
    """, session_id, target_message_index)

    if not snapshot:
        return {"error": "No snapshot found before target message"}

    # Restore git state
    subprocess.run(
        ["git", "checkout", snapshot['git_commit_hash']],
        check=True
    )

    # Restore ledger
    if snapshot['ledger_content']:
        write_ledger(snapshot['ledger_content'])

    # Restore TodoWrite state
    if snapshot['todo_state']:
        restore_todo_state(snapshot['todo_state'])

    # Mark later snapshots as undone
    await pool.execute("""
        DELETE FROM state_snapshots
        WHERE session_id = $1 AND message_index > $2
    """, session_id, target_message_index)

    return {
        "restored_to": snapshot['message_index'],
        "git_commit": snapshot['git_commit_hash'],
    }
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/session_manager.py` | Session CRUD, branching, merge |
| `scripts/git_integration.py` | Auto-commit, branch per session |
| `scripts/state_storage.py` | PostgreSQL/SQLite storage |
| `scripts/disconnect_handler.py` | Auto-save on disconnect |
| `scripts/mode_detector.py` | Session mode detection |
| `scripts/workspace_manager.py` | Multi-repo workspace |
| `docker/init-sessions.sql` | Session schema |

## Files to Modify

| File | Changes |
|------|---------|
| `docker/docker-compose.yml` | Add session tables to PostgreSQL |
| `.claude/settings.json` | Add session hooks |
| `.claude/hooks/src/session-start-continuity.ts` | Add mode detection |

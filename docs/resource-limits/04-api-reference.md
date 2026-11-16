# API Reference

This document provides comprehensive API documentation for developers extending the resource limits and orphan detection system.

---

## TypeScript APIs

### resource-utils.ts

Provides system resource querying using the Node.js `os` module.

**Location:** `.claude/hooks/src/shared/resource-utils.ts`

#### `SystemResources` Interface

```typescript
interface SystemResources {
  /** Free RAM in bytes */
  freeRAM: number;
  /** Total RAM in bytes */
  totalRAM: number;
  /** Number of CPU cores */
  cpuCores: number;
  /** Load averages for 1, 5, and 15 minutes */
  loadAvg: number[];
}
```

#### `getSystemResources(): SystemResources`

Returns current system resource information by querying the OS.

**Returns:** `SystemResources` object with current values.

**Implementation:**
- `freeRAM`: Uses `os.freemem()`
- `totalRAM`: Uses `os.totalmem()`
- `cpuCores`: Uses `os.cpus().length`
- `loadAvg`: Uses `os.loadavg()` (1m, 5m, 15m averages)

**Example:**
```typescript
import { getSystemResources } from './shared/resource-utils.js';

const resources = getSystemResources();
console.log(`Free RAM: ${resources.freeRAM / 1024 / 1024} MB`);
console.log(`CPU Cores: ${resources.cpuCores}`);
console.log(`Load Average (1m): ${resources.loadAvg[0]}`);
```

---

### resource-reader.ts

Reads resource state from JSON files written by the status monitoring script.

**Location:** `.claude/hooks/src/shared/resource-reader.ts`

#### `ResourceState` Interface

```typescript
interface ResourceState {
  /** Free RAM in MB */
  freeMemMB: number;
  /** Number of currently running agents */
  activeAgents: number;
  /** Maximum agents allowed based on available RAM */
  maxAgents: number;
  /** Current context usage percentage (0-100) */
  contextPct: number;
}
```

#### `DEFAULT_RESOURCE_STATE` Constant

```typescript
const DEFAULT_RESOURCE_STATE: ResourceState = {
  freeMemMB: 4096,   // 4GB reasonable minimum
  activeAgents: 0,    // Assume none running
  maxAgents: 10,      // Reasonable default limit
  contextPct: 0,      // Assume fresh context
};
```

Used as fallback when the resource state file is missing or corrupt.

#### `getSessionId(): string`

Get the session ID from environment variables.

**Priority:**
1. `CLAUDE_SESSION_ID` (if set by Claude Code)
2. `process.ppid` or `process.pid` (as fallback)

**Returns:** Session ID string.

**Example:**
```typescript
import { getSessionId } from './shared/resource-reader.js';

const sessionId = getSessionId();
// Returns "abc123" if CLAUDE_SESSION_ID="abc123"
// Returns "12345" if falling back to PPID
```

#### `getResourceFilePath(sessionId: string): string`

Get the path to the resource state JSON file for a session.

**Parameters:**
- `sessionId` - Session ID to use in the filename

**Returns:** Path string `/tmp/claude-resources-{sessionId}.json`

**Example:**
```typescript
import { getResourceFilePath } from './shared/resource-reader.js';

const path = getResourceFilePath('abc123');
// Returns: "/tmp/claude-resources-abc123.json"
```

#### `readResourceState(): ResourceState | null`

Read resource state from the JSON file.

**Returns:**
- `ResourceState` object if file exists and is valid JSON
- `null` if file doesn't exist or contains invalid JSON

Missing fields are filled with defaults from `DEFAULT_RESOURCE_STATE`.

**Example:**
```typescript
import { readResourceState } from './shared/resource-reader.js';

const state = readResourceState();
if (state && state.activeAgents >= state.maxAgents) {
  console.log('Agent limit reached!');
}

// Handle missing file
if (state === null) {
  console.log('No resource state available');
}
```

---

### db-utils.ts

Database utilities for querying the coordination SQLite database.

**Location:** `.claude/hooks/src/shared/db-utils.ts`

#### `QueryResult` Interface

```typescript
interface QueryResult {
  success: boolean;
  stdout: string;
  stderr: string;
}
```

#### `getDbPath(): string`

Get the absolute path to the coordination database.

**Environment Variables:**
- Uses `CLAUDE_PROJECT_DIR` if set
- Falls back to `process.cwd()`

**Returns:** Path to `.claude/cache/agentica-coordination/coordination.db`

**Example:**
```typescript
import { getDbPath } from './shared/db-utils.js';

const dbPath = getDbPath();
// Returns: "/path/to/project/.claude/cache/agentica-coordination/coordination.db"
```

#### `queryDb(pythonQuery: string, args: string[]): string`

Execute a Python query against the coordination database.

**Parameters:**
- `pythonQuery` - Python code to execute (receives args via `sys.argv`)
- `args` - Arguments passed to Python (`sys.argv[1]`, `sys.argv[2]`, ...)

**Returns:** stdout from Python subprocess (trimmed).

**Throws:** `Error` if Python subprocess fails.

**Security:** Uses `spawnSync` with argument array to prevent command injection.

**Example:**
```typescript
import { queryDb } from './shared/db-utils.js';

const count = queryDb(`
import sqlite3
import sys
conn = sqlite3.connect(sys.argv[1])
print(conn.execute("SELECT COUNT(*) FROM agents").fetchone()[0])
`, ['/path/to/db.sqlite']);
```

#### `runPythonQuery(script: string, args: string[]): QueryResult`

Execute a Python query with structured result (non-throwing).

**Parameters:**
- `script` - Python code to execute (receives args via `sys.argv`)
- `args` - Arguments passed to Python

**Returns:** `QueryResult` object with `success`, `stdout`, and `stderr`.

Unlike `queryDb()`, this function does not throw on error.

**Example:**
```typescript
import { runPythonQuery } from './shared/db-utils.js';

const result = runPythonQuery('print("hello")', []);
if (result.success) {
  console.log(result.stdout); // "hello"
} else {
  console.error(result.stderr);
}
```

#### `getActiveAgentCount(): number`

Get the count of active (running) agents across all sessions.

**Returns:** Number of agents with `status='running'`, or `0` on any error.

Returns `0` if:
- Database doesn't exist
- Database query fails
- `agents` table doesn't exist

**Example:**
```typescript
import { getActiveAgentCount } from './shared/db-utils.js';

const count = getActiveAgentCount();
if (count >= 10) {
  console.log('Too many agents running');
}
```

---

### pattern-router.ts

Pattern detection and ID validation utilities.

**Location:** `.claude/hooks/src/shared/pattern-router.ts`

#### `SUPPORTED_PATTERNS` Constant

```typescript
const SUPPORTED_PATTERNS = [
  'swarm',
  'jury',
  'pipeline',
  'generator_critic',
  'hierarchical',
  'map_reduce',
  'blackboard',
  'circuit_breaker',
  'chain_of_responsibility',
  'adversarial',
  'event_driven',
] as const;
```

#### `PatternType` Type

```typescript
type PatternType = (typeof SUPPORTED_PATTERNS)[number];
```

Union type of all supported pattern strings.

#### `detectPattern(): string | null`

Detect the current pattern type from the `PATTERN_TYPE` environment variable.

**Returns:** Pattern name string or `null` if not set/empty.

**Example:**
```typescript
import { detectPattern } from './shared/pattern-router.js';

// When PATTERN_TYPE=swarm
detectPattern(); // returns 'swarm'

// When PATTERN_TYPE is not set
detectPattern(); // returns null
```

#### `SAFE_ID_PATTERN` Constant

```typescript
const SAFE_ID_PATTERN = /^[a-zA-Z0-9_-]{1,64}$/;
```

Regex for validating IDs. Prevents:
- Path traversal (`../`)
- Command injection (`$(command)`, `` `command` ``)
- SQL injection (`'; DROP TABLE`)

**Examples:**
```typescript
SAFE_ID_PATTERN.test('abc123');        // true
SAFE_ID_PATTERN.test('agent-001');     // true
SAFE_ID_PATTERN.test('swarm_coord');   // true
SAFE_ID_PATTERN.test('../etc/passwd'); // false
SAFE_ID_PATTERN.test('$(whoami)');     // false
```

#### `isValidId(id: string): boolean`

Validate an ID against the safe pattern.

**Parameters:**
- `id` - The ID to validate

**Returns:** `true` if the ID is safe, `false` otherwise.

---

### types.ts

Shared type definitions for Claude Code hooks.

**Location:** `.claude/hooks/src/shared/types.ts`

#### Hook Input Types

```typescript
interface SubagentStartInput {
  session_id: string;
  agent_id?: string | null;
  agent_type?: string;
}

interface SubagentStopInput {
  session_id: string;
  agent_id?: string | null;
  agent_type?: string;
}

interface PreToolUseInput {
  session_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

interface PostToolUseInput {
  session_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_response: unknown;
}

interface StopInput {
  session_id: string;
  stop_hook_active?: boolean;
}
```

#### Hook Output Types

```typescript
interface HookOutput {
  result: 'continue' | 'block';
  message?: string;
  reason?: string;
}
```

---

## Python APIs

### coordination.py

SQLite-backed coordination database for multi-agent observability.

**Location:** `scripts/agentica/coordination.py`

#### Data Classes

##### `OrphanCandidate`

```python
@dataclass
class OrphanCandidate:
    """Candidate orphan agent for cleanup."""
    agent_id: str
    ppid: int | None
    parent_agent_id: str | None
    spawned_at: datetime
    tier: int          # 1=Unix orphan, 2=parent dead, 3=app orphan
    reason: str
```

**Tier Descriptions:**
| Tier | Condition | Action |
|------|-----------|--------|
| 1 | `ppid == 1` (true Unix orphan) | Kill immediately |
| 2 | Parent agent status != 'running' | Kill after 30min grace |
| 3 | Running > 24h without completion | Kill after timeout |

##### `AgentRecord`

```python
@dataclass
class AgentRecord:
    """Record of a spawned agent."""
    id: str
    session_id: str
    premise: str | None
    model: str | None
    scope_keys: list[str]
    pattern: str | None
    parent_agent_id: str | None
    pid: int | None
    ppid: int | None
    spawned_at: datetime
    completed_at: datetime | None
    status: str            # 'running', 'completed', 'failed', 'killed'
    error_message: str | None
```

##### `TaskRecord`

```python
@dataclass
class TaskRecord:
    """Record of a completed task."""
    id: str
    agent_id: str
    pattern: str | None
    input_summary: str
    output_summary: str
    output_type: str
    artifacts: dict[str, Any]
    duration_ms: int
    completed_at: datetime
```

##### `BroadcastRecord`

```python
@dataclass
class BroadcastRecord:
    """Record of a broadcast message in a swarm."""
    id: str
    swarm_id: str
    sender_agent: str
    broadcast_type: BroadcastType
    payload: dict[str, Any]
    created_at: datetime
```

##### `BroadcastType` Enum

```python
class BroadcastType(str, Enum):
    """Type of broadcast message for swarm coordination."""
    FINDING = "finding"      # Discovered something useful
    QUESTION = "question"    # Asking other agents
    BLOCKER = "blocker"      # Stuck, need help
    DONE = "done"            # Agent completed its work
    ABORT = "abort"          # Critical failure, abort swarm
```

#### `CoordinationDB` Class

```python
class CoordinationDB:
    """SQLite database for agent coordination tracking.

    Thread-safe via new connection per operation.
    Suitable for multi-agent concurrent access.
    """
```

##### Constructor

```python
def __init__(
    self,
    db_path: Path | None = None,
    session_id: str | None = None
)
```

**Parameters:**
- `db_path` - Optional custom database path (default: project cache)
- `session_id` - Session identifier for agent isolation (default: generated UUID)

**Example:**
```python
from scripts.agentica.coordination import CoordinationDB

# Default path and generated session ID
db = CoordinationDB()

# Custom session ID
db = CoordinationDB(session_id="my-session")

# Custom path
db = CoordinationDB(db_path=Path("/tmp/test.db"))
```

##### `register_agent()`

```python
def register_agent(
    self,
    agent_id: str,
    premise: str | None = None,
    model: str | None = None,
    scope_keys: list[str] | None = None,
    pattern: str | None = None,
    parent_agent_id: str | None = None,
    pid: int | None = None,
    ppid: int | None = None,
) -> AgentRecord
```

Register a spawned agent in the database.

**Example:**
```python
record = db.register_agent(
    agent_id="agent-001",
    pattern="swarm",
    premise="Research assistant",
    pid=os.getpid(),
    ppid=os.getppid(),
)
```

##### `complete_agent()`

```python
def complete_agent(
    self,
    agent_id: str,
    status: str = "completed",
    error_message: str | None = None,
) -> None
```

Mark an agent as completed or failed.

**Example:**
```python
# Mark as completed
db.complete_agent("agent-001", status="completed")

# Mark as failed with error
db.complete_agent("agent-001", status="failed", error_message="Timeout")

# Mark as killed (by orphan cleanup)
db.complete_agent("agent-001", status="killed", error_message="Orphan cleanup")
```

##### `record_task()`

```python
def record_task(
    self,
    agent_id: str,
    input_text: str,
    output: Any,
    duration_ms: int,
    pattern: str | None = None,
    artifacts: dict[str, Any] | None = None,
) -> TaskRecord
```

Record a completed task with optional artifacts.

**Example:**
```python
task = db.record_task(
    agent_id="agent-001",
    input_text="Analyze this code",
    output={"findings": ["bug1", "bug2"]},
    duration_ms=1500,
    pattern="swarm",
    artifacts={"report": "analysis.md"},
)
```

##### `get_running_agents()`

```python
def get_running_agents(
    self,
    pattern: str | None = None
) -> list[AgentRecord]
```

Get all running agents in the current session, optionally filtered by pattern.

##### `get_all_running_agents()`

```python
def get_all_running_agents(
    self,
    pattern: str | None = None
) -> list[AgentRecord]
```

Get all running agents across ALL sessions, optionally filtered by pattern.

##### `get_global_running_count()`

```python
def get_global_running_count(self) -> int
```

Count ALL running agents across all sessions.

##### `find_orphans()` / `get_orphan_candidates()`

```python
def find_orphans(self) -> list[OrphanCandidate]
```

Find potential orphan agents using three-tier detection.

**Tier Detection Logic:**

| Tier | Query Criteria | Grace Period |
|------|----------------|--------------|
| 1 | `ppid = 1` | None (immediate) |
| 2 | Parent agent `status != 'running'` | 30 minutes |
| 3 | Running > 24h with `parent_agent_id` set | 24 hours |

**Safety:** Excludes main sessions (`parent_agent_id IS NULL AND ppid != 1`) to prevent accidentally killing the orchestrator.

**Example:**
```python
orphans = db.find_orphans()
for orphan in orphans:
    print(f"Tier {orphan.tier}: {orphan.agent_id} - {orphan.reason}")
```

##### `create_broadcast()`

```python
def create_broadcast(
    self,
    swarm_id: str,
    sender_agent: str,
    broadcast_type: BroadcastType,
    payload: dict[str, Any],
) -> BroadcastRecord
```

Create a broadcast message for swarm coordination.

##### `get_broadcasts()`

```python
def get_broadcasts(
    self,
    swarm_id: str,
    since: datetime | None = None,
    exclude_sender: str | None = None,
    broadcast_types: list[BroadcastType] | None = None,
) -> list[BroadcastRecord]
```

Get broadcasts for a swarm with optional filters.

---

### watch_agents.py

Real-time agent monitoring with subprocess tracking.

**Location:** `scripts/agentica/watch_agents.py`

#### `is_unix_orphan(pid: int) -> bool`

Check if a process is a Unix orphan (ppid == 1).

**Parameters:**
- `pid` - The process ID to check

**Returns:**
- `True` if process exists and parent is init/launchd (PID 1)
- `False` if process doesn't exist, has a living parent, or on error

**Example:**
```python
from scripts.agentica.watch_agents import is_unix_orphan

if is_unix_orphan(12345):
    print("Process 12345 is an orphan")
```

#### `find_claude_processes() -> list[dict[str, Any]]`

Find running Claude CLI processes.

**Returns:** List of dicts with:
- `pid: int` - Process ID
- `parent_pid: int` - Parent process ID
- `elapsed: str` - Elapsed time string
- `command: str` - Command line (truncated to 80 chars)

#### `get_process_tree(parent_pid: int) -> list[dict[str, Any]]`

Get all child processes of a given PID (recursive).

**Parameters:**
- `parent_pid` - The parent process ID to find children for

**Returns:** List of child process dicts with `pid`, `parent_pid`, `command`, and `depth`.

#### `DirectoryWatcher` Class

```python
class DirectoryWatcher:
    """Watch a directory for file changes."""

    def __init__(self, directory: str)
    def get_changes(self) -> list[dict[str, Any]]
```

Returns changes with:
- `type: str` - "created", "modified", or "deleted"
- `path: str` - File path
- `timestamp: float` - Unix timestamp

#### `SubprocessMonitor` Class

```python
class SubprocessMonitor:
    """Unified subprocess and file system monitor."""

    def __init__(self, watch_dirs: list[str] | None = None)
    def take_snapshot(self) -> None
    def get_diff_since_snapshot(self) -> dict[str, Any]
    def get_status(self) -> dict[str, Any]
```

**`get_status()` Returns:**
```python
{
    "claude_processes": [...],  # From find_claude_processes()
    "file_changes": [...],      # Accumulated changes
    "timestamp": "...",         # ISO timestamp
    "watched_dirs": [...]       # Directories being watched
}
```

---

### cleanup_orphans.py

Orphan agent cleanup with three-tier detection.

**Location:** `scripts/agentica/cleanup_orphans.py`

#### `kill_process(pid: int) -> bool`

Attempt to kill a process with SIGTERM.

**Parameters:**
- `pid` - Process ID to kill

**Returns:**
- `True` if signal was sent successfully
- `False` if process doesn't exist or permission denied

#### `cleanup_orphans()`

```python
def cleanup_orphans(
    db: CoordinationDB | None = None,
    dry_run: bool = True,
    tier_filter: int | None = None,
) -> list[OrphanCandidate]
```

Find and optionally kill orphaned agent processes.

**Parameters:**
- `db` - CoordinationDB instance (uses default if None)
- `dry_run` - If True, only report orphans without killing
- `tier_filter` - If set, only process orphans of this tier (1, 2, or 3)

**Returns:** List of `OrphanCandidate` objects that were processed.

**Example:**
```python
from scripts.agentica.cleanup_orphans import cleanup_orphans
from scripts.agentica.coordination import CoordinationDB

db = CoordinationDB()

# Dry run - just report
orphans = cleanup_orphans(db=db, dry_run=True)

# Actually kill tier 1 orphans only
killed = cleanup_orphans(db=db, dry_run=False, tier_filter=1)
```

---

## CLI Tools

### watch_agents.py

```
usage: watch_agents.py [-h] [--watch] [--completed] [--summary] [--pattern PATTERN]
                       [--session SESSION] [--all-sessions] [--monitor]
                       [--watch-dir WATCH_DIR] [--logs] [--logs-dir LOGS_DIR]
                       [--orphans] [--json]

Watch running Agentica agents

options:
  -h, --help            show this help message and exit
  --watch, -w           Watch in real-time
  --completed, -c       Show completed tasks
  --summary, -s         Show session summary
  --pattern PATTERN, -p PATTERN
                        Filter by pattern
  --session SESSION     Session ID
  --all-sessions, -a    Show agents from all sessions
  --monitor, -m         Enable subprocess monitoring
  --watch-dir WATCH_DIR
                        Directory to watch for file changes
  --logs, -l            Enable log tailing for agent messages
  --logs-dir LOGS_DIR   Directory containing agent log files
  --orphans, -o         Show orphan candidates
  --json, -j            Output in JSON format
```

**Examples:**

```bash
# Watch agents in real-time
uv run python scripts/agentica/watch_agents.py --watch

# Show agents from all sessions
uv run python scripts/agentica/watch_agents.py --all-sessions

# Show orphan candidates as JSON
uv run python scripts/agentica/watch_agents.py --orphans --json

# Filter by pattern with subprocess monitoring
uv run python scripts/agentica/watch_agents.py --pattern swarm --monitor
```

### cleanup_orphans.py

```
usage: cleanup_orphans.py [-h] [--dry-run] [--kill] [--tier {1,2,3}] [--session SESSION]

Clean up orphaned agents using three-tier detection

options:
  -h, --help         show this help message and exit
  --dry-run          Report orphans without killing (default: True)
  --kill             Actually kill orphan processes (disables --dry-run)
  --tier {1,2,3}     Only process orphans of this tier
  --session SESSION  Session ID to use for the coordination database
```

**Examples:**

```bash
# Dry run - see what would be cleaned
uv run python scripts/agentica/cleanup_orphans.py --dry-run

# Kill only tier 1 (true Unix orphans)
uv run python scripts/agentica/cleanup_orphans.py --kill --tier 1

# Kill all orphans
uv run python scripts/agentica/cleanup_orphans.py --kill
```

---

## Database Schema

The coordination database uses SQLite with the following schema:

### `agents` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PRIMARY KEY | Unique agent identifier |
| `session_id` | TEXT NOT NULL | Session for isolation |
| `premise` | TEXT | Agent's system prompt |
| `model` | TEXT | Model name |
| `scope_keys` | TEXT | JSON array of scope function names |
| `pattern` | TEXT | Coordination pattern |
| `parent_agent_id` | TEXT | Parent agent (for hierarchical) |
| `pid` | INTEGER | Process ID for orphan detection |
| `ppid` | INTEGER | Parent process ID |
| `spawned_at` | TEXT NOT NULL | ISO timestamp |
| `completed_at` | TEXT | ISO timestamp |
| `status` | TEXT DEFAULT 'running' | running/completed/failed/killed |
| `error_message` | TEXT | Error details if failed |

### `completed_tasks` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PRIMARY KEY | Unique task identifier |
| `agent_id` | TEXT NOT NULL | Foreign key to agents |
| `pattern` | TEXT | Coordination pattern |
| `input_summary` | TEXT | Truncated input (max 500 chars) |
| `output_summary` | TEXT | Truncated output (max 500 chars) |
| `output_type` | TEXT | Python type name |
| `artifacts` | TEXT | JSON dict of artifacts |
| `duration_ms` | INTEGER | Execution time |
| `completed_at` | TEXT NOT NULL | ISO timestamp |

### `broadcasts` Table

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PRIMARY KEY | Unique broadcast identifier |
| `swarm_id` | TEXT NOT NULL | Swarm identifier |
| `sender_agent` | TEXT NOT NULL | Sending agent ID |
| `broadcast_type` | TEXT NOT NULL | finding/question/blocker/done/abort |
| `payload` | TEXT NOT NULL | JSON serialized data |
| `created_at` | TEXT NOT NULL | ISO timestamp |

### Indexes

```sql
CREATE INDEX idx_agents_session ON agents(session_id);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_pattern ON agents(pattern);
CREATE INDEX idx_tasks_agent ON completed_tasks(agent_id);
CREATE INDEX idx_broadcasts_swarm ON broadcasts(swarm_id, created_at);
```

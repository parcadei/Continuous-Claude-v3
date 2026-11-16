---
root_span_id: f728943a-4c7a-40b7-aec7-b27be4282d16
turn_span_id: 8e088335-9715-4e54-b9c2-1009b7a2917a
session_id: f728943a-4c7a-40b7-aec7-b27be4282d16
---

# Code Map: Dynamic Resource Limits Implementation

## Overview

This codebase implements a pattern-aware multi-agent orchestration system using Claude Code hooks. The architecture supports 11 orchestration patterns (swarm, jury, pipeline, etc.) with coordination via SQLite database, status line communication via /tmp files, and subprocess management for agent tracking.

Key infrastructure:
- **TypeScript hooks** in `.claude/hooks/src/` with shell wrappers in `.claude/hooks/`
- **Python coordination** in `scripts/agentica/` for database and process management
- **Status line script** in `.claude/scripts/status.sh` for cross-hook state communication

---

## Hook Architecture

### Hook Registration (`.claude/settings.json`)

```json
{
  "statusLine": { "command": "$HOME/.claude/scripts/status.sh" },
  "hooks": {
    "PreToolUse": [{ "command": ".../.claude/hooks/pre-tool-use.sh" }],
    "PostToolUse": [
      { "command": ".../.claude/hooks/post-tool-use.sh" },
      { "matcher": "Task", "command": ".../post-task-complete.sh" },
      { "matcher": "Edit|Write", "command": ".../typescript-preflight.sh" }
    ],
    "UserPromptSubmit": [{ "command": ".../skill-activation-prompt.sh" }],
    "Stop": [{ "command": ".../stop-coordinator.sh" }],
    "SubagentStart": [{ "command": ".../subagent-start.sh" }],
    "SubagentStop": [{ "command": ".../subagent-stop.sh" }],
    "SessionStart": [{ "matcher": "resume|compact|clear", "command": "..." }],
    "SessionEnd": [{ "command": ".../session-end-cleanup-swarms.sh" }]
  }
}
```

### Shell Wrapper Pattern

All shell wrappers follow this pattern (delegate to TypeScript via `npx tsx`):

```bash
#!/bin/bash
set -e
cd "$CLAUDE_PROJECT_DIR/.claude/hooks"
cat | npx tsx src/<handler>.ts
```

### Hook Input/Output Types

**File:** `.claude/hooks/src/shared/types.ts`

```typescript
// Input types (piped via stdin as JSON)
interface PreToolUseInput {
  session_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

interface SubagentStartInput {
  session_id: string;
  agent_id?: string | null;
  agent_type?: string;
}

interface StopInput {
  session_id: string;
  stop_hook_active?: boolean;  // Prevents infinite loops
}

// Output type (printed to stdout as JSON)
interface HookOutput {
  result: 'continue' | 'block';
  message?: string;  // Injected into context
  reason?: string;   // For block reason
}
```

---

## Key Files for Implementation

### 1. PreToolUse Router

**Path:** `.claude/hooks/src/pre-tool-use.ts`

**Purpose:** Routes PreToolUse events to pattern-specific handlers based on `PATTERN_TYPE` env var.

**Key Functions:**
```typescript
// Main router
async function main(): Promise<void>
  - Reads JSON from stdin
  - Calls detectPattern() to get current pattern
  - Routes to pattern handler (handleSwarm, handleJury, etc.)
  - Outputs JSON { result, message? }

// Pattern handlers
async function handleSwarm(input: PreToolUseInput): Promise<HookOutput>
async function handleJury(input: PreToolUseInput): Promise<HookOutput>
async function handlePipeline(input: PreToolUseInput): Promise<HookOutput>
```

**Dependencies:**
- `./shared/pattern-router.js` - detectPattern(), isValidId()
- `./shared/db-utils.js` - getDbPath(), runPythonQuery()
- `./patterns/swarm.js` - onPreToolUse()
- (other pattern modules)

### 2. Stop Coordinator Router

**Path:** `.claude/hooks/src/stop-coordinator.ts`

**Purpose:** Handles Stop hook events - can BLOCK coordinator until agents complete.

**Key Functions:**
```typescript
async function onStop(input: StopInput): Promise<HookOutput>
  - Checks stop_hook_active to prevent infinite loops
  - Routes to pattern-specific stop handler
  - Can return { result: 'block', message: '...' } to prevent stop

// Pattern-specific
async function handleJuryStop(input: StopInput): Promise<HookOutput>
async function handlePipelineStop(input: StopInput): Promise<HookOutput>
```

### 3. SubagentStart Router

**Path:** `.claude/hooks/src/subagent-start.ts`

**Purpose:** Handles agent startup - injects context for pattern isolation.

**Key Functions:**
```typescript
async function main(): Promise<void>
  - Routes to pattern handler
  - For jury: injects isolation context
  - For pipeline: injects stage context
```

### 4. SubagentStop Router

**Path:** `.claude/hooks/src/subagent-stop.ts`

**Purpose:** Handles agent completion - broadcasts "done" messages, tracks completion.

**Key Functions:**
```typescript
function handleSwarm(input: SubagentStopInput): HookOutput
function handleJury(input: SubagentStopInput): HookOutput
function handlePipeline(input: SubagentStopInput): HookOutput
```

### 5. Skill Activation Prompt

**Path:** `.claude/hooks/src/skill-activation-prompt.ts`

**Purpose:** UserPromptSubmit hook that:
1. Matches prompts to skill rules
2. Injects skill activation suggestions
3. **Reads context % from /tmp file and injects warnings**

**Key Functions:**
```typescript
async function main(): Promise<void>
  - Loads skill-rules.json
  - Matches prompt keywords/patterns
  - Reads context file from /tmp/claude-context-pct-{sessionId}.txt
  - Injects tiered warnings (70%, 80%, 90%)
```

**Cross-hook Communication:**
```typescript
// Reads context % written by status.sh
const sessionId = process.env.CLAUDE_SESSION_ID || process.env.CLAUDE_PPID || 'default';
const contextFile = `/tmp/claude-context-pct-${sessionId}.txt`;
const pct = parseInt(readFileSync(contextFile, 'utf-8').trim(), 10);
```

### 6. Pattern Router (Shared)

**Path:** `.claude/hooks/src/shared/pattern-router.ts`

**Purpose:** Pattern detection and ID validation.

**Key Exports:**
```typescript
const SUPPORTED_PATTERNS = [
  'swarm', 'jury', 'pipeline', 'generator_critic',
  'hierarchical', 'map_reduce', 'blackboard',
  'circuit_breaker', 'chain_of_responsibility',
  'adversarial', 'event_driven'
] as const;

function detectPattern(): string | null
  - Returns process.env.PATTERN_TYPE or null

const SAFE_ID_PATTERN = /^[a-zA-Z0-9_-]{1,64}$/;

function isValidId(id: string): boolean
  - Validates IDs to prevent injection
```

### 7. Database Utilities (Shared)

**Path:** `.claude/hooks/src/shared/db-utils.ts`

**Purpose:** SQLite database access via Python subprocess.

**Key Exports:**
```typescript
function getDbPath(): string
  - Returns: ${CLAUDE_PROJECT_DIR}/.claude/cache/agentica-coordination/coordination.db

function runPythonQuery(script: string, args: string[]): QueryResult
  - Executes Python with spawnSync
  - Returns { success: boolean, stdout: string, stderr: string }
```

### 8. Swarm Pattern Module

**Path:** `.claude/hooks/src/patterns/swarm.ts`

**Purpose:** Unified swarm coordination handlers.

**Key Exports:**
```typescript
async function onSubagentStart(input: SubagentStartInput): Promise<HookOutput>
  - Logs agent joining swarm

async function onSubagentStop(input: SubagentStopInput): Promise<HookOutput>
  - Broadcasts "done" message
  - Returns synthesis message when all complete

async function onPreToolUse(input: PreToolUseInput): Promise<HookOutput>
  - Injects broadcasts from other agents into context

async function onPostToolUse(input: PostToolUseInput): Promise<HookOutput>
  - Records "started" broadcast when Task spawns agent

async function onStop(input: StopInput): Promise<HookOutput>
  - BLOCKS coordinator until all agents done
  - Returns { result: 'block', message: 'Waiting for N agent(s)...' }
```

---

## Status Line Integration

### Status Line Script

**Path:** `.claude/scripts/status.sh`

**Purpose:** Generates status line and writes context % for other hooks.

**Key Behavior:**
```bash
# Calculate context usage
input_tokens=$(jq '.context_window.current_usage.input_tokens')
cache_read=$(jq '.context_window.current_usage.cache_read_input_tokens')
cache_creation=$(jq '.context_window.current_usage.cache_creation_input_tokens')
system_overhead=45000
total_tokens=$((input_tokens + cache_read + cache_creation + system_overhead))
context_pct=$((total_tokens * 100 / context_size))

# Write for hooks (per-session to avoid multi-instance conflicts)
session_id="${CLAUDE_SESSION_ID:-$PPID}"
echo "$context_pct" > "/tmp/claude-context-pct-${session_id}.txt"

# Output status line with color-coded context
if [[ "$context_pct" -ge 80 ]]; then
    ctx_display="\033[31m... ${context_pct}%\033[0m"  # Red warning
elif [[ "$context_pct" -ge 60 ]]; then
    ctx_display="\033[33m... ${context_pct}%\033[0m"  # Yellow
else
    ctx_display="\033[32m... ${context_pct}%\033[0m"  # Green
fi
```

**Cross-Hook Communication Pattern:**
1. StatusLine runs on every render (high frequency)
2. Writes context % to `/tmp/claude-context-pct-{sessionId}.txt`
3. UserPromptSubmit hook reads this file
4. Hook injects tiered warnings based on context %

---

## Coordination Database Schema

**Path:** `scripts/agentica/coordination.py`

**Database Location:** `.claude/cache/agentica-coordination/coordination.db`

### Tables

```sql
-- Running and completed agents
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    premise TEXT,
    model TEXT,
    scope_keys TEXT,       -- JSON array
    pattern TEXT,          -- swarm, hierarchical, jury, etc.
    parent_agent_id TEXT,  -- For hierarchical patterns
    spawned_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT DEFAULT 'running',  -- running, completed, failed
    error_message TEXT
);

-- Task completion records
CREATE TABLE completed_tasks (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    pattern TEXT,
    input_summary TEXT,    -- Truncated input
    output_summary TEXT,   -- Truncated output
    output_type TEXT,
    artifacts TEXT,        -- JSON dict
    duration_ms INTEGER,
    completed_at TEXT NOT NULL,
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

-- Swarm broadcast messages
CREATE TABLE broadcasts (
    id TEXT PRIMARY KEY,
    swarm_id TEXT NOT NULL,
    sender_agent TEXT NOT NULL,
    broadcast_type TEXT NOT NULL,  -- finding, question, blocker, done, abort
    payload TEXT NOT NULL,         -- JSON
    created_at TEXT NOT NULL
);

-- Indexes for performance
CREATE INDEX idx_agents_session ON agents(session_id);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_pattern ON agents(pattern);
CREATE INDEX idx_broadcasts_swarm ON broadcasts(swarm_id, created_at);
```

### Key Queries Used by Hooks

```sql
-- Count done vs total agents in swarm (for Stop blocking)
SELECT COUNT(DISTINCT sender_agent) as done_count
FROM broadcasts
WHERE swarm_id = ? AND broadcast_type = 'done';

SELECT COUNT(DISTINCT sender_agent) as total_count
FROM broadcasts WHERE swarm_id = ?;

-- Get broadcasts for context injection
SELECT sender_agent, broadcast_type, payload, created_at
FROM broadcasts
WHERE swarm_id = ? AND sender_agent != ?
ORDER BY created_at DESC LIMIT 10;
```

---

## Process Management

### watch_agents.py

**Path:** `scripts/agentica/watch_agents.py`

**Purpose:** Real-time monitoring of running agents with subprocess tracking.

**Key Classes:**
```python
class SubprocessMonitor:
    """Tracks Claude CLI processes and file changes."""

    def __init__(self, watch_dirs: list[str] | None = None):
        self.watch_dirs = watch_dirs or []
        self._watchers = [DirectoryWatcher(d) for d in self.watch_dirs]

    def get_status(self) -> dict[str, Any]:
        """Returns claude_processes, file_changes, timestamp, watched_dirs"""

def find_claude_processes() -> list[dict[str, Any]]:
    """Find running claude CLI processes via ps command.
    Returns: [{ pid, parent_pid, elapsed, command }]
    """
    # Uses: ps -eo pid,ppid,etime,command
    # Filters for: "claude" in command and "-p" in command

def get_process_tree(parent_pid: int) -> list[dict[str, Any]]:
    """Get all child processes recursively via pgrep."""

class DirectoryWatcher:
    """Watch directory for file changes (created/modified/deleted)."""

    def get_changes(self) -> list[dict[str, Any]]:
        """Returns changes since last check."""
```

**CLI Usage:**
```bash
uv run python scripts/agentica/watch_agents.py --watch          # Real-time table
uv run python scripts/agentica/watch_agents.py --monitor       # + subprocess tracking
uv run python scripts/agentica/watch_agents.py --all-sessions  # Cross-session view
uv run python scripts/agentica/watch_agents.py --pattern swarm # Filter by pattern
```

### tracked_agent.py

**Path:** `scripts/agentica/tracked_agent.py`

**Purpose:** Wrapper for agentica agents with automatic coordination DB tracking.

**Key Functions:**
```python
async def tracked_spawn(
    db: CoordinationDB | None,
    premise: str,
    model: Optional[str] = None,
    scope: Optional[dict[str, Any]] = None,
    pattern: Optional[str] = None,
    parent_agent_id: Optional[str] = None,
    **kwargs,
) -> TrackedAgent:
    """Spawn agent with automatic tracking.
    - Registers agent in DB on spawn
    - Records tasks on completion
    - Updates status on close/failure
    """

class TrackedAgent:
    """Wrapper with observability."""

    async def call(self, return_type: type[T], prompt: str, **kwargs) -> T:
        """Call with timing and artifact tracking."""

    async def close(self) -> None:
        """Mark agent completed in DB."""
```

---

## Session Tree Schema (for branching)

**Path:** `scripts/agentica/session_tree_schema.sql`

**Database:** `.claude/cache/agentica-memory/memory.db`

```sql
-- Session entries with tree structure
CREATE TABLE session_entries (
    id TEXT PRIMARY KEY,           -- "se-{uuid8}"
    session_id TEXT NOT NULL,
    branch_id TEXT,
    type TEXT NOT NULL,            -- session, message, branch, model_change
    parent_id TEXT,
    timestamp REAL NOT NULL,
    -- Session-specific
    cwd TEXT, provider TEXT, model_id TEXT,
    -- Message-specific
    role TEXT, content TEXT, usage_json TEXT,
    -- Branch-specific
    branch_name TEXT, branch_description TEXT
);

-- Branch tracking
CREATE TABLE branches (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    parent_branch_id TEXT,
    fork_point_id TEXT,
    created_at REAL NOT NULL,
    is_active BOOLEAN DEFAULT FALSE
);
```

---

## Environment Variables

### Pattern Identification
- `PATTERN_TYPE` - Current pattern (swarm, jury, pipeline, etc.)
- `PATTERN_ID` - Unique execution ID for pattern instance
- `SWARM_ID` - Legacy/alias for swarm pattern
- `AGENT_ID` - Current agent identifier
- `AGENT_ROLE` - Role within pattern (coordinator, worker, juror)

### Hook Context
- `CLAUDE_PROJECT_DIR` - Project root directory
- `CLAUDE_SESSION_ID` - Session identifier (if available)
- `CLAUDE_PPID` - Parent process ID (used as session fallback)

### Pattern-Specific
- `JUROR_INDEX`, `TOTAL_JURORS`, `JURY_ISOLATION` - Jury pattern
- `PIPELINE_STAGE_INDEX`, `PIPELINE_TOTAL_STAGES` - Pipeline pattern
- `HIERARCHY_LEVEL`, `COORDINATOR_ID` - Hierarchical pattern
- `GC_ITERATION` - Generator/Critic pattern
- `MAPPER_INDEX`, `TOTAL_MAPPERS` - Map/Reduce pattern

---

## Implementation Recommendations

### Adding Resource Limit Tracking

1. **StatusLine Enhancement:**
   - Already calculates context % with system overhead
   - Writes to `/tmp/claude-context-pct-{sessionId}.txt`
   - Could add: agent count, pattern info, memory usage

2. **UserPromptSubmit Hook Enhancement:**
   - Already reads context % from temp file
   - Already has tiered warning logic (70%, 80%, 90%)
   - Could add: agent count limits, pattern-specific warnings

3. **Cross-Hook State File Pattern:**
   ```bash
   # Write (StatusLine or any hook)
   echo "$value" > "/tmp/claude-{metric}-{sessionId}.txt"

   # Read (any hook)
   value=$(cat "/tmp/claude-{metric}-{sessionId}.txt" 2>/dev/null || echo "0")
   ```

4. **Database-Backed Limits:**
   - Add limits table to coordination.db
   - Query in PreToolUse to block if over limit
   - Update in PostToolUse after agent spawn

5. **Agent Count Tracking:**
   ```sql
   -- Quick count of running agents
   SELECT COUNT(*) FROM agents WHERE status = 'running';

   -- Pattern-specific limits
   SELECT pattern, COUNT(*) as count
   FROM agents WHERE status = 'running'
   GROUP BY pattern;
   ```

# Module: TUI & Monitoring

## Overview

Upgrade the monitor TUI to a multi-layered dashboard with Apple/Palantir-inspired clean design. Data sources: JSONL (live events) + PostgreSQL (status). Health checks use hybrid alert-on-change pattern.

---

## Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  CLAUDE CONTINUITY KIT v3                                    [H]elp [Q]uit  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─── HEALTH ───────────────────┐  ┌─── RESOURCES ──────────────────────┐  │
│  │  PostgreSQL    ● Connected   │  │  CPU   [████████░░░░]  67%         │  │
│  │  Redis         ● Connected   │  │  RAM   [██████░░░░░░]  52%         │  │
│  │  Docker        ● Running     │  │  Agents: 4 active / 10 max        │  │
│  │  LMStudio      ○ Offline     │  │                                   │  │
│  └──────────────────────────────┘  └────────────────────────────────────┘  │
│                                                                             │
│  ┌─── ACTIVE SWARMS ────────────────────────────────────────────────────┐  │
│  │  ID          Pattern    Agents   Status      Duration                │  │
│  │  ─────────────────────────────────────────────────────────────────── │  │
│  │  sw-a1b2c3   Swarm      3/3      Running     2m 34s                  │  │
│  │  sw-d4e5f6   Jury       2/3      Quorum      1m 12s                  │  │
│  │  sw-g7h8i9   Pipeline   1/4      Stage 2     4m 01s                  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─── AGENT DETAIL (sw-a1b2c3) ─────────────────────────────────────────┐  │
│  │  Agent       Role              Last Tool    Tokens    Status         │  │
│  │  ─────────────────────────────────────────────────────────────────── │  │
│  │  agent-001   Security Expert   Grep         12.4k     Working        │  │
│  │  agent-002   Perf Expert       Read         8.2k      Working        │  │
│  │  agent-003   Sentinel          Bash         3.1k      Monitoring     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─── LIVE FEED ────────────────────────────────────────────────────────┐  │
│  │  14:32:01  agent-001  Read     src/auth.py                           │  │
│  │  14:32:03  agent-002  Grep     "performance" in src/                 │  │
│  │  14:32:05  sentinel   CHECK    All agents on-topic ✓                 │  │
│  │  14:32:08  agent-001  Write    analysis.json                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  [↑↓] Navigate  [Enter] Expand  [K] Kill Agent  [M] Message  [R] Refresh  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Sources

### JSONL Streaming (Live Events)

```python
# scripts/agent_monitor_tui/jsonl_watcher.py
import asyncio
from pathlib import Path
from watchfiles import awatch

async def watch_jsonl(log_dir: str):
    """Watch JSONL files for live events."""

    async for changes in awatch(log_dir):
        for change_type, path in changes:
            if path.endswith('.jsonl'):
                # Read new lines
                events = read_new_lines(path)
                for event in events:
                    yield parse_event(event)
```

### PostgreSQL Status

```python
# scripts/agent_monitor_tui/db_status.py
import asyncpg

async def get_swarm_status(pool: asyncpg.Pool) -> list[dict]:
    """Get current swarm status from coordination DB."""

    return await pool.fetch("""
        SELECT
            session_id as swarm_id,
            pattern,
            COUNT(*) FILTER (WHERE status = 'running') as running,
            COUNT(*) as total,
            MIN(spawned_at) as started_at
        FROM agents
        WHERE status IN ('running', 'completed')
        GROUP BY session_id, pattern
    """)

async def get_agent_details(pool: asyncpg.Pool, swarm_id: str) -> list[dict]:
    """Get details for agents in a swarm."""

    return await pool.fetch("""
        SELECT
            agent_id,
            premise as role,
            status,
            spawned_at,
            completed_at
        FROM agents
        WHERE session_id = $1
        ORDER BY spawned_at
    """, swarm_id)
```

---

## Health Check System

### Hybrid: Poll in Background, Alert on Change

```python
# scripts/agent_monitor_tui/health.py
import asyncio
from dataclasses import dataclass
from enum import Enum

class HealthStatus(Enum):
    CONNECTED = "●"
    DISCONNECTED = "○"
    DEGRADED = "◐"

@dataclass
class ServiceHealth:
    name: str
    status: HealthStatus
    last_check: float
    error: str | None = None

class HealthMonitor:
    def __init__(self, on_change: callable):
        self.services: dict[str, ServiceHealth] = {}
        self.on_change = on_change
        self._check_interval = 10  # seconds

    async def start(self):
        """Start background health monitoring."""
        while True:
            await self._check_all()
            await asyncio.sleep(self._check_interval)

    async def _check_all(self):
        for name, checker in self._checkers.items():
            old_status = self.services.get(name)
            new_status = await checker()

            if old_status != new_status:
                self.services[name] = new_status
                await self.on_change(name, new_status)  # Alert on change

    async def _check_postgres(self) -> ServiceHealth:
        try:
            await self.pool.execute("SELECT 1")
            return ServiceHealth("PostgreSQL", HealthStatus.CONNECTED, time.time())
        except Exception as e:
            return ServiceHealth("PostgreSQL", HealthStatus.DISCONNECTED, time.time(), str(e))

    async def _check_redis(self) -> ServiceHealth:
        try:
            await self.redis.ping()
            return ServiceHealth("Redis", HealthStatus.CONNECTED, time.time())
        except Exception as e:
            return ServiceHealth("Redis", HealthStatus.DISCONNECTED, time.time(), str(e))
```

---

## Design Principles

### Apple/Palantir-Inspired Guidelines

1. **Minimal chrome** - No decorative borders, focus on data
2. **Consistent spacing** - 2-space padding, aligned columns
3. **Muted colors** - Use color sparingly, only for status
4. **No flickering** - Update only on change, not every poll
5. **Progressive disclosure** - Overview → Detail on expand
6. **Keyboard-first** - All actions via keyboard shortcuts

### Color Palette

```python
COLORS = {
    'healthy': '\033[32m',      # Green
    'warning': '\033[33m',      # Yellow
    'error': '\033[31m',        # Red
    'muted': '\033[90m',        # Gray
    'accent': '\033[36m',       # Cyan
    'reset': '\033[0m',
}
```

---

## Agent Interaction

### Kill Agent

```python
async def kill_agent(agent_id: str):
    """Kill a running agent."""

    # Get PID from DB
    row = await pool.fetchrow(
        "SELECT pid FROM agents WHERE agent_id = $1",
        agent_id
    )

    if row and row['pid']:
        os.kill(row['pid'], signal.SIGTERM)

    # Update status
    await pool.execute("""
        UPDATE agents SET status = 'killed', completed_at = NOW()
        WHERE agent_id = $1
    """, agent_id)
```

### Message Agent (via Blackboard)

```python
async def message_agent(target_agent: str, message: str):
    """Send a message to an agent via blackboard."""

    await pool.execute("""
        INSERT INTO blackboard (swarm_id, sender_agent, message_type, target_agent, payload)
        VALUES ($1, 'orchestrator', 'directive', $2, $3)
    """,
        get_current_swarm(),
        target_agent,
        json.dumps({"action": "message", "message": message})
    )
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/agent_monitor_tui/main.py` | TUI entry point |
| `scripts/agent_monitor_tui/views.py` | Dashboard views |
| `scripts/agent_monitor_tui/health.py` | Health monitoring |
| `scripts/agent_monitor_tui/jsonl_watcher.py` | JSONL streaming |
| `scripts/agent_monitor_tui/db_status.py` | PostgreSQL queries |
| `scripts/agent_monitor_tui/actions.py` | Kill, message, etc. |

## Dependencies

```toml
[project.optional-dependencies]
tui = [
    "textual>=0.40.0",
    "watchfiles>=0.20.0",
]
```

---

## Log Rotation

JSONL logs archived to compressed storage:
- Time-based rotation (new file per day)
- Files older than 7 days: gzip and move to archive/
- Files older than 30 days: delete compressed archives

```python
# scripts/log_rotation.py
async def rotate_logs(log_dir: str, archive_dir: str):
    """Rotate and compress old JSONL logs."""
    now = datetime.now()

    for log_file in Path(log_dir).glob("*.jsonl"):
        file_age = now - datetime.fromtimestamp(log_file.stat().st_mtime)

        if file_age > timedelta(days=7):
            # Compress and move
            compressed = archive_dir / f"{log_file.stem}.jsonl.gz"
            with gzip.open(compressed, 'wt') as f:
                f.write(log_file.read_text())
            log_file.unlink()

        if file_age > timedelta(days=30):
            # Delete old archives
            compressed.unlink()
```

## Token Tracking via OpenTelemetry

TUI queries OTel metrics endpoint for token usage:
- Requires user to configure OTel export
- Falls back to "Enable OTel for token tracking" message if unavailable

```python
async def get_token_usage() -> dict | None:
    """Query OTel metrics for token usage."""
    try:
        # Assumes OTel collector at default endpoint
        response = await httpx.get("http://localhost:9090/api/v1/query", params={
            "query": "claude_code_token_usage"
        })
        return response.json()
    except Exception:
        return None  # OTel not configured
```

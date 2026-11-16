# Module: Concurrency & Coordination

## Overview

Migrate CoordinationDB from SQLite to PostgreSQL. Implement dynamic concurrency strategies per pattern type. Enable blackboard polling via PreToolUse hooks.

---

## PostgreSQL Schema

```sql
-- Coordination database schema
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Agents table
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    agent_id TEXT UNIQUE NOT NULL,
    parent_agent_id UUID REFERENCES agents(id),
    premise TEXT,
    pattern TEXT,
    depth_level INTEGER DEFAULT 1,
    pid INTEGER,
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'orphaned')),
    spawned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    result_summary TEXT
);

CREATE INDEX idx_agents_session ON agents(session_id);
CREATE INDEX idx_agents_status ON agents(status);
CREATE INDEX idx_agents_pattern ON agents(pattern);
CREATE INDEX idx_agents_parent ON agents(parent_agent_id);

-- Blackboard for inter-agent messaging
CREATE TABLE blackboard (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    swarm_id TEXT NOT NULL,
    sender_agent TEXT NOT NULL,
    message_type TEXT NOT NULL CHECK (message_type IN ('finding', 'directive', 'status', 'quorum')),
    target_agent TEXT,  -- NULL = broadcast to all
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_by JSONB DEFAULT '[]'::jsonb  -- Array of agent_ids that have read this
);

CREATE INDEX idx_blackboard_swarm ON blackboard(swarm_id, created_at);
CREATE INDEX idx_blackboard_target ON blackboard(target_agent) WHERE target_agent IS NOT NULL;

-- Sandbox computations (shared state)
CREATE TABLE sandbox_computations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value JSONB NOT NULL,
    computed_by TEXT NOT NULL,  -- agent_id
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    UNIQUE(session_id, key)
);

CREATE INDEX idx_sandbox_session_key ON sandbox_computations(session_id, key);
```

---

## Dynamic Concurrency Strategies

| Pattern | Strategy | Rationale |
|---------|----------|-----------|
| Swarm | Append-only | Independent writes, no conflicts |
| Jury | Optimistic locking | Converging votes need consistency |
| Pipeline | Sequential | No concurrency needed |
| MapReduce | Append-only (mappers), Sequential (reducer) | Mappers independent, reducer aggregates |
| Blackboard | Row-level locking | Shared state requires coordination |

### Implementation

```python
# scripts/agentica_patterns/coordination_pg.py
from enum import Enum
import asyncpg

class ConcurrencyStrategy(Enum):
    APPEND_ONLY = "append_only"
    OPTIMISTIC = "optimistic"
    ROW_LOCK = "row_lock"

PATTERN_STRATEGIES = {
    "swarm": ConcurrencyStrategy.APPEND_ONLY,
    "jury": ConcurrencyStrategy.OPTIMISTIC,
    "pipeline": ConcurrencyStrategy.APPEND_ONLY,  # Sequential anyway
    "map_reduce": ConcurrencyStrategy.APPEND_ONLY,
    "blackboard": ConcurrencyStrategy.ROW_LOCK,
    "hierarchical": ConcurrencyStrategy.OPTIMISTIC,
    "sentinel": ConcurrencyStrategy.ROW_LOCK,  # Sentinel updates need consistency
}

async def write_result(
    pool: asyncpg.Pool,
    agent_id: str,
    result: dict,
    pattern: str,
) -> None:
    strategy = PATTERN_STRATEGIES.get(pattern, ConcurrencyStrategy.APPEND_ONLY)

    if strategy == ConcurrencyStrategy.APPEND_ONLY:
        await pool.execute("""
            INSERT INTO agent_results (agent_id, result, created_at)
            VALUES ($1, $2, NOW())
        """, agent_id, result)

    elif strategy == ConcurrencyStrategy.OPTIMISTIC:
        # Check version, retry on conflict
        async with pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    "SELECT version FROM agent_results WHERE agent_id = $1",
                    agent_id
                )
                if current:
                    await conn.execute("""
                        UPDATE agent_results
                        SET result = $2, version = version + 1
                        WHERE agent_id = $1 AND version = $3
                    """, agent_id, result, current['version'])
                else:
                    await conn.execute("""
                        INSERT INTO agent_results (agent_id, result, version)
                        VALUES ($1, $2, 1)
                    """, agent_id, result)

    elif strategy == ConcurrencyStrategy.ROW_LOCK:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "SELECT * FROM agent_results WHERE agent_id = $1 FOR UPDATE",
                    agent_id
                )
                await conn.execute("""
                    INSERT INTO agent_results (agent_id, result)
                    VALUES ($1, $2)
                    ON CONFLICT (agent_id) DO UPDATE SET result = $2
                """, agent_id, result)
```

---

## Blackboard Polling

### PreToolUse Hook (Write-Path Only)

```typescript
// .claude/hooks/src/blackboard-poll.ts

const WRITE_TOOLS = ['Bash', 'Write', 'Edit', 'MultiEdit'];

async function main() {
    const input = JSON.parse(await readStdin());

    // Only poll for write operations
    if (!WRITE_TOOLS.includes(input.tool_name)) {
        console.log(JSON.stringify({ result: 'continue' }));
        return;
    }

    const agentId = process.env.AGENT_ID;
    const swarmId = process.env.SWARM_ID;

    if (!agentId || !swarmId) {
        console.log(JSON.stringify({ result: 'continue' }));
        return;
    }

    // Poll blackboard for directives
    const messages = await pollBlackboard(swarmId, agentId);

    if (messages.length > 0) {
        // Check for blocking directives
        const blockingDirective = messages.find(m =>
            m.message_type === 'directive' &&
            (m.target_agent === agentId || m.target_agent === null)
        );

        if (blockingDirective) {
            console.log(JSON.stringify({
                result: 'block',
                reason: `Directive from sentinel: ${blockingDirective.payload.message}`
            }));
            return;
        }

        // Inject findings as context
        const findings = messages
            .filter(m => m.message_type === 'finding')
            .map(m => m.payload.summary)
            .join('\n');

        if (findings) {
            console.log(JSON.stringify({
                result: 'continue',
                message: `[Blackboard Update]\n${findings}`
            }));
            return;
        }
    }

    console.log(JSON.stringify({ result: 'continue' }));
}
```

---

## PgBouncer Integration

Add PgBouncer to Docker stack for connection multiplexing:
- Sits between agents and PostgreSQL
- Maintains small pool of real connections (20)
- Accepts many client connections (500+)
- Agents connect to PgBouncer, not PostgreSQL directly

```yaml
# docker-compose.yml addition
pgbouncer:
  image: edoburu/pgbouncer:latest
  environment:
    DATABASE_URL: postgres://postgres:password@postgres:5432/coordination
    POOL_MODE: transaction
    MAX_CLIENT_CONN: 500
    DEFAULT_POOL_SIZE: 20
  ports:
    - "6432:6432"
```

## Spawn Backpressure

Block spawning until PostgreSQL confirms registration:
- Prevents runaway agent spawning when DB is slow
- Agent cannot start work before registered
- Queue-based waiting with timeout

```python
async def spawn_agent_with_backpressure(prompt: str, timeout: float = 30.0) -> SpawnedAgent:
    """Spawn agent, blocking until DB confirms registration."""
    agent_id = generate_uuid()

    # Register first, block until confirmed
    await asyncio.wait_for(
        register_agent_in_db(agent_id),
        timeout=timeout
    )

    # Only now spawn the process
    return spawn_agent(prompt, agent_id=agent_id)
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/agentica_patterns/coordination_pg.py` | PostgreSQL coordination |
| `scripts/agentica_patterns/blackboard_pg.py` | Blackboard operations |
| `.claude/hooks/src/blackboard-poll.ts` | PreToolUse polling hook |
| `docker/init-coordination.sql` | Schema initialization |

## Poll Cleanup Strategy

> Reference: [00-architecture-decisions.md](./00-architecture-decisions.md) - Poll Cleanup (Blackboard)

### Status Tracking

1. **Track read counts** - Store agent IDs in `read_by` JSONB array
2. **Mark resolved** - When all target agents have read the message
3. **Archive to DB** - Move to `blackboard_archive` table for audit trail
4. **Delete from active** - Remove from active blackboard after archival

```sql
-- Archive resolved messages
INSERT INTO blackboard_archive
SELECT * FROM blackboard
WHERE id IN (
    SELECT id FROM blackboard b
    WHERE jsonb_array_length(b.read_by) >= (
        SELECT COUNT(*) FROM agents a
        WHERE a.swarm_id = b.swarm_id AND a.status = 'running'
    )
);

-- Delete archived
DELETE FROM blackboard WHERE id IN (SELECT id FROM blackboard_archive WHERE archived_at > NOW() - INTERVAL '1 minute');
```

---

## Hook Invocation Security

> Reference: [00-architecture-decisions.md](./00-architecture-decisions.md) - Hook Security

Hook invocation MUST use JSON over stdin with subprocess arrays - never string interpolation.

```typescript
// CORRECT - JSON stdin + subprocess array
import { execFile } from 'child_process';

const data = { swarm_id: swarmId, agent_id: agentId };
const child = execFile('python', ['blackboard_poll.py'], {
    input: JSON.stringify(data)
});

// WRONG - command injection risk
execSync(`python blackboard_poll.py --swarm '${swarmId}'`);  // NEVER DO THIS
```

---

## SpawnQueue Architecture

> Reference: [00-architecture-decisions.md](./00-architecture-decisions.md) - Spawn Coordination

The SpawnQueue (formerly "spawn blackboard") uses a dual-store architecture:
- **Redis** - Hot polling at 100ms intervals for real-time coordination
- **PostgreSQL** - Durability and audit trail

This is **NOT** the same as the Pattern Blackboard (shared state during task execution).

---

## Files to Modify

| File | Changes |
|------|---------|
| `scripts/agentica_patterns/coordination.py` | Add PG support, keep SQLite fallback |
| `docker/docker-compose.yml` | Add Redis service |

# Module: Error Recovery

## Overview

Handle agent crashes, database failures, and orchestrator disconnection. Use temporal memory for context-efficient resume. Apply quorum-based completion for partial pattern failures.

---

## Agent Crash Recovery

### Fresh Start + Temporal Summary

When an agent crashes, spawn a fresh agent with temporal memory context:

```python
async def recover_from_crash(crashed_agent_id: str) -> SpawnedAgent:
    """Recover a crashed agent with temporal memory context."""

    # Get agent info
    agent_info = await get_agent_info(crashed_agent_id)

    # Get temporal memory summary (compact, not full context)
    temporal_summary = await get_temporal_summary(
        session_id=agent_info.session_id,
        max_tokens=2000,  # Budget for context
    )

    # Build recovery prompt
    recovery_prompt = f"""
You are resuming a task that was interrupted.

PREVIOUS PROGRESS:
{temporal_summary.to_markdown()}

ORIGINAL TASK:
{agent_info.original_prompt}

Continue from where the previous agent left off. Do not repeat completed work.
"""

    # Spawn fresh agent
    new_agent = spawn_agent(
        prompt=recovery_prompt,
        perspective=agent_info.premise,
        depth_level=agent_info.depth_level,
    )

    # Link to crashed agent for tracking
    await link_recovery(crashed_agent_id, new_agent.agent_id)

    return new_agent
```

### Temporal Memory Summary

```python
async def get_temporal_summary(session_id: str, max_tokens: int = 2000) -> TemporalHandoffState:
    """Get a token-efficient summary of agent progress."""

    store = await create_temporal_store(session_id=session_id)

    # Get invariants (facts that never changed - stable anchors)
    invariants = await store.get_invariants()

    # Get recent transitions (what changed recently)
    transitions = await store.get_recent_transitions(limit=10)

    # Get pending goals
    pending_goals = await store.get_pending_goals()

    return TemporalHandoffState(
        invariants=invariants,
        transitions=transitions,
        pending_goals=pending_goals,
    )
```

---

## Database Failure Recovery

### Retry with Backoff + TUI Notification

```python
import asyncio
from functools import wraps

def db_retry(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator for database operations with retry and notification."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (asyncpg.PostgresConnectionError, asyncpg.InterfaceError) as e:
                    last_error = e
                    delay = base_delay * (2 ** attempt)

                    # Notify TUI of DB issue
                    await notify_health_change("PostgreSQL", "DISCONNECTED", str(e))

                    if attempt < max_retries - 1:
                        await asyncio.sleep(delay)

            # All retries failed
            await notify_health_change("PostgreSQL", "FAILED", str(last_error))
            raise DatabaseUnavailableError(f"Database unavailable after {max_retries} retries: {last_error}")

        return wrapper
    return decorator

# Usage
@db_retry(max_retries=3)
async def register_agent(agent_id: str, **kwargs):
    await pool.execute(...)
```

### TUI Health Notification

```python
async def notify_health_change(service: str, status: str, error: str | None = None):
    """Notify TUI of health change via Redis pub/sub."""

    message = {
        "service": service,
        "status": status,
        "error": error,
        "timestamp": datetime.now().isoformat(),
    }

    await redis.publish("health_updates", json.dumps(message))
```

---

## Orchestrator Crash Recovery

### Continue + Alert (Orphaned Agents)

When orchestrator disconnects, agents continue but mark themselves as orphaned:

```python
# In each headless agent's startup
async def check_parent_heartbeat():
    """Monitor parent orchestrator heartbeat."""

    parent_id = os.environ.get("PARENT_AGENT_ID", "orchestrator")

    while True:
        await asyncio.sleep(30)  # Check every 30s

        # Check if parent is still alive
        parent_alive = await check_heartbeat(parent_id)

        if not parent_alive:
            # Mark self as orphaned
            await pool.execute("""
                UPDATE agents SET status = 'orphaned'
                WHERE agent_id = $1
            """, os.environ.get("AGENT_ID"))

            # Continue working, but TUI will show alert
            logger.warning(f"Parent {parent_id} disconnected. Continuing as orphan.")
```

### TUI Orphan Alert

```python
# In TUI
async def check_orphans():
    """Check for orphaned agents and display alert."""

    orphans = await pool.fetch("""
        SELECT agent_id, premise, spawned_at
        FROM agents
        WHERE status = 'orphaned'
    """)

    if orphans:
        console.print(f"[bold yellow]⚠ {len(orphans)} orphaned agents running[/bold yellow]")
        for orphan in orphans:
            console.print(f"  - {orphan['agent_id']}: {orphan['premise']}")
```

### Resume Orphaned Work

```python
async def resume_orphaned_work():
    """Resume work from orphaned agents in new session."""

    orphans = await pool.fetch("""
        SELECT * FROM agents WHERE status = 'orphaned'
    """)

    for orphan in orphans:
        # Get agent's results (if any)
        results = await get_agent_results(orphan['agent_id'])

        if results:
            console.print(f"Orphan {orphan['agent_id']} has results:")
            console.print(results.summary)

        # User decides: resume, kill, or ignore
        action = Prompt.ask(
            f"Action for {orphan['agent_id']}",
            choices=["resume", "kill", "ignore"]
        )

        if action == "resume":
            await recover_from_crash(orphan['agent_id'])
        elif action == "kill":
            await kill_agent(orphan['agent_id'])
        # ignore = leave running
```

---

## Quorum-Based Pattern Completion

### Partial Success Handling

```python
async def wait_for_quorum(
    agents: list[SpawnedAgent],
    quorum: int,
    timeout: float = 300,
) -> list[AgentResult]:
    """Wait for quorum of agents to complete."""

    completed = []
    start_time = asyncio.get_event_loop().time()

    while len(completed) < quorum:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > timeout:
            break

        for agent in agents:
            if agent.agent_id not in [c.agent_id for c in completed]:
                result = await check_agent_status(agent.agent_id)
                if result.status in ('completed', 'failed'):
                    completed.append(result)

        await asyncio.sleep(1)

    # Check if quorum met
    successful = [c for c in completed if c.status == 'completed']

    if len(successful) >= quorum:
        # Quorum met - proceed with available results
        return successful
    else:
        # Quorum not met - raise or degrade
        raise QuorumNotMetError(f"Only {len(successful)}/{quorum} agents completed successfully")
```

### Pattern-Specific Quorum

| Pattern | Quorum Rule |
|---------|-------------|
| Jury | 2/3 minimum (majority) |
| Swarm | 1/N (any result useful) |
| MapReduce | All mappers before reducer |
| Pipeline | All stages (sequential) |
| Hierarchical | Coordinator always required |

---

## Graceful Shutdown via SessionEnd Hook

SessionEnd hook handles Ctrl+C and session exit:

```typescript
// .claude/hooks/src/session-end-shutdown.ts
async function main() {
    const input = JSON.parse(await readStdin());

    // Get all running agent PIDs
    const agents = await pool.fetch(`
        SELECT pid FROM agents WHERE status = 'running'
    `);

    // SIGTERM all agents
    for (const agent of agents) {
        if (agent.pid) {
            process.kill(agent.pid, 'SIGTERM');
        }
    }

    // Wait up to 30s for graceful exit
    const deadline = Date.now() + 30000;
    while (Date.now() < deadline) {
        const running = await pool.fetchval(`
            SELECT COUNT(*) FROM agents WHERE status = 'running'
        `);
        if (running === 0) break;
        await sleep(1000);
    }

    // SIGKILL any remaining
    const remaining = await pool.fetch(`
        SELECT pid FROM agents WHERE status = 'running'
    `);
    for (const agent of remaining) {
        if (agent.pid) {
            process.kill(agent.pid, 'SIGKILL');
        }
    }

    console.log(JSON.stringify({ result: 'continue' }));
}
```

## Orphan Auto-Detection

SessionStart hook detects orphaned agents:

```typescript
// .claude/hooks/src/session-start-orphans.ts
async function checkOrphans() {
    const orphans = await pool.fetch(`
        SELECT agent_id, premise, spawned_at
        FROM agents WHERE status = 'orphaned'
    `);

    if (orphans.length > 0) {
        return {
            result: 'continue',
            message: `Found ${orphans.length} orphaned agents from previous session:
${orphans.map(o => `- ${o.agent_id}: ${o.premise}`).join('\n')}

Use /resume-orphans to adopt them, or /kill-orphans to terminate.`
        };
    }

    return { result: 'continue' };
}
```

## Redis Fallback

If Redis crashes, continue without cache:

```python
async def get_with_redis_fallback(key: str) -> Any:
    """Get from Redis, fall back to PostgreSQL."""
    try:
        cached = await redis.get(key)
        if cached:
            return json.loads(cached)
    except RedisError:
        pass  # Continue without cache

    # Fall back to PostgreSQL
    return await pool.fetchval(
        "SELECT value FROM cache_fallback WHERE key = $1",
        key
    )
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/agentica_patterns/recovery.py` | Recovery logic |
| `scripts/agentica_patterns/heartbeat.py` | Heartbeat monitoring |
| `scripts/agentica_patterns/quorum.py` | Quorum utilities |

## Files to Modify

| File | Changes |
|------|---------|
| `scripts/agentica_patterns/patterns.py` | Add quorum support |
| `scripts/temporal_memory/summarizer.py` | Optimize for recovery |

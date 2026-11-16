# Starvation Vulnerability Audit

## Summary
- **Total issues found**: 8
- **High risk**: 4
- **Medium risk**: 4
- **Low risk**: 0

## Findings

### Finding 1: Hard Resource Limit Blocks Without Timeout

- **File:Line**: `.claude/hooks/src/pre-tool-use.ts:201-210`
- **Pattern detected**: When agent limit is reached (activeAgents >= maxAgents), the hook blocks the agent spawn indefinitely. There is no timeout mechanism, so waiting agents could starve if they never get priority.
- **Risk level**: HIGH
- **Suggested fix**:
  - Add a timeout per blocked agent request
  - Implement an aging mechanism where older blocked requests get priority
  - Provide queue position feedback to the user rather than hard blocking indefinitely

---

### Finding 2: PostgreSQL Connection Pool Without Acquire Timeout

- **File:Line**: `scripts/agentica/postgres_pool.py:102-109`
- **Pattern detected**: The asyncpg pool is created with `max_size=10` and no explicit timeout for connection acquisition. If all 10 connections are held by agents that are waiting (e.g., for I/O), new agents requesting connections will block indefinitely waiting for a pool slot.
- **Risk level**: HIGH
- **Suggested fix**:
  - Add `acquire_timeout` parameter to `asyncpg.create_pool()` (e.g., `acquire_timeout=30`)
  - Configure `command_timeout=60` (already set, good)
  - Consider implementing connection borrowing with automatic timeout and cleanup

---

### Finding 3: SQLite Database Lock Without Busy Timeout

- **File:Line**: `.claude/hooks/dist/shared/db-utils.js:115`
- **Pattern detected**: Direct SQLite connections in Python subprocesses do not set `PRAGMA busy_timeout`. When multiple hooks try to write to the database simultaneously, the second writer blocks indefinitely waiting for the first writer to release the lock.
- **Risk level**: HIGH
- **Suggested fix**:
  - Add `conn.execute("PRAGMA busy_timeout = 5000")` to set 5-second timeout (in all Python query scripts)
  - Enable WAL mode: `conn.execute("PRAGMA journal_mode = WAL")`
  - Implement exponential backoff retry logic at the hook level for transient lock timeouts

---

### Finding 4: Stop Hooks Block Coordinator Without Timeout

- **File:Line**: `.claude/hooks/dist/stop-coordinator.js:119-124`
- **Pattern detected**: The stop hook blocks the coordinator if not all jurors have voted (`result: 'block'`). If a juror agent crashes or hangs, the coordinator will block indefinitely waiting for a vote that never comes.
- **Risk level**: HIGH
- **Suggested fix**:
  - Add a maximum wait time in the blocking message or environment variable
  - Implement a "wait deadline" based on spawn time + timeout
  - Check if jurors are still alive before blocking (query agent status table)
  - Provide fallback: "Proceeding with partial votes after 30s timeout"

---

### Finding 5: Event-Driven Pattern Uses Unbounded Concurrent Dispatch

- **File:Line**: `scripts/agentica/patterns/event_driven.py:185-187`
- **Pattern detected**: `asyncio.gather()` with no concurrency limit spawns N subscriber agents in parallel for a single event. If you have 100 subscribers, this creates 100 concurrent tasks without semaphore control. Combined with the maxAgents limit, this could create starvation where one event blocks all future work.
- **Risk level**: MEDIUM
- **Suggested fix**:
  - Add a `max_concurrent_subscribers` parameter to EventDriven
  - Use `asyncio.Semaphore` to limit concurrent dispatch: `async with semaphore: await agent.call(...)`
  - Implement priority queuing: high-priority events get more slots

---

### Finding 6: gather_fail_fast TaskGroup Without Timeout

- **File:Line**: `scripts/agentica/patterns/primitives.py:501`
- **Pattern detected**: `asyncio.TaskGroup()` waits indefinitely for all tasks to complete. If any subtask hangs (e.g., blocked on a database lock), all sibling tasks are cancelled, causing cascading failures.
- **Risk level**: MEDIUM
- **Suggested fix**:
  - Wrap TaskGroup operations with `asyncio.timeout()` (Python 3.11+)
  - Add timeout parameter to `gather_fail_fast()` function
  - Implement per-task timeouts at the caller level (Swarm, Hierarchical, Jury)

---

### Finding 7: Resource State Check Is TOCTOU Race

- **File:Line**: `.claude/hooks/dist/shared/resource-reader.js:74-75`
- **Pattern detected**: The pre-tool-use hook reads `maxAgents` from a file, then checks `activeAgents >= maxAgents`. Between the read and the block decision, another hook might have incremented `activeAgents`. Multiple agents could slip through the limit simultaneously.
- **Risk level**: MEDIUM
- **Suggested fix**:
  - Use an atomic compare-and-swap pattern (write to DB with transaction)
  - Implement a semaphore in the coordination DB instead of file-based limits
  - Use a distributed lock with expiration for resource allocation

---

### Finding 8: Hierarchical Pattern Spawns Specialists Sequentially Without Timeout

- **File:Line**: `scripts/agentica/patterns/hierarchical.py:225-247`
- **Pattern detected**: Specialists are spawned one-at-a-time in `_ensure_specialist()`, called from `_execute_subtasks()`. If the first specialist hangs waiting for a database lock, the entire hierarchical execution stalls with no timeout.
- **Risk level**: MEDIUM
- **Suggested fix**:
  - Implement concurrent specialist spawning with `asyncio.gather()`
  - Add timeout to each specialist spawn operation
  - Implement graceful degradation: "Proceeding with partial team after timeout"

---

## Critical Actions (Priority Order)

1. Add `PRAGMA busy_timeout` to all SQLite queries (quick, high impact)
2. Add `acquire_timeout` to asyncpg pool configuration
3. Implement per-agent request timeout in pre-tool-use blocking logic
4. Add maximum wait deadline to all stop hook blocks
5. Implement semaphore-based concurrency control in EventDriven
6. Wrap gather_fail_fast with asyncio.timeout()

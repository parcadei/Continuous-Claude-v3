# Race Condition Vulnerability Audit

## Summary
- **Total issues found**: 9
- **High risk**: 3
- **Medium risk**: 6
- **Low risk**: 0

## Findings

### Finding 1: CircuitBreaker Pattern - Concurrent State Mutations (HIGH RISK)

- **File:Line**: `scripts/agentica/patterns/circuit_breaker.py:170-202`
- **Pattern detected**: Multiple concurrent state mutations without atomicity
  - `self.state` read in `_should_try_primary()` at line 172
  - State transition at line 180: `self.state = CircuitState.HALF_OPEN`
  - `self.failure_count` incremented at line 195 without lock
  - `self.state` mutation at lines 199-202
- **Risk level**: HIGH
- **Issue**: Race condition between `_should_try_primary()` and `_record_failure()`. If multiple async tasks call `execute()` concurrently:
  - Thread 1 reads `self.state == OPEN` and elapsed time > timeout
  - Thread 2 reads same state and also enters HALF_OPEN test
  - Both attempt primary agent simultaneously
  - Both can modify `self.state` and `self.failure_count` concurrently
  - Results in undefined state and inconsistent failure counts
- **Suggested fix**: Add asyncio.Lock() to protect state mutations:
  ```python
  def __init__(self, ...):
      self._state_lock = asyncio.Lock()

  async def _record_failure(self):
      async with self._state_lock:
          self.failure_count += 1
          self.last_failure_time = time.time()
          if self.failure_count >= self.max_failures:
              self.state = CircuitState.OPEN
  ```

---

### Finding 2: Blackboard Pattern - Concurrent State Writes (HIGH RISK)

- **File:Line**: `scripts/agentica/patterns/blackboard.py:40-90`
- **Pattern detected**: Shared `BlackboardState._data` dict without synchronization
  - Multiple specialists write to state concurrently (line 307: `state[key] = contribution[key]`)
  - No lock protecting dict access
  - History list appended without lock (line 66-70)
- **Risk level**: HIGH
- **Issue**: Dict is not thread-safe across threads/async tasks. Multiple specialists running `_run_specialist()` concurrently will race on state mutations:
  - Specialist 1 reads state for key "requirements"
  - Specialist 2 modifies "requirements"
  - Specialist 1 overwrites with stale read
  - History corruption with interleaved append operations
  - Potential KeyError or missing state updates
- **Suggested fix**: Use asyncio.Lock() or dict.update() within critical section:
  ```python
  class BlackboardState:
      def __init__(self):
          self._data: dict[str, Any] = {}
          self._lock = asyncio.Lock()
          self.history: list[dict[str, Any]] = []

      async def set_item(self, key: str, value: Any) -> None:
          async with self._lock:
              self._data[key] = value
              self.history.append(...)
  ```

---

### Finding 3: Hierarchical Pattern - Lazy Agent Initialization Race (HIGH RISK)

- **File:Line**: `scripts/agentica/patterns/hierarchical.py:204-223`
- **Pattern detected**: Check-then-act pattern without atomicity for coordinator lazy spawn
  ```python
  if self.coordinator is None:  # Line 204 - check
      # Lines 205-217: long operation
      self.coordinator = await tracked_spawn(...)  # Line 215 - act
  ```
- **Risk level**: HIGH
- **Issue**: Multiple concurrent calls to `_ensure_coordinator()` can all see `self.coordinator is None`, spawn multiple coordinators, and overwrite each other:
  - Coordinator_Spawn_1 passes check at line 204
  - Coordinator_Spawn_2 also passes check at line 204 (before line 215 completes)
  - Both spawn duplicate coordinator agents
  - Second spawn overwrites first, wasting resources and losing reference
  - Same issue with `_ensure_specialist()` at line 227-247
- **Suggested fix**: Use asyncio.Lock() for lazy initialization:
  ```python
  def __init__(self, ...):
      self._coordinator_lock = asyncio.Lock()

  async def _ensure_coordinator(self):
      async with self._coordinator_lock:
          if self.coordinator is None:
              # spawn logic
  ```

---

### Finding 4: Adversarial Pattern - Concurrent Agent State Mutation (MEDIUM RISK)

- **File:Line**: `scripts/agentica/patterns/adversarial.py:189-191`
- **Pattern detected**: State reset in debate() without synchronization
  ```python
  self.advocate = None       # Line 190
  self.adversary = None      # Line 191
  self.debate_history = []   # Line 204
  ```
- **Risk level**: MEDIUM
- **Issue**: If `resolve()` calls `debate()` while other tasks are in `_ensure_advocate()`, the reset clears agents mid-spawn:
  - Task 1 clears `self.advocate = None` at line 190
  - Task 2 is inside `_ensure_advocate()` and spawning
  - Task 2 completes spawn and assigns to `self.advocate`
  - But Task 1 may re-enter, clearing it again
  - Multiple agent instances created concurrently
- **Suggested fix**: Use asyncio.Lock() to gate debate() execution

---

### Finding 5: TrackedAgent - State Flag Race Condition (MEDIUM RISK)

- **File:Line**: `scripts/agentica/tracked_agent.py:74-77`
- **Pattern detected**: Check-then-act on `_closed` flag
  ```python
  if self._closed:        # Line 74 - check
      return              # Line 75
  self._closed = True     # Line 77 - act
  ```
- **Risk level**: MEDIUM
- **Issue**: Concurrent calls to `close()` can both see `_closed=False`, both proceed, causing duplicate completion messages to DB:
  - Thread 1 checks `_closed=False` at line 74
  - Thread 2 also checks `_closed=False` at line 74 (interleaved)
  - Both call `db.complete_agent()` at line 80
  - Two completion events recorded for same agent
- **Suggested fix**: Use atomic test-and-set or asyncio.Lock()

---

### Finding 6: Generator/Critic Pattern - Env Variable Race (MEDIUM RISK)

- **File:Line**: `scripts/agentica/patterns/generator_critic.py:96-142`
- **Pattern detected**: Direct `os.environ` mutation without context manager during spawn
  - Lines 100-105: Set env vars for generator spawn
  - Lines 124-129: Set env vars for critic spawn
  - **No try/finally** to restore
- **Risk level**: MEDIUM
- **Issue**: If spawning multiple GeneratorCritic instances concurrently, env vars get overwritten:
  - GC_Instance_1 sets `os.environ["GC_ID"]` = "id1"
  - GC_Instance_2 sets `os.environ["GC_ID"]` = "id2" (overwrites before instance_1 spawns)
  - Child process launched by instance_1 sees "id2" instead of "id1"
  - Hooks route to wrong pattern handler
- **Suggested fix**: Use contextmanager for env var block

---

### Finding 7: Jury Pattern - Concurrent jury_id Assignment (MEDIUM RISK)

- **File:Line**: `scripts/agentica/patterns/jury.py:257-258`
- **Pattern detected**: Race on `self.jury_id` assignment in `decide()`
  ```python
  self.jury_id = uuid4().hex[:12]  # Line 258 - no lock
  jurors = await self._spawn_jurors()  # Line 260
  ```
- **Risk level**: MEDIUM
- **Issue**: Multiple concurrent `decide()` calls race on `self.jury_id`:
  - Call_1: Sets `jury_id = "uuid1"`, then spawns jurors
  - Call_2: Overwrites `jury_id = "uuid2"` before Call_1 completes spawn
  - Jurors from Call_1 get env var with "uuid2"
  - Hooks correlate wrong agents to wrong jury
- **Suggested fix**: Move jury_id to local variable:
  ```python
  async def decide(self, return_type: type, question: str) -> Any:
      jury_id = uuid4().hex[:12]  # Local, not self.jury_id
      jurors = await self._spawn_jurors(jury_id)
  ```

---

### Finding 8: Swarm/Jury/Hierarchical Pattern - os.environ Races (MEDIUM RISK)

- **Files**:
  - `swarm.py:113-147` (context manager approach - SAFER)
  - `jury.py:151-191` (context manager approach - SAFER)
  - `hierarchical.py:121-200` (context manager approach - SAFER)
  - `event_driven.py:112-149` (context manager approach - SAFER)
- **Pattern detected**: While most patterns use `@contextmanager` for env vars (good), the restoration can still race if parent task is cancelled
- **Risk level**: MEDIUM
- **Issue**: If async task is cancelled during `yield`, finally block may not restore env vars properly
- **Suggested fix**: Use try/except/finally with explicit cancellation handling or Thread-local storage

---

### Finding 9: Coordination DB - SQLite Connection Pool Issue (LOW RISK - But Worth Noting)

- **File:Line**: `scripts/agentica/coordination.py:191-200`
- **Pattern detected**: New SQLite connection per operation (correct approach)
- **Positive**: SQLite handles concurrent access with locks
- **Issue**: If multiple processes write simultaneously, database lock contention can cause "database is locked" errors under high concurrency
- **Mitigation**: SQLite is generally safe; this is not a race condition per se, but can cause timeouts

---

## Recommended Mitigation Strategy

### Priority 1 (Execute Immediately):
- Add `asyncio.Lock()` to CircuitBreaker, Blackboard, Hierarchical for critical sections
- These have direct test failures under concurrent load

### Priority 2 (Execute Soon):
- Add locks to TrackedAgent.close()
- Fix Jury pattern to use local variables instead of self.jury_id
- Fix Adversarial pattern debate() reset race

### Priority 3 (Execute When Convenient):
- Review env var context managers for cancellation safety
- Consider using contextvars for environment isolation instead of os.environ

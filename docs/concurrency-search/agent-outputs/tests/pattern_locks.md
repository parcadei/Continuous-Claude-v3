# Pattern Concurrency Tests Summary

## Test File Location

`/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_pattern_concurrency.py`

## Test Overview

These tests verify the race conditions identified in `docs/concurrency-search/RACE_FINDINGS.md`. They are designed to **FAIL** without proper `asyncio.Lock()` protection and will **PASS** once the patterns are fixed.

## Test Results (Current State: FAILING)

| Test | Status | Issue Demonstrated |
|------|--------|-------------------|
| `test_concurrent_execute_state_consistency` | FAIL | CircuitBreaker `failure_count` exceeds `max_failures` |
| `test_concurrent_read_modify_write_race` | FAIL | BlackboardState loses updates in read-modify-write |
| `test_concurrent_ensure_coordinator_single_spawn` | FAIL | Hierarchical spawns 5 coordinators instead of 1 |
| `test_concurrent_ensure_specialist_single_spawn` | FAIL | Hierarchical spawns 5 specialists instead of 1 |
| `test_concurrent_execute_tasks_share_coordinator` | FAIL | Hierarchical spawns 3 coordinators instead of 1 |

## Detailed Test Descriptions

### 1. CircuitBreaker Tests

#### `test_concurrent_execute_state_consistency`
**What it tests:** 10 concurrent `execute()` calls with failing primary agent.

**Expected behavior:** `failure_count` should be capped at `max_failures` (3), and state should transition to `OPEN`.

**Current failure:**
```
AssertionError: Inconsistent failure_count: 10
assert 10 <= 3
```

**Root cause:** `_record_failure()` increments `failure_count` without lock:
```python
def _record_failure(self):
    self.failure_count += 1  # Race: read-modify-write
    if self.failure_count >= self.max_failures:
        self.state = CircuitState.OPEN  # Race: state transition
```

### 2. Blackboard Tests

#### `test_concurrent_read_modify_write_race`
**What it tests:** 10 concurrent increments to a counter stored in BlackboardState.

**Expected behavior:** Counter should equal 10 after 10 increments.

**Current failure:**
```
AssertionError: Expected counter=10, got 1.
Lost updates due to read-modify-write race condition.
```

**Root cause:** Non-atomic read-modify-write pattern:
```python
current = state["counter"]  # Read
await asyncio.sleep(...)    # Race window
state["counter"] = current + 1  # Write (overwrites concurrent updates)
```

### 3. Hierarchical Tests

#### `test_concurrent_ensure_coordinator_single_spawn`
**What it tests:** 5 concurrent `_ensure_coordinator()` calls.

**Expected behavior:** Only 1 coordinator should be spawned.

**Current failure:**
```
AssertionError: Expected 1 spawn call, got 5.
Multiple coordinators were spawned due to race condition.
```

**Root cause:** Check-then-act pattern without lock:
```python
if self.coordinator is None:  # Check (all 5 pass)
    self.coordinator = await spawn(...)  # Act (all 5 spawn)
```

#### `test_concurrent_ensure_specialist_single_spawn`
**What it tests:** 5 concurrent `_ensure_specialist('researcher')` calls.

**Expected behavior:** Only 1 specialist should be spawned.

**Current failure:**
```
AssertionError: Expected 1 spawn call, got 5.
Multiple specialists were spawned due to race condition.
```

**Root cause:** Same check-then-act pattern:
```python
if name not in self.specialists:  # Check (all 5 pass)
    self.specialists[name] = await spawn(...)  # Act (all 5 spawn)
```

#### `test_concurrent_execute_tasks_share_coordinator`
**What it tests:** 3 concurrent `execute()` calls should share 1 coordinator.

**Expected behavior:** Only 1 coordinator spawn across all executions.

**Current failure:**
```
AssertionError: Expected 1 coordinator spawn, got 3.
Race condition in _ensure_coordinator.
```

## Implementation Required to Pass Tests

### CircuitBreaker Fix

Add `asyncio.Lock()` to protect state mutations:

```python
class CircuitBreaker:
    def __init__(self, ...):
        self._state_lock = asyncio.Lock()

    async def _record_failure(self):
        async with self._state_lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.max_failures:
                self.state = CircuitState.OPEN
            elif self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN

    async def _record_success(self):
        async with self._state_lock:
            self.failure_count = 0
            self.state = CircuitState.CLOSED
            self.last_failure_time = None
```

### Blackboard Fix

Add `asyncio.Lock()` to `BlackboardState`:

```python
class BlackboardState:
    def __init__(self):
        self._data: dict[str, Any] = {}
        self.history: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def set_item(self, key: str, value: Any) -> None:
        async with self._lock:
            self._data[key] = value
            self.history.append({"action": "set", "key": key, "value": value})

    async def get_item(self, key: str) -> Any:
        async with self._lock:
            return self._data[key]
```

### Hierarchical Fix

Add `asyncio.Lock()` for lazy initialization:

```python
class Hierarchical:
    def __init__(self, ...):
        self._coordinator_lock = asyncio.Lock()
        self._specialist_locks: dict[str, asyncio.Lock] = {}

    async def _ensure_coordinator(self):
        async with self._coordinator_lock:
            if self.coordinator is None:
                # spawn coordinator
                pass

    async def _ensure_specialist(self, name: str):
        # Get or create lock for this specialist name
        if name not in self._specialist_locks:
            self._specialist_locks[name] = asyncio.Lock()

        async with self._specialist_locks[name]:
            if name not in self.specialists:
                # spawn specialist
                pass
```

## Running the Tests

```bash
# Run all concurrency tests
uv run pytest tests/unit/test_pattern_concurrency.py -v

# Run specific pattern tests
uv run pytest tests/unit/test_pattern_concurrency.py::TestCircuitBreakerConcurrency -v
uv run pytest tests/unit/test_pattern_concurrency.py::TestBlackboardConcurrency -v
uv run pytest tests/unit/test_pattern_concurrency.py::TestHierarchicalConcurrency -v
```

## Notes

- Tests use `asyncio.sleep()` delays to widen the race window
- Tests mock `spawn()` to avoid requiring the actual agentica library
- Some tests pass due to CPython's GIL making simple dict operations atomic
- The `test_concurrent_read_modify_write_race` explicitly tests the read-modify-write pattern where GIL atomicity doesn't help

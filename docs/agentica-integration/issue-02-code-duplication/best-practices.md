# Best Practices: Eliminating Code Duplication via Python Abstractions

Generated: 2025-12-29

## Executive Summary

This research covers Python patterns for eliminating ~300 lines of code duplication between two functions that differ only in caching strategy. The recommended approach combines Protocol types for interface definition, the Strategy pattern for pluggable behavior, and Factory functions for creation. The codebase already implements this pattern correctly via `CacheManager` Protocol - this document captures the best practices for future reference.

## Research Context

**Problem:** `_create_file_ops_with_shared()` and `_create_file_ops_default()` in `unified_scope.py` originally contained ~300 lines of identical logic, differing only in:
- `SharedContext` (thread-safe, inter-agent cache) vs
- Local `dict` (single-agent, no synchronization)

**Solution (Already Implemented):** The codebase now uses:
1. `CacheManager` Protocol (line 43-81 in unified_scope.py)
2. `LocalCacheManager` concrete class (line 83-130)
3. Single `_create_file_ops(cache_manager)` factory (line 154+)

---

## Key Pattern 1: Python Protocol Types (PEP 544)

### When to Use Protocol

Protocols enable structural typing ("duck typing with type hints"). Use them when:

- Third-party classes (like `SharedContext`) already have the methods you need
- You want interface compliance without inheritance
- Static type checkers should validate compatibility
- Runtime `isinstance()` checks are NOT required

### Protocol Definition Pattern

```python
from typing import Protocol, Any

class CacheManager(Protocol):
    """Protocol for cache/log operations in file ops factory.

    This protocol defines the interface that both SharedContext and
    LocalCacheManager implement, enabling a single _create_file_ops()
    factory to work with either caching strategy.
    """

    def get_cached(self, path: str) -> ClaudeResult | None:
        """Get cached result for path, or None if not cached."""
        ...

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        """Cache result for path."""
        ...

    def invalidate(self, path: str) -> None:
        """Invalidate cache entry for path (if exists)."""
        ...

    def log_operation(self, operation: dict[str, Any]) -> None:
        """Log an operation."""
        ...

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        """Get copy of all cached results."""
        ...

    def get_all_operations(self) -> list[dict[str, Any]]:
        """Get copy of all logged operations."""
        ...

    def clear_cache(self) -> None:
        """Clear all cached results."""
        ...
```

### Why Protocol Over ABC

| Feature | Protocol | ABC |
|---------|----------|-----|
| Existing class compatibility | Yes (structural) | No (requires inheritance) |
| Default implementations | No | Yes |
| Runtime isinstance checks | @runtime_checkable needed | Built-in |
| Type checker support | Full | Full |

**For this codebase:** Protocol is correct because `SharedContext` already exists with the right methods. We don't want to force it to inherit from an abstract base class.

---

## Key Pattern 2: Strategy Pattern for Pluggable Behavior

### The Pattern

```
Context (file ops) --uses--> Strategy (CacheManager)
                                    |
                  +-----------------+-----------------+
                  |                                   |
     SharedCacheManager                      LocalCacheManager
     (thread-safe, shared)                   (simple, isolated)
```

### Concrete Implementation

```python
class LocalCacheManager:
    """Cache manager with local dict storage for single-agent use.

    Not thread-safe - intentionally designed for single-agent contexts
    where SharedContext's locking overhead is unnecessary.
    """

    def __init__(self, cache_reads: bool = True):
        self._cache_reads = cache_reads
        self._cache: dict[str, ClaudeResult] = {}
        self._operations: list[dict[str, Any]] = []

    def get_cached(self, path: str) -> ClaudeResult | None:
        if not self._cache_reads:
            return None
        return self._cache.get(path)

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        if self._cache_reads:
            self._cache[path] = result

    def invalidate(self, path: str) -> None:
        self._cache.pop(path, None)

    def log_operation(self, operation: dict[str, Any]) -> None:
        self._operations.append(operation)

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        return dict(self._cache)

    def get_all_operations(self) -> list[dict[str, Any]]:
        return list(self._operations)

    def clear_cache(self) -> None:
        self._cache.clear()
```

### Strategy Benefits

1. **Open/Closed Principle:** Add new caching strategies without modifying existing code
2. **Single Responsibility:** Each strategy handles only its caching logic
3. **Testability:** Test strategies in isolation with simple unit tests
4. **Swappability:** Change strategy at runtime without code changes

---

## Key Pattern 3: Factory Pattern with Dependency Injection

### Simple Factory Function

```python
def _create_file_ops(
    cache_manager: CacheManager,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file operations with pluggable cache manager.

    This is the unified implementation that handles all caching strategies.
    The cache_manager parameter determines whether caching uses shared
    context (inter-agent, thread-safe) or local dict (single agent).

    Args:
        cache_manager: CacheManager implementation (SharedContext or LocalCacheManager)
        project_dir: Optional project directory for path validation

    Returns:
        Dict of file operation functions
    """
    # All file operations use cache_manager.get_cached(), set_cached(), etc.
    # Single implementation, no duplication
```

### Thin Wrappers for Backward Compatibility

```python
def _create_file_ops_with_shared(
    shared: SharedContext,
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file ops with shared context (existing API)."""
    # SharedContext already implements CacheManager protocol
    return _create_file_ops(shared, project_dir)


def _create_file_ops_default(
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file ops with local caching (existing API)."""
    return _create_file_ops(LocalCacheManager(cache_reads), project_dir)
```

---

## Key Pattern 4: Type-Safe Abstractions in Python 3.11+

### Modern Python Features Used

1. **Union Type Syntax:** `str | None` instead of `Optional[str]`
2. **Protocol Types:** Structural subtyping (PEP 544)
3. **Type Parameter Defaults:** Available in Python 3.13+ for generic protocols
4. **dataclass:** For immutable value objects like `ClaudeResult`

### Type Checking Configuration

```python
# pyproject.toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_ignores = true
```

### Verifying Protocol Compliance

```python
from typing import assert_type

# Type checker validates SharedContext satisfies CacheManager
def test_shared_context_is_cache_manager(ctx: SharedContext) -> None:
    cache: CacheManager = ctx  # Type checker validates this
```

---

## DRY Principle Applied

### Before Refactoring

```
_create_file_ops_with_shared()  ~300 lines
_create_file_ops_default()      ~300 lines
                                ========
Total                           ~600 lines (50% duplicate)
```

### After Refactoring

```
CacheManager Protocol            ~30 lines
LocalCacheManager                ~45 lines
_create_file_ops()              ~250 lines
Wrapper functions                ~10 lines
                                ========
Total                           ~335 lines (0% duplicate)
```

### Reduction: 44% fewer lines, 100% less duplication

---

## Testing Strategy

### Unit Tests for Cache Managers

```python
def test_local_cache_manager_get_set():
    mgr = LocalCacheManager(cache_reads=True)
    result = ClaudeResult(success=True, operation="read", path="/test")

    assert mgr.get_cached("/test") is None  # Not cached yet
    mgr.set_cached("/test", result)
    assert mgr.get_cached("/test") == result  # Now cached


def test_local_cache_manager_caching_disabled():
    mgr = LocalCacheManager(cache_reads=False)
    result = ClaudeResult(success=True, operation="read", path="/test")

    mgr.set_cached("/test", result)
    assert mgr.get_cached("/test") is None  # Caching disabled
```

### Unit Tests for File Operations

```python
def test_read_file_uses_cache():
    mock_cache = Mock(spec=CacheManager)
    mock_cache.get_cached.return_value = ClaudeResult(
        success=True, operation="read", path="/test", content="cached"
    )

    ops = _create_file_ops(mock_cache)
    result = ops["read_file"]("/test")

    assert result["cached"] is True
    assert result["content"] == "cached"
    mock_cache.get_cached.assert_called_once_with("/test")
```

---

## Sources

1. **PEP 544 - Protocols: Structural subtyping (static duck typing)**
   - https://peps.python.org/pep-0544/

2. **Python typing documentation - Protocol**
   - https://docs.python.org/3/library/typing.html#typing.Protocol

3. **Design Patterns: Elements of Reusable Object-Oriented Software**
   - Gamma et al. (Gang of Four) - Strategy Pattern chapter

4. **Clean Code** by Robert C. Martin
   - Chapter 10: Classes, DRY principle

5. **Effective Python, 3rd Edition** by Brett Slatkin
   - Item 43: Inherit from collections.abc for Custom Container Types

---

## Recommendations for Similar Refactorings

1. **Identify the Variance:** What differs between duplicate functions? (caching strategy)

2. **Extract Interface:** Define Protocol with methods that capture the variance

3. **Implement Strategies:** Create concrete classes implementing the protocol

4. **Unify Logic:** Single function accepting the protocol type

5. **Wrap for Compatibility:** Thin wrappers maintain existing API

6. **Test at Each Layer:**
   - Strategy implementations in isolation
   - Unified function with mock strategies
   - Wrappers with integration tests

---

## Open Questions

1. **Cache Eviction:** Should CacheManager include TTL or LRU eviction?

2. **Metrics:** Track cache hit/miss rates for debugging?

3. **Async Support:** Should there be an AsyncCacheManager protocol for async file ops?

4. **Thread Safety:** LocalCacheManager intentionally not thread-safe - document this clearly

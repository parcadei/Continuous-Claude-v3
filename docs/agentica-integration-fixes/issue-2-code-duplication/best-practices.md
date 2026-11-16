# Best Practices: Eliminating Code Duplication via Abstraction in Python

Generated: 2025-12-29

## Executive Summary

This document provides research-backed best practices for eliminating code duplication in Python through abstraction patterns. The focus is on Strategy Pattern for pluggable caching, Protocol/ABC patterns for interface definition, Factory Pattern implementation, and DRY principle application. These patterns are directly applicable to refactoring the `unified_scope.py` code duplication issue.

## Research Question

How to eliminate code duplication between `_create_file_ops_with_shared()` and `_create_file_ops_default()` functions that differ only in their caching strategy (SharedContext vs local dict)?

## Key Findings

### Finding 1: Strategy Pattern for Pluggable Caching

The Strategy Pattern is the most appropriate pattern for this use case. It allows defining a family of algorithms (caching strategies), encapsulating each one, and making them interchangeable.

**Python Implementation Pattern:**

```python
from typing import Protocol, TypeVar, Generic
from dataclasses import dataclass

T = TypeVar('T')

class CacheStrategy(Protocol[T]):
    """Protocol defining the cache interface."""

    def get(self, key: str) -> T | None:
        """Retrieve cached value or None if not present."""
        ...

    def set(self, key: str, value: T) -> None:
        """Store value in cache."""
        ...

    def clear(self) -> None:
        """Clear all cached entries."""
        ...

    def get_all(self) -> dict[str, T]:
        """Get all cached entries."""
        ...
```

**Key Benefits:**
- Swappable implementations without changing client code
- Easy to test with mock strategies
- Open/Closed principle: new strategies without modifying existing code
- Source: Python Design Patterns (Gang of Four adapted for Python)

### Finding 2: Python Protocol vs ABC Patterns

**Use Protocol (PEP 544 - Structural Subtyping) when:**
- You want duck typing with static type checking
- Third-party classes need to satisfy the interface
- No implementation sharing needed
- Runtime isinstance checks not required

**Use ABC when:**
- You need to share default implementations
- Runtime isinstance/issubclass checks are needed
- You want to enforce method implementation at class creation

**Recommended for Cache Manager: Protocol**

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class CacheManager(Protocol):
    """Cache manager protocol for file operations."""

    def get_cached(self, path: str) -> ClaudeResult | None: ...
    def set_cached(self, path: str, result: ClaudeResult) -> None: ...
    def get_all_cached(self) -> dict[str, ClaudeResult]: ...
    def clear_cache(self) -> None: ...
    def log_operation(self, entry: dict) -> None: ...
    def get_all_operations(self) -> list[dict]: ...
```

**Why Protocol over ABC:**
- SharedContext already exists - Protocol allows it to satisfy interface without inheritance
- Cleaner for structural typing in Python 3.12+
- No need for shared implementation between cache managers
- Source: PEP 544, Python typing documentation

### Finding 3: Factory Pattern Best Practices

The Factory Pattern should be used to create the appropriate cache manager based on context.

**Simple Factory Function (Recommended for this case):**

```python
def create_cache_manager(
    shared: SharedContext | None = None,
    cache_reads: bool = True
) -> CacheManager:
    """Factory function to create appropriate cache manager.

    Args:
        shared: SharedContext for inter-agent caching, or None for local
        cache_reads: Whether to cache read operations

    Returns:
        CacheManager implementation
    """
    if shared is not None:
        return SharedCacheManager(shared, cache_reads)
    return LocalCacheManager(cache_reads)
```

**Factory Pattern Guidelines:**
1. Keep factory logic simple - it should only decide WHICH to create
2. Let the created objects handle their own complexity
3. Return interfaces/protocols, not concrete classes
4. Factory functions over Factory classes for simple cases
5. Source: "Clean Code" by Robert C. Martin, Python best practices

### Finding 4: DRY Principle Implementation Patterns

**The Rule of Three:**
- Duplicate once: maybe acceptable
- Duplicate twice: refactor immediately
- Current situation: 300+ lines duplicated = critical refactor needed

**Extraction Strategies:**

1. **Parameterized Behavior (Best for this case):**
```python
def _create_file_ops(cache_manager: CacheManager, project_dir: str | None = None):
    """Single implementation with pluggable cache manager."""

    def read_file(path: str) -> dict[str, Any]:
        path = _canonicalize_path(path, project_dir)

        cached = cache_manager.get_cached(path)
        if cached:
            return {"success": True, "path": path, "content": cached.content, "cached": True}

        # ... rest of implementation

        cache_manager.set_cached(path, result)
        cache_manager.log_operation({"operation": "read", "path": path, "success": True})

        return {"success": True, "path": path, "content": response, "cached": False}

    # ... other operations

    return {
        "read_file": read_file,
        "write_file": write_file,
        # ...
    }
```

2. **Thin Wrapper Pattern:**
```python
# Keep original function signatures for backward compatibility
def _create_file_ops_with_shared(
    shared: SharedContext,
    cache_reads: bool = True,
    project_dir: str | None = None
) -> dict[str, Any]:
    """Create file ops with shared context (backward compatible)."""
    manager = SharedCacheManager(shared, cache_reads)
    return _create_file_ops(manager, project_dir)

def _create_file_ops_default(
    cache_reads: bool = True,
    project_dir: str | None = None
) -> dict[str, Any]:
    """Create file ops with local cache (backward compatible)."""
    manager = LocalCacheManager(cache_reads)
    return _create_file_ops(manager, project_dir)
```

## Concrete Implementation Recommendation

### Step 1: Define the Protocol

```python
# cache_protocol.py or at top of unified_scope.py

from typing import Protocol
from dataclasses import dataclass

@dataclass
class ClaudeResult:
    success: bool
    operation: str
    path: str
    content: str | None
    raw_response: str | None = None

class CacheManager(Protocol):
    """Protocol for cache management in file operations."""

    def get_cached(self, path: str) -> ClaudeResult | None:
        """Get cached result for path."""
        ...

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        """Cache result for path."""
        ...

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        """Get all cached results."""
        ...

    def clear_cache(self) -> None:
        """Clear all cached results."""
        ...

    def log_operation(self, entry: dict) -> None:
        """Log an operation."""
        ...

    def get_all_operations(self) -> list[dict]:
        """Get all logged operations."""
        ...
```

### Step 2: Implement Concrete Cache Managers

```python
class SharedCacheManager:
    """Cache manager that uses SharedContext for inter-agent caching."""

    def __init__(self, shared: SharedContext, cache_reads: bool = True):
        self._shared = shared
        self._cache_reads = cache_reads

    def get_cached(self, path: str) -> ClaudeResult | None:
        if not self._cache_reads:
            return None
        return self._shared.get_cached(path)

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        if self._cache_reads:
            self._shared.set_cached(path, result)

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        return self._shared.get_all_cached()

    def clear_cache(self) -> None:
        self._shared.clear_cache()

    def log_operation(self, entry: dict) -> None:
        self._shared.log_operation(entry)

    def get_all_operations(self) -> list[dict]:
        return self._shared.get_all_operations()


class LocalCacheManager:
    """Cache manager with local dict storage (no sharing)."""

    def __init__(self, cache_reads: bool = True):
        self._cache_reads = cache_reads
        self._cache: dict[str, ClaudeResult] = {}
        self._operations: list[dict] = []

    def get_cached(self, path: str) -> ClaudeResult | None:
        if not self._cache_reads:
            return None
        return self._cache.get(path)

    def set_cached(self, path: str, result: ClaudeResult) -> None:
        if self._cache_reads:
            self._cache[path] = result

    def get_all_cached(self) -> dict[str, ClaudeResult]:
        return dict(self._cache)

    def clear_cache(self) -> None:
        self._cache.clear()

    def log_operation(self, entry: dict) -> None:
        self._operations.append(entry)

    def get_all_operations(self) -> list[dict]:
        return list(self._operations)
```

### Step 3: Unified File Operations Factory

```python
def _create_file_ops(
    cache_manager: CacheManager,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file operations with pluggable cache manager.

    This is the single implementation that handles all caching strategies.
    The cache_manager parameter determines whether caching uses shared
    context (inter-agent) or local dict (single agent).
    """

    def read_file(path: str) -> dict[str, Any]:
        """Read a file using Claude CLI."""
        try:
            path = _canonicalize_path(path, project_dir)
        except ValueError as e:
            return {"success": False, "path": path, "content": None, "error": str(e)}

        cached = cache_manager.get_cached(path)
        if cached:
            return {
                "success": cached.success,
                "path": cached.path,
                "content": cached.content,
                "cached": True,
            }

        prompt = f"""Read the file at: {path}

Return the file content. If the file doesn't exist, explain the error."""

        try:
            response = _call_claude_cli(prompt, ["Read"])

            result = ClaudeResult(
                success=True,
                operation="read",
                path=path,
                content=response,
                raw_response=response,
            )

            cache_manager.set_cached(path, result)
            cache_manager.log_operation({
                "operation": "read",
                "path": path,
                "success": True,
            })

            return {
                "success": True,
                "path": path,
                "content": response,
                "cached": False,
            }

        except Exception as e:
            cache_manager.log_operation({
                "operation": "read",
                "path": path,
                "success": False,
                "error": str(e),
            })
            return {
                "success": False,
                "path": path,
                "content": None,
                "error": str(e),
            }

    # ... write_file, edit_file, bash, grep, glob_search ...
    # All follow same pattern: use cache_manager instead of direct access

    def debug_get_cache() -> dict[str, ClaudeResult]:
        return cache_manager.get_all_cached()

    def debug_get_operation_log() -> list[dict]:
        return cache_manager.get_all_operations()

    def debug_clear_cache() -> None:
        cache_manager.clear_cache()

    return {
        "read_file": read_file,
        "write_file": write_file,
        "edit_file": edit_file,
        "bash": bash,
        "grep": grep,
        "glob": glob_search,
        "debug_get_cache": debug_get_cache,
        "debug_get_operation_log": debug_get_operation_log,
        "debug_clear_cache": debug_clear_cache,
    }


# Backward-compatible wrappers
def _create_file_ops_with_shared(
    shared: SharedContext,
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file operations with shared context (backward compatible)."""
    return _create_file_ops(SharedCacheManager(shared, cache_reads), project_dir)


def _create_file_ops_default(
    cache_reads: bool = True,
    project_dir: str | None = None,
) -> dict[str, Any]:
    """Create file operations with local cache (backward compatible)."""
    return _create_file_ops(LocalCacheManager(cache_reads), project_dir)
```

## Sources

1. **PEP 544 - Protocols: Structural subtyping (static duck typing)**
   - https://peps.python.org/pep-0544/
   - Official Python specification for Protocol type

2. **Python typing documentation - Protocols**
   - https://docs.python.org/3/library/typing.html#typing.Protocol
   - Standard library documentation

3. **Design Patterns: Elements of Reusable Object-Oriented Software**
   - Gang of Four (Gamma, Helm, Johnson, Vlissides)
   - Strategy Pattern, Factory Pattern definitions

4. **Clean Code: A Handbook of Agile Software Craftsmanship**
   - Robert C. Martin
   - DRY principle, extraction patterns

5. **Effective Python: 90 Specific Ways to Write Better Python**
   - Brett Slatkin
   - Python-specific abstraction patterns

## Recommendations

1. **Use Protocol over ABC** - SharedContext already exists; Protocol allows structural typing without modifying it

2. **Implement Strategy Pattern** - Create `CacheManager` protocol with `SharedCacheManager` and `LocalCacheManager` implementations

3. **Single Factory Function** - One `_create_file_ops(cache_manager)` replaces two duplicate functions

4. **Maintain Backward Compatibility** - Keep thin wrapper functions that create appropriate manager and delegate

5. **Test Each Layer:**
   - Unit test cache managers independently
   - Unit test file operations with mock cache manager
   - Integration test wrappers

## Impact Assessment

| Metric | Before | After |
|--------|--------|-------|
| Lines of Code | ~600 (duplicated) | ~350 (unified) |
| Maintenance Points | 2 (parallel changes needed) | 1 |
| Test Surface | 2x (each path) | 1x + strategy tests |
| Extension Difficulty | High (copy-paste) | Low (new strategy class) |

## Open Questions

1. **Thread Safety:** Does `LocalCacheManager` need thread-safe operations? The current local dict implementation is not thread-safe, but that may be intentional for single-agent use.

2. **Cache Expiration:** Should the protocol include TTL or invalidation methods for future cache strategies?

3. **Metrics/Observability:** Should cache hits/misses be tracked for debugging? Could be added to the protocol.

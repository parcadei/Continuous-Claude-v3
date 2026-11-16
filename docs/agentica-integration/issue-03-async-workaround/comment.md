# Issue 03: Complex Async Workaround with ThreadPoolExecutor

**Severity:** MINOR (Style/Performance)
**File:** `scripts/agentica/unified_scope.py`
**Lines:** 34-56, 709-712

## Summary

The code uses `ThreadPoolExecutor` to handle nested event loops, adding significant overhead for every async call. This creates unnecessary thread churn for high-frequency memory operations.

## Current Code (Lines 34-56)

The `_run_async` function creates a new thread for every async operation to work around nested event loop issues.

## CodeRabbit Proposed Fix

Simpler approach - fail fast when called from async context rather than working around it:

```python
def _run_async(coro):
    """Run an async coroutine synchronously."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # Already in async context - should not happen in normal usage
        raise RuntimeError(
            "Cannot use unified_scope from within async context. "
            "Use async variants or refactor to avoid nesting."
        )
```

## Alternative Considerations

1. Async-first API design
2. Connection pooling strategy
3. Lazy initialization to reduce startup overhead
4. Document expected usage patterns (sync vs async contexts)

## Fix Requirements

1. Evaluate if ThreadPoolExecutor workaround is actually needed
2. If not, simplify to fail-fast approach
3. If yes, document why and consider connection pooling
4. Add performance notes to docstrings

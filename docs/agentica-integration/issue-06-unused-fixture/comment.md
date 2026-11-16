# Issue 06: Unused mock_spawn Fixture

**Severity:** MINOR
**File:** `tests/unit/test_crud_patterns_batch2.py`
**Lines:** 522-543

## Summary

The `mock_spawn` fixture is declared in the method signature but never used in the test body. This means the actual `spawn` function would be called if any handler matched. While the test expects no handler to match, having the mock ensures isolation.

## Current Code

```python
@pytest.mark.asyncio
async def test_raises_error_when_no_handler_matches(self, mock_spawn):
    """If no handler can handle the request, should raise an error."""
    from scripts.agentica.patterns import ChainOfResponsibility, Handler

    # ... test setup ...

    # Query that matches neither
    with pytest.raises(ValueError, match="No handler"):
        await chain.process("What is the meaning of life?")

    # mock_spawn never used!
```

## Proposed Fix

```python
@pytest.mark.asyncio
async def test_raises_error_when_no_handler_matches(self, mock_spawn):
    """If no handler can handle the request, should raise an error."""
    from scripts.agentica.patterns import ChainOfResponsibility, Handler

    # ... test setup ...

    # Query that matches neither
    with pytest.raises(ValueError, match="No handler"):
        await chain.process("What is the meaning of life?")

    mock_spawn.assert_not_called()
```

## Fix Requirements

1. Add `mock_spawn.assert_not_called()` after the test
2. This documents and enforces that no spawn occurred

# Minor Test Issues Fix Plan

Generated: 2025-12-29

## Goal

Fix 5 minor test quality issues (Issues 3-7) that involve unused variables, weak assertions, and missing mock verifications. All fixes are quick and localized.

## Summary

| Issue | File | Line(s) | Problem | Fix Type |
|-------|------|---------|---------|----------|
| 3 | test_unified_scope_e2e.py | 583 | Unused asyncio.Lock() | Remove dead code |
| 4 | test_crud_patterns_batch2.py | 145-148 | Weak assertion (always passes) | Strengthen assertion |
| 5 | test_crud_patterns_batch2.py | 522-543 | Unused mock fixture | Add mock verification |
| 6 | test_crud_patterns_batch2.py | 780-786 | Weak prompt assertion | Strengthen assertion |
| 7 | test_unified_scope.py | 124 | Unused variable result_b | Add assertion |

---

## Issue 3: Remove Unused asyncio.Lock()

**File:** `tests/integration/test_unified_scope_e2e.py`
**Line:** 583

### Current Code (lines 580-584)
```python
        num_agents = 5
        tasks_per_agent = 5
        all_task_ids: list[str] = []
        lock = asyncio.Lock()
        errors: list[Exception] = []
```

### Fixed Code
```python
        num_agents = 5
        tasks_per_agent = 5
        all_task_ids: list[str] = []
        errors: list[Exception] = []
```

### Rationale
The `lock` variable is never used. The test uses threads (via `ThreadPoolExecutor`), not async coroutines, so an `asyncio.Lock` would not provide synchronization anyway.

---

## Issue 4: Fix Weak Assertion That Always Passes

**File:** `tests/unit/test_crud_patterns_batch2.py`
**Lines:** 145-148

### Current Code
```python
        # Reducer should have been called
        assert reducer_prompt is not None
        # Final result should be from reducer
        assert "combined" in result.lower() or result is not None
```

### Fixed Code
```python
        # Reducer should have been called
        assert reducer_prompt is not None
        # Final result should be from reducer (verify it contains expected content)
        assert result is not None
        assert "combined" in result.lower(), f"Expected 'combined' in result, got: {result}"
```

### Rationale
The original assertion `"combined" in result.lower() or result is not None` always passes because `result` is never `None` (it comes from `await mr.execute(...)`). Separating the assertions ensures we actually verify the expected content.

---

## Issue 5: Add Mock Verification for Unused Fixture

**File:** `tests/unit/test_crud_patterns_batch2.py`
**Lines:** 522-543

### Current Code (test function)
```python
    @pytest.mark.asyncio
    async def test_raises_error_when_no_handler_matches(self, mock_spawn):
        """If no handler can handle the request, should raise an error."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        chain = ChainOfResponsibility(
            handlers=[
                Handler(
                    premise="You handle Python questions.",
                    can_handle=lambda q: "python" in q.lower(),
                ),
                Handler(
                    premise="You handle JavaScript questions.",
                    can_handle=lambda q: "javascript" in q.lower(),
                ),
            ]
        )

        # Query that matches neither
        with pytest.raises(ValueError, match="No handler"):
            await chain.process("What is the meaning of life?")
```

### Fixed Code
```python
    @pytest.mark.asyncio
    async def test_raises_error_when_no_handler_matches(self, mock_spawn):
        """If no handler can handle the request, should raise an error."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        chain = ChainOfResponsibility(
            handlers=[
                Handler(
                    premise="You handle Python questions.",
                    can_handle=lambda q: "python" in q.lower(),
                ),
                Handler(
                    premise="You handle JavaScript questions.",
                    can_handle=lambda q: "javascript" in q.lower(),
                ),
            ]
        )

        # Query that matches neither
        with pytest.raises(ValueError, match="No handler"):
            await chain.process("What is the meaning of life?")

        # Verify no spawn was attempted since no handler matched
        mock_spawn.assert_not_called()
```

### Rationale
The `mock_spawn` fixture ensures test isolation, but adding an explicit assertion documents the expected behavior: when no handler matches, no spawn should occur.

---

## Issue 6: Strengthen Prompt Reliability Assertion

**File:** `tests/unit/test_crud_patterns_batch2.py`
**Lines:** 780-786

### Current Code
```python
        await bb.solve("Build auth system")

        # Designer should see requirements in prompt
        if captured_prompts:
            all_prompts = " ".join(captured_prompts)
            # The prompt should reference requirements or contain state info
            assert len(all_prompts) > 0
```

### Fixed Code
```python
        await bb.solve("Build auth system")

        # Designer should see requirements in prompt
        assert captured_prompts, "Expected prompts to be captured"
        all_prompts = " ".join(captured_prompts)
        # The prompt should reference requirements data from reads_from
        assert "requirements" in all_prompts.lower() or "user auth" in all_prompts.lower(), \
            f"Expected requirements context in prompt, got: {all_prompts[:200]}"
```

### Rationale
1. The `if captured_prompts:` silently passes when no prompts are captured, which could hide bugs
2. `assert len(all_prompts) > 0` only checks non-empty, not actual content
3. The test's purpose is to verify `reads_from=["requirements"]` works, so we should check for "requirements" or the actual data "user auth"

---

## Issue 7: Add Assertion for Unused Variable result_b

**File:** `tests/unit/test_unified_scope.py`
**Lines:** 123-128

### Current Code
```python
        # Session B should not see session A's memory
        result_b = scope_b["recall"]("secret_key")
        # But recall in session A should work
        result_a = scope_a["recall"]("secret_key")

        assert "secret_value_a" in result_a, "Session A should recall its own memory"
```

### Fixed Code
```python
        # Session B should not see session A's memory
        result_b = scope_b["recall"]("secret_key")
        assert "secret_value_a" not in result_b, "Session B should not see A's memory immediately"

        # But recall in session A should work
        result_a = scope_a["recall"]("secret_key")

        assert "secret_value_a" in result_a, "Session A should recall its own memory"
```

### Rationale
The `result_b` variable was computed but never verified. Adding this assertion tests memory isolation at the point where `scope_b` was created (before `scope_b_fresh`), catching isolation bugs earlier.

---

## Implementation Order

All fixes are independent and can be applied in any order. Suggested sequence:

1. Issue 3 - Simple deletion (lowest risk)
2. Issue 7 - Add assertion (simple addition)
3. Issue 5 - Add mock verification (simple addition)
4. Issue 4 - Fix weak assertion (behavior change)
5. Issue 6 - Strengthen assertion (behavior change, may need adjustment)

## Verification

After applying all fixes:

```bash
# Run affected test files
uv run pytest tests/integration/test_unified_scope_e2e.py -v
uv run pytest tests/unit/test_crud_patterns_batch2.py -v
uv run pytest tests/unit/test_unified_scope.py -v

# Or run all tests
uv run pytest tests/ -v
```

## Risks

- **Issue 6**: The assertion may fail if the blackboard pattern doesn't include "requirements" in prompts as expected. If so, examine the actual prompt content to determine the correct assertion.
- **Issue 4**: If the reducer doesn't return "combined" in its response, the test will fail. Verify the mock setup produces expected output.

## Estimated Effort

Total: ~15 minutes

- Issue 3: 2 minutes (delete one line)
- Issue 4: 3 minutes (split and strengthen assertion)
- Issue 5: 2 minutes (add one assertion)
- Issue 6: 5 minutes (strengthen assertion, may need debugging)
- Issue 7: 3 minutes (add one assertion)

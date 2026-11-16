# Issue 07: Weak Prompt Reliability Assertion

**Severity:** MINOR
**File:** `tests/unit/test_crud_patterns_batch2.py`
**Lines:** 780-786

## Summary

The test verifies that specialists see state they depend on, but the assertion only checks that prompts are non-empty. This doesn't validate that the `requirements` key (from `reads_from`) is actually included in the designer's prompt.

## Current Code

```python
# Designer should see requirements in prompt
if captured_prompts:
    all_prompts = " ".join(captured_prompts)
    # The prompt should reference requirements or contain state info
    assert len(all_prompts) > 0
```

## Proposed Fix

```python
# Designer should see requirements in prompt
if captured_prompts:
    all_prompts = " ".join(captured_prompts)
    # The prompt should reference requirements data
    assert "requirements" in all_prompts.lower() or "user auth" in all_prompts.lower(), \
        f"Expected requirements context in prompt, got: {all_prompts[:200]}"
```

## Fix Requirements

1. Replace length check with actual content verification
2. Check for expected requirements content in prompts
3. Add failure message showing actual prompt content

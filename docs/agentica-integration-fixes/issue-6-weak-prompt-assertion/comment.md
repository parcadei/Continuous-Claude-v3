# Issue 6: Weak Prompt Reliability Assertion (MINOR)

## Location
- `tests/unit/test_crud_patterns_batch2.py` lines 780-786

## Description
The test verifies that specialists see state they depend on, but the assertion only checks that prompts are non-empty. This doesn't validate that the `requirements` key (from `reads_from`) is actually included in the designer's prompt.

## Proposed Fix
```diff
         # Designer should see requirements in prompt
         if captured_prompts:
             all_prompts = " ".join(captured_prompts)
-            # The prompt should reference requirements or contain state info
-            assert len(all_prompts) > 0
+            # The prompt should reference requirements data
+            assert "requirements" in all_prompts.lower() or "user auth" in all_prompts.lower(), \
+                f"Expected requirements context in prompt, got: {all_prompts[:200]}"
```

## Impact
- Test doesn't verify core functionality (state passing between specialists)
- Could miss regressions in prompt construction

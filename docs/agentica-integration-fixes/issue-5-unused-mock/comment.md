# Issue 5: Unused Mock Fixture (MINOR)

## Location
- `tests/unit/test_crud_patterns_batch2.py` lines 522-543

## Description
The `mock_spawn` fixture is declared in the method signature but never used in the test body. This means the actual `spawn` function would be called if any handler matched. While the test expects no handler to match, having the mock ensures isolation.

## Proposed Fix
```diff
     @pytest.mark.asyncio
-    async def test_raises_error_when_no_handler_matches(self, mock_spawn):
+    async def test_raises_error_when_no_handler_matches(self, mock_spawn):  # noqa: ARG002
         """If no handler can handle the request, should raise an error."""
         # ... test code ...
         with pytest.raises(ValueError, match="No handler"):
             await chain.process("What is the meaning of life?")
+
+        mock_spawn.assert_not_called()
```

## Impact
- Test not fully isolated from real spawn function
- Missing assertion that no spawn occurred

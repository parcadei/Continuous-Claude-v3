# Issue 7: Unused Variable in Memory Test (MINOR)

## Location
- `tests/unit/test_unified_scope.py` lines 110-134

## Description
Line 124 assigns `result_b` but never uses it. The test only verifies isolation using `scope_b_fresh` (line 133). Either add an assertion on `result_b` to verify immediate isolation, or remove the unused assignment.

## Proposed Fix
```diff
         # Session B should not see session A's memory
         result_b = scope_b["recall"]("secret_key")
+        assert "secret_value_a" not in result_b, "Session B should not see A's memory"
+
         # But recall in session A should work
         result_a = scope_a["recall"]("secret_key")
```

## Impact
- Missing assertion that could catch memory isolation bugs
- Dead code that suggests incomplete test

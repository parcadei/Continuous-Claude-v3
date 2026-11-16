# Implementation Plan: Code Duplication Refactor - Remaining Linting Fixes

Generated: 2025-12-29

## Goal

Address the remaining CodeRabbit-identified issues in `scripts/agentica/unified_scope.py` after the Protocol-based refactoring was completed. The code duplication has been resolved (single `_create_file_ops()` factory with `CacheManager` Protocol). This plan addresses the 25 Ruff linting issues:
- TRY300: Move return statements to else blocks
- BLE001: Catch specific exceptions instead of bare `Exception`
- RUF051: Use `dict.pop()` instead of `if key in dict: del dict[key]`

## Current State Analysis

### Refactoring Status: COMPLETE

The Protocol-based refactoring is fully implemented:
- `CacheManager` Protocol: lines 43-80
- `LocalCacheManager` class: lines 83-129
- Single `_create_file_ops()` factory: lines 154-504
- Thin wrappers preserved for backward compatibility: lines 507-553

### Remaining Work: Linting Issues

| Issue | Count | Location Pattern |
|-------|-------|------------------|
| TRY300 | ~8 | try/except blocks in `_create_file_ops` |
| BLE001 | ~8 | `except Exception as e:` blocks |
| RUF051 | 1 | `claude_scope.py:163-167` (SharedContext.invalidate) |

## Desired End State

1. All Ruff linting issues resolved
2. Exception handling uses specific exception types where appropriate
3. Code passes `uv run ruff check scripts/agentica/unified_scope.py scripts/agentica/claude_scope.py`
4. All existing tests continue to pass
5. Backward compatibility preserved

## What We're NOT Doing

- Changing the CacheManager Protocol design (already complete)
- Modifying the `_create_file_ops` function signature
- Breaking backward compatibility with existing callers
- Adding new features beyond linting fixes

## Implementation Approach

Fix linting issues in order of dependency and risk:
1. RUF051 (simplest, isolated change)
2. TRY300 (move returns to else blocks - low risk)
3. BLE001 (catch specific exceptions - medium risk, needs careful analysis)

---

## Phase 1: Fix RUF051 - Use dict.pop() Pattern

### Overview
Replace `if key in dict: del dict[key]` with `dict.pop(key, None)` pattern.

### Changes Required

#### 1. SharedContext.invalidate()
**File:** `scripts/agentica/claude_scope.py`
**Lines:** 163-167

**Current code:**
```python
def invalidate(self, path: str) -> None:
    """Invalidate cache for a path (thread-safe)."""
    with self._lock:
        if path in self.file_cache:
            del self.file_cache[path]
```

**New code:**
```python
def invalidate(self, path: str) -> None:
    """Invalidate cache for a path (thread-safe)."""
    with self._lock:
        self.file_cache.pop(path, None)
```

### Success Criteria

#### Automated Verification:
- [ ] Ruff RUF051 passes: `uv run ruff check scripts/agentica/claude_scope.py --select RUF051`
- [ ] Unit tests pass: `uv run pytest tests/unit/test_cache_manager_protocol.py -v`
- [ ] Thread safety test: `uv run pytest tests/unit/test_cache_manager_protocol.py::TestSharedContextSatisfiesProtocol -v`

#### Manual Verification:
- [ ] Review change does not alter thread-safety guarantees

---

## Phase 2: Fix TRY300 - Move Returns to Else Blocks

### Overview
When a `try` block ends with `return`, move the return to an `else` block to make control flow explicit.

### Changes Required

#### 1. read_file() function
**File:** `scripts/agentica/unified_scope.py`
**Lines:** 172-234

**Pattern to apply:**
```python
# BEFORE
try:
    response = _call_claude_cli(prompt, ["Read"])
    # ... setup result ...
    return {"success": True, ...}
except Exception as e:
    return {"success": False, ...}

# AFTER
try:
    response = _call_claude_cli(prompt, ["Read"])
    # ... setup result ...
except Exception as e:
    return {"success": False, ...}
else:
    return {"success": True, ...}
```

#### 2. write_file() function
**File:** `scripts/agentica/unified_scope.py`
**Lines:** 236-283

Apply same pattern.

#### 3. edit_file() function
**File:** `scripts/agentica/unified_scope.py`
**Lines:** 285-337

Apply same pattern.

#### 4. bash() function
**File:** `scripts/agentica/unified_scope.py`
**Lines:** 339-398

Apply same pattern.

#### 5. grep() function
**File:** `scripts/agentica/unified_scope.py`
**Lines:** 400-438

Apply same pattern.

#### 6. glob_search() function
**File:** `scripts/agentica/unified_scope.py`
**Lines:** 440-480

Apply same pattern.

### Success Criteria

#### Automated Verification:
- [ ] Ruff TRY300 passes: `uv run ruff check scripts/agentica/unified_scope.py --select TRY300`
- [ ] Unit tests pass: `uv run pytest tests/unit/test_cache_manager_protocol.py -v`
- [ ] Integration tests pass: `uv run pytest tests/integration/test_unified_scope_e2e.py -v`

#### Manual Verification:
- [ ] Control flow is clearer with explicit else blocks

---

## Phase 3: Fix BLE001 - Specific Exception Types

### Overview
Replace bare `except Exception` with specific exception types. This requires analyzing what exceptions each operation can raise.

### Exception Analysis

| Operation | Primary Exception Sources | Specific Types |
|-----------|--------------------------|----------------|
| `_call_claude_cli` | subprocess failures | `subprocess.SubprocessError`, `subprocess.TimeoutExpired`, `RuntimeError` |
| Path operations | file not found, permission | `OSError`, `PermissionError`, `FileNotFoundError` |
| JSON parsing | malformed response | `ValueError`, `json.JSONDecodeError` |

### Changes Required

#### 1. Define exception type alias
**File:** `scripts/agentica/unified_scope.py`
**Location:** After imports (around line 31)

```python
# Exception types for file operations
# subprocess.SubprocessError covers CalledProcessError, TimeoutExpired
# OSError covers FileNotFoundError, PermissionError, etc.
# RuntimeError for CLI-level failures
FileOpError = (subprocess.SubprocessError, OSError, RuntimeError, ValueError)
```

#### 2. Update read_file()
**File:** `scripts/agentica/unified_scope.py`

```python
# BEFORE
except Exception as e:

# AFTER
except FileOpError as e:
```

#### 3. Update write_file()
Apply same change.

#### 4. Update edit_file()
Apply same change.

#### 5. Update bash()
Apply same change.

#### 6. Update grep()
Apply same change.

#### 7. Update glob_search()
Apply same change.

### Success Criteria

#### Automated Verification:
- [ ] Ruff BLE001 passes: `uv run ruff check scripts/agentica/unified_scope.py --select BLE001`
- [ ] Full test suite: `uv run pytest tests/unit/test_cache_manager_protocol.py tests/unit/test_unified_scope.py -v`
- [ ] Type checking: `uv run mypy scripts/agentica/unified_scope.py --ignore-missing-imports`

#### Manual Verification:
- [ ] Exception handling is appropriately scoped
- [ ] No unhandled exceptions can escape to caller

---

## Phase 4: Final Verification

### Overview
Run full linting and test suite to confirm all issues resolved.

### Verification Commands

```bash
# Full Ruff check on both files
uv run ruff check scripts/agentica/unified_scope.py scripts/agentica/claude_scope.py

# All unit tests
uv run pytest tests/unit/test_cache_manager_protocol.py tests/unit/test_unified_scope.py tests/unit/test_claude_scope.py -v

# Integration tests
uv run pytest tests/integration/test_unified_scope_e2e.py -v

# Type checking
uv run mypy scripts/agentica/unified_scope.py scripts/agentica/claude_scope.py --ignore-missing-imports
```

### Success Criteria

#### Automated Verification:
- [ ] `uv run ruff check` shows 0 errors for both files
- [ ] All unit tests pass (100%)
- [ ] All integration tests pass
- [ ] Type checking passes with no errors

#### Manual Verification:
- [ ] Code review confirms changes are idiomatic Python
- [ ] Documentation is up to date

---

## Testing Strategy

### Unit Tests (existing)
- `tests/unit/test_cache_manager_protocol.py` - Protocol compliance and behavior
- `tests/unit/test_unified_scope.py` - Scope creation and operation

### Integration Tests (existing)
- `tests/integration/test_unified_scope_e2e.py` - Full workflow

### No New Tests Required
The existing test suite already covers the affected code paths. The linting changes are refactoring that preserves behavior.

---

## Performance Considerations

None. These are purely stylistic refactoring changes that do not affect runtime performance.

---

## Migration Notes

No migration required. All changes are internal implementation details that do not affect the public API.

---

## Risks & Considerations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Specific exceptions miss edge cases | Low | Use broad tuple `FileOpError` that covers all likely failures |
| Thread-safety regression in Phase 1 | Very Low | Lock is preserved, only internal logic changes |
| Behavior change in else blocks | Very Low | Semantically equivalent, tests verify |

---

## References

- Original issue: `docs/coderabbit-review/issue-code-duplication/comments/coderabbit-comment.md`
- Codemap analysis: `docs/coderabbit-review/issue-code-duplication/codemap/analysis.md`
- Research findings: `docs/coderabbit-review/issue-code-duplication/research/findings.md`
- Existing tests: `tests/unit/test_cache_manager_protocol.py`
- Source files:
  - `scripts/agentica/unified_scope.py`
  - `scripts/agentica/claude_scope.py`

---

## Estimated Complexity

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1 (RUF051) | 5 min | Very Low |
| Phase 2 (TRY300) | 15 min | Low |
| Phase 3 (BLE001) | 20 min | Medium |
| Phase 4 (Verify) | 10 min | None |
| **Total** | **50 min** | **Low** |

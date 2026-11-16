# Phase 6: Test Commands and Expected Output

## Quick Test

```bash
cd /Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit
bash test_phase6.sh
```

## Individual Commands

### 1. Run Unit Tests

```bash
uv run pytest tests/unit/test_agent_scope.py -v
```

**Expected Output**:
```
tests/unit/test_agent_scope.py::TestScopeInjection::test_create_agent_scope_includes_memory PASSED
tests/unit/test_agent_scope.py::TestScopeInjection::test_create_agent_scope_includes_tasks PASSED
tests/unit/test_agent_scope.py::TestScopeInjection::test_remember_and_recall_work PASSED
tests/unit/test_agent_scope.py::TestScopeInjection::test_task_functions_work PASSED
tests/unit/test_agent_scope.py::TestScopeInjection::test_scope_shares_session_id PASSED
tests/unit/test_agent_scope.py::TestScopeInjection::test_include_memory_flag PASSED
tests/unit/test_agent_scope.py::TestScopeInjection::test_include_tasks_flag PASSED
tests/unit/test_agent_scope.py::TestScopeInjection::test_extra_scope_items PASSED
tests/unit/test_agent_scope.py::TestScopeInjection::test_store_fact_function PASSED
tests/unit/test_agent_scope.py::TestScopeInjection::test_get_all_tasks_function PASSED
tests/unit/test_agent_scope.py::TestScopeInjection::test_advanced_access_services PASSED

========================= 11 passed in X.XXs =========================
```

### 2. Run QLTY Check

```bash
qlty check scripts/agentica/agent_scope.py
```

**Expected Output**:
```
No issues found
```

### 3. Test Interactive Import

```bash
uv run python -c "
from scripts.agentica.agent_scope import create_agent_scope
from pathlib import Path
import tempfile

# Create scope
with tempfile.TemporaryDirectory() as tmpdir:
    db_path = Path(tmpdir) / 'test.db'
    scope = create_agent_scope(session_id='test', db_path=db_path)

    # Verify functions exist
    assert 'remember' in scope
    assert 'recall' in scope
    assert 'create_task' in scope
    assert 'complete_task' in scope

    # Test memory
    scope['remember']('key', 'value')
    result = scope['recall']('key')
    assert 'value' in result

    # Test tasks
    task_id = scope['create_task']('Test task')
    ready = scope['get_ready_tasks']()
    assert task_id in ready

    print('✓ All interactive tests passed')
"
```

**Expected Output**:
```
✓ All interactive tests passed
```

## Test What Each Test Validates

### Test 1: `test_create_agent_scope_includes_memory`
Verifies that `create_agent_scope()` returns a dict with memory functions:
- `remember`
- `recall`
- `search_memory`
- All are callable

### Test 2: `test_create_agent_scope_includes_tasks`
Verifies that `create_agent_scope()` returns a dict with task functions:
- `create_task`
- `complete_task`
- `get_ready_tasks`
- All are callable

### Test 3: `test_remember_and_recall_work`
End-to-end test of memory:
1. Store fact: `remember("user_preference", "Prefers Python over JavaScript")`
2. Retrieve: `recall("user_preference")`
3. Verify "Python" appears in result

### Test 4: `test_task_functions_work`
End-to-end test of tasks:
1. Create task: `create_task("Research API options")`
2. Verify task is ready: `task_id in get_ready_tasks()`
3. Complete task: `complete_task(task_id)`
4. Verify task no longer ready: `task_id not in get_ready_tasks()`

### Test 5: `test_scope_shares_session_id`
Verifies session isolation:
1. Create two scopes with different session_ids
2. Store same key with different values
3. Verify each scope retrieves its own value

### Test 6: `test_include_memory_flag`
Verifies `include_memory=False` excludes memory functions:
- No `remember`, `recall` in scope
- Tasks still included

### Test 7: `test_include_tasks_flag`
Verifies `include_tasks=False` excludes task functions:
- No `create_task`, `complete_task` in scope
- Memory still included

### Test 8: `test_extra_scope_items`
Verifies `extra_scope` parameter merges custom tools:
1. Pass custom function and dict
2. Verify both appear in scope
3. Verify custom function is callable

### Test 9: `test_store_fact_function`
Verifies archival memory via `store_fact()`:
1. Store fact in archival
2. Search for it
3. Verify fact appears in results

### Test 10: `test_get_all_tasks_function`
Verifies task listing:
1. Create multiple tasks
2. Call `get_all_tasks()`
3. Verify all tasks present

### Test 11: `test_advanced_access_services`
Verifies direct service access:
1. Access `_memory_service`
2. Access `_task_graph`
3. Verify can call service methods directly

## Troubleshooting

### Import Error
```
ImportError: cannot import name 'create_agent_scope'
```

**Solution**: Ensure Python path includes project root:
```bash
export PYTHONPATH=/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit:$PYTHONPATH
```

### Database Error
```
sqlite3.OperationalError: unable to open database file
```

**Solution**: Check database directory permissions:
```bash
mkdir -p .claude/cache/agentica-memory
mkdir -p .claude/cache/agentica-tasks
chmod 755 .claude/cache/agentica-*
```

### Test Hangs
If tests hang, check for:
- Unfinished database transactions
- Lock files in cache directory

**Solution**:
```bash
rm -f .claude/cache/agentica-memory/*.db-shm
rm -f .claude/cache/agentica-memory/*.db-wal
rm -f .claude/cache/agentica-tasks/*.db-shm
rm -f .claude/cache/agentica-tasks/*.db-wal
```

## Success Criteria

Phase 6 is complete when:
- ✓ All 11 tests pass
- ✓ QLTY check passes with no issues
- ✓ Interactive import test works
- ✓ No warnings or errors during test run
- ✓ Files created:
  - `scripts/agentica/agent_scope.py` (implementation)
  - `tests/unit/test_agent_scope.py` (tests)
  - `test_phase6.sh` (test runner)
  - `PHASE6_SUMMARY.md` (documentation)
  - `PHASE6_TEST_COMMANDS.md` (this file)

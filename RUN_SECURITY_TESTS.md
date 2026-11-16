# Run Security E2E Tests

## Quick Start

```bash
cd /Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit
uv run pytest tests/integration/test_security_e2e.py -v
```

## Alternative Methods

### Method 1: Python Test Runner
```bash
python run_security_e2e_tests.py
```

### Method 2: Shell Script
```bash
chmod +x run_security_tests.sh
./run_security_tests.sh
```

### Method 3: With Coverage
```bash
uv run pytest tests/integration/test_security_e2e.py -v \
  --cov=scripts.agentica.claude_scope \
  --cov=scripts.agentica.unified_scope \
  --cov=scripts.agentica.span_processor \
  --cov-report=term-missing
```

## Run Specific Tests

### Path Validation Only
```bash
uv run pytest tests/integration/test_security_e2e.py::TestSecurityE2E::test_path_traversal_blocked_in_full_pipeline -v
```

### Async Safety Only
```bash
uv run pytest tests/integration/test_security_e2e.py -k "concurrent" -v
```

### Cross-Component Only
```bash
uv run pytest tests/integration/test_security_e2e.py::TestSecurityE2E::test_cross_component_flow -v
```

## Expected Results

✅ **15 tests should PASS**

```
tests/integration/test_security_e2e.py::TestSecurityE2E::test_path_traversal_blocked_in_full_pipeline PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_path_traversal_via_symlinks PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_path_validation_allows_valid_paths PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_concurrent_shared_context_operations PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_shared_context_cache_operations PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_unified_scope_path_validation PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_span_processing_context_concurrent_summaries PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_span_processing_context_reference_resolution PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_cross_component_flow PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_shared_context_invalidation_race PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_unified_scope_memory_and_tasks_disabled_path_validation PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_span_processing_context_write_conflicts PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_path_validation_with_tilde_expansion PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_concurrent_cache_and_invalidation PASSED
tests/integration/test_security_e2e.py::TestSecurityE2E::test_project_dir_none_allows_all_paths PASSED

================= 15 passed in X.XXs =================
```

## What's Being Tested

### Security Components
- ✅ Path traversal protection
- ✅ Symlink resolution
- ✅ Tilde expansion handling
- ✅ Project boundary enforcement

### Async Safety
- ✅ SharedContext concurrent operations
- ✅ SpanProcessingContext concurrent summaries
- ✅ Cache atomicity
- ✅ Operation logging integrity

### Integration
- ✅ UnifiedScope path validation
- ✅ Cross-component async coordination
- ✅ Independent component isolation

## Documentation

- **Test Details:** `SECURITY_E2E_TEST_SUMMARY.md`
- **Full Report:** `SECURITY_E2E_TEST_REPORT.md`
- **Test Code:** `tests/integration/test_security_e2e.py`

## Troubleshooting

### If tests fail:

1. Check Python version: `uv run python --version` (should be 3.11+)
2. Install dependencies: `uv sync`
3. Check test file exists: `ls -la tests/integration/test_security_e2e.py`
4. Run with verbose output: `uv run pytest tests/integration/test_security_e2e.py -vv`

### Common Issues:

- **Import errors**: Run `uv sync` to install dependencies
- **Async errors**: Ensure pytest-asyncio installed: `uv pip list | grep pytest-asyncio`
- **Path errors**: Verify project directory structure is intact

## Success Criteria

All 15 tests must pass to confirm:

1. ✅ Path validation works across all entry points
2. ✅ Async locks prevent race conditions
3. ✅ Components integrate without conflicts
4. ✅ Security hardening is production-ready

---

**Last Updated:** 2025-12-28
**Test Suite Version:** 1.0
**Total Tests:** 15
**Expected Pass Rate:** 100%

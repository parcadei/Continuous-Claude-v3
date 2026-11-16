# TDD Phase 1: Failing Tests Output

Generated: 2025-12-29

## Summary

**Test File:** `tests/unit/test_agent_handoff_security.py`

**Results:** 20 failed, 11 passed, 17 skipped

The failing tests confirm the path traversal vulnerabilities exist in `scripts/agentica/agent_handoff.py`.

## Test Categories

### Helper Function Tests (17 SKIPPED)
Tests for `_validate_path_component`, `_validate_filename`, `_validate_path_within_base` are skipped because these helper functions don't exist yet (Phase 1 implementation required).

### Vulnerability Confirmation Tests (20 FAILED)
These tests prove the vulnerability exists by demonstrating that malicious inputs are accepted:

| Test Class | Failures | Attack Vector |
|------------|----------|---------------|
| TestSessionIdPathTraversal | 3 | `../evil`, `../../../../outside`, `/tmp/evil` |
| TestPhasePathTraversal | 5 | `../../../tmp`, `../../etc` in phase parameters |
| TestArtifactNameTraversal | 3 | `../../.bashrc`, `.bashrc` in artifact names |
| TestCleanupPathTraversal | 2 | Escaped session_dir, symlink attacks |
| TestDoubleEncodingAttacks | 3 | `....//`, `..\\..\\`, mixed separators |
| TestKnownAttackVectors | 4 | All 4 attack vectors from the plan |

### Sanity Tests (11 PASSED)
These tests verify that valid inputs work correctly:
- Valid session IDs work
- Valid phase operations work
- Valid artifact operations work
- Full workflow completes successfully

## Key Vulnerability Evidence

### 1. Session ID Traversal
```
FAILED: VULNERABILITY: Session ID '../evil' should be rejected but was accepted.
Directory created at: /private/.../evil
```

### 2. cleanup() Arbitrary Deletion
```
FAILED: VULNERABILITY: cleanup() deleted directory outside base!
Target was: /private/.../should-not-delete
```

### 3. Phase Parameter Traversal
```
FAILED: VULNERABILITY: Phase traversal should be rejected.
Got: .../base/task-123/../../../tmp
```

### 4. Artifact Name Traversal
```
FAILED: VULNERABILITY: Artifact name traversal should be rejected
```

## Raw Test Output

```
============================= test session starts ==============================
platform darwin -- Python 3.13.9, pytest-9.0.2, pluggy-1.6.0
collected 48 items

TestValidatePathComponentHelper: 8 SKIPPED (helper not implemented)
TestValidateFilenameHelper: 6 SKIPPED (helper not implemented)
TestValidatePathWithinBaseHelper: 3 SKIPPED (helper not implemented)

TestSessionIdPathTraversal:
  test_session_id_basic_traversal_creates_outside_base FAILED
  test_session_id_deep_traversal FAILED
  test_session_id_absolute_path FAILED
  test_session_id_null_byte_injection PASSED (OS blocks null bytes in paths)

TestPhasePathTraversal:
  test_get_output_dir_traversal FAILED
  test_chain_from_traversal FAILED
  test_read_summary_traversal FAILED
  test_write_summary_traversal FAILED
  test_list_artifacts_traversal FAILED

TestArtifactNameTraversal:
  test_write_artifact_name_traversal FAILED
  test_write_artifact_hidden_file FAILED
  test_read_artifact_traversal FAILED
  test_artifact_name_null_byte PASSED (OS blocks null bytes)

TestCleanupPathTraversal:
  test_cleanup_valid_session_works PASSED
  test_cleanup_refuses_escaped_session_dir FAILED
  test_cleanup_refuses_symlink_attack FAILED (OSError from shutil.rmtree)

TestDoubleEncodingAttacks:
  test_double_dot_encoding FAILED
  test_backslash_traversal FAILED
  test_mixed_separator_traversal FAILED
  test_url_encoded_traversal PASSED (literal interpretation)

TestUnicodeNormalizationAttacks:
  test_unicode_slash_variants PASSED (allowlist blocks non-ASCII)
  test_unicode_dot_variants PASSED (allowlist blocks non-ASCII)

TestKnownAttackVectors:
  test_attack_vector_1_from_plan FAILED
  test_attack_vector_2_from_plan FAILED
  test_attack_vector_3_from_plan FAILED
  test_attack_vector_4_from_plan FAILED

TestValidInputsStillWork:
  test_valid_session_id PASSED
  test_valid_phase_operations PASSED
  test_valid_artifact_operations PASSED
  test_valid_summary_operations PASSED
  test_full_workflow PASSED

================== 20 failed, 11 passed, 17 skipped in 0.18s ===================
```

## Next Steps

1. **Phase 1**: Implement `_validate_path_component`, `_validate_filename`, `_validate_path_within_base` helpers
2. **Phase 2**: Add validation to `__init__` and core methods
3. **Phase 3**: Add validation to read/write methods
4. **Phase 4**: Secure `cleanup()` method
5. **Phase 5**: Update convenience functions
6. Re-run tests - all 48 should pass

## Acceptance Criteria

When the fix is complete:
- 0 FAILED tests
- 17 SKIPPED tests become PASSED (helper tests)
- All 48 tests PASS

# LLMSpanMemory Tests Codemap

**Files:**
- `tests/unit/test_llm_span_memory.py` (3400+ lines)
- `tests/unit/test_llm_span_memory_mutations.py` (1194 lines)
- `tests/integration/test_llm_span_memory_e2e.py` (1151 lines)

**Generated:** 2025-12-28

---

## Unit Tests: `test_llm_span_memory.py`

### Phase 1: LLMSpanMemory Dataclass Tests

```python
class TestLLMSpanMemoryInstantiation:                    # L25-73
    """Test basic instantiation of LLMSpanMemory dataclass."""
    def test_llm_span_memory_instantiation(self): ...    # L28-53
    def test_llm_span_memory_field_types(self): ...      # L55-73

class TestLLMSpanMemoryAutoEmbeddingText:                # L75-137
    """Test auto-generation of embedding_text."""
    def test_llm_span_memory_auto_embedding_text(self): ...  # L78-96
    def test_llm_span_memory_embedding_text_format(self): ... # L98-112
    def test_llm_span_memory_empty_intent_or_decision(self): ... # L114-137

class TestLLMSpanMemoryAutoContentHash:                  # L139-238
    """Test auto-generation of content_hash."""
    def test_llm_span_memory_auto_content_hash(self): ...    # L142-158
    def test_llm_span_memory_content_hash_deterministic(self): ... # L159-179
    def test_llm_span_memory_content_hash_unique_per_span(self): ... # L181-201
    def test_llm_span_memory_content_hash_unique_per_session(self): ... # L203-223
    def test_llm_span_memory_content_hash_length(self): ...  # L225-238

class TestLLMSpanMemoryDefaultLists:                     # L240-305
    """Test default values for list fields."""
    def test_llm_span_memory_default_lists(self): ...    # L243-259
    def test_llm_span_memory_explicit_lists(self): ...   # L261-277
    def test_llm_span_memory_list_independence(self): ... # L279-305

class TestLLMSpanMemoryOptionalFields:                   # L307-399
    """Test optional fields that can be None."""
    def test_llm_span_memory_optional_fields(self): ...  # L310-325
    def test_llm_span_memory_with_outcome(self): ...     # L327-341
    def test_llm_span_memory_with_error_summary(self): ... # L343-356
    def test_llm_span_memory_with_embedding(self): ...   # L358-373
    def test_llm_span_memory_all_optional_fields_set(self): ... # L375-399

class TestLLMSpanMemoryPostInit:                         # L401-472
    """Test __post_init__ behavior."""
    def test_llm_span_memory_post_init_generates_hash(self): ... # L404-419
    def test_llm_span_memory_post_init_generates_embedding_text(self): ... # L421-436
    def test_llm_span_memory_post_init_respects_explicit_hash(self): ... # L438-454
    def test_llm_span_memory_post_init_respects_explicit_embedding_text(self): ... # L456-472

class TestLLMSpanMemoryEdgeCases:                        # L474-537
    """Test edge cases and boundary conditions."""
    def test_llm_span_memory_very_long_intent(self): ... # L477-494
    def test_llm_span_memory_unicode_content(self): ...  # L496-509
    def test_llm_span_memory_high_turn_number(self): ... # L511-523
    def test_llm_span_memory_zero_turn_number(self): ... # L525-537
```

### Phase 2: Turn/Span Hierarchy Parser Tests

```python
class TestBuildTurnLLMHierarchy:                         # L544-938
    """Tests for build_turn_llm_hierarchy function."""

    # Fixtures
    @pytest.fixture def mock_session_root_span(self): ...    # L556-564
    @pytest.fixture def mock_turn_spans(self): ...           # L566-612
    @pytest.fixture def mock_llm_spans(self): ...            # L614-688
    @pytest.fixture def mock_tool_spans(self): ...           # L690-708
    @pytest.fixture def all_spans(self, ...): ...            # L710-716

    # Tests
    def test_builds_hierarchy_from_spans(self, all_spans): ... # L718-738
    def test_handles_multiple_turns(self, all_spans): ...    # L740-748
    def test_maps_llm_spans_to_parent_turn(self, all_spans): ... # L750-768
    def test_handles_empty_turn(self, all_spans): ...        # L770-782
    def test_handles_no_turns(self): ...                     # L784-790
    def test_extracts_turn_input(self, all_spans): ...       # L792-804
    def test_extracts_turn_span_id(self, all_spans): ...     # L806-813
    def test_llm_spans_contain_output(self, all_spans): ...  # L815-824
    def test_excludes_tool_spans_from_llm_list(self, all_spans): ... # L826-837
    def test_handles_missing_input_field(self, ...): ...     # L839-860
    def test_handles_dict_input_field(self, ...): ...        # L862-882
    def test_handles_nested_span_parents(self, ...): ...     # L884-909
    def test_ignores_non_turn_task_spans(self, ...): ...     # L911-938
```

### Phase 3: Extract User Intent Tests

```python
class TestExtractUserIntentRaw:                          # L946-1101
    """Tests for extract_user_intent_raw function."""
    def test_extracts_string_input(self): ...            # L953-964
    def test_truncates_long_input(self): ...             # L966-977
    def test_respects_custom_max_chars(self): ...        # L979-992
    def test_handles_dict_input_with_content_field(self): ... # L994-1005
    def test_handles_dict_input_with_text_field(self): ... # L1007-1018
    def test_handles_none_input(self): ...               # L1020-1028
    def test_handles_missing_input_field(self): ...      # L1030-1038
    def test_handles_empty_string_input(self): ...       # L1040-1048
    def test_handles_empty_dict_input(self): ...         # L1050-1058
    def test_no_truncation_for_short_input(self): ...    # L1060-1071
    def test_handles_unicode_input(self): ...            # L1073-1085
    def test_truncation_at_word_boundary_optional(self): ... # L1087-1101
```

### Phase 4: Extract LLM Decision Tests

```python
class TestExtractLLMDecision:                            # L1108-1249
    """Tests for extract_llm_decision function."""
    def test_extracts_content_from_output_dict(self): ... # L1115-1126
    def test_truncates_long_content(self): ...           # L1128-1139
    def test_respects_custom_max_chars(self): ...        # L1141-1153
    def test_handles_string_output(self): ...            # L1155-1163
    def test_handles_none_output(self): ...              # L1165-1172
    def test_handles_missing_output_field(self): ...     # L1174-1181
    def test_handles_empty_content(self): ...            # L1183-1192
    def test_handles_missing_content_in_dict(self): ...  # L1194-1206
    def test_no_truncation_for_short_content(self): ...  # L1208-1218
    def test_handles_nested_content_structure(self): ... # L1220-1236
    def test_strips_whitespace(self): ...                # L1238-1249
```

### Phase 5: Extract Tools Tests

```python
class TestExtractToolsFromLLMSpan:                       # L1256-1426
    """Tests for extract_tools_from_llm_span function."""
    def test_extracts_single_tool(self): ...             # L1263-1278
    def test_extracts_multiple_tools(self): ...          # L1280-1298
    def test_deduplicates_tool_names(self): ...          # L1300-1321
    def test_returns_empty_list_for_no_tools(self): ...  # L1323-1334
    def test_handles_missing_tool_calls_field(self): ... # L1336-1347
    def test_handles_none_output(self): ...              # L1349-1357
    def test_handles_missing_output_field(self): ...     # L1359-1366
    def test_handles_malformed_tool_call(self): ...      # L1368-1388
    def test_handles_none_in_tool_calls_list(self): ...  # L1390-1407
    def test_preserves_tool_order(self): ...             # L1409-1426
```

### Phase 6: Extract Files Tests

```python
class TestExtractFilesFromTurn:                          # L1433-1500+
    """Tests for extract_files_from_turn function."""
    @pytest.fixture def mock_spans_with_files(self): ... # L1440-1484
    def test_extracts_write_file_paths(self, ...): ...   # L1486-1492
    def test_extracts_edit_file_paths(self, ...): ...    # L1494-1500
    # Additional tests continue...
```

---

## Mutation Tests: `test_llm_span_memory_mutations.py`

### 1. Hash Determinism Tests

```python
class TestHashDeterminism:                               # L40-98
    """Tests for hash determinism across different field orderings."""
    def test_same_content_always_produces_same_hash(self): ...  # L43-58
    def test_hash_stable_across_dict_field_orderings(self): ... # L60-97
    def test_hash_changes_when_user_intent_changes(self): ...   # L99-122
    def test_hash_changes_when_decision_changes(self): ...      # L124-147
```

### 2. Truncation Boundary Tests

```python
class TestTruncationBoundaries:                          # L155-257
    """Tests for exact truncation boundaries."""
    def test_extract_user_intent_at_exactly_500_chars(self): ... # L158-170
    def test_extract_user_intent_at_499_chars(self): ...  # L172-180
    def test_extract_user_intent_at_501_chars(self): ...  # L182-197
    def test_extract_llm_decision_at_exactly_300_chars(self): ... # L199-206
    def test_extract_llm_decision_at_299_chars(self): ... # L208-216
    def test_extract_llm_decision_at_301_chars(self): ... # L218-228
    def test_default_max_chars_is_500_for_intent(self): ... # L230-243
    def test_default_max_chars_is_300_for_decision(self): ... # L245-257
```

### 3. Whitespace Handling Tests

```python
class TestWhitespaceHandling:                            # L264-311
    """Tests for whitespace handling in extraction."""
    def test_extract_llm_decision_strips_leading_whitespace(self): ... # L267-278
    def test_extract_llm_decision_strips_trailing_whitespace(self): ... # L280-286
    def test_extract_llm_decision_strips_both_ends(self): ... # L288-294
    def test_whitespace_only_input_returns_empty(self): ... # L296-302
    def test_extract_llm_decision_from_dict_strips_whitespace(self): ... # L304-311
```

### 4. Error Context Window Tests

```python
class TestErrorContextWindow:                            # L318-549
    """Tests for error context extraction boundaries."""
    def test_error_context_includes_chars_before_match(self): ... # L321-348
    def test_error_context_starts_at_correct_position(self): ... # L350-376
    def test_error_context_prefix_not_truncated_to_zero(self): ... # L378-406
    def test_error_context_includes_chars_after_match(self): ... # L408-432
    def test_error_context_truncated_to_500_chars(self): ... # L434-455
    def test_error_context_exactly_500_when_exceeds(self): ... # L457-491
    def test_error_context_not_truncated_under_500(self): ... # L493-519
    def test_error_context_between_100_and_500_preserved(self): ... # L521-549
```

### 5. Unicode Handling Tests

```python
class TestUnicodeHandling:                               # L556-628
    """Tests for Unicode character handling."""
    def test_emoji_in_user_intent(self): ...             # L559-575
    def test_cjk_characters_in_decision(self): ...       # L577-590
    def test_truncation_does_not_break_utf8(self): ...   # L592-607
    def test_unicode_normalization_in_hash(self): ...    # L609-628
```

### 6. Concurrent Access Tests

```python
class TestConcurrentAccess:                              # L635-720
    """Tests for concurrent access patterns."""
    @pytest.mark.asyncio
    async def test_parallel_store_calls_no_race(self): ... # L638-689
    @pytest.mark.asyncio
    async def test_duplicate_detection_under_concurrency(self): ... # L691-720
```

### 7. Malformed Data Tests

```python
class TestMalformedData:                                 # L727-789
    """Tests for handling malformed or unexpected data."""
    def test_span_with_null_span_parents(self): ...      # L730-745
    def test_span_with_missing_output_field(self): ...   # L747-752
    def test_span_with_none_output(self): ...            # L754-760
    def test_deeply_nested_dict_input(self): ...         # L762-772
    def test_extract_intent_with_list_input(self): ...   # L774-780
    def test_extract_decision_with_numeric_output(self): ... # L782-789
```

### 8. SQL Injection Prevention Tests

```python
class TestSQLInjectionPrevention:                        # L796-897
    """Tests for SQL injection prevention."""
    def test_session_id_with_sql_injection_attempt(self): ... # L799-838
    def test_session_id_with_special_characters(self): ... # L840-869
    def test_outcome_lookup_with_unicode(self): ...      # L871-897
```

### 9. Hash Uniqueness Tests

```python
class TestHashUniqueness:                                # L904-979
    """Additional tests for hash uniqueness guarantees."""
    def test_1000_different_inputs_produce_1000_unique_hashes(self): ... # L907-922
    def test_hash_includes_all_required_fields(self): ... # L924-979
```

### 10. Edge Case Tests

```python
class TestEdgeCases:                                     # L986-1073
    """Tests for edge cases and boundary conditions."""
    def test_empty_user_intent(self): ...                # L989-1001
    def test_empty_decision(self): ...                   # L1003-1014
    def test_very_long_content(self): ...                # L1016-1032
    def test_newlines_in_content(self): ...              # L1034-1045
    def test_special_json_characters(self): ...          # L1047-1060
    def test_null_byte_handling(self): ...               # L1062-1073
    def test_turn_number_zero(self): ...                 # L1075-1085
    def test_negative_turn_number(self): ...             # L1087-1097
```

### 11. Error Pattern Detection Tests

```python
class TestErrorPatternDetection:                         # L1104-1194
    """Tests for error pattern detection in bash output."""
    def test_traceback_detection_case_insensitive(self): ... # L1107-1133
    def test_error_not_detected_for_non_bash_spans(self): ... # L1135-1149
    def test_error_detected_in_stderr(self): ...         # L1151-1165
    def test_multiple_error_patterns(self): ...          # L1167-1194
```

---

## E2E Tests: `test_llm_span_memory_e2e.py`

### Test Fixtures

```python
def unique_session_id() -> str: ...                      # L42-44
def create_mock_turn_span(...) -> dict[str, Any]: ...    # L47-74
def create_mock_llm_span(...) -> dict[str, Any]: ...     # L76-107
def create_mock_tool_span(...) -> dict[str, Any]: ...    # L109-138
def create_mock_session_spans() -> tuple[...]: ...       # L140-322

class MockMemoryBackend:                                 # L324-356
    """Mock memory backend for testing storage operations."""
    async def store(...) -> str: ...
    async def search(...) -> list[dict[str, Any]]: ...
    async def close(): ...

class MockEmbeddingService:                              # L358-384
    """Mock embedding service for testing."""
    async def embed(text: str) -> list[float]: ...
    async def embed_batch(texts: list[str]) -> list[list[float]]: ...
```

### Full Pipeline E2E Tests

```python
class TestLLMSpanMemoryE2E:                              # L391-852
    """End-to-end tests for LLMSpanMemory extraction pipeline."""

    @pytest.mark.integration
    async def test_full_pipeline_with_mock_session(self): ... # L394-438

    @pytest.mark.integration
    async def test_full_pipeline_with_embedding_and_storage(self): ... # L440-494

    @pytest.mark.integration
    async def test_cli_invocation_with_test_session(self): ... # L496-520

    @pytest.mark.integration
    async def test_metrics_tracking_accurate(self): ...  # L522-569

    @pytest.mark.integration
    async def test_deduplication_on_re_run(self): ...    # L571-631

    @pytest.mark.integration
    async def test_error_recovery(self): ...             # L633-678

    @pytest.mark.integration
    async def test_turn_with_zero_llm_spans_handled(self): ... # L680-721

    @pytest.mark.integration
    async def test_error_detection_in_bash_spans(self): ... # L723-768

    @pytest.mark.integration
    async def test_files_touched_extraction(self): ...   # L770-812

    @pytest.mark.integration
    async def test_tools_called_extraction(self): ...    # L814-852
```

### Real API Tests (Require BRAINTRUST_API_KEY)

```python
@pytest.mark.skipif(not os.getenv("BRAINTRUST_API_KEY"), ...)
class TestLLMSpanMemoryRealAPI:                          # L859-943
    """Integration tests using real Braintrust API."""

    @pytest.mark.integration
    async def test_extract_from_real_session(self): ... # L870-906

    @pytest.mark.integration
    async def test_backfill_with_real_embedding(self): ... # L908-943
```

### Performance Tests

```python
class TestLLMSpanMemoryPerformance:                      # L950-1009
    """Performance tests for LLMSpanMemory extraction."""

    @pytest.mark.integration
    async def test_extraction_performance_100_spans(self): ... # L953-992

    @pytest.mark.integration
    async def test_embedding_batch_performance(self): ... # L994-1009
```

### Edge Case Tests

```python
class TestLLMSpanMemoryEdgeCases:                        # L1016-1151
    """Edge case tests for LLMSpanMemory extraction."""

    @pytest.mark.integration
    async def test_empty_spans_list(self): ...           # L1019-1025

    @pytest.mark.integration
    async def test_spans_with_no_turns(self): ...        # L1027-1043

    @pytest.mark.integration
    async def test_deeply_nested_turns(self): ...        # L1045-1066

    @pytest.mark.integration
    async def test_unicode_content_handling(self): ...   # L1068-1082

    @pytest.mark.integration
    async def test_very_long_content_truncation(self): ... # L1084-1104

    @pytest.mark.integration
    async def test_null_and_none_values(self): ...       # L1106-1125

    @pytest.mark.integration
    async def test_malformed_tool_calls(self): ...       # L1127-1151
```

---

## Test Coverage Summary

| Category | Unit Tests | Mutation Tests | E2E Tests |
|----------|------------|----------------|-----------|
| Dataclass instantiation | 10+ | - | - |
| Auto-computed fields | 8+ | 4 | 2 |
| Hash determinism | 4 | 4 | 2 |
| Truncation boundaries | 4 | 8 | 2 |
| Whitespace handling | - | 5 | - |
| Error context window | - | 8 | 2 |
| Unicode handling | 2 | 4 | 2 |
| Concurrent access | - | 2 | - |
| Malformed data | 6+ | 6 | 4 |
| SQL injection | - | 3 | - |
| Performance | - | - | 2 |
| Full pipeline | - | - | 10+ |

---

## Running Tests

```bash
# Unit tests only
uv run pytest tests/unit/test_llm_span_memory.py -v

# Mutation tests only
uv run pytest tests/unit/test_llm_span_memory_mutations.py -v

# E2E tests (mock only)
uv run pytest tests/integration/test_llm_span_memory_e2e.py -v

# E2E tests with real API
BRAINTRUST_API_KEY=... uv run pytest tests/integration/test_llm_span_memory_e2e.py -v -m integration

# All LLMSpanMemory tests
uv run pytest tests/ -k "llm_span_memory" -v
```

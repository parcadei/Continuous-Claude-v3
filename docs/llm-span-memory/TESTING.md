# LLMSpanMemory Test Suite Documentation

## Test Suite Overview

| Metric | Value |
|--------|-------|
| **Total Tests** | 215 |
| **Passing** | 213 |
| **Skipped** | 2 (require external API keys) |
| **Coverage Target** | 100% mutation kill rate |

### Test File Locations

```
tests/unit/test_llm_span_memory.py           # 140 tests - Core unit tests
tests/unit/test_llm_span_memory_mutations.py # 54 tests  - Mutation-resistant tests
tests/integration/test_llm_span_memory_e2e.py # 21 tests  - End-to-end pipeline tests
```

---

## Test Categories

### Unit Tests (140 tests)

```
+-----------------------------------------+-------+----------------------------------+
| Category                                | Tests | Coverage                         |
+-----------------------------------------+-------+----------------------------------+
| Dataclass Instantiation                 |   6   | Required fields, field types     |
| Auto-Generated embedding_text           |   3   | Format, content, edge cases      |
| Auto-Generated content_hash             |   5   | Determinism, uniqueness, length  |
| Default List Fields                     |   3   | Empty defaults, independence     |
| Optional Fields                         |   5   | None defaults, explicit values   |
| __post_init__ Behavior                  |   4   | Auto-generation, explicit respect|
| Edge Cases                              |   4   | Long input, unicode, turn bounds |
| Turn/LLM Hierarchy Builder              |  13   | Turn/span mapping, edge cases    |
| User Intent Extraction                  |  10   | String/dict input, truncation    |
| LLM Decision Extraction                 |   9   | Output parsing, whitespace       |
| Tool Extraction from LLM Spans          |   8   | tool_calls parsing, dedup        |
| File Extraction from Turn               |   9   | Read/Write/Edit span parsing     |
| Session Outcome Lookup                  |   8   | DB query, SQL injection defense  |
| Error Detection in Turn                 |  11   | Traceback patterns, context      |
| LLMSpanMemory Extraction                |  10   | Full pipeline, edge cases        |
| User Intent Summarization               |   5   | Truncation, format               |
| Memory Storage                          |   7   | Store, dedup, error handling     |
| Backfill Session Integration            |   6   | Full backfill flow               |
| BackfillResult Fields                   |   4   | Metrics tracking                 |
| CLI Flag Parsing                        |   5   | --extract-span-memories          |
| CLI Execution                           |   5   | Main entry point behavior        |
+-----------------------------------------+-------+----------------------------------+
```

### Mutation Tests (54 tests)

```
+-----------------------------------------+-------+----------------------------------+
| Category                                | Tests | Mutations Caught                 |
+-----------------------------------------+-------+----------------------------------+
| Hash Determinism                        |   4   | sort_keys, field inclusion       |
| Truncation Boundaries                   |  10   | Off-by-one, default values       |
| Whitespace Handling                     |   5   | strip() removal, edge cases      |
| Error Context Window                    |  10   | -50/+200 char windows, 500 limit |
| Unicode Handling                        |   4   | Emoji, CJK, UTF-8 truncation     |
| Concurrent Access                       |   2   | Race conditions, dedup           |
| Malformed Data                          |   7   | Null fields, wrong types         |
| SQL Injection Prevention                |   3   | Parameterized queries            |
| Hash Uniqueness                         |   2   | 1000-input collision test        |
| Edge Cases                              |   7   | Empty, long, special chars       |
+-----------------------------------------+-------+----------------------------------+
```

### E2E Tests (21 tests)

```
+-----------------------------------------+-------+----------------------------------+
| Category                                | Tests | Coverage                         |
+-----------------------------------------+-------+----------------------------------+
| Full Pipeline with Mock Session         |   1   | Extract -> count -> verify       |
| Pipeline with Embedding + Storage       |   1   | Embed -> store -> verify         |
| CLI Invocation                          |   1   | Argument parsing                 |
| Metrics Tracking                        |   1   | BackfillResult accuracy          |
| Deduplication on Re-run                 |   1   | content_hash determinism         |
| Error Recovery                          |   1   | Partial failures                 |
| Turn with Zero LLM Spans                |   1   | Edge case handling               |
| Error Detection in Bash Spans           |   1   | Traceback capture                |
| Files Touched Extraction                |   1   | Read/Write/Edit dedup            |
| Tools Called Extraction                 |   1   | tool_calls parsing               |
| Real API Tests (2 tests, skipped)*      |   2   | Braintrust API integration       |
| Performance: 100 Spans                  |   1   | < 1s extraction                  |
| Performance: Batch Embedding            |   1   | < 1s for 100 texts               |
| Edge: Empty Spans List                  |   1   | Empty input handling             |
| Edge: No Turn Spans                     |   1   | Orphan LLM span handling         |
| Edge: Deeply Nested Turns               |   1   | Nested task spans                |
| Edge: Unicode Content                   |   1   | Emoji/unicode in spans           |
| Edge: Very Long Content                 |   1   | Truncation verification          |
| Edge: Null/None Values                  |   1   | Graceful null handling           |
| Edge: Malformed Tool Calls              |   1   | Invalid structure handling       |
+-----------------------------------------+-------+----------------------------------+

* Skipped tests require BRAINTRUST_API_KEY and TEST_SESSION_ID environment variables
```

---

## Mutation Testing Results

### Summary

| Phase | Tests | Mutations | Killed | Survived | Score |
|-------|-------|-----------|--------|----------|-------|
| Phase A (baseline) | ~20 | 38 | 25 | 13 | **65.8%** |
| Phase E (improvements) | 49 | 15 | 13 | 2 | 86.7% |
| Phase G (final) | 54 | 15 | 15 | 0 | **100%** |

### Key Mutations Caught

1. **Hash Determinism** (`sort_keys=True` removal)
   - Tests verify same content always produces identical hash
   - Tests verify different fields produce different hashes

2. **Truncation Boundaries** (off-by-one errors)
   - Test at exactly 500 chars (no truncation)
   - Test at 501 chars (truncation with "...")
   - Test at exactly 300 chars for decisions

3. **Error Context Windows** (-50/+200 char mutations)
   - Test verifies exactly 50 chars of prefix context
   - Test verifies 200 chars of suffix context
   - Test verifies 500 char truncation limit

4. **Hash Field Inclusion** (field removal mutations)
   - Test: changing user_intent produces different hash
   - Test: changing decision produces different hash
   - Test: changing span_id produces different hash
   - Test: changing session_id produces different hash

5. **Whitespace Handling** (strip() removal)
   - Test: leading whitespace stripped
   - Test: trailing whitespace stripped
   - Test: whitespace-only input returns empty string

---

## Running Tests

### All Unit Tests

```bash
# Core unit tests
uv run pytest tests/unit/test_llm_span_memory.py -v

# Mutation tests
uv run pytest tests/unit/test_llm_span_memory_mutations.py -v

# Both unit test files
uv run pytest tests/unit/test_llm_span_memory.py tests/unit/test_llm_span_memory_mutations.py -v
```

### E2E Tests

```bash
# Mock-based E2E tests (no API keys required)
uv run pytest tests/integration/test_llm_span_memory_e2e.py -v

# With real Braintrust API (requires API keys)
BRAINTRUST_API_KEY=your-key TEST_SESSION_ID=your-session \
  uv run pytest tests/integration/test_llm_span_memory_e2e.py -v -m integration
```

### With Coverage

```bash
# Coverage for memory_backfill module
uv run pytest --cov=scripts.agentica.memory_backfill \
  tests/unit/test_llm_span_memory.py \
  tests/unit/test_llm_span_memory_mutations.py -v

# HTML coverage report
uv run pytest --cov=scripts.agentica.memory_backfill \
  --cov-report=html \
  tests/unit/test_llm_span_memory*.py

# Coverage with branch analysis
uv run pytest --cov=scripts.agentica.memory_backfill \
  --cov-branch \
  tests/unit/test_llm_span_memory*.py
```

### Quick Test Runs

```bash
# Fast smoke test (parallel)
uv run pytest tests/unit/test_llm_span_memory.py -x -q

# Single test class
uv run pytest tests/unit/test_llm_span_memory.py::TestLLMSpanMemoryInstantiation -v

# Single test
uv run pytest tests/unit/test_llm_span_memory.py::TestLLMSpanMemoryInstantiation::test_llm_span_memory_instantiation -v

# Pattern matching
uv run pytest tests/unit/test_llm_span_memory.py -k "hash" -v
```

---

## Adding New Tests

### Test File Organization

| Test Type | Location | When to Use |
|-----------|----------|-------------|
| Unit tests | `test_llm_span_memory.py` | Testing individual functions/methods |
| Mutation tests | `test_llm_span_memory_mutations.py` | Tests designed to catch specific code mutations |
| E2E tests | `test_llm_span_memory_e2e.py` | Full pipeline integration tests |

### Naming Conventions

```python
# Test classes: Test<FunctionName> or Test<Feature>
class TestExtractUserIntentRaw:
    ...

class TestLLMSpanMemoryInstantiation:
    ...

# Test methods: test_<behavior>_<condition>
def test_extract_user_intent_at_exactly_max_chars(self):
    ...

def test_content_hash_changes_with_user_intent(self):
    ...
```

### Mock Patterns Used

#### 1. Memory Backend Mock
```python
class MockMemoryBackend:
    """Mock memory backend for testing storage operations."""

    def __init__(self):
        self.stored: list[dict[str, Any]] = []

    async def store(self, content: str, metadata: dict, embedding=None) -> str:
        memory_id = f"mem-{uuid4().hex[:8]}"
        self.stored.append({"id": memory_id, "content": content, ...})
        return memory_id

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        return self.search_results[:limit]
```

#### 2. Embedding Service Mock
```python
class MockEmbeddingService:
    """Deterministic mock embedding service."""

    async def embed(self, text: str) -> list[float]:
        # Hash-based deterministic embedding
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        return [float(int(text_hash[i:i+2], 16)) / 255.0
                for i in range(0, len(text_hash), 2)][:self.dimension]
```

#### 3. Span Fixture Factory
```python
def create_mock_turn_span(turn_number: int, span_id: str, user_input: str) -> dict:
    return {
        "span_id": span_id,
        "name": f"Turn {turn_number}",
        "span_parents": [],
        "span_attributes": {"type": "task", "name": f"Turn {turn_number}"},
        "input": user_input,
    }

def create_mock_llm_span(span_id: str, parent_id: str, decision: str) -> dict:
    return {
        "span_id": span_id,
        "name": "llm",
        "span_parents": [parent_id],
        "span_attributes": {"type": "llm"},
        "output": {"content": decision},
    }
```

#### 4. Database Mock with tempfile
```python
def test_sql_injection_prevention(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / ".claude" / "cache" / "context.db"
        db_path.parent.mkdir(parents=True)

        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE handoffs (...)")
        conn.commit()
        conn.close()

        with patch.dict("os.environ", {"CONTEXT_DB_PATH": str(db_path)}):
            result = lookup_session_outcome("'; DROP TABLE handoffs; --")

        # Verify table still exists
```

### Test Categories to Add

When adding new tests, consider which category fits:

1. **Boundary Tests**: Test at exact limits (not just above/below)
2. **Mutation-Resistant Tests**: Design to catch specific code changes
3. **Error Path Tests**: Test error handling and recovery
4. **Concurrent Tests**: Use `@pytest.mark.asyncio` with `asyncio.gather`
5. **Performance Tests**: Include time assertions (`assert elapsed < 1.0`)

### Example: Adding a Boundary Test

```python
class TestNewBoundary:
    """Tests for new boundary condition."""

    def test_at_exactly_boundary(self):
        """Test behavior at exact boundary (catches >= vs > mutations)."""
        # Create input at EXACTLY the boundary
        input_at_boundary = "x" * 500  # Exactly 500

        result = function_under_test(input_at_boundary)

        # Verify NO truncation at exact boundary
        assert len(result) == 500
        assert not result.endswith("...")

    def test_one_over_boundary(self):
        """Test behavior one over boundary (catches off-by-one)."""
        input_over = "x" * 501  # One over

        result = function_under_test(input_over)

        # Verify truncation at boundary + 1
        assert len(result) == 503  # 500 + "..."
        assert result.endswith("...")
```

---

## Test Design Principles

### Lessons from Mutation Testing

1. **Avoid `or` in Assertions**
   ```python
   # BAD: Mutation can survive
   assert "error" in result or "Error" in result

   # GOOD: Specific assertion
   assert "Traceback" in result
   ```

2. **Check Exact Values, Not Bounds**
   ```python
   # BAD: Bounds only
   assert len(result) <= 500

   # GOOD: Exact value
   assert len(result) == 500
   ```

3. **Use Distinct Countable Patterns**
   ```python
   # BAD: Hard to verify
   prefix = "x" * 100

   # GOOD: Countable pattern
   prefix = "PREFIX_CHAR_" * 10  # Each occurrence = 12 chars
   assert prefix_count >= 4  # At least 48 chars of prefix
   ```

4. **Test Field Independence**
   ```python
   # Test that changing ONLY one field changes the hash
   base = create_memory(intent="A", decision="X")
   diff = create_memory(intent="B", decision="X")  # Only intent differs
   assert base.content_hash != diff.content_hash
   ```

---

## References

- Implementation: `scripts/agentica_patterns/memory_backfill.py`
- Plan: `thoughts/shared/plans/2025-12-28-llm-span-memory-model.md`
- Mutation Results: `thoughts/shared/agent-outputs/mutation-testing/phase-a/mutation-results.md`
- Final Validation: `thoughts/shared/agent-outputs/mutation-testing/phase-g/final-validation.md`

# Research Report: Weak Prompt Assertion in test_crud_patterns_batch2.py:786

**Generated:** 2025-12-29
**Status:** Complete

## Executive Summary

The test at line 786 in `tests/unit/test_crud_patterns_batch2.py` performs insufficient validation of prompt content. It only checks that prompts are captured (non-empty list) but does not validate that the key requirement—the "requirements" data—is actually included in the specialist's prompt. The test relies on a loose, case-insensitive string matching fallback that does not strictly verify the intended data flow from `reads_from` to prompt content.

## Research Question

What is the proper assertion strategy for validating that a specialist's prompt contains the expected context from keys they depend on (via `reads_from`)?

## Key Findings

### Finding 1: Current Assertion Weakness (Line 786-790)

**Location:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_crud_patterns_batch2.py:786-790`

```python
# Designer should see requirements in prompt
assert captured_prompts, "Expected prompts to be captured"
all_prompts = " ".join(captured_prompts)
# The prompt should reference requirements data from reads_from
assert "requirements" in all_prompts.lower() or "user auth" in all_prompts.lower(), \
    f"Expected requirements context in prompt, got: {all_prompts[:200]}"
```

**Problems identified:**

1. **First assertion is too weak:** `assert captured_prompts` only validates that the list is non-empty, not that prompts were actually captured during the correct phase
2. **Fallback string matching is too loose:** The assertion uses `.lower()` and an OR condition (`"requirements"` OR `"user auth"`), which means either string could satisfy the requirement, making it a false positive detector
3. **Lacks structural validation:** The assertion doesn't verify that the "requirements" key-value pair from the blackboard state is properly injected into the prompt
4. **No verification of dependency injection:** The test doesn't confirm that `reads_from: ["requirements"]` actually resulted in the requirements data being included

**Why this matters:** A specialist defined with `reads_from=["requirements"]` should see the actual requirements data in their prompt. The current assertion could pass even if the Blackboard pattern is not properly injecting this context.

---

### Finding 2: Blackboard Pattern's Prompt Construction (Lines 247-256)

**Location:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/patterns/blackboard.py:247-256`

```python
# Build context from keys the specialist reads
read_context = ""
if specialist.reads_from:
    for key in specialist.reads_from:
        if key in state:
            read_context += f"\n{key}: {state[key]}"

prompt = f"""
Task: {query}

You are responsible for: {specialist.writes_to}
{f"Based on: {read_context}" if read_context else ""}

Current blackboard state: {state.to_dict()}

Provide your contribution as a dict with keys: {specialist.writes_to}
"""
```

**How this works:**

1. The specialist's `reads_from` keys determine which blackboard values are extracted
2. These are formatted into a `read_context` string with format: `key: value`
3. If `read_context` is non-empty, the phrase "Based on: " is prepended
4. The prompt includes both the `read_context` AND the full `state.to_dict()`

**Implication for testing:** A proper assertion should verify that:
- When a specialist has `reads_from=["requirements"]`
- AND the blackboard state contains `{"requirements": "user auth needed"}`
- THEN the prompt should contain both:
  1. The explicit "Based on: requirements: user auth needed" section
  2. The full state dict in "Current blackboard state"

---

### Finding 3: Test Pattern Structure (Lines 743-790)

**Context:** The test `test_specialist_prompt_contains_readable_keys`

```python
@pytest.mark.asyncio
async def test_specialist_prompt_contains_readable_keys(self, mock_spawn):
    """Verify specialists see state they depend on (prompt reliability)."""
    from scripts.agentica.patterns import Blackboard, Specialist

    captured_prompts = []
    iteration = {"value": 0}

    def spawn_side_effect(**kwargs):
        mock_agent = AsyncMock()
        premise = kwargs.get("premise", "")

        async def mock_call(return_type, prompt, **kw):
            if "check" in premise.lower():
                iteration["value"] += 1
                return {"complete": iteration["value"] >= 2}
            elif "design" in premise.lower():
                captured_prompts.append(prompt)  # ← Captures prompt from designer specialist
                return {"design": "microservices architecture"}
            else:
                return {"requirements": "user auth needed"}

        mock_agent.call = mock_call
        return mock_agent

    mock_spawn.side_effect = spawn_side_effect

    bb = Blackboard(
        specialists=[
            Specialist(premise="You analyze requirements.", writes_to=["requirements"]),
            Specialist(
                premise="You design architecture.",
                reads_from=["requirements"],  # ← Depends on requirements
                writes_to=["design"],
            ),
        ],
        controller_premise="You check if complete.",
        max_iterations=3,
    )

    await bb.solve("Build auth system")

    # WEAK ASSERTION HERE ↓
    assert captured_prompts, "Expected prompts to be captured"
    all_prompts = " ".join(captured_prompts)
    assert "requirements" in all_prompts.lower() or "user auth" in all_prompts.lower(), \
        f"Expected requirements context in prompt, got: {all_prompts[:200]}"
```

**Test flow:**
1. Two specialists are created: one that writes "requirements", another that reads from "requirements"
2. The mock captures prompts when the design specialist (which has `reads_from=["requirements"]`) is called
3. The assertion checks if prompts contain "requirements" or "user auth" (the value that gets written)

---

### Finding 4: Related Test Patterns for Comparison

**Location:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_crud_prompt_reliability.py:27-91`

The `test_crud_prompt_reliability.py` file provides better assertion patterns:

```python
# Pattern 1: Direct string assertions
assert "security_auditor" in captured_prompt
assert "performance_analyst" in captured_prompt
assert "ux_reviewer" in captured_prompt

# Pattern 2: Multi-requirement assertions
assert captured_prompt is not None
assert "specialist" in captured_prompt.lower()
assert "task" in captured_prompt.lower()

# Pattern 3: Structured validation
assert "approved" in result.artifacts
assert isinstance(result.artifacts["approved"], bool)
assert "feedback" in result.artifacts
assert isinstance(result.artifacts["feedback"], str)
```

These tests use multiple discrete assertions rather than OR conditions, which is more precise.

---

### Finding 5: Proper Assertion Strategy

Based on the codebase patterns and best practices, the assertion should validate:

**Level 1: Capture validation**
```python
assert captured_prompts, "Expected prompts to be captured"
assert len(captured_prompts) > 0, "At least one specialist prompt should be captured"
```

**Level 2: Explicit key presence**
```python
# Should find exact key name in prompt
assert "requirements" in all_prompts, \
    f"Expected 'requirements' key in prompt, got: {all_prompts}"
```

**Level 3: Data value presence**
```python
# Should find the actual value that was written to blackboard
assert "user auth" in all_prompts, \
    f"Expected 'user auth' (requirements value) in prompt, got: {all_prompts}"
```

**Level 4: Section presence**
```python
# Should verify the "Based on:" section exists when reads_from is specified
assert "Based on:" in all_prompts, \
    f"Expected 'Based on:' section for read context in prompt, got: {all_prompts}"
```

**Level 5: Structured validation**
```python
# Most rigorous: split prompt and validate structure
lines = all_prompts.split('\n')
assert any("requirements:" in line for line in lines), \
    f"Expected 'requirements:' key-value pair in prompt, got:\n{all_prompts}"
```

---

## Codebase Analysis

### Pattern: Prompt Reliability Testing

The codebase distinguishes between multiple levels of test rigor:

1. **Level 1: Basic execution** - Does the pattern run without errors?
2. **Level 2: Structure validation** - Are the right number of agents spawned?
3. **Level 3: Prompt engineering** - Does the prompt contain expected elements?
4. **Level 4: Structured output** - Does the agent's response match expected format?

The test at line 786 is attempting **Level 3** but uses weak assertions characteristic of **Level 2**.

### Files Involved

- **Test file:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_crud_patterns_batch2.py`
  - Lines 743-790: Full test function
  - Line 786: Weak assertion

- **Pattern implementation:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/scripts/agentica/patterns/blackboard.py`
  - Lines 227-259: `_run_specialist()` method that builds the prompt
  - Lines 241-256: Prompt construction with read context injection

- **Reference test file:** `/Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit/tests/unit/test_crud_prompt_reliability.py`
  - Lines 27-91: Better assertion patterns for prompt content

---

## Sources

1. **Weak assertion location:** `tests/unit/test_crud_patterns_batch2.py:786-790`
   - Lines 743-790: Full test context

2. **Prompt construction in Blackboard pattern:** `scripts/agentica/patterns/blackboard.py:227-259`
   - Shows how `reads_from` keys are injected into specialist prompts

3. **Better assertion patterns:** `tests/unit/test_crud_prompt_reliability.py:27-91`
   - Examples of multi-level prompt assertions
   - Uses specific assertions rather than OR conditions

4. **Test framework context:** `tests/unit/test_crud_patterns_batch2.py:1-27`
   - File-level documentation of test levels (Level 3/4 tests)

---

## Recommendations

### Immediate Fix (Minimum Change)

Replace the weak OR-condition assertion with separate, specific assertions:

```python
# OLD (weak):
assert "requirements" in all_prompts.lower() or "user auth" in all_prompts.lower(), \
    f"Expected requirements context in prompt, got: {all_prompts[:200]}"

# NEW (stronger):
assert "requirements" in all_prompts, \
    f"Expected 'requirements' key in prompt for specialist with reads_from=['requirements'], got: {all_prompts}"
assert "user auth" in all_prompts or "based on" in all_prompts.lower(), \
    f"Expected requirements value ('user auth') or 'Based on:' section in prompt, got: {all_prompts}"
```

### Comprehensive Fix (Best Practice)

Add multi-level validation to match Level 3/4 rigor:

```python
# 1. Validate capture
assert captured_prompts, "Expected prompts to be captured"
assert len(captured_prompts) >= 1, "Designer specialist should have been called"

# 2. Validate key presence
all_prompts = " ".join(captured_prompts)
assert "requirements" in all_prompts, \
    f"Specialist with reads_from=['requirements'] should see 'requirements' in prompt. Got:\n{all_prompts}"

# 3. Validate value presence
assert "user auth" in all_prompts, \
    f"Specialist should see the requirements value ('user auth') in prompt. Got:\n{all_prompts}"

# 4. Validate section structure
assert "Based on:" in all_prompts or "Current blackboard state" in all_prompts, \
    f"Prompt should include context from reads_from. Got:\n{all_prompts}"
```

### Long-term Pattern Improvement

Consider creating a test helper function for prompt validation:

```python
def assert_specialist_sees_dependency(prompt: str, reads_from: list[str], state: dict):
    """Validate that specialist prompt includes all required dependencies."""
    for key in reads_from:
        assert key in prompt, \
            f"Specialist with reads_from={reads_from} should see '{key}' in prompt.\nGot: {prompt}"
        if key in state:
            assert str(state[key]) in prompt, \
                f"Specialist should see value of '{key}' in prompt.\nGot: {prompt}"
```

---

## Open Questions

1. **Coverage:** Are there other tests in the file that check blackboard state injection? Should they all be strengthened?

2. **Mutation testing:** Would a mutation that removes read context injection be caught by the current assertion? (Likely not.)

3. **Error messages:** Should the test show the full prompt on failure, or truncate as currently done with `[:200]`? (Full prompt would be more debuggable.)

4. **Multiple iterations:** The test runs up to 3 iterations—does it validate that the requirements appear consistently across iterations?

---

## Summary

The assertion at line 786 is **functionally weak** because it:

1. Uses an OR condition that masks the actual requirement
2. Only validates list non-emptiness, not capture timing
3. Relies on loose string matching (case-insensitive partial matches)
4. Doesn't verify the dependency injection mechanism itself

**Proper assertion** should separately validate:
- That the "requirements" key name appears in the prompt
- That the "user auth" value appears in the prompt
- That the "Based on:" section exists (indicating reads_from was processed)
- That the structure matches Blackboard's documented prompt format

The Blackboard pattern implementation correctly injects read context (lines 241-256 of blackboard.py), but the test's assertions don't rigorously verify this behavior. The fix is straightforward: replace the single OR-condition assertion with multiple specific assertions.

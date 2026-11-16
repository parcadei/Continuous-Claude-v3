# Module: Z3 & Erotetic Logic

## Overview

Keep Z3 SMT solver for formal question detection. Make propositions fully dynamic via LLM pre-pass. Enable personalization through pattern learning over time.

---

## How Z3 Works (Current)

Z3 encodes propositions as Boolean constraints and finds "what's unknown":

```python
# Current: Hardcoded propositions
propositions = {
    "framework": ["react", "vue", "svelte"],
    "db_type": ["postgres", "sqlite", "mysql"],
}

# Z3 creates: framework_react, framework_vue, framework_svelte
# Constraint: exactly_one(framework_*)
# Given user input, finds unconstrained categories → clarifying questions
```

---

## Dynamic Proposition Generation

### Fast Path: Pattern Extraction

Before invoking any LLM, extract propositions via regex patterns. This handles 80%+ of cases with zero latency:

```python
# From scripts/workflow_erotetic.py

PROPOSITION_PATTERNS: dict[str, re.Pattern] = {
    'framework': re.compile(r'\b(fastapi|express|hono|gin|django|flask|rails|spring|nest\.?js)\b', re.IGNORECASE),
    'auth_method': re.compile(r'\b(jwt|oauth\d?|session|api[- ]?key|basic auth|bearer|saml|oidc)\b', re.IGNORECASE),
    'database': re.compile(r'\b(postgres(?:ql)?|mysql|sqlite|mongodb|redis|dynamodb|firestore)\b', re.IGNORECASE),
    'hosting': re.compile(r'\b(vercel|aws|gcp|azure|heroku|railway|fly\.io|cloudflare)\b', re.IGNORECASE),
    'language': re.compile(r'\b(python|typescript|javascript|go|rust|java|ruby|php)\b', re.IGNORECASE),
    'testing': re.compile(r'\b(pytest|jest|vitest|mocha|junit|rspec)\b', re.IGNORECASE),
}

def extract_via_patterns(task: str) -> list[Proposition] | None:
    """Fast extraction via regex - no LLM call needed."""
    propositions = []
    for prop_name, pattern in PROPOSITION_PATTERNS.items():
        match = pattern.search(task)
        if match:
            propositions.append(Proposition(
                name=prop_name,
                value=match.group(0).lower(),
                source="pattern"
            ))
    return propositions if propositions else None
```

Reference: `scripts/workflow_erotetic.py` contains the full pattern set with Q-value ordering.

### LLM Path: Claude CLI Subprocess

When patterns don't match, use Claude CLI subprocess (not direct API calls):

```python
# scripts/z3_erotetic_dynamic.py

PROPOSITION_PROMPT = """
Analyze this task and identify decision points that could go multiple ways.

Task: {task}

Return JSON:
{
  "propositions": [
    {
      "name": "category_name",
      "options": ["option1", "option2", "option3"],
      "prompt": "Question to ask user if not specified"
    }
  ]
}

Only include decisions that:
1. Have 2+ mutually exclusive options
2. Significantly affect implementation
3. Are not already specified in the task
"""

async def generate_propositions(task: str) -> list[Proposition]:
    """Generate propositions via Claude CLI subprocess."""

    # Fast path: pattern extraction (from workflow_erotetic.py)
    pattern_propositions = extract_via_patterns(task)
    if pattern_propositions:
        return pattern_propositions

    # LLM path: Claude CLI subprocess
    prompt = PROPOSITION_PROMPT.format(task=task)
    result = subprocess.run(
        ["claude", "-p", prompt,
         "--append-system-prompt", "Return ONLY valid JSON. Format: {\"propositions\": [...]}",
         "--output-format", "json"],
        capture_output=True, text=True, timeout=60
    )

    if result.returncode != 0:
        # Fallback: LMStudio or empty
        return await try_lmstudio_fallback(prompt)

    return parse_propositions(result.stdout)
```

### LMStudio Fallback

For offline use or when Claude CLI is unavailable, fall back to local LMStudio:

```python
async def try_lmstudio_fallback(prompt: str) -> list[Proposition]:
    """Fallback to LMStudio for offline proposition generation."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "http://localhost:1234/v1/chat/completions",
                json={
                    "model": "local-model",
                    "messages": [
                        {"role": "system", "content": "Return ONLY valid JSON. Format: {\"propositions\": [...]}"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1024
                }
            )

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return parse_propositions(content)

    except Exception:
        pass  # LMStudio not available

    # Ultimate fallback: return empty (will use hardcoded propositions)
    return []
```

**Fallback chain:**
1. Pattern extraction (0ms) - handles most cases
2. Claude CLI subprocess (~2s) - handles novel cases
3. LMStudio local (~1s) - offline fallback
4. Empty list - use hardcoded defaults

### Z3 Integration

```python
async def check_unknowns(task: str, user_input: str) -> list[str]:
    """Check for unknowns using dynamic propositions + Z3."""

    # Generate propositions for this task
    propositions = await generate_propositions(task)

    # Extract what user has already specified
    specified = extract_specified_values(user_input, propositions)

    # Use Z3 to find unconstrained propositions
    unknowns = z3_find_unknowns(propositions, specified)

    return [p.prompt for p in unknowns]
```

---

## Personalization

### Learning from Patterns

```python
# Track user choices in PostgreSQL
async def record_choice(
    user_id: str,
    proposition_name: str,
    chosen_option: str,
    context: str,
) -> None:
    await pool.execute("""
        INSERT INTO user_preferences (user_id, proposition, choice, context, count)
        VALUES ($1, $2, $3, $4, 1)
        ON CONFLICT (user_id, proposition, choice)
        DO UPDATE SET count = user_preferences.count + 1
    """, user_id, proposition_name, chosen_option, context)

# Use preferences to pre-fill or prioritize options
async def get_user_preferences(user_id: str) -> dict[str, str]:
    rows = await pool.fetch("""
        SELECT DISTINCT ON (proposition) proposition, choice
        FROM user_preferences
        WHERE user_id = $1
        ORDER BY proposition, count DESC
    """, user_id)
    return {row['proposition']: row['choice'] for row in rows}
```

### JSONL Backfill

During setup, extract patterns from existing sessions:

```python
# scripts/backfill_preferences.py

async def backfill_from_jsonl(jsonl_dir: str, user_id: str):
    """Extract user patterns from JSONL session logs."""

    for jsonl_file in Path(jsonl_dir).glob("*.jsonl"):
        with open(jsonl_file) as f:
            for line in f:
                event = json.loads(line)

                # Look for tool calls that reveal preferences
                if event.get("type") == "tool_use":
                    tool = event.get("tool_name")
                    params = event.get("parameters", {})

                    # Infer preferences from patterns
                    if tool == "Write" and ".ts" in params.get("path", ""):
                        await record_choice(user_id, "language", "typescript", "file_extension")

                    if tool == "Bash" and "pytest" in params.get("command", ""):
                        await record_choice(user_id, "test_framework", "pytest", "command_usage")
```

---

## Integration with AskUserQuestion

> **Reference**: See `00-architecture-decisions.md` for authoritative erotetic behavior.

### Gates BLOCK (Not Continue)

Per architecture decision: When E(X,Q) is not empty (unknowns exist), the gate MUST return `'block'`:

```python
async def erotetic_gate(task: str, user_input: str) -> dict:
    """Gate that BLOCKS if unknowns exist."""

    unknowns = await check_unknowns(task, user_input)

    if not unknowns:
        return {"result": "continue"}  # E(X,Q) = empty, proceed

    # E(X,Q) != empty: BLOCK and ask questions
    # Get user preferences to pre-fill
    preferences = await get_user_preferences(current_user_id())

    # Build AskUserQuestion with preferences
    questions = []
    for unknown in unknowns:
        options = get_options_for_proposition(unknown)

        # Prioritize user's preferred option
        if unknown.name in preferences:
            preferred = preferences[unknown.name]
            options = [preferred] + [o for o in options if o != preferred]

        questions.append({
            "question": unknown.prompt,
            "header": unknown.name,
            "options": [{"label": o, "description": ""} for o in options],
            "multiSelect": False,
        })

    # CRITICAL: Return 'block', not 'continue'
    return {
        "result": "block",
        "reason": "Resolve unknowns before proceeding",
        "questions": questions
    }
```

### Question Batching

Per architecture decision: Max 4 questions per round (AskUserQuestion tool limit).

```python
MAX_QUESTIONS_PER_ROUND = 4

async def erotetic_gate_with_batching(task: str, user_input: str) -> dict:
    """Gate with question batching - max 4 per round."""

    unknowns = await check_unknowns(task, user_input)

    if not unknowns:
        return {"result": "continue"}

    # Batch: max 4 questions per round
    # After user answers, recompute E(X,Q) and repeat
    batch = unknowns[:MAX_QUESTIONS_PER_ROUND]

    preferences = await get_user_preferences(current_user_id())
    questions = build_questions(batch, preferences)

    return {
        "result": "block",
        "reason": f"Resolve {len(unknowns)} unknowns ({len(batch)} this round)",
        "questions": questions,
        "remaining_unknowns": len(unknowns) - len(batch)
    }
```

---

## Z3 + Sentinel Division

Per architecture decision: Z3 handles composition validation, sentinel handles parameters.

| Component | Role | Timeout |
|-----------|------|---------|
| Z3 | Composition validation (goal consistency, mutual exclusion) | 2 seconds |
| Sentinel | Parameter extraction (tool/resource availability) | N/A |

```python
import asyncio

Z3_TIMEOUT_SECONDS = 2

async def hybrid_check(task: str, user_input: str) -> list[str]:
    """Z3 for composition, sentinel for parameters."""

    # Z3: Composition validation with timeout
    try:
        z3_unknowns = await asyncio.wait_for(
            z3_find_composition_unknowns(task, user_input),
            timeout=Z3_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        # Fallback to sentinel if Z3 times out
        z3_unknowns = await sentinel_composition_fallback(task, user_input)

    # Sentinel: Parameter extraction (no timeout needed, fast)
    param_unknowns = sentinel_extract_params(task, user_input)

    return z3_unknowns + param_unknowns
```

### Fallback Chain

1. **Z3** (2s timeout) - formal composition validation
2. **Sentinel** (fallback) - keyword-based detection if Z3 times out
3. **Empty list** - proceed if both fail (fail-open for UX)
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `scripts/z3_erotetic.py` | Add dynamic proposition support |
| `scripts/erotetic_skill_check.py` | Integrate with AskUserQuestion |
| `.claude/hooks/src/erotetic-clarification.ts` | Call dynamic Z3 |

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/z3_erotetic_dynamic.py` | LLM-based proposition generation |
| `scripts/backfill_preferences.py` | JSONL preference extraction |
| `scripts/user_preferences.py` | Preference storage/retrieval |

## Schema Additions

```sql
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    proposition TEXT NOT NULL,
    choice TEXT NOT NULL,
    context TEXT,
    count INTEGER DEFAULT 1,
    last_used TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, proposition, choice)
);

CREATE INDEX idx_preferences_user ON user_preferences(user_id);
```

# Module: Erotetic Logic & Temporal Memory

## Overview

This module documents the integration between erotetic (question-based) reasoning and temporal memory in RIGG. The system identifies WHAT is unconstrained (Z3), decides WHETHER to ask (ETO decision theory), and persists facts across session boundaries (temporal memory).

---

## Z3 Erotetic Integration

### Architecture

```
User Task
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                  Proposition Extraction                      │
│  ┌─────────────────┐    ┌─────────────────┐    ┌──────────┐ │
│  │  Pattern-Based  │───▶│  LLM (Claude)   │───▶│ LMStudio │ │
│  │  Fast Path      │    │  CLI Subprocess │    │ Offline  │ │
│  │  (0ms)          │    │  (~2s)          │    │ (~1s)    │ │
│  └─────────────────┘    └─────────────────┘    └──────────┘ │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                  Z3 Constraint Solver                        │
│  Encodes propositions as Boolean constraints                 │
│  Finds: E(X,Q) = {propositions not entailed by context}     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
Decision: Block (has unknowns) or Continue (all determined)
```

### Pattern-Based Fast Path

Most propositions are extracted via regex patterns with zero latency. This handles 80%+ of cases:

**Reference:** `scripts/workflow_erotetic.py`

```python
PROPOSITION_PATTERNS: dict[str, re.Pattern] = {
    'framework': re.compile(r'\b(fastapi|express|hono|gin|django|flask|rails|spring|nest\.?js)\b', re.IGNORECASE),
    'auth_method': re.compile(r'\b(jwt|oauth\d?|session|api[- ]?key|basic auth|bearer|saml|oidc)\b', re.IGNORECASE),
    'database': re.compile(r'\b(postgres(?:ql)?|mysql|sqlite|mongodb|redis|dynamodb|firestore)\b', re.IGNORECASE),
    'hosting': re.compile(r'\b(vercel|aws|gcp|azure|heroku|railway|fly\.io|cloudflare)\b', re.IGNORECASE),
    'language': re.compile(r'\b(python|typescript|javascript|go|rust|java|ruby|php)\b', re.IGNORECASE),
    'testing': re.compile(r'\b(pytest|jest|vitest|mocha|junit|rspec)\b', re.IGNORECASE),
}
```

### LLM Fallback via Claude Subprocess

When patterns do not match, the system invokes Claude CLI as a subprocess:

**Reference:** `docs/refactor/07-z3-erotetic.md`

```python
async def generate_propositions(task: str) -> list[Proposition]:
    """Generate propositions via Claude CLI subprocess."""

    # Fast path: pattern extraction
    pattern_propositions = extract_via_patterns(task)
    if pattern_propositions:
        return pattern_propositions

    # LLM path: Claude CLI subprocess
    result = subprocess.run(
        ["claude", "-p", prompt,
         "--append-system-prompt", "Return ONLY valid JSON.",
         "--output-format", "json"],
        capture_output=True, text=True, timeout=60
    )

    if result.returncode != 0:
        return await try_lmstudio_fallback(prompt)

    return parse_propositions(result.stdout)
```

### LMStudio Offline Fallback

For offline use or when Claude CLI is unavailable:

```python
async def try_lmstudio_fallback(prompt: str) -> list[Proposition]:
    """Fallback to LMStudio for offline proposition generation."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "http://localhost:1234/v1/chat/completions",
            json={
                "model": "local-model",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 1024
            }
        )
        # ... parse response
```

**Fallback Chain:**
1. Pattern extraction (0ms) - handles most cases
2. Claude CLI subprocess (~2s) - handles novel cases
3. LMStudio local (~1s) - offline fallback
4. Empty list - use hardcoded defaults

### Z3 check_evocation

The core function returns propositions that are UNKNOWN (not entailed):

**Reference:** `scripts/z3_erotetic.py`

```python
def check_evocation(propositions: dict[str, Any]) -> dict[str, Any]:
    """
    Check which propositions are UNKNOWN (not entailed by context).

    Returns:
        {
            "isEmpty": bool,      # True if no unknowns
            "unknowns": list,     # Unknown proposition names
            "count": int          # Number of unknowns
        }
    """
```

**Unknown Values:**
- `None` = unknown proposition
- `"UNKNOWN"` (uppercase string) = unknown proposition

**Known Values (everything else):**
- `True`, `False` (booleans)
- Numbers, strings (other than "UNKNOWN")
- Lists, dicts (complex values are considered resolved)

---

## Decision Theory (ETO) Layer

Z3 identifies WHAT is unconstrained. ETO decides WHETHER to ask.

### Expected Utility Calculation

```
Expected Utility = P(wrong) * cost_of_wrong - cost_of_asking
```

Where:
- `P(wrong)` = probability of making wrong assumption
- `cost_of_wrong` = cost of implementing with wrong assumption (tokens, rework)
- `cost_of_asking` = cost of interrupting user (context switch, latency)

### Decision Rule

```python
def should_ask(proposition: str, context: dict) -> bool:
    """Decide whether to ask about a proposition using ETO."""

    p_wrong = estimate_wrong_probability(proposition, context)
    cost_wrong = estimate_wrong_cost(proposition)
    cost_ask = ASKING_COST  # Fixed overhead (~50 tokens + user latency)

    expected_utility = p_wrong * cost_wrong - cost_ask

    return expected_utility > 0
```

### Utility Values by Proposition Type

Based on Q-value ranking from `scripts/erotetic_q_ranking.py`:

| Proposition | Q-Value | Why | Ask When... |
|-------------|---------|-----|-------------|
| framework | HIGH | Partitions entire solution architecture | Almost always |
| auth_method | HIGH | Determines middleware stack, token storage | Almost always |
| database | HIGH | Affects data model, queries, migrations | Almost always |
| language | HIGH | Determines runtime, dependencies, tooling | Almost always |
| hosting | MED | Affects deployment but changeable | If cost > threshold |
| testing | MED | Affects quality but not core architecture | If cost > threshold |
| styling | MED | Affects UI but mostly orthogonal | Rarely |

### Skip Low-Value Questions

Questions with low expected utility are skipped:

```python
# Skip if:
# 1. Proposition has LOW Q-value AND
# 2. Context provides strong prior AND
# 3. Cost of asking exceeds expected benefit

if q_config.q_value == "LOW" and prior_confidence > 0.8:
    return False  # Skip asking, use prior
```

---

## Utility Value Learning

### Learning from History

Track when assumptions were wrong to calibrate P(wrong):

**Reference:** `docs/refactor/07-z3-erotetic.md`

```python
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
```

### user_preferences Table Schema

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

### Personalization via Preferences

Retrieve user's historical choices to pre-fill options:

```python
async def get_user_preferences(user_id: str) -> dict[str, str]:
    rows = await pool.fetch("""
        SELECT DISTINCT ON (proposition) proposition, choice
        FROM user_preferences
        WHERE user_id = $1
        ORDER BY proposition, count DESC
    """, user_id)
    return {row['proposition']: row['choice'] for row in rows}
```

---

## Question Decomposition Display

### Always Show Decomposition

Questions are always shown to the user with full decomposition:

**Reference:** `scripts/temporal_memory/handoff.py`

```markdown
## Open Questions (E(X,Q) - PRIORITY)
| Question | Q-Value | Why Ask First |
|----------|---------|---------------|
| framework | HIGH | Framework choice partitions entire solution architecture |
| auth_method | HIGH | Auth method determines middleware stack, token storage |
| database | HIGH | Database choice affects data model, queries, migrations |
```

### Collapsible Question Tree

UI representation for multi-level decomposition:

```
▼ Build a REST API for user management
  ├─ ▶ [HIGH] What framework? (FastAPI, Express, Django...)
  │     └─ Affects: routing, middleware, async support
  ├─ ▶ [HIGH] What authentication? (JWT, OAuth, Session...)
  │     └─ Affects: security, session handling, token storage
  └─ ▶ [HIGH] What database? (PostgreSQL, MySQL, MongoDB...)
        └─ Affects: data model, queries, migrations
```

### User Can Edit Sub-Questions

Users can:
1. Dismiss irrelevant questions (mark as answered with default)
2. Add custom questions not detected
3. Reorder by personal priority
4. Provide partial answers that trigger new sub-questions

---

## Temporal Memory

### Architecture

**Reference:** `scripts/temporal_memory/store_pg.py`

```
┌─────────────────────────────────────────────────────────────┐
│                    Temporal Memory Store                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           temporal_facts Table                       │    │
│  │  - session_id: Session isolation                    │    │
│  │  - key: Fact name                                   │    │
│  │  - value: Current value                             │    │
│  │  - turn_established: When first set                 │    │
│  │  - turn_last_changed: When last modified            │    │
│  │  - change_count: Number of revisions                │    │
│  │  - confidence: Calibrated confidence score          │    │
│  │  - embedding: pgvector (1024 dim) for similarity    │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           temporal_traces Table                      │    │
│  │  - session_id: Session isolation                    │    │
│  │  - turn: Turn number                                │    │
│  │  - facts_json: Snapshot of all facts at turn        │    │
│  │  - erotetic_json: E(X,Q) result at turn             │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Factory Pattern: Backend Selection

**Reference:** `scripts/temporal_memory/factory.py`

```python
TemporalBackendType = Literal["sqlite", "postgres"]

async def create_temporal_store(
    backend: TemporalBackendType = "sqlite",
    session_id: str = "default",
    db_path: Path | None = None,
) -> Union["TemporalMemoryStore", "TemporalMemoryStorePG"]:
    """Create temporal store with specified backend."""

    if backend == "sqlite":
        from scripts.temporal_memory.store import TemporalMemoryStore
        store = TemporalMemoryStore(session_id=session_id, db_path=db_path)
    elif backend == "postgres":
        from scripts.temporal_memory.store_pg import TemporalMemoryStorePG
        store = TemporalMemoryStorePG(session_id=session_id)

    await store.connect()
    return store
```

**Environment Configuration:**
- `TEMPORAL_BACKEND=sqlite` (default, development)
- `TEMPORAL_BACKEND=postgres` (production)

### Hot/Cold Tiering (90-Day Archival)

**Reference:** `docs/refactor/20-temporal-archival.md`

| Tier | Storage | Age | Access |
|------|---------|-----|--------|
| Hot | PostgreSQL | 0-90 days | Full query, vector search |
| Cold | Disk (gzipped JSONL) | >90 days | Manual restore |

**Archival Strategy by Fact Type:**

| Fact Type | Archival Action |
|-----------|-----------------|
| Invariants (G()) | Keep forever (already minimal, high value) |
| High-utility transitions | Archive as-is |
| Low-utility HOLDS | Prune (transition history captures changes) |
| Embeddings | Drop (re-compute if needed) |

### pgvector for Embeddings

Vector similarity search for semantic recall:

```python
async def search_similar(
    self,
    query_embedding: list[float],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search facts by vector similarity using pgvector."""

    async with get_connection() as conn:
        await init_pgvector(conn)

        rows = await conn.fetch("""
            SELECT
                key, value, confidence,
                1 - (embedding <=> $2::vector) as similarity
            FROM temporal_facts
            WHERE session_id = $1 AND embedding IS NOT NULL
            ORDER BY embedding <=> $2::vector
            LIMIT $3
        """, self.session_id, query_embedding, limit)

        return [{"key": r["key"], "value": r["value"],
                 "similarity": r["similarity"]} for r in rows]
```

### Inertia Rule

**Reference:** `scripts/temporal_memory/inertia.py`

TEL inertia rule for belief persistence:
```
holds(P, T+1) :- holds(P, T), not -holds(P, T+1)
```

Facts persist unless explicitly negated:

```python
def apply_inertia(
    facts_at_t: dict[str, Any],
    updates_at_t_plus_1: dict[str, Any]
) -> dict[str, Any]:
    """Apply inertia rule to compute facts at T+1."""
    result = dict(facts_at_t)  # Persisted facts
    result.update(updates_at_t_plus_1)  # Explicit updates
    return result
```

**Priority Hierarchy for Conflict Resolution:**
```
EXPLICIT_NEGATION > RECENT_OBSERVATION > INVARIANT > HISTORICAL
```

---

## Context Management

### Never Hit Context Window

Session handoffs preserve continuity without context overflow.

### Invisible Handoffs at 65% + Growth Rate Detection

**Trigger Conditions:**
1. Context usage exceeds 65% threshold
2. Growth rate indicates imminent overflow
3. Approaching hard limit (128k tokens)

```
┌─────────────────────────────────────────────────────────────┐
│                  Context Monitor                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  if context_usage > 0.65 and growth_rate > threshold:       │
│      trigger_handoff()                                       │
│                                                              │
│  Growth Rate = (current_tokens - previous_tokens) / turns    │
│                                                              │
│  Threshold = (max_tokens * 0.35) / estimated_remaining_turns │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Summarize -> Temporal Memory -> Fresh Session

**Handoff Pipeline:**

```
1. Detect threshold (65% + growth rate)
         │
         ▼
2. Generate temporal summary
   - Invariants (facts that never changed)
   - Current state snapshot
   - Pending goals (unchecked items)
   - Open questions (ranked by Q-value)
   - Recent transitions (utility-ranked)
         │
         ▼
3. Store in temporal memory
   - Persist to PostgreSQL/SQLite
   - Index for vector search
         │
         ▼
4. Create handoff document
   - thoughts/shared/handoffs/{session}/
   - Structured markdown with all context
         │
         ▼
5. Clear context (fresh session)
   - /clear command
   - SessionStart hook loads ledger
         │
         ▼
6. Resume from handoff
   - Continuity ledger provides state
   - Temporal memory provides history
```

### Continuity Ledger Pattern

**Reference:** `.claude/rules/continuity.md`

The ledger is the single source of truth:

```markdown
# CONTINUITY_CLAUDE-{session-name}.md

## State
- Done:
  - [x] Phase 1: Setup database schema
  - [x] Phase 2: Create API endpoints
- Now: [→] Phase 3: Add validation logic
- Next: Phase 4: Frontend components
- Remaining:
  - [ ] Phase 5: Wire up API calls
  - [ ] Phase 6: Write tests

## Working Set
- Files: /path/to/relevant/files
- Branch: feature/xyz
- Test: pytest tests/

## Open Questions
- UNCONFIRMED: Does the auth middleware need updating?
```

**Why file-based checkboxes:** TodoWrite survives compaction, but the understanding around those todos degrades each time context is compressed. File-based checkboxes are never compressed - full fidelity preserved.

### TemporalHandoffState

**Reference:** `scripts/temporal_memory/handoff.py`

```python
@dataclass
class TemporalHandoffState:
    """Extended handoff state with temporal information."""

    context: str = ""                    # Current work description
    next_instruction: str = ""           # What to do next
    invariants: dict[str, Any]           # Facts that never changed
    current_state: dict[str, Any]        # All current facts
    eventualities: list[str]             # Pending goals
    open_questions: list[tuple[str, str, str]]  # (name, Q-value, why)
    transitions: list[str]               # Recent state changes
    turn_count: int = 0                  # Current turn number

    def to_markdown(self) -> str:
        """Generate structured handoff document."""
        # ... produces markdown with all sections
```

### Temporal Summary for Handoffs

**Reference:** `scripts/temporal_memory/summarizer.py`

Token-budgeted summary generation:

```python
async def summarize(
    self, store: TemporalMemoryStore, budget_tokens: int = 2000
) -> TemporalSummary:
    """Generate token-budgeted temporal summary."""

    return TemporalSummary(
        open_questions=await store.get_open_questions(),
        invariants=[inv.to_compact() for inv in await self.extract_invariants(store)],
        pending_goals=await self._extract_pending_goals(store),
        transitions=[f"T={t.turn}: {t.from_state} -> {t.to_state}"
                    for t in await self.extract_transitions(store)],
        current_state=await store.get_current_state(),
        turn_count=store._current_turn,
        token_estimate=computed_tokens
    )
```

**Utility-Based Transition Ranking:**

```python
def _compute_utility(self, transition, current_turn, q_value=1.0):
    """U(event) = importance * recency * access_frequency"""

    age = current_turn - transition.turn
    recency = 0.5 ** (age / 15)  # 15-turn half-life

    return q_value * recency * frequency_factor
```

---

## File References

| File | Purpose |
|------|---------|
| `scripts/z3_erotetic.py` | Core E(X,Q) computation |
| `scripts/workflow_erotetic.py` | Pattern extraction, gate evaluation |
| `scripts/erotetic_q_ranking.py` | Q-value ranking by architectural impact |
| `scripts/temporal_memory/store.py` | SQLite temporal store |
| `scripts/temporal_memory/store_pg.py` | PostgreSQL temporal store |
| `scripts/temporal_memory/factory.py` | Backend factory pattern |
| `scripts/temporal_memory/inertia.py` | TEL inertia rules |
| `scripts/temporal_memory/summarizer.py` | Token-budgeted summarization |
| `scripts/temporal_memory/handoff.py` | Agent-to-agent state transfer |
| `docs/refactor/07-z3-erotetic.md` | Z3 integration specification |
| `docs/refactor/20-temporal-archival.md` | Hot/cold tiering strategy |

---

## Integration Points

### With Gate System

The erotetic gate is one of three gates in the composition pipeline:

```
User Prompt
    │
    ├─▶ [E] Erotetic Gate ──▶ Block if unknowns exist
    │
    ├─▶ [R] Resource Gate ──▶ Block if resources unavailable
    │
    └─▶ [C] Composition Gate ──▶ Block if composition invalid
```

### With AskUserQuestion

When gate blocks, generate structured questions:

```python
async def erotetic_gate(task: str, user_input: str) -> dict | None:
    unknowns = await check_unknowns(task, user_input)

    if not unknowns:
        return None  # Proceed

    preferences = await get_user_preferences(current_user_id())

    questions = []
    for unknown in unknowns:
        options = get_options_for_proposition(unknown)
        if unknown.name in preferences:
            options = [preferences[unknown.name]] + [o for o in options if o != preferred]

        questions.append({
            "question": unknown.prompt,
            "header": unknown.name,
            "options": [{"label": o} for o in options],
            "multiSelect": False,
        })

    return {"action": "ask", "questions": questions}
```

### With Braintrust Tracing

Temporal facts are indexed in Braintrust for cross-session learning:

```
temporal_facts → Braintrust spans → Pattern extraction → Skill generation
```

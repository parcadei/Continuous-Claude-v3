# Phase 2: Mutation Testing & Gap Analysis

**Created**: 2025-12-29
**Status**: IN_PROGRESS

## Goal
Mutation test existing fixes, research missed bug patterns, fill gaps, triple-verify with Nia.

## Phase 1 Complete (11 HIGH issues fixed)
- 54 unit tests + 12 E2E tests passing
- 5 implementations: SQLite, httpx, patterns, postgres, span_processor
- All jury-approved

## Phase 2 Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: MUTATION TESTING                                        │
│  → Mutate concurrency tests to find weak assertions              │
│  → Output: docs/concurrency-search/agent-outputs/mutations/      │
├─────────────────────────────────────────────────────────────────┤
│  Step 2: NIA RESEARCH - Bug Categories                           │
│  → Research: asyncio concurrency bugs, Python threading pitfalls │
│  → Research: SQLite WAL edge cases, connection pool antipatterns │
│  → Output: docs/concurrency-search/agent-outputs/research/       │
├─────────────────────────────────────────────────────────────────┤
│  Step 3: GAP ANALYSIS                                            │
│  → Compare mutations + research to find missed patterns          │
│  → Output: docs/concurrency-search/agent-outputs/gaps/           │
├─────────────────────────────────────────────────────────────────┤
│  Step 4: TDD - Write Failing Tests                               │
│  → Tests for each gap identified                                 │
│  → Output: tests/unit/test_concurrency_gaps.py                   │
├─────────────────────────────────────────────────────────────────┤
│  Step 5: IMPLEMENT Fixes                                         │
│  → Fix each gap to pass tests                                    │
│  → Output: docs/concurrency-search/agent-outputs/implementations/│
├─────────────────────────────────────────────────────────────────┤
│  Step 6: MUTATION Round 2                                        │
│  → Mutate new tests to verify coverage                           │
├─────────────────────────────────────────────────────────────────┤
│  Step 7: NIA VALIDATION                                          │
│  → Triple-check all fixes against documentation                  │
│  → No assumptions - verify every pattern                         │
└─────────────────────────────────────────────────────────────────┘
```

## Files to Mutate
- tests/unit/test_sqlite_busy_timeout.py
- tests/unit/test_embedding_client_reuse.py
- tests/unit/test_pattern_concurrency.py
- tests/unit/test_postgres_pool_timeout.py
- tests/unit/test_span_processor_async_lock.py
- tests/integration/test_concurrency_e2e.py

## Research Topics for Nia
1. Python asyncio.Lock vs threading.Lock edge cases
2. SQLite WAL mode corruption scenarios
3. asyncpg connection pool best practices
4. httpx.AsyncClient lifecycle patterns
5. Concurrent data structure patterns in Python

## Working Set
- Branch: feature/agentica-integration
- Test cmd: `uv run pytest tests/unit/test_concurrency_*.py -v`
- Mutation cmd: `uv run mutmut run --paths-to-mutate=<file>`

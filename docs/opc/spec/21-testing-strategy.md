# Module: Testing Strategy

## Overview

Comprehensive testing across 4 layers: unit, E2E, property-based, integration.

---

## Priority Order

1. **Unit tests** - Fastest feedback, component isolation
2. **E2E sessions** - Full session simulation
3. **Property-based** - Algebra laws, edge cases
4. **Integration tests** - Pattern combinations, DB coordination

---

## Unit Tests

### Pattern Components

```python
# tests/unit/test_patterns.py
import pytest
from scripts.agentica_patterns import spawn_agent, wait_for_all

async def test_spawn_agent_depth_limit():
    """Spawn should fail at depth 3."""
    os.environ["DEPTH_LEVEL"] = "3"

    with pytest.raises(DepthLimitExceeded):
        spawn_agent("test prompt")

async def test_spawn_registers_in_db():
    """Agent should be registered before process starts."""
    agent = spawn_agent("test prompt")

    # Check DB immediately (before process can complete)
    row = await pool.fetchrow(
        "SELECT * FROM agents WHERE agent_id = $1",
        agent.agent_id
    )
    assert row is not None
    assert row["status"] == "running"
```

### PostgreSQL Coordination

```python
# tests/unit/test_coordination.py
async def test_optimistic_locking():
    """Optimistic locking should retry on conflict."""
    # Setup: two concurrent updates
    async def update_1():
        await write_result(agent_id, {"vote": "yes"}, "jury")

    async def update_2():
        await write_result(agent_id, {"vote": "no"}, "jury")

    # One should succeed, one should retry
    results = await asyncio.gather(update_1(), update_2())

    # Verify final state is consistent
    row = await pool.fetchrow("SELECT * FROM agent_results WHERE agent_id = $1", agent_id)
    assert row is not None
```

---

## E2E Session Tests

```python
# tests/e2e/test_full_session.py
async def test_swarm_session():
    """Full swarm session from spawn to completion."""

    # Start session
    session = await start_session()

    # Execute swarm pattern
    result = await execute_pattern(
        pattern="swarm",
        task="Research authentication patterns",
        perspectives=["security", "performance", "usability"]
    )

    # Verify all agents completed
    agents = await pool.fetch(
        "SELECT * FROM agents WHERE session_id = $1",
        session.id
    )
    assert len(agents) == 3
    assert all(a["status"] == "completed" for a in agents)

    # Verify synthesis
    assert result.synthesis is not None
    assert len(result.agent_outputs) == 3
```

---

## Property-Based Tests

### Pattern Algebra Laws

```python
# tests/property/test_algebra.py
from hypothesis import given, strategies as st

@given(st.lists(st.text(), min_size=2, max_size=5))
async def test_parallel_commutativity(agents):
    """A | B = B | A (parallel is commutative)."""
    result_ab = await parallel(agents)
    result_ba = await parallel(list(reversed(agents)))

    # Results should be equivalent (order doesn't matter)
    assert set(result_ab.keys()) == set(result_ba.keys())

@given(st.lists(st.text(), min_size=3, max_size=5))
async def test_sequential_associativity(stages):
    """(A ; B) ; C = A ; (B ; C)."""
    # Left association
    ab = await sequential([stages[0], stages[1]])
    abc_left = await sequential([ab, stages[2]])

    # Right association
    bc = await sequential([stages[1], stages[2]])
    abc_right = await sequential([stages[0], bc])

    assert abc_left == abc_right
```

---

## Integration Tests

```python
# tests/integration/test_patterns.py
async def test_hierarchical_with_swarm():
    """Hierarchical coordinator with swarm workers."""

    result = await execute_pattern(
        pattern="hierarchical",
        coordinator_prompt="Coordinate security audit",
        worker_pattern="swarm",
        workers=3
    )

    # Verify coordinator ran
    assert result.coordinator_output is not None

    # Verify all workers ran
    assert len(result.worker_outputs) == 3

    # Verify DB state
    agents = await pool.fetch("SELECT * FROM agents WHERE pattern = 'hierarchical'")
    assert len(agents) == 4  # 1 coordinator + 3 workers
```

---

## Coverage Targets

| Component | Target |
|-----------|--------|
| All 11 patterns | 100% |
| Sub-agent spawning | 100% |
| PostgreSQL coordination | 100% |
| Meta-learning depth limits | 100% |
| Error recovery paths | 90% |
| Temporal memory | 90% |

---

## Test Commands

```bash
# Unit tests
uv run pytest tests/unit/ -v

# E2E tests (requires Docker stack)
uv run pytest tests/e2e/ -v --docker

# Property tests
uv run pytest tests/property/ -v --hypothesis-show-statistics

# Integration tests
uv run pytest tests/integration/ -v

# Full suite
uv run pytest tests/ -v --cov=scripts
```

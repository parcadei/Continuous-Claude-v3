# Module: Testing Strategy

## Overview

Comprehensive testing: unit tests for components, integration tests for patterns, E2E tests for full workflows. Mock headless agents for fast testing.

---

## Test Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           E2E Tests                                         │
│  - Full pattern execution with real agents                                  │
│  - Setup wizard flow                                                        │
│  - TUI interaction                                                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Integration Tests                                     │
│  - Pattern coordination (spawn, wait, aggregate)                            │
│  - Database operations (PostgreSQL, Redis)                                  │
│  - Hook execution chains                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Unit Tests                                        │
│  - Individual functions                                                     │
│  - Data models                                                              │
│  - Utility functions                                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Unit Tests

### Pattern Logic

```python
# tests/unit/test_patterns.py
import pytest
from scripts.agentica_patterns.patterns.swarm import SwarmPattern
from scripts.agentica_patterns.primitives import Aggregator

class TestSwarmPattern:

    def test_swarm_aggregation(self):
        """Test swarm result aggregation."""
        aggregator = Aggregator(strategy="consensus")

        results = [
            {"finding": "Security issue in auth.py", "confidence": 0.9},
            {"finding": "Security issue in auth.py", "confidence": 0.8},
            {"finding": "Performance issue in db.py", "confidence": 0.7},
        ]

        aggregated = aggregator.aggregate(results)

        assert len(aggregated) == 2
        assert aggregated[0]["finding"] == "Security issue in auth.py"
        assert aggregated[0]["confidence"] > 0.8  # Combined confidence

    def test_quorum_calculation(self):
        """Test quorum thresholds."""
        pattern = SwarmPattern(agent_count=5)

        assert pattern.get_quorum(3) == 2  # 3 agents, need 2
        assert pattern.get_quorum(5) == 3  # 5 agents, need 3 (majority)
```

### Z3 Erotetic Logic

```python
# tests/unit/test_z3_erotetic.py
import pytest
from scripts.z3_erotetic_dynamic import generate_propositions, check_unknowns

class TestZ3Erotetic:

    @pytest.mark.asyncio
    async def test_proposition_generation(self):
        """Test dynamic proposition generation."""
        task = "Implement user authentication"

        propositions = await generate_propositions(task)

        assert len(propositions) > 0
        assert any(p.name == "auth_method" for p in propositions)

    @pytest.mark.asyncio
    async def test_unknown_detection(self):
        """Test unknown detection."""
        task = "Implement authentication"
        user_input = "Use OAuth"

        unknowns = await check_unknowns(task, user_input)

        # OAuth specified, but storage might be unknown
        assert "auth_method" not in [u.name for u in unknowns]
```

---

## Integration Tests

### Pattern Coordination

```python
# tests/integration/test_pattern_coordination.py
import pytest
import asyncio
from scripts.claude_spawn import spawn_agent, wait_for_all
from scripts.agentica_patterns.coordination_pg import CoordinationDB

class TestPatternCoordination:

    @pytest.fixture
    async def coordination_db(self):
        """Setup test database."""
        db = CoordinationDB(test_mode=True)
        await db.initialize()
        yield db
        await db.cleanup()

    @pytest.mark.asyncio
    async def test_swarm_coordination(self, coordination_db):
        """Test swarm agent coordination."""
        # Use mock agents for speed
        agents = []
        for i in range(3):
            agent = await spawn_mock_agent(f"Research angle {i}")
            agents.append(agent)

        # Wait for all
        results = await wait_for_all(agents, timeout=10)

        assert len(results) == 3
        assert all(r.status == "completed" for r in results)

    @pytest.mark.asyncio
    async def test_blackboard_polling(self, coordination_db):
        """Test blackboard message exchange."""
        swarm_id = "test-swarm"

        # Sentinel posts directive
        await coordination_db.post_to_blackboard(
            swarm_id=swarm_id,
            sender="sentinel",
            message_type="directive",
            target_agent="agent-1",
            payload={"action": "correct", "message": "Fix the bug"},
        )

        # Agent polls
        messages = await coordination_db.poll_blackboard(
            swarm_id=swarm_id,
            agent_id="agent-1",
        )

        assert len(messages) == 1
        assert messages[0]["payload"]["action"] == "correct"
```

### Mock Agent

```python
# tests/fixtures/mock_agent.py
from dataclasses import dataclass
import asyncio

@dataclass
class MockAgent:
    agent_id: str
    prompt: str
    delay: float = 0.5

    async def run(self) -> dict:
        """Simulate agent execution."""
        await asyncio.sleep(self.delay)
        return {
            "status": "completed",
            "result": f"Mock result for: {self.prompt[:50]}",
        }

async def spawn_mock_agent(prompt: str) -> MockAgent:
    """Spawn a mock agent for testing."""
    agent = MockAgent(
        agent_id=generate_uuid(),
        prompt=prompt,
    )
    asyncio.create_task(agent.run())
    return agent
```

---

## E2E Tests

### Full Pattern Execution

```python
# tests/e2e/test_swarm_e2e.py
import pytest
import subprocess

class TestSwarmE2E:

    @pytest.mark.slow
    @pytest.mark.e2e
    def test_real_swarm_execution(self):
        """Test real swarm pattern with Claude agents."""

        # This spawns real agents - slow but comprehensive
        result = subprocess.run([
            "uv", "run", "python", "scripts/test_swarm_e2e.py",
            "--query", "What are best practices for error handling?",
            "--num-agents", "3",
            "--timeout", "120",
        ], capture_output=True, text=True, timeout=180)

        assert result.returncode == 0
        assert "completed" in result.stdout.lower()
```

### Setup Wizard

```python
# tests/e2e/test_setup_wizard.py
import pytest
from unittest.mock import patch

class TestSetupWizard:

    @pytest.mark.e2e
    def test_setup_flow(self, tmp_path):
        """Test setup wizard flow."""

        with patch('rich.prompt.Confirm.ask') as mock_confirm:
            # Simulate user inputs
            mock_confirm.side_effect = [
                True,   # Start Docker
                True,   # Initialize DB
                False,  # Skip math features
            ]

            from scripts.setup_wizard import main
            main(project_dir=tmp_path)

            # Verify files created
            assert (tmp_path / '.claude' / 'settings.json').exists()
            assert (tmp_path / 'docker' / 'docker-compose.yml').exists()
```

---

## CI Configuration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run pytest tests/unit -v

  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
      redis:
        image: redis:7
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run pytest tests/integration -v
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/postgres

  e2e:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: docker compose -f docker/docker-compose.yml up -d
      - run: uv run pytest tests/e2e -v --timeout=300
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `tests/unit/test_patterns.py` | Pattern unit tests |
| `tests/unit/test_z3_erotetic.py` | Z3 logic tests |
| `tests/integration/test_pattern_coordination.py` | Integration tests |
| `tests/e2e/test_swarm_e2e.py` | E2E pattern tests |
| `tests/fixtures/mock_agent.py` | Mock agent utilities |
| `.github/workflows/test.yml` | CI configuration |

## Test Commands

```bash
# Unit tests (fast)
uv run pytest tests/unit -v

# Integration tests (requires Docker)
docker compose up -d
uv run pytest tests/integration -v

# E2E tests (slow, real agents)
uv run pytest tests/e2e -v --timeout=300

# All tests with coverage
uv run pytest --cov=scripts --cov-report=html
```

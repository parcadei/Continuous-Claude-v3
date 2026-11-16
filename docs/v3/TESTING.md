# Testing

Test suite documentation and contribution guide for claude-continuity-kit.

## Overview

- **2626+ tests** covering patterns, hooks, security, memory, and MCP runtime
- **pytest + pytest-asyncio** for async test support
- **Unit + Integration + E2E** test levels
- **TDD approach** - many tests written before implementation

## Running Tests

### All Tests

```bash
uv run pytest -v
```

### Quick Smoke Test

```bash
uv run pytest tests/unit/test_greeting.py -v
```

### Specific Categories

```bash
# Unit tests only (~2400 tests)
uv run pytest tests/unit/ -v

# Integration tests (~200 tests)
uv run pytest tests/integration/ -v

# Pattern tests (Agentica orchestration patterns)
uv run pytest tests/unit/test_agentica_*.py -v

# Hook handler tests
uv run pytest tests/unit/test_*_handlers.py -v

# Security tests
uv run pytest tests/unit/test_security_*.py -v

# Memory/persistence tests
uv run pytest tests/unit/test_memory_*.py -v

# Async bug detection tests
uv run pytest tests/unit/test_async_*.py -v
```

### With Coverage

```bash
uv run pytest --cov=scripts/agentica --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Parallel Execution

```bash
# Install pytest-xdist first
uv add pytest-xdist --dev

# Run tests in parallel
uv run pytest -n auto
```

## Test Organization

| Directory | Purpose | Count |
|-----------|---------|-------|
| `tests/unit/` | Unit tests for patterns, hooks, security | ~2400 |
| `tests/integration/` | Integration tests with real MCP servers | ~200 |
| `tests/` (root) | Artifact index and query tests | ~30 |

### Unit Test Categories

| Category | Files | Description |
|----------|-------|-------------|
| **Pattern Tests** | `test_agentica_*.py` (19) | Orchestration patterns (Swarm, Pipeline, etc.) |
| **Pattern Type Tests** | `test_*_pattern_type.py` (11) | Environment variable propagation |
| **Handler Tests** | `test_*_handlers.py` (11) | Hook handler implementations |
| **Security Tests** | `test_security_*.py` (7) | Path traversal, injection, threading |
| **Router Tests** | `test_*_router.py` (5) | PreToolUse/SubagentStart routing |
| **Subagent Tests** | `test_subagent_*.py` (4) | Agent lifecycle hooks |
| **Memory Tests** | `test_memory_*.py` (5) | Memory service, PostgreSQL, backfill |
| **Async Bug Tests** | `test_async_*.py` (5) | Race conditions, lock safety |
| **CRUD Tests** | `test_crud_*.py` (6) | Pattern CRUD operations |

### Integration Tests

| File | Description |
|------|-------------|
| `test_agentica_server_integration.py` | Agentica server lifecycle |
| `test_broadcast_flow.py` | Inter-agent broadcast messaging |
| `test_claude_scope_e2e.py` | Claude Code tool sandbox |
| `test_hook_integration.py` | Full hook pipeline E2E |
| `test_llm_span_memory_e2e.py` | LLM span memory persistence |
| `test_memory_e2e.py` | Memory service E2E |
| `test_postgres_setup.py` | PostgreSQL setup verification |
| `test_security_e2e.py` | Security controls E2E |
| `test_sqlite_to_postgres_migration.py` | Database migration |
| `test_v3_integration.py` | V3 API integration |

## Writing Tests

### Pattern Tests

Pattern tests verify Agentica orchestration patterns work correctly.

```python
"""Tests for Agentica Swarm pattern."""

import pytest
from unittest.mock import AsyncMock, patch
from scripts.agentica.patterns import Swarm, AggregateMode

class TestSwarmParallelExecution:
    """Test that swarm runs agents in parallel."""

    @pytest.mark.asyncio
    async def test_swarm_spawns_correct_number_of_agents(self):
        """Swarm should spawn one agent per perspective."""
        perspectives = ["Expert 1", "Expert 2", "Expert 3"]
        swarm = Swarm(perspectives=perspectives)

        with patch('scripts.agentica.patterns.swarm.spawn') as mock_spawn:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value={"result": "test"})
            mock_spawn.return_value = mock_agent

            await swarm.execute("Test query")

            assert mock_spawn.call_count == 3
```

### Hook Tests

Hook tests verify shell wrappers and TypeScript handlers.

```python
"""Tests for SessionEnd Cleanup Hook."""

import os
import subprocess
from pathlib import Path
import pytest

class TestSessionEndHookFiles:
    """Tests for hook file existence and structure."""

    @pytest.fixture
    def hooks_dir(self) -> Path:
        """Path to hooks directory."""
        return Path(__file__).parents[2] / ".claude" / "hooks"

    def test_shell_wrapper_exists(self, hooks_dir: Path) -> None:
        """Shell wrapper exists at expected path."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"
        assert shell_wrapper.exists()

    def test_shell_wrapper_is_executable(self, hooks_dir: Path) -> None:
        """Shell wrapper has executable permission."""
        shell_wrapper = hooks_dir / "session-end-cleanup-swarms.sh"
        if not shell_wrapper.exists():
            pytest.skip("Shell wrapper doesn't exist yet")
        assert os.access(shell_wrapper, os.X_OK)

    def test_typescript_handler_exists(self, hooks_dir: Path) -> None:
        """TypeScript handler exists at expected path."""
        ts_handler = hooks_dir / "src" / "session-end-cleanup-swarms.ts"
        assert ts_handler.exists()
```

### Security Tests

Security tests verify path canonicalization and injection prevention.

```python
"""Security tests for path canonicalization."""

import pytest
from pathlib import Path

class TestCanonicalizePathHelper:
    """Test _canonicalize_path helper function."""

    def test_canonicalize_raises_when_path_escapes_project_dir(self, tmp_path):
        """Should raise ValueError when path escapes project_dir."""
        from scripts.agentica.claude_scope import _canonicalize_path

        project_dir = tmp_path / "project"
        project_dir.mkdir()

        with pytest.raises(ValueError):
            _canonicalize_path("../secret.txt", str(project_dir))
```

### Integration Tests

Integration tests verify end-to-end flows with real databases.

```python
"""E2E Integration Tests for Hook Flow."""

import sqlite3
import tempfile
from pathlib import Path
from uuid import uuid4
import pytest

@pytest.fixture
def temp_coordination_db(tmp_path: Path) -> tuple[Path, str]:
    """Create a temp coordination database with broadcasts."""
    cache_dir = tmp_path / ".claude" / "cache" / "agentica-coordination"
    cache_dir.mkdir(parents=True)
    db_path = cache_dir / "coordination.db"
    swarm_id = f"test-swarm-{uuid4().hex[:8]}"

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS broadcasts (
            id INTEGER PRIMARY KEY,
            swarm_id TEXT,
            sender_id TEXT,
            message TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

    return db_path, swarm_id
```

## Fixtures

### Common Fixtures

Located in `tests/integration/conftest.py`:

```python
@pytest.fixture(scope="session", autouse=True)
def mcp_config_for_tests(tmp_path_factory):
    """Verify MCP config exists for integration tests."""
    project_root = Path(__file__).parent.parent.parent
    mcp_json = project_root / ".mcp.json"
    mcp_config_json = project_root / "mcp_config.json"

    if mcp_json.exists():
        yield mcp_json
    elif mcp_config_json.exists():
        yield mcp_config_json
    else:
        pytest.skip("No MCP config found")


@pytest.fixture(autouse=True)
async def cleanup_mcp_manager():
    """Cleanup MCP client manager after each test."""
    yield
    try:
        manager = get_mcp_client_manager()
        if manager._state.value != "uninitialized":
            await manager.cleanup()
    finally:
        get_mcp_client_manager.cache_clear()
```

### Useful Fixture Patterns

```python
# Temporary project directory
@pytest.fixture
def project_dir() -> Path:
    return Path(__file__).parent.parent.parent

# Hooks directory
@pytest.fixture
def hooks_dir(project_dir: Path) -> Path:
    return project_dir / ".claude" / "hooks"

# Temporary database with cleanup
@pytest.fixture
def temp_db() -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path
```

## pytest Configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
testpaths = ["tests"]
pythonpath = ["src"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

Key settings:
- **asyncio_mode = "auto"**: Auto-detect async tests
- **pythonpath = ["src"]**: Include src/ in import path
- **testpaths = ["tests"]**: Only look in tests/ directory

## Markers

### Skip Conditions

```python
# Skip if agentica not installed
try:
    from agentica import spawn
    HAS_AGENTICA = True
except ImportError:
    HAS_AGENTICA = False

@pytest.mark.skipif(not HAS_AGENTICA, reason="agentica not installed")
async def test_with_agentica():
    ...

# Skip if file doesn't exist (TDD tests)
def test_feature(self, hooks_dir):
    if not (hooks_dir / "feature.sh").exists():
        pytest.skip("Feature not implemented yet")
```

### Custom Markers

```python
# Flaky tests (requires pytest-rerunfailures)
@pytest.mark.flaky(reruns=2)
async def test_timing_sensitive():
    ...
```

## TDD Workflow

Many tests follow TDD (Test-Driven Development):

1. **Write failing tests first** - Tests document expected behavior
2. **Run tests to confirm failure** - `uv run pytest tests/unit/test_new_feature.py -v`
3. **Implement the feature** - Make tests pass
4. **Refactor** - Clean up while keeping tests green

Example TDD test file header:

```python
"""Tests for Feature X (TDD - tests written first).

Tests are designed to FAIL initially until Feature X is implemented.

See plan: thoughts/shared/plans/2025-12-28-feature-x.md
"""
```

## Troubleshooting

### Import Errors

```bash
# Ensure src/ is in path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Or use uv which handles this automatically
uv run pytest tests/unit/test_file.py -v
```

### Async Test Failures

```bash
# Check asyncio mode
uv run pytest --co -q | head -5  # Should show async markers

# Run single async test with verbose output
uv run pytest tests/unit/test_async_file.py::TestClass::test_method -v -s
```

### MCP Config Not Found

```bash
# Integration tests need MCP config
cp mcp_config.json .mcp.json

# Or create minimal config
echo '{"mcpServers": {}}' > .mcp.json
```

### Slow Tests

```bash
# Find slow tests
uv run pytest --durations=10

# Skip slow integration tests during development
uv run pytest tests/unit/ -v
```

## CI/CD Integration

For GitHub Actions or similar:

```yaml
- name: Run tests
  run: |
    uv sync --all-extras
    uv run pytest tests/ -v --tb=short

- name: Run with coverage
  run: |
    uv run pytest --cov=scripts/agentica --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    files: coverage.xml
```

## Related Documentation

- [PATTERNS.md](./PATTERNS.md) - Agentica orchestration patterns
- [HOOKS.md](./HOOKS.md) - Claude Code hooks reference
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [API.md](./API.md) - API reference

# Contributing to Claude Continuity Kit

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:

- Be respectful and considerate in all interactions
- Focus on constructive feedback
- Accept responsibility for mistakes gracefully
- Prioritize the community's best interests

Unacceptable behavior includes harassment, trolling, or personal attacks. Violations may result in removal from the project.

## Reporting Bugs

### Before Submitting

1. Check the [existing issues](https://github.com/your-org/claude-continuity-kit/issues) to avoid duplicates
2. Ensure you're using the latest version
3. Collect relevant information:
   - Python version (`python --version`)
   - OS and version
   - Steps to reproduce
   - Expected vs actual behavior

### Submitting a Bug Report

Open an issue with:

- **Title**: Clear, concise description
- **Environment**: Python version, OS, relevant package versions
- **Steps to Reproduce**: Numbered list of actions
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happened
- **Logs/Errors**: Include full stack traces if available

## Submitting Changes

### PR Workflow

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/claude-continuity-kit.git
   cd claude-continuity-kit
   ```

2. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

3. **Set Up Development Environment**
   ```bash
   # Install uv if you haven't
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Install dependencies
   uv sync --all-extras
   ```

4. **Make Your Changes**
   - Write tests for new functionality
   - Follow the code style guidelines below
   - Keep commits focused and atomic

5. **Run Tests**
   ```bash
   # Run all tests
   uv run pytest

   # Run specific test files
   uv run pytest tests/unit/test_your_feature.py

   # Run with coverage
   uv run pytest --cov=src
   ```

6. **Format and Lint**
   ```bash
   # Format code
   uv run black src tests scripts

   # Lint
   uv run ruff check src tests scripts

   # Type check
   uv run mypy src
   ```

7. **Commit and Push**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   git push origin feature/your-feature-name
   ```

8. **Open a Pull Request**
   - Use a clear, descriptive title
   - Reference any related issues (`Fixes #123`)
   - Describe what changes you made and why
   - Include test plan or verification steps

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation only
- `test:` Adding or updating tests
- `refactor:` Code change that neither fixes a bug nor adds a feature
- `chore:` Maintenance tasks

Examples:
```
feat: add circuit breaker pattern to handler routing
fix: resolve race condition in PostgreSQL pool initialization
docs: update pattern selection guide in PATTERNS.md
test: add E2E tests for hierarchical coordination
```

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Node.js 18+ (for TypeScript hooks)
- PostgreSQL 15+ with pgvector (optional, for memory features)

### Quick Setup

```bash
# Clone the repository
git clone https://github.com/your-org/claude-continuity-kit.git
cd claude-continuity-kit

# Install Python dependencies
uv sync --all-extras

# Install Node dependencies (for hooks)
cd .claude/hooks && npm install && cd ../..

# Build TypeScript hooks
npm run build --prefix .claude/hooks

# Copy environment template
cp .env.example .env
# Edit .env with your API keys
```

### Running Tests

```bash
# All unit tests (fast, ~30 seconds)
uv run pytest tests/unit/

# Pattern-specific tests
uv run pytest tests/unit/test_*_pattern_type.py
uv run pytest tests/unit/test_*_handlers.py

# Integration tests (requires PostgreSQL)
uv run pytest tests/integration/

# Full test suite
uv run pytest
```

### Test Organization

The test suite is organized by pattern and layer:

```
tests/
  unit/
    test_<pattern>_pattern_type.py  # Pattern type definitions
    test_<pattern>_handlers.py      # Handler implementations
  integration/
    test_<pattern>_e2e.py           # End-to-end flows
```

## Code Style Guidelines

### Python

- **Formatter**: Black with 100 character line length
- **Linter**: Ruff for style checks
- **Type Hints**: Required for all public functions
- **Docstrings**: Google style for public APIs

```python
def process_task(
    task_id: str,
    config: TaskConfig,
    *,
    timeout: float = 30.0,
) -> TaskResult:
    """Process a task with the given configuration.

    Args:
        task_id: Unique identifier for the task.
        config: Configuration for task processing.
        timeout: Maximum time to wait in seconds.

    Returns:
        TaskResult containing the processing outcome.

    Raises:
        TaskTimeoutError: If processing exceeds timeout.
    """
    ...
```

### TypeScript (Hooks)

- **Style**: ESLint with TypeScript rules
- **Formatting**: Prettier (2 spaces, no semicolons in output)
- **Async**: Use async/await, handle errors properly

```typescript
interface HookInput {
  session_id: string;
  tool_name: string;
}

async function processHook(input: HookInput): Promise<HookOutput> {
  // Implementation
}
```

### Testing

- Write tests before or alongside implementation (TDD encouraged)
- Test edge cases and error conditions
- Use descriptive test names that explain the scenario
- Mock external services in unit tests

```python
def test_circuit_breaker_opens_after_threshold_failures():
    """Circuit breaker should open after N consecutive failures."""
    breaker = CircuitBreaker(failure_threshold=3)

    for _ in range(3):
        breaker.record_failure()

    assert breaker.is_open
```

## Pattern Development

When adding new multi-agent patterns:

1. **Type Definition**: Add to `scripts/agentica/patterns/types/<pattern>_type.py`
2. **Handler Implementation**: Add to `scripts/agentica/patterns/<pattern>_handlers.py`
3. **Router Integration**: Update `scripts/agentica/unified_scope.py`
4. **Tests**: Add both unit tests and E2E tests
5. **Documentation**: Update `scripts/agentica/PATTERNS.md`

Reference existing patterns (Swarm, Jury, Pipeline) for implementation guidance.

## Questions?

- Open a [Discussion](https://github.com/your-org/claude-continuity-kit/discussions) for questions
- Check the [README](README.md) for usage documentation
- Review [PATTERNS.md](scripts/agentica/PATTERNS.md) for pattern details

Thank you for contributing!

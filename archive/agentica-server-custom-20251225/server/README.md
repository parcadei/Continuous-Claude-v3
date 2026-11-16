# Agentica Server

FastAPI server hosting stateful Agentica agents.

## Features

- REST API for querying agents
- State persistence across queries and server restarts
- Lazy agent creation on first query
- Memory management for large states

## Quick Start

```bash
# Install dependencies
uv pip install -e ".[agentica]"

# Start server
uv run python -m scripts.agentica.server

# Or with uvicorn directly
uvicorn scripts.agentica.server:app --reload --port 8765
```

## API

### Health Check
```bash
curl http://localhost:8765/health
```

### Query Agent
```bash
curl -X POST http://localhost:8765/agent/research/query \
    -H "Content-Type: application/json" \
    -d '{"query": "What is Model Context Protocol?"}'
```

### Available Agents

| Type | Description |
|------|-------------|
| `research` | Queries Perplexity and Nia for research tasks |

## State Persistence

Agent state is persisted to:
```
.claude/cache/agentica-state/{agent_type}.json
```

State includes:
- `findings`: List of key discoveries
- `sources`: Dict of URLs to titles
- `query_history`: List of queries processed
- `timestamp`: Last update time

## Memory Management

When state exceeds 1MB:
1. Warning logged
2. State flushed (keeps last 5 findings, summarizes history)
3. Full state archived (optional)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PERPLEXITY_API_KEY` | Yes* | For Perplexity search |
| `NIA_API_KEY` | Yes* | For Nia documentation search |
| `CLAUDE_PROJECT_DIR` | No | Project root (defaults to cwd) |

*At least one API key required for research agent.

## Adding New Agents

1. Create `scripts/agentica/server/{agent_name}_agent.py`
2. Use `@register_agent("name")` decorator
3. Implement `create_{name}_agent()` async function
4. Define scope functions for agent capabilities

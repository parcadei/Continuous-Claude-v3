# Quick Start Guide

Get up and running with Claude Continuity Kit's multi-agent system in 10 minutes.

## Prerequisites

- **Python 3.11+** (3.13 recommended)
- **uv package manager** - [Install uv](https://docs.astral.sh/uv/)
- **Docker** - For PostgreSQL (or use existing Postgres instance)
- **API Keys** (optional, but recommended):
  - Anthropic API key (for Claude models)
  - Voyage AI (for embeddings)
  - Cohere (for reranking)
  - OpenAI (for alternative models)

## Installation

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/cosimo/claude-continuity-kit.git
cd claude-continuity-kit
uv sync --all-extras
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```bash
# Required for Claude models
ANTHROPIC_API_KEY=sk-ant-...

# Optional: For embeddings (falls back to local models)
VOYAGE_API_KEY=pa-...

# Optional: For reranking
COHERE_API_KEY=...

# Optional: For OpenAI models
OPENAI_API_KEY=sk-...
```

### 3. Set Python Version

```bash
echo "3.13" > .python-version
```

## Running

### Terminal 1: Start PostgreSQL

```bash
./docker/start-postgres.sh
```

This starts PostgreSQL with the schema pre-loaded. Verify it's running:

```bash
docker ps | grep postgres
```

### Terminal 2: Start Agentica Server (Optional)

For MCP integration:

```bash
uv run python scripts/agentica/server.py
```

You should see:
```
MCP Server 'agentica' running on stdio
```

### Terminal 3: Watch Agents (Optional)

See agent tree and memory in real-time:

```bash
uv run python scripts/agentica/watch_agents.py
```

This shows:
- Agent hierarchy tree
- Memory query interface
- Live agent spawning

### Terminal 4: Claude Code

```bash
claude
```

Or use the native Python REPL:

```bash
uv run python scripts/agentica/native_repl/coordinator.py
```

## Your First Multi-Agent Task

### Pattern 1: Swarm Research

In Claude Code or the native REPL:

```
Use swarm pattern to research Python async best practices.
Spawn 3 agents with different perspectives and synthesize findings.
```

**What happens:**
1. Coordinator spawns 3 research agents
2. Each explores different angles (performance, patterns, pitfalls)
3. Synthesizer combines findings into unified report
4. All memory persists in PostgreSQL

**Verify:**
- Watcher shows agent tree with 4 agents (1 coordinator + 3 workers)
- Memory query shows conversation history
- After `/clear`, context reloads from PostgreSQL

### Pattern 2: Hierarchical Implementation

```
Use hierarchical pattern to implement a REST API:
- Coordinator: Plan architecture
- Specialist: Design endpoints
- Worker: Write code
```

**What happens:**
1. Top-level coordinator creates plan
2. Specialist agents handle design decisions
3. Worker agents implement code
4. Results flow up hierarchy

### Pattern 3: Generator/Critic Loop

```
Use generator/critic to write documentation:
- Generator creates initial draft
- Critic reviews and suggests improvements
- Iterate 3 times
```

**What happens:**
1. Generator writes draft
2. Critic provides feedback
3. Generator refines based on critique
4. Loop until criteria met

## Verify It Works

### Check 1: Agent Tree

In the watcher terminal, you should see:

```
Session Tree:
root_12345
├── swarm_coordinator_abc
│   ├── researcher_1_def
│   ├── researcher_2_ghi
│   └── researcher_3_jkl
└── synthesizer_mno
```

### Check 2: Memory Persistence

```python
# In Claude Code
Skill("agent-memory")
# Query: "What did the swarm research?"
```

Or in native REPL:

```python
from scripts.agentica.memory_service_pg import PostgresMemoryService

service = PostgresMemoryService()
await service.initialize()

# Search across all agents
results = await service.semantic_search(
    query="async best practices",
    scope="global",
    limit=5
)

for r in results:
    print(f"{r.agent_id}: {r.content[:100]}")
```

### Check 3: Scope Sharing

```python
# Agent A writes to scope
await agent_a.scope_write("shared_key", {"data": "value"})

# Agent B reads from scope
data = await agent_b.scope_read("shared_key")
assert data == {"data": "value"}
```

## Troubleshooting

### PostgreSQL Connection Issues

```bash
# Check container is running
docker ps

# Check logs
docker logs claude-postgres

# Restart if needed
docker stop claude-postgres
./docker/start-postgres.sh
```

### Python Version Mismatch

```bash
# Check what uv is using
uv run python --version

# Should match .python-version
cat .python-version

# If mismatch, recreate venv
rm -rf .venv
uv venv
uv sync --all-extras
```

### Import Errors

```bash
# Verify agentica is installed
uv pip show agentica

# If missing
uv sync --all-extras

# Test import
uv run python -c "import agentica; print(agentica.__version__)"
```

### Memory Service Not Initialized

```python
# In scripts, always initialize first
from scripts.agentica.memory_service_pg import PostgresMemoryService

service = PostgresMemoryService()
await service.initialize()  # Must call before using
```

### Embedding Service Errors

If you see "Voyage API key not found":

```bash
# Option 1: Add Voyage key to .env
VOYAGE_API_KEY=pa-...

# Option 2: Use local embeddings (slower)
# Edit scripts/agentica/embedding_service.py
# Set LOCAL_FALLBACK = True
```

### Watcher Shows No Agents

```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Check schema is loaded
docker exec claude-postgres psql -U postgres -d agent_continuity -c "\dt"

# Should show: session_tree, agent_memory, scope_data
```

### MCP Server Not Connecting

```bash
# Check server is running
ps aux | grep "scripts/agentica/server.py"

# Verify .mcp.json config
cat .mcp.json

# Test connection
echo '{"method":"tools/list"}' | uv run python scripts/agentica/server.py
```

## Next Steps

1. **Read Pattern Guide**: `docs/guides/PATTERNS.md` - Learn all 12 patterns
2. **Explore Examples**: `scripts/agentica/examples/` - Working implementations
3. **Run Tests**: `uv run pytest tests/unit/test_agentica_*.py`
4. **Check Architecture**: `docs/architecture/` - System design docs
5. **Join Community**: GitHub Discussions for questions

## Common Workflows

### Development Loop

```bash
# Edit pattern implementation
vim scripts/agentica/patterns/swarm.py

# Run tests
uv run pytest tests/unit/test_agentica_swarm.py -v

# Test in REPL
uv run python scripts/agentica/native_repl/coordinator.py
> "use swarm to test my changes"
```

### Debugging Agent Behavior

```bash
# Terminal 1: Watch agents
uv run python scripts/agentica/watch_agents.py

# Terminal 2: Run task
uv run python scripts/agentica/native_repl/coordinator.py

# Terminal 3: Query memory
uv run python -c "
from scripts.agentica.memory_service_pg import PostgresMemoryService
import asyncio

async def debug():
    service = PostgresMemoryService()
    await service.initialize()
    history = await service.get_conversation_history('agent_id')
    for msg in history:
        print(f'{msg.role}: {msg.content[:100]}')

asyncio.run(debug())
"
```

### Inspecting Database

```bash
# Connect to PostgreSQL
docker exec -it claude-postgres psql -U postgres -d agent_continuity

# View session tree
SELECT * FROM session_tree ORDER BY created_at DESC LIMIT 10;

# View memory
SELECT agent_id, role, substring(content, 1, 50)
FROM agent_memory
ORDER BY timestamp DESC LIMIT 20;

# View scope data
SELECT * FROM scope_data;
```

## Performance Tips

1. **Use local embeddings for development** - Faster than API calls
2. **Limit agent depth** - Hierarchies >3 levels get expensive
3. **Reuse agents** - Don't spawn new agents for repeated tasks
4. **Batch memory queries** - Use `get_conversation_history()` vs multiple queries
5. **Clear old sessions** - Run cleanup script periodically

## Support

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: Questions and community help
- **Documentation**: `docs/` directory
- **Examples**: `scripts/agentica/examples/`

---

**You're ready!** Start with a simple swarm pattern and explore from there. The system handles persistence, memory, and coordination automatically.

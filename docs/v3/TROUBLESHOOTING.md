# Troubleshooting

Solutions for common issues when working with Claude Continuity Kit.

---

## Quick Diagnostics

Run these commands to diagnose your environment:

```bash
# Check Python version (should be 3.12+)
uv run python --version

# Check installed packages
uv pip list | grep -E "agentica|aiosqlite|asyncpg|pydantic"

# Test core import
uv run python -c "from scripts.agentica.patterns import Swarm; print('Patterns OK')"

# Check hooks are executable
ls -la .claude/hooks/*.sh

# Check if ledger directory exists
ls -la thoughts/ledgers/

# Check database files
ls -la .claude/cache/*.db .claude/cache/*/*.db 2>/dev/null || echo "No databases found"

# Test MCP runtime
uv run python -m runtime.harness --help
```

---

## Common Issues

### Installation

#### Python version mismatch

**Symptom:** Import errors or `python_version >= 3.12` failures during install.

**Cause:** uv is using an older Python version than expected.

**Solution:**
```bash
# Check what uv is actually using
uv run python --version

# Check pinned version
cat .python-version

# Fix by updating .python-version and recreating venv
echo "3.13" > .python-version
rm -rf .venv && uv venv && uv sync --all-extras
```

---

#### ModuleNotFoundError: No module named 'agentica'

**Symptom:** `ModuleNotFoundError: No module named 'agentica'`

**Cause:** Optional dependencies not installed.

**Solution:**
```bash
uv sync --extra agentica

# Verify
uv run python -c "import agentica; print('OK')"
```

---

#### ModuleNotFoundError: No module named 'aiosqlite'

**Symptom:** SQLite backend fails to initialize.

**Cause:** aiosqlite dependency not installed.

**Solution:**
```bash
uv pip install aiosqlite
```

---

#### ModuleNotFoundError: No module named 'asyncpg'

**Symptom:** PostgreSQL backend fails to initialize.

**Cause:** PostgreSQL dependencies not installed.

**Solution:**
```bash
uv pip install asyncpg pgvector
```

---

#### uv: command not found

**Symptom:** `uv: command not found`

**Cause:** uv package manager not installed.

**Solution:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

### Hooks

#### Hook not firing

**Symptom:** No hook output, no errors, hook appears to do nothing.

**Checklist:**

1. **Check registration in settings.json:**
   ```bash
   cat .claude/settings.json | jq '.hooks'
   ```

2. **Check shell script has execute permission:**
   ```bash
   chmod +x .claude/hooks/*.sh
   ```

3. **Check script path uses correct variable:**
   ```bash
   # Scripts should use $CLAUDE_PROJECT_DIR for project paths
   grep -l "CLAUDE_PROJECT_DIR" .claude/hooks/*.sh
   ```

4. **Check matcher pattern matches tool name:**
   ```bash
   # Matchers are case-sensitive: "Bash" != "bash"
   cat .claude/settings.json | jq '.hooks.PreToolUse[].matcher'
   ```

5. **Test hook manually:**
   ```bash
   echo '{"tool_name":"Bash","tool_input":{"command":"ls"},"session_id":"test"}' | \
     .claude/hooks/pre-tool-use.sh
   ```

---

#### TypeScript changes not applied

**Symptom:** Edited `.ts` file but hook behavior unchanged.

**Cause:** Bundled JavaScript not rebuilt after TypeScript edit.

**Solution:**
```bash
cd .claude/hooks
npx esbuild src/my-hook.ts \
  --bundle --platform=node --format=esm \
  --outfile=dist/my-hook.mjs

# Or rebuild all hooks
./build.sh
```

---

#### Infinite loop in Stop hook

**Symptom:** Hook keeps blocking, Claude never completes.

**Cause:** Not checking `stop_hook_active` flag.

**Solution:** Check the flag before blocking:
```typescript
// In Stop hook
if (input.stop_hook_active) {
  return { result: 'continue' };  // Don't block if already active
}
```

---

#### Ledger not loading after /clear

**Symptom:** Session state not restored after running `/clear`.

**Checklist:**

1. **Check ledger file exists:**
   ```bash
   ls thoughts/ledgers/CONTINUITY_CLAUDE-*.md
   ```

2. **Check SessionStart hook is registered:**
   ```bash
   cat .claude/settings.json | jq '.hooks.SessionStart'
   ```

3. **Check hook matcher includes "clear":**
   ```bash
   # Matcher should be: "resume|compact|clear"
   cat .claude/settings.json | jq '.hooks.SessionStart[].matcher'
   ```

4. **Test SessionStart hook manually:**
   ```bash
   echo '{"hook_event_name":"SessionStart","source":"clear","session_id":"test"}' | \
     .claude/hooks/session-start-continuity.sh
   ```

---

### Patterns

#### Swarm agents not broadcasting

**Symptom:** No cross-agent communication in swarm pattern.

**Checklist:**

1. **Check SWARM_ID env var is set:**
   ```bash
   # In SubagentStart hook, verify pattern type is detected
   PATTERN_TYPE=swarm SWARM_ID=test-swarm \
     echo '{"session_id":"agent-1"}' | .claude/hooks/subagent-start.sh
   ```

2. **Check coordination database exists:**
   ```bash
   ls -la .claude/cache/agentica-coordination/coordination.db
   ```

3. **Query broadcasts table:**
   ```bash
   sqlite3 ".claude/cache/agentica-coordination/coordination.db" \
     "SELECT * FROM broadcasts ORDER BY created_at DESC LIMIT 10;"
   ```

---

#### Jury not reaching consensus

**Symptom:** `ConsensusNotReachedError` in Jury pattern.

**Cause:** Using `UNANIMOUS` or `THRESHOLD` mode and votes don't meet criteria.

**Solution:**
```python
# Use MAJORITY for more lenient consensus
from scripts.agentica.patterns import Jury, ConsensusMode

jury = Jury(
    num_jurors=5,
    consensus_mode=ConsensusMode.MAJORITY  # Instead of UNANIMOUS or THRESHOLD
)
```

Or allow partial votes:
```python
jury = Jury(
    num_jurors=5,
    consensus_mode=ConsensusMode.THRESHOLD,
    threshold=0.6,
    allow_partial=True,
    min_jurors=3  # Continue with at least 3 votes
)
```

---

#### Pipeline stage failure

**Symptom:** Pipeline stops mid-execution.

**Solution:** Check stage function signature and return type:
```python
# Stage functions MUST:
# 1. Be async
# 2. Accept HandoffState
# 3. Return HandoffState

async def my_stage(state: HandoffState) -> HandoffState:
    # Process...
    state.add_artifact("result", result)
    state.update_instruction("Next step description")
    return state  # Don't forget to return!
```

---

### Memory

#### Vector search returning empty results

**Symptom:** `search_vector()` returns no results.

**Checklist:**

1. **Check memories were stored with embeddings:**
   ```python
   # WRONG: No embedding stored
   await memory.store("content")

   # RIGHT: Store with embedding
   embedding = await embedding_service.embed("content")
   await memory.store("content", embedding=embedding)
   ```

2. **Check PostgreSQL has pgvector extension:**
   ```bash
   docker exec claude-postgres psql -U postgres -d agent_continuity \
     -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
   ```

3. **Check archival_memory table has embeddings:**
   ```bash
   docker exec claude-postgres psql -U postgres -d agent_continuity \
     -c "SELECT id, (embedding IS NOT NULL) as has_embedding FROM archival_memory LIMIT 10;"
   ```

---

#### "database is locked" (SQLite)

**Symptom:** SQLite write operations fail with database lock error.

**Cause:** Multiple concurrent writes to SQLite file.

**Solution:** Switch to PostgreSQL for concurrent workloads:
```bash
export AGENTICA_MEMORY_BACKEND=postgres
./docker/start-postgres.sh
```

---

#### Memory service not initialized

**Symptom:** Operations fail with "not connected" or "not initialized" errors.

**Cause:** Forgot to call `connect()` before using memory service.

**Solution:**
```python
# Always initialize before use
from scripts.agentica.memory_service_pg import MemoryServicePG

service = MemoryServicePG()
await service.initialize()  # REQUIRED before any operations

# Or use factory which auto-connects
from scripts.agentica.memory_factory import create_memory_service
memory = await create_memory_service("postgres", session_id="my-session")
```

---

### PostgreSQL

#### Connection refused

**Symptom:** `Connection refused` or `Cannot connect to PostgreSQL`

**Checklist:**

1. **Check container is running:**
   ```bash
   docker ps | grep postgres
   ```

2. **Check container logs:**
   ```bash
   docker logs claude-postgres
   ```

3. **Restart PostgreSQL:**
   ```bash
   docker stop claude-postgres
   ./docker/start-postgres.sh
   ```

4. **Verify connection URL:**
   ```bash
   echo $AGENTICA_POSTGRES_URL
   # Default: postgresql://postgres:agentica_dev@localhost:5432/agent_continuity
   ```

---

#### Schema not loaded

**Symptom:** Table not found errors.

**Checklist:**

1. **Check tables exist:**
   ```bash
   docker exec claude-postgres psql -U postgres -d agent_continuity -c "\dt"
   # Should show: session_tree, agent_memory, scope_data, core_memory, archival_memory
   ```

2. **Reload schema manually:**
   ```bash
   docker exec -i claude-postgres psql -U postgres -d agent_continuity < docker/init.sql
   ```

---

#### pgvector extension missing

**Symptom:** `ERROR: type "vector" does not exist`

**Cause:** pgvector extension not installed in database.

**Solution:**
```bash
docker exec claude-postgres psql -U postgres -d agent_continuity \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

---

### MCP

#### MCP server not configured

**Symptom:** `MCP server not configured` error.

**Checklist:**

1. **Check config file exists:**
   ```bash
   ls -la .mcp.json mcp_config.json
   ```

2. **Regenerate wrappers:**
   ```bash
   uv run mcp-generate
   ```

3. **Check .env has required API keys:**
   ```bash
   cat .env | grep -E "^[A-Z].*_API_KEY"
   ```

---

#### Connection closed

**Symptom:** MCP server connection drops mid-operation.

**Checklist:**

1. **Verify server command:**
   ```bash
   # Check if the command exists
   which npx
   which uv
   ```

2. **Check server logs:**
   ```bash
   # Run server manually to see errors
   npx -y @anthropic/repoprompt-mcp 2>&1
   ```

3. **Check environment variables are set:**
   ```bash
   source .env
   echo $PERPLEXITY_API_KEY  # Should not be empty
   ```

---

#### No config file found

**Symptom:** `No MCP configuration file found`

**Cause:** Neither `.mcp.json` nor `mcp_config.json` exists.

**Solution:**
```bash
# Create from example or generate
cp mcp_config.example.json mcp_config.json

# Or regenerate with available servers
uv run mcp-generate
```

---

### Embedding Service

#### Voyage API key not found

**Symptom:** `Voyage API key not found` or embedding calls fail.

**Solution:**

Option 1 - Add Voyage key:
```bash
# In .env
VOYAGE_API_KEY=pa-...
```

Option 2 - Use OpenAI embeddings:
```python
from scripts.agentica.embedding_service import EmbeddingService

service = EmbeddingService(provider="openai")
# Requires OPENAI_API_KEY in .env
```

Option 3 - Use local embeddings (slower but free):
```python
from scripts.agentica.local_embedding import LocalEmbedding

embedder = LocalEmbedding()
embedding = await embedder.embed("text")
```

---

#### Embedding dimension mismatch

**Symptom:** Vector dimension errors when storing/searching.

**Cause:** Different embedding providers have different dimensions.

**Solution:** The system auto-pads to 4096 dimensions. No action needed.

If you see persistent errors, ensure you're using the same provider for storage and retrieval.

---

### Watcher

#### Watcher shows no agents

**Symptom:** `watch_agents.py` displays empty tree.

**Checklist:**

1. **Check PostgreSQL is running:**
   ```bash
   docker ps | grep postgres
   ```

2. **Check schema is loaded:**
   ```bash
   docker exec claude-postgres psql -U postgres -d agent_continuity -c "\dt"
   ```

3. **Check session_tree table has data:**
   ```bash
   docker exec claude-postgres psql -U postgres -d agent_continuity \
     -c "SELECT * FROM session_tree ORDER BY created_at DESC LIMIT 10;"
   ```

---

## Error Messages Reference

| Error | Cause | Fix |
|-------|-------|-----|
| `MCP server not configured` | Missing `.mcp.json` or `.env` | Copy `.env.example` to `.env`, add API keys |
| `Connection closed` | MCP server crashed | Check server logs, verify command works |
| `No config file found` | Missing `.mcp.json` | Run `uv run mcp-generate` |
| `ModuleNotFoundError: agentica` | Missing optional deps | Run `uv sync --extra agentica` |
| `Python 3.11 detected` | Wrong Python version | Update `.python-version` to 3.13 |
| `database is locked` | SQLite concurrent access | Switch to PostgreSQL for multi-agent |
| `Connection refused` | PostgreSQL not running | Run `./docker/start-postgres.sh` |
| `type "vector" does not exist` | pgvector not installed | Run `CREATE EXTENSION vector;` |
| `ConsensusNotReachedError` | Jury votes don't meet threshold | Use `MAJORITY` mode or lower threshold |
| `stop_hook_active loop` | Missing flag check in Stop hook | Check `stop_hook_active` before blocking |
| `tool_result not found` | Wrong field name in hook | Use `tool_response` not `tool_result` |

---

## Debug Tips

### Enable verbose logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check SQLite database

```bash
# Verify file exists
ls -lh .claude/cache/agentica-memory/memory.db

# Inspect schema
sqlite3 .claude/cache/agentica-memory/memory.db ".schema"

# Count records
sqlite3 .claude/cache/agentica-memory/memory.db \
  "SELECT COUNT(*) FROM archival_memory;"
```

### Check PostgreSQL database

```bash
# Test connection
docker exec claude-postgres psql -U postgres -d agent_continuity \
  -c "SELECT version();"

# List tables
docker exec claude-postgres psql -U postgres -d agent_continuity -c "\dt"

# Inspect session tree
docker exec claude-postgres psql -U postgres -d agent_continuity \
  -c "SELECT * FROM session_tree ORDER BY created_at DESC LIMIT 10;"

# Inspect agent memory
docker exec claude-postgres psql -U postgres -d agent_continuity \
  -c "SELECT agent_id, role, substring(content, 1, 50) FROM agent_memory ORDER BY timestamp DESC LIMIT 20;"
```

### Test hooks manually

```bash
# PreToolUse
echo '{"tool_name":"Bash","tool_input":{"command":"ls"},"session_id":"test"}' | \
  .claude/hooks/pre-tool-use.sh

# PostToolUse
echo '{"tool_name":"Write","tool_input":{"file_path":"test.md"},"tool_response":{"success":true},"session_id":"test"}' | \
  .claude/hooks/post-tool-use.sh

# SessionStart
echo '{"hook_event_name":"SessionStart","source":"resume","session_id":"test"}' | \
  .claude/hooks/session-start-continuity.sh

# Stop
echo '{"hook_event_name":"Stop","stop_hook_active":false,"session_id":"test"}' | \
  .claude/hooks/stop-coordinator.sh
```

### Query coordination database

```bash
# Check broadcasts
sqlite3 ".claude/cache/agentica-coordination/coordination.db" \
  "SELECT * FROM broadcasts WHERE swarm_id = 'my-swarm' ORDER BY created_at;"

# Check agent status
sqlite3 ".claude/cache/agentica-coordination/coordination.db" \
  "SELECT swarm_id, COUNT(DISTINCT sender_agent) as agents, \
          SUM(CASE WHEN broadcast_type='done' THEN 1 ELSE 0 END) as done \
   FROM broadcasts GROUP BY swarm_id;"
```

---

## Getting Help

- **GitHub Issues**: [Report bugs and request features](https://github.com/cosimo/claude-continuity-kit/issues)
- **Documentation**: See `docs/` directory for detailed guides
- **Quick Start**: `docs/QUICKSTART.md`
- **Architecture**: `docs/ARCHITECTURE.md`
- **Patterns**: `docs/PATTERNS.md`
- **Hooks**: `docs/HOOKS.md`

---

**Last Updated**: 2025-12-28

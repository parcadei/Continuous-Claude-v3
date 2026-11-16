# Temporal Memory PostgreSQL Migration Runbook

**Document Version:** 1.0
**Last Updated:** 2025-12-31
**Risk Level:** LOW (reversible, SQLite still works)

---

## 1. Overview

### What This Migration Does

Migrates the temporal memory system from SQLite to PostgreSQL with pgvector support. This enables:

- **Multi-agent concurrent access** - Multiple agents can read/write simultaneously
- **Vector similarity search** - Semantic search via pgvector embeddings
- **Production-grade persistence** - Connection pooling, transactions, ACID compliance
- **Unified schema** - Consolidates two previously separate SQLite implementations

### When to Migrate

| Scenario | Recommended Backend |
|----------|---------------------|
| Single agent, local development | SQLite (default) |
| Multi-agent workflows | PostgreSQL |
| Production deployment | PostgreSQL |
| Semantic/vector search needed | PostgreSQL |
| Quick prototyping | SQLite |

### Target Output

| Artifact | Location |
|----------|----------|
| PostgreSQL tables | `temporal_facts`, `temporal_traces` |
| Backup | `.claude/cache/temporal-memory/temporal.db.bak.<timestamp>` |
| Migration log | Console output with row counts |

---

## 2. Pre-Migration Checklist

Before running the migration, verify all prerequisites:

```bash
# Run from project root
cd /Users/cosimo/Documents/experimental/research/mcp-test/claude-continuity-kit
```

### Required Checks

- [ ] **PostgreSQL container running**:
  ```bash
  # Start Docker container
  cd docker && ./start-postgres.sh

  # Verify running
  docker ps | grep agentica-postgres

  # Expected: container running on port 5433
  ```

- [ ] **Environment variables set**:
  ```bash
  # Check for required env vars
  grep -q "AGENTICA_POSTGRES_URL" .env && echo "OK: AGENTICA_POSTGRES_URL found" || echo "MISSING: Add AGENTICA_POSTGRES_URL"

  # Or verify in environment
  [ -n "$AGENTICA_POSTGRES_URL" ] && echo "OK: URL set" || echo "MISSING: Export AGENTICA_POSTGRES_URL"
  ```

- [ ] **Test database connection**:
  ```bash
  uv run python -c "
  import asyncio
  from scripts.agentica_patterns.postgres_pool import get_connection

  async def test():
      async with get_connection() as conn:
          result = await conn.fetchval('SELECT 1')
          print(f'Connection OK: {result}')

  asyncio.run(test())
  "
  ```

- [ ] **Verify temporal schema exists in PostgreSQL**:
  ```bash
  docker exec -it agentica-postgres psql -U agentica -d agentica_memory \
      -c "\dt temporal*"

  # Expected: temporal_facts and temporal_traces tables
  # If missing, restart container: ./stop-postgres.sh && ./start-postgres.sh
  ```

- [ ] **Backup existing SQLite database** (if it exists):
  ```bash
  TEMPORAL_DB=".claude/cache/temporal-memory/temporal.db"

  [ -f "$TEMPORAL_DB" ] && \
    cp "$TEMPORAL_DB" "${TEMPORAL_DB}.bak.$(date +%Y%m%d-%H%M%S)" && \
    echo "Backup created" || echo "No existing DB to backup"
  ```

- [ ] **Check SQLite row counts** (baseline for verification):
  ```bash
  TEMPORAL_DB=".claude/cache/temporal-memory/temporal.db"

  [ -f "$TEMPORAL_DB" ] && sqlite3 "$TEMPORAL_DB" "
      SELECT 'temporal_facts' as table_name, COUNT(*) as rows FROM temporal_facts
      UNION ALL
      SELECT 'temporal_traces', COUNT(*) FROM temporal_traces
      UNION ALL
      SELECT 'temporal_trace', COUNT(*) FROM temporal_trace;
  " 2>/dev/null || echo "No existing SQLite database"
  ```

---

## 3. Migration Execution Steps

### Step 1: Dry Run Validation

First, validate what will be migrated without writing to PostgreSQL:

```bash
uv run python scripts/migrate_temporal_to_postgres.py \
    .claude/cache/temporal-memory/temporal.db \
    --dry-run
```

Expected output:
```
DRY RUN - No data will be written
Facts to migrate: 1,234
Traces to migrate: 567
Sessions affected: 45
```

### Step 2: Execute Migration

Run the actual migration:

```bash
uv run python scripts/migrate_temporal_to_postgres.py \
    .claude/cache/temporal-memory/temporal.db
```

Expected output:
```
Migration starting...
  Migrating facts: 1,234 rows
  Migrating traces (temporal_traces): 400 rows
  Migrating traces (temporal_trace): 167 rows
Migration complete: {
  'facts_read': 1234,
  'facts_migrated': 1234,
  'facts_skipped': 0,
  'traces_read': 567,
  'traces_migrated': 567
}
```

### Step 3: Verify Row Counts

Confirm data was migrated correctly:

```bash
# PostgreSQL counts
docker exec -it agentica-postgres psql -U agentica -d agentica_memory -c "
    SELECT 'temporal_facts' as table_name, COUNT(*) as rows FROM temporal_facts
    UNION ALL
    SELECT 'temporal_traces', COUNT(*) FROM temporal_traces;
"

# Should match SQLite counts from pre-migration check
```

### Step 4: Switch Backend

Configure the system to use PostgreSQL:

```bash
# Add to .env or export directly
export TEMPORAL_BACKEND=postgres

# Verify setting
echo $TEMPORAL_BACKEND  # Should print: postgres
```

### Step 5: Verify Operations

Test that the PostgreSQL backend works:

```bash
uv run python -c "
import asyncio
from scripts.temporal_memory.factory import create_temporal_store, get_temporal_backend

async def test():
    print(f'Backend: {get_temporal_backend()}')
    store = await create_temporal_store(
        backend='postgres',
        session_id='migration-test'
    )
    await store.record(turn=1, facts={'test': 'migration successful'})
    state = await store.get_current_state()
    print(f'Current state: {state}')
    # Cleanup
    from scripts.agentica_patterns.postgres_pool import get_connection
    async with get_connection() as conn:
        await conn.execute(\"DELETE FROM temporal_facts WHERE session_id = 'migration-test'\")

asyncio.run(test())
"
```

---

## 4. Rollback Procedure

If issues occur, rollback is simple because SQLite remains unchanged.

### Immediate Rollback

Switch back to SQLite (data remains intact):

```bash
# Revert to SQLite backend
export TEMPORAL_BACKEND=sqlite
unset TEMPORAL_BACKEND  # Or remove from .env
```

### Restore from Backup

If SQLite was modified (shouldn't happen during read-only migration):

```bash
# Find most recent backup
ls -lt .claude/cache/temporal-memory/temporal.db.bak.*

# Restore (replace timestamp with actual)
cp .claude/cache/temporal-memory/temporal.db.bak.20250101-120000 \
   .claude/cache/temporal-memory/temporal.db
```

### Clean PostgreSQL Data

If you want to clear migrated data and retry:

```bash
docker exec -it agentica-postgres psql -U agentica -d agentica_memory -c "
    TRUNCATE temporal_facts, temporal_traces CASCADE;
"
```

---

## 5. Troubleshooting Guide

### Connection Errors

**Symptom**: "connection refused" or "could not connect to server"

**Diagnosis**:
```bash
# Check container status
docker ps | grep agentica-postgres

# Check container logs
docker logs agentica-postgres --tail 50

# Verify port
netstat -an | grep 5433
```

**Fix**:
```bash
# Restart container
cd docker && ./stop-postgres.sh && ./start-postgres.sh

# Wait for startup
sleep 5

# Retry
```

### Pool Exhaustion

**Symptom**: "connection pool exhausted" or timeout errors

**Diagnosis**:
```bash
# Check active connections
docker exec -it agentica-postgres psql -U agentica -d agentica_memory -c "
    SELECT count(*) FROM pg_stat_activity WHERE datname = 'agentica_memory';
"
```

**Fix**:
```bash
# Increase pool size
export AGENTICA_MAX_POOL_SIZE=30

# Or reset pool
uv run python -c "
from scripts.agentica_patterns.postgres_pool import reset_pool
reset_pool()
print('Pool reset')
"
```

### Missing Tables

**Symptom**: "relation temporal_facts does not exist"

**Fix**:
```bash
# Recreate schema (init.sql runs on container start)
cd docker && ./stop-postgres.sh && ./start-postgres.sh

# Or manually apply schema
docker exec -it agentica-postgres psql -U agentica -d agentica_memory -f /docker-entrypoint-initdb.d/init.sql
```

### Duplicate Key Errors

**Symptom**: "duplicate key value violates unique constraint"

**Cause**: Running migration twice on same data

**Fix**: Migration is idempotent. Duplicates are skipped via `ON CONFLICT DO NOTHING`. If you see this, the data already exists.

### Timestamp Conversion Errors

**Symptom**: "invalid input syntax for type timestamp"

**Cause**: SQLite has inconsistent timestamp formats (TEXT vs REAL)

**Fix**: The migration script handles both formats. If errors persist:
```bash
# Check problematic rows in SQLite
sqlite3 .claude/cache/temporal-memory/temporal.db "
    SELECT created_at FROM temporal_facts LIMIT 5;
"
```

---

## 6. Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TEMPORAL_BACKEND` | No | `sqlite` | Backend selection: `sqlite` or `postgres` |
| `AGENTICA_POSTGRES_URL` | For postgres | - | PostgreSQL connection URL |
| `AGENTICA_MAX_POOL_SIZE` | No | `20` | Connection pool maximum |
| `AGENTICA_ACQUIRE_TIMEOUT` | No | `30` | Pool acquire timeout (seconds) |
| `CLAUDE_PROJECT_DIR` | No | `.` | Project root for SQLite path resolution |

### Example .env Configuration

```bash
# Temporal Memory Backend
# Options: sqlite (default, development), postgres (production)
TEMPORAL_BACKEND=postgres

# PostgreSQL Connection
AGENTICA_POSTGRES_URL=postgresql://agentica:agentica_dev@localhost:5433/agentica_memory

# Connection Pool Settings (optional)
AGENTICA_MAX_POOL_SIZE=20
AGENTICA_ACQUIRE_TIMEOUT=30
```

---

## 7. CLI Usage Examples

### Migration Script

```bash
# Basic migration
uv run python scripts/migrate_temporal_to_postgres.py temporal.db

# Dry run (no writes)
uv run python scripts/migrate_temporal_to_postgres.py temporal.db --dry-run

# Migrate specific session only
uv run python scripts/migrate_temporal_to_postgres.py temporal.db --session-id abc123

# Custom batch size for large databases
uv run python scripts/migrate_temporal_to_postgres.py temporal.db --batch-size 500
```

### Factory Usage

```python
from scripts.temporal_memory.factory import (
    create_temporal_store,
    create_temporal_writer,
    get_temporal_backend,
)

# Get current backend
backend = get_temporal_backend()  # reads TEMPORAL_BACKEND env

# Create store with explicit backend
store = await create_temporal_store(
    backend="postgres",
    session_id="my-session"
)

# Create writer with explicit backend
writer = await create_temporal_writer(
    backend="postgres"
)
```

### Direct PostgreSQL Queries

```bash
# Check fact counts by session
docker exec -it agentica-postgres psql -U agentica -d agentica_memory -c "
    SELECT session_id, COUNT(*) as facts
    FROM temporal_facts
    GROUP BY session_id
    ORDER BY facts DESC
    LIMIT 10;
"

# Check recent facts
docker exec -it agentica-postgres psql -U agentica -d agentica_memory -c "
    SELECT key, value, confidence, created_at
    FROM temporal_facts
    ORDER BY created_at DESC
    LIMIT 10;
"

# Check trace distribution
docker exec -it agentica-postgres psql -U agentica -d agentica_memory -c "
    SELECT session_id, MAX(turn) as max_turn, COUNT(*) as traces
    FROM temporal_traces
    GROUP BY session_id
    ORDER BY max_turn DESC
    LIMIT 10;
"
```

---

## 8. Post-Migration Verification Checklist

After migration, verify the system is working correctly:

- [ ] **Row counts match**: PostgreSQL counts equal SQLite counts
- [ ] **Factory selects correct backend**: `get_temporal_backend()` returns `postgres`
- [ ] **Store operations work**: `record()`, `get_current_state()`, `get_trace()`
- [ ] **Writer operations work**: `write_facts()`, `write_traces()`
- [ ] **Concurrent access works**: Multiple agents can access simultaneously
- [ ] **Vector search works** (if embeddings present): `search_similar()`

### Automated Verification

```bash
# Run PostgreSQL-specific tests
TEMPORAL_BACKEND=postgres uv run pytest \
    tests/unit/test_temporal_store_pg.py \
    tests/unit/test_backfill_temporal_writer_pg.py \
    tests/unit/test_temporal_factory.py \
    -v --tb=short
```

---

## 9. Pipeline Components Reference

| Component | File | Purpose |
|-----------|------|---------|
| Migration CLI | `scripts/migrate_temporal_to_postgres.py` | SQLite to PostgreSQL migration |
| Factory | `scripts/temporal_memory/factory.py` | Backend-agnostic store creation |
| Protocol | `scripts/temporal_memory/protocol.py` | Interface definitions |
| Store (SQLite) | `scripts/temporal_memory/store.py` | SQLite implementation |
| Store (PG) | `scripts/temporal_memory/store_pg.py` | PostgreSQL implementation |
| Writer (SQLite) | `scripts/backfill/temporal_writer.py` | SQLite backfill writer |
| Writer (PG) | `scripts/backfill/temporal_writer_pg.py` | PostgreSQL backfill writer |
| Pool | `scripts/agentica_patterns/postgres_pool.py` | Connection pool utilities |
| Schema | `docker/init.sql` | PostgreSQL DDL |

---

## 10. Quick Reference

| Action | Command |
|--------|---------|
| Start PostgreSQL | `cd docker && ./start-postgres.sh` |
| Stop PostgreSQL | `cd docker && ./stop-postgres.sh` |
| Dry run migration | `uv run python scripts/migrate_temporal_to_postgres.py db.sqlite --dry-run` |
| Run migration | `uv run python scripts/migrate_temporal_to_postgres.py db.sqlite` |
| Switch to PostgreSQL | `export TEMPORAL_BACKEND=postgres` |
| Switch to SQLite | `unset TEMPORAL_BACKEND` |
| Check table counts | `docker exec -it agentica-postgres psql -U agentica -d agentica_memory -c "SELECT COUNT(*) FROM temporal_facts"` |
| Run PG tests | `TEMPORAL_BACKEND=postgres uv run pytest tests/unit/test_temporal_store_pg.py -v` |

---

**Version Information:**
- **Document Version:** 1.0
- **Related Plan:** `thoughts/shared/handoffs/temporal-postgres/plan.md`
- **Implementation Phases:** 3.1-3.6
- **Last Updated:** 2025-12-31

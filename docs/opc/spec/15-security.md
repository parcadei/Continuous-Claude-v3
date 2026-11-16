# Module: Security Model

## Overview

Security model for headless agents: process isolation, database access controls, secret handling, and sandbox restrictions.

---

## Threat Model

| Threat | Mitigation |
|--------|------------|
| Runaway agents consuming resources | Depth limit (max 3), resource checks |
| Agent accessing sensitive files | Sandbox isolation, read-only mounts |
| Agent leaking secrets | No env var pass-through, vault for secrets |
| Agent corrupting shared state | Row-level locking, append-only patterns |
| Malicious code in sandbox | Docker isolation, no network, resource limits |

---

## Process Isolation

### Agent Spawning Restrictions

```python
def spawn_agent(prompt: str, **kwargs) -> SpawnedAgent:
    """Spawn agent with security restrictions."""

    # 1. Depth limit check
    depth = int(os.environ.get("DEPTH_LEVEL", "0"))
    if depth >= 3:
        raise SecurityError("Depth limit exceeded")

    # 2. Resource check
    if not check_resources_available():
        raise SecurityError("Insufficient resources")

    # 3. Filter environment variables
    safe_env = filter_safe_env_vars(os.environ)

    # 4. Spawn with restrictions
    proc = subprocess.Popen(
        ["claude", "-p", prompt],
        env=safe_env,
        # Don't inherit file descriptors
        close_fds=True,
    )

    return SpawnedAgent(pid=proc.pid, ...)

def filter_safe_env_vars(env: dict) -> dict:
    """Filter environment to safe variables only."""

    ALLOWED_VARS = {
        # Core
        'HOME', 'USER', 'PATH', 'SHELL',
        # Claude
        'CLAUDE_PROJECT_DIR', 'DEPTH_LEVEL', 'AGENT_ID',
        'PARENT_AGENT_ID', 'SESSION_ID', 'PATTERN_TYPE',
        # Database (use vault instead of direct secrets)
        'DATABASE_URL_VAULT_KEY',
    }

    return {k: v for k, v in env.items() if k in ALLOWED_VARS}
```

---

## Database Access Controls

### Connection Pooling with Limits

```python
async def create_agent_pool() -> asyncpg.Pool:
    """Create database pool with agent-specific limits."""

    return await asyncpg.create_pool(
        get_database_url(),
        min_size=1,
        max_size=5,  # Limit concurrent connections per agent
        command_timeout=30,  # Prevent long-running queries
        statement_cache_size=0,  # Disable statement cache for security
    )
```

### Row-Level Security (PostgreSQL)

```sql
-- Enable RLS
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;

-- Agents can only see/modify their own rows
CREATE POLICY agent_isolation ON agents
    FOR ALL
    USING (agent_id = current_setting('app.current_agent_id')::text)
    WITH CHECK (agent_id = current_setting('app.current_agent_id')::text);

-- Exception: orchestrator can see all
CREATE POLICY orchestrator_access ON agents
    FOR SELECT
    USING (current_setting('app.is_orchestrator', true)::boolean = true);
```

### Setting Agent Context

```python
async def set_agent_context(conn: asyncpg.Connection, agent_id: str):
    """Set agent context for RLS."""

    await conn.execute("SET app.current_agent_id = $1", agent_id)
    await conn.execute("SET app.is_orchestrator = false")
```

---

## Secret Handling

### Vault Pattern

Never pass secrets via environment variables. Use a vault:

```python
# scripts/secret_vault.py
import keyring

class SecretVault:
    """Secure secret storage."""

    SERVICE_NAME = "claude-continuity-kit"

    @classmethod
    def get(cls, key: str) -> str | None:
        """Get a secret from the vault."""
        return keyring.get_password(cls.SERVICE_NAME, key)

    @classmethod
    def set(cls, key: str, value: str) -> None:
        """Store a secret in the vault."""
        keyring.set_password(cls.SERVICE_NAME, key, value)

# Usage in agent
database_url = SecretVault.get("DATABASE_URL")
```

### Setup Wizard Secret Storage

```python
async def store_secrets():
    """Store secrets during setup."""

    postgres_password = Prompt.ask("PostgreSQL password", password=True)
    SecretVault.set("POSTGRES_PASSWORD", postgres_password)

    perplexity_key = Prompt.ask("Perplexity API key (optional)", password=True)
    if perplexity_key:
        SecretVault.set("PERPLEXITY_API_KEY", perplexity_key)
```

---

## Sandbox Security

### Docker Restrictions

```yaml
# docker-compose.yml
sandbox:
  security_opt:
    - no-new-privileges:true
  cap_drop:
    - ALL
  read_only: true
  tmpfs:
    - /tmp:size=100m,noexec
  network_mode: "none"  # No network access
  mem_limit: 512m
  cpus: 0.5
  pids_limit: 100
```

### Code Restrictions

```python
# Restricted builtins in sandbox
FORBIDDEN_BUILTINS = {
    'open', 'exec', 'eval', 'compile',
    '__import__', 'input', 'breakpoint',
    'memoryview', 'globals', 'locals',
}

ALLOWED_MODULES = {
    'numpy', 'scipy', 'sympy', 'pandas',
    'math', 'statistics', 'itertools',
    'functools', 'collections', 'json',
}
```

---

## Agent Sandboxing

### Allowed Tools per Pattern

```python
PATTERN_ALLOWED_TOOLS = {
    'swarm': ['Read', 'Grep', 'Glob', 'WebSearch'],
    'jury': ['Read'],  # Jurors can only read, not modify
    'sentinel': ['Read', 'Grep', 'Bash'],  # Bash for blackboard CLI
    'pipeline': ['Read', 'Write', 'Edit', 'Bash'],  # Full access for implementation
}

def get_allowed_tools(pattern: str) -> list[str]:
    """Get allowed tools for pattern."""
    return PATTERN_ALLOWED_TOOLS.get(pattern, ['Read', 'Grep', 'Glob'])
```

### Hook-Based Enforcement

```typescript
// .claude/hooks/src/tool-restriction.ts
const input = JSON.parse(await readStdin());

const pattern = process.env.PATTERN_TYPE;
const allowedTools = PATTERN_ALLOWED_TOOLS[pattern] || DEFAULT_TOOLS;

if (!allowedTools.includes(input.tool_name)) {
    console.log(JSON.stringify({
        result: 'block',
        reason: `Tool ${input.tool_name} not allowed for ${pattern} pattern`
    }));
}
```

---

## Audit Logging

### Security Events

```python
async def log_security_event(
    event_type: str,
    agent_id: str,
    details: dict,
):
    """Log security-relevant events."""

    await pool.execute("""
        INSERT INTO security_log (event_type, agent_id, details, timestamp)
        VALUES ($1, $2, $3, NOW())
    """, event_type, agent_id, json.dumps(details))

# Log spawn attempts
await log_security_event("agent_spawn", agent_id, {
    "depth": depth_level,
    "pattern": pattern,
    "allowed_tools": allowed_tools,
})

# Log blocked actions
await log_security_event("tool_blocked", agent_id, {
    "tool": tool_name,
    "reason": "Not in allowed list",
})
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/secret_vault.py` | Secure secret storage |
| `scripts/security_audit.py` | Audit logging |
| `.claude/hooks/src/tool-restriction.ts` | Tool enforcement hook |

## Schema Additions

```sql
CREATE TABLE security_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    agent_id TEXT,
    details JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_security_log_type ON security_log(event_type, timestamp);
CREATE INDEX idx_security_log_agent ON security_log(agent_id, timestamp);
```

---

## Append-Only Audit Log

Security log table enforced as append-only:

```sql
-- Trigger to prevent DELETE/UPDATE on security_log
CREATE OR REPLACE FUNCTION prevent_security_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'security_log is append-only: % not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER security_log_no_delete
    BEFORE DELETE ON security_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_security_log_modification();

CREATE TRIGGER security_log_no_update
    BEFORE UPDATE ON security_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_security_log_modification();
```

Only way to remove old logs is via a separate admin connection with TRUNCATE (requires superuser).

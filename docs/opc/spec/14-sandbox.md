# Module: Shared Sandbox

## Overview

Docker-based isolated code execution with shared state via Redis (hot cache) and PostgreSQL (durable storage). Agents can execute code once and share results.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Agent 1                                        │
│  sandbox.execute("result = heavy_computation()")                           │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Sandbox Runner (Docker)                             │
│  ┌─────────────────────┐                                                   │
│  │  Isolated Container │  - No network access                              │
│  │  - Limited CPU/RAM  │  - Read-only filesystem (except /tmp)             │
│  │  - No root          │  - Timeout enforcement                            │
│  └─────────────────────┘                                                   │
│           │                                                                 │
│           ▼                                                                 │
│  Execute code, return result                                                │
└────────────────────────────────────┬────────────────────────────────────────┘
                                     │
            ┌────────────────────────┼────────────────────────────────────────┐
            │                        │                                        │
            ▼                        ▼                                        │
┌─────────────────────┐  ┌─────────────────────┐                             │
│       Redis         │  │     PostgreSQL      │                             │
│    (hot cache)      │  │   (durable store)   │                             │
│                     │  │                     │                             │
│  TTL: 1 hour        │  │  Permanent record   │                             │
│  Fast reads         │  │  Queryable          │                             │
└─────────────────────┘  └─────────────────────┘                             │
            │                        │                                        │
            └────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Agent 2                                        │
│  result = sandbox.get("result")  # No re-execution needed                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Docker Sandbox

### Dockerfile

```dockerfile
# docker/Dockerfile.sandbox
FROM python:3.12-slim

# Security: non-root user
RUN useradd -m -s /bin/bash sandbox
USER sandbox
WORKDIR /home/sandbox

# Install common libraries
RUN pip install --user numpy scipy sympy pandas

# No network access (configured in docker-compose)
# Read-only filesystem (except /tmp)
# Resource limits (in docker-compose)

COPY --chown=sandbox:sandbox sandbox_runner.py /home/sandbox/
ENTRYPOINT ["python", "sandbox_runner.py"]
```

### Sandbox Runner

```python
# docker/sandbox_runner.py
import json
import sys
import resource
import signal

# Set resource limits
resource.setrlimit(resource.RLIMIT_CPU, (30, 30))  # 30 seconds CPU
resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))  # 512MB RAM

def timeout_handler(signum, frame):
    raise TimeoutError("Execution timed out")

signal.signal(signal.SIGALRM, timeout_handler)

def execute_code(code: str, timeout: int = 30) -> dict:
    """Execute code in sandbox."""

    signal.alarm(timeout)

    try:
        # Create restricted globals
        restricted_globals = {
            '__builtins__': {
                'print': print,
                'len': len,
                'range': range,
                'sum': sum,
                'min': min,
                'max': max,
                'sorted': sorted,
                'list': list,
                'dict': dict,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
                # Math
                'abs': abs,
                'round': round,
                'pow': pow,
            },
        }

        # Import allowed modules
        import numpy as np
        import sympy as sp
        restricted_globals['np'] = np
        restricted_globals['numpy'] = np
        restricted_globals['sp'] = sp
        restricted_globals['sympy'] = sp

        local_vars = {}
        exec(code, restricted_globals, local_vars)

        signal.alarm(0)

        # Extract result
        result = local_vars.get('result', None)

        return {
            'success': True,
            'result': serialize_result(result),
            'variables': {k: serialize_result(v) for k, v in local_vars.items() if not k.startswith('_')},
        }

    except Exception as e:
        signal.alarm(0)
        return {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
        }

def serialize_result(obj):
    """Serialize result to JSON-compatible format."""
    if hasattr(obj, 'tolist'):  # numpy array
        return obj.tolist()
    if hasattr(obj, '__dict__'):
        return str(obj)
    return obj

if __name__ == '__main__':
    request = json.load(sys.stdin)
    result = execute_code(request['code'], request.get('timeout', 30))
    json.dump(result, sys.stdout)
```

---

## Sandbox Client

### Python API

```python
# scripts/sandbox_client.py
import docker
import json
import hashlib
import asyncpg
import redis.asyncio as redis

class SandboxClient:
    """Client for shared sandbox execution."""

    def __init__(self, pool: asyncpg.Pool, redis_client: redis.Redis):
        self.pool = pool
        self.redis = redis_client
        self.docker = docker.from_env()
        self.container_name = "claude-sandbox"

    async def execute(
        self,
        code: str,
        key: str | None = None,
        cache_ttl: int = 3600,
    ) -> dict:
        """Execute code in sandbox, caching result."""

        # Generate cache key
        if key is None:
            key = hashlib.sha256(code.encode()).hexdigest()[:16]

        session_id = os.environ.get("SESSION_ID", "default")
        cache_key = f"sandbox:{session_id}:{key}"

        # Check Redis cache first
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # Check PostgreSQL for durable results
        row = await self.pool.fetchrow("""
            SELECT value FROM sandbox_computations
            WHERE session_id = $1 AND key = $2
        """, session_id, key)

        if row:
            result = json.loads(row['value'])
            # Warm Redis cache
            await self.redis.setex(cache_key, cache_ttl, row['value'])
            return result

        # Execute in Docker sandbox
        result = await self._docker_execute(code)

        if result['success']:
            # Store in PostgreSQL (durable)
            await self.pool.execute("""
                INSERT INTO sandbox_computations (session_id, key, value, computed_by)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (session_id, key) DO UPDATE SET value = $3
            """, session_id, key, json.dumps(result), os.environ.get("AGENT_ID", "unknown"))

            # Store in Redis (fast)
            await self.redis.setex(cache_key, cache_ttl, json.dumps(result))

        return result

    async def get(self, key: str) -> dict | None:
        """Get a previously computed result."""

        session_id = os.environ.get("SESSION_ID", "default")
        cache_key = f"sandbox:{session_id}:{key}"

        # Check Redis first
        cached = await self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # Check PostgreSQL
        row = await self.pool.fetchrow("""
            SELECT value FROM sandbox_computations
            WHERE session_id = $1 AND key = $2
        """, session_id, key)

        if row:
            return json.loads(row['value'])

        return None

    async def _docker_execute(self, code: str) -> dict:
        """Execute code in Docker container."""

        try:
            result = self.docker.containers.run(
                self.container_name,
                stdin_open=True,
                remove=True,
                network_disabled=True,
                mem_limit='512m',
                cpu_period=100000,
                cpu_quota=50000,  # 50% CPU
                read_only=True,
                tmpfs={'/tmp': 'size=100m'},
                input=json.dumps({'code': code}).encode(),
            )
            return json.loads(result)
        except Exception as e:
            return {'success': False, 'error': str(e), 'error_type': 'DockerError'}
```

---

## Agent Usage

```python
# In an agent's code
sandbox = get_sandbox_client()

# Execute expensive computation once
result = await sandbox.execute("""
import numpy as np
data = np.random.randn(10000, 100)
result = np.linalg.svd(data, full_matrices=False)
""", key="svd_analysis")

# Later, another agent can retrieve it
cached = await sandbox.get("svd_analysis")
# No re-execution needed
```

---

## gVisor Runtime

Use gVisor (runsc) for syscall-level isolation:

```yaml
# docker-compose.yml
sandbox:
  runtime: runsc  # gVisor runtime
  security_opt:
    - no-new-privileges:true
  cap_drop:
    - ALL
  read_only: true
  network_mode: "none"
```

Install gVisor on host:
```bash
# Install runsc
curl -fsSL https://gvisor.dev/archive.key | sudo gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main" | sudo tee /etc/apt/sources.list.d/gvisor.list
sudo apt-get update && sudo apt-get install -y runsc

# Configure Docker to use gVisor
sudo runsc install
sudo systemctl restart docker
```

## Invalid JSON Recovery

Retry with stricter prompt on invalid JSON:

```python
async def execute_with_json_recovery(prompt: str) -> dict:
    """Execute agent, retry with stricter prompt if JSON invalid."""

    # First attempt
    result = await run_claude_p(prompt)

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        pass

    # Retry with stricter system prompt
    strict_prompt = f"""
{prompt}

CRITICAL: Return ONLY valid JSON. No prose, no markdown, no explanation.
Example format: {{"result": "...", "status": "success"}}
"""
    result = await run_claude_p(strict_prompt, append_system="Return ONLY valid JSON.")

    try:
        return json.loads(result)
    except json.JSONDecodeError:
        raise InvalidAgentOutputError(f"Agent returned invalid JSON after retry: {result[:200]}")
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `docker/Dockerfile.sandbox` | Sandbox container |
| `docker/sandbox_runner.py` | In-container execution |
| `scripts/sandbox_client.py` | Python client |

## Schema Additions

See `06-concurrency-coordination.md` for `sandbox_computations` table.

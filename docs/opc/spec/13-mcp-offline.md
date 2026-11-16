# Module: MCP & Offline Mode

## Overview

Headless agents inherit MCP configuration via skill-rules.json code execution pattern. Graceful degradation when services are unavailable. Full offline mode with SQLite + local LLM.

---

## MCP Inheritance

### Code Execution Pattern

Agents don't call MCP tools directly. Instead, they use scripts that wrap MCP:

```json
// skill-rules.json
{
  "research-agent": {
    "type": "agent",
    "mcpPattern": "code-execution",
    "scripts": [
      "scripts/perplexity_search.py",
      "scripts/firecrawl_scrape.py"
    ]
  }
}
```

### Why Code Execution?

| Direct MCP | Code Execution |
|------------|----------------|
| 15-30 tool schemas in context | 0 schemas (just script names) |
| ~5000 tokens overhead | ~100 tokens overhead |
| Requires MCP server connection | Scripts are standalone |

### Agent Script Usage

```python
# In headless agent
# Instead of: mcp.call("perplexity__search", query=...)
# Use: Bash("uv run python scripts/perplexity_search.py --query '...'")
```

---

## Graceful Degradation

### Service Availability Checks

```python
# scripts/service_checks.py

async def check_service(service: str) -> tuple[bool, str]:
    """Check if a service is available."""

    checks = {
        'lmstudio': check_lmstudio,
        'postgres': check_postgres,
        'redis': check_redis,
        'perplexity': check_perplexity_api,
        'voyage': check_voyage_api,
    }

    checker = checks.get(service)
    if not checker:
        return True, "Unknown service"

    return await checker()

async def check_lmstudio() -> tuple[bool, str]:
    """Check LMStudio availability."""

    url = os.environ.get("LMSTUDIO_URL", "http://localhost:1234")

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{url}/v1/models")
            if response.status_code == 200:
                return True, "Connected"
            return False, f"HTTP {response.status_code}"
    except Exception as e:
        return False, str(e)
```

### Fallback Messages

```python
# From hook-developer pattern
FALLBACK_MESSAGES = {
    'lmstudio': """
LMStudio not available at {url}.

To enable Godel-Prover tactic suggestions:
1. Install LMStudio from https://lmstudio.ai/
2. Load "Goedel-Prover-V2-8B" model
3. Start the local server on port 1234

Continuing without AI-assisted tactics...
""",
    'postgres': """
PostgreSQL not available at {url}.

Falling back to SQLite for coordination.
Some features may be limited:
- Parallel agent writes may conflict
- No pgvector semantic search

To enable PostgreSQL:
1. docker compose up -d postgres
2. Set DATABASE_URL environment variable
""",
}
```

---

## Offline Mode

### Capability Matrix

| Feature | Online | Offline |
|---------|--------|---------|
| Agent coordination | PostgreSQL | SQLite |
| Embeddings | Voyage/OpenAI API | sentence-transformers local |
| Search | Perplexity API | Local grep/ripgrep |
| Theorem proving | Godel-Prover + LMStudio | LMStudio only |
| Sandbox | Docker container | Subprocess (less isolated) |

### Offline Detection

```python
async def detect_offline_mode() -> bool:
    """Detect if we're offline."""

    # Check internet connectivity
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.get("https://api.anthropic.com/health")
            return False  # Online
    except:
        return True  # Offline

async def configure_for_offline():
    """Configure services for offline mode."""

    config = load_config()

    # Switch to SQLite
    config['database'] = {
        'backend': 'sqlite',
        'path': '.claude/cache/coordination.db',
    }

    # Switch to local embeddings
    config['embeddings'] = {
        'provider': 'local',
        'model': 'all-MiniLM-L6-v2',
    }

    # Disable external search
    config['search'] = {
        'enabled': False,
        'fallback': 'local_grep',
    }

    save_config(config)
    logger.info("Configured for offline mode")
```

### Local Embeddings

```python
# scripts/local_embeddings.py

from sentence_transformers import SentenceTransformer

class LocalEmbeddingProvider:
    """Local embedding provider using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings locally."""
        embeddings = self.model.encode(texts)
        return embeddings.tolist()

    @property
    def dimensions(self) -> int:
        return self.model.get_sentence_embedding_dimension()
```

---

## MCP Server Configuration

### .mcp.json Structure

```json
{
  "mcpServers": {
    "perplexity": {
      "type": "stdio",
      "command": "uvx",
      "args": ["mcp-server-perplexity"],
      "env": {
        "PERPLEXITY_API_KEY": "${PERPLEXITY_API_KEY}"
      }
    },
    "firecrawl": {
      "type": "http",
      "url": "https://api.firecrawl.dev/v1",
      "headers": {
        "Authorization": "Bearer ${FIRECRAWL_API_KEY}"
      }
    }
  }
}
```

### Agent Environment

Agents inherit `.mcp.json` but don't load MCP servers directly:

```bash
# Environment passed to agent
CLAUDE_PROJECT_DIR=/path/to/project  # .mcp.json lives here
MCP_CONFIG_PATH=$CLAUDE_PROJECT_DIR/.mcp.json
```

Scripts read `.mcp.json` to get credentials, then make API calls directly.

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/service_checks.py` | Service availability checks |
| `scripts/local_embeddings.py` | Offline embedding provider |
| `scripts/offline_search.py` | Local search fallback |

## Files to Modify

| File | Changes |
|------|---------|
| `scripts/agentica_patterns/memory_factory.py` | Add offline mode |
| `scripts/agentica_patterns/embedding_service.py` | Add local provider |

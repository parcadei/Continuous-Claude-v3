# Agentica Integration

Agentica is the orchestration layer used for multi-agent workflows without inflating Claude’s context window.

## Execution diagram

```
Claude Code (main)
  → Agentica agent
     → tool calls (Read/Write/Bash)
     → state persists in Python runtime
```

## Proxy / server topology

```
Agentica Server
  │  INFERENCE_ENDPOINT_URL
  ▼
Claude Proxy (FastAPI)
  │  subprocess
  ▼
Claude CLI / API
```

Request flow (concrete):

```
Agentica agent
  → POST /v1/chat/completions (proxy)
     → claude_proxy.py
        → Claude CLI subprocess
           → stdout streamed back
```

## Key lessons (from integration journey)

- Claude Code is the interface layer; Agentica is the runtime/state layer.
- Proxy approach avoids extra LLM costs by routing through Claude CLI.
- Agentica server sessions are ephemeral; persistence must be external.
- Use file-based handoffs to keep the main context clean.
- Keep watcher running during multi-agent runs to debug agent output quickly.
- "Hydration is impossible" in long sessions: replaying full context is too costly; persist state externally instead.

## What worked

- Using the Claude proxy for $0 LLM cost.
- Task-based orchestration (research → plan → validate → implement → review).
- File-based handoffs to keep main context clean.
- Explicit agent prompts with injected specs avoid divergence.

## Key files

- Proxy: `scripts/agentica_patterns/claude_proxy.py`
- Agentica server: `workspace/agentica-research/agentica-server`
- Watcher: `scripts/agentica_patterns/watch_agents.py`

## Startup commands

```bash
# Terminal 1: Claude proxy
uv run python scripts/agentica_patterns/claude_proxy.py --port 8080

# Terminal 2: Agentica server
cd workspace/agentica-research/agentica-server
INFERENCE_ENDPOINT_URL=http://localhost:8080/v1/chat/completions uv run agentica-server --port 2345

# Terminal 3 (optional): watcher
uv run python scripts/agentica_patterns/watch_agents.py --watch --logs
```

## Reference docs

- `docs/AGENTICA_INTEGRATION_JOURNEY.md`
- `docs/agentica-architecture/FULL_STACK.md`
- `docs/agentica-architecture/SCOPE_AND_MEMORY.md`

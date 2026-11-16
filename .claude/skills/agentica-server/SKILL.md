---
name: agentica-server
description: Agentica server + Claude proxy setup - architecture, startup sequence, debugging
allowed-tools: [Bash, Read]
---

# Agentica Server + Claude Proxy Setup

Complete reference for running Agentica SDK with a local Claude proxy. This enables Python agents to use Claude CLI as their inference backend.

## When to Use

Use this skill when:
- Starting Agentica development with Claude proxy
- Debugging connection issues between SDK, server, and proxy
- Setting up a fresh Agentica environment
- Troubleshooting agent tool access or hallucination issues

## Architecture

```
Agentica SDK (client code)
    | S_M_BASE_URL=http://localhost:2345
    v
ClientSessionManager
    |
    v
Agentica Server (agentica-server)
    | INFERENCE_ENDPOINT_URL=http://localhost:8080/v1/chat/completions
    v
Claude Proxy (claude_proxy.py)
    |
    v
Claude CLI (claude -p)
```

## Environment Variables

| Variable | Set By | Used By | Purpose |
|----------|--------|---------|---------|
| `INFERENCE_ENDPOINT_URL` | Human | agentica-server | Where server sends LLM inference requests |
| `S_M_BASE_URL` | Human | Agentica SDK client | Where SDK connects to session manager |

**KEY:** These are NOT the same endpoint!
- SDK connects to server (port 2345)
- Server connects to proxy (port 8080)

## Startup Sequence

Must start in this order (each in a separate terminal):

### Terminal 1: Claude Proxy

```bash
uv run python scripts/agentica/claude_proxy.py --port 8080
```

### Terminal 2: Agentica Server

**MUST run from its directory:**

```bash
cd workspace/agentica-research/agentica-server
INFERENCE_ENDPOINT_URL=http://localhost:8080/v1/chat/completions uv run agentica-server --port 2345
```

### Terminal 3: Your Agent Script

```bash
S_M_BASE_URL=http://localhost:2345 uv run python scripts/agentica/your_script.py
```

## Health Checks

```bash
# Claude proxy health
curl http://localhost:8080/health

# Agentica server health
curl http://localhost:2345/health
```

## Common Errors & Fixes

### 1. APIConnectionError after agent spawn

**Symptom:** Agent spawns successfully but fails on first call with connection error.

**Cause:** Claude proxy returning plain JSON instead of SSE format.

**Fix:** Proxy must return Server-Sent Events format:
```
data: {"choices": [...]}\n\n
```

### 2. ModuleNotFoundError for agentica-server

**Symptom:** `ModuleNotFoundError: No module named 'agentica_server'`

**Cause:** Running `uv run agentica-server` from wrong directory.

**Fix:** Must `cd workspace/agentica-research/agentica-server` first.

### 3. Agent can't use Read/Write/Edit tools

**Symptom:** Agent asks for file contents instead of reading them.

**Cause:** Missing `--allowedTools` in claude_proxy.py CLI call.

**Fix:** Proxy must pass tool permissions:
```bash
claude -p ... --allowedTools Read Write Edit Bash
```

### 4. Agent claims success but didn't do task

**Symptom:** Agent says "I've created the file" but file doesn't exist.

**Cause:** Hallucination - agent describing intended actions without executing.

**Fix:** Added emphatic anti-hallucination prompt in REPL_BASELINE:
```
CRITICAL: Use ACTUAL tools. Never DESCRIBE using tools.
```

### 5. Timeout on agent.call()

**Symptom:** Call hangs for 30+ seconds then times out.

**Cause:** Claude CLI taking too long or stuck in a loop.

**Fix:** Check proxy logs for the actual CLI output. May need to simplify prompt.

## Key Files

| File | Purpose |
|------|---------|
| `scripts/agentica/claude_proxy.py` | OpenAI-compatible proxy with SSE streaming |
| `workspace/agentica-research/agentica-server/` | Local agentica-server installation |
| `scripts/agentica/PATTERNS.md` | Multi-agent pattern documentation |

## Quick Verification

Test the full stack:

```bash
# 1. Verify proxy responds
curl http://localhost:8080/health

# 2. Verify server responds
curl http://localhost:2345/health

# 3. Test inference through proxy
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"claude","messages":[{"role":"user","content":"Say hello"}]}'
```

## Checklist

Before running agents:
- [ ] Claude proxy running on port 8080
- [ ] Agentica server running on port 2345 (from its directory)
- [ ] `S_M_BASE_URL` set for client scripts
- [ ] `INFERENCE_ENDPOINT_URL` set for server
- [ ] Both health checks return 200

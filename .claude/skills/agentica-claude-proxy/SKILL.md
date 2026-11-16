---
name: agentica-claude-proxy
description: Guide for integrating Agentica SDK with Claude Code CLI proxy
allowed-tools: [Read, Bash]
---

# Agentica-Claude Code Proxy Integration

Use this skill when developing or debugging the Agentica-Claude proxy integration.

## When to Use

- Setting up Agentica agents to use Claude Code tools
- Debugging agent hallucination issues
- Fixing permission errors in file operations
- Understanding the REPL response format

## Architecture Overview

```
Agentica Agent → S_M_BASE_URL → Claude Proxy → claude -p → Claude CLI (with tools)
                 (localhost:2345)   (localhost:8080)
```

## Critical Requirements

### 1. --allowedTools Flag (REQUIRED)

Claude CLI in `-p` mode restricts file operations. You MUST add:

```python
subprocess.run([
    "claude", "-p", prompt,
    "--append-system-prompt", system_prompt,
    "--allowedTools", "Read", "Write", "Edit", "Bash",  # REQUIRED
])
```

Without this, agents will report "permission denied" for Write/Edit operations.

### 2. SSE Streaming Format (REQUIRED)

Agentica expects SSE streaming, not plain JSON:

```python
# Response format
yield f"data: {json.dumps(chunk)}\n\n"
yield "data: [DONE]\n\n"
```

### 3. REPL Response Format (REQUIRED)

Agents MUST return results as Python code blocks with a return statement:

```python
return "your result here"
```

Agentica's REPL parser extracts code between \`\`\`python and \`\`\`.

## Anti-Hallucination Prompt Engineering

Agents will hallucinate success without actually using tools unless you explicitly warn them:

```
## ANTI-HALLUCINATION WARNING

**STOP AND READ THIS CAREFULLY:**

You have access to these tools: Read, Write, Edit, Bash

When the task asks you to create/modify/run something:
1. FIRST: Actually invoke the tool (Read, Write, Edit, or Bash)
2. SECOND: Wait for the tool result
3. THIRD: Then return your answer based on what actually happened

**DO NOT** skip the tool invocation and just claim success!

If you didn't invoke a tool, you CANNOT claim the action succeeded.
```

## Path Sandboxing

Both Claude Code and Agentica have sandboxes:

- `/tmp/` paths are blocked by Claude Code
- Files outside project directory blocked by Agentica

**Solution:** Use project-relative paths like `workspace/` instead of `/tmp/`

## Debugging

### Check Agent Logs

```bash
cat logs/agent-<N>.log
```

Note: Logs only show final conversational response, not tool invocations.

### Test Proxy Directly

```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "claude", "messages": [{"role": "user", "content": "Create file at workspace/test.txt"}], "stream": false}'
```

### Verify File Operations

```bash
# After agent claims to create file
ls -la workspace/test.txt
cat workspace/test.txt
```

## Server Commands

### Start Servers

```bash
# Terminal 1: Proxy
uv run python scripts/agentica/claude_proxy.py --port 8080

# Terminal 2: Agentica Server
cd workspace/agentica-research/agentica-server
INFERENCE_ENDPOINT_URL=http://localhost:8080/v1/chat/completions uv run agentica-server --port 2345
```

### Use Swarm

```bash
S_M_BASE_URL=http://localhost:2345 uv run python your_script.py
```

### Health Checks

```bash
curl http://localhost:8080/health  # Proxy
curl http://localhost:2345/health  # Agentica
```

## Reference Files

- Proxy implementation: `scripts/agentica/claude_proxy.py`
- REPL_BASELINE prompt: `scripts/agentica/claude_proxy.py:49-155`
- Comprehensive test: `workspace/test_swarm_all_tools.py`
- DependencySwarm: `scripts/agentica/dependency_swarm.py`

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| "Permission denied" | Missing --allowedTools | Add `--allowedTools Read Write Edit Bash` |
| Agent claims success but file not created | Hallucination | Add anti-hallucination prompt section |
| "Cannot access /tmp/..." | Sandbox restriction | Use project-relative paths |
| "APIConnectionError" | Wrong response format | Use SSE streaming (data: {...}\n\n) |
| "NameError: view_file" | Agent using REPL functions | Add REPL_BASELINE with native tool examples |

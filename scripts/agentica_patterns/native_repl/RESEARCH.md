# Native REPL Research Notes

**Date:** 2025-12-26
**Context:** Approach 3 of Agentica-Claude integration evaluation

## Background

Three approaches being evaluated for building a hierarchical research agent:

| Approach | Intelligence Layer | Execution Layer | File I/O |
|----------|-------------------|-----------------|----------|
| **1. Baseline** | Claude Code Task agent | Claude Code tools directly | Native Read/Write/Edit |
| **2. Agentica Router** | Claude via HTTP proxy | Agentica REPL | REPL functions (broken - don't exist) |
| **3. Native REPL** | Claude via HTTP proxy | Agentica REPL | Claude Code CLI via scope wrappers |

## Key Insight

> "The agent script is code that triggers code to run within the REPL. The real agent is the one that lives in the REPL that produces the output."

The Agentica agent is orchestration. Claude Code CLI running inside the REPL scope is the actual worker.

---

## Agentica REPL Model (Oracle Research - docs.symbolica.ai)

### How Agents Execute Code

- Agents write Python code in **triple-backtick code blocks**
- REPL processes blocks and returns execution results
- If code not properly formatted: `"No code was executed. Use ```python code blocks to execute code."`

### Scope/State Model

**Scope** = dictionary defining what tools/functions an agent can access:

```python
from agentica import spawn

agent = await spawn(
    premise="You are a truth-teller.",
    scope={"web_search": web_search}  # <-- This is the scope
)
```

Per-call scope extension:
```python
result = await agent.call(
    "Analyze the dataset",
    {"dataset": dataset, "analyzer_tool": analyzer_tool}  # Additional scope
)
```

### State Persistence

| State Type | Behavior |
|------------|----------|
| Agent instances | State maintained automatically across calls |
| Agentic functions | Use `persist=True` for conversation history |
| REPL variables | Variables persist within session's execution context |

### Return Values

- Use `return` statement in a separate REPL session
- Type-safe: specify expected return type as first argument to `agent.call()`
- Supports primitives (`str`, `int`, `bool`) and Pydantic models

```python
result: int = await agent.call(int, "What is 2+2?")
```

---

## Claude Code CLI Reference (code.claude.com)

### Core Flags for Autonomous Operation

| Flag | Description | Example |
|------|-------------|---------|
| `-p, --print` | Non-interactive mode | `claude -p "query"` |
| `--max-turns` | Limit agentic turns | `--max-turns 3` |
| `--output-format` | Output: `text`, `json`, `stream-json` | `--output-format json` |
| `--model` | Model selection | `--model sonnet` |

### Tool Control Flags

| Flag | Description | Example |
|------|-------------|---------|
| `--allowed-tools` | Tools that execute without permission prompt | `"Bash(git:*)" "Read"` |
| `--disallowed-tools` | Tools removed from context entirely | `"Write" "Edit"` |
| `--dangerously-skip-permissions` | Skip all permission prompts | (flag only) |

### System Prompt Customization

| Flag | Description | Use Case |
|------|-------------|----------|
| `--system-prompt` | Replace entire system prompt | Full override |
| `--append-system-prompt` | Append to default prompt | **Recommended** - preserves Claude Code defaults |
| `--system-prompt-file` | Load from file | Long prompts |

### Session Management

| Flag | Description |
|------|-------------|
| `--continue` | Continue last session |
| `--resume` | Resume specific session by ID |
| `--session-id` | Use specific session ID (UUID) |

### Full Autonomous Agent Example

```bash
claude \
  --print \
  --output-format json \
  --agent my-agent \
  --allowed-tools "Read,Search,Bash(git:*)" \
  --append-system-prompt "Be concise and thorough" \
  --dangerously-skip-permissions \
  --add-dir ./additional-context \
  "Analyze the codebase and generate a report"
```

---

## Architecture for Approach 3

```
┌─────────────────────────────────────────────────────────────────┐
│  Python Script (orchestration)                                  │
│    └─ DependencySwarm.run(tasks)                                │
│                                                                 │
│         ┌─────────────────────────────────────────────────┐     │
│         │  Agent (Agentica spawn)                         │     │
│         │    └─ REPL Session                              │     │
│         │         └─ scope: { run_claude: async fn }      │     │
│         │                                                 │     │
│         │  Agent's REPL code:                             │     │
│         │  ```python                                      │     │
│         │  result = await run_claude(                     │     │
│         │      task="Read pyproject.toml",                │     │
│         │      tools=["Read"],                            │     │
│         │      max_turns=3                                │     │
│         │  )                                              │     │
│         │  return result                                  │     │
│         │  ```                                            │     │
│         │                                                 │     │
│         │  run_claude() executes:                         │     │
│         │  subprocess.run([                               │     │
│         │    'claude', '-p',                              │     │
│         │    '--max-turns', '3',                          │     │
│         │    '--output-format', 'json',                   │     │
│         │    '--allowed-tools', 'Read',                   │     │
│         │    '--dangerously-skip-permissions',            │     │
│         │    task                                         │     │
│         │  ])                                             │     │
│         └─────────────────────────────────────────────────┘     │
│                              ↓                                  │
│                         OUTPUT                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

1. **Use `--append-system-prompt`** not `--system-prompt` to preserve Claude Code's default behavior
2. **Use `--output-format json`** for parseable results in REPL
3. **Use `--dangerously-skip-permissions`** for headless operation
4. **Tool whitelist per task** - only enable tools needed for specific operation
5. **Max turns limit** - prevent runaway agent loops

## Files to Implement

- `run_claude.py` - Async wrapper function for Claude Code CLI
- `native_swarm.py` - DependencySwarm using native REPL with run_claude in scope
- `test_native_swarm.py` - Tests for comparison with Approaches 1 & 2

## References

- Agentica docs: https://docs.symbolica.ai
- Claude Code CLI: https://code.claude.com/docs/en/cli-reference
- Approach 1 baseline: `scripts/agentica/baseline/`
- Approach 2 router: `scripts/agentica/research_coordinator.py`

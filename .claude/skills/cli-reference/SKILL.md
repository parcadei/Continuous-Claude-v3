---
name: cli-reference
description: Claude Code CLI commands, flags, headless mode, and automation patterns
allowed-tools: [Read]
---

# CLI Reference

Complete reference for Claude Code command-line interface.

## When to Use

- "What CLI flags are available?"
- "How do I use headless mode?"
- "Claude in automation/CI/CD"
- "Output format options"
- "System prompt via CLI"

## Core Commands

```bash
claude                    # Start interactive REPL
claude "query"            # REPL with initial prompt
claude -p "query"         # Headless mode (exit after)
claude -c                 # Continue most recent session
claude -r "session" "q"   # Resume specific session
claude update             # Update to latest version
claude mcp                # Configure MCP servers
```

## Essential Flags

### Session Control

| Flag | Description |
|------|-------------|
| `-c, --continue` | Continue most recent conversation |
| `-r, --resume` | Resume by session ID or name |
| `--session-id` | Use specific UUID |
| `--fork-session` | Create new session on resume |

### Headless Mode

| Flag | Description |
|------|-------------|
| `-p, --print` | Non-interactive, exit after |
| `--output-format` | `text`, `json`, `stream-json` |
| `--max-turns` | Limit agentic turns |
| `--verbose` | Enable verbose logging |

### Tool Control

| Flag | Description |
|------|-------------|
| `--allowedTools` | Auto-approve these tools |
| `--disallowedTools` | Block these tools |
| `--tools` | Only allow these tools |
| `--dangerously-skip-permissions` | Skip all prompts |

### System Prompt

| Flag | Behavior |
|------|----------|
| `--system-prompt` | Replace entire prompt |
| `--system-prompt-file` | Replace from file |
| `--append-system-prompt` | Add to default (recommended) |

## Output Formats

### JSON
```bash
claude -p "query" --output-format json
# {"result": "...", "session_id": "...", "usage": {...}}
```

### Streaming
```bash
claude -p "query" --output-format stream-json
# Newline-delimited JSON events
```

### Structured Output
```bash
claude -p "Extract data" \
  --output-format json \
  --json-schema '{"type":"object","properties":{...}}'
```

## Common Patterns

### CI/CD Automation
```bash
claude -p "Run tests and fix failures" \
  --allowedTools "Bash,Read,Edit" \
  --output-format json | jq '.result'
```

### Piped Input
```bash
cat error.log | claude -p "Find root cause"
gh pr diff | claude -p "Review for security issues"
```

### Multi-turn
```bash
id=$(claude -p "Start" --output-format json | jq -r '.session_id')
claude -p "Continue" --resume "$id"
```

### Custom Agents
```bash
claude --agents '{
  "reviewer": {
    "description": "Code review specialist",
    "prompt": "Review for quality and security",
    "tools": ["Read", "Bash"],
    "model": "sonnet"
  }
}'
```

## Model Selection

```bash
claude --model sonnet    # Fast, capable
claude --model opus      # Most capable
claude --model haiku     # Fastest
```

## Keyboard Shortcuts (Interactive)

| Shortcut | Action |
|----------|--------|
| `Ctrl+C` | Cancel current |
| `Ctrl+D` | Exit |
| `Ctrl+R` | Reverse search history |
| `Esc Esc` | Rewind changes |
| `Shift+Tab` | Toggle permission mode |

## Quick Commands

| Prefix | Action |
|--------|--------|
| `/` | Slash command |
| `!` | Bash mode |
| `#` | Add to memory |
| `@` | File mention |

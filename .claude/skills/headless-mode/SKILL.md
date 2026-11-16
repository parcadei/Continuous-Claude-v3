---
name: headless-mode
description: Run Claude Code non-interactively for automation, CI/CD, and scripting
allowed-tools: [Read, Bash]
---

# Headless Mode Reference

Run Claude Code without interactive terminal for automation and scripting.

## When to Use

- "Run Claude in automation"
- "Non-interactive Claude"
- "Parse Claude output in scripts"
- "CI/CD integration"
- "Pipe input to Claude"

## Basic Usage

```bash
# Single query, exit after response
claude -p "Find bugs in this code"

# Continue previous conversation
claude -c -p "Now fix the bugs"

# Resume specific session
claude -r "session-id" -p "Continue work"
```

## Output Formats

### Text (Default)
```bash
claude -p "What does this code do?"
# Plain text response
```

### JSON
```bash
claude -p "Analyze code" --output-format json
# {
#   "result": "...",
#   "session_id": "abc-123",
#   "usage": {"input_tokens": 1234, "output_tokens": 567}
# }
```

### Streaming JSON
```bash
claude -p "Long task" --output-format stream-json
# Newline-delimited JSON events
```

### Structured Output
```bash
claude -p "Extract functions" \
  --output-format json \
  --json-schema '{"type":"object","properties":{"functions":{"type":"array"}}}'
```

## Tool Control

```bash
# Auto-approve specific tools
claude -p "Fix bugs" --allowedTools "Bash,Read,Edit"

# Block specific tools
claude -p "Analyze" --disallowedTools "Write,Edit"

# Only allow these tools
claude -p "Search" --tools "Read,Grep,Glob"

# Skip all permission prompts (DANGEROUS)
claude -p "Task" --dangerously-skip-permissions
```

## System Prompt Options

```bash
# Replace entire prompt
claude -p "query" --system-prompt "You are a security expert"

# Append to default (RECOMMENDED)
claude -p "query" --append-system-prompt "Focus on security"

# Load from file
claude -p "query" --system-prompt-file ./prompt.txt
```

## Common Patterns

### CI/CD Integration
```bash
claude -p "Run tests and fix failures" \
  --allowedTools "Bash,Read,Edit" \
  --max-turns 5 \
  --output-format json | jq '.result'
```

### Piped Input
```bash
cat error.log | claude -p "Find root cause"
gh pr diff | claude -p "Review for security"
```

### Multi-turn Conversation
```bash
# Start
id=$(claude -p "Start analysis" --output-format json | jq -r '.session_id')

# Continue
claude -p "Focus on database" --resume "$id" --output-format json
```

### Parse with jq
```bash
# Extract result
claude -p "Summarize" --output-format json | jq -r '.result'

# Extract session ID
claude -p "Start" --output-format json | jq -r '.session_id'

# Extract usage
claude -p "Analyze" --output-format json | jq '.usage'
```

## Key Flags

| Flag | Description |
|------|-------------|
| `-p, --print` | Headless mode (exit after) |
| `--output-format` | `text`, `json`, `stream-json` |
| `--max-turns` | Limit agentic turns |
| `--allowedTools` | Auto-approve tools |
| `-c, --continue` | Continue last session |
| `-r, --resume` | Resume specific session |
| `--verbose` | Enable verbose logging |

## GitHub Actions Example

```yaml
- name: Run Claude
  run: |
    claude -p "Review code" \
      --allowedTools "Bash,Read" \
      --output-format json > result.json

- name: Parse result
  run: |
    jq -r '.result' result.json
```

## Best Practices

1. **Use `--output-format json`** for parsing
2. **Set `--max-turns`** to prevent runaway
3. **Use `--allowedTools`** for predictable behavior
4. **Store session IDs** for multi-turn
5. **Use `--append-system-prompt`** (keeps defaults)

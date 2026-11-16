---
name: settings-reference
description: Claude Code settings, permissions, environment variables, and configuration files
allowed-tools: [Read, Bash]
---

# Settings Reference

Complete reference for Claude Code configuration files, permissions, and environment variables.

## When to Use

- "Where are Claude Code settings?"
- "How do I configure permissions?"
- "What environment variables does Claude use?"
- "How do I deny access to .env files?"
- "Settings precedence order"

## Configuration Scopes

| Scope | Location | Priority |
|-------|----------|----------|
| Enterprise | `/Library/Application Support/ClaudeCode/managed-settings.json` | Highest |
| Local | `.claude/settings.local.json` | High |
| Project | `.claude/settings.json` | Medium |
| User | `~/.claude/settings.json` | Low |

## Permission Modes

| Mode | Behavior |
|------|----------|
| `default` | Prompt on first use of each tool |
| `acceptEdits` | Auto-approve file edits |
| `plan` | Analyze only, no modifications |
| `bypassPermissions` | Skip all prompts (safe environments) |

## settings.json Structure

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run test:*)",
      "Read(./src/**)",
      "Edit(./src/**)"
    ],
    "ask": [
      "Bash(git push:*)"
    ],
    "deny": [
      "Read(.env)",
      "Read(.env.*)",
      "Read(./secrets/**)"
    ]
  },
  "sandbox": {
    "enabled": true,
    "excludedCommands": ["git", "docker"]
  },
  "env": {
    "NODE_ENV": "development"
  }
}
```

## Permission Patterns

```json
{
  "permissions": {
    "allow": [
      "Bash",                              // All bash
      "Bash(npm run test:*)",              // Wildcard
      "Read(./src/**)",                    // Glob pattern
      "WebFetch(domain:github.com)",       // Domain filter
      "mcp__github"                        // All tools from MCP server
    ]
  }
}
```

## Path Syntax

| Pattern | Meaning |
|---------|---------|
| `Read(./src/**)` | Relative to settings file |
| `Read(~/Documents/*)` | Home directory |
| `Read(//absolute/path)` | Absolute (double slash) |

## Key Environment Variables

### API & Auth
```bash
ANTHROPIC_API_KEY="sk-..."
```

### Model
```bash
ANTHROPIC_MODEL="claude-opus-4-5-20251101"
```

### Cloud Providers
```bash
CLAUDE_CODE_USE_VERTEX=1
CLAUDE_CODE_USE_BEDROCK=1
```

### Execution
```bash
BASH_DEFAULT_TIMEOUT_MS=30000
BASH_MAX_TIMEOUT_MS=120000
```

### Telemetry
```bash
DISABLE_TELEMETRY=1
DISABLE_AUTOUPDATER=1
```

## Secure Development Template

```json
{
  "permissions": {
    "allow": [
      "Bash(npm run:*)",
      "Bash(git:*)",
      "Read(./src/**)",
      "Edit(./src/**)"
    ],
    "deny": [
      "Read(.env)",
      "Read(.env.*)",
      "Read(./secrets/**)"
    ]
  },
  "sandbox": {
    "enabled": true,
    "excludedCommands": ["git", "docker"]
  }
}
```

## Commands

```bash
/config            # View current settings
/allowed-tools     # Interactive permission editor
/permissions       # View all permission rules
```

---
name: mcp-configuration
description: Configure MCP (Model Context Protocol) servers - transports, scopes, authentication, and troubleshooting
allowed-tools: [Read, Bash]
---

# MCP Configuration Reference

Connect Claude Code to external tools, databases, and APIs via MCP servers.

## When to Use

- "How do I add an MCP server?"
- "Configure MCP for GitHub/Sentry/database"
- "MCP authentication setup"
- "MCP connection not working"
- "What's the difference between stdio/http/sse?"

## Transport Types

### HTTP (Recommended for Cloud Services)

```bash
# Basic
claude mcp add --transport http notion https://mcp.notion.com/mcp

# With auth header
claude mcp add --transport http stripe https://mcp.stripe.com \
  --header "Authorization: Bearer ${STRIPE_API_KEY}"
```

### Stdio (Local Processes)

```bash
# Pattern: everything AFTER -- is the command
claude mcp add --transport stdio airtable \
  --env AIRTABLE_API_KEY=YOUR_KEY \
  -- npx -y airtable-mcp-server

# Windows: needs cmd /c wrapper
claude mcp add --transport stdio server -- cmd /c npx -y package
```

### SSE (Legacy)

```bash
claude mcp add --transport sse asana https://mcp.asana.com/sse
```

## Scopes

| Scope | Location | Shared? | Command |
|-------|----------|---------|---------|
| Local | `~/.claude.json` (project key) | No | `--scope local` (default) |
| Project | `.mcp.json` | Yes (git) | `--scope project` |
| User | `~/.claude.json` | No | `--scope user` |

**Precedence:** Local > Project > User

## .mcp.json Format

```json
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {
        "Authorization": "Bearer ${GITHUB_TOKEN}"
      }
    },
    "database": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@bytebase/dbhub"],
      "env": {
        "DATABASE_URL": "${DATABASE_URL}"
      }
    }
  }
}
```

## Environment Variable Expansion

```json
{
  "url": "${API_URL}",                    // Required
  "url": "${API_URL:-https://default}",   // With fallback
}
```

## Common Servers

```bash
# GitHub
claude mcp add --transport http github https://api.githubcopilot.com/mcp/

# Sentry
claude mcp add --transport http sentry https://mcp.sentry.dev/mcp

# PostgreSQL
claude mcp add --transport stdio db \
  -- npx -y @bytebase/dbhub --dsn "${DATABASE_URL}"

# Filesystem
claude mcp add --transport stdio fs \
  -- npx -y @modelcontextprotocol/server-filesystem /path/to/dir
```

## Management Commands

```bash
claude mcp list                    # List all servers
claude mcp get <name>              # Server details
claude mcp remove <name>           # Remove server
/mcp                               # In-session management + OAuth
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Connection closed" (Windows) | Add `cmd /c` before npx |
| Env var not expanding | Export before running claude |
| "MCP server not configured" | Check `claude mcp list`, verify scope |
| "Cannot find command" | Use full path: `/usr/local/bin/python3` |

## OAuth Authentication

```bash
# Add server, then authenticate in Claude:
claude mcp add --transport http github https://api.githubcopilot.com/mcp/
# Then run /mcp and select "Authenticate"
```

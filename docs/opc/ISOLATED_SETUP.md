# OPC Isolated Development Setup

Run Claude Code in complete isolation so it thinks it's in a fresh global environment.

## Quick Start

```bash
# Create PERSISTENT isolated config directory (survives reboot)
mkdir -p ~/.opc-dev/.claude

# Copy OPC configuration to isolated location
cp -r .claude/* ~/.opc-dev/.claude/

# Copy handoffs/thoughts for continuity
cp -r thoughts ~/.opc-dev/

# Run Claude with isolated config
CLAUDE_CONFIG_DIR=~/.opc-dev claude
```

**Note:** Use `~/.opc-dev/` not `/tmp/` - tmp is cleared on reboot!

## What This Does

- `CLAUDE_CONFIG_DIR` overrides the default `~/.claude/` location
- Claude sees `/tmp/opc-dev/.claude/` as its "global" config
- No conflict with your actual global Claude setup
- All agents, skills, hooks, and settings are isolated

## Development Workflow

```bash
# Terminal 1: Start isolated Claude
export CLAUDE_CONFIG_DIR=/tmp/opc-dev
claude

# Terminal 2: Monitor TUI (separate process)
cd /path/to/opc && docker-compose up -d
python scripts/observe_agents.py --watch
```

## Verify Isolation

Inside Claude Code, run:
```
/config
```

You should see paths pointing to `/tmp/opc-dev/.claude/` not `~/.claude/`.

## Reset Environment

```bash
# Wipe and recreate isolated env
rm -rf /tmp/opc-dev
mkdir -p /tmp/opc-dev/.claude
cp -r .claude/* /tmp/opc-dev/.claude/
```

## Docker Backend

The Docker stack (PostgreSQL, Redis) runs separately and doesn't need isolation:

```bash
# Start backend services
docker-compose up -d

# Check status
docker-compose ps
```

## Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `CLAUDE_CONFIG_DIR` | Override config location | `/tmp/opc-dev` |
| `CLAUDE_ENV` | dev/prod mode | `dev` |
| `TEMPORAL_BACKEND` | sqlite/postgres | `postgres` |

## Scope Hierarchy (Reference)

Claude Code has 4 scope levels:
1. **Enterprise** (highest precedence) - managed by org
2. **Local** - `$CLAUDE_CONFIG_DIR/.claude/settings.local.json`
3. **Project** - `.claude/settings.json` in project
4. **User** (lowest) - `~/.claude/settings.json`

`CLAUDE_CONFIG_DIR` overrides where Local and User scopes are read from.

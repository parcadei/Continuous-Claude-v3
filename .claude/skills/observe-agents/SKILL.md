---
name: observe-agents
description: Query agent memory, blackboard, tasks, and outputs while agents run
allowed-tools: [Bash, Read]
---

# Observe Running Agents

Query all agent data sources from main Claude while agents run in background.

## When to Use

- User asks "what are agents doing?"
- User asks "what's on the blackboard?"
- User asks "what did agents remember/store?"
- Need to check agent progress during swarm/hierarchical execution
- Debugging agent coordination issues

## Data Sources

| Source | What's There | Command |
|--------|--------------|---------|
| **Memory** | PostgreSQL archival_memory | `--what memory` |
| **Blackboard** | HOT tier JSON files | `--what blackboard` |
| **Tasks** | Task graph SQLite | `--what tasks` |
| **Outputs** | Agent markdown files | `--what outputs` |
| **All** | Combined view | `--what all` |

## Commands

### Quick Check (All Sources)
```bash
uv run python scripts/observe_agents.py --what all
```

### Query Memory
```bash
# All recent memory
uv run python scripts/observe_agents.py --what memory

# Search for specific content
uv run python scripts/observe_agents.py --what memory --query "API design"

# Filter by session
uv run python scripts/observe_agents.py --what memory --session-id abc123
```

### Check Blackboard
```bash
uv run python scripts/observe_agents.py --what blackboard
```

### View Tasks
```bash
uv run python scripts/observe_agents.py --what tasks
```

### List Agent Outputs
```bash
uv run python scripts/observe_agents.py --what outputs
```

### JSON Output (for parsing)
```bash
uv run python scripts/observe_agents.py --what all --json
```

## Architecture

```
Main Claude (this skill)
    |
    +-- PostgreSQL -------- memory, tags, temporal
    |   \-- GLOBAL VIEW (no session filter)
    |
    +-- Blackboard -------- /tmp/claude-blackboard/*.json
    |   \-- Live agent state
    |
    +-- Task Graph -------- .claude/cache/agentica-coordination/tasks.db
    |   \-- Task dependencies
    |
    \-- Agent Outputs ----- .claude/cache/agents/*/
        \-- Summaries and handoffs
```

## Example Use Cases

1. **Monitor Swarm Progress**
   ```bash
   # Check what swarm agents have found
   uv run python scripts/observe_agents.py --what memory --query "research"
   ```

2. **Debug Blackboard Communication**
   ```bash
   # See all blackboard entries
   uv run python scripts/observe_agents.py --what blackboard
   ```

3. **Track Task Completion**
   ```bash
   # View task graph state
   uv run python scripts/observe_agents.py --what tasks
   ```

## Requirements

- PostgreSQL running (for memory queries)
- Environment: `AGENTICA_POSTGRES_URL` set

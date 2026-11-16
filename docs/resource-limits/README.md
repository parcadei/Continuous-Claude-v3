# Dynamic Resource Limits & Orphan Detection

> Intelligent process management for Claude Code multi-agent workflows

Prevent out-of-memory conditions and orphaned processes when orchestrating multiple Claude Code agents. This system dynamically calculates agent limits based on available RAM and automatically cleans up abandoned agent processes using a three-tier detection algorithm.

## Features

- **Dynamic Limits** - RAM-based agent limits that adapt to your system (formula: `(freeRAM - 2GB) / 500MB`)
- **Orphan Detection** - Three-tier detection distinguishing Unix orphans from app-level orphans
- **Status Visibility** - See resource usage (`RAM:8G Ag:3/12`) in your status line
- **Safe Defaults** - Dry-run by default, main sessions protected from cleanup
- **Soft + Hard Limits** - Advisory warnings at 80%, blocking at 100% capacity

## How It Works

```
                    +-------------------+
                    |    status.sh      |  Calculates RAM + agent count
                    +-------------------+
                            |
                            v
                    /tmp/claude-resources-{session}.json
                            |
            +---------------+---------------+
            v                               v
+------------------------+    +------------------------+
| skill-activation.ts    |    |    pre-tool-use.ts     |
| (Soft limit: advisory) |    | (Hard limit: blocks)   |
+------------------------+    +------------------------+
            |
            v
+-------------------------------------------+
|           session-end-cleanup.ts          |  Orphan detection
+-------------------------------------------+
```

## Quick Start

### View Current Resource Status

```bash
# Check resource status in status line
# Status displays: "145K 72% | main U:6 | RAM:8G Ag:3/12"

# View orphan candidates
uv run python scripts/agentica/watch_agents.py --orphans
```

### Monitor Running Agents

```bash
# Real-time agent table
uv run python scripts/agentica/watch_agents.py --watch

# With subprocess tracking
uv run python scripts/agentica/watch_agents.py --monitor
```

### Clean Up Orphaned Agents

```bash
# Dry run (default, safe)
uv run python scripts/agentica/cleanup_orphans.py --dry-run

# Only kill Unix orphans (tier 1, safest)
uv run python scripts/agentica/cleanup_orphans.py --kill --tier 1

# Kill all orphan tiers (use with caution)
uv run python scripts/agentica/cleanup_orphans.py --kill
```

### Test Resource Limits

```bash
# Simulate hitting the limit
echo '{"freeMemMB": 4000, "activeAgents": 8, "maxAgents": 8}' > /tmp/claude-resources-test.json
echo '{"tool_name": "Task"}' | CLAUDE_SESSION_ID=test npx tsx .claude/hooks/src/pre-tool-use.ts
# Expected: {"result":"block","reason":"Agent limit reached: 8/8 agents running..."}
```

## Orphan Detection Tiers

| Tier | Condition | Grace Period | Risk |
|------|-----------|--------------|------|
| 1 | `ppid = 1` (Unix orphan) | None | Safe |
| 2 | Parent agent dead | 30 minutes | Low |
| 3 | Running > 24 hours | 24 hours | Medium |

**Important:** Main sessions (`parent_agent_id IS NULL`) are always excluded from orphan detection.

## Resource Limit Formula

```
max_agents = (freeRAM_MB - 2048) / 500
```

- **Safety Buffer:** 2GB reserved for system
- **Per Agent:** 500MB allocation
- **Minimum:** 1 agent (always allows at least one)
- **Maximum:** Capped at 20 agents

## Status Line Display

When agents are active, your status line shows resource usage:

- **Green:** `RAM:12G Ag:2/16` (< 50% utilized)
- **Yellow:** `RAM:8G Ag:6/10` (50-75% utilized)
- **Red:** `RAM:4G Ag:8/8` (> 75% utilized)

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](01-architecture.md) | System design, code maps, and component diagrams |
| [Problem & Reasoning](02-problem-and-reasoning.md) | Why we built this and design decisions |
| [User Guide](03-user-guide.md) | How to use the system effectively |
| [API Reference](04-api-reference.md) | Developer documentation and interfaces |

## File Structure

```
.claude/
  hooks/src/
    shared/
      resource-reader.ts    # Reads /tmp resource JSON
      resource-utils.ts     # Node.js os module wrapper
    pre-tool-use.ts         # Hard limit (blocks Task)
    skill-activation-prompt.ts  # Soft limit (advisory)
    session-end-cleanup-swarms.ts  # Orphan cleanup trigger
  scripts/
    get-resources.sh        # Cross-platform RAM detection
    status.sh               # Status line + resource JSON output

scripts/agentica/
  coordination.py           # SQLite DB with pid/ppid tracking
  watch_agents.py           # Agent monitoring + orphan display
  cleanup_orphans.py        # Three-tier orphan cleanup CLI
```

## Requirements

- Claude Code CLI
- Python 3.11+
- Node.js 18+
- macOS or Linux (Windows requires WSL)

## Test Coverage

| Category | Tests | Status |
|----------|-------|--------|
| Resource Utils | 21 | Passing |
| Agent Count | 7 | Passing |
| Status Resources | 18 | Passing |
| Resource Reader | 20 | Passing |
| Soft/Hard Limits | 31 | Passing |
| Orphan Detection | 46 | Passing |
| Status Line Display | 14 | Passing |

Run all tests:
```bash
uv run pytest tests/unit/test_resource_*.py \
              tests/unit/test_orphan_*.py \
              tests/unit/test_cleanup_*.py \
              tests/unit/test_status_*.py -v
```

## Configuration

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `CLAUDE_SESSION_ID` | Session identifier for resource file paths |
| `CLAUDE_PROJECT_DIR` | Project root directory |
| `PATTERN_TYPE` | Current orchestration pattern (swarm, jury, etc.) |

### Tunable Parameters (status.sh)

```bash
safety_mb=2048      # Reserved RAM buffer
per_agent_mb=500    # RAM per agent
max_cap=20          # Absolute maximum agents
```

## Troubleshooting

### Agents spawning despite limit

1. Check resource file exists: `cat /tmp/claude-resources-*.json`
2. Verify status.sh is running: Check status line shows context %
3. Check hook registration in `.claude/settings.json`

### Orphan cleanup too aggressive

1. Use `--dry-run` first to preview what would be cleaned
2. Use `--tier 1` to only clean safest Unix orphans
3. Increase grace periods in `coordination.py` if needed

### Resource file not updating

1. Ensure status.sh has execute permissions
2. Check Python availability: `uv run python --version`
3. Verify coordination.db exists in `.claude/cache/agentica-coordination/`

## License

MIT License - see [LICENSE](../../LICENSE) for details.

---

**Implementation Status:** 13/14 phases complete | 187 tests | Production Ready

See [FINAL-REVIEW.md](../implementation/FINAL-REVIEW.md) for complete implementation details.

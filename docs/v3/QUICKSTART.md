# Quick Start

Get Claude Continuity Kit running in 5 minutes.

## Prerequisites

- **Python 3.12+** - [Download](https://www.python.org/downloads/)
- **uv** (package manager) - [Install uv](https://docs.astral.sh/uv/)
- **Node.js 18+** (for hooks) - [Download](https://nodejs.org/)

Optional:
- **Docker** - For PostgreSQL (multi-agent memory)
- **API Keys** - For external services (see [Environment Variables](#environment-variables))

## Installation

### Step 1: Clone and Install

```bash
git clone https://github.com/parcadei/claude-continuity-kit.git
cd claude-continuity-kit
uv sync
```

**Expected output:**
```
Resolved 42 packages in 1.23s
Downloaded 12 packages in 0.89s
Installed 42 packages in 0.45s
```

### Step 2: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` to add API keys (all optional):

```bash
# Session tracing (recommended)
BRAINTRUST_API_KEY=sk-...

# Web research
PERPLEXITY_API_KEY=pplx-...

# Fast code search
MORPH_API_KEY=sk-...
```

### Step 3: Verify Installation

```bash
uv run pytest tests/unit/test_greeting.py -v
```

**Expected output:**
```
tests/unit/test_greeting.py::test_greeting PASSED
========================= 1 passed in 0.12s =========================
```

## Your First Session

### Start a Session

```bash
claude
```

You should see the status line appear:
```
12.5K 8% | main U:0 |
```

### Test Continuity

1. **Update the ledger:**
   ```
   "save state, I'm testing the continuity system"
   ```

2. **Run `/clear` and verify reload:**
   ```
   /clear
   ```

   The system message should show your ledger was loaded:
   ```
   Loaded ledger: thoughts/ledgers/CONTINUITY_CLAUDE-<session>.md
   ```

### Use a Pattern (Optional - requires PostgreSQL)

For multi-agent patterns, start PostgreSQL first:

```bash
# Terminal 1: Start database
./docker/start-postgres.sh

# Terminal 2: Watch agents (optional)
uv run python scripts/agentica/watch_agents.py

# Terminal 3: Start Claude
claude
```

Try a simple swarm:
```
Use swarm pattern to analyze 3 different approaches for error handling.
```

**What happens:**
1. Coordinator spawns 3 research agents
2. Each explores a different angle
3. Results are synthesized into a single report
4. Memory persists in PostgreSQL

## What to Expect

After setup, you have:

| Feature | Status | Requires |
|---------|--------|----------|
| Continuity ledgers | Working | Nothing |
| Handoff system | Working | Nothing |
| TDD workflow | Working | Nothing |
| Status line | Working | Nothing |
| Skill suggestions | Working | Nothing |
| Session tracing | Optional | BRAINTRUST_API_KEY |
| Multi-agent patterns | Optional | PostgreSQL |
| Web search | Optional | PERPLEXITY_API_KEY |
| Fast code search | Optional | MORPH_API_KEY |

## Next Steps

- [PATTERNS.md](architecture/PATTERNS.md) - Learn all 11 orchestration patterns
- [HOOKS.md](HOOKS.md) - Customize session lifecycle behavior
- [EXAMPLES.md](EXAMPLES.md) - Runnable code samples

## Troubleshooting

### Common Issues

| Error | Solution |
|-------|----------|
| `uv: command not found` | Install uv: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `Python 3.11 detected` | Update `.python-version`: `echo "3.13" > .python-version && rm -rf .venv && uv venv && uv sync` |
| `MCP server not configured` | Run `uv run mcp-generate` and check `.env` has required keys |
| Ledger not loading after `/clear` | Verify `thoughts/ledgers/CONTINUITY_CLAUDE-*.md` exists; check `chmod +x .claude/hooks/*.sh` |
| `ModuleNotFoundError: No module named 'agentica'` | Run `uv sync --extra agentica` |
| PostgreSQL connection refused | Run `./docker/start-postgres.sh` and verify: `docker ps \| grep postgres` |

### Quick Diagnostics

```bash
# Check Python version
uv run python --version

# Check installed packages
uv pip list | grep -E "agentica|mcp|pydantic"

# Verify hooks are executable
ls -la .claude/hooks/*.sh

# Check ledger directory exists
ls -la thoughts/ledgers/

# Test MCP runtime
uv run python -m runtime.harness --help
```

### Getting Help

- **GitHub Issues** - Bug reports and feature requests
- **README.md** - Full documentation
- **docs/TROUBLESHOOTING.md** - Extended troubleshooting guide

---

**Ready to go deeper?** See [PATTERNS.md](architecture/PATTERNS.md) for multi-agent orchestration patterns or [ARCHITECTURE.md](ARCHITECTURE.md) for system design details.

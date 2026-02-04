# Continuous-Claude Windows Cheat Sheet

> **See also:** [Architecture Docs](docs/architecture/INDEX.md) for system overview and navigation

## Memory Daemon

```powershell
# Check status
python C:\Users\david.hayes\.claude\scripts\core\core\memory_daemon.py status

# Start manually
C:\Users\david.hayes\.claude\scripts\start-memory-daemon.ps1

# Stop
python C:\Users\david.hayes\.claude\scripts\core\core\memory_daemon.py stop
```

## Docker Services (PostgreSQL - Port 5432)

```powershell
# Start PostgreSQL (auto-starts on session via session-start-docker hook)
& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" compose -f "C:\Users\david.hayes\.claude\docker\docker-compose.yml" up -d

# Check status
& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" ps --filter "name=continuous-claude-postgres"

# Stop PostgreSQL
& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" compose -f "C:\Users\david.hayes\.claude\docker\docker-compose.yml" down

# View logs
& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" logs continuous-claude-postgres

# Query database directly
& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" exec continuous-claude-postgres psql -U claude -d continuous_claude -c "SELECT COUNT(*) FROM archival_memory;"
```

**Note:** Container uses port 5432 (default PostgreSQL port)

## Task Scheduler (Auto-Start)

```powershell
# View task
Get-ScheduledTask -TaskName 'ClaudeMemoryDaemon'

# Run now
Start-ScheduledTask -TaskName 'ClaudeMemoryDaemon'

# Remove auto-start
Unregister-ScheduledTask -TaskName 'ClaudeMemoryDaemon' -Confirm:$false

# Re-create auto-start
C:\Users\david.hayes\.claude\scripts\setup-task-scheduler.ps1
```

## Hooks

```powershell
# Rebuild TypeScript hooks after changes
cd C:\Users\david.hayes\.claude\hooks
npm run build

# Build single hook
node node_modules/esbuild/bin/esbuild src/my-hook.ts --bundle --platform=node --format=esm --outdir=dist --out-extension:.js=.mjs

# Test a hook manually (example)
echo '{}' | node C:\Users\david.hayes\.claude\hooks\dist\session-register.mjs
```

### Key Hooks
| Hook | Trigger | Purpose |
|------|---------|---------|
| `session-start-docker.mjs` | SessionStart | Auto-start PostgreSQL container |
| `session-register.mjs` | SessionStart | Register in coordination DB |
| `session-start-continuity.mjs` | SessionStart | Load handoff ledger |
| `session-start-tree-daemon.ps1` | SessionStart | Start knowledge tree watcher |
| `session-start-memory-daemon.ps1` | SessionStart | **Auto-start memory daemon** |
| `memory-awareness.mjs` | UserPromptSubmit | Auto-inject relevant memories |
| `pageindex-watch.mjs` | PostToolUse:Write\|Edit | Rebuild PageIndex on .md changes |
| `pre-compact-extract.mjs` | PreCompact | Extract learnings before compression |
| `smarter-everyday.mjs` | PostToolUse | Detect problem resolution patterns |
| `user-confirmation-detector.mjs` | UserPromptSubmit | Capture "it's fixed" signals |
| `session-end-extract.mjs` | SessionEnd | Final learning extraction sweep |
| `maestro-state-manager.mjs` | UserPromptSubmit | Track maestro workflow state |
| `ralph-delegation-enforcer.mjs` | PreToolUse:Task | Enforce ralph routing (**BLOCKS**) |
| `git-memory-check.mjs` | PreToolUse:Bash | Check memory before git (**BLOCKS**) |
| `pre-tool-knowledge.mjs` | PreToolUse:Task | Inject knowledge tree context |
| `post-plan-roadmap.mjs` | PostToolUse:ExitPlanMode | Update ROADMAP from plan |
| `roadmap-completion.mjs` | PostToolUse:TaskUpdate | Mark goals complete |
| `prd-roadmap-sync.mjs` | PostToolUse:Write\|Edit | Sync PRD/Tasks with ROADMAP |
| `sync-to-repo.mjs` | PostToolUse:Write\|Edit | Auto-sync to team repo |

## Repo Sync

```powershell
# Manual sync (if needed)
cd C:\Users\david.hayes\continuous-claude\scripts
bash sync-claude.sh --to-repo --dry-run  # Preview
bash sync-claude.sh --to-repo            # Apply

# Pull team updates
cd C:\Users\david.hayes\continuous-claude && git pull
bash scripts/sync-claude.sh --from-repo
```

**Auto-sync:** The `sync-to-repo.mjs` hook automatically syncs changes to `hooks/`, `skills/`, `rules/`, `agents/`, `scripts/` when you edit files in `~/.claude`.

## Knowledge Tree

```powershell
# Check daemon status
cd ~/.claude/scripts/core/core; uv run python tree_daemon.py --project . --status

# Regenerate manually
cd ~/.claude/scripts/core/core; uv run python knowledge_tree.py --project .

# Query tree
cd ~/.claude/scripts/core/core; uv run python query_tree.py --project . --describe
cd ~/.claude/scripts/core/core; uv run python query_tree.py --project . --query "where to add API"
```

**Output:** `{project}/.claude/knowledge-tree.json`
**Daemon:** Auto-starts on session, debounces 2s on file changes

## ROADMAP

```powershell
# Location
{project}/ROADMAP.md  # or {project}/.claude/ROADMAP.md
```

### /roadmap Skill Commands

| Command | Purpose |
|---------|---------|
| `/roadmap show` | Display current ROADMAP state |
| `/roadmap add <item>` | Add item to Planned section |
| `/roadmap focus <item>` | Set Current Focus |
| `/roadmap complete` | Mark current goal done |

### The 4 ROADMAP Hooks

| Hook | Trigger | ROADMAP Section |
|------|---------|-----------------|
| `post-plan-roadmap` | ExitPlanMode | Current Focus + Recent Planning |
| `prd-roadmap-sync` | Write\|Edit PRD files | Planned |
| `git-commit-roadmap` | Bash git commit | Completed |
| `roadmap-completion` | TaskUpdate completed | Current Focus → Completed |

### Plan Directory Fallback
The post-plan-roadmap hook checks 3 locations (in order):
1. `{projectDir}/.claude/plans` - Standard project plans
2. `{projectDir}/plans` - When project IS ~/.claude
3. `~/.claude/plans` - User-level fallback

## Rollback

```powershell
# Stop everything first
python C:\Users\david.hayes\.claude\scripts\core\core\memory_daemon.py stop
& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" compose -f "C:\Users\david.hayes\.claude\docker\docker-compose.yml" down

# Restore from backup
Remove-Item "C:\Users\david.hayes\.claude" -Recurse -Force
Copy-Item "C:\Users\david.hayes\claude-archives\superClaude-v4.1.0-20260110-175711" "C:\Users\david.hayes\.claude" -Recurse
```

## Key Directories

| Path | Purpose |
|------|---------|
| `.claude\hooks\` | Hook scripts (100+ files) |
| `.claude\hooks\dist\` | Compiled JS hooks (100+ files) |
| `.claude\scripts\pageindex\` | PageIndex CLI and tree search |
| `.claude\agents\` | Agent definitions (53 files) |
| `.claude\skills\` | Skill definitions (383 files) |
| `.claude\scripts\core\core\` | Memory daemon, TLDR |
| `.claude\docker\` | PostgreSQL compose |
| `.claude\commands\` | SuperClaude commands (preserved) |
| `thoughts\shared\handoffs\` | Session handoffs |
| `thoughts\ledgers\` | Continuity ledgers |

## Environment Variables

```powershell
# Set PostgreSQL connection (user-level)
[System.Environment]::SetEnvironmentVariable('DATABASE_URL', 'postgresql://claude:claude_dev@localhost:5432/continuous_claude', 'User')

# Verify
$env:DATABASE_URL

# Required in ~/.claude/.env
DATABASE_URL=postgresql://claude:claude_dev@localhost:5432/continuous_claude
BRAINTRUST_API_KEY=sk-...
TRACE_TO_BRAINTRUST=true
```

## Troubleshooting

### DATABASE_URL Priority
The system loads DATABASE_URL in this order:
1. `opc/.env` (authoritative - uses override=True)
2. Shell environment variables
3. `~/.claude/.env` (supplements only)

```powershell
# Check if daemon is running
python C:\Users\david.hayes\.claude\scripts\core\core\memory_daemon.py status

# Check Docker
& "C:\Program Files\Docker\Docker\resources\bin\docker.exe" ps

# Check hook logs (if any errors)
Get-Content C:\Users\david.hayes\.claude\memory-daemon.log -Tail 20

# Verify settings.json is valid JSON
Get-Content C:\Users\david.hayes\.claude\settings.json | ConvertFrom-Json
```

---
*Created: 2026-01-10 | Continuous-Claude-v3 Windows Adaptation*

---

## Memory System (Semantic Recall)

### Recall Learnings
```powershell
# Hybrid search (text + vector) - RECOMMENDED
cd ~/.claude && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "your topic"

# Pure vector search (similarity scores 0.4-0.9)
cd ~/.claude && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "topic" --vector-only

# Text-only (fast, no embedding)
cd ~/.claude && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "topic" --text-only
```

### Store Learning
```powershell
cd ~/.claude && PYTHONPATH=. uv run python scripts/core/store_learning.py `
  --session-id "name" --type WORKING_SOLUTION `
  --content "What you learned" --context "topic" `
  --tags "tag1,tag2" --confidence high
```

**Note:** `--project-dir` auto-detected from `CLAUDE_PROJECT_DIR` env var

### Learning Types
| Type | Use For |
|------|---------|
| `WORKING_SOLUTION` | Fixes that worked |
| `FAILED_APPROACH` | What didn't work |
| `ARCHITECTURAL_DECISION` | Design choices |
| `ERROR_FIX` | Error->solution pairs |

### Score Interpretation
| Mode | Good Score | Notes |
|------|------------|-------|
| Hybrid RRF | 0.02-0.03 | Low is fine (ranking fusion) |
| Vector-only | 0.4-0.9 | Cosine similarity |

### Backfill Embeddings
```powershell
cd ~/.claude/scripts/core; uv run python core/backfill_embeddings.py
```

### Quick DB Queries
```powershell
# Count memories
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c "SELECT COUNT(*) FROM archival_memory;"

# Check embedding coverage
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c "SELECT COUNT(*) as total, COUNT(embedding) as with_emb FROM archival_memory;"
```

### Embedding Model
- **Model**: BAAI/bge-large-en-v1.5 (local, free)
- **Dimensions**: 1024
- **Index**: HNSW (fast cosine similarity)

---

## PageIndex (Document Navigation)

PageIndex provides **reasoning-based document search** with 98.7% accuracy (vs ~50% for vector similarity).

### Generate Tree for Document
```powershell
cd $CLAUDE_OPC_DIR && uv run python scripts/pageindex/cli/pageindex_cli.py generate ROADMAP.md
```

### Search Indexed Documents
```powershell
cd $CLAUDE_OPC_DIR && uv run python scripts/pageindex/cli/pageindex_cli.py search "current goals"
```

### Hybrid Search (Vector + PageIndex) - RECOMMENDED
```powershell
cd $CLAUDE_OPC_DIR && uv run python scripts/core/recall_learnings.py --query "topic" --hybrid
```

### PageIndex-Only Search
```powershell
cd $CLAUDE_OPC_DIR && uv run python scripts/core/recall_learnings.py --query "topic" --pageindex
```

### List Indexed Documents
```powershell
cd $CLAUDE_OPC_DIR && uv run python scripts/pageindex/cli/pageindex_cli.py list
```

**When to use:** Large structured docs (ROADMAP, ARCHITECTURE). 98.7% accuracy vs ~50% vector similarity.

---
*Updated: 2026-02-03 | + PageIndex System, Five Pillars*

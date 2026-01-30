# Continuous Claude Memory Architecture

> Generated: 2026-01-30 (Memory daemon auto-start added)

## Claude Code Intelligence Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CLAUDE CODE SESSION                                     │
│                                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │   User      │───▶│   Claude    │───▶│    Tools    │───▶│   Output    │          │
│  │   Prompt    │    │   Reasoning │    │   (Bash,    │    │   Response  │          │
│  └─────────────┘    └─────────────┘    │   Edit...)  │    └─────────────┘          │
│         │                  │           └─────────────┘           │                  │
└─────────│──────────────────│─────────────────────────────────────│──────────────────┘
          │                  │                                     │
          ▼                  ▼                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                    HOOKS LAYER                                       │
│                                                                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐                   │
│  │  SessionStart    │  │   PreToolUse     │  │  PostToolUse     │                   │
│  │  ──────────────  │  │  ──────────────  │  │  ──────────────  │                   │
│  │  • Docker start  │  │  • Knowledge     │  │  • Braintrust    │                   │
│  │  • Session reg   │  │    injection     │  │    span logging  │                   │
│  │  • Tree daemon   │  │  • Task routing  │  │  • Learning      │                   │
│  │  • Continuity    │  │                  │  │    extraction    │                   │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘                   │
└───────────│─────────────────────│─────────────────────│─────────────────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                              FOUR PILLARS OF INTELLIGENCE                             │
├───────────────────┬───────────────────┬───────────────────┬───────────────────────────┤
│                   │                   │                   │                           │
│  ┌─────────────┐  │  ┌─────────────┐  │  ┌─────────────┐  │  ┌─────────────────────┐  │
│  │   MEMORY    │  │  │  KNOWLEDGE  │  │  │   ROADMAP   │  │  │     BRAINTRUST      │  │
│  │   SYSTEM    │  │  │    TREE     │  │  │             │  │  │                     │  │
│  └──────┬──────┘  │  └──────┬──────┘  │  └──────┬──────┘  │  └──────────┬──────────┘  │
│         │         │         │         │         │         │             │             │
│  ┌──────▼──────┐  │  ┌──────▼──────┐  │  ┌──────▼──────┐  │  ┌──────────▼──────────┐  │
│  │ PostgreSQL  │  │  │    JSON     │  │  │  Markdown   │  │  │   Braintrust API    │  │
│  │ + pgvector  │  │  │    File     │  │  │    File     │  │  │   (Cloud)           │  │
│  └─────────────┘  │  └─────────────┘  │  └─────────────┘  │  └─────────────────────┘  │
│         │         │         │         │         │         │             │             │
│  PURPOSE:        │  PURPOSE:         │  PURPOSE:         │  PURPOSE:                 │
│  ───────────     │  ───────────      │  ───────────      │  ───────────              │
│  • Cross-session │  • Project        │  • Goal           │  • Session                │
│    learning      │    navigation     │    tracking       │    observability          │
│  • Pattern       │  • File           │  • Progress       │  • Span                   │
│    recall        │    discovery      │    visibility     │    tracing                │
│  • Error→fix     │  • Task→file      │  • Completed/     │  • Tool call              │
│    pairs         │    mapping        │    planned        │    logging                │
│  • Decisions     │  • Stack          │  • Auto-update    │  • Analytics              │
│                  │    detection      │    on plan exit   │                           │
│                  │                   │                   │                           │
│  SCOPE:          │  SCOPE:           │  SCOPE:           │  SCOPE:                   │
│  ───────         │  ───────          │  ───────          │  ───────                  │
│  • PROJECT       │  • Per-project    │  • Per-project    │  • All sessions           │
│    (isolated)    │  • .claude/       │  • .claude/       │  • workspace_             │
│  • GLOBAL        │    knowledge-     │    ROADMAP.md     │    project_id             │
│    (shared)      │    tree.json      │                   │    for isolation          │
│                  │                   │                   │                           │
├──────────────────┼───────────────────┼───────────────────┼───────────────────────────┤
│  PERSISTENCE     │  PERSISTENCE      │  PERSISTENCE      │  PERSISTENCE              │
│  ────────────    │  ────────────     │  ────────────     │  ────────────             │
│  Docker:         │  File:            │  File:            │  Cloud:                   │
│  continuous-     │  {project}/       │  {project}/       │  api.braintrust.dev       │
│  claude-postgres │  .claude/         │  ROADMAP.md       │                           │
│  Port 5434       │  knowledge-       │                   │  Local state:             │
│                  │  tree.json        │                   │  ~/.claude/state/         │
│  1024-dim BGE    │                   │                   │  braintrust_sessions/     │
│  embeddings      │  Updated by       │  Updated by       │                           │
│                  │  daemon (2s       │  post-plan        │                           │
│                  │  debounce)        │  hook             │                           │
└──────────────────┴───────────────────┴───────────────────┴───────────────────────────┘
```

## Data Flow

```
SESSION START
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. session-start-docker.mjs → Start PostgreSQL if not running  │
│  2. session-register.mjs → Register in coordination DB          │
│  3. session-start-continuity.mjs → Load handoff ledger          │
│  4. session-start-init-check.mjs → Check project init           │
│  5. session-start-tree-daemon.ps1 → Start knowledge tree daemon │
│  6. session-start-memory-daemon.ps1 → Start memory daemon ◄ NEW │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
DURING SESSION
     │
     ├──▶ User asks implementation question
     │         │
     │         ▼
     │    ┌─────────────────────────────────────────────────────┐
     │    │  pre-tool-knowledge.ts                              │
     │    │  ─────────────────────                              │
     │    │  Reads knowledge-tree.json                          │
     │    │  Injects: directories, entry points, current goals  │
     │    └─────────────────────────────────────────────────────┘
     │
     ├──▶ Claude uses tools (Bash, Edit, Read...)
     │         │
     │         ▼
     │    ┌─────────────────────────────────────────────────────┐
     │    │  braintrust_hooks.py (post_tool_use)                │
     │    │  ──────────────────────────────────                 │
     │    │  Creates span: tool name, input, output, duration   │
     │    │  Includes workspace_project_id for isolation        │
     │    └─────────────────────────────────────────────────────┘
     │
     ├──▶ File changes detected
     │         │
     │         ▼
     │    ┌─────────────────────────────────────────────────────┐
     │    │  tree_daemon.py (watchdog)                          │
     │    │  ─────────────────────────                          │
     │    │  Debounces 2s, regenerates knowledge-tree.json      │
     │    └─────────────────────────────────────────────────────┘
     │
     └──▶ User exits plan mode
              │
              ▼
         ┌─────────────────────────────────────────────────────┐
         │  post-plan-roadmap.ts                               │
         │  ─────────────────────                              │
         │  Parses plan, updates ROADMAP.md goals              │
         └─────────────────────────────────────────────────────┘
     │
     ▼
SESSION END / LEARNING
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  store_learning.py                                              │
│  ─────────────────                                              │
│  • Generates BGE embedding (1024-dim)                           │
│  • Classifies scope (PROJECT vs GLOBAL)                         │
│  • Deduplicates against existing learnings                      │
│  • Stores in PostgreSQL with project_id                         │
└─────────────────────────────────────────────────────────────────┘
```

## Responsibility Matrix

| System | What it knows | When it's used | Isolation |
|--------|---------------|----------------|-----------|
| **Memory** | Past learnings, errors, decisions, patterns | Recall via `/recall` or hooks | `project_id` hash |
| **Knowledge Tree** | File structure, stack, components | Implementation tasks | Per-project JSON |
| **Roadmap** | Goals: current, completed, planned | Planning, progress tracking | Per-project `.md` |
| **Braintrust** | Session traces, tool calls, timing | Debugging, analytics | `workspace_project_id` |

---

## Component Details

### 1. Memory System

**Location:** PostgreSQL container `continuous-claude-postgres` on port 5434

**Schema:**
```sql
CREATE TABLE archival_memory (
    id UUID PRIMARY KEY,
    project_id TEXT,           -- SHA-256 hash (16 chars) of project path
    scope TEXT,                -- 'PROJECT' or 'GLOBAL'
    content TEXT,
    embedding vector(1024),    -- BGE bge-large-en-v1.5 embeddings
    metadata JSONB,
    created_at TIMESTAMPTZ
);
```

**Scripts:**
- `scripts/core/recall_learnings.py` - Semantic search via pgvector
- `scripts/core/store_learning.py` - Store with embeddings + deduplication

**Usage:**
```bash
# Recall
cd ~/.claude && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "auth patterns" --k 5

# Store
cd ~/.claude && PYTHONPATH=. uv run python scripts/core/store_learning.py \
  --session-id "my-session" \
  --type WORKING_SOLUTION \
  --content "Pattern X works for Y" \
  --context "feature development"
```

### 2. Knowledge Tree

**Location:** `{project}/.claude/knowledge-tree.json`

**Scripts:**
- `scripts/core/core/knowledge_tree.py` - Generator
- `scripts/core/core/tree_daemon.py` - File watcher (2s debounce)
- `scripts/core/core/query_tree.py` - Natural language queries

**Hook:** `hooks/src/pre-tool-knowledge.ts` - Injects context before Task tool

**Key files detected:**
- README.md, package.json, pyproject.toml (project info)
- ROADMAP.md (goals)
- docker-compose.yml, Dockerfile (deployment)

### 3. Roadmap

**Location:** `{project}/ROADMAP.md` or `{project}/.claude/ROADMAP.md`

**Hooks:**
| Hook | Trigger | Action |
|------|---------|--------|
| `post-plan-roadmap.ts` | ExitPlanMode | Adds planning session to ROADMAP |
| `roadmap-completion.ts` | TaskUpdate (completed) | Moves current → completed |
| `prd-roadmap-sync.ts` | Write/Edit prd-*.md | Adds PRD to Planned section |
| `prd-roadmap-sync.ts` | Write/Edit tasks-*.md | Updates progress, promotes to Current |

**Format:**
```markdown
# Project Roadmap

## Current
**Feature Name**
- Started: 2026-01-29
- Progress: 12/20 tasks (60%)

## Completed
- [x] Finished feature (2026-01-15)

## Planned
- [ ] Future feature [PRD-002] (high)
```

**PRD/Tasks Integration:**
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ prd-*.md     │────▶│ ROADMAP.md   │────▶│ ROADMAP.md   │
│ (created)    │     │ ## Planned   │     │ ## Completed │
└──────────────┘     └──────────────┘     └──────────────┘
       │                    │                    ▲
       ▼                    ▼                    │
┌──────────────┐     ┌──────────────┐           │
│ tasks-*.md   │────▶│ ROADMAP.md   │───────────┘
│ (progress)   │     │ ## Current   │  (100% complete)
└──────────────┘     │ - Progress   │
                     └──────────────┘
```

### 4. Braintrust

**Location:** Cloud API + local state in `~/.claude/state/braintrust_sessions/`

**Script:** `hooks/braintrust_hooks.py`

**Spans captured:**
- Session root span (workspace, hostname, user)
- Turn spans (user prompts)
- Tool call spans (name, input, output, duration)

**Project isolation:** `workspace_project_id` in span metadata (SHA-256 hash of project path)

---

## Configuration

**Environment (`.env`):**
```bash
DATABASE_URL=postgresql://claude:claude_dev@localhost:5434/continuous_claude
BRAINTRUST_API_KEY=sk-...
TRACE_TO_BRAINTRUST=true
BRAINTRUST_CC_PROJECT=My Project
```

**Docker (`docker/.env`):**
```bash
POSTGRES_PORT=5434
POSTGRES_USER=claude
POSTGRES_PASSWORD=claude_dev
POSTGRES_DB=continuous_claude
```

---

## Fixes Applied (2026-01-29, 2026-01-30)

1. **Import paths fixed:** `scripts.core.db` → `scripts.core.core.db`
2. **Docker port aligned:** Port 5434 in docker/.env
3. **Auto-start hook:** `session-start-docker.ts` starts PostgreSQL on session start
4. **Project isolation:** `workspace_project_id` added to Braintrust spans
5. **Tree daemon optimized:** Debounce increased 500ms → 2000ms
6. **ROADMAP completion hook:** `roadmap-completion.ts` - auto-updates on TaskUpdate
7. **PRD/Tasks sync hook:** `prd-roadmap-sync.ts` - syncs ai-dev-tasks workflow with ROADMAP
8. **Memory daemon auto-start (2026-01-30):** `session-start-memory-daemon.ps1` - starts memory extraction daemon on session start (completes the "Four Pillars" auto-start)

---

## All Registered Hooks

### SessionStart
| Hook | Purpose |
|------|---------|
| `session-start-docker.mjs` | Start PostgreSQL container if not running |
| `session-register.mjs` | Register session in coordination DB |
| `session-start-continuity.mjs` | Load handoff ledger |
| `session-start-init-check.mjs` | Check project initialization |
| `session-start-tree-daemon.ps1` | Start knowledge tree file watcher |
| `session-start-memory-daemon.ps1` | **Auto-start memory extraction daemon** |

### PreToolUse
| Matcher | Hook | Purpose |
|---------|------|---------|
| `Task` | `pre-tool-knowledge.mjs` | Inject knowledge tree context |
| `Task` | `explore-to-scout.mjs` | Route Explore → Scout agent |

### PostToolUse
| Matcher | Hook | Purpose |
|---------|------|---------|
| `Grep\|Read` | `epistemic-reminder.mjs` | Warn about grep-only claims |
| `ExitPlanMode` | `post-plan-roadmap.mjs` | Add planning session to ROADMAP |
| `TaskUpdate` | `roadmap-completion.mjs` | Mark goals complete on task completion |
| `Write\|Edit` | `prd-roadmap-sync.mjs` | Sync PRD/Tasks with ROADMAP |
| `Write\|Edit` | `sync-to-repo.mjs` | Auto-sync ~/.claude to continuous-claude repo |

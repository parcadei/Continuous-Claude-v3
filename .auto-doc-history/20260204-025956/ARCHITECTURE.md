# Continuous Claude v3 - Architecture Guide

## Executive Summary

Continuous Claude v3 is an **agentic AI development environment** built on top of Claude Code. It transforms a single AI assistant into a coordinated system of specialized agents, with automatic context management, semantic memory, and token-efficient code analysis. Think of it as "VS Code + GitHub Copilot, but the AI can delegate to specialist AIs, remember past sessions, and understand code at the AST level."

The system has four main layers: **Skills** (what users can trigger), **Hooks** (automatic behaviors), **Agents** (specialized sub-assistants), and **Infrastructure** (persistence and analysis tools).

---

## Architecture Diagram

```
+-----------------------------------------------------------------------------------+
|                              USER INTERACTION                                      |
|  "help me understand authentication" | "implement feature X" | "debug this bug"   |
+-----------------------------------------------------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
|                           SKILL ACTIVATION LAYER                                   |
|  skill-rules.json -> keyword/intent matching -> skill suggestion/injection         |
+-----------------------------------------------------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
|                               HOOK LAYER                                           |
|                                                                                    |
|  +-------------+    +---------------+    +--------------+    +----------------+   |
|  | SessionStart|    | UserPrompt    |    | PreToolUse   |    | PostToolUse    |   |
|  | - Continuity|    | - Skill inject|    | - Search rtr |    | - Compiler     |   |
|  | - Indexing  |    | - Braintrust  |    | - TLDR inject|    | - Handoff idx  |   |
|  +-------------+    +---------------+    +--------------+    +----------------+   |
|                                                                                    |
|  +-------------+    +---------------+    +--------------+    +----------------+   |
|  | SubagentSt  |    | SubagentStop  |    | Stop         |    | SessionEnd     |   |
|  | - Register  |    | - Continuity  |    | - Coordinator|    | - Cleanup      |   |
|  +-------------+    +---------------+    +--------------+    +----------------+   |
+-----------------------------------------------------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
|                              AGENT LAYER (41 agents)                               |
|                                                                                    |
|  ORCHESTRATORS          IMPLEMENTERS         EXPLORERS          REVIEWERS         |
|  +----------+           +----------+         +----------+       +----------+      |
|  | maestro  |           | kraken   |         | scout    |       | critic   |      |
|  | (opus)   |           | (opus)   |         | (sonnet) |       | (sonnet) |      |
|  | multi-ag |           | TDD impl |         | codebase |       | code     |      |
|  +----------+           +----------+         +----------+       +----------+      |
|                                                                                    |
|  PLANNERS              DEBUGGERS            VALIDATORS         SPECIALIZED        |
|  +----------+          +----------+         +----------+       +----------+       |
|  | architect|          | sleuth   |         | arbiter  |       | aegis    |       |
|  | (opus)   |          | (opus)   |         | (opus)   |       | security |       |
|  | design   |          | debug    |         | testing  |       +----------+       |
|  +----------+          +----------+         +----------+       | phoenix  |       |
|                                                                | refactor |       |
|                                                                +----------+       |
+-----------------------------------------------------------------------------------+
                                        |
                                        v
+-----------------------------------------------------------------------------------+
|                           INFRASTRUCTURE LAYER                                     |
|                                                                                    |
|  +-------------------+  +-------------------+  +-------------------+               |
|  | TLDR-Code 5-Layer |  | PostgreSQL+pgvec  |  | File Persistence  |               |
|  | - AST (structure) |  | - sessions        |  | - thoughts/shared |               |
|  | - Call Graph      |  | - file_claims     |  |   - handoffs/     |               |
|  | - CFG (control)   |  | - archival_memory |  |   - plans/        |               |
|  | - DFG (data flow) |  | - handoffs        |  |   - ledgers/      |               |
|  | - PDG (deps)      |  |                   |  | - .claude/cache/  |               |
|  +-------------------+  +-------------------+  +-------------------+               |
|                                                                                    |
|  +-------------------+  +-------------------+  +-------------------+               |
|  | Symbol Index      |  | Artifact Index    |  | MCP Servers       |               |
|  | /tmp/claude-      |  | (SQLite FTS5)     |  | - Firecrawl       |               |
|  | symbol-index/     |  | - handoffs        |  | - Perplexity      |               |
|  | symbols.json      |  | - plans           |  | - GitHub          |               |
|  | callers.json      |  | - continuity      |  | - AST-grep        |               |
|  +-------------------+  +-------------------+  +-------------------+               |
+-----------------------------------------------------------------------------------+
```

---

## 1. Capability Catalog (What Users Can Do)

Users activate capabilities through **natural language keywords**. No slash commands needed - the system detects intent.

### Planning & Workflow

| Capability | Trigger Keywords | What It Does |
|------------|-----------------|--------------|
| **Create Plan** | "create plan", "plan feature", "design" | Architect agent creates phased implementation plan |
| **Implement Plan** | "implement plan", "execute plan", "follow plan" | Kraken agent executes plan with TDD |
| **Create Handoff** | "create handoff", "done for today", "wrap up" | Saves session state for future pickup |
| **Resume Handoff** | "resume handoff", "continue work", "pick up where" | Restores context from previous session |
| **Continuity Ledger** | "save state", "before compact", "low on context" | Creates checkpoint within session |

### Code Understanding (TLDR-Code)

| Capability | Trigger Keywords | What It Does |
|------------|-----------------|--------------|
| **Call Graph** | "what calls", "who calls", "calls what" | Shows function call relationships |
| **Complexity Analysis** | "how complex", "cyclomatic" | CFG-based complexity metrics |
| **Data Flow** | "where does variable", "what sets" | Tracks variable origins and uses |
| **Program Slicing** | "what affects line", "dependencies" | PDG-based impact analysis |

### Search & Research

| Capability | Trigger Keywords | What It Does |
|------------|-----------------|--------------|
| **Semantic Search** | "recall", "what worked", "past decisions" | Searches archival memory with embeddings |
| **Structural Search** | "ast", "find all calls", "refactor" | AST-grep for code patterns |
| **Text Search** | "grep", "find in code", "search for" | Fast text search via Morph/Grep |
| **Web Research** | "search the web", "look up", "perplexity" | AI-powered web search |
| **Documentation** | "docs", "how to use", "API reference" | Library docs via Nia |

### Code Quality

| Capability | Trigger Keywords | What It Does |
|------------|-----------------|--------------|
| **Quality Check** | "lint", "code quality", "auto-fix" | Qlty CLI with 70+ linters |
| **TDD Workflow** | "implement", "add feature", "fix bug" | Forces test-first development |
| **Debug** | "debug", "investigate", "why is it" | Spawns debug-agent for investigation |

### Git & GitHub

| Capability | Trigger Keywords | What It Does |
|------------|-----------------|--------------|
| **Commit** | "commit", "save changes", "push" | Git commit with user approval |
| **PR Description** | "describe pr", "create pr" | Generates PR description from changes |
| **GitHub Search** | "github", "search repo", "PR" | Searches GitHub via MCP |

### Math & Computation

| Capability | Trigger Keywords | What It Does |
|------------|-----------------|--------------|
| **Math Computation** | "calculate", "solve", "integrate" | SymPy, Z3, Pint computation |
| **Formal Proofs** | "prove", "theorem", "verify" | Lean 4 + Godel-Prover |

---

## 2. Hook Layer (Automatic Behaviors)

Hooks fire automatically at specific lifecycle points. Users don't invoke them directly - they just work.

### PreToolUse Hooks

| Hook | Triggers On | What It Does |
|------|-------------|--------------|
| `path-rules` | Read, Edit, Write | Enforces file access patterns |
| `tldr-read-enforcer` | Read | Intercepts file reads, offers TLDR context instead |
| `smart-search-router` | Grep | Routes to AST-grep/LEANN/Grep based on query type |
| `tldr-context-inject` | Task | Adds code context to subagent prompts |
| `file-claims` | Edit | Tracks which session owns which files |
| `pre-edit-context` | Edit | Injects context before edits |

### PostToolUse Hooks

| Hook | Triggers On | What It Does |
|------|-------------|--------------|
| `pattern-orchestrator` | Task | Manages multi-agent patterns (pipeline, jury, debate) |
| `typescript-preflight` | Edit, Write | Runs TypeScript compiler check |
| `handoff-index` | Write | Indexes handoff documents for search |
| `compiler-in-the-loop` | Write | Validates code changes compile |
| `import-validator` | Edit, Write | Checks import statements are valid |

### Session Lifecycle Hooks

| Hook | Fires When | What It Does |
|------|------------|--------------|
| `session-register` | SessionStart | Registers session in coordination layer |
| `session-start-continuity` | Resume/Compact | Restores continuity ledger |
| `skill-activation-prompt` | UserPromptSubmit | Suggests relevant skills |
| `subagent-start` | SubagentStart | Registers subagent spawn |
| `subagent-stop-continuity` | SubagentStop | Saves subagent state |
| `stop-coordinator` | Stop | Handles graceful shutdown |
| `session-end-cleanup` | SessionEnd | Cleanup and final state save |

---

## 3. Agent Layer

41 specialized agents, each with a defined role, model preference, and tool access.

### Orchestration Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| **maestro** | opus | Multi-agent coordination, pattern selection |
| **kraken** | opus | TDD implementation, checkpointing, resumable work |

### Planning Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| **architect** | opus | Feature design, interface planning, integration design |
| **phoenix** | opus | Refactoring plans, tech debt analysis |
| **pioneer** | opus | Migration planning, framework upgrades |

### Exploration Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| **scout** | sonnet | Codebase exploration, pattern finding |
| **oracle** | opus | External research (web, docs) |
| **pathfinder** | sonnet | Navigation, file location |

### Implementation Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| **spark** | sonnet | Quick fixes, small changes |
| **kraken** | opus | Full TDD implementation |

### Debugging Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| **sleuth** | opus | Debug investigation, root cause analysis |
| **profiler** | opus | Performance analysis |

### Validation Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| **arbiter** | opus | Unit/integration testing |
| **atlas** | opus | E2E testing |
| **validator** | sonnet | Plan validation against precedent |

### Review Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| **critic** | sonnet | Code review |
| **judge** | sonnet | Refactor review |
| **warden** | sonnet | Security review |
| **surveyor** | sonnet | Migration completeness |

### Specialized Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| **aegis** | opus | Security analysis, vulnerability scanning |
| **herald** | sonnet | Release preparation, changelog |
| **scribe** | sonnet | Documentation generation |
| **liaison** | sonnet | Integration/API quality review |

### Agent Output Location

All agents write their output to:
```
.claude/cache/agents/<agent-name>/latest-output.md
```

---

## 4. Infrastructure Layer

### TLDR-Code (5-Layer Code Analysis)

**Install:** `uv tool install llm-tldr` | **Source:** [github.com/parcadei/tldr-code](https://github.com/parcadei/tldr-code)

A token-efficient code understanding system that provides 85% token savings compared to raw file reads.

| Layer | Extractor | What It Provides |
|-------|-----------|------------------|
| **L1: AST** | `ast_extractor.py` | Functions, classes, imports, structure |
| **L2: Call Graph** | `hybrid_extractor.py`, `cross_file_calls.py` | What calls what, cross-file dependencies |
| **L3: CFG** | `cfg_extractor.py` | Control flow, cyclomatic complexity |
| **L4: DFG** | `dfg_extractor.py` | Variable definitions and uses, data flow |
| **L5: PDG** | `pdg_extractor.py` | Program dependencies, backward/forward slicing |

**Supported Languages:** Python, TypeScript, Go, Rust

**API Entry Point:** `tldr/api.py`
```python
from tldr.api import get_relevant_context, query, get_slice
```

### PostgreSQL + pgvector

Schema in `docker/init-schema.sql`

| Table | Purpose |
|-------|---------|
| `sessions` | Cross-terminal awareness and coordination |
| `file_claims` | Cross-terminal file locking |
| `archival_memory` | Long-term learnings with vector embeddings |
| `handoffs` | Session handoffs with embeddings |

**Features:**
- Semantic search via pgvector embeddings (1024-dim BGE)
- Hybrid RRF search (text + vector combined)
- Cross-session coordination

### Artifact Index (SQLite FTS5)

Schema: `opc/scripts/artifact_schema.sql`
Location: `.claude/cache/context-graph/context.db`

| Table | Indexed Content |
|-------|-----------------|
| `handoffs` | Task summary, what worked/failed, key decisions |
| `plans` | Title, overview, approach, phases |
| `continuity` | Goal, state, learnings |
| `queries` | Q&A pairs for compound learning |

**Features:**
- Full-text search with porter stemming
- BM25 ranking with column weights
- Automatic FTS sync via triggers

### File-Based Persistence

```
thoughts/
  shared/
    handoffs/           # Session handoff documents (YAML)
      <session-name>/
        current.md      # Active handoff
        *.yaml          # Historical handoffs
    plans/              # Implementation plans
    ledgers/            # Continuity snapshots
  experiments/          # A/B tests, comparisons
  skill-builds/         # Skill development iterations

.claude/
  cache/
    agents/             # Agent outputs
      <agent>/latest-output.md
    patterns/           # Multi-agent pattern state
      pipeline-*.json
      jury-*.json
    context-graph/      # SQLite artifact index
  hooks/src/            # Hook implementations
  skills/               # Skill definitions
  agents/               # Agent definitions
```

### Symbol Index

Location: `/tmp/claude-symbol-index/`

| File | Content |
|------|---------|
| `symbols.json` | Function/class definitions with location |
| `callers.json` | Who calls each function |

Built by `build_symbol_index.py` on SessionStart.

---

## 5. Key Python Scripts

### Entry Points (User-Callable)

| Script | Purpose |
|--------|---------|
| `recall_learnings.py` | Semantic search of archival memory |
| `store_learning.py` | Store a new learning |
| `observe_agents.py` | Query running agent state |
| `braintrust_analyze.py` | Analyze session logs |
| `artifact_query.py` | Search artifact index |

### Background Services

| Script | Purpose |
|--------|---------|
| `build_symbol_index.py` | Builds symbol index on session start |
| `index_incremental.py` | Incremental artifact indexing |

### Computation Backends

| Script | Purpose |
|--------|---------|
| `sympy_compute.py` | Symbolic math |
| `z3_solve.py` | Constraint solving |
| `pint_compute.py` | Unit conversions |
| `math_router.py` | Routes math queries to backends |

### Hook Launcher

`hook_launcher.py` - Central dispatcher that compiles and runs TypeScript hooks via the `tsc-cache/` directory.

---

## 6. Data Flow Diagrams

### User Request Flow

```
User: "debug the authentication bug"
         |
         v
+-------------------+
| UserPromptSubmit  |  skill-activation-prompt hook fires
+-------------------+
         |
         v (skill suggested: debug-agent)
+-------------------+
| Task Tool         |  spawns debug-agent
+-------------------+
         |
         v
+-------------------+
| PreToolUse:Task   |  tldr-context-inject adds code context
+-------------------+
         |
         v
+-------------------+
| debug-agent runs  |  uses TLDR-code, searches codebase
+-------------------+
         |
         v
+-------------------+
| PostToolUse:Task  |  pattern-orchestrator checks completion
+-------------------+
         |
         v
+-------------------+
| Agent Output      |  .claude/cache/agents/debug-agent/latest-output.md
+-------------------+
```

### Code Context Injection Flow

```
Claude wants to Read file.py
         |
         v
+-------------------+
| PreToolUse:Read   |  tldr-read-enforcer fires
+-------------------+
         |
         v (blocks read, suggests TLDR)
+-------------------+
| TLDR Analysis     |
| L1: AST extract   |
| L2: Call graph    |
| L3: CFG (if func) |
+-------------------+
         |
         v
+-------------------+
| Context Returned  |  95% fewer tokens than raw file
+-------------------+
```

### Search Routing Flow

```
Claude calls Grep("validateToken")
         |
         v
+-------------------+
| PreToolUse:Grep   |  smart-search-router fires
+-------------------+
         |
         v (detects: structural query about function)
+-------------------+
| Route Decision    |
| - Structural? -> AST-grep
| - Semantic?   -> LEANN/Embeddings
| - Literal?    -> Grep (pass through)
+-------------------+
         |
         v (this is structural)
+-------------------+
| Redirect to       |  uses AST-grep for function references
| AST-grep          |
+-------------------+
```

---

## 7. Key Files Reference

### Configuration

| File | Purpose |
|------|---------|
| `.claude/settings.json` | Hook registration, tool configuration |
| `.claude/skills/skill-rules.json` | Skill triggers and keywords |
| `opc/pyproject.toml` | Python dependencies |

### Hook Implementations

| File | Purpose |
|------|---------|
| `.claude/hooks/src/smart-search-router.ts` | Routes searches to best tool |
| `.claude/hooks/src/tldr-context-inject.ts` | Adds TLDR context to agents |
| `.claude/hooks/src/pattern-orchestrator.ts` | Multi-agent pattern management |
| `.claude/hooks/src/session-start-continuity.ts` | Restores session state |
| `.claude/hooks/src/handoff-index.ts` | Indexes handoff documents |

### Agent Definitions

| File | Purpose |
|------|---------|
| `.claude/agents/kraken.md` | TDD implementation agent |
| `.claude/agents/maestro.md` | Multi-agent orchestrator |
| `.claude/agents/architect.md` | Feature planning agent |
| `.claude/agents/scout.md` | Codebase exploration |

### Core Libraries

| File | Purpose |
|------|---------|
| `tldr/api.py` (llm-tldr package) | TLDR-Code public API |
| `opc/scripts/temporal_memory/store_pg.py` | Temporal memory PostgreSQL store |
| `opc/scripts/artifact_index.py` | Artifact index management |

---

## 8. Getting Started

### For Users

1. **Ask naturally** - "help me understand the auth system" triggers appropriate skills/agents
2. **Create plans first** - "create a plan for feature X" before implementing
3. **Use handoffs** - "create handoff" when stopping, "resume handoff" when returning
4. **Trust the routing** - the system picks the right tool (TLDR vs Grep vs AST-grep)

### For Developers

1. **Add skills** in `.claude/skills/<skill-name>/SKILL.md`
2. **Register triggers** in `.claude/skills/skill-rules.json`
3. **Add hooks** in `.claude/hooks/src/*.ts`, register in `.claude/settings.json`
4. **Add agents** in `.claude/agents/<agent>.md`

### Key Invariants

- **Agents write to files, not stdout** - all agent output goes to `.claude/cache/agents/`
- **Hooks are fast** - timeouts are 5-60 seconds
- **Memory is semantic** - use embeddings for recall, not exact match
- **TDD is enforced** - implementation agents write tests first
- **Context is precious** - TLDR saves 85% tokens

---

## 9. Glossary

| Term | Meaning |
|------|---------|
| **Skill** | A capability triggered by keywords in user input |
| **Hook** | Automatic behavior at lifecycle points (PreToolUse, etc.) |
| **Agent** | Specialized sub-assistant spawned via Task tool |
| **TLDR-Code** | Token-efficient code analysis (5 layers) |
| **Handoff** | Document transferring state between sessions |
| **Continuity Ledger** | Checkpoint within a session |
| **Artifact Index** | Full-text searchable index of past work |
| **Temporal Fact** | Fact that evolves over turns (e.g., "current goal") |
| **Pattern** | Multi-agent coordination (pipeline, jury, debate, gencritic) |

---

## 10. TLDR 5-Layer Analysis Results

> Generated via `tldr arch`, `tldr calls`, `tldr dead`, `tldr cfg`, `tldr dfg`

### 10.1 Architectural Layer Detection (L2: Call Graph)

TLDR detected 3 architectural layers based on call patterns:

#### Entry Layer (Controllers/Handlers)
Files that are called from outside but rarely call other internal code.

| Directory | Calls Out | Calls In | Functions | Inferred Layer |
|-----------|-----------|----------|-----------|----------------|
| `scripts/` (root) | 21 | 3 | 1,232 | HIGH (entry) |
| `archive/` | 66 | 6 | 590+ | HIGH (entry, dead code) |
| `temporal_memory/` | 13 | 1 | 55 | HIGH (entry) |

#### Service Layer (Business Logic)
Files that mediate between entry and data layers.

| Directory | Calls Out | Calls In | Functions | Inferred Layer |
|-----------|-----------|----------|-----------|----------------|
| `monitors/` | 1 | 0 | 25 | MIDDLE (service) |

#### Data Layer (Utilities)
Files that provide primitive operations, rarely call other code.

| Directory | Calls Out | Calls In | Functions | Inferred Layer |
|-----------|-----------|----------|-----------|----------------|
| `agentica_patterns/` | 4 | 116 | 251 | LOW (utility) |
| `setup/` | 0 | 4 | 67 | LOW (utility) |
| `sacred_tui/` | 0 | 2 | 11 | LOW (utility) |
| `security/` | 0 | 0 | 4 | LOW (utility) |

### 10.2 Cross-File Call Graph (Key Edges)

Selected high-impact call relationships:

```
math_router.py
  → sympy_compute.py:safe_parse
  → numpy_compute.py:cmd_*
  → scipy_compute.py:cmd_*
  → mpmath_compute.py:cmd_*

temporal_memory/store_pg.py
  → postgres_pool.py:get_connection
  → postgres_pool.py:init_pgvector

memory_service_pg.py
  → postgres_pool.py:get_connection (38 callers total)
  → embedding_service.py:embed

braintrust_hooks.py
  → session_start → get_project_id
  → session_start → get_session_value
  → log → ensure_dirs
```

#### Most Called Functions (Impact Analysis)

| Function | File | Caller Count | Description |
|----------|------|--------------|-------------|
| `get_connection` | `postgres_pool.py` | 38 | Central DB connection pool |
| `math_command` | `math_base.py` | 50+ | Math computation wrapper |
| `parse_array` | `math_base.py` | 30+ | Array parsing for numpy |
| `parse_matrix` | `math_base.py` | 20+ | Matrix parsing for scipy |

### 10.3 Complexity Hot Spots (L3: CFG)

Functions with elevated cyclomatic complexity:

| Function | File | Complexity | Blocks | Reason |
|----------|------|------------|--------|--------|
| `session_start` | `braintrust_hooks.py` | 5 | 13 | Multiple early returns |
| `search_hybrid` | `memory_service_pg.py` | 3 | 6 | Date filter branches |
| `infer_pattern` | `pattern_inference.py` | 12+ | - | Pattern matching logic |
| `main` | `compiler-in-the-loop.ts` | 8+ | - | Lean4 + Loogle integration |
| `main` | `skill-activation-prompt.ts` | 10+ | - | Large skill matching switch |

#### Refactoring Candidates

1. **`skill-activation-prompt.ts:main`** - Extract skill matchers to separate functions
2. **`pattern_inference.py:infer_pattern`** - Use strategy pattern
3. **`braintrust_hooks.py`** - Split session vs span logic

### 10.4 Data Flow Analysis (L4: DFG)

#### Key Data Paths

**PostgreSQL Connection Flow (38 callers):**
```
postgres_pool.py:get_connection()
    ├── memory_service_pg.py (all methods)
    ├── temporal_memory/store_pg.py
    ├── coordination_pg.py
    ├── message_memory.py
    └── populate_temporal_sessions.py
```

**Embedding Pipeline:**
```
Input text
    → embedding_service.py:embed()
        → OpenAI/Local API
            → memory_service_pg.py:store()
                → PostgreSQL (pgvector column)
```

**search_hybrid Data Flow:**
```
Parameters:
    text_query: str
    query_embedding: list[float] (1536 dims)
    limit: int = 10
    text_weight: float = 0.5
    vector_weight: float = 0.5
    start_date, end_date: Optional[datetime]
        │
        ▼
    _pad_embedding() → padded_query
        │
        ▼
    Build SQL conditions (date filters)
        │
        ▼
    Execute hybrid query:
        SELECT ...
        ts_rank(...) * text_weight +
        (1 - embedding <=> query) * vector_weight
        │
        ▼
Output: list[MemoryRecord]
```

### 10.5 Dead Code Analysis

#### Cleanup Completed (2026-01-07)

**Files archived:**
| File | Reason |
|------|--------|
| `offline_search.py` → `archive/` | Duplicate of wizard functionality, only test imports |
| `service_checks.py` → `archive/` | Duplicate of wizard functionality, only test imports |
| `test_mcp_offline.py` → `tests/archive/` | Tests for archived files |

**Functions removed:**
| File | Function | Reason |
|------|----------|--------|
| `braintrust_analyze.py` | `format_duration` | Never called, no tests |
| `secrets_filter.py` | `mask_secret` | Never called, not exported |

**Functions kept (have tests, cross-platform support):**
| File | Function | Reason |
|------|----------|--------|
| `hook_launcher.py` | `expand_path` | Cross-platform path handling, tested |

#### Archive Directory (490+ functions)

The `archive/` directory contains deprecated subsystems:

| File | Status | Note |
|------|--------|------|
| `offline_search.py` | Archived | Duplicate of wizard SQLite fallback |
| `service_checks.py` | Archived | Duplicate of wizard service checks |
| `user_preferences.py` | Dead | Old preference system |
| `websocket_multiplex.py` | Dead | Replaced by coordination_pg |
| `skill_validation.py` | Dead | Moved to hooks |
| `ledger_workflow.py` | Dead | Superseded by continuity hooks |
| `post_tool_use_flywheel.py` | Dead | Never integrated |
| `db_connection.py` | Dead | Replaced by postgres_pool |

### 10.6 Circular Dependencies

**Resolved:** The `claude_scope ↔ unified_scope` circular dependency was eliminated by archiving both modules (2026-01-07). These were Agentica infrastructure modules that were never integrated into production hooks or skills.

No circular dependencies remain in active code.

### 10.7 TLDR-Code Package Structure

**PyPI:** `llm-tldr` | **Source:** [github.com/parcadei/tldr-code](https://github.com/parcadei/tldr-code)

| Module | Layer | Functions | Classes | Purpose |
|--------|-------|-----------|---------|---------|
| `api.py` | API | 20 | 3 | Unified interface |
| `ast_extractor.py` | L1 | 2 | 6 | Python AST extraction |
| `hybrid_extractor.py` | L1 | 1 | 1 | Multi-language AST |
| `cross_file_calls.py` | L2 | 53 | 2 | Call graph building |
| `cfg_extractor.py` | L3 | 7 | 5 | Control flow graphs |
| `dfg_extractor.py` | L4 | 7 | 7 | Data flow analysis |
| `pdg_extractor.py` | L5 | 6 | 4 | Program dependencies |
| `analysis.py` | Util | 9 | 1 | Impact/dead code |
| `cli.py` | CLI | 1 | 0 | Command-line entry |

### 10.8 Hook System Structure

Location: `.claude/hooks/src/`

| Category | Hooks | Purpose |
|----------|-------|---------|
| Session | 4 | Start/end lifecycle |
| Tool Interception | 8 | Enhance tool behavior |
| Subagent | 4 | Agent coordination |
| Patterns | 2 | Multi-agent orchestration |
| Validation | 3 | Code quality gates |

**Key Hook Functions:**

| Hook | Key Functions |
|------|---------------|
| `skill-activation-prompt.ts` | `runPatternInference`, `generateAgenticaOutput` |
| `tldr-context-inject.ts` | `detectIntent`, `getTldrContext`, `extractEntryPoints` |
| `subagent-stop-continuity.ts` | `parseStructuredHandoff`, `createYamlHandoff` |
| `compiler-in-the-loop.ts` | `runLeanCompiler`, `getGoedelSuggestions`, `queryLoogle` |
| `pattern-orchestrator.ts` | `handlePipeline`, `handleJury`, `handleDebate`, `handleGenCritic` |

---

## 11. Summary Statistics

| Metric | Count | Notes |
|--------|-------|-------|
| Python functions | 2,328 | Across all `opc/scripts/` |
| TypeScript hooks | 34 | Active in `.claude/hooks/src/` |
| Skills | 123 | In `.claude/skills/` |
| Agents | 41 | Defined in system prompt |
| Tests | 265+ | TLDR-code alone |
| Entry layer functions | 1,057 | Called from outside |
| Leaf functions | 729 | Utility/helper code |
| Dead functions | 4 active, 43 archived | Most dead code now in archive/ |
| Circular dependencies | 0 | Resolved by archiving scope modules |
| get_connection callers | 38 | Most called internal function |

---

*This architecture document is generated by TLDR 5-layer analysis. Token cost: ~5,000 (vs ~50,000 raw files = 90% savings).*

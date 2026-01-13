# Continuous-Claude-v3: Master Fix Plan

**Created:** 2026-01-11
**Based On:** README_VS_REALITY_AUDIT.md
**Agents Used:** 15 (3 batches of 5, 2 passes)

---

## Executive Summary

This plan addresses all discrepancies found between README claims and codebase reality.

| Priority | Issues | Effort |
|----------|--------|--------|
| **Critical** | 4 | 8-10 weeks |
| **High** | 6 | 2-3 weeks |
| **Medium** | 4 | 1-2 weeks |
| **Low** | 5 | 1 day |

---

## Critical Issues (Must Fix)

### Issue #1: TLDR 5-Layer Code Analysis - DOES NOT EXIST

**Status:** Documentation exists, implementation doesn't
**Affected Lines:** 24, 228-230, 621-688, 688, 1055

**Recommended Solution:** Build custom implementation using existing tools

**Implementation Plan:**

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1-2 | L1 (AST) + L2 (Call Graph) | AST parser, call graph, basic CLI |
| 3 | L3 (CFG) + Complexity | Control flow, radon integration |
| 4 | Semantic Search | sentence-transformers, FAISS index |
| 5 | Testing + Integration | Hook integration, docs |

**Required Dependencies:**
```bash
uv pip install tree-sitter tree-sitter-languages networkx faiss-cpu
```

**Directory Structure to Create:**
```
opc/packages/tldr-code/
├── tldr/
│   ├── cli.py              # 22 CLI commands
│   ├── core/
│   │   ├── ast_parser.py   # L1
│   │   ├── call_graph.py   # L2
│   │   ├── cfg.py          # L3
│   │   ├── dfg.py          # L4
│   │   └── pdg.py          # L5
│   ├── semantic/
│   │   ├── embeddings.py
│   │   └── search.py
│   └── cache/
├── tests/
├── pyproject.toml
└── README.md
```

**Immediate Action:** Update README line 688 to remove non-existent path reference

---

### Issue #2: `/build` Skill - MISSING

**Status:** RESOLVED
**Affected Lines:** 127, 416, 433-444, 909-923

**Implementation Plan:**

| Phase | Action | Files |
|-------|--------|-------|
| 1 | Create skill directory | `~/.claude/skills/build/` |
| 2 | Write SKILL.md | Full documentation with modes |
| 3 | Register triggers | Add to `skill-rules.json` |
| 4 | Update workflow-router | Change Build goal to delegate to /build |

**SKILL.md Structure:**
```markdown
# /build - Feature Development

## Modes

| Mode | Chain | Use Case |
|------|-------|----------|
| `greenfield` | discovery → plan → validate → implement → test → commit | New feature |
| `brownfield` | onboard → scout → plan → validate → implement → test | Existing codebase |
| `tdd` | plan → test-first → implement → test | Test-driven |
| `refactor` | impact → plan → TDD → implement | Safe refactoring |

## Usage

/build greenfield "user authentication"
build brownfield --skip-discovery "add payments"
build tdd "add caching layer"
```

**Effort:** 1-2 days

---

### Issue #3: Docker Credentials MISMATCH

**Status:** docker-compose.yml has different credentials than running container
**Affected Files:** `opc/docker-compose.yml`, `opc/.env`

**Current State:**
| Setting | docker-compose.yml | Running Container | .env |
|---------|-------------------|-------------------|------|
| User | `opc` | `claude` | `claude` |
| Password | `opc_dev_password` | `claude_dev` | `claude_dev` |
| Database | `opc` | `continuous_claude` | `continuous_claude` |
| Container | `opc-postgres` | `continuous-claude-postgres` | - |

**Fix Commands:**

```bash
# 1. Backup current database
docker exec continuous-claude-postgres pg_dump -U claude continuous_claude > ~/backup.sql

# 2. Stop and remove current container (volume preserved)
docker stop continuous-claude-postgres && docker rm continuous-claude-postgres

# 3. Update docker-compose.yml with correct values
# See "Files to Update" below

# 4. Start via docker-compose
cd /Users/grantray/Github/Continuous-Claude-v3/opc && docker-compose up -d postgres

# 5. Verify
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c "SELECT COUNT(*) FROM sessions;"
```

**Files to Update:**

`opc/docker-compose.yml` lines 8, 10-12, 19:
```yaml
container_name: continuous-claude-postgres
environment:
  POSTGRES_USER: claude
  POSTGRES_PASSWORD: claude_dev
  POSTGRES_DB: continuous_claude
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U claude -d continuous_claude"]
```

**Effort:** 30 minutes

---

### Issue #4: MCP Scripts - Need runtime.harness

**Status:** Scripts work but require `uv run python -m runtime.harness`
**Affected Scripts:**
- `scripts/mcp/github_search.py`
- `scripts/mcp/morph_search.py`
- `scripts/mcp/morph_apply.py`
- `scripts/qlty_check.py`
- `scripts/ast_grep_find.py`

**Fix:** Scripts are actually correct, just need proper invocation:

```bash
# Correct usage (via harness)
uv run python -m runtime.harness scripts/mcp/github_search.py --type code --query "auth"

# Standalone scripts (work directly)
uv run python scripts/mcp/firecrawl_scrape.py --search "query"
uv run python scripts/mcp/nia_docs.py search universal "query"
```

**Action:** Update any documentation showing incorrect usage

**Effort:** 10 minutes (verify scripts are correct)

---

## High Priority Issues

### Issue #5: Redis Container - NOT RUNNING

**Status:** Container created but not started

**Fix Commands:**
```bash
# Stop local Redis if running on port 6379
kill $(lsof -t -i :6379) 2>/dev/null || true

# Start Docker Redis
docker start opc-redis

# Verify
docker exec opc-redis redis-cli ping
```

**Effort:** 5 minutes

---

### Issue #6: Math Path Mismatch

**Status:** RESOLVED
**Affected File:** `.claude/skills/math-unified/SKILL.md`

**Files to Fix:**
| File | Line | Change |
|------|------|--------|
| `.claude/skills/math-unified/SKILL.md` | 34, 86, 99, 108, 157, 164, 171, 178 | `.claude/scripts/math/` → `opc/scripts/mathlib/` |
| `opc/scripts/mathlib/mpmath_compute.py` | 186 | Fix import path |
| `opc/scripts/mathlib/scipy_compute.py` | 37 | Fix import path |
| `opc/scripts/mathlib/numpy_compute.py` | 17 | Fix import path |
| `opc/scripts/mathlib/sympy_baseline_validation.py` | 27 | Fix import path |
| `opc/scripts/setup/claude_integration.py` | 500 | Fix path |

**Effort:** 30 minutes

---

### Issue #7: Directory Structure - README Out of Date

**Status:** README claims non-existent paths

**Files to Update:**

| README Line | Current | Change To |
|-------------|---------|-----------|
| 688 | `opc/packages/tldr-code/` | `docs/tools/tldr.md` |
| 1054-1055 | `packages/tldr-code/` | Remove |
| 1059-1060 | `opc/docker/init-schema.sql` | `opc/init-db.sql` |

**Complete Directory Section Replace (Lines 1040-1067):**
```diff
 continuous-claude/
 ├── .claude/
 │   ├── agents/           # 32 specialized AI agents
 │   ├── hooks/            # 30 lifecycle hooks
 │   │   ├── src/          # TypeScript source
 │   │   └── dist/         # Compiled JavaScript
 │   ├── skills/           # 104 modular capabilities
 │   ├── rules/            # System policies
-│   ├── scripts/          # Python utilities
+│   ├── scripts/          # Python utilities (global, 8 files)
 │   └── settings.json     # Hook configuration
 ├── opc/
-│   ├── packages/
-│   │   └── tldr-code/    # 5-layer code analysis
 │   ├── scripts/
 │   │   ├── setup/        # Wizard, Docker, integration
 │   │   └── core/         # recall_learnings, store_learning
-│   └── docker/
-│       └── init-schema.sql  # 4-table PostgreSQL schema
+│   ├── init-db.sql       # Database schema
+│   └── pyproject.toml
+├── docker/
+│   └── init-schema.sql   # Docker config
+├── proofs/               # Lean4 formal proofs
 └── docs/                 # Documentation
```

**Effort:** 1 hour

---

### Issue #8: Looge - Wrong Path

**Status:** Installed but looks for script in wrong location

**Fix Command:**
```bash
cp /Users/grantray/Github/Continuous-Claude-v3/opc/scripts/loogle_server.py /Users/grantray/.local/bin/loogle_server.py
```

**Also Fix Documentation:**
| File | Change |
|------|--------|
| `.claude/skills/loogle-search/SKILL.md` | `~/tools/loogle` → `~/.local/share/loogle` |
| `.claude/skills/prove/SKILL.md` | `~/tools/loogle` → `~/.local/share/loogle` |

**Effort:** 10 minutes

---

### Issue #9: Skills Count - 109 vs 104

**Status:** README claims 109, actual is 104

**Files to Update:**
| File | Line | Change |
|------|------|--------|
| README.md | 7 | `Skills-109-green.svg` → `Skills-104-green.svg` |
| README.md | 21 | `Skills (109)` → `Skills (104)` |
| README.md | 49 | "109 skills" → "104 skills" |
| README.md | 187 | "109 skills" → "104 skills" |
| README.md | 222 | Skills (109) → Skills (104) |
| README.md | 973 | Skills (109) → Skills (104) |
| README.md | 1049 | "109 modular capabilities" → "104" |

**Optional:** Add 2 missing skills:
- `formalize` - Formalize math for Lean4
- `dependency-preflight` - Check dependencies

**Effort:** 15 minutes (just update README)

---

### Issue #10: Thoughts Directory - Missing

**Status:** RESOLVED

**Options:**
1. Create directory: `mkdir -p thoughts/ledgers thoughts/shared/handoffs thoughts/shared/plans`
2. Update README to use actual storage location (`.claude/hooks/dist/` patterns)

**Recommendation:** Create directory for continuity system

**Effort:** 5 minutes

---

## Medium Priority Issues

### Issue #11: Hooks Count - 30 vs 64

**Status:** README claims 30, actual is 64 compiled

**Fix:** This is actually fine - README counts 30 bash wrappers, 64 compiled hooks exist

**Action:** Update README to clarify: "30 configurable hooks, 64 total"

**Effort:** 10 minutes

---

### Issue #12: Agents Count - 32 vs 48

**Status:** README claims 32, 48 files exist

**Analysis:**
- 32 .md documentation files (matches README)
- 16 .json config files (extra, not counted)

**Fix:** No action needed - README is accurate

**Effort:** 5 minutes (verify)

---

### Issue #13: GitHub Username

**Status:** README uses `parcadei` in URLs

**Action:** Verify actual repo owner and update if needed

**Lines:** 170, 944, 1107

**Effort:** 5 minutes

---

### Issue #14: Star History Link

**Status:** Line 1107 references v2 repo

**Fix:** Update to v3 repo or remove

**Effort:** 5 minutes

---

## Low Priority Issues

### Issue #15: init-db.sql Location

**Status:** RESOLVED

**Fix:** Update README line 1059-1060

**Effort:** 5 minutes

---

### Issue #16: MCP Scripts Documentation

**Status:** Some scripts mention `runtime.harness` incorrectly

**Fix:** Update script docstrings to show correct usage

**Effort:** 10 minutes

---

### Issue #17: qlty-check Works

**Status:** Was reported broken, now works via harness

**Fix:** Document correct usage

**Effort:** 5 minutes

---

## Implementation Order

### Phase 1: Quick Wins (Day 1)
1. Fix skills count (README updates)
2. Fix directory structure (README updates)
3. Start Redis container
4. Copy Looge script
5. Fix math paths

### Phase 2: Critical Fixes (Week 1-2)
1. Implement `/build` skill
2. Fix Docker credentials
3. Update TLDR documentation

### Phase 3: Major Implementation (Weeks 3-16)
1. Build TLDR 5-layer analysis (if decided)
2. Add missing skills
3. Complete documentation updates

---

## Files Modified Summary

| Category | Files | Effort |
|----------|-------|--------|
| README updates | 1 file (many lines) | 2 hours |
| Docker config | 1 file | 30 min |
| Skills | 3-5 files | 1-2 days |
| Math paths | 6 files | 30 min |
| Documentation | 5-10 files | 1 hour |
| TLDR implementation | 20+ files | 16 weeks (optional) |

---

## Verification Commands

After fixes, run:

```bash
# Verify Redis
docker exec opc-redis redis-cli ping
redis-cli ping

# Verify PostgreSQL
docker exec continuous-claude-postgres psql -U claude -d continuous_claude -c "SELECT 1;"

# Verify skills count
ls ~/.claude/skills/*/SKILL.md | wc -l
# Should show 104

# Verify /build skill exists
ls ~/.claude/skills/build/SKILL.md

# Verify math works
cd opc && uv run python scripts/mathlib/sympy_compute.py solve "x**2 - 4 = 0" --var x

# Verify MCP scripts work
uv run python -m runtime.harness scripts/mcp/github_search.py --type code --query "test" --limit 1

# Verify Looge
loogle-search "theorem"
```

---

## Risk Assessment

| Issue | Risk Level | Mitigation |
|-------|------------|------------|
| Docker credentials | HIGH | Backup before migration |
| TLDR implementation | HIGH | Option B (existing tools) reduces risk |
| Redis port conflict | MEDIUM | Stop local Redis first |
| Skills count | LOW | README update only |

---

## Success Criteria

- [ ] README accurately reflects codebase
- [ ] All skills documented exist
- [ ] All documented commands work
- [ ] PostgreSQL credentials consistent
- [ ] Redis running
- [ ] Math skills work correctly
- [ ] MCP tools work via harness
- [ ] Looge theorem search works

---

*Plan generated by 15 parallel Scout agents across 2 passes.*

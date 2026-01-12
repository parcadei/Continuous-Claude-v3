# README vs Reality: Comprehensive Discrepancy Audit

**Audit Date:** 2026-01-11
**Audited By:** 10+ Parallel Scout Agents (2 passes)
**README Version:** Current main branch

---

## Executive Summary

| Category | README Claim | Actual | Accuracy |
|----------|--------------|--------|----------|
| **Skills** | 109 | 107 | 98.2% |
| **Agents** | 32 | 48 files | 150% (over) |
| **Hooks** | 30 | 64 compiled / 30 wrappers | Misleading |
| **Math System** | 6 libraries + Lean4 | 7 libs work, Looge broken | 85% |
| **Memory System** | 4 tables + full-featured | ✓ Accurate | 100% |
| **TLDR System** | 5-layer analysis + daemon | ✗ DOES NOT EXIST | 0% |
| **Workflows** | 7 commands | 6/7 (build missing) | 86% |
| **Directory Structure** | Claimed structure | 6 major discrepancies | 60% |
| **Docker Setup** | Working stack | Partial (Redis down) | 70% |

**Overall Accuracy: ~65%** - The README contains significant exaggerations and missing implementations.

---

## Critical Discrepancies (Must Read)

### 1. TLDR Code Analysis - DOES NOT EXIST ⚠️ CRITICAL

**README Claims (lines 621-688):**
- 5-layer code analysis (AST, Call Graph, CFG, DFG, PDG)
- `tldr tree`, `tldr structure`, `tldr search`, `tldr context`, `tldr cfg`, `tldr dfg`, `tldr slice`, `tldr impact`, `tldr dead`, `tldr arch` commands
- `tldr daemon semantic` for natural language queries
- 95% token savings claim
- Semantic index in `.tldr/` directory

**Reality:**
- The `tldr` command IS installed but it's **tldr-pages v1.6.1** (cheat sheets for CLI commands)
- `packages/tldr-code/` directory **DOES NOT EXIST**
- All scripts that try to import from `tldr.api` fail silently
- No 5-layer analysis, no daemon, no semantic index

**Verdict:** The entire TLDR code analysis system described is **fictional documentation**.

---

### 2. `/build` Skill - MISSING ⚠️ CRITICAL

**README Claims (lines 909-922):**
- `/build greenfield "user dashboard"`
- `/build brownfield "feature"`
- `/build tdd "feature"`
- `/build refactor "feature"`
- Chain: discovery → plan → validate → implement → commit → PR

**Reality:**
- No `build/` skill exists in `~/.claude/skills/`
- `workflow-router` handles build goals by directly spawning `kraken` agent
- No separate `/build` workflow implementation

**Verdict:** The entire `/build` workflow section describes functionality that **doesn't exist**.

---

### 3. Credentials Mismatch - CRITICAL

**README Claims:**
- Docker Compose credentials work out of the box

**Reality:**
| Setting | docker-compose.yml | .env (actual) |
|---------|-------------------|---------------|
| User | `opc` | `claude` |
| Password | `opc_dev_password` | `claude_dev` |
| Database | `opc` | `continuous_claude` |
| Container | `opc-postgres` | `continuous-claude-postgres` |

The running container uses different credentials than what docker-compose.yml defines.

---

### 4. Directory Structure - 6 Major Discrepancies

**README Claims (lines 1040-1067):**
```
continuous-claude/
├── .claude/scripts/          # Python utilities
├── opc/packages/tldr-code/   # 5-layer code analysis
├── opc/docker/init-schema.sql
├── thoughts/ledgers/
├── thoughts/shared/handoffs/
└── thoughts/shared/plans/
```

**Reality:**
- `.claude/scripts/` - **DOES NOT EXIST**
- `opc/packages/tldr-code/` - **DOES NOT EXIST**
- `opc/docker/init-schema.sql` - **DOES NOT EXIST** (actual file is `opc/init-db.sql`)
- `thoughts/` directory - **DOES NOT EXIST**

**Unclaimed but exists:**
- `docker/` at root
- `proofs/` directory
- `CLAUDE_CODE_AUDIT_REPORT.md`

---

## Detailed Section-by-Section Analysis

### Skills System (98.2% Accurate)

| Metric | README | Actual | Status |
|--------|--------|--------|--------|
| Skills count | 109 | 107 | **-2 skills** |
| Skills badge | "Skills-109-green.svg" | 107 | Inaccurate |

**Missing skills:** 2 skills from the claimed 109 are not present.

**Verdict:** Minor inaccuracy (2 skills).

---

### Agents System (150% - Overclaimed)

| Metric | README | Actual | Status |
|--------|--------|--------|--------|
| Agent count | 32 | 48 files | **+16 files** |

**Reality:**
- 32 .md documentation files (matches claim)
- 16 .json configuration files (not claimed)

**Undocumented agents:**
- `context-query-agent` - Has .md but not in category breakdown
- `sentinel`, `warden` - Have .json but no .md docs

**Verdict:** Documentation undercounts actual agents (more exist than claimed).

---

### Hooks System (Misleading)

| Metric | README Claims | Actual | Status |
|--------|---------------|--------|--------|
| Hook count | 30 | 64 compiled / 30 wrappers | **Misleading** |

**Reality:**
- 30 bash wrappers (what README counts)
- 64 compiled .mjs files (actual implementation)
- Several `.sh` files are utilities, not hooks (`build.sh`, `persist-project-dir.sh`, `session-symbol-index.sh`)

**Verdict:** README understates actual hook complexity by 100%+.

---

### Math System (85% Accurate)

| Feature | README | Reality | Status |
|---------|--------|---------|--------|
| SymPy | ✓ Works | ✓ Works | Accurate |
| Z3 | ✓ Works | ✓ Works | Accurate |
| Pint | ✓ Works | ✓ Works | Accurate |
| Shapely | ✓ Works | ✓ Works | Accurate |
| NumPy | ✓ Claimed | Import issue | Broken |
| SciPy | ✓ Claimed | Import issue | Broken |
| mpmath | ✓ Claimed | Import issue | Broken |
| Lean4 | ✓ Works | v4.26.0 installed | Accurate |
| Loogle | ✓ Works | Broken (path issue) | Broken |
| Mathlib | ✓ Claimed | Not verified | Unknown |

**Path Issues:**
- README skill SKILL.md references `opc/scripts/math/` (doesn't exist)
- Actual path is `opc/scripts/mathlib/`

**Verdict:** Core math works, but some paths broken and Looge is non-functional.

---

### Memory System (100% Accurate) ✅

| Feature | README | Reality | Status |
|---------|--------|---------|--------|
| PostgreSQL + pgvector | ✓ | ✓ Works | Accurate |
| 4 tables | ✓ | ✓ All exist | Accurate |
| recall_learnings.py | ✓ | ✓ Works | Accurate |
| store_learning.py | ✓ | ✓ Works | Accurate |
| memory-awareness hook | ✓ | ✓ Exists | Accurate |

**Verdict:** The only section that is 100% accurate.

---

### Workflows (86% Accurate)

| Workflow | README | Reality | Status |
|----------|--------|---------|--------|
| `/workflow` | ✓ | ✓ Exists | Accurate |
| `/fix` | ✓ | ✓ Exists | Accurate |
| `/build` | ✓ | ✗ MISSING | **Critical** |
| `/tdd` | ✓ | ✓ Exists | Accurate |
| `/refactor` | ✓ | ✓ Exists | Accurate |
| `/premortem` | ✓ | ✓ Exists | Accurate |
| `/explore` | ✓ | ✓ Exists | Accurate |

**Verdict:** `/build` is missing, everything else works.

---

### Docker & Setup (70% Accurate)

| Feature | README | Reality | Status |
|---------|--------|---------|--------|
| docker-compose.yml | ✓ | ✓ Exists | Accurate |
| init-db.sql | ✓ | ✓ Exists (renamed) | Minor |
| Wizard (12 steps) | ✓ | ✓ Works | Accurate |
| PostgreSQL | ✓ | ✓ Running | Accurate |
| Redis | ✓ Claimed | ✗ Not running | Broken |
| Credentials | ✓ Claimed | ✗ Mismatch | Critical |

**Verdict:** Core works but Redis down and credentials misaligned.

---

### Scripts & Commands (Partial)

| Script | README | Reality | Status |
|--------|--------|---------|--------|
| recall_learnings.py | ✓ Mentioned | ✓ Works | Accurate |
| store_learning.py | ✓ Mentioned | ✓ Works | Accurate |
| MCP tools | ✓ Mentioned | 5/10 work | Broken |
| qlty-check | ✓ Mentioned | ✗ Import error | Broken |

**MCP Broken Scripts (import 'runtime' module missing):**
- github_search.py
- firecrawl_scrape.py
- morph_search.py
- morph_apply.py
- nia_docs.py
- qlty_check.py
- ast_grep_find.py

**Verdict:** Core scripts work, MCP tools need `runtime/` module.

---

## Summary Table: All Discrepancies

| # | Item | README Says | Reality | Severity |
|---|------|-------------|---------|----------|
| 1 | TLDR 5-layer analysis | Exists | DOES NOT EXIST | Critical |
| 2 | TLDR commands | 22 CLI commands | tldr-pages (cheat sheets) | Critical |
| 3 | `/build` skill | Exists | MISSING | Critical |
| 4 | Credentials | Match | MISMATCHED | Critical |
| 5 | Directory structure | .claude/scripts/ | DOES NOT EXIST | High |
| 6 | Directory structure | opc/packages/tldr-code/ | DOES NOT EXIST | High |
| 7 | Directory structure | thoughts/ | DOES NOT EXIST | High |
| 8 | Redis | Part of stack | NOT RUNNING | Medium |
| 9 | Skills count | 109 | 107 | Low |
| 10 | Agents count | 32 | 48 files | Low |
| 11 | Hooks count | 30 | 64 compiled | Low |
| 12 | Loogle | Works | Broken (path) | Medium |
| 13 | NumPy/SciPy/mpmath | Works | Import issues | Medium |
| 14 | MCP tools | Work | Need runtime module | Medium |
| 15 | init-schema.sql location | opc/docker/ | opc/ (renamed) | Low |

---

## Recommendations

### Immediate (Critical)
1. **Fix or remove TLDR section** - Either implement the 5-layer analysis or remove the documentation
2. **Add `/build` skill** - Or clarify that workflow-router handles builds directly
3. **Fix credentials** - Align docker-compose.yml with .env

### Short-Term
4. **Fix directory structure claims** - Update README to match reality
5. **Start Redis container** - `docker start opc-redis`
6. **Fix MCP runtime module** - Install or document the runtime dependency
7. **Fix math import paths** - Update SKILL.md to point to `mathlib/`

### Long-Term
8. **Verify Mathlib installation** for `/prove` skill
9. **Fix or remove Loogle** - Install properly or update docs
10. **Add tests for all scripts** - Prevent regressions

---

## Files Referenced in This Report

| Path | Purpose |
|------|---------|
| `README.md` | Source of claims |
| `~/.claude/skills/` | Installed skills |
| `~/.claude/agents/` | Installed agents |
| `~/.claude/hooks/` | Installed hooks |
| `opc/scripts/` | Python scripts |
| `opc/docker-compose.yml` | Docker configuration |
| `opc/init-db.sql` | Database schema |
| `opc/scripts/setup/wizard.py` | Setup wizard |

---

*Audit completed by multi-agent scout team (10+ parallel agents, 2 passes).*

---
name: system_overview
description: Show users how Continuous Claude works - hooks, memory, and coordination
allowed-tools: [Bash, Read]
---

# System Overview

Show users how Continuous Claude works - the opinionated setup with hooks, memory, and coordination.

## When to Use

- User asks "how does this work?"
- User asks "what can you remember?"
- User asks "what's different about this setup?"
- User runs `/system_overview`

## Response

```
CONTINUOUS CLAUDE SYSTEM OVERVIEW
=================================

MEMORY LAYER (PostgreSQL + pgvector)
------------------------------------
- 78,000+ temporal facts from past sessions
- Learnings extracted automatically at session end
- Semantic search with embeddings

RECALL: uv run python opc/scripts/recall_temporal_facts.py --query "your topic"

HOOKS (9 event types registered)
--------------------------------
SessionStart    → Load continuity ledger, rebuild symbol index
UserPromptSubmit → Skill activation check, context injection
PreToolUse      → Smart search routing (Grep → TLDR for code)
PostToolUse     → File claims, compiler feedback
PreCompact      → Save state before context compaction
Stop            → Extract learnings, create handoffs
SubagentStart   → Register spawned agents
SubagentStop    → Coordination, handoff creation
SessionEnd      → Cleanup

CONTINUITY SYSTEM
-----------------
Ledger:   thoughts/ledgers/CONTINUITY_CLAUDE-{session}.md
Handoffs: thoughts/shared/handoffs/{session}/*.yaml

Commands:
  /resume_handoff <path>  - Continue from handoff
  /create_handoff         - Create snapshot for transfer

TLDR CODE INTELLIGENCE
----------------------
5-layer analysis: AST → Call Graph → CFG → DFG → PDG
95% token savings vs reading raw files
Auto-intercepts Grep for .py/.ts/.go/.rs files

Pre-built index: /tmp/claude-symbol-index/symbols.json

SETUP
-----
Run: uv run python opc/scripts/setup/wizard.py

Options:
  [1] SQLite only (simple, offline)
  [2] PostgreSQL + pgvector (semantic search)
```

## Key Files

| Component | Location |
|-----------|----------|
| Hook registration | `.claude/settings.json` |
| Hook implementations | `.claude/hooks/src/*.ts` |
| Rules (auto-injected) | `.claude/rules/*.md` |
| Skills | `.claude/skills/*/SKILL.md` |
| Setup wizard | `opc/scripts/setup/wizard.py` |
| Recall script | `opc/scripts/recall_temporal_facts.py` |
| Store learning | `opc/scripts/core/store_learning.py` |
| Symbol index builder | `opc/scripts/build_symbol_index.py` |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `CONTINUOUS_CLAUDE_DB_URL` | PostgreSQL connection |
| `VOYAGE_API_KEY` | Embeddings (optional) |
| `BRAINTRUST_API_KEY` | Tracing (optional) |
| `CLAUDE_PROJECT_DIR` | Auto-set by Claude Code |

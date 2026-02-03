# PageIndex Search Skill

Tree-based RAG for large markdown documents using LLM reasoning.

## Overview

PageIndex uses hierarchical tree indexes + LLM reasoning (98.7% accuracy) instead of vector similarity (~50%). Best for structured documents like ROADMAPs, architecture docs, and READMEs.

## When to Use

| Document Type | Use PageIndex? |
|---------------|----------------|
| ROADMAP.md | ✅ Yes - hierarchical goals |
| ARCHITECTURE.md | ✅ Yes - structured sections |
| Large READMEs | ✅ Yes - organized content |
| Session learnings | ❌ No - use vector memory |
| Code patterns | ❌ No - use vector memory |

## Quick Commands

```bash
# Generate tree index
cd $CLAUDE_OPC_DIR && PYTHONPATH=. uv run python scripts/pageindex/cli/pageindex_cli.py generate ROADMAP.md

# Search indexed documents
cd $CLAUDE_OPC_DIR && PYTHONPATH=. uv run python scripts/pageindex/cli/pageindex_cli.py search "current goals"

# List indexed documents
cd $CLAUDE_OPC_DIR && PYTHONPATH=. uv run python scripts/pageindex/cli/pageindex_cli.py list

# Show tree structure
cd $CLAUDE_OPC_DIR && PYTHONPATH=. uv run python scripts/pageindex/cli/pageindex_cli.py show ROADMAP.md
```

## Integration with /recall

```bash
# PageIndex-only search
cd $CLAUDE_OPC_DIR && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "roadmap status" --pageindex

# Hybrid search (vector + PageIndex)
cd $CLAUDE_OPC_DIR && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "authentication" --hybrid
```

## How It Works

1. **Index Generation**: Parses markdown headers into tree structure
2. **Storage**: Tree stored in PostgreSQL `pageindex_trees` table
3. **Search**: LLM reasons over tree outline to find relevant nodes
4. **Results**: Returns node content with line numbers and relevance explanation

## Architecture

```
Query
  │
  ▼
┌─────────────────┐
│  Tree Outline   │  (titles only, ~500 tokens)
│  [0001] Intro   │
│  [0002] Goals   │
│    [0003] Q1    │
│    [0004] Q2    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  LLM Reasoning  │  Claude analyzes structure
│  "Which nodes   │
│   are relevant?"│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Node Retrieval │  Fetch full content for matched nodes
│  [0003] Q1 text │
│  [0004] Q2 text │
└─────────────────┘
```

## Database Table

```sql
CREATE TABLE pageindex_trees (
    id UUID PRIMARY KEY,
    project_id TEXT NOT NULL,
    doc_path TEXT NOT NULL,
    doc_type TEXT,  -- ROADMAP, DOCUMENTATION, etc.
    tree_structure JSONB NOT NULL,
    doc_hash TEXT,  -- For change detection
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    UNIQUE(project_id, doc_path)
);
```

## Best Practices

1. **Index large docs**: Any markdown >1000 lines benefits from tree indexing
2. **Rebuild on change**: Use `pageindex rebuild` after major doc updates
3. **Use hybrid for mixed queries**: Combine PageIndex + vector for comprehensive search
4. **Check doc_hash**: Avoid redundant reindexing of unchanged files

## Comparison: Vector vs PageIndex

| Aspect | Vector Memory | PageIndex |
|--------|---------------|-----------|
| **Best for** | Code patterns, learnings | Structured docs |
| **Accuracy** | ~50% (similarity) | 98.7% (reasoning) |
| **Speed** | Fast (~100ms) | Slower (~2s LLM call) |
| **Token cost** | Embedding only | LLM inference |
| **Structure** | Flat chunks | Hierarchical |

## Troubleshooting

**No index found**: Run `pageindex generate <file>` first
**Outdated results**: Run `pageindex rebuild --force`
**LLM errors**: Check Claude Code CLI is available on PATH

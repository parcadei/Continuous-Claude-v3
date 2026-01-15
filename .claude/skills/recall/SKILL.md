---
name: recall
description: Query semantic memory for relevant learnings from past sessions
allowed-tools: [Bash, Read]
---

# Recall - Semantic Memory Retrieval

Query the memory system for relevant learnings from past sessions.

## Usage

```
/recall <query>
```

## Examples

```
/recall hook development patterns
/recall wizard installation
/recall TypeScript errors
```

## What It Does

1. Runs semantic search against stored learnings (PostgreSQL + BGE embeddings)
2. Returns top 5 results with full content
3. Shows learning type, confidence, and session context

## Execution

When this skill is invoked, run:

```bash
cd $CLAUDE_OPC_DIR && PYTHONPATH=. uv run python scripts/core/recall_learnings.py --query "<ARGS>" --k 5
```

Where `<ARGS>` is the query provided by the user.

## Output Format

Present results as:

```
## Memory Recall: "<query>"

### 1. [TYPE] (confidence: high, id: abc123)
<full content>

### 2. [TYPE] (confidence: medium, id: def456)
<full content>
```

## Options

The user can specify options after the query:

- `--k N` - Return N results (default: 5)
- `--vector-only` - Use pure vector search (higher precision)
- `--text-only` - Use text search only (faster)

Example: `/recall hook patterns --k 10 --vector-only`

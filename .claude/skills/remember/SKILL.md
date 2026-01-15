---
name: remember
description: Store a learning, pattern, or decision in the memory system for future recall
allowed-tools: [Bash, Read]
---

# Remember - Store Learning in Memory

Store a learning, pattern, or decision in the memory system for future recall.

## Usage

```
/remember <what you learned>
```

Or with explicit type:

```
/remember --type WORKING_SOLUTION <what you learned>
```

## Examples

```
/remember TypeScript hooks require npm install before they work
/remember --type ARCHITECTURAL_DECISION Session affinity uses terminal PID
/remember --type FAILED_APPROACH Don't use subshell for store_learning command
```

## What It Does

1. Stores the learning in PostgreSQL with BGE embeddings
2. Auto-detects learning type if not specified
3. Extracts tags from content
4. Returns confirmation with ID

## Learning Types

| Type | Use For |
|------|---------|
| `WORKING_SOLUTION` | Fixes, solutions that worked (default) |
| `ARCHITECTURAL_DECISION` | Design choices, system structure |
| `CODEBASE_PATTERN` | Patterns discovered in code |
| `FAILED_APPROACH` | What didn't work |
| `ERROR_FIX` | Specific error resolutions |

## Execution

When this skill is invoked, run:

```bash
cd $CLAUDE_OPC_DIR && PYTHONPATH=. uv run python scripts/core/store_learning.py \
  --session-id "manual-$(date +%Y%m%d-%H%M)" \
  --type <TYPE or WORKING_SOLUTION> \
  --content "<ARGS>" \
  --context "manual entry via /remember" \
  --confidence medium
```

## Auto-Type Detection

If no `--type` specified, infer from content:
- Contains "error", "fix", "bug" → ERROR_FIX
- Contains "decided", "chose", "architecture" → ARCHITECTURAL_DECISION
- Contains "pattern", "always", "convention" → CODEBASE_PATTERN
- Contains "failed", "didn't work", "don't" → FAILED_APPROACH
- Default → WORKING_SOLUTION

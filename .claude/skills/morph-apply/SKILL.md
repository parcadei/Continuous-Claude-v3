---
name: morph-apply
description: Fast file editing via Morph Apply API (10,500 tokens/sec, 98% accuracy)
allowed-tools: [Bash, Read]
---

# Morph Fast Apply

Fast, AI-powered file editing using the Morph Apply API. Edit files without reading them first. Processes at 10,500 tokens/sec with 98% accuracy.

## When to Use

- Fast file edits without reading entire file first
- Batch edits to a file (multiple changes in one operation)
- When you know what to change but file is large
- Large files where reading would consume too many tokens

## Key Pattern: Code Markers

Use `// ... existing code ...` (or language-appropriate comments) to mark where edits go:

```python
# ... existing code ...
try:
    result = process()
except Exception as e:
    log.error(e)
# ... existing code ...
```

The API intelligently places your edit in the right location.

## Usage

### Add error handling
```bash
uv run python -m runtime.harness scripts/morph_apply.py \
    --file "src/auth.py" \
    --instruction "Add error handling to login function" \
    --code_edit "# ... existing code ...
try:
    user = authenticate(credentials)
except AuthError as e:
    log.error(f'Auth failed: {e}')
    raise
# ... existing code ..."
```

### Add logging
```bash
uv run python -m runtime.harness scripts/morph_apply.py \
    --file "src/api.py" \
    --instruction "Add debug logging" \
    --code_edit "# ... existing code ...
logger.debug(f'Processing request: {request.id}')
# ... existing code ..."
```

### TypeScript example
```bash
uv run python -m runtime.harness scripts/morph_apply.py \
    --file "src/types.ts" \
    --instruction "Add user validation" \
    --code_edit "// ... existing code ...
if (!user) throw new Error('User not found');
if (!user.isActive) throw new Error('User inactive');
// ... existing code ..."
```

## Parameters

| Parameter | Description |
|-----------|-------------|
| `--file` | File path to edit (required) |
| `--instruction` | Human description of the change (required) |
| `--code_edit` | Code snippet with markers showing where to place edit (required) |

## vs Claude's Edit Tool

| Tool | Best For |
|------|----------|
| **morph-apply** | Fast edits, don't need to read file first, large files, batch edits |
| **Claude Edit** | Small precise edits when file is already in context |

**Use morph-apply when:**
- File is not in context and reading it would be expensive
- File is very large (>500 lines)
- Making multiple related edits at once
- You know the context of the change (function name, class, etc.)

**Use Claude Edit when:**
- File is already in context from prior Read
- Very precise edits requiring exact old/new string matching
- Small files (<200 lines)

## MCP Server Required

Requires `morph` server in mcp_config.json with `MORPH_API_KEY`.

## Performance

- **Speed**: 10,500 tokens/sec
- **Accuracy**: 98% correct placement
- **Token savings**: Don't need to read entire file first

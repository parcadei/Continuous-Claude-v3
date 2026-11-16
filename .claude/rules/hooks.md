---
globs: [".claude/hooks/**/*"]
---

# Hook Development Rules

When working with files in `.claude/hooks/`:

## Pattern
Shell wrapper (.sh) → TypeScript (.ts) via `npx tsx`

## Shell Wrapper Template
```bash
#!/bin/bash
set -e
cd "$CLAUDE_PROJECT_DIR/.claude/hooks"
cat | npx tsx <handler>.ts
```

## TypeScript Handler Pattern
```typescript
interface HookInput {
  // Event-specific fields
}

async function main() {
  const input: HookInput = JSON.parse(await readStdin());

  // Process input

  const output = {
    result: 'continue',  // or 'block'
    message: 'Optional system reminder'
  };

  console.log(JSON.stringify(output));
}
```

## Hook Events
- **PreToolUse** - Before tool execution (can block)
- **PostToolUse** - After tool execution
- **UserPromptSubmit** - Before processing user prompt
- **PreCompact** - Before context compaction
- **SessionStart** - On session start/resume/compact
- **Stop** - When agent finishes

## Testing
Test hooks manually:
```bash
echo '{"type": "resume"}' | .claude/hooks/session-start-continuity.sh
```

## Registration
Add hooks to `.claude/settings.json`:
```json
{
  "hooks": {
    "EventName": [{
      "matcher": ["pattern"],  // Optional
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/hook.sh"
      }]
    }]
  }
}
```

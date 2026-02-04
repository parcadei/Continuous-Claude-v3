# Hook Subsystem

## Lifecycle

```
SessionStart ──────→ Runs once when Claude session begins
                     • session-start-docker (ensure services)
                     • session-start-parallel (setup tasks)

UserPromptSubmit ──→ Runs when user sends a message
                     • heartbeat (session keepalive)
                     • memory-awareness (inject relevant memories)
                     • skill-activation (detect skill triggers)

PreToolUse ────────→ Runs BEFORE each tool execution
                     • file-claims (distributed locking) [CAN BLOCK]
                     • task-router (suggest better agent)
                     • explore-to-scout (redirect Explore→scout)

PostToolUse ───────→ Runs AFTER each tool execution
                     • epistemic-reminder (verify grep claims)
                     • roadmap-completion (track progress)
                     • git-commit-roadmap (log commits to ROADMAP)
                     • post-plan-roadmap (update ROADMAP on plan exit)
                     • prd-roadmap-sync (sync PRD files to ROADMAP)
```

## Hook Response Schema

```typescript
interface HookResponse {
  // Continue normally (optional message)
  continue?: boolean;
  message?: string;

  // Block the tool (PreToolUse only)
  decision?: "block";
  reason?: string;

  // Modify tool input
  modifiedInput?: object;
}
```

## Key Hooks

| Hook | Trigger | Can Block | Purpose |
|------|---------|-----------|---------|
| file-claims | PreToolUse:Edit | Yes | Prevent file conflicts |
| task-router | PreToolUse:Task | No | Suggest better agent |
| explore-to-scout | PreToolUse:Task | No | Redirect Explore→scout |
| memory-awareness | UserPromptSubmit | No | Inject relevant memories |
| heartbeat | UserPromptSubmit | No | Session keepalive |
| epistemic-reminder | PostToolUse:Grep | No | Verify before claiming |

## File Locations

```
~/.claude/hooks/
├── src/                 # TypeScript source
│   ├── file-claims.ts
│   ├── memory-awareness.ts
│   └── ...
├── dist/                # Compiled JavaScript
│   └── *.js
├── build.sh             # Compile TS → JS
└── package.json
```

## Creating a Hook

1. Create `~/.claude/hooks/src/my-hook.ts`
2. Export hook function matching lifecycle
3. Run `~/.claude/hooks/build.sh`
4. Register in `~/.claude/settings.json`

```typescript
// Example PreToolUse hook
export async function preToolUse(input: {
  tool_name: string;
  tool_input: object;
}): Promise<{ continue: boolean; message?: string }> {
  if (input.tool_name === "Edit") {
    // Check something
    return { continue: true, message: "Checked!" };
  }
  return { continue: true };
}
```

## Registration

In `~/.claude/settings.json`:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": ["node ~/.claude/hooks/dist/file-claims.js"]
      }
    ]
  }
}
```

## Debugging Hooks

```bash
# Test hook directly
echo '{"tool_name":"Edit","tool_input":{}}' | node ~/.claude/hooks/dist/my-hook.js

# Check hook output in Claude
# Hooks log to stderr, visible in terminal
```

## Common Patterns

| Pattern | Use Case |
|---------|----------|
| Block + suggest | PreToolUse blocks, suggests alternative |
| Inject context | UserPromptSubmit adds info to message |
| Log + continue | PostToolUse logs without modifying |
| Redirect | PreToolUse modifies tool input |

## Deep Dive

For comprehensive hook documentation (718 lines) with exit codes, MCP patterns, and examples:
→ `~/continuous-claude/docs/hooks/README.md`

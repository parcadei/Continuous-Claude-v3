# Hook System

Claude Code lifecycle integration for custom behavior during session events, tool execution, and multi-agent orchestration.

## Overview

Hooks intercept Claude Code events to enable:
- **Context injection** - Add relevant information before tool execution
- **State persistence** - Load/save session state across clears and compacts
- **Agent coordination** - Orchestrate multi-agent patterns (swarm, jury, pipeline, etc.)
- **Validation** - Block dangerous operations or enforce quality gates

## Available Hooks

| Hook | Event | Can Block? | Use Case |
|------|-------|------------|----------|
| **PreToolUse** | Before tool executes | Yes | Inject context, block dangerous tools |
| **PostToolUse** | After tool completes | Partial | Record results, trigger side effects |
| **SubagentStart** | Agent spawned (Task tool) | No | Initialize agent state, inject context |
| **SubagentStop** | Agent finished | Yes | Cleanup, track completion |
| **Stop** | Session ending | Yes | Block until ready, force continuation |
| **SessionStart** | Session begins | No | Load state from ledger/handoffs |
| **SessionEnd** | Session ends | No | Save state, cleanup, trigger learnings |
| **UserPromptSubmit** | User input received | Yes | Validate input, inject context |
| **PreCompact** | Before context compaction | No | Save state before compression |
| **PermissionRequest** | Permission dialog shows | Yes | Auto-approve/deny operations |
| **Notification** | System notification | No | Custom alert handling |

---

## Hook Development

### File Structure

Each hook follows the shell wrapper + TypeScript pattern:

```
.claude/hooks/
  pre-tool-use.sh          # Shell wrapper
  src/
    pre-tool-use.ts        # TypeScript handler
    shared/
      types.ts             # Shared type definitions
      pattern-router.ts    # Pattern detection utilities
      db-utils.ts          # Database query utilities
    patterns/
      swarm.ts             # Swarm pattern handlers
      jury.ts              # Jury pattern handlers
      ...
  dist/
    pre-tool-use.mjs       # Bundled for production (optional)
```

### Shell Wrapper Template

```bash
#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
cat | npx tsx src/my-hook.ts
```

Or for bundled production hooks:

```bash
#!/bin/bash
set -e
cd "$HOME/.claude/hooks"
cat | node dist/my-hook.mjs
```

### TypeScript Handler Pattern

```typescript
import { readFileSync } from 'fs';

interface HookInput {
  session_id: string;
  hook_event_name: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_response?: Record<string, unknown>;
  // Additional fields per hook type
}

interface HookOutput {
  result: 'continue' | 'block';
  message?: string;      // Injected into Claude's context
  reason?: string;       // For blocking decisions
}

function readStdin(): string {
  return readFileSync(0, 'utf-8');
}

async function main() {
  const input: HookInput = JSON.parse(readStdin());

  // Process input and determine action
  const output: HookOutput = {
    result: 'continue',
    message: 'Optional context to inject'
  };

  console.log(JSON.stringify(output));
}

main().catch(err => {
  console.error('Error:', err);
  console.log(JSON.stringify({ result: 'continue' }));
});
```

---

## Input Schemas

### PreToolUse

```json
{
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "permission_mode": "default|plan|acceptEdits|bypassPermissions",
  "hook_event_name": "PreToolUse",
  "tool_name": "string",
  "tool_input": {
    "file_path": "string",
    "command": "string"
  },
  "tool_use_id": "string"
}
```

### PostToolUse

```json
{
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "permission_mode": "string",
  "hook_event_name": "PostToolUse",
  "tool_name": "string",
  "tool_input": {},
  "tool_response": {
    "filePath": "string",
    "success": true,
    "output": "string",
    "exitCode": 0
  },
  "tool_use_id": "string"
}
```

**CRITICAL:** The response field is `tool_response`, NOT `tool_result`.

### SubagentStart / SubagentStop

```json
{
  "session_id": "string",
  "agent_id": "string|null",
  "agent_type": "string"
}
```

### Stop

```json
{
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "permission_mode": "string",
  "hook_event_name": "Stop",
  "stop_hook_active": false
}
```

**CRITICAL:** Check `stop_hook_active: true` to prevent infinite loops!

### SessionStart

```json
{
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "permission_mode": "string",
  "hook_event_name": "SessionStart",
  "source": "startup|resume|clear|compact"
}
```

### SessionEnd

```json
{
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "permission_mode": "string",
  "hook_event_name": "SessionEnd",
  "reason": "clear|logout|prompt_input_exit|other"
}
```

### UserPromptSubmit

```json
{
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "permission_mode": "string",
  "hook_event_name": "UserPromptSubmit",
  "prompt": "string"
}
```

### PreCompact

```json
{
  "session_id": "string",
  "transcript_path": "string",
  "cwd": "string",
  "permission_mode": "string",
  "hook_event_name": "PreCompact",
  "trigger": "manual|auto",
  "custom_instructions": "string"
}
```

---

## Output Schema

All hooks return the same basic structure:

```typescript
interface HookOutput {
  result: 'continue' | 'block';
  message?: string;      // Added to Claude's context
  reason?: string;       // Explanation for blocking
}
```

### Blocking Behavior

| Hook | Block Effect |
|------|-------------|
| PreToolUse | Tool execution prevented, reason shown to Claude |
| PostToolUse | Partial - can prompt Claude to fix issues |
| UserPromptSubmit | Prompt discarded, reason shown to user only |
| Stop | Forces Claude to continue with reason as prompt |
| SubagentStop | Can force continuation |

### Exit Code 2

Exit code 2 provides an alternative blocking mechanism:
- **stdout:** IGNORED
- **stderr:** Shown to Claude (PreToolUse, Stop) or user (UserPromptSubmit)

---

## Registration

Register hooks in `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Task",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/pre-tool-use.sh",
            "timeout": 60
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/typescript-preflight.sh",
            "timeout": 40
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "resume|compact|clear",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/session-start-continuity.sh"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/session-end-cleanup.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/stop-coordinator.sh"
          }
        ]
      }
    ],
    "SubagentStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/subagent-start.sh"
          }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/subagent-stop.sh"
          }
        ]
      }
    ]
  }
}
```

### Matcher Patterns

| Pattern | Matches |
|---------|---------|
| `Bash` | Exactly Bash tool |
| `Edit\|Write` | Edit OR Write |
| `Read.*` | Regex: Read* |
| `mcp__.*__write.*` | MCP write tools |
| `*` | All tools |
| `startup\|resume\|clear\|compact` | SessionStart sources |
| `manual\|auto` | PreCompact triggers |

**Case-sensitive:** `Bash` does not match `bash`.

### Events Requiring Matchers

- PreToolUse - YES (tool name regex)
- PostToolUse - YES (tool name regex)
- PermissionRequest - YES (tool name regex)
- SessionStart - YES (source: startup|resume|clear|compact)
- PreCompact - YES (trigger: manual|auto)
- Notification - Optional (notification_type)

### Events Without Matchers

- UserPromptSubmit
- SessionEnd
- Stop
- SubagentStart
- SubagentStop

---

## Environment Variables

### Available to All Hooks

| Variable | Description |
|----------|-------------|
| `CLAUDE_PROJECT_DIR` | Absolute path to project root |
| `CLAUDE_CODE_REMOTE` | "true" if remote, empty if local |

### SessionStart Only

| Variable | Description |
|----------|-------------|
| `CLAUDE_ENV_FILE` | Path to write `export VAR=value` lines for persistent env vars |

---

## Pattern-Aware Hooks

When hooks are triggered during multi-agent orchestration patterns, additional environment variables provide pattern context.

### Supported Patterns

- `swarm` - Multiple agents exploring in parallel, broadcasting findings
- `jury` - Independent agents voting on a decision
- `pipeline` - Sequential stages passing artifacts downstream
- `generator_critic` - Iterative generation and critique cycles
- `hierarchical` - Coordinator delegating to specialists
- `map_reduce` - Fan-out mappers, fan-in reducer
- `blackboard` - Shared knowledge base with contributors
- `circuit_breaker` - Primary with fallback on failure
- `chain_of_responsibility` - Handler chain with priority
- `adversarial` - Advocate, adversary, and judge
- `event_driven` - Publishers and subscribers

### Pattern Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PATTERN_TYPE` | Active orchestration pattern | `swarm`, `jury`, `pipeline` |
| `PATTERN_ID` | Unique ID for this pattern execution | `swarm-abc123` |
| `AGENT_ROLE` | Role within pattern | `coordinator`, `worker`, `juror` |
| `SWARM_ID` | Swarm identifier (swarm pattern) | `research-swarm-001` |
| `JURY_ID` | Jury identifier (jury pattern) | `review-jury-xyz` |
| `TOTAL_JURORS` | Number of jurors (jury pattern) | `5` |
| `JUROR_INDEX` | Current juror number (jury pattern) | `2` |
| `PIPELINE_STAGE_INDEX` | Current stage (pipeline pattern) | `3` |
| `PIPELINE_TOTAL_STAGES` | Total stages (pipeline pattern) | `5` |
| `HIERARCHY_LEVEL` | Nesting depth (hierarchical pattern) | `0`, `1`, `2` |
| `GC_ITERATION` | Iteration count (generator_critic) | `1`, `2`, `3` |

### Pattern Handler Structure

Hooks route to pattern-specific handlers based on `PATTERN_TYPE`:

```typescript
import { detectPattern } from './shared/pattern-router.js';
import * as swarm from './patterns/swarm.js';
import * as jury from './patterns/jury.js';
// ... other patterns

async function main() {
  const input = JSON.parse(readStdin());
  const patternType = detectPattern();

  let output: HookOutput;

  switch (patternType) {
    case 'swarm':
      output = await swarm.onPreToolUse(input);
      break;
    case 'jury':
      output = await jury.onPreToolUse(input);
      break;
    // ... other patterns
    default:
      output = { result: 'continue' };
  }

  console.log(JSON.stringify(output));
}
```

### Pattern Handler Example: Swarm

```typescript
// .claude/hooks/src/patterns/swarm.ts

export async function onPreToolUse(input: PreToolUseInput): Promise<HookOutput> {
  const swarmId = process.env.SWARM_ID;
  if (!swarmId) return { result: 'continue' };

  // Query broadcasts from other agents
  const broadcasts = await queryBroadcasts(swarmId, input.session_id);

  if (broadcasts.length > 0) {
    let message = '\n--- SWARM BROADCASTS ---\n';
    for (const b of broadcasts) {
      message += `[${b.type}] from ${b.sender}: ${JSON.stringify(b.payload)}\n`;
    }
    return { result: 'continue', message };
  }

  return { result: 'continue' };
}

export async function onStop(input: StopInput): Promise<HookOutput> {
  if (input.stop_hook_active) return { result: 'continue' };

  const swarmId = process.env.SWARM_ID;
  const counts = await getSwarmCounts(swarmId);

  if (counts.done < counts.total) {
    return {
      result: 'block',
      message: `Waiting for ${counts.total - counts.done} agents to complete.`
    };
  }

  return { result: 'continue' };
}
```

### Coordination Database

Pattern-aware hooks use SQLite for state tracking:

**Location:** `$CLAUDE_PROJECT_DIR/.claude/cache/agentica-coordination/coordination.db`

**Key Tables:**

```sql
CREATE TABLE broadcasts (
  id TEXT PRIMARY KEY,
  swarm_id TEXT,
  sender_agent TEXT,
  broadcast_type TEXT,  -- 'finding', 'question', 'blocker', 'done', 'started'
  payload TEXT,         -- JSON
  created_at TEXT
);

CREATE TABLE jury_votes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  jury_id TEXT,
  juror_id TEXT,
  vote TEXT,
  reasoning TEXT,
  created_at TEXT
);

CREATE TABLE pipeline_stages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pipeline_id TEXT,
  stage_index INTEGER,
  stage_name TEXT,
  status TEXT,          -- 'pending', 'running', 'completed'
  output TEXT,          -- JSON
  created_at TEXT
);

CREATE TABLE pipeline_artifacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pipeline_id TEXT,
  stage_index INTEGER,
  artifact_type TEXT,
  artifact_path TEXT,
  artifact_content TEXT,
  created_at TEXT
);
```

---

## Testing Hooks

### Manual Test Commands

```bash
# PreToolUse (Bash)
echo '{"tool_name":"Bash","tool_input":{"command":"ls"},"session_id":"test"}' | \
  .claude/hooks/pre-tool-use.sh

# PostToolUse (Write)
echo '{"tool_name":"Write","tool_input":{"file_path":"test.md"},"tool_response":{"success":true},"session_id":"test"}' | \
  .claude/hooks/post-tool-use.sh

# SessionStart (resume)
echo '{"hook_event_name":"SessionStart","source":"resume","session_id":"test"}' | \
  .claude/hooks/session-start-continuity.sh

# SessionEnd
echo '{"hook_event_name":"SessionEnd","reason":"clear","session_id":"test"}' | \
  .claude/hooks/session-end-cleanup.sh

# Stop
echo '{"hook_event_name":"Stop","stop_hook_active":false,"session_id":"test"}' | \
  .claude/hooks/stop-coordinator.sh

# SubagentStart (with swarm context)
PATTERN_TYPE=swarm SWARM_ID=test-swarm \
  echo '{"session_id":"agent-1","agent_id":"agent-1"}' | \
  .claude/hooks/subagent-start.sh

# SubagentStop (with swarm context)
PATTERN_TYPE=swarm SWARM_ID=test-swarm \
  echo '{"session_id":"agent-1","agent_id":"agent-1"}' | \
  .claude/hooks/subagent-stop.sh
```

### Rebuild After TypeScript Edits

```bash
cd .claude/hooks
npx esbuild src/my-hook.ts \
  --bundle --platform=node --format=esm \
  --outfile=dist/my-hook.mjs
```

### Query Coordination Database

```bash
# Check broadcasts
sqlite3 ".claude/cache/agentica-coordination/coordination.db" \
  "SELECT * FROM broadcasts WHERE swarm_id = 'my-swarm' ORDER BY created_at;"

# Check jury votes
sqlite3 ".claude/cache/agentica-coordination/coordination.db" \
  "SELECT * FROM jury_votes WHERE jury_id = 'my-jury';"

# Check agent completion status
sqlite3 ".claude/cache/agentica-coordination/coordination.db" \
  "SELECT swarm_id, COUNT(DISTINCT sender_agent) as agents, \
          SUM(CASE WHEN broadcast_type='done' THEN 1 ELSE 0 END) as done \
   FROM broadcasts GROUP BY swarm_id;"
```

---

## Common Patterns

### Block Dangerous Files (PreToolUse)

```python
#!/usr/bin/env python3
import json, sys

data = json.load(sys.stdin)
path = data.get('tool_input', {}).get('file_path', '')

BLOCKED = ['.env', 'secrets.json', '.git/']
if any(b in path for b in BLOCKED):
    print(json.dumps({
        "result": "block",
        "reason": f"Blocked: {path} is protected"
    }))
else:
    print('{"result": "continue"}')
```

### Auto-Format Files (PostToolUse)

```bash
#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ "$FILE" == *.ts ]] || [[ "$FILE" == *.tsx ]]; then
  npx prettier --write "$FILE" 2>/dev/null
fi

echo '{"result": "continue"}'
```

### Inject Git Context (UserPromptSubmit)

```bash
#!/bin/bash
echo "Git status:"
git status --short 2>/dev/null || echo "(not a git repo)"
echo ""
echo "Recent commits:"
git log --oneline -5 2>/dev/null || echo "(no commits)"
```

### Force Test Verification (Stop)

```python
#!/usr/bin/env python3
import json, sys, subprocess

data = json.load(sys.stdin)

# Prevent infinite loops
if data.get('stop_hook_active'):
    print('{"result": "continue"}')
    sys.exit(0)

# Check if tests pass
result = subprocess.run(['npm', 'test'], capture_output=True)
if result.returncode != 0:
    print(json.dumps({
        "result": "block",
        "reason": "Tests are failing. Please fix before stopping."
    }))
else:
    print('{"result": "continue"}')
```

### Load Continuity Ledger (SessionStart)

```typescript
// On resume/clear/compact, load session state from ledger
if (sessionType !== 'startup') {
  const ledgerContent = fs.readFileSync(ledgerPath, 'utf-8');
  return {
    result: 'continue',
    hookSpecificOutput: {
      hookEventName: 'SessionStart',
      additionalContext: `Continuity ledger:\n\n${ledgerContent}`
    }
  };
}
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Hook not firing | Check registration in settings.json, verify matcher pattern |
| Permission denied | Add `chmod +x` to shell wrapper |
| TypeScript changes not applied | Rebuild bundle with esbuild |
| Using wrong field name | Use `tool_response` not `tool_result` |
| Output not valid JSON | Ensure single JSON object on stdout |
| Infinite loop in Stop hook | Check `stop_hook_active` before blocking |
| Path issues | Use `$CLAUDE_PROJECT_DIR` for project paths |
| Pattern not detected | Verify `PATTERN_TYPE` env var is set |
| Database queries failing | Check coordination.db exists at expected path |

### Debugging Checklist

- [ ] Hook registered in settings.json?
- [ ] Shell script has `+x` permission?
- [ ] Bundle rebuilt after TS changes?
- [ ] Using `tool_response` not `tool_result`?
- [ ] Output is valid JSON (or plain text for UserPromptSubmit)?
- [ ] Checking `stop_hook_active` in Stop hooks?
- [ ] Using `$CLAUDE_PROJECT_DIR` for paths?
- [ ] Pattern env vars set when testing pattern hooks?

---

## Key Learnings

1. **Field names matter** - Use `tool_response` not `tool_result`
2. **Output format** - `result: "block"` + `reason` for blocking
3. **Exit code 2** - stderr goes to Claude/user, stdout IGNORED
4. **Rebuild bundles** - TypeScript source edits need compilation
5. **Test manually** - `echo '{}' | ./hook.sh` before relying on it
6. **Check outputs first** - Verify files exist before editing code
7. **Graceful degradation** - Return `{ result: 'continue' }` on errors
8. **Validate IDs** - Use `isValidId()` for swarm/agent/pattern IDs to prevent injection
9. **Detached spawn** - Use for fire-and-forget operations (learning extraction)
10. **Prune state** - Remove old entries to prevent ledger/DB bloat

---

## See Also

- `/debug-hooks` - Systematic debugging workflow skill
- `.claude/rules/hooks.md` - Hook development rules
- `.claude/skills/hook-developer/SKILL.md` - Complete reference
- `scripts/agentica/PATTERNS.md` - Multi-agent orchestration patterns
- `.claude/hooks/src/patterns/` - Pattern handler implementations

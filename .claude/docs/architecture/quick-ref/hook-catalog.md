# Hook Catalog

> 100+ hooks organized by lifecycle

## By Lifecycle

### SessionStart

| Hook | Purpose | Blocks |
|------|---------|--------|
| `session-start-docker.mjs` | Ensure Docker services running | No |
| `session-start-parallel.mjs` | Parallel setup tasks | No |
| `session-register.mjs` | Register in coordination DB | No |
| `session-start-continuity.mjs` | Load handoff ledger | No |
| `session-start-init-check.mjs` | Verify infrastructure | No |
| `session-start-tree-daemon.ps1` | Start knowledge tree watcher | No |
| `session-start-memory-daemon.ps1` | Start memory daemon | No |

### UserPromptSubmit

| Hook | Purpose | Blocks |
|------|---------|--------|
| `heartbeat.mjs` | Session keepalive to database | No |
| `memory-awareness.mjs` | **Inject relevant memories** | No |
| `user-confirmation-detector.mjs` | **Capture "it's fixed" signals** | No |
| `maestro-state-manager.mjs` | **Track maestro workflow state** | No |
| `skill-activation-prompt.mjs` | Detect skill triggers | No |
| `guardrail-enforcer.mjs` | Apply guardrails | No |

### PreToolUse

| Hook | Matches | Purpose | Blocks |
|------|---------|---------|--------|
| `file-claims.mjs` | Edit | Distributed file locking | **Yes** |
| `ralph-delegation-enforcer.mjs` | Task | **Enforce ralph routing** | **Yes** |
| `git-memory-check.mjs` | Bash | **Check memory before git** | **Yes** |
| `explore-to-scout.mjs` | Task | Redirect Explore→scout | No |
| `pre-compact-extract.mjs` | Compact | **Extract learnings before compression** | No |
| `task-router.mjs` | Task | Suggest better agent | No |
| `pre-tool-knowledge.mjs` | Task | Inject knowledge tree context | No |
| `hook-auto-execute.mjs` | * | Auto-run blocked commands | No |

### PostToolUse

| Hook | Matches | Purpose | Blocks |
|------|---------|---------|--------|
| `pageindex-watch.mjs` | Write\|Edit | **Rebuild PageIndex on .md changes** | No |
| `smarter-everyday.mjs` | * | **Detect problem resolution patterns** | No |
| `session-end-extract.mjs` | SessionEnd | **Final learning extraction sweep** | No |
| `agent-error-capture.mjs` | Task | **Log agent failures** | No |
| `epistemic-reminder.mjs` | Grep | Warn about grep claims | No |
| `roadmap-completion.mjs` | TaskUpdate | Mark goals complete | No |
| `post-plan-roadmap.mjs` | ExitPlanMode | Update ROADMAP from plan | No |
| `prd-roadmap-sync.mjs` | Write\|Edit | Sync PRD/Tasks with ROADMAP | No |
| `git-commit-roadmap.mjs` | Bash | **Add commits to ROADMAP Completed** | No |
| `sync-to-repo.mjs` | Write\|Edit | Auto-sync to team repo | No |

### PreCompact

| Hook | Purpose | Blocks |
|------|---------|--------|
| `pre-compact-extract.mjs` | Extract learnings before context compression | No |

### SessionEnd

| Hook | Purpose | Blocks |
|------|---------|--------|
| `session-end-extract.mjs` | Final learning extraction sweep | No |

## Blocking Hooks (3 Total)

Only PreToolUse hooks can block. Currently **3 hooks** can block:

| Hook | Trigger | When It Blocks |
|------|---------|----------------|
| `file-claims.mjs` | Edit | File claimed by another session |
| `ralph-delegation-enforcer.mjs` | Task | Non-Ralph agents during Ralph workflow |
| `git-memory-check.mjs` | Bash | Git commands that violate stored preferences |

When blocked:

```json
{
  "decision": "block",
  "reason": "File claimed by another session"
}
```

The tool execution is prevented and reason shown.

## Learning Extraction Hooks

These hooks capture learnings for the memory system:

| Hook | When | What It Captures |
|------|------|------------------|
| `memory-awareness.mjs` | User prompt | Injects relevant past learnings |
| `smarter-everyday.mjs` | Post tool use | Problem resolution patterns |
| `user-confirmation-detector.mjs` | User prompt | "It's fixed", "that worked" signals |
| `pre-compact-extract.mjs` | Pre-compact | Learnings before context compression |
| `session-end-extract.mjs` | Session end | Final sweep for unextracted learnings |

## Workflow Hooks

| Hook | Purpose |
|------|---------|
| `maestro-state-manager.mjs` | Track maestro workflow state across prompts |
| `ralph-delegation-enforcer.mjs` | Ensure tasks route through ralph agents |

### ROADMAP Hooks (4 total)

| Hook | Trigger | ROADMAP Section |
|------|---------|-----------------|
| `post-plan-roadmap.mjs` | ExitPlanMode | Current Focus + Recent Planning |
| `prd-roadmap-sync.mjs` | Write\|Edit PRD files | Planned |
| `git-commit-roadmap.mjs` | Bash git commit | Completed |
| `roadmap-completion.mjs` | TaskUpdate completed | Current Focus → Completed |

## File Locations

```
~/.claude/hooks/
├── src/              # TypeScript source (100+ files)
├── dist/             # Compiled JS (run these)
├── build.sh          # Compiler script
└── package.json
```

## Registration

In `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit",
        "hooks": ["node ~/.claude/hooks/dist/file-claims.mjs"]
      },
      {
        "matcher": "Task",
        "hooks": ["node ~/.claude/hooks/dist/ralph-delegation-enforcer.mjs"]
      },
      {
        "matcher": "Bash",
        "hooks": ["node ~/.claude/hooks/dist/git-memory-check.mjs"]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": ["node ~/.claude/hooks/dist/pageindex-watch.mjs"]
      },
      {
        "matcher": "Grep",
        "hooks": ["node ~/.claude/hooks/dist/epistemic-reminder.mjs"]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": ["node ~/.claude/hooks/dist/memory-awareness.mjs"]
      },
      {
        "hooks": ["node ~/.claude/hooks/dist/user-confirmation-detector.mjs"]
      }
    ]
  }
}
```

## Common Hook Patterns

| Pattern | Example | Use Case |
|---------|---------|----------|
| Block + reason | file-claims | Prevent conflicts |
| Inject message | memory-awareness | Add context |
| Log + continue | heartbeat | Tracking |
| Modify input | task-router | Redirect |
| Extract data | smarter-everyday | Learning capture |

## Debugging

```bash
# Test hook manually
echo '{"tool_name":"Edit","tool_input":{}}' | \
  node ~/.claude/hooks/dist/my-hook.mjs

# Hook stderr visible in terminal
# Check for JSON parse errors
```

## Creating New Hooks

1. Create `src/my-hook.ts`
2. Export lifecycle function
3. Run `npm run build` or `./build.sh`
4. Add to settings.json
5. Test with echo | node

## Hook Categories

| Category | Hooks | Purpose |
|----------|-------|---------|
| Session | 7 | Setup, teardown, registration |
| Memory | 5 | Learning extraction, recall |
| Workflow | 4 | Ralph, maestro, ROADMAP |
| Safety | 3 | File claims, git checks |
| Context | 3 | Knowledge tree, routing |
| Observability | 2 | Logging, error capture |

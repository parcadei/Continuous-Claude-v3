---
name: token-burn-debug
description: Diagnose and fix token/context burn issues
---

# Token Burn Debugging

## When to Use

- "Why is my usage so high?"
- "Context fills up too fast"
- "What's burning tokens?"

## Step 1: Measure Injected Text Sizes

```bash
wc -c $CLAUDE_PROJECT_DIR/CLAUDE.md $CLAUDE_PROJECT_DIR/.claude/rules/*.md | tail -5
```

Rough conversion: 4 chars ~ 1 token

## Step 2: Audit Hook Surface Area

```bash
cat $CLAUDE_PROJECT_DIR/.claude/settings.json | jq '.hooks'
```

Classify each hook into categories:

| Category | Token Cost | Example |
|----------|------------|---------|
| **Injects into context** | Yes (compounding) | session-start-continuity.sh |
| **Influences behavior** | Indirect (causes extra calls) | skill-activation-prompt |
| **External only** | None | Braintrust tracing hooks |

## Step 3: Find the Big Rocks

Check for large injections on clear/compact:

```bash
# Ledger sizes
wc -c $CLAUDE_PROJECT_DIR/thoughts/ledgers/*.md

# Session-start hook output
echo '{"type": "resume"}' | $CLAUDE_PROJECT_DIR/.claude/hooks/session-start-continuity.sh | wc -c
```

## Step 4: Model Token Consumption

```
(per-call overhead + history + outputs) x (#calls) x (#parallel sessions)
```

- 5 worktrees = 5x everything
- Agent spawns = additional multiplier

## Step 5: Common Fixes

| Problem | Fix |
|---------|-----|
| Large ledger injection | Prune ledger to last N sessions |
| Behavior-nudging hooks | Disable for token-sensitive users |
| Verbose CLAUDE.md | Reduce to essentials |
| Too many agents | Use agents for context-efficiency, not token-efficiency |

## Key Insight

Agents are **context-efficient** (main thread stays smaller), not **token-efficient** (they create additional API calls + overhead).

## Source Sessions

- a8b5a799: Ledger injection (48KB) discovered via Braintrust analysis
- 2243c067: Environment setup consumed significant tokens before actual work
